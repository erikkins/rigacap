#!/usr/bin/env python3
"""
DD-conditional TRAILING STOP tightening — when WF equity is X% below peak,
tighten the trailing stop from baseline (e.g. 12%) to a tighter value
(e.g. 8%). Restore baseline when equity makes a new peak.

LOCAL RESEARCH ONLY. Monkey-patches BacktesterService.run_backtest at
runtime to override self.trailing_stop_pct for the duration of a single
period's backtest, based on inter-period equity tracking. Production
code paths are untouched.

Why this is different from wf_drawdown_sizing.py:
  - That patch shrank NEW position sizes during DD → didn't reverse
    existing positions' decline, killed recovery upside.
  - This patch tightens the EXIT trail on existing positions → frees
    cash faster during DD, doesn't cap recovery (survivors keep
    full size).

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/dd_tighten/2021-01-25/result.pkl \\
    WF_RESULT_JSON=/tmp/dd_tighten/2021-01-25/result.json \\
        caffeinate -i python3 scripts/wf_dd_tighten_stop.py \\
            --start 2021-01-25 \\
            --dd-threshold 10 \\
            --tight-stop 8
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
    p.add_argument('--dd-threshold', type=float, default=10.0,
                   help='WF equity %% below peak that triggers stop tightening (default 10)')
    p.add_argument('--tight-stop', type=float, default=8.0,
                   help='Tightened trailing-stop %% applied in DD (default 8, baseline 12)')
    p.add_argument('--baseline-stop', type=float, default=12.0,
                   help='Baseline trailing-stop %% to restore out of DD (default 12)')
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--strategy-id', type=int, default=5)
    p.add_argument('--profit-lock', type=float, default=0,
                   help='Tighten trailing stop once position up X%% (default 0=disabled)')
    p.add_argument('--profit-lock-stop', type=float, default=6.0,
                   help='Tightened trail %% from peak after profit-lock triggers (default 6)')
    p.add_argument('--bear-keep-pct', type=float, default=0.0,
                   help='Partial-cash mode: keep top X%% positions during bear regime exit (0=close all)')
    p.add_argument('--regime-cooldown', type=int, default=0,
                   help='Trading days to stay in cash after regime exit before re-entry (0=disabled)')
    p.add_argument('--panic-only', action='store_true',
                   help='Market filter: only exit on panic_crash regime, not on SPY<200MA')
    p.add_argument('--tier1-size', type=int, default=0,
                   help='Top N most-liquid symbols get tier-1 composite-score bonus (0=disabled)')
    p.add_argument('--tier1-bonus', type=float, default=0.0,
                   help='Score bonus added for tier-1 symbols')
    return p.parse_args()


def install_dd_tighten_patch(dd_threshold_pct, tight_stop_pct, baseline_stop_pct,
                              profit_lock_pct=0, profit_lock_stop_pct=6.0,
                              regime_cooldown_days=0):
    """Monkey-patch BacktesterService.run_backtest. Tracks running equity
    across periods. Before each period:
      - Compute DD vs running peak
      - If in DD: override self.trailing_stop_pct = tight_stop_pct/100
      - Else: ensure self.trailing_stop_pct = baseline_stop_pct/100

    State carries equity, peak watermark, in_dd flag, and counters."""
    from app.services.backtester import BacktesterService

    state = {
        'period_index': 0,
        'equity': 100000.0,
        'peak': 100000.0,
        'in_dd': False,
        'tightened_periods': 0,
    }
    orig_run = BacktesterService.run_backtest

    def patched_run(self, *args, **kwargs):
        p = state['period_index']
        dd_pct = (state['peak'] - state['equity']) / state['peak'] * 100 if state['peak'] else 0
        in_dd = dd_pct >= dd_threshold_pct
        was_in_dd = state['in_dd']
        state['in_dd'] = in_dd

        # Force profit-lock on every period (DB-loaded fixed-strategy params
        # don't include CLI overrides; backtester reads self.profit_lock_pct
        # directly at line 746 of backtester.py)
        if profit_lock_pct > 0:
            self.profit_lock_pct = profit_lock_pct
            self.profit_lock_stop_pct = profit_lock_stop_pct
        # Same pattern for regime_cooldown_days — backtester reads
        # self.regime_cooldown_days at line 1163 of backtester.py.
        if regime_cooldown_days > 0:
            self.regime_cooldown_days = regime_cooldown_days

        # Override trailing-stop for THIS period
        saved_trail = self.trailing_stop_pct
        try:
            if in_dd:
                self.trailing_stop_pct = tight_stop_pct / 100.0
                state['tightened_periods'] += 1
                if state['tightened_periods'] <= 5 or state['tightened_periods'] % 10 == 0:
                    print(f"   🛑 Period {p+1}: DD={dd_pct:.1f}% ≥ {dd_threshold_pct:.0f}% → "
                          f"trail {saved_trail*100:.1f}% → {self.trailing_stop_pct*100:.1f}% "
                          f"(equity ${state['equity']:,.0f} / peak ${state['peak']:,.0f})")
            else:
                # Out of DD — make sure trail is at baseline (covers any prior overrides)
                self.trailing_stop_pct = baseline_stop_pct / 100.0
                if was_in_dd:
                    print(f"   ↗️  Period {p+1}: out of DD ({dd_pct:.1f}% < {dd_threshold_pct:.0f}%) → "
                          f"trail restored to {self.trailing_stop_pct*100:.1f}%")

            state['period_index'] += 1
            result = orig_run(self, *args, **kwargs)
        finally:
            self.trailing_stop_pct = saved_trail

        # Update running equity from this period's return
        period_ret = getattr(result, 'total_return_pct', None) or 0
        state['equity'] *= (1.0 + period_ret / 100.0)
        if state['equity'] > state['peak']:
            state['peak'] = state['equity']
        return result

    BacktesterService.run_backtest = patched_run
    return state


async def main():
    args = parse_args()

    # Panic-only market filter: override settings before backtester imports.
    # settings.MARKET_FILTER_PANIC_ONLY is read at line 1157 of backtester.py
    # inside the daily loop, so a runtime monkey-patch works as long as it
    # happens before the WF service kicks off.
    if args.panic_only:
        from app.core.config import settings as _settings
        _settings.MARKET_FILTER_PANIC_ONLY = True

    state = install_dd_tighten_patch(args.dd_threshold, args.tight_stop, args.baseline_stop,
                                     profit_lock_pct=args.profit_lock,
                                     profit_lock_stop_pct=args.profit_lock_stop,
                                     regime_cooldown_days=args.regime_cooldown)
    print(f"🔧 Patch installed — dd_threshold={args.dd_threshold}%, "
          f"tight_stop={args.tight_stop}%, baseline_stop={args.baseline_stop}%\n")

    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.core.database import async_session

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

    print(f"\nRunning WF: {args.start} → {end_str}")
    print(f"  Strategy: id={args.strategy_id} (no AI), canonical params, DD-tighten patch active")
    print()

    t0 = time.time()
    async with async_session() as db:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db,
            start_date=start,
            end_date=end,
            reoptimization_frequency='biweekly',
            min_score_diff=10.0,
            enable_ai_optimization=False,
            max_symbols=args.max_symbols,
            fixed_strategy_id=args.strategy_id,
            n_trials=0,
            carry_positions=True,
            max_positions=6,
            position_size_pct=15.0,
            near_50d_high_pct=3.0,
            trailing_stop_pct=args.baseline_stop,
            dwap_threshold_pct=5.0,
            profit_lock_pct=args.profit_lock,
            profit_lock_stop_pct=args.profit_lock_stop,
            bear_keep_pct=args.bear_keep_pct,
            tier1_size=args.tier1_size,
            tier1_bonus=args.tier1_bonus,
            periods_limit=0,
        )
    dur = time.time() - t0

    pkl_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/dd_tighten_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/dd_tighten_{args.start}/result.json')
    os.makedirs(os.path.dirname(pkl_out), exist_ok=True)
    with open(pkl_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_out, 'w') as f:
        json.dump({
            'start_date': args.start,
            'dd_threshold_pct': args.dd_threshold,
            'tight_stop_pct': args.tight_stop,
            'baseline_stop_pct': args.baseline_stop,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'tightened_periods': state['tightened_periods'],
            'total_periods': state['period_index'],
        }, f, indent=2, default=str)

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
    mdd = result.max_drawdown_pct
    calmar = (ann * 100) / mdd if mdd else 0

    print(f"\n{'=' * 60}")
    print(f"RESULTS — DD-tighten stop "
          f"(threshold={args.dd_threshold}%, tight={args.tight_stop}%, baseline={args.baseline_stop}%)")
    print(f"{'=' * 60}")
    print(f"  Total return:        {result.total_return_pct:+.2f}%")
    print(f"  Annualized:          {ann*100:+.2f}%")
    print(f"  Sharpe:              {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:               {mdd:.2f}%")
    print(f"  Calmar:              {calmar:.2f}")
    print(f"  Benchmark:           {getattr(result, 'benchmark_return_pct', 0):+.2f}%")
    print(f"  Trades:              {len(result.trades)}")
    print(f"  Tightened periods:   {state['tightened_periods']} / {state['period_index']}")
    print(f"  Duration:            {dur:.0f}s")
    print()
    print(f"Baseline Date 3 reference: +186.34% / ann 23.4% / Sharpe 0.87 / MaxDD 33.49% / Calmar 0.70")
    print(f"  Δret:    {result.total_return_pct - 186.34:+.2f}pp")
    print(f"  ΔSharpe: {result.sharpe_ratio - 0.87:+.2f}")
    print(f"  ΔMaxDD:  {mdd - 33.49:+.2f}pp")
    print(f"  ΔCalmar: {calmar - 0.70:+.2f}")


if __name__ == '__main__':
    asyncio.run(main())
