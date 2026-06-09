#!/usr/bin/env python3
"""
VIX-conditional position sizing.

Trigger: read ^VIX close at the start of each WF period.
If VIX >= threshold: scale position_size_pct down by `scale`.
Else: use baseline position_size_pct.

Forward-looking signal (VIX = market's implied 30d vol) instead of
the failed reactive portfolio-DD signal from wf_drawdown_sizing.py.

LOCAL RESEARCH ONLY. Monkey-patches BacktesterService.run_backtest.

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/vix_sizing/2021-01-25/result.pkl \\
    WF_RESULT_JSON=/tmp/vix_sizing/2021-01-25/result.json \\
        caffeinate -i python3 scripts/wf_vix_sizing.py \\
            --start 2021-01-25 --vix-threshold 25 --vix-scale 0.5
"""
import argparse, asyncio, gzip, json, os, pickle, sys, time
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
    p.add_argument('--vix-threshold', type=float, default=25.0,
                   help='VIX level above which to scale down sizing (default 25)')
    p.add_argument('--vix-scale', type=float, default=0.5,
                   help='Position size multiplier when VIX >= threshold (default 0.5 = half)')
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--strategy-id', type=int, default=5)
    return p.parse_args()


def install_vix_patch(vix_df, vix_threshold, vix_scale):
    """Look up VIX at the start date of each period; scale size if elevated."""
    from app.services.backtester import BacktesterService

    state = {
        'period_index': 0,
        'periods_scaled': 0,
    }
    orig_run = BacktesterService.run_backtest

    def patched_run(self, *args, **kwargs):
        p = state['period_index']
        # Use the start_date passed to run_backtest
        start_date = kwargs.get('start_date') or (args[2] if len(args) > 2 else None)
        if start_date is None:
            # Fall back to no-op
            state['period_index'] += 1
            return orig_run(self, *args, **kwargs)

        # Find VIX close on or before start_date
        target_ts = pd.Timestamp(start_date)
        idx = vix_df.index
        if idx.tz is not None:
            target_ts = target_ts.tz_localize(idx.tz) if target_ts.tz is None else target_ts.tz_convert(idx.tz)
        # Most recent VIX bar at or before target
        past = vix_df[vix_df.index <= target_ts]
        if len(past) == 0:
            state['period_index'] += 1
            return orig_run(self, *args, **kwargs)
        vix_close = past['close'].iloc[-1]

        saved_pct = self.position_size_pct
        try:
            if vix_close >= vix_threshold:
                self.position_size_pct = saved_pct * vix_scale
                state['periods_scaled'] += 1
                if state['periods_scaled'] <= 5 or state['periods_scaled'] % 10 == 0:
                    print(f"   📉 Period {p+1}: VIX={vix_close:.1f} ≥ {vix_threshold} → "
                          f"size {saved_pct*100:.1f}% → {self.position_size_pct*100:.2f}%")
            state['period_index'] += 1
            result = orig_run(self, *args, **kwargs)
        finally:
            self.position_size_pct = saved_pct
        return result

    BacktesterService.run_backtest = patched_run
    return state


async def main():
    args = parse_args()

    # Load pickle to get VIX series (before any patch)
    print(f"📦 Loading pickle: {args.pickle}")
    with gzip.open(args.pickle, 'rb') as f:
        cache = pickle.load(f)
    if '^VIX' not in cache:
        print("❌ ^VIX not in pickle")
        sys.exit(1)
    vix_df = cache['^VIX']
    print(f"  ✅ ^VIX series: {len(vix_df)} bars, "
          f"latest {vix_df.index[-1].strftime('%Y-%m-%d')} close={vix_df['close'].iloc[-1]:.1f}")

    state = install_vix_patch(vix_df, args.vix_threshold, args.vix_scale)
    print(f"🔧 Patch — vix_threshold={args.vix_threshold}, vix_scale={args.vix_scale}\n")

    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.core.database import async_session

    scanner_service.data_cache = cache
    scanner_service.universe = list(cache.keys())
    print(f"  ✅ {len(cache)} symbols loaded into scanner")

    end_str = args.end
    if end_str is None:
        sy, sm, sd = args.start.split('-')
        end_str = f"{int(sy) + 5}-{sm}-{sd}"

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
            max_positions=6, position_size_pct=15.0,
            near_50d_high_pct=3.0, trailing_stop_pct=12.0,
            dwap_threshold_pct=5.0, periods_limit=0,
        )
    dur = time.time() - t0

    pkl_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/vix_sizing_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/vix_sizing_{args.start}/result.json')
    os.makedirs(os.path.dirname(pkl_out), exist_ok=True)
    with open(pkl_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_out, 'w') as f:
        json.dump({
            'start_date': args.start,
            'vix_threshold': args.vix_threshold,
            'vix_scale': args.vix_scale,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'periods_scaled': state['periods_scaled'],
            'total_periods': state['period_index'],
        }, f, indent=2, default=str)

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
    mdd = result.max_drawdown_pct
    calmar = (ann * 100) / mdd if mdd else 0

    print(f"\n{'=' * 60}")
    print(f"RESULTS — VIX sizing (threshold={args.vix_threshold}, scale={args.vix_scale})")
    print(f"{'=' * 60}")
    print(f"  Total return:        {result.total_return_pct:+.2f}%")
    print(f"  Annualized:          {ann*100:+.2f}%")
    print(f"  Sharpe:              {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:               {mdd:.2f}%")
    print(f"  Calmar:              {calmar:.2f}")
    print(f"  Periods scaled:      {state['periods_scaled']} / {state['period_index']}")
    print(f"  Duration:            {dur:.0f}s")


if __name__ == '__main__':
    asyncio.run(main())
