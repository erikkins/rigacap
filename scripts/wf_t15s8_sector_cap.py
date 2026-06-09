#!/usr/bin/env python3
"""
STACK TEST: t15/s8 (DD-conditional trail tighten) + SECTOR CAP.

Two stacked patches:
  1. t15/s8 — when WF synthetic DD >= 15%, tighten trail 12% → 8%
  2. sector cap — limit candidate ticker_list to max N per GICS sector
     before each backtester run; forces diversification, attacks
     structural concentration risk

LOCAL RESEARCH ONLY. Monkey-patches BacktesterService.run_backtest.

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/sector_cap/2021-01-25/result.pkl \\
    WF_RESULT_JSON=/tmp/sector_cap/2021-01-25/result.json \\
        caffeinate -i python3 scripts/wf_t15s8_sector_cap.py \\
            --start 2021-01-25 --sector-cap 2
"""
import argparse, asyncio, gzip, json, os, pickle, sys, time
from datetime import datetime

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
    p.add_argument('--dd-threshold', type=float, default=15.0)
    p.add_argument('--tight-stop', type=float, default=8.0)
    p.add_argument('--baseline-stop', type=float, default=12.0)
    p.add_argument('--sector-cap', type=int, default=2,
                   help='Max candidates per GICS sector (default 2)')
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--strategy-id', type=int, default=5)
    p.add_argument('--max-positions', type=int, default=6,
                   help='Max simultaneous positions (default 6)')
    p.add_argument('--position-size', type=float, default=15.0,
                   help='Position size pct (default 15.0)')
    p.add_argument('--dwap-threshold', type=float, default=5.0,
                   help='DWAP entry threshold pct (default 5.0)')
    p.add_argument('--near-50d-high', type=float, default=3.0,
                   help='Breakout window pct (default 3.0)')
    return p.parse_args()


def install_stacked_patch(dd_threshold_pct, tight_stop_pct, baseline_stop_pct, sector_cap):
    """Two stacked patches via single run_backtest wrapper."""
    from app.services.backtester import BacktesterService
    from app.services.walk_forward_service import walk_forward_service

    state = {
        'period_index': 0,
        'equity': 100000.0,
        'peak': 100000.0,
        'tightened_periods': 0,
        'sector_capped_calls': 0,
        'avg_universe_in': 0,
        'avg_universe_out': 0,
    }
    orig_run = BacktesterService.run_backtest

    def patched_run(self, *args, **kwargs):
        p = state['period_index']

        # --- Sector cap: filter ticker_list BEFORE the backtester scans ---
        if sector_cap > 0:
            tl = kwargs.get('ticker_list')
            if tl is None and len(args) >= 4:
                tl = args[3]
            if tl:
                in_n = len(tl)
                capped = walk_forward_service._apply_sector_cap(list(tl), sector_cap)
                out_n = len(capped)
                if out_n < in_n:
                    state['sector_capped_calls'] += 1
                    state['avg_universe_in'] = (state['avg_universe_in'] * (state['sector_capped_calls'] - 1) + in_n) / state['sector_capped_calls']
                    state['avg_universe_out'] = (state['avg_universe_out'] * (state['sector_capped_calls'] - 1) + out_n) / state['sector_capped_calls']
                    if 'ticker_list' in kwargs:
                        kwargs['ticker_list'] = capped
                    else:
                        args = list(args)
                        args[3] = capped
                        args = tuple(args)
                    if state['sector_capped_calls'] <= 3:
                        print(f"   🧱 Period {p+1}: sector cap {in_n} → {out_n} tickers")

        # --- DD-tighten: override trail based on portfolio-DD ---
        dd_pct = (state['peak'] - state['equity']) / state['peak'] * 100 if state['peak'] else 0
        in_dd = dd_pct >= dd_threshold_pct
        saved_trail = self.trailing_stop_pct
        try:
            if in_dd:
                self.trailing_stop_pct = tight_stop_pct / 100.0
                state['tightened_periods'] += 1
                if state['tightened_periods'] <= 3:
                    print(f"   🛑 Period {p+1}: DD={dd_pct:.1f}% → trail {saved_trail*100:.1f}% → {self.trailing_stop_pct*100:.1f}%")
            else:
                self.trailing_stop_pct = baseline_stop_pct / 100.0
            state['period_index'] += 1
            result = orig_run(self, *args, **kwargs)
        finally:
            self.trailing_stop_pct = saved_trail

        period_ret = getattr(result, 'total_return_pct', None) or 0
        state['equity'] *= (1.0 + period_ret / 100.0)
        if state['equity'] > state['peak']:
            state['peak'] = state['equity']
        return result

    BacktesterService.run_backtest = patched_run
    return state


