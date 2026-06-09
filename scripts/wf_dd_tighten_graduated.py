#!/usr/bin/env python3
"""
DD-conditional trailing stop tightening — DEPTH-GRADUATED variant.

Instead of binary (in-DD → tight / out-of-DD → baseline), scale the trail
by DD depth:
  - DD <  threshold_low (e.g. 15%):  baseline trail (12%)
  - DD  threshold_low - mid:         mid trail (10%)
  - DD  threshold_mid - high:        tight trail (8%)
  - DD >= threshold_high:            very-tight trail (6%) — force out persistent bleeders

Hypothesis: rewards positions that survive shallow DDs (gives them room
with 10%), keeps the t15/s8 win for moderate DDs, and forces out the
persistent bleeders that drive the March 2021 failure mode.

LOCAL RESEARCH ONLY. Monkey-patches BacktesterService.run_backtest.

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/dd_graduated/2021-03-15/result.pkl \\
    WF_RESULT_JSON=/tmp/dd_graduated/2021-03-15/result.json \\
        caffeinate -i python3 scripts/wf_dd_tighten_graduated.py \\
            --start 2021-03-15 \\
            --t-low 15 --t-mid 20 --t-high 25 \\
            --stop-mid 10 --stop-tight 8 --stop-very-tight 6
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
    p.add_argument('--t-low', type=float, default=15.0, help='DD%% to enter mid (default 15)')
    p.add_argument('--t-mid', type=float, default=20.0, help='DD%% to enter tight (default 20)')
    p.add_argument('--t-high', type=float, default=25.0, help='DD%% to enter very-tight (default 25)')
    p.add_argument('--baseline-stop', type=float, default=12.0)
    p.add_argument('--stop-mid', type=float, default=10.0)
    p.add_argument('--stop-tight', type=float, default=8.0)
    p.add_argument('--stop-very-tight', type=float, default=6.0)
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--strategy-id', type=int, default=5)
    return p.parse_args()


def install_graduated_patch(t_low, t_mid, t_high,
                            baseline, mid, tight, very_tight):
    """Depth-graduated patch. Larger DD → tighter stop. Reset on new peak."""
    from app.services.backtester import BacktesterService

    state = {
        'period_index': 0,
        'equity': 100000.0,
        'peak': 100000.0,
        'periods_at': {'baseline': 0, 'mid': 0, 'tight': 0, 'very_tight': 0},
    }
    orig_run = BacktesterService.run_backtest

    def patched_run(self, *args, **kwargs):
        p = state['period_index']
        dd_pct = (state['peak'] - state['equity']) / state['peak'] * 100 if state['peak'] else 0

        # Pick band
        if dd_pct >= t_high:
            level = 'very_tight'
            chosen_stop = very_tight
        elif dd_pct >= t_mid:
            level = 'tight'
            chosen_stop = tight
        elif dd_pct >= t_low:
            level = 'mid'
            chosen_stop = mid
        else:
            level = 'baseline'
            chosen_stop = baseline

        state['periods_at'][level] += 1

        saved_trail = self.trailing_stop_pct
        try:
            self.trailing_stop_pct = chosen_stop / 100.0
            if level != 'baseline' and state['periods_at'][level] <= 3:
                # Print first 3 entries into each level for observability
                print(f"   📐 Period {p+1}: DD={dd_pct:.1f}% → {level} ({chosen_stop:.1f}% trail) "
                      f"[equity ${state['equity']:,.0f} / peak ${state['peak']:,.0f}]")
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

    state = install_graduated_patch(
        args.t_low, args.t_mid, args.t_high,
        args.baseline_stop, args.stop_mid, args.stop_tight, args.stop_very_tight)
    print(f"🔧 Patch — graduated bands: <{args.t_low}%={args.baseline_stop}%, "
          f"{args.t_low}-{args.t_mid}={args.stop_mid}%, "
          f"{args.t_mid}-{args.t_high}={args.stop_tight}%, "
          f">{args.t_high}={args.stop_very_tight}%\n")

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
            near_50d_high_pct=3.0, trailing_stop_pct=args.baseline_stop,
            dwap_threshold_pct=5.0, periods_limit=0,
        )
    dur = time.time() - t0

    pkl_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/dd_graduated_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/dd_graduated_{args.start}/result.json')
    os.makedirs(os.path.dirname(pkl_out), exist_ok=True)
    with open(pkl_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_out, 'w') as f:
        json.dump({
            'start_date': args.start,
            't_low': args.t_low, 't_mid': args.t_mid, 't_high': args.t_high,
            'baseline_stop': args.baseline_stop, 'stop_mid': args.stop_mid,
            'stop_tight': args.stop_tight, 'stop_very_tight': args.stop_very_tight,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'periods_at': state['periods_at'],
            'total_periods': state['period_index'],
        }, f, indent=2, default=str)

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
    mdd = result.max_drawdown_pct
    calmar = (ann * 100) / mdd if mdd else 0

    print(f"\n{'=' * 60}")
    print(f"RESULTS — DD-graduated")
    print(f"{'=' * 60}")
    print(f"  Total return:        {result.total_return_pct:+.2f}%")
    print(f"  Annualized:          {ann*100:+.2f}%")
    print(f"  Sharpe:              {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:               {mdd:.2f}%")
    print(f"  Calmar:              {calmar:.2f}")
    print(f"  Periods at band:     baseline={state['periods_at']['baseline']}, "
          f"mid={state['periods_at']['mid']}, "
          f"tight={state['periods_at']['tight']}, "
          f"very_tight={state['periods_at']['very_tight']}")
    print(f"  Duration:            {dur:.0f}s")


if __name__ == '__main__':
    asyncio.run(main())
