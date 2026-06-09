#!/usr/bin/env python3
"""
One-off WF test: canonical Apr 28 strategy params + PRE-Run5 momentum scoring.

Purpose: Run5 (Apr 19 deploy) changed 5 momentum-scoring config.py constants
that were never rolled back during the May 18 parity restoration. This means
the canonical Apr 28 baseline (+145%/0.92/20.3%) was generated against a
HYBRID config: Apr 28 strategy params + Run5 momentum scoring. We never
WF-tested the canonical strategy params with the *original* pre-Run5
momentum values. This script does that — single 5y run, all canonical CLI
overrides, but momentum scoring constants set to their pre-Run5 values.

If the result is ≥ canonical, Run5's momentum tuning was noise / overfit;
we should consider rolling those values back too.
If the result is materially worse, Run5's momentum scoring was genuine
signal and the hybrid we ship is justified.

Pre-Run5 values (from config.py before commit 6231186 on Apr 19 2026):
    SHORT_MOMENTUM_DAYS:  10  (Run5 set to 5)
    SHORT_MOM_WEIGHT:    0.5  (Run5 set to 0.3)
    LONG_MOM_WEIGHT:     0.3  (Run5 set to 0.2)
    VOLATILITY_PENALTY:  0.2  (Run5 set to 0.15)
    MOMENTUM_SECTOR_CAP:   5  (Run5 set to 0)

Usage:
    cd /Users/erikkins/CODE/stocker-app
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/wf_prerun5/result.pkl \\
    WF_RESULT_JSON=/tmp/wf_prerun5/result.json \\
        caffeinate -i python3 scripts/wf_prerun5_momentum.py
"""
import asyncio
import gzip
import os
import pickle
import sys
import time
from datetime import datetime

# Backend on path + worker-mode imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
if not os.environ.get('DATABASE_URL'):
    _dotenv = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(_dotenv):
        for _line in open(_dotenv):
            if _line.startswith('DATABASE_URL='):
                os.environ['DATABASE_URL'] = _line.strip().split('=', 1)[1]
                break
os.environ.setdefault('LAMBDA_ROLE', 'worker')


PICKLE_PATH = 'backend/data/all_data_11y.pkl.gz'  # Same source as canonical Apr 28
START = '2021-01-04'
END = '2026-01-04'

RESULT_PICKLE = os.environ.get('WF_RESULT_PICKLE', '/tmp/wf_prerun5/result.pkl')
RESULT_JSON = os.environ.get('WF_RESULT_JSON', '/tmp/wf_prerun5/result.json')


def load_pickle(path):
    abs_path = os.path.join(os.path.dirname(__file__), '..', path)
    print(f"📦 Loading pickle: {abs_path}")
    t0 = time.time()
    with gzip.open(abs_path, 'rb') as f:
        data = pickle.load(f)
    print(f"  ✅ {len(data)} symbols in {time.time() - t0:.1f}s")
    return data


async def run():
    # MONKEY-PATCH config BEFORE the WF service imports / reads it
    from app.core.config import settings
    print("=" * 60)
    print("Pre-Run5 momentum values (override config.py at runtime)")
    print("=" * 60)
    overrides = {
        'SHORT_MOMENTUM_DAYS': 10,
        'SHORT_MOM_WEIGHT': 0.5,
        'LONG_MOM_WEIGHT': 0.3,
        'VOLATILITY_PENALTY': 0.2,
        'MOMENTUM_SECTOR_CAP': 5,
    }
    for k, v in overrides.items():
        old = getattr(settings, k, None)
        setattr(settings, k, v)
        new = getattr(settings, k)
        print(f"  settings.{k}: {old} → {new}")
    # The 5 canonical strategy params come via the function args (CLI override
    # equivalent) so we don't need to patch those.
    print()

    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.core.database import async_session

    data_cache = load_pickle(PICKLE_PATH)
    scanner_service.data_cache = data_cache
    scanner_service.universe = list(data_cache.keys())

    start = datetime.strptime(START, '%Y-%m-%d')
    end = datetime.strptime(END, '%Y-%m-%d')

    print(f"Running 5y WF: {START} → {END}")
    print(f"  strategy_id=5, max_symbols=200, --no-ai, periods_limit=0 (run all)")
    print(f"  Canonical Apr 28 strategy params: 12/3/5.0/6/15%")
    print(f"  Momentum scoring: PRE-Run5 (10/0.5/0.3/0.2/5)")
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
            max_symbols=200,
            fixed_strategy_id=5,
            n_trials=30,
            carry_positions=True,
            max_positions=6,
            position_size_pct=15.0,
            near_50d_high_pct=3.0,
            trailing_stop_pct=12.0,
            dwap_threshold_pct=5.0,
            optimizer_version='v2m',  # match local_wf_runner.py default
            risk_preference=0.8,      # match local_wf_runner.py default
            warmup_periods=0,
            param_smoothing=0.0,
            ensemble_seeds=0,
            periods_limit=0,
            profit_lock_pct=0,
            profit_lock_stop_pct=6.0,
        )
    dur = time.time() - t0

    # Save result
    os.makedirs(os.path.dirname(RESULT_PICKLE), exist_ok=True)
    with open(RESULT_PICKLE, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    import json
    summary = {
        'total_return_pct': result.total_return_pct,
        'sharpe_ratio': result.sharpe_ratio,
        'max_drawdown_pct': result.max_drawdown_pct,
        'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
        'total_trades': getattr(result, 'total_trades', len(result.trades) if hasattr(result, 'trades') else None),
        'duration_minutes': dur / 60,
        'momentum_overrides': overrides,
    }
    with open(RESULT_JSON, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print()
    print("=" * 60)
    print("RESULTS — pre-Run5 momentum scoring")
    print("=" * 60)
    print(f"  Total return:  {result.total_return_pct:+.2f}%")
    print(f"  Sharpe ratio:  {result.sharpe_ratio:.2f}")
    print(f"  Max drawdown:  {result.max_drawdown_pct:.2f}%")
    print(f"  Benchmark:     {summary['benchmark_return_pct']:+.2f}% (SPY)" if summary['benchmark_return_pct'] is not None else "")
    print(f"  Total trades:  {summary['total_trades']}")
    print(f"  Duration:      {dur / 60:.1f} min")
    print()
    print(f"vs canonical hybrid (+145.4% / 0.92 / 20.3%):")
    print(f"  Return delta:  {result.total_return_pct - 145.36:+.2f} pp")
    print(f"  Sharpe delta:  {result.sharpe_ratio - 0.92:+.3f}")
    print(f"  MaxDD delta:   {result.max_drawdown_pct - 20.26:+.2f} pp")


if __name__ == '__main__':
    asyncio.run(run())
