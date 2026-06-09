#!/usr/bin/env python3
"""
VIX-conditional trailing stop TIGHTENING.

Hybrid of two previous tests:
  - Trigger: VIX >= threshold (from wf_vix_sizing.py, forward signal)
  - Mechanism: tighten trail 12% → 8% (from wf_dd_tighten_stop.py, proven)

Hypothesis: VIX-sizing failed because shrinking entries doesn't help MaxDD.
VIX-trail-tighten uses the same trigger but the proven exit-side mechanism.
If it works on the same 5 dates as t15/s8, it's orthogonal (different trigger
source) and can be stacked.

LOCAL RESEARCH ONLY. Monkey-patches BacktesterService.run_backtest.

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/vix_trail/2021-01-25/result.pkl \\
    WF_RESULT_JSON=/tmp/vix_trail/2021-01-25/result.json \\
        caffeinate -i python3 scripts/wf_vix_trail_tighten.py \\
            --start 2021-01-25 --vix-threshold 25 --tight-stop 8
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
                   help='VIX level above which to tighten the trail (default 25)')
    p.add_argument('--tight-stop', type=float, default=8.0,
                   help='Tightened trail %% when VIX trigger active (default 8)')
    p.add_argument('--baseline-stop', type=float, default=12.0)
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--strategy-id', type=int, default=5)
    return p.parse_args()


def install_vix_trail_patch(vix_df, vix_threshold, tight_stop_pct, baseline_stop_pct):
    """VIX trigger + trail-tighten mechanism."""
    from app.services.backtester import BacktesterService

    state = {'period_index': 0, 'periods_tightened': 0}
    orig_run = BacktesterService.run_backtest

    def patched_run(self, *args, **kwargs):
        p = state['period_index']
        start_date = kwargs.get('start_date') or (args[2] if len(args) > 2 else None)
        vix_close = None
        if start_date is not None:
            target_ts = pd.Timestamp(start_date)
            idx = vix_df.index
            if idx.tz is not None:
                target_ts = target_ts.tz_localize(idx.tz) if target_ts.tz is None else target_ts.tz_convert(idx.tz)
            past = vix_df[vix_df.index <= target_ts]
            if len(past) > 0:
                vix_close = past['close'].iloc[-1]

        saved_trail = self.trailing_stop_pct
        try:
            if vix_close is not None and vix_close >= vix_threshold:
                self.trailing_stop_pct = tight_stop_pct / 100.0
                state['periods_tightened'] += 1
                if state['periods_tightened'] <= 5 or state['periods_tightened'] % 10 == 0:
                    print(f"   🛑 Period {p+1}: VIX={vix_close:.1f} ≥ {vix_threshold} → "
                          f"trail {saved_trail*100:.1f}% → {self.trailing_stop_pct*100:.1f}%")
            else:
                self.trailing_stop_pct = baseline_stop_pct / 100.0
            state['period_index'] += 1
            result = orig_run(self, *args, **kwargs)
        finally:
            self.trailing_stop_pct = saved_trail
        return result

    BacktesterService.run_backtest = patched_run
    return state


async def main():
    args = parse_args()

    print(f"📦 Loading pickle: {args.pickle}")
    with gzip.open(args.pickle, 'rb') as f:
        cache = pickle.load(f)
    if '^VIX' not in cache:
        print("❌ ^VIX not in pickle"); sys.exit(1)
    vix_df = cache['^VIX']
    print(f"  ✅ ^VIX series: {len(vix_df)} bars")

    state = install_vix_trail_patch(vix_df, args.vix_threshold, args.tight_stop, args.baseline_stop)
    print(f"🔧 Patch — VIX trigger >= {args.vix_threshold}, "
          f"tight_stop={args.tight_stop}%, baseline={args.baseline_stop}%\n")

    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.core.database import async_session

    scanner_service.data_cache = cache
    scanner_service.universe = list(cache.keys())

    end_str = args.end
    if end_str is None:
        sy, sm, sd = args.start.split('-')
        end_str = f"{int(sy) + 5}-{sm}-{sd}"

    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')

    print(f"Running WF: {args.start} → {end_str}\n")

    t0 = time.time()
    async with async_session() as db:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db, start_date=start, end_date=end,
            reoptimization_frequency='biweekly',
            min_score_diff=10.0, enable_ai_optimization=False,
            max_symbols=args.max_symbols, fixed_strategy_id=args.strategy_id,
            n_trials=0, carry_positions=True,
            max_positions=6, position_size_pct=15.0,
            near_50d_high_pct=3.0, trailing_stop_pct=args.baseline_stop,
            dwap_threshold_pct=5.0, periods_limit=0,
        )
    dur = time.time() - t0

    pkl_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/vix_trail_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/vix_trail_{args.start}/result.json')
    os.makedirs(os.path.dirname(pkl_out), exist_ok=True)
    with open(pkl_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_out, 'w') as f:
        json.dump({
            'start_date': args.start,
            'vix_threshold': args.vix_threshold,
            'tight_stop_pct': args.tight_stop,
            'baseline_stop_pct': args.baseline_stop,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'periods_tightened': state['periods_tightened'],
            'total_periods': state['period_index'],
        }, f, indent=2, default=str)

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
    mdd = result.max_drawdown_pct
    calmar = (ann * 100) / mdd if mdd else 0
    print(f"\n{'=' * 60}")
    print(f"RESULTS — VIX trail-tighten (vix≥{args.vix_threshold} → {args.tight_stop}%)")
    print(f"{'=' * 60}")
    print(f"  Total return:        {result.total_return_pct:+.2f}%")
    print(f"  Annualized:          {ann*100:+.2f}%")
    print(f"  Sharpe:              {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:               {mdd:.2f}%")
    print(f"  Calmar:              {calmar:.2f}")
    print(f"  Periods tightened:   {state['periods_tightened']} / {state['period_index']}")
    print(f"  Duration:            {dur:.0f}s")


if __name__ == '__main__':
    asyncio.run(main())
