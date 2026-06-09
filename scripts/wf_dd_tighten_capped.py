#!/usr/bin/env python3
"""
DD-conditional trailing stop tightening WITH max-consecutive cap.

Refinement of wf_dd_tighten_stop.py — adds a counter that limits how many
consecutive periods we tighten. If we've been tightened for N periods
without recovery, the strategy is clearly being CHURNED by the tight stop,
so revert to baseline for K periods to give it room to breathe.

LOCAL RESEARCH ONLY. Monkey-patches BacktesterService.run_backtest.

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/dd_capped/2021-03-15/result.pkl \\
    WF_RESULT_JSON=/tmp/dd_capped/2021-03-15/result.json \\
        caffeinate -i python3 scripts/wf_dd_tighten_capped.py \\
            --start 2021-03-15 \\
            --dd-threshold 15 \\
            --tight-stop 8 \\
            --max-consec 8 \\
            --release-periods 2
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
    p.add_argument('--max-consec', type=int, default=8,
                   help='Max consecutive tightened periods before forced release (default 8 = ~16 weeks)')
    p.add_argument('--release-periods', type=int, default=2,
                   help='Periods to stay released after hitting cap (default 2)')
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--strategy-id', type=int, default=5)
    return p.parse_args()


def install_capped_patch(dd_threshold_pct, tight_stop_pct, baseline_stop_pct,
                        max_consec, release_periods):
    """Patch with max-consecutive-tightened cap.

    States:
      - normal: out of DD or below threshold → baseline trail
      - tightened: in DD, within consecutive cap → tight trail
      - cooldown: hit consecutive cap → forced baseline for release_periods
    """
    from app.services.backtester import BacktesterService

    state = {
        'period_index': 0,
        'equity': 100000.0,
        'peak': 100000.0,
        'consec_tightened': 0,
        'cooldown_remaining': 0,
        'tightened_periods': 0,
        'cap_releases': 0,
    }
    orig_run = BacktesterService.run_backtest

    def patched_run(self, *args, **kwargs):
        p = state['period_index']
        dd_pct = (state['peak'] - state['equity']) / state['peak'] * 100 if state['peak'] else 0
        in_dd = dd_pct >= dd_threshold_pct

        saved_trail = self.trailing_stop_pct
        try:
            if state['cooldown_remaining'] > 0:
                # Forced release after hitting consecutive cap
                self.trailing_stop_pct = baseline_stop_pct / 100.0
                state['cooldown_remaining'] -= 1
                if state['cooldown_remaining'] == 0:
                    print(f"   🔄 Period {p+1}: cooldown ended, can re-tighten if DD persists")
            elif in_dd:
                if state['consec_tightened'] >= max_consec:
                    # Hit the cap — force release
                    print(f"   ⏸️  Period {p+1}: consecutive-cap hit ({state['consec_tightened']}), "
                          f"forced baseline for {release_periods} periods (DD={dd_pct:.1f}%)")
                    self.trailing_stop_pct = baseline_stop_pct / 100.0
                    state['cap_releases'] += 1
                    state['cooldown_remaining'] = release_periods - 1
                    state['consec_tightened'] = 0
                else:
                    self.trailing_stop_pct = tight_stop_pct / 100.0
                    state['consec_tightened'] += 1
                    state['tightened_periods'] += 1
            else:
                # Out of DD — reset counter, baseline trail
                self.trailing_stop_pct = baseline_stop_pct / 100.0
                if state['consec_tightened'] > 0:
                    print(f"   ↗️  Period {p+1}: out of DD ({dd_pct:.1f}%), tightened streak {state['consec_tightened']} cleared")
                state['consec_tightened'] = 0

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

    state = install_capped_patch(args.dd_threshold, args.tight_stop, args.baseline_stop,
                                  args.max_consec, args.release_periods)
    print(f"🔧 Patch — dd_threshold={args.dd_threshold}%, tight_stop={args.tight_stop}%, "
          f"max_consec={args.max_consec}, release_periods={args.release_periods}\n")

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

    pkl_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/dd_capped_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/dd_capped_{args.start}/result.json')
    os.makedirs(os.path.dirname(pkl_out), exist_ok=True)
    with open(pkl_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_out, 'w') as f:
        json.dump({
            'start_date': args.start,
            'dd_threshold_pct': args.dd_threshold,
            'tight_stop_pct': args.tight_stop,
            'baseline_stop_pct': args.baseline_stop,
            'max_consec': args.max_consec,
            'release_periods': args.release_periods,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'tightened_periods': state['tightened_periods'],
            'cap_releases': state['cap_releases'],
            'total_periods': state['period_index'],
        }, f, indent=2, default=str)

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
    mdd = result.max_drawdown_pct
    calmar = (ann * 100) / mdd if mdd else 0

    print(f"\n{'=' * 60}")
    print(f"RESULTS — DD-capped (threshold={args.dd_threshold}%, tight={args.tight_stop}%, "
          f"max_consec={args.max_consec}, release={args.release_periods})")
    print(f"{'=' * 60}")
    print(f"  Total return:        {result.total_return_pct:+.2f}%")
    print(f"  Annualized:          {ann*100:+.2f}%")
    print(f"  Sharpe:              {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:               {mdd:.2f}%")
    print(f"  Calmar:              {calmar:.2f}")
    print(f"  Tightened periods:   {state['tightened_periods']} / {state['period_index']}")
    print(f"  Cap releases:        {state['cap_releases']}")
    print(f"  Duration:            {dur:.0f}s")


if __name__ == '__main__':
    asyncio.run(main())
