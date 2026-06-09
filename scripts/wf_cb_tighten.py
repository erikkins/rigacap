#!/usr/bin/env python3
"""
Test: circuit_breaker_tighten_pct on Date 3.

When CB fires (3 same-day trailing stops), tighten ALL existing positions'
trailing stops to N% from peak. Default in StrategyParams is 0 (disabled).
This test sets it to a configurable value and measures MaxDD impact.

LOCAL RESEARCH ONLY — monkey-patches run_backtest at runtime, no
production code touched.

Usage:
    python3 scripts/wf_cb_tighten.py --start 2021-01-25 --tighten-pct 6
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
    p.add_argument('--tighten-pct', type=float, required=True,
                   help='When CB triggers, tighten trailing stops to X% from peak (e.g. 6)')
    return p.parse_args()


def install_cb_tighten_patch(tighten_pct):
    """Force circuit_breaker_tighten_pct = tighten_pct on every backtest run.
    Logged once per WF (period 1) for confirmation."""
    from app.services.backtester import BacktesterService
    state = {'period_index': 0, 'cb_fires': []}
    orig_run = BacktesterService.run_backtest

    def patched_run(self, *args, **kwargs):
        self.circuit_breaker_tighten_pct = tighten_pct
        if state['period_index'] == 0:
            print(f"🔧 CB tighten patch active: stops={self.circuit_breaker_stops}, "
                  f"pause={self.circuit_breaker_pause_days}d, "
                  f"tighten={self.circuit_breaker_tighten_pct}%")
        state['period_index'] += 1
        return orig_run(self, *args, **kwargs)

    BacktesterService.run_backtest = patched_run
    return state


async def main():
    args = parse_args()
    state = install_cb_tighten_patch(args.tighten_pct)

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
    print(f"  ✅ {len(cache)} symbols\n")

    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')

    print(f"Running WF: {args.start} → {end_str}")
    print(f"  Canonical params + CB tighten {args.tighten_pct}%\n")

    t0 = time.time()
    async with async_session() as db:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db,
            start_date=start, end_date=end,
            reoptimization_frequency='biweekly',
            min_score_diff=10.0,
            enable_ai_optimization=False,
            max_symbols=200,
            fixed_strategy_id=5,
            n_trials=0,
            carry_positions=True,
            max_positions=6, position_size_pct=15.0,
            near_50d_high_pct=3.0, trailing_stop_pct=12.0, dwap_threshold_pct=5.0,
            periods_limit=0,
        )
    dur = time.time() - t0

    out_dir = f'/tmp/cb_tighten_{args.tighten_pct}/{args.start}'
    os.makedirs(out_dir, exist_ok=True)
    with open(f'{out_dir}/result.pkl', 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Count CB events from pause_events
    pe = getattr(result, 'pause_events', []) or []
    cb_events = [p for p in pe if isinstance(p, dict) and p.get('source') == 'circuit_breaker']

    years = (end - start).days / 365.25
    ann = (1 + result.total_return_pct/100) ** (1/years) - 1
    print(f"\n{'=' * 60}")
    print(f"RESULTS — CB tighten {args.tighten_pct}%")
    print(f"{'=' * 60}")
    print(f"  Total return:   {result.total_return_pct:+.2f}%")
    print(f"  Sharpe:         {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:          {result.max_drawdown_pct:.2f}%")
    print(f"  Benchmark:      {getattr(result, 'benchmark_return_pct', 0):+.2f}%")
    print(f"  Trades:         {len(result.trades)}")
    print(f"  CB events:      {len(cb_events)}")
    print(f"  Annualized:     {ann*100:+.2f}%")
    print(f"  Duration:       {dur:.0f}s")
    print()
    print(f"vs baseline (no tighten) Date 3: +186.34% / 0.87 / 33.49%")
    print(f"  return Δ:       {result.total_return_pct - 186.34:+.2f}pp")
    print(f"  Sharpe Δ:       {result.sharpe_ratio - 0.87:+.2f}")
    print(f"  MaxDD Δ:        {result.max_drawdown_pct - 33.49:+.2f}pp")

    with open(f'{out_dir}/result.json', 'w') as f:
        json.dump({
            'start_date': args.start,
            'tighten_pct': args.tighten_pct,
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'cb_events': len(cb_events),
        }, f, indent=2, default=str)


if __name__ == '__main__':
    asyncio.run(main())
