#!/usr/bin/env python3
"""
Parameter Tournament — Find which params actually matter.

Runs 17 single-param optimizations in parallel. Each one holds all params
at baseline values except ONE, which gets optimized across its full range.
The param that produces the biggest improvement over baseline = most important.

Usage:
    source backend/venv/bin/activate
    python3 scripts/param_tournament.py
"""

import asyncio
import gzip
import json
import os
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor
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

# Baseline params (Job 224 — the proven 16.3% ann config)
BASELINE = {
    "dwap_threshold_pct": 5.0,
    "trailing_stop_pct": 12.0,
    "max_positions": 6,
    "position_size_pct": 15.0,
    "near_50d_high_pct": 5.0,
    "short_mom_weight": 0.5,
    "long_mom_weight": 0.3,
    "volatility_penalty": 0.2,
    "short_momentum_days": 10,
    "long_momentum_days": 60,
    "rsi_oversold_filter": 100,  # disabled
    "volume_ratio_min": 0.0,     # disabled
    "exit_type": "trailing_stop",
    "sector_cap": 0,             # disabled
    "breakeven_pct": 0,          # disabled
    "profit_lock_pct": 0,        # disabled
    "profit_lock_stop_pct": 5.0,
}

# Search ranges for each param (min, max, step)
PARAM_RANGES = {
    "dwap_threshold_pct": (3.0, 7.0, 0.5),
    "trailing_stop_pct": (8.0, 18.0, 1.0),
    "max_positions": (4, 8, 1),
    "position_size_pct": (10.0, 20.0, 2.0),
    "near_50d_high_pct": (2.0, 8.0, 1.0),
    "short_mom_weight": (0.3, 0.7, 0.1),
    "long_mom_weight": (0.1, 0.5, 0.1),
    "volatility_penalty": (0.05, 0.30, 0.05),
    "short_momentum_days": (5, 20, 5),       # categorical: 5,10,15,20
    "long_momentum_days": (40, 120, 20),      # categorical: 40,60,80,100,120
    "rsi_oversold_filter": (60, 100, 10),
    "volume_ratio_min": (0.0, 1.5, 0.3),
    "sector_cap": (0, 4, 1),
    "breakeven_pct": (0, 10, 2),
    "profit_lock_pct": (0, 20, 4),
    "profit_lock_stop_pct": (3.0, 8.0, 1.0),
}

# WF config
START_DATE = "2021-02-01"
END_DATE = "2026-02-01"
MAX_SYMBOLS = 200
PICKLE_PATH = "backend/data/all_data.pkl.gz"


def generate_values(low, high, step):
    """Generate all values in range."""
    values = []
    v = low
    while v <= high + 0.001:
        if isinstance(low, int) and isinstance(step, int):
            values.append(int(v))
        else:
            values.append(round(v, 4))
        v += step
    return values