async def main():
    args = parse_args()
    state = install_stacked_patch(args.dd_threshold, args.tight_stop, args.baseline_stop, args.sector_cap)
    print(f"🔧 Stacked patch — t{args.dd_threshold:.0f}/s{args.tight_stop:.0f} "
          f"+ sector_cap={args.sector_cap}\n")

    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.services.stock_universe import stock_universe_service
    from app.core.database import async_session

    # Load sector cache (S3 fetch + merge into symbol_info). Required for
    # _apply_sector_cap to actually filter — without this call symbol_info
    # is empty and get_symbol_info returns no sector, so the cap silently
    # no-ops. ensure_loaded() does the S3 fetch + merge as a side effect.
    print("🌐 Loading universe + merging sectors cache...")
    await stock_universe_service.ensure_loaded()
    sector_count = sum(1 for v in stock_universe_service.symbol_info.values() if v.get('sector'))
    print(f"  ✅ {len(stock_universe_service.symbol_info)} symbols in metadata, "
          f"{sector_count} with sector data")

    end_str = args.end
    if end_str is None:
        sy, sm, sd = args.start.split('-')
        end_str = f"{int(sy) + 5}-{sm}-{sd}"

    print(f"📦 Loading pickle: {args.pickle}")
    with gzip.open(args.pickle, 'rb') as f:
        cache = pickle.load(f)
    scanner_service.data_cache = cache
    scanner_service.universe = list(cache.keys())
    print(f"  ✅ {len(cache)} symbols")

    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')

    print(f"\nRunning WF: {args.start} → {end_str}\n")

    t0 = time.time()
    async with async_session() as db:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db, start_date=start, end_date=end,
            reoptimization_frequency='biweekly',
            min_score_diff=10.0, enable_ai_optimization=False,
            max_symbols=args.max_symbols, fixed_strategy_id=args.strategy_id,
            n_trials=0, carry_positions=True,
            max_positions=args.max_positions, position_size_pct=args.position_size,
            near_50d_high_pct=args.near_50d_high, trailing_stop_pct=args.baseline_stop,
            dwap_threshold_pct=args.dwap_threshold, periods_limit=0,
        )
    dur = time.time() - t0

    pkl_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/sector_cap_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/sector_cap_{args.start}/result.json')
    os.makedirs(os.path.dirname(pkl_out), exist_ok=True)
    with open(pkl_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_out, 'w') as f:
        json.dump({
            'start_date': args.start,
            'dd_threshold_pct': args.dd_threshold,
            'tight_stop_pct': args.tight_stop,
            'baseline_stop_pct': args.baseline_stop,
            'sector_cap': args.sector_cap,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'tightened_periods': state['tightened_periods'],
            'sector_capped_calls': state['sector_capped_calls'],
            'avg_universe_in': state['avg_universe_in'],
            'avg_universe_out': state['avg_universe_out'],
            'total_periods': state['period_index'],
        }, f, indent=2, default=str)

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
    mdd = result.max_drawdown_pct
    calmar = (ann * 100) / mdd if mdd else 0
    print(f"\n{'=' * 60}")
    print(f"RESULTS — t15/s8 + sector_cap={args.sector_cap}")
    print(f"{'=' * 60}")
    print(f"  Total return:        {result.total_return_pct:+.2f}%")
    print(f"  Annualized:          {ann*100:+.2f}%")
    print(f"  Sharpe:              {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:               {mdd:.2f}%")
    print(f"  Calmar:              {calmar:.2f}")
    print(f"  Tightened periods:   {state['tightened_periods']} / {state['period_index']}")
    print(f"  Sector-capped calls: {state['sector_capped_calls']} / {state['period_index']}")
    if state['sector_capped_calls']:
        print(f"  Avg universe:        {state['avg_universe_in']:.0f} → {state['avg_universe_out']:.0f}")
    print(f"  Duration:            {dur:.0f}s")


if __name__ == '__main__':
    asyncio.run(main())
