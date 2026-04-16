#!/usr/bin/env python3
"""
Local Walk-Forward Runner — Run WF sims locally with high trial counts.

No Lambda timeout constraint. Uses local pickle + prod RDS.

Usage:
    source backend/venv/bin/activate
    caffeinate -i python3 scripts/local_wf_runner.py [--n-trials 100] [--start 2021-02-01] [--end 2026-02-01]

    # Keep machine awake: caffeinate -i prevents idle sleep
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
import traceback
from datetime import datetime as _dt

# --- Result safety helpers ---
# After the Apr 16 29h run lost per-period params because the final DB INSERT
# crashed with an asyncpg ConnectionDoesNotExistError, we always pickle the
# result object to /tmp BEFORE attempting the DB write, retry the INSERT on
# connection errors, and install signal handlers so an accidental kill still
# flushes state. Losing 29h of compute to a single unhandled connection drop
# is not acceptable.

_PICKLE_PATH = os.environ.get("WF_RESULT_PICKLE", "/tmp/wf_run_result.pkl")
_JSON_PATH = os.environ.get("WF_RESULT_JSON", "/tmp/wf_run_result.json")
_current_result_ref = {"result": None}  # captured by handlers


def _safe_pickle(obj, path):
    """Pickle obj to path atomically (write-then-rename)."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
        sz = os.path.getsize(path) / 1024 / 1024
        print(f"💾 Result pickled to {path} ({sz:.1f} MB)")
        return True
    except Exception as e:
        print(f"⚠️  Pickle to {path} failed: {e}")
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass
        return False


def _safe_json_dump(result, path):
    """Best-effort JSON dump of the scalar summary (for humans) — never raises."""
    try:
        summary = {
            "captured_at": _dt.utcnow().isoformat() + "Z",
            "total_return_pct": getattr(result, "total_return_pct", None),
            "sharpe_ratio": getattr(result, "sharpe_ratio", None),
            "max_drawdown_pct": getattr(result, "max_drawdown_pct", None),
            "benchmark_return_pct": getattr(result, "benchmark_return_pct", None),
            "num_strategy_switches": getattr(result, "num_strategy_switches", None),
            "total_trades": getattr(result, "total_trades", None),
            "win_rate_pct": getattr(result, "win_rate_pct", None),
            "job_id": getattr(result, "job_id", None),
            "switch_history_count": len(getattr(result, "switch_history", []) or []),
            "equity_curve_count": len(getattr(result, "equity_curve", []) or []),
            "trades_count": len(getattr(result, "trades", []) or []),
        }
        with open(path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"📝 Summary JSON written to {path}")
    except Exception as e:
        print(f"⚠️  JSON dump failed: {e}")


def _install_signal_handlers():
    """On SIGINT/SIGTERM, flush result pickle before exit."""
    def _handler(signum, _frame):
        print(f"\n🛑 Signal {signum} received — flushing result before exit")
        r = _current_result_ref.get("result")
        if r is not None:
            _safe_pickle(r, _PICKLE_PATH)
            _safe_json_dump(r, _JSON_PATH)
        else:
            print("⚠️  No result captured yet — nothing to save")
        # Re-raise default behavior so process actually exits
        sys.exit(130 if signum == signal.SIGINT else 143)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Set environment BEFORE importing app modules
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
os.environ.setdefault('LAMBDA_ROLE', 'worker')  # Ensure worker-mode imports


