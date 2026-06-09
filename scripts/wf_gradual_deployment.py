#!/usr/bin/env python3
"""
Mechanism A test — gradual capital deployment via runtime monkey-patch.

LOCAL RESEARCH ONLY. Does NOT modify any production code paths. The
mechanism is a per-period scale applied to position_size_pct before
each period's backtest. Production code never sees these patches.

How it works:
  - Counter tracks the actual period index across the WF run.
  - Before each period, CustomBacktester.configure() scales
    position_size_pct by a ramp factor.
  - After RAMP_PERIODS periods, scale = 1.0 (canonical behavior).
  - Force --no-ai so TPE doesn't interact with the scaling (with AI
    off, configure() is only called on real period sims, not inner
    trial backtests).

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/gradual/2021-01-25/result.pkl \\
    WF_RESULT_JSON=/tmp/gradual/2021-01-25/result.json \\
        caffeinate -i python3 scripts/wf_gradual_deployment.py \\
            --start 2021-01-25 \\
            --ramp-periods 4 \\
            --initial-scale 0.5
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
    p.add_argument('--ramp-periods', type=int, default=4,
                   help='Number of periods to ramp over (default 4 = 8 weeks biweekly)')
    p.add_argument('--initial-scale', type=float, default=0.5,
                   help='Position size scale at period 1 (default 0.5 = half size)')
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--strategy-id', type=int, default=5)
    return p.parse_args()


def install_gradual_patch(ramp_periods, initial_scale):
    """Monkey-patch BacktesterService.run_backtest to scale position_size_pct
    just before the trade loop runs. Patching at this entry point ensures
    we apply the scale AFTER the WF service has finished overwriting
    position_size_pct from its CLI-override args (lines 837-849 of
    walk_forward_service._simulate_period_with_params).

    State carries a per-WF-run period counter. After ramp_periods periods,
    scale = 1.0 (canonical). On each call we save → scale → run → restore
    so the backtester instance can be re-used cleanly."""
    from app.services.backtester import BacktesterService

    state = {'period_index': 0}
    orig_run = BacktesterService.run_backtest

    def scaled_run(self, *args, **kwargs):
        p = state['period_index']
        saved_pct = self.position_size_pct
        try:
            if p < ramp_periods:
                scale = initial_scale + (1.0 - initial_scale) * (p / max(ramp_periods - 1, 1))
                scale = min(scale, 1.0)
                self.position_size_pct = self.position_size_pct * scale
                print(f"   📐 Period {p+1}/{ramp_periods} ramp: "
                      f"size {saved_pct*100:.1f}% → {self.position_size_pct*100:.2f}% "
                      f"(scale={scale:.3f})")
            state['period_index'] += 1
            return orig_run(self, *args, **kwargs)
        finally:
            self.position_size_pct = saved_pct

    BacktesterService.run_backtest = scaled_run
    return state


async def main():
    args = parse_args()

    # Install patch FIRST, before any imports trigger backtester instantiation
    state = install_gradual_patch(args.ramp_periods, args.initial_scale)
    print(f"🔧 Patch installed — ramp_periods={args.ramp_periods}, initial_scale={args.initial_scale}\n")

    # Now import + run
    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.core.database import async_session

    # Compute end date
    end_str = args.end
    if end_str is None:
        sy, sm, sd = args.start.split('-')
        end_str = f"{int(sy) + 5}-{sm}-{sd}"

    # Load pickle
    print(f"📦 Loading pickle: {args.pickle}")
    with gzip.open(args.pickle, 'rb') as f:
        cache = pickle.load(f)
    scanner_service.data_cache = cache
    scanner_service.universe = list(cache.keys())
    print(f"  ✅ {len(cache)} symbols")

    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')

    print(f"\nRunning WF: {args.start} → {end_str}")
    print(f"  Strategy: id={args.strategy_id} (no AI), canonical params, gradual deployment patch active")
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
            # Canonical 5 params (matching the unrampеd sweep)
            max_positions=6,
            position_size_pct=15.0,
            near_50d_high_pct=3.0,
            trailing_stop_pct=12.0,
            dwap_threshold_pct=5.0,
            periods_limit=0,
        )
    dur = time.time() - t0

    pkl_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/gradual_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/gradual_{args.start}/result.json')
    os.makedirs(os.path.dirname(pkl_out), exist_ok=True)
    with open(pkl_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_out, 'w') as f:
        json.dump({
            'start_date': args.start,
            'ramp_periods': args.ramp_periods,
            'initial_scale': args.initial_scale,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
        }, f, indent=2, default=str)

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct/100) ** (1/years) - 1
    print(f"\n{'=' * 60}")
    print(f"RESULTS — gradual deployment (ramp={args.ramp_periods}, initial={args.initial_scale})")
    print(f"{'=' * 60}")
    print(f"  Total return:    {result.total_return_pct:+.2f}%")
    print(f"  Sharpe:          {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:           {result.max_drawdown_pct:.2f}%")
    print(f"  Benchmark:       {getattr(result, 'benchmark_return_pct', 0):+.2f}%")
    print(f"  Trades:          {len(result.trades)}")
    print(f"  Annualized:      {ann*100:+.2f}%")
    print(f"  Duration:        {dur:.0f}s")
    print(f"  Configure calls: {state['period_index']} (expect ~131 for 5y biweekly)")


if __name__ == '__main__':
    asyncio.run(main())
