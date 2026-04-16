#!/usr/bin/env python3
"""
TPE Optimizer — Megacap fallback params, focused on 2023.

Keeps Trial 37 base params fixed. Only searches megacap-specific params.
Runs 2022-07-01 to 2024-06-30 (18 months centered on 2023) across 4 start dates.
Optimizes for: positive 2023 return + low MaxDD.

Usage:
    source backend/venv/bin/activate
    caffeinate -i python3 scripts/tpe_megacap_2023.py --trials 30
"""

import argparse
import asyncio
import gzip
import json
import os
import pickle
import sys
import time
from datetime import datetime

import optuna
from optuna.samplers import TPESampler

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

# Trial 37 base params (fixed)
T37 = dict(
    trailing_stop_pct=13.0, near_50d_high_pct=5.0, dwap_threshold_pct=6.5,
    max_positions=8, position_size_pct=17.0, bear_keep_pct=0.1,
    pyramid_threshold_pct=15.0, pyramid_size_pct=2.5, pyramid_max_adds=2,
    profit_lock_pct=15.0, profit_lock_stop_pct=5.0,
)

# Test dates — start mid-2022 so 2023 is fully captured
DATES = ['2022-07-01', '2022-10-01', '2023-01-01', '2023-04-01']
END = '2024-06-30'


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--trials', type=int, default=30)
    p.add_argument('--pickle', default='backend/data/all_data.pkl.gz')
    return p.parse_args()


async def run_single(start, end, **mc_params):
    from app.services.walk_forward_service import walk_forward_service
    from app.core.database import async_session

    async with async_session() as db:
        r = await walk_forward_service.run_walk_forward_simulation(
            db=db,
            start_date=datetime.strptime(start, '%Y-%m-%d'),
            end_date=datetime.strptime(end, '%Y-%m-%d'),
            reoptimization_frequency='biweekly', min_score_diff=10.0,
            enable_ai_optimization=False, max_symbols=500,
            fixed_strategy_id=5, carry_positions=True, periods_limit=0,
            **T37, **mc_params,
        )
    return {
        'return_pct': r.total_return_pct,
        'sharpe': r.sharpe_ratio,
        'max_dd': r.max_drawdown_pct,
    }


async def evaluate(mc_params):
    results = []
    for start in DATES:
        try:
            r = await run_single(start, END, **mc_params)
            results.append(r)
        except Exception as e:
            print(f"  ERROR {start}: {e}")
            return None

    returns = [r['return_pct'] for r in results]
    sharpes = [r['sharpe'] for r in results]
    max_dds = [r['max_dd'] for r in results]

    return {
        'avg_return': sum(returns) / len(returns),
        'avg_sharpe': sum(sharpes) / len(sharpes),
        'worst_max_dd': max(max_dds),
        'worst_return': min(returns),
        'all_positive': all(r > 0 for r in returns),
    }


def objective(trial):
    mc_params = {
        'megacap_fallback': trial.suggest_int('megacap_fallback', 1, 3),
        'megacap_trailing_stop_pct': trial.suggest_float('megacap_trailing_stop_pct', 0, 25, step=5),
        'megacap_regime_delay': trial.suggest_int('megacap_regime_delay', 0, 6),
    }

    # If megacap_trailing_stop_pct is 0, use primary stop
    t0 = time.time()
    print(f"\nTrial {trial.number + 1}: {mc_params}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        metrics = loop.run_until_complete(evaluate(mc_params))
    finally:
        loop.close()

    if metrics is None:
        return float('-inf'), float('inf')

    dur = time.time() - t0
    print(f"  Result ({dur:.0f}s): avg_ret={metrics['avg_return']:+.1f}% | "
          f"sharpe={metrics['avg_sharpe']:.2f} | worst_mdd={metrics['worst_max_dd']:.1f}% | "
          f"worst_ret={metrics['worst_return']:+.1f}% | all_pos={metrics['all_positive']}")

    trial.set_user_attr('metrics', metrics)
    trial.set_user_attr('params', mc_params)

    # Bi-objective: maximize avg return, minimize worst MaxDD
    return metrics['avg_return'], -metrics['worst_max_dd']


def main():
    args = parse_args()

    with gzip.open(os.path.join(os.path.dirname(__file__), '..', args.pickle), 'rb') as f:
        data = pickle.load(f)
    from app.services.scanner import scanner_service
    scanner_service.data_cache = data
    scanner_service.universe = list(data.keys())
    print(f"Loaded {len(data)} symbols")
    print(f"Searching megacap params for 2023, {args.trials} trials")
    print(f"Dates: {DATES} → {END}")

    study = optuna.create_study(
        directions=['maximize', 'maximize'],
        sampler=TPESampler(seed=42, multivariate=True),
    )

    study.optimize(objective, n_trials=args.trials)

    # Results
    print(f"\n{'='*60}")
    print(f"PARETO FRONT ({len(study.best_trials)} solutions)")
    print(f"{'='*60}")

    best_positive = None
    for trial in study.best_trials:
        m = trial.user_attrs.get('metrics', {})
        p = trial.user_attrs.get('params', {})
        flag = ' *** ALL POSITIVE' if m.get('all_positive') else ''
        print(f"  Trial {trial.number}: ret={m.get('avg_return',0):+.1f}% | "
              f"mdd={m.get('worst_max_dd',0):.1f}% | "
              f"worst={m.get('worst_return',0):+.1f}%{flag} | {p}")
        if m.get('all_positive') and (best_positive is None or m['avg_return'] > best_positive[0]):
            best_positive = (m['avg_return'], p, m)

    if best_positive:
        print(f"\n{'='*60}")
        print(f"BEST ALL-POSITIVE: +{best_positive[0]:.1f}%")
        print(f"  Params: {json.dumps(best_positive[1], indent=4)}")
        print(f"  Metrics: {best_positive[2]}")
        print(f"{'='*60}")

    # Save
    with open(os.path.join(os.path.dirname(__file__), '..', 'scripts/tpe_megacap_results.json'), 'w') as f:
        json.dump({
            'pareto': [{
                'trial': t.number,
                'params': t.user_attrs.get('params'),
                'metrics': t.user_attrs.get('metrics'),
            } for t in study.best_trials],
            'best_positive': best_positive,
        }, f, indent=2, default=str)


if __name__ == '__main__':
    main()