def parse_args():
    p = argparse.ArgumentParser(description='Local Walk-Forward Runner')
    p.add_argument('--n-trials', type=int, default=100, help='Optuna trials per period (default: 100)')
    p.add_argument('--start', default='2021-02-01', help='Sim start date (default: 2021-02-01)')
    p.add_argument('--end', default='2026-02-01', help='Sim end date (default: 2026-02-01)')
    p.add_argument('--max-symbols', type=int, default=200, help='Symbol universe size (default: 200)')
    p.add_argument('--optimizer', default='v2m', help='Optimizer version: v2m, v2c, v2 (default: v2m)')
    p.add_argument('--risk-pref', type=float, default=0.8, help='Risk preference 0-1 (default: 0.8)')
    p.add_argument('--warmup', type=int, default=0, help='Warmup periods before optimizer kicks in (default: 0)')
    p.add_argument('--ensemble', type=int, default=0, help='Ensemble seeds (0=disabled, default: 0)')
    p.add_argument('--pickle', default='backend/data/all_data.pkl.gz', help='Path to pickle file')
    p.add_argument('--strategy-id', type=int, default=5, help='Strategy ID (default: 5 = ensemble)')
    p.add_argument('--near-50d-high', type=float, default=3.0, help='Breakout window pct (default: 3.0)')
    p.add_argument('--trailing-stop', type=float, default=12.0, help='Trailing stop pct (default: 12.0)')
    p.add_argument('--dwap-threshold', type=float, default=5.0, help='DWAP threshold pct (default: 5.0)')
    p.add_argument('--max-positions', type=int, default=6, help='Max positions (default: 6)')
    p.add_argument('--position-size', type=float, default=15.0, help='Position size pct (default: 15.0)')
    p.add_argument('--panic-only', action='store_true', help='Only exit on panic crash (not SPY < 200MA)')
    p.add_argument('--profit-lock', type=float, default=0, help='Tighten stop once up X%% (0=disabled)')
    p.add_argument('--profit-lock-stop', type=float, default=6.0, help='Tightened trailing stop %% (default: 6)')
    p.add_argument('--megacap-fallback', type=int, default=0, help='Buy top N large-caps when no primary signals (0=disabled)')
    p.add_argument('--no-ai', action='store_true', help='Disable AI optimizer (use fixed params)')
    p.add_argument('--rs-slots', type=int, default=0, help='RS Leaders slots (0=disabled, default: 0)')
    p.add_argument('--rs-stop', type=float, default=0, help='RS trailing stop pct (0=same as primary, e.g. 20 for 20%%)')
    p.add_argument('--dry-run', action='store_true', help='Print config and exit without running')
    return p.parse_args()


def load_pickle(pickle_path: str) -> dict:
    """Load pickle data into scanner service cache."""
    abs_path = os.path.join(os.path.dirname(__file__), '..', pickle_path)
    if not os.path.exists(abs_path):
        # Try as absolute
        abs_path = pickle_path
    if not os.path.exists(abs_path):
        print(f"❌ Pickle not found: {pickle_path}")
        sys.exit(1)

    size_mb = os.path.getsize(abs_path) / 1024 / 1024
    print(f"📦 Loading pickle: {abs_path} ({size_mb:.1f} MB)")
    t0 = time.time()
    with gzip.open(abs_path, 'rb') as f:
        data = pickle.load(f)
    dur = time.time() - t0
    print(f"✅ Loaded {len(data)} symbols in {dur:.1f}s")
    return data


