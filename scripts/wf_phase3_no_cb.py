#!/usr/bin/env python3
"""
Phase 3 WF runner — TPE with circuit-breaker params LOCKED at canonical defaults.

Phase 2 diagnosis (May 21 2026): TPE+CB had destructive interaction. TPE
optimized per-period drawdown by picking aggressive CB params (e.g.
stops=2, pause_days=20), which fired 18× over 5y on Date 3 totaling 150
pause-days in cash. That cash-drag tanked 5 of 8 dates to single-digit
returns. Canonical Apr 28 baseline used FIXED CB defaults (stops=3,
pause_days=10) and worked fine.

Phase 3 hypothesis: remove CB from the TPE search space. TPE keeps
tuning the other params; CB stays at the StrategyParams defaults the
backtester reads when no override is supplied (stops=3, pause=10d, 0%).

Usage:
    source backend/venv/bin/activate
    WF_RESULT_PICKLE=/tmp/tpe_phase3/2021-01-25/wf_run_result.pkl \\
    WF_RESULT_JSON=/tmp/tpe_phase3/2021-01-25/wf_run_result.json \\
    caffeinate -i python3 scripts/wf_phase3_no_cb.py --start 2021-01-25
"""
import argparse
import asyncio
import gzip
import json
import os
import pickle
import signal
import sys
import time
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# DATABASE_URL from .env
if not os.environ.get('DATABASE_URL'):
    _dotenv = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(_dotenv):
        for _line in open(_dotenv):
            if _line.startswith('DATABASE_URL='):
                os.environ['DATABASE_URL'] = _line.strip().split('=', 1)[1]
                break
os.environ.setdefault('LAMBDA_ROLE', 'worker')

# Constants
PICKLE_PATH_DEFAULT = '/tmp/parity_test/prod_after_refetch.pkl.gz'
N_TRIALS = 30
OPTIMIZER = "v2m"
RISK_PREF = 0.3


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--start', required=True, help='Start date, e.g. 2021-01-25')
    p.add_argument('--end', default=None, help='End date (default: start + 5y)')
    p.add_argument('--pickle', default=PICKLE_PATH_DEFAULT)
    p.add_argument('--strategy-id', type=int, default=5)
    p.add_argument('--max-symbols', type=int, default=200)
    p.add_argument('--n-trials', type=int, default=N_TRIALS)
    p.add_argument('--risk-pref', type=float, default=RISK_PREF)
    return p.parse_args()


def load_pickle(path):
    abs_path = os.path.join(os.path.dirname(__file__), '..', path)
    if not os.path.exists(abs_path):
        abs_path = path
    print(f"📦 Loading pickle: {abs_path}")
    with gzip.open(abs_path, 'rb') as f:
        return pickle.load(f)


async def run(args):
    # === THE PHASE 3 PATCH ===
    # Strip CB params from the V2M search space BEFORE the optimizer reads it.
    # The backtester defaults (stops=3, pause_days=10, tighten_pct=0) will
    # be used since StrategyParams defaults populate when TPE doesn't suggest.
    from app.services.strategy_params_v2 import V2_MEDIUM_PARAM_SPACES
    cb_keys = ['circuit_breaker_stops', 'circuit_breaker_pause_days', 'circuit_breaker_tighten_pct']
    for k in cb_keys:
        popped = V2_MEDIUM_PARAM_SPACES['ensemble'].pop(k, None)
        if popped is not None:
            print(f"🔒 Removed from V2M search space: {k} (was {popped})")
    print()

    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.core.database import async_session

    # Compute end_date if not given
    end_str = args.end
    if end_str is None:
        sy, sm, sd = args.start.split('-')
        end_str = f"{int(sy) + 5}-{sm}-{sd}"

    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')

    data_cache = load_pickle(args.pickle)
    scanner_service.data_cache = data_cache
    scanner_service.universe = list(data_cache.keys())

    print(f"Phase 3 WF: {args.start} → {end_str}")
    print(f"  strategy_id={args.strategy_id}, max_symbols={args.max_symbols}")
    print(f"  optimizer=v2m, risk_pref={args.risk_pref}, n_trials={args.n_trials}")
    print(f"  CB params: LOCKED at StrategyParams defaults (3 stops / 10d pause)")
    print(f"  Pickle: {len(data_cache)} symbols\n")

    pickle_out = os.environ.get('WF_RESULT_PICKLE', f'/tmp/phase3_{args.start}/result.pkl')
    json_out = os.environ.get('WF_RESULT_JSON', f'/tmp/phase3_{args.start}/result.json')
    os.makedirs(os.path.dirname(pickle_out), exist_ok=True)

    # Install signal handlers to flush on SIGINT/SIGTERM
    _ref = {'r': None}

    def _flush(signum, frame):
        print(f"\n🛑 Signal {signum} — flushing partial result")
        r = _ref.get('r')
        if r is not None:
            with open(pickle_out, 'wb') as f:
                pickle.dump(r, f, protocol=pickle.HIGHEST_PROTOCOL)
        sys.exit(130)
    signal.signal(signal.SIGINT, _flush)
    signal.signal(signal.SIGTERM, _flush)

    t0 = time.time()
    async with async_session() as db:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db,
            start_date=start,
            end_date=end,
            reoptimization_frequency='biweekly',
            min_score_diff=10.0,
            enable_ai_optimization=True,
            max_symbols=args.max_symbols,
            fixed_strategy_id=args.strategy_id,
            n_trials=args.n_trials,
            carry_positions=True,
            optimizer_version='v2m',
            risk_preference=args.risk_pref,
            warmup_periods=0,
            param_smoothing=0.0,
            ensemble_seeds=0,
            periods_limit=0,
        )
    _ref['r'] = result
    dur = time.time() - t0

    with open(pickle_out, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    summary = {
        'total_return_pct': result.total_return_pct,
        'sharpe_ratio': result.sharpe_ratio,
        'max_drawdown_pct': result.max_drawdown_pct,
        'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
        'trades_count': len(result.trades),
        'pause_count': len(getattr(result, 'pause_events', []) or []),
        'duration_minutes': dur / 60,
    }
    with open(json_out, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n{'=' * 60}")
    print("RESULTS — Phase 3 (CB locked at defaults)")
    print(f"{'=' * 60}")
    print(f"  Total return:  {result.total_return_pct:+.2f}%")
    print(f"  Sharpe:        {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:         {result.max_drawdown_pct:.2f}%")
    print(f"  Trades:        {len(result.trades)}")
    print(f"  CB pauses:     {len(getattr(result, 'pause_events', []) or [])}")
    print(f"  Duration:      {dur / 60:.1f} min")


def main():
    args = parse_args()
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
