#!/usr/bin/env python3
"""
Multi-Objective TPE Optimizer — Find optimal strategy params across multiple start dates.

Optimizes for: avg return, avg Sharpe, min MaxDD, min return spread.
Each trial runs across N start dates to prevent overfitting.

Usage:
    source backend/venv/bin/activate
    caffeinate -i python3 scripts/tpe_optimizer.py --trials 50
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

# Start dates for multi-date validation
VALIDATION_DATES = [
    '2021-01-01',
    '2021-02-12',
    '2021-06-04',
    '2021-10-01',
]

END_DATE = '2026-04-01'


def parse_args():
    p = argparse.ArgumentParser(description='Multi-Objective TPE Optimizer')
    p.add_argument('--trials', type=int, default=50, help='Number of Optuna trials (default: 50)')
    p.add_argument('--pickle', default='backend/data/all_data.pkl.gz', help='Path to pickle')
    p.add_argument('--output', default='scripts/tpe_results.json', help='Output file for results')
    return p.parse_args()


def load_data(pickle_path):
    abs_path = os.path.join(os.path.dirname(__file__), '..', pickle_path)
    print(f"Loading pickle: {abs_path}")
    with gzip.open(abs_path, 'rb') as f:
        data = pickle.load(f)
    print(f"Loaded {len(data)} symbols")
    return data


async def run_single(start_date_str, **params):
    """Run one WF simulation and return metrics."""
    from app.services.walk_forward_service import walk_forward_service
    from app.core.database import async_session

    start = datetime.strptime(start_date_str, '%Y-%m-%d')
    end = datetime.strptime(END_DATE, '%Y-%m-%d')

    async with async_session() as db:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db,
            start_date=start,
            end_date=end,
            reoptimization_frequency='biweekly',
            min_score_diff=10.0,
            enable_ai_optimization=False,
            max_symbols=500,
            fixed_strategy_id=5,
            carry_positions=True,
            periods_limit=0,
            **params,
        )

    return {
        'return_pct': result.total_return_pct,
        'sharpe': result.sharpe_ratio,
        'max_dd': result.max_drawdown_pct,
    }


async def evaluate_params(params):
    """Run across all validation dates and return averaged metrics."""
    results = []
    for date_str in VALIDATION_DATES:
        try:
            r = await run_single(date_str, **params)
            results.append(r)
        except Exception as e:
            print(f"  ERROR on {date_str}: {e}")
            return None

    returns = [r['return_pct'] for r in results]
    sharpes = [r['sharpe'] for r in results]
    max_dds = [r['max_dd'] for r in results]

    avg_return = sum(returns) / len(returns)
    avg_sharpe = sum(sharpes) / len(sharpes)
    avg_max_dd = sum(max_dds) / len(max_dds)
    worst_max_dd = max(max_dds)  # Highest drawdown across dates
    return_spread = max(returns) - min(returns)
    worst_return = min(returns)

    return {
        'avg_return': avg_return,
        'avg_sharpe': avg_sharpe,
        'avg_max_dd': avg_max_dd,
        'worst_max_dd': worst_max_dd,
        'return_spread': return_spread,
        'worst_return': worst_return,
        'per_date': results,
    }


def objective(trial):
    """Optuna objective — returns 4 values for multi-objective optimization."""

    # Search space — only kwargs run_walk_forward_simulation actually accepts.
    # The previously-included pyramid_* kwargs threw TypeError on every trial
    # (Apr 16 2026) and produced an empty Pareto front; removed here.
    params = {
        'trailing_stop_pct': trial.suggest_float('trailing_stop_pct', 8.0, 15.0, step=1.0),
        'near_50d_high_pct': trial.suggest_float('near_50d_high_pct', 3.0, 8.0, step=0.5),
        'dwap_threshold_pct': trial.suggest_float('dwap_threshold_pct', 3.0, 8.0, step=0.5),
        'max_positions': trial.suggest_int('max_positions', 4, 8),
        'position_size_pct': trial.suggest_float('position_size_pct', 10.0, 20.0, step=1.0),
        'bear_keep_pct': trial.suggest_float('bear_keep_pct', 0.0, 0.5, step=0.1),
        'profit_lock_pct': trial.suggest_float('profit_lock_pct', 0.0, 40.0, step=5.0),
        'profit_lock_stop_pct': trial.suggest_float('profit_lock_stop_pct', 4.0, 10.0, step=1.0),
    }

    # Disable profit lock if threshold is 0
    if params['profit_lock_pct'] == 0:
        params['profit_lock_stop_pct'] = 6.0

    t0 = time.time()
    trial_num = trial.number + 1

    print(f"\n{'='*60}")
    print(f"Trial {trial_num}: {params}")
    print(f"{'='*60}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        metrics = loop.run_until_complete(evaluate_params(params))
    finally:
        loop.close()

    if metrics is None:
        # Failed trial
        return float('-inf'), float('inf'), float('-inf'), float('inf')

    dur = time.time() - t0

    print(f"Trial {trial_num} ({dur:.0f}s): "
          f"avg_ret={metrics['avg_return']:+.1f}% | "
          f"avg_sharpe={metrics['avg_sharpe']:.2f} | "
          f"avg_mdd={metrics['avg_max_dd']:.1f}% | "
          f"worst_mdd={metrics['worst_max_dd']:.1f}% | "
          f"spread={metrics['return_spread']:.0f}pp | "
          f"worst_ret={metrics['worst_return']:+.1f}%")

    # Store full metrics as user attrs
    trial.set_user_attr('metrics', metrics)
    trial.set_user_attr('params', params)
    trial.set_user_attr('duration', dur)

    # 4 objectives: maximize return, maximize sharpe, minimize max_dd, minimize spread
    return (
        metrics['avg_return'],       # maximize
        metrics['avg_sharpe'],       # maximize
        -metrics['worst_max_dd'],    # minimize (negate for maximization)
        -metrics['return_spread'],   # minimize (negate for maximization)
    )


def main():
    args = parse_args()

    # Load data
    data = load_data(args.pickle)
    from app.services.scanner import scanner_service
    scanner_service.data_cache = data
    scanner_service.universe = list(data.keys())

    print(f"\nTPE Multi-Objective Optimizer")
    print(f"  Trials: {args.trials}")
    print(f"  Dates: {VALIDATION_DATES}")
    print(f"  End: {END_DATE}")
    print(f"  Objectives: avg_return (max), avg_sharpe (max), worst_mdd (min), spread (min)")
    print(f"  Est. time: {args.trials * len(VALIDATION_DATES) * 5 / 60:.0f} hours")

    # Create multi-objective study
    study = optuna.create_study(
        directions=['maximize', 'maximize', 'maximize', 'maximize'],  # All maximized (MDD/spread negated in objective)
        sampler=TPESampler(seed=42, multivariate=True),
        study_name='rigacap_strategy_tuning',
    )

    t0 = time.time()
    study.optimize(objective, n_trials=args.trials, show_progress_bar=False)
    total_dur = time.time() - t0

    # Extract Pareto front
    pareto = study.best_trials
    print(f"\n{'='*60}")
    print(f"PARETO FRONT ({len(pareto)} solutions, {total_dur/3600:.1f} hours)")
    print(f"{'='*60}")

    results = []
    for i, trial in enumerate(pareto):
        m = trial.user_attrs.get('metrics', {})
        p = trial.user_attrs.get('params', {})
        print(f"\n  #{i+1} (Trial {trial.number}):")
        print(f"    Return: {m.get('avg_return', 0):+.1f}% | Sharpe: {m.get('avg_sharpe', 0):.2f} | "
              f"MDD: {m.get('worst_max_dd', 0):.1f}% | Spread: {m.get('return_spread', 0):.0f}pp")
        print(f"    Params: {p}")
        results.append({
            'trial': trial.number,
            'values': list(trial.values),
            'metrics': m,
            'params': p,
        })

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), '..', args.output)
    with open(output_path, 'w') as f:
        json.dump({
            'pareto_front': results,
            'total_trials': args.trials,
            'duration_hours': total_dur / 3600,
            'validation_dates': VALIDATION_DATES,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")

    # Print the "best balanced" solution (highest Sharpe with MDD < 30%)
    best_balanced = None
    for trial in pareto:
        m = trial.user_attrs.get('metrics', {})
        if m.get('worst_max_dd', 100) <= 30 and m.get('avg_return', 0) >= 200:
            if best_balanced is None or m.get('avg_sharpe', 0) > best_balanced.user_attrs.get('metrics', {}).get('avg_sharpe', 0):
                best_balanced = trial

    if best_balanced:
        m = best_balanced.user_attrs['metrics']
        p = best_balanced.user_attrs['params']
        print(f"\n{'='*60}")
        print(f"BEST BALANCED (MDD<30%, Return>200%):")
        print(f"  Return: {m['avg_return']:+.1f}% | Sharpe: {m['avg_sharpe']:.2f} | "
              f"MDD: {m['worst_max_dd']:.1f}% | Spread: {m['return_spread']:.0f}pp")
        print(f"  Params: {json.dumps(p, indent=4)}")
        print(f"{'='*60}")
    else:
        print("\nNo solution found with MDD<30% and Return>200%")


if __name__ == '__main__':
    main()
