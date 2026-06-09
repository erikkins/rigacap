#!/usr/bin/env python3
"""
2b-3 — Validate native per-bar T3 against the monkey-patch's 10-day-cadence T3.

Calls run_backtest as ONE continuous 5y window per start date (no WF service
periods, no monkey-patch). Sets dd_tighten_threshold_pct=10 and
dd_tighten_stop_pct=8 on the BacktesterService instance — the per-bar native
logic added in 2b-2 handles peak tracking + DD-tighten internally.

Compare results to /tmp/sweep_52mon_prod_T3/<start>/result.json (monkey-patch).

Usage:
    source backend/venv/bin/activate
    WF_RESULT_JSON=/tmp/native_t3_2021-01-04/result.json \\
        caffeinate -i python3 scripts/wf_native_t3_sweep.py \\
            --start 2021-01-04 --end 2026-01-04
"""
import argparse, gzip, json, os, pickle, sys, time
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

if not os.environ.get('DATABASE_URL'):
    for line in open(os.path.join(os.path.dirname(__file__), '..', '.env')):
        if line.startswith('DATABASE_URL='):
            os.environ['DATABASE_URL'] = line.strip().split('=', 1)[1]
            break
os.environ.setdefault('LAMBDA_ROLE', 'worker')


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--start', required=True)
    p.add_argument('--end', default=None)
    p.add_argument('--pickle', default='/tmp/parity_test/prod_after_refetch.pkl.gz')
    p.add_argument('--dd-threshold', type=float, default=10.0)
    p.add_argument('--tight-stop', type=float, default=8.0)
    p.add_argument('--baseline-stop', type=float, default=12.0)
    p.add_argument('--max-symbols', type=int, default=200,
                   help='Top N by liquidity (matches WF service default)')
    p.add_argument('--dwap-threshold-pct', type=float, default=None,
                   help='Override DWAP entry threshold % (e.g. 7.0). Default: backtester default (5.0).')
    p.add_argument('--near-50d-high-pct', type=float, default=None,
                   help='Override near-50d-high filter % (e.g. 2.0). Default: backtester default (3.0).')
    p.add_argument('--max-positions', type=int, default=None,
                   help='Override max concurrent positions (e.g. 4). Default: backtester default (6).')
    p.add_argument('--position-size-pct', type=float, default=None,
                   help='Override % of capital per position (e.g. 22.0). Default: backtester default (15.0).')
    return p.parse_args()