def run_single_param_sweep(param_name, result_queue):
    """Run a sweep of one param, testing each value with a quick backtest."""
    import asyncio

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

    async def _sweep():
        from datetime import datetime
        from app.services.scanner import scanner_service
        from app.services.strategy_analyzer import StrategyParams, CustomBacktester

        # Load pickle
        abs_path = os.path.join(os.path.dirname(__file__), '..', PICKLE_PATH)
        with gzip.open(abs_path, 'rb') as f:
            data_cache = pickle.load(f)
        scanner_service.data_cache = data_cache
        scanner_service.universe = list(data_cache.keys())

        # Get top symbols by volume
        from app.services.strategy_analyzer import get_top_liquid_symbols
        top_symbols = get_top_liquid_symbols(MAX_SYMBOLS)

        low, high, step = PARAM_RANGES[param_name]
        values = generate_values(low, high, step)

        results = []
        for val in values:
            # Build params: baseline + override this one param
            test_params = dict(BASELINE)
            test_params[param_name] = val

            try:
                params = StrategyParams(**test_params)
                bt = CustomBacktester()
                bt.configure(params)
                bt.data_cache = data_cache

                # Run backtest over the full period
                start_dt = datetime.strptime(START_DATE, '%Y-%m-%d')
                end_dt = datetime.strptime(END_DATE, '%Y-%m-%d')
                result = bt.run_backtest(
                    ticker_list=top_symbols,
                    start_date=start_dt,
                    end_date=end_dt,
                    strategy_type='ensemble',
                )
                total_return = result.total_return_pct
                sharpe = result.sharpe_ratio
                max_dd = result.max_drawdown_pct
                trades = result.total_trades
                results.append({
                    'value': val,
                    'return': total_return,
                    'sharpe': sharpe,
                    'max_dd': max_dd,
                    'trades': trades,
                })
            except Exception as e:
                results.append({
                    'value': val,
                    'return': 0,
                    'sharpe': 0,
                    'max_dd': 0,
                    'trades': 0,
                    'error': str(e),
                })

        # Find best value
        best = max(results, key=lambda r: r['return'])
        baseline_val = BASELINE[param_name]
        baseline_result = next((r for r in results if r['value'] == baseline_val), results[0])

        improvement = best['return'] - baseline_result['return']

        summary = {
            'param': param_name,
            'baseline_value': baseline_val,
            'baseline_return': baseline_result['return'],
            'best_value': best['value'],
            'best_return': best['return'],
            'best_sharpe': best['sharpe'],
            'best_max_dd': best['max_dd'],
            'improvement': improvement,
            'all_results': results,
        }

        result_queue.put(summary)
        print(f"  {param_name}: baseline={baseline_val}→{baseline_result['return']:+.1f}%, "
              f"best={best['value']}→{best['return']:+.1f}% (Δ{improvement:+.1f}pp)")

    asyncio.run(_sweep())


def main():
    t0 = time.time()
    print(f"{'='*70}")
    print(f"PARAMETER TOURNAMENT — Which params actually matter?")
    print(f"{'='*70}")
    print(f"Baseline: {json.dumps({k:v for k,v in BASELINE.items() if v != 0 and v != 100}, indent=None)}")
    print(f"Testing {len(PARAM_RANGES)} params, each swept independently")
    print(f"Period: {START_DATE} → {END_DATE}, {MAX_SYMBOLS} symbols")
    print(f"{'='*70}\n")

    result_queue = Queue()
    processes = []

    # Launch all sweeps in parallel
    for param_name in PARAM_RANGES:
        p = Process(target=run_single_param_sweep, args=(param_name, result_queue))
        p.start()
        processes.append(p)
        print(f"  Launched: {param_name}")

    print(f"\n{len(processes)} sweeps running in parallel...\n")

    # Wait for all to finish
    for p in processes:
        p.join()

    # Collect results
    all_results = []
    while not result_queue.empty():
        all_results.append(result_queue.get())

    # Sort by improvement (most impactful first)
    all_results.sort(key=lambda r: -abs(r['improvement']))

    dur = time.time() - t0

    print(f"\n{'='*70}")
    print(f"TOURNAMENT RESULTS (sorted by impact)")
    print(f"{'='*70}")
    print(f"{'Param':<25} {'Baseline':>10} {'Best Val':>10} {'Base Ret':>10} {'Best Ret':>10} {'Impact':>10}")
    print('-' * 75)
    for r in all_results:
        print(f"{r['param']:<25} {str(r['baseline_value']):>10} {str(r['best_value']):>10} "
              f"{r['baseline_return']:>+10.1f}% {r['best_return']:>+10.1f}% {r['improvement']:>+10.1f}pp")

    # Top 5 most impactful
    print(f"\n{'='*70}")
    print(f"TOP PARAMS (biggest impact on returns)")
    print(f"{'='*70}")
    for i, r in enumerate(all_results[:6], 1):
        direction = "↑" if r['best_return'] > r['baseline_return'] else "↓"
        print(f"  #{i} {r['param']}: {r['baseline_value']} → {r['best_value']} "
              f"({r['improvement']:+.1f}pp) Sharpe={r['best_sharpe']:.2f} MaxDD={r['best_max_dd']:.1f}%")

    print(f"\n  Completed in {dur/60:.1f} minutes")

    # Save full results
    output_path = '/tmp/param_tournament_results.json'
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"  Full results saved to: {output_path}")


if __name__ == '__main__':
    main()
