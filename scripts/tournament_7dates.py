#!/usr/bin/env python3
"""Run the tournament-winning config across all 7 start dates in parallel."""

import asyncio
import gzip
import os
import pickle
import sys
import time
from multiprocessing import Process, Queue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
# DATABASE_URL is required — load from .env if not already in environment.
# Never hardcode a real credential here (see memory: feedback_never_check_in_secrets.md).
if not os.environ.get('DATABASE_URL'):
    _dotenv = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(_dotenv):
        for _line in open(_dotenv):
            if _line.startswith('DATABASE_URL='):
                os.environ['DATABASE_URL'] = _line.strip().split('=', 1)[1]
                break
if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL not set. Create .env at repo root or export it.')
os.environ.setdefault('LAMBDA_ROLE', 'worker')

START_DATES = [
    ("2021-01-04", "2026-01-04"),
    ("2021-01-18", "2026-01-18"),
    ("2021-01-25", "2026-01-25"),
    ("2021-02-01", "2026-02-01"),
    ("2021-02-08", "2026-02-08"),
    ("2021-02-15", "2026-02-15"),
    ("2021-03-01", "2026-03-01"),
]


def run_one(start_date, end_date, result_queue):
    # DATABASE_URL already loaded at module scope; just ensure worker-mode imports.
    os.environ.setdefault('LAMBDA_ROLE', 'worker')

    async def _run():
        from datetime import datetime
        from app.services.walk_forward_service import walk_forward_service
        from app.services.scanner import scanner_service
        from app.core.database import async_session

        with gzip.open(os.path.join(os.path.dirname(__file__), '..', 'backend', 'data', 'all_data.pkl.gz'), 'rb') as f:
            scanner_service.data_cache = pickle.load(f)
        scanner_service.universe = list(scanner_service.data_cache.keys())

        t0 = time.time()
        async with async_session() as db:
            result = await walk_forward_service.run_walk_forward_simulation(
                db=db,
                start_date=datetime.strptime(start_date, '%Y-%m-%d'),
                end_date=datetime.strptime(end_date, '%Y-%m-%d'),
                reoptimization_frequency='biweekly',
                min_score_diff=10.0,
                enable_ai_optimization=False,
                max_symbols=200,
                fixed_strategy_id=5,
                carry_positions=True,
                trailing_stop_pct=12.0,
                near_50d_high_pct=3.0,
                periods_limit=0,
            )

        dur = time.time() - t0
        tr = result.total_return_pct
        years = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days / 365.25
        ann = ((1 + tr / 100) ** (1 / years) - 1) * 100 if tr > 0 else tr / years

        summary = {
            'start': start_date,
            'return': tr,
            'ann': ann,
            'sharpe': result.sharpe_ratio,
            'max_dd': result.max_drawdown_pct,
            'benchmark': result.benchmark_return_pct,
            'duration': dur,
        }
        result_queue.put(summary)
        print(f"  {start_date}: {tr:+.1f}% ({ann:+.1f}% ann), Sharpe {result.sharpe_ratio:.2f}, MaxDD {result.max_drawdown_pct:.1f}%")

    asyncio.run(_run())


def main():
    t0 = time.time()
    print("=" * 70)
    print("TOURNAMENT WINNER VALIDATION — 7 Start Dates")
    print("Config: near_50d_high_pct=3%, trailing_stop=12%, no optimizer")
    print("=" * 70)

    result_queue = Queue()
    processes = []

    for sd, ed in START_DATES:
        p = Process(target=run_one, args=(sd, ed, result_queue))
        p.start()
        processes.append(p)

    print(f"Launched {len(processes)} parallel runs...\n")

    for p in processes:
        p.join()

    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    results.sort(key=lambda r: -r['ann'])

    dur = time.time() - t0

    print(f"\n{'=' * 70}")
    print(f"RESULTS (sorted by annualized return)")
    print(f"{'=' * 70}")
    print(f"  Start       Return    Ann%   Sharpe  MaxDD   vsSPY")
    print(f"  {'-' * 60}")
    for r in results:
        vs = r['return'] - r['benchmark']
        marker = " ***" if r['ann'] >= 20 else ""
        print(f"  {r['start']}  {r['return']:>+8.1f}% {r['ann']:>+6.1f}% {r['sharpe']:>7.2f} {r['max_dd']:>6.1f}% {vs:>+7.1f}pp{marker}")

    anns = [r['ann'] for r in results]
    avg = sum(anns) / len(anns)
    pos = sum(1 for a in anns if a > 0)
    over_20 = sum(1 for a in anns if a >= 20)
    print(f"\n  Avg: {avg:+.1f}% ann | Positive: {pos}/{len(results)} | 20%+: {over_20}/{len(results)}")
    print(f"  Completed in {dur / 60:.1f} minutes")


if __name__ == '__main__':
    main()