async def run_simulation(args):
    """Run the walk-forward simulation."""
    from datetime import datetime
    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.core.database import async_session

    # Load data into scanner cache
    data_cache = load_pickle(args.pickle)
    scanner_service.data_cache = data_cache
    scanner_service.universe = list(data_cache.keys())

    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(args.end, '%Y-%m-%d')

    config = {
        'start_date': args.start,
        'end_date': args.end,
        'n_trials': args.n_trials,
        'max_symbols': args.max_symbols,
        'optimizer_version': args.optimizer,
        'risk_preference': args.risk_pref,
        'strategy_id': args.strategy_id,
    }

    print(f"\n{'='*60}")
    print(f"Walk-Forward Simulation")
    print(f"{'='*60}")
    print(f"  Period:     {args.start} → {args.end}")
    print(f"  Trials:     {args.n_trials} per period")
    print(f"  Symbols:    {args.max_symbols}")
    print(f"  Optimizer:  {args.optimizer}")
    print(f"  Risk pref:  {args.risk_pref}")
    print(f"  Warmup:     {args.warmup} periods")
    print(f"  Ensemble:   {args.ensemble} seeds")
    print(f"  Strategy:   {args.strategy_id}")
    print(f"  Positions:  {args.max_positions} @ {args.position_size}%")
    print(f"  Near 50d:   {args.near_50d_high}%")
    print(f"  Trail stop: {args.trailing_stop}%")
    print(f"  DWAP thr:   {args.dwap_threshold}%")
    print(f"  Panic only: {args.panic_only}")
    print(f"  RS Leaders: {args.rs_slots} slots (stop: {args.rs_stop}%)" if args.rs_slots else f"  RS Leaders: disabled")
    print(f"  AI:         {not args.no_ai}")
    print(f"  Pickle:     {len(data_cache)} symbols")
    print(f"{'='*60}\n")

    from app.core.config import settings
    if args.panic_only:
        settings.MARKET_FILTER_PANIC_ONLY = True
    # Store RS stop on settings so backtester can read it (hacky but works for testing)
    settings._rs_trailing_stop_pct = args.rs_stop / 100 if args.rs_stop > 0 else 0

    if args.dry_run:
        print("🏁 Dry run — exiting without running simulation")
        return

    _install_signal_handlers()
    print(f"🛡️  Signal handlers installed — SIGINT/SIGTERM will flush {_PICKLE_PATH}")

    t0 = time.time()
    result = None
    run_err = None

    try:
        async with async_session() as db:
            result = await walk_forward_service.run_walk_forward_simulation(
                db=db,
                start_date=start,
                end_date=end,
                reoptimization_frequency='biweekly',
                min_score_diff=10.0,
                enable_ai_optimization=not args.no_ai,
                max_symbols=args.max_symbols,
                fixed_strategy_id=args.strategy_id,
                n_trials=args.n_trials,
                carry_positions=True,
                max_positions=args.max_positions,
                position_size_pct=args.position_size,
                near_50d_high_pct=args.near_50d_high,
                trailing_stop_pct=args.trailing_stop,
                dwap_threshold_pct=args.dwap_threshold,
                optimizer_version=args.optimizer,
                risk_preference=args.risk_pref,
                warmup_periods=args.warmup,
                ensemble_seeds=args.ensemble,
                periods_limit=0,  # No limit locally — run all periods
                profit_lock_pct=args.profit_lock,
                profit_lock_stop_pct=args.profit_lock_stop,
            )
        _current_result_ref["result"] = result
    except Exception as e:
        run_err = e
        print(f"\n❌ run_walk_forward_simulation raised: {e!r}")
        traceback.print_exc()
        # Service may have populated a partial result on the session before raising — try to recover
        # by checking the session's attribute cache (best-effort, usually empty)
        pass

    # ALWAYS pickle whatever we have, even on partial / failed runs
    if result is not None:
        _safe_pickle(result, _PICKLE_PATH)
        _safe_json_dump(result, _JSON_PATH)
    else:
        print("⚠️  No result object captured — nothing to pickle. Check logs above.")

    if run_err is not None:
        print(f"\n❌ Run failed — see error above. Pickle (if any) is at {_PICKLE_PATH}")
        sys.exit(1)

    dur = time.time() - t0
    hours = dur / 3600
    mins = (dur % 3600) / 60

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  Total return: {result.total_return_pct:+.1f}%")
    print(f"  Sharpe ratio: {result.sharpe_ratio:.2f}")
    print(f"  Max drawdown: {result.max_drawdown_pct:.1f}%")
    print(f"  Total trades: {getattr(result, 'total_trades', len(result.trades))}")
    print(f"  Win rate:     {getattr(result, 'win_rate_pct', 0):.1f}%")
    print(f"  Benchmark:    {getattr(result, 'benchmark_return_pct', 0):+.1f}% (SPY)")
    print(f"  Duration:     {int(hours)}h {int(mins)}m")
    if result.job_id:
        print(f"  Job ID:       {result.job_id}")
    print(f"{'='*60}")

    # Calculate annualized
    years = (end - start).days / 365.25
    if result.total_return_pct > 0:
        ann = ((1 + result.total_return_pct / 100) ** (1 / years) - 1) * 100
    else:
        ann = result.total_return_pct / years
    print(f"  Annualized:   {ann:+.1f}%")
    print(f"  vs SPY:       {result.total_return_pct - result.benchmark_return_pct:+.1f}pp")


def main():
    args = parse_args()
    asyncio.run(run_simulation(args))


if __name__ == '__main__':
    main()
