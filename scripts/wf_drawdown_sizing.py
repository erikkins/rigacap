#!/usr/bin/env python3
"""
DD-conditional sizing test — halve position_size_pct when WF equity is
DD% below its running peak, restore when a new peak is set.

LOCAL RESEARCH ONLY. Does NOT modify any production code paths. Same
runtime monkey-patch pattern as wf_gradual_deployment.py.

The trigger is reactive (looks at actual WF equity), not regime-classifier
or time-based. After each period's backtest, we read the realized period
return, update running peak/equity, and decide the sizing for the NEXT
period. Carried positions keep their original size — only new entries
in the next period are downsized.

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/dd_sizing/2021-01-25/result.pkl \\
    WF_RESULT_JSON=/tmp/dd_sizing/2021-01-25/result.json \\
        caffeinate -i python3 scripts/wf_drawdown_sizing.py \\
            --start 2021-01-25 \\
            --dd-threshold 10 \\
            --dd-scale 0.5
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
                   help='Drawdown %% from peak that triggers sizing cut (default 10)')
    p.add_argument('--dd-scale', type=float, default=0.5,
                   help='Multiplier applied to position_size_pct when in DD (default 0.5)')
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--strategy-id', type=int, default=5)
    return p.parse_args()


def install_dd_patch(dd_threshold_pct, dd_scale):
    """Reactive DD sizing patch.

    State carries running equity (starts at 100k synthetic, scales by each
    period's total_return_pct), a peak watermark, and the in-DD flag.
    Before each backtest we set position_size_pct based on prior state.
    AFTER each backtest we update the running equity from the period
    return.

    The period return must come from the BacktesterResult that
    run_backtest returns — pull total_return_pct off it.
    """
    from app.services.backtester import BacktesterService

    state = {
        'period_index': 0,
        'equity': 100000.0,
        'peak': 100000.0,
        'in_dd': False,
        'dd_periods': 0,        # count of periods entered while in DD
        'sized_down_count': 0,  # how many times we actually downsized
    }
    orig_run = BacktesterService.run_backtest

    def patched_run(self, *args, **kwargs):
        p = state['period_index']
        dd_pct = (state['peak'] - state['equity']) / state['peak'] * 100 if state['peak'] else 0
        in_dd = dd_pct >= dd_threshold_pct
        state['in_dd'] = in_dd

        saved_pct = self.position_size_pct
        try:
            if in_dd:
                self.position_size_pct = saved_pct * dd_scale
                state['sized_down_count'] += 1
                if state['sized_down_count'] <= 5 or state['sized_down_count'] % 10 == 0:
                    print(f"   📉 Period {p+1}: DD={dd_pct:.1f}% ≥ {dd_threshold_pct:.0f}% → "
                          f"size {saved_pct*100:.1f}% → {self.position_size_pct*100:.2f}% "
                          f"(equity ${state['equity']:,.0f} / peak ${state['peak']:,.0f})")
            state['period_index'] += 1
            result = orig_run(self, *args, **kwargs)
        finally:
            self.position_size_pct = saved_pct

        # Update running equity from the period return
        period_ret = getattr(result, 'total_return_pct', None) or 0
        state['equity'] *= (1.0 + period_ret / 100.0)
        if state['equity'] > state['peak']:
            if state['in_dd']:
                print(f"   📈 Period {p+1}: new equity peak ${state['equity']:,.0f} "
                      f"(DD={dd_pct:.1f}% cleared)")
            state['peak'] = state['equity']
        return result

    BacktesterService.run_backtest = patched_run
    return state


async def main():
    args = parse_args()

    state = install_dd_patch(args.dd_threshold, args.dd_scale)
    print(f"🔧 Patch installed — dd_threshold={args.dd_threshold}%, "
          f"dd_scale={args.dd_scale}\n")

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
    print(f"  Strategy: id={args.strategy_id} (no AI), canonical params, DD-sizing patch active")
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
            trailing_stop_pct=12.0,
            dwap_threshold_pct=5.0,
            periods_limit=0,
        )
    dur = time.time() - t0

    pkl_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/dd_sizing_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/dd_sizing_{args.start}/result.json')
    os.makedirs(os.path.dirname(pkl_out), exist_ok=True)
    with open(pkl_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_out, 'w') as f:
        json.dump({
            'start_date': args.start,
            'dd_threshold_pct': args.dd_threshold,
            'dd_scale': args.dd_scale,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'sized_down_periods': state['sized_down_count'],
            'total_periods': state['period_index'],
        }, f, indent=2, default=str)

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
    print(f"\n{'=' * 60}")
    print(f"RESULTS — DD-conditional sizing "
          f"(threshold={args.dd_threshold}%, scale={args.dd_scale})")
    print(f"{'=' * 60}")
    print(f"  Total return:        {result.total_return_pct:+.2f}%")
    print(f"  Sharpe:              {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:               {result.max_drawdown_pct:.2f}%")
    print(f"  Benchmark:           {getattr(result, 'benchmark_return_pct', 0):+.2f}%")
    print(f"  Trades:              {len(result.trades)}")
    print(f"  Annualized:          {ann*100:+.2f}%")
    print(f"  Duration:            {dur:.0f}s")
    print(f"  Sized-down periods:  {state['sized_down_count']} / {state['period_index']}")
    print()
    print(f"vs canonical Date 3 (no DD patch): +186.34% / 0.87 / 33.49%")
    print(f"  return Δ:   {result.total_return_pct - 186.34:+.2f}pp")
    print(f"  Sharpe Δ:   {result.sharpe_ratio - 0.87:+.2f}")
    print(f"  MaxDD Δ:    {result.max_drawdown_pct - 33.49:+.2f}pp")


if __name__ == '__main__':
    asyncio.run(main())