def main():
    args = parse_args()

    import asyncio
    from app.services.backtester import BacktesterService
    from app.services.scanner import scanner_service
    from app.services.walk_forward_service import walk_forward_service

    print(f"Loading pickle: {args.pickle}")
    with gzip.open(args.pickle, 'rb') as f:
        cache = pickle.load(f)
    scanner_service.data_cache = cache
    scanner_service.universe = list(cache.keys())
    print(f"  {len(cache)} symbols (full pickle)")

    end_str = args.end
    if end_str is None:
        sy, sm, sd = args.start.split('-')
        end_str = f"{int(sy) + 5}-{sm}-{sd}"
    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')

    # Filter universe to top-N by liquidity as-of start_date (matches what WF
    # service did for the monkey-patch test). Without this the full pickle's
    # 4500+ symbols dominate and entry quality collapses.
    top_symbols = walk_forward_service._get_top_symbols_as_of(start, args.max_symbols)
    scanner_service.data_cache = {s: cache[s] for s in top_symbols if s in cache}
    # Keep SPY for the market regime check even if it's not in top_symbols
    if 'SPY' in cache and 'SPY' not in scanner_service.data_cache:
        scanner_service.data_cache['SPY'] = cache['SPY']
    scanner_service.universe = list(scanner_service.data_cache.keys())
    print(f"  {len(scanner_service.data_cache)} symbols (top-{args.max_symbols} by liquidity)")

    bt = BacktesterService()
    bt.trailing_stop_pct = args.baseline_stop / 100.0
    bt.dd_tighten_threshold_pct = args.dd_threshold
    bt.dd_tighten_stop_pct = args.tight_stop
    # Optional entry-tightening overrides. Note: dwap_threshold_pct is stored
    # as a decimal (0.05 = 5%) but near_50d_high_pct is stored as percent (3.0).
    if args.dwap_threshold_pct is not None:
        bt.dwap_threshold_pct = args.dwap_threshold_pct / 100.0
    if args.near_50d_high_pct is not None:
        bt.near_50d_high_pct = args.near_50d_high_pct
    # Concentration / sizing overrides (Category A levers).
    # max_positions is integer count, position_size_pct stored as decimal (0.15 = 15%).
    if args.max_positions is not None:
        bt.max_positions = args.max_positions
    if args.position_size_pct is not None:
        bt.position_size_pct = args.position_size_pct / 100.0
    print(f"Backtester configured: trail={args.baseline_stop}% baseline, "
          f"tighten to {args.tight_stop}% when portfolio DD ≥ {args.dd_threshold}%, "
          f"dwap_threshold={bt.dwap_threshold_pct*100:.1f}%, "
          f"near_50d_high={bt.near_50d_high_pct:.1f}%")
    print(f"Continuous 5y backtest: {args.start} → {end_str}\n")

    t0 = time.time()
    result = bt.run_backtest(
        start_date=start,
        end_date=end,
        strategy_type='ensemble',
        force_close_at_end=False,
    )
    dur = time.time() - t0

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
    mdd = result.max_drawdown_pct
    calmar = (ann * 100) / mdd if mdd else 0

    # Compute warmup metadata: how many trading days of pickle history exist
    # before `start`. Methodology v2 nominal target is ~130 trading days (~26
    # weeks). Earliest tuning starts may have less; record it so we can
    # audit which results were warmup-light.
    pickle_first_date = None
    if 'SPY' in cache and not cache['SPY'].empty:
        pickle_first_date = pd.Timestamp(cache['SPY'].index.min()).normalize()
    if pickle_first_date is not None and pd.Timestamp(start) > pickle_first_date:
        warmup_calendar_days = (pd.Timestamp(start) - pickle_first_date).days
        warmup_trading_days_est = int(warmup_calendar_days * 252 / 365)
    else:
        warmup_calendar_days = 0
        warmup_trading_days_est = 0

    # Hash the pickle for reproducibility (cheap once at end of run)
    import hashlib
    pickle_sha256 = None
    try:
        with open(args.pickle, 'rb') as fh:
            pickle_sha256 = hashlib.sha256(fh.read()).hexdigest()
    except Exception:
        pass

    # Git SHA for reproducibility. Also flag dirty working tree — the SHA
    # alone doesn't tell us whether local edits were active during the sweep,
    # which would make the result un-reproducible from the SHA.
    git_sha = None
    git_dirty = None
    try:
        import subprocess
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        git_sha = subprocess.check_output(
            ['git', '-C', repo, 'rev-parse', 'HEAD'],
            stderr=subprocess.DEVNULL).decode().strip()
        # Returncode 0 = clean, 1 = dirty
        ret = subprocess.call(
            ['git', '-C', repo, 'diff', '--quiet'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git_dirty = (ret != 0)
    except Exception:
        pass

    json_out = os.environ.get(
        'WF_RESULT_JSON',
        f'/tmp/native_t3_{args.start}/result.json',
    )
    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    result_dict = {
        'start_date': args.start,
        'end_date': end_str,
        'dd_threshold_pct': args.dd_threshold,
        'tight_stop_pct': args.tight_stop,
        'baseline_stop_pct': args.baseline_stop,
        'dwap_threshold_pct': bt.dwap_threshold_pct * 100,
        'near_50d_high_pct': bt.near_50d_high_pct,
        'max_positions': bt.max_positions,
        'position_size_pct': bt.position_size_pct * 100,
        'universe_size': args.max_symbols,
        'total_return_pct': result.total_return_pct,
        'sharpe_ratio': result.sharpe_ratio,
        'max_drawdown_pct': mdd,
        'calmar': calmar,
        'annualized_pct': ann * 100,
        'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
        'trades_count': len(result.trades),
        'duration_sec': dur,
        # Methodology v2 metadata (per ~/rigacap-research/docs/testing_methodology.md)
        'warmup_calendar_days_available': warmup_calendar_days,
        'warmup_trading_days_est': warmup_trading_days_est,
        'warmup_v2_target_met': warmup_trading_days_est >= 130,
        'pickle_path': args.pickle,
        'pickle_sha256': pickle_sha256,
        'git_sha': git_sha,
        'git_dirty': git_dirty,
        'methodology_version': 'v2',
    }
    with open(json_out, 'w') as f:
        json.dump(result_dict, f, indent=2, default=str)

    print(f"{'=' * 60}")
    print(f"NATIVE per-bar T3 — {args.start} → {end_str}")
    print(f"{'=' * 60}")
    print(f"  Total return: {result.total_return_pct:+.2f}%")
    print(f"  Annualized:   {ann*100:+.2f}%")
    print(f"  Sharpe:       {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:        {mdd:.2f}%")
    print(f"  Calmar:       {calmar:.2f}")
    print(f"  Trades:       {len(result.trades)}")
    print(f"  Duration:     {dur:.0f}s")


if __name__ == '__main__':
    main()
