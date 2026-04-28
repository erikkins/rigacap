"""
RigaCap API - FastAPI Backend with Real Data

Connects to:
- yfinance for market data (5 years historical)
- PostgreSQL for persistence
- Real DWAP-based signal generation
- APScheduler for daily EOD updates
"""

import logging
from contextlib import asynccontextmanager
from mangum import Mangum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
import pandas as pd

from app.core.config import settings
from app.core.database import init_db, get_db, Position as DBPosition, Trade as DBTrade, Signal as DBSignal, User, async_session
from app.core.security import get_current_user, get_admin_user, require_valid_subscription
from app.api.signals import router as signals_router, public_router as public_signals_router
from app.api.email import router as email_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.admin import router as admin_router
from app.api.social import router as social_router
from app.api.push import router as push_router
from app.api.two_factor import router as two_factor_router
from app.services.scanner import scanner_service
# scheduler_service is deferred — imported inline by:
#   * the lifespan startup (local dev only; Lambda doesn't run lifespan)
#   * handler() (worker event paths reference it many places)
#   * /health, /scheduler-status, /scheduler/run-now endpoints
# Saves ~235ms of Python module import on API Lambda cold start, where
# scheduler_service is purely a status-getter and never actually drives
# anything (cron lives on the Worker, not the API).
from app.services.backtester import backtester_service
from app.services.market_analysis import market_analysis_service
from app.services.data_export import data_export_service


# ============================================================================
# Helper Functions
# ============================================================================

def get_split_adjusted_price(symbol: str, entry_date: datetime, fallback_price: float) -> float:
    """
    Get the split-adjusted close price for a symbol on a given date.

    yfinance retroactively adjusts all historical prices after splits,
    so looking up the close price for an entry date gives us the
    split-adjusted value automatically.

    Args:
        symbol: Stock symbol
        entry_date: Date the position was opened
        fallback_price: Original stored entry price (used if date not found)

    Returns:
        Split-adjusted close price, or fallback_price if not found
    """
    if symbol not in scanner_service.data_cache:
        return fallback_price

    df = scanner_service.data_cache[symbol]
    if df.empty:
        return fallback_price

    # Convert entry_date to date-only for comparison
    target_date = entry_date.date() if hasattr(entry_date, 'date') else entry_date

    # Find the closest date on or before entry_date
    # (markets may be closed on exact entry date)
    try:
        # Filter to dates <= entry_date
        df_before = df[df.index.date <= target_date]
        if df_before.empty:
            return fallback_price

        # Get the most recent date
        adjusted_price = float(df_before.iloc[-1]['close'])
        return adjusted_price
    except Exception:
        return fallback_price


async def _wait_for_alpaca_settlement(
    lambda_context=None,
    max_retries: int = 10,
    retry_interval: int = 30,
    min_spy_volume: int = 10_000_000,
) -> dict:
    """
    Pre-flight: wait for Alpaca to settle today's bars before bulk fetch.
    Fetches SPY from Alpaca only. Checks today's bar exists with real volume.
    Returns dict with settled, attempts, elapsed, fallback_to_yfinance.
    """
    import asyncio
    import time
    from zoneinfo import ZoneInfo
    from app.services.market_data_provider import AlpacaProvider
    from app.services.health_monitor_service import _last_market_day

    now_et = datetime.now(ZoneInfo('America/New_York'))
    expected_date = _last_market_day(now_et.date())
    start = time.time()
    result = {"settled": False, "attempts": 0, "spy_date": None,
              "spy_volume": None, "fallback_to_yfinance": False}

    alpaca = AlpacaProvider()
    five_days_ago = (expected_date - timedelta(days=7)).strftime("%Y-%m-%d")

    for attempt in range(1, max_retries + 1):
        result["attempts"] = attempt

        # Bail if Lambda running low on time (need 10 min for scan+export)
        if lambda_context:
            remaining = lambda_context.get_remaining_time_in_millis()
            if remaining < 600_000:
                print(f"⏰ Settlement check: bailing, only {remaining/1000:.0f}s left")
                break

        try:
            bars = await alpaca.fetch_bars(["SPY"], start_date=five_days_ago)
            spy_df = bars.get("SPY")
            if spy_df is not None and len(spy_df) > 0:
                last_date = spy_df.index.max()
                last_date_normalized = pd.Timestamp(last_date).normalize().tz_localize(None)
                expected_ts = pd.Timestamp(expected_date)
                last_vol = int(spy_df.iloc[-1].get("volume", 0))
                result["spy_date"] = str(last_date_normalized.date())
                result["spy_volume"] = last_vol

                if last_date_normalized >= expected_ts and last_vol >= min_spy_volume:
                    result["settled"] = True
                    print(f"📡 Alpaca settled: attempt {attempt}, "
                          f"SPY {last_date_normalized.date()}, vol={last_vol:,}")
                    break
                else:
                    print(f"📡 Settlement attempt {attempt}/{max_retries}: "
                          f"SPY date={last_date_normalized.date()} (need {expected_date}), "
                          f"vol={last_vol:,} (need {min_spy_volume:,}) — waiting {retry_interval}s...")
            else:
                print(f"📡 Settlement attempt {attempt}/{max_retries}: "
                      f"no SPY data from Alpaca — waiting {retry_interval}s...")
        except Exception as e:
            print(f"📡 Settlement attempt {attempt}/{max_retries}: error {e} — waiting {retry_interval}s...")

        if attempt < max_retries:
            await asyncio.sleep(retry_interval)

    result["elapsed_seconds"] = time.time() - start
    if not result["settled"]:
        result["fallback_to_yfinance"] = True
    return result


# ============================================================================
# Pydantic Models
# ============================================================================

class PositionResponse(BaseModel):
    id: int
    symbol: str
    shares: float
    entry_price: float
    entry_date: str
    current_price: float
    stop_loss: float
    profit_target: float
    pnl_pct: float
    days_held: int
    # Trailing stop fields
    high_water_mark: float = 0.0  # Highest price since entry
    trailing_stop_price: float = 0.0  # Current trailing stop level
    trailing_stop_pct: float = 12.0  # Trailing stop percentage
    distance_to_stop_pct: float = 0.0  # How far price is from trailing stop (negative = below stop)
    sell_signal: str = "hold"  # hold, warning, sell


class PositionsListResponse(BaseModel):
    positions: List[PositionResponse]
    total_value: float
    total_pnl_pct: float


class OpenPositionRequest(BaseModel):
    symbol: str
    shares: Optional[float] = None
    price: Optional[float] = None
    entry_date: Optional[str] = None  # YYYY-MM-DD, for time-travel mode


class EquityPoint(BaseModel):
    date: str
    equity: float


# ============================================================================
# Lifespan (startup/shutdown)
# ============================================================================

async def store_signals_callback(signals):
    """Callback to store signals in database and export to S3 after scheduled scan"""
    if not signals:
        return

    # NOTE: latest.json (legacy DWAP signal export) is DEPRECATED.
    # dashboard.json is the single source of truth for all signals.
    # See signal consistency rule (Mar 27 2026 incident).

    # Store in database for historical tracking
    try:
        async with async_session() as db:
            for sig in signals:
                db_signal = DBSignal(
                    symbol=sig.symbol,
                    signal_type=sig.signal_type,
                    price=sig.price,
                    dwap=sig.dwap,
                    pct_above_dwap=sig.pct_above_dwap,
                    volume=sig.volume,
                    volume_ratio=sig.volume_ratio,
                    stop_loss=sig.stop_loss,
                    profit_target=sig.profit_target,
                    is_strong=sig.is_strong,
                    status="active"
                )
                db.add(db_signal)
            await db.commit()
            print(f"💾 Stored {len(signals)} signals in database")
    except Exception as e:
        print(f"⚠️ Database storage skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup - skip DB for Lambda to avoid INIT timeout"""
    print("🚀 Starting RigaCap API...")

    import os
    is_lambda = os.environ.get("ENVIRONMENT") == "prod"

    if is_lambda:
        # Lambda: Skip DB init during startup to avoid 10s INIT timeout
        # Database will initialize lazily on first request
        print("📦 Lambda mode: Skipping DB init (will initialize on first request)")
    else:
        # Local dev: Initialize DB and start scheduler
        try:
            await init_db()
        except Exception as e:
            print(f"⚠️ Database not available: {e}")
            print("   Running in memory-only mode (positions won't persist)")

        cached_data = data_export_service.import_all()
        if cached_data:
            scanner_service.data_cache = cached_data
            print(f"📊 Loaded {len(cached_data)} symbols from cached parquet files")
        from app.services.scheduler import scheduler_service as _sched
        _sched.add_callback(store_signals_callback)
        _sched.start()
        print("📅 Scheduler started for daily EOD updates")

    yield

    # Cleanup
    print("👋 Shutting down RigaCap API...")
    if not is_lambda:
        from app.services.scheduler import scheduler_service as _sched
        _sched.stop()


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="RigaCap API",
    version="2.0.0",
    description="DWAP-based stock trading signals with 5-year historical data",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Include API routers
app.include_router(signals_router, prefix="/api/signals", tags=["signals"])
app.include_router(email_router, prefix="/api/email", tags=["email"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(billing_router, prefix="/api/billing", tags=["billing"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(social_router, prefix="/api/admin/social", tags=["social"])
app.include_router(push_router, prefix="/api/push", tags=["push"])
app.include_router(two_factor_router, prefix="/api/auth/2fa", tags=["2fa"])
app.include_router(public_signals_router, prefix="/api/public", tags=["public"])

# Lambda handler (for AWS Lambda deployment)
# lifespan="off" avoids issues with event loop reuse on warm Lambdas
_mangum_handler = None
_lambda_data_loaded = False


def _ensure_lambda_data_loaded():
    """Load data from S3 on Lambda cold start (runs once per container)."""
    global _lambda_data_loaded
    if _lambda_data_loaded:
        return

    import os
    if os.environ.get("ENVIRONMENT") != "prod":
        _lambda_data_loaded = True
        return

    # API Lambda skips pickle loading entirely — dashboard reads from S3 JSON cache,
    # positions from DB. This keeps API cold starts fast and memory under 1 GB.
    if os.environ.get("LAMBDA_ROLE") == "api":
        print("⚡ API Lambda: skipping pickle load (LAMBDA_ROLE=api)")
        _lambda_data_loaded = True
        return

    # Only load if cache is empty
    if not scanner_service.data_cache:
        print("📦 Lambda cold start: Loading data from S3...")
        try:
            cached_data = data_export_service.import_all()
            if cached_data:
                scanner_service.data_cache = cached_data
                print(f"✅ Loaded {len(cached_data)} symbols from S3")
                _lambda_data_loaded = True
            else:
                print("⚠️ No cached data found in S3 — will retry next request")
        except Exception as e:
            print(f"⚠️ Failed to load data from S3: {e} — will retry next request")
    else:
        _lambda_data_loaded = True


async def _run_walk_forward_job(job_config: dict, wf_state_key: str = None):
    """Run walk-forward simulation job asynchronously.

    Supports self-chaining for large simulations that exceed Lambda's 900s timeout.
    When periods_limit > 0, processes a chunk of periods, saves state to S3,
    and async-invokes self for the next chunk.

    Args:
        job_config: Walk-forward job configuration dict
        wf_state_key: S3 key for continuation state (set by self-chaining)
    """
    import json, os
    from datetime import datetime
    from app.services.walk_forward_service import walk_forward_service
    from sqlalchemy import select
    from app.core.database import WalkForwardSimulation

    job_id = job_config.get("job_id")
    periods_limit = job_config.get("periods_limit", 0)
    continuation_state = None

    # Load continuation state from S3 if resuming
    if wf_state_key:
        try:
            import boto3
            from app.services.data_export import S3_BUCKET
            s3 = boto3.client('s3', region_name='us-east-1')
            resp = s3.get_object(Bucket=S3_BUCKET, Key=wf_state_key)
            continuation_state = json.loads(resp['Body'].read())
            if continuation_state.get("completed"):
                print(f"[ASYNC-WF] Job already completed (return={continuation_state.get('total_return_pct')}%), skipping")
                return {"status": "already_completed", "job_id": continuation_state.get("job_id")}
            job_id = continuation_state.get("job_id", job_id)
            print(f"[ASYNC-WF] Loaded continuation state from s3://{S3_BUCKET}/{wf_state_key}, "
                  f"job_id={job_id}, period_index={continuation_state.get('period_index')}")
        except Exception as e:
            print(f"[ASYNC-WF] Failed to load continuation state: {e}")
            return {"status": "failed", "error": f"Failed to load continuation state: {e}"}

    async with async_session() as db:
        try:
            # If no job_id provided, create a new job record (first chunk only)
            if not job_id:
                start = datetime.strptime(job_config["start_date"], "%Y-%m-%d")
                end = datetime.strptime(job_config["end_date"], "%Y-%m-%d")
                new_job = WalkForwardSimulation(
                    simulation_date=datetime.utcnow(),
                    start_date=start,
                    end_date=end,
                    reoptimization_frequency=job_config.get("frequency", "biweekly"),
                    status="running",
                    total_return_pct=0,
                    sharpe_ratio=0,
                    max_drawdown_pct=0,
                    num_strategy_switches=0,
                    benchmark_return_pct=0,
                )
                db.add(new_job)
                await db.commit()
                await db.refresh(new_job)
                job_id = new_job.id
                print(f"[ASYNC-WF] Created new job {job_id}")
            elif not wf_state_key:
                # First invocation with explicit job_id — update status
                result = await db.execute(
                    select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = "running"
                    await db.commit()

            chunk_label = f"period {continuation_state['period_index']}" if continuation_state else "start"
            print(f"[ASYNC-WF] Walk-forward job {job_id} ({chunk_label}), periods_limit={periods_limit}")

            # Allow WF payload to override market filter mode for A/B testing
            if "panic_only" in job_config:
                from app.core.config import settings
                settings.MARKET_FILTER_PANIC_ONLY = job_config["panic_only"]
                print(f"[ASYNC-WF] Market filter override: panic_only={job_config['panic_only']}")

            # Run the simulation
            start = datetime.strptime(job_config["start_date"], "%Y-%m-%d")
            end = datetime.strptime(job_config["end_date"], "%Y-%m-%d")

            sim_result = await walk_forward_service.run_walk_forward_simulation(
                db=db,
                start_date=start,
                end_date=end,
                reoptimization_frequency=job_config.get("frequency", "biweekly"),
                min_score_diff=job_config.get("min_score_diff", 10.0),
                enable_ai_optimization=job_config.get("enable_ai", False),
                max_symbols=job_config.get("max_symbols", 100),
                existing_job_id=job_id,
                fixed_strategy_id=job_config.get("strategy_id"),
                n_trials=job_config.get("n_trials", 30),
                carry_positions=job_config.get("carry_positions", True),
                max_positions=job_config.get("max_positions"),
                position_size_pct=job_config.get("position_size_pct"),
                periods_limit=periods_limit,
                continuation_state=continuation_state,
                optimizer_version=job_config.get("optimizer_version", "v1"),
                risk_preference=job_config.get("risk_preference", 0.5),
                tier1_size=job_config.get("tier1_size", 0),
                tier1_bonus=job_config.get("tier1_bonus", 0.0),
                dwap_threshold_pct=job_config.get("dwap_threshold_pct"),
                near_50d_high_pct=job_config.get("near_50d_high_pct"),
                trailing_stop_pct=job_config.get("trailing_stop_pct"),
                regime_reentry_mode=job_config.get("regime_reentry_mode", False),
                bear_keep_pct=job_config.get("bear_keep_pct", 0.0),
                graduated_reentry=job_config.get("graduated_reentry", False),
                param_smoothing=job_config.get("param_smoothing", 0.0),
                warmup_periods=job_config.get("warmup_periods", 0),
                ensemble_seeds=job_config.get("ensemble_seeds", 0),
                regime_fixed_params=job_config.get("regime_fixed_params"),
            )

            # Check if more chunks are needed
            if sim_result.continuation_state:
                # Save state to S3 and self-chain
                import boto3
                from app.services.data_export import S3_BUCKET
                s3 = boto3.client('s3', region_name='us-east-1')
                state_key = f"wf-state/{job_id}.json"
                state_data = sim_result.continuation_state
                state_data["job_id"] = job_id  # Ensure job_id is in state
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=state_key,
                    Body=json.dumps(state_data),
                    ContentType='application/json',
                )
                next_period = state_data.get("period_index", "?")
                print(f"[ASYNC-WF] Saved state to s3://{S3_BUCKET}/{state_key} (next period: {next_period})")

                # Self-invoke for next chunk
                chain_payload = {
                    "walk_forward_job": job_config,
                    "wf_state_key": state_key,
                }
                # Ensure job_id is in the config for continuation
                chain_payload["walk_forward_job"]["job_id"] = job_id
                boto3.client('lambda', region_name='us-east-1').invoke(
                    FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                    InvocationType='Event',  # async fire-and-forget
                    Payload=json.dumps(chain_payload),
                )
                print(f"[ASYNC-WF] 🔗 Self-chained job {job_id} for period {next_period}")
                return {
                    "status": "chaining",
                    "job_id": job_id,
                    "next_period": next_period,
                    "state_key": state_key,
                }
            else:
                # Simulation complete — mark state file as done (don't delete, for monitoring)
                if wf_state_key:
                    try:
                        import boto3
                        from app.services.data_export import S3_BUCKET
                        s3 = boto3.client('s3', region_name='us-east-1')
                        s3.put_object(
                            Bucket=S3_BUCKET,
                            Key=wf_state_key,
                            Body=json.dumps({
                                "completed": True,
                                "job_id": job_id,
                                "total_return_pct": sim_result.total_return_pct,
                                "sharpe_ratio": getattr(sim_result, 'sharpe_ratio', None),
                                "max_drawdown_pct": getattr(sim_result, 'max_drawdown_pct', None),
                                "total_trades": getattr(sim_result, 'total_trades', None),
                            }, default=str),
                            ContentType='application/json',
                        )
                        print(f"[ASYNC-WF] Marked state file complete: {wf_state_key}")
                    except Exception as cleanup_err:
                        print(f"[ASYNC-WF] Warning: failed to update state file: {cleanup_err}")

                print(f"[ASYNC-WF] Job {job_id} completed: return={sim_result.total_return_pct}%")
                return {"status": "completed", "job_id": job_id}

        except Exception as e:
            import traceback
            print(f"[ASYNC-WF] Job {job_id} failed: {e}")
            print(traceback.format_exc())

            # Update job status to failed
            try:
                result = await db.execute(
                    select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.switch_history_json = json.dumps({"error": str(e)})
                    await db.commit()
            except Exception:
                pass

            return {"status": "failed", "job_id": job_id, "error": str(e)}


async def _get_walk_forward_history(limit: int = 10):
    """Get list of recent walk-forward simulations."""
    import json
    from sqlalchemy import select, desc
    from app.core.database import WalkForwardSimulation

    async with async_session() as db:
        result = await db.execute(
            select(WalkForwardSimulation)
            .order_by(desc(WalkForwardSimulation.simulation_date))
            .limit(limit)
        )
        sims = result.scalars().all()

        simulations = []
        for s in sims:
            # Try to get the initial strategy from switch_history
            strategy_name = None
            if s.switch_history_json:
                try:
                    switch_history = json.loads(s.switch_history_json)
                    if switch_history and len(switch_history) > 0:
                        strategy_name = switch_history[0].get("strategy_name")
                except (json.JSONDecodeError, KeyError):
                    pass

            simulations.append({
                "id": s.id,
                "simulation_date": s.simulation_date.isoformat() if s.simulation_date else None,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "strategy_name": strategy_name,
                "reoptimization_frequency": s.reoptimization_frequency,
                "total_return_pct": s.total_return_pct,
                "sharpe_ratio": s.sharpe_ratio,
                "max_drawdown_pct": s.max_drawdown_pct,
                "benchmark_return_pct": s.benchmark_return_pct,
                "num_strategy_switches": s.num_strategy_switches,
                "status": s.status,
                "has_trades": bool(s.trades_json),
            })

        return {
            "status": "success",
            "simulations": simulations
        }


async def _seed_and_list_strategies():
    """Seed strategies if needed and return the list."""
    from sqlalchemy import select
    from app.core.database import StrategyDefinition
    from app.api.admin import seed_strategies

    async with async_session() as db:
        # Seed strategies
        count = await seed_strategies(db)
        print(f"[SEED] Seeded {count} strategies")

        # List all strategies
        result = await db.execute(select(StrategyDefinition).order_by(StrategyDefinition.id))
        strategies = result.scalars().all()

        return {
            "status": "success",
            "seeded": count,
            "strategies": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "strategy_type": s.strategy_type,
                    "is_active": s.is_active
                }
                for s in strategies
            ]
        }


async def _list_strategies():
    """List all strategies."""
    from sqlalchemy import select
    from app.core.database import StrategyDefinition

    async with async_session() as db:
        result = await db.execute(select(StrategyDefinition).order_by(StrategyDefinition.id))
        strategies = result.scalars().all()

        return {
            "status": "success",
            "strategies": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "strategy_type": s.strategy_type,
                    "is_active": s.is_active
                }
                for s in strategies
            ]
        }


async def _get_walk_forward_trades(simulation_id: int):
    """Get detailed trades from a walk-forward simulation."""
    import json
    from sqlalchemy import select
    from app.core.database import WalkForwardSimulation

    async with async_session() as db:
        result = await db.execute(
            select(WalkForwardSimulation).where(WalkForwardSimulation.id == simulation_id)
        )
        sim = result.scalars().first()

        if not sim:
            return {"status": "error", "error": f"Simulation {simulation_id} not found"}

        trades = json.loads(sim.trades_json) if sim.trades_json else []

        # Calculate summary statistics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get('pnl_pct', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl_pct', 0) <= 0]

        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        avg_win = sum(t.get('pnl_pct', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.get('pnl_pct', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0
        total_pnl = sum(t.get('pnl_dollars', 0) for t in trades)

        # Group by exit reason
        exit_reasons = {}
        for t in trades:
            reason = t.get('exit_reason', 'unknown')
            if reason not in exit_reasons:
                exit_reasons[reason] = 0
            exit_reasons[reason] += 1

        # Get strategy name from switch history
        strategy_name = None
        if sim.switch_history_json:
            try:
                switch_history = json.loads(sim.switch_history_json)
                if switch_history and len(switch_history) > 0:
                    strategy_name = switch_history[0].get("strategy_name")
            except (json.JSONDecodeError, KeyError):
                pass

        return {
            "status": "success",
            "simulation_id": simulation_id,
            "strategy_name": strategy_name,
            "simulation_date": sim.simulation_date.isoformat() if sim.simulation_date else None,
            "start_date": sim.start_date.isoformat() if sim.start_date else None,
            "end_date": sim.end_date.isoformat() if sim.end_date else None,
            "total_return_pct": sim.total_return_pct,
            "benchmark_return_pct": sim.benchmark_return_pct,
            "trades": trades,
            "summary": {
                "total_trades": total_trades,
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "win_rate_pct": round(win_rate, 1),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "total_pnl_dollars": round(total_pnl, 2),
                "exit_reasons": exit_reasons
            }
        }


async def _notify_portfolio_change(action: str, trades: list):
    """Send admin email when the live model portfolio is modified (buys/sells)."""
    if not trades:
        return
    try:
        from app.services.email_service import admin_email_service, ADMIN_EMAILS

        if action == "BUY":
            lines = []
            for t in trades:
                sym = t.get("symbol", "?")
                price = t.get("entry_price", t.get("price", 0))
                shares = t.get("shares", 0)
                cost = t.get("cost_basis", 0)
                lines.append(f"  {sym} — {shares:.1f} shares @ ${price:.2f} (${cost:,.0f})")
            body = f"Live Model Portfolio — {len(trades)} position(s) opened:\n\n" + "\n".join(lines)
            subject = f"Portfolio BUY: {', '.join(t.get('symbol', '?') for t in trades)}"
        else:  # SELL
            lines = []
            for t in trades:
                sym = t.get("symbol", "?")
                pnl = t.get("pnl_pct", 0)
                reason = t.get("exit_reason", "unknown")
                price = t.get("exit_price", 0)
                lines.append(f"  {sym} — {pnl:+.1f}% @ ${price:.2f} ({reason})")
            body = f"Live Model Portfolio — {len(trades)} position(s) closed:\n\n" + "\n".join(lines)
            subject = f"Portfolio SELL: {', '.join(t.get('symbol', '?') for t in trades)}"

        for admin in ADMIN_EMAILS:
            await admin_email_service.send_admin_alert(admin, subject, body)
        print(f"📧 Portfolio {action} notification sent for {len(trades)} trade(s)")
    except Exception as e:
        print(f"⚠️ Portfolio notification email failed (non-fatal): {e}")


def handler(event, context):
    """
    Lambda handler that supports:
    1. Warmer events (from EventBridge scheduled warmer)
    2. Walk-forward async jobs (from async Lambda invocation)
    3. Pickle rebuild (self-chaining catch-up for missing symbols)
    4. API Gateway HTTP API events (via Mangum)
    """
    import asyncio
    import os
    # Defer scheduler_service to here — it's only used in the worker-side
    # event paths below (send_daily_emails, check_double_signal_alerts, etc.)
    # plus the FastAPI /health endpoint which has its own inline import.
    # Keeping it out of module-level shaves ~235ms off API Lambda cold start.
    from app.services.scheduler import scheduler_service
    global _mangum_handler

    # Log every non-warmer event for debugging (EventBridge async invocations were failing silently)
    if not event.get("warmer"):
        event_keys = [k for k in event.keys() if not k.startswith("_")]
        print(f"🔔 Lambda handler invoked: keys={event_keys}")

    # Pipeline health report — runs WITHOUT pickle (lightweight S3/CW/DB checks only)
    # Must be handled BEFORE _ensure_lambda_data_loaded() to skip the 2+ GB pickle load
    if event.get("pipeline_health_report"):
        print("🩺 Pipeline health report triggered")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def _run_health_report():
                from app.services.health_monitor_service import health_monitor_service
                from app.services.email_service import admin_email_service, ADMIN_EMAILS

                report = await health_monitor_service.run_all_checks()

                # Only email if there are issues (unless always_send is set)
                config = event.get("pipeline_health_report", {})
                always_send = config.get("always_send", False) if isinstance(config, dict) else False

                should_send = always_send or report.yellow_count > 0 or report.red_count > 0

                if should_send:
                    for admin in ADMIN_EMAILS:
                        await admin_email_service.send_health_report(admin, report)
                    print(f"📧 Health report emailed: {report.green_count}G/{report.yellow_count}Y/{report.red_count}R")
                else:
                    print(f"✅ All clear ({report.green_count}/{len(report.checks)} green) — no email sent")

                return {
                    "status": report.overall_status.value,
                    "green": report.green_count,
                    "yellow": report.yellow_count,
                    "red": report.red_count,
                    "email_sent": should_send,
                    "checks": [
                        {"name": c.name, "status": c.status.value, "value": c.value, "message": c.message}
                        for c in report.checks
                    ],
                }

            result = loop.run_until_complete(_run_health_report())
            return {"statusCode": 200, "body": result}
        except Exception as e:
            import traceback
            print(f"❌ Health report failed: {e}")
            print(traceback.format_exc())
            return {"statusCode": 500, "error": str(e)}

    # Run DB migrations — lightweight, no pickle needed
    if event.get("run_migration"):
        print("🔧 Running DB migrations via Lambda event")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def _run_migrations():
                from sqlalchemy import text
                from app.core.database import async_session
                results = []
                migrations = [
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS comped_at TIMESTAMP",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS comped_by UUID REFERENCES users(id)",
                ]
                # Support custom SQL via event payload (admin-only, direct Lambda invoke)
                custom_sql = event.get("sql")
                if custom_sql:
                    migrations = [custom_sql] if isinstance(custom_sql, str) else custom_sql
                async with async_session() as db:
                    for sql in migrations:
                        try:
                            result = await db.execute(text(sql))
                            row_data = None
                            if result.returns_rows:
                                row_data = [dict(r._mapping) for r in result.fetchall()]
                            results.append({"sql": sql[:80], "status": "ok", "rows": row_data})
                        except Exception as e:
                            results.append({"sql": sql[:80], "status": "error", "error": str(e)})
                    await db.commit()
                return results

            result = loop.run_until_complete(_run_migrations())
            print(f"🔧 Migration results: {result}")
            return {"statusCode": 200, "body": {"migrations": result}}
        except Exception as e:
            import traceback
            print(f"❌ Migration failed: {e}")
            print(traceback.format_exc())
            return {"statusCode": 500, "error": str(e)}

    # Unwind pre-universe-change model portfolio positions
    if event.get("unwind_old_positions"):
        print("🔄 Unwinding pre-universe-change model portfolio positions")
        try:
            cutoff_date = event.get("cutoff_date", "2026-03-09")
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def _unwind():
                from sqlalchemy import text
                from datetime import date as _date
                from app.core.database import async_session
                cutoff = _date.fromisoformat(cutoff_date)
                async with async_session() as db:
                    # Close pre-cutoff positions
                    close_result = await db.execute(text(
                        "UPDATE model_positions "
                        "SET status = 'closed', exit_date = NOW(), exit_reason = 'universe_change' "
                        "WHERE status = 'open' AND entry_date < :cutoff"
                    ), {"cutoff": cutoff})
                    closed_count = close_result.rowcount

                    # Recalculate cash from closed positions (return capital)
                    cash_result = await db.execute(text(
                        "SELECT COALESCE(SUM(shares * COALESCE(exit_price, entry_price)), 0) "
                        "FROM model_positions "
                        "WHERE exit_reason = 'universe_change' AND status = 'closed'"
                    ))
                    returned_capital = float(cash_result.scalar() or 0)

                    # Update portfolio state
                    await db.execute(text(
                        "UPDATE model_portfolio_state "
                        "SET current_cash = current_cash + :capital "
                        "WHERE portfolio_type = 'ensemble'"
                    ), {"capital": returned_capital})

                    await db.commit()
                    return {"closed": closed_count, "returned_capital": round(returned_capital, 2)}

            result = loop.run_until_complete(_unwind())
            print(f"🔄 Unwind result: {result}")
            return {"statusCode": 200, "body": result}
        except Exception as e:
            import traceback
            print(f"❌ Unwind failed: {e}")
            print(traceback.format_exc())
            return {"statusCode": 500, "error": str(e)}

    # Ensure data is loaded on cold start
    _ensure_lambda_data_loaded()

    # API Lambda skips all event payload checks — go straight to Mangum for HTTP requests.
    # Worker Lambda (or unset LAMBDA_ROLE for backward compat) processes event payloads.
    if os.environ.get("LAMBDA_ROLE") == "api":
        # Only handle health-check warmers on API Lambda
        if event.get("warmer"):
            return {
                "statusCode": 200,
                "body": '{"status": "warm", "role": "api"}'
            }
        # Fall through to Mangum for API Gateway events
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                asyncio.set_event_loop(asyncio.new_event_loop())
                _mangum_handler = None
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
            _mangum_handler = None

        if _mangum_handler is None:
            _mangum_handler = Mangum(app, lifespan="off")

        return _mangum_handler(event, context)

    # Handle warmer events - just return success to keep Lambda warm
    if event.get("warmer"):
        print(f"🔥 Warmer ping - {len(scanner_service.data_cache)} symbols in cache")
        return {
            "statusCode": 200,
            "body": f'{{"status": "warm", "symbols_loaded": {len(scanner_service.data_cache)}}}'
        }

    # Handle daily scan (EventBridge: 4 PM ET Mon-Fri)
    # Refreshes data from yfinance, persists cache to S3, exports signals + dashboard + snapshot
    if event.get("daily_scan"):
        print(f"📡 Daily scan triggered - {len(scanner_service.data_cache)} symbols in cache")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_daily_scan(lambda_context=None):
            from app.services.data_export import data_export_service
            from app.api.signals import compute_shared_dashboard_data
            from datetime import date
            import time as _time_mod

            # Pipeline log accumulator
            _steps = []
            _scan_t0 = _time_mod.time()
            _step_t0 = _scan_t0
            # Collects (step_name, exception_repr) for non-fatal pipeline failures
            # so we can send a single consolidated admin alert at the end of the scan.
            # Prior to Apr 15 2026, these failures only printed ⚠️ warnings — the
            # live portfolio silently sat in cash for 9 days behind an IndentError.
            pipeline_failures: list = []

            def _log_step(name, status, detail=""):
                nonlocal _step_t0
                now = _time_mod.time()
                _steps.append({
                    "name": name,
                    "status": status,
                    "duration_s": round(now - _step_t0, 1),
                    "detail": str(detail)[:300],
                })
                _step_t0 = now

            def _write_pipeline_log(log_status, signals_count=0, data=None, snap_result=None, entry_result=None, exit_result=None, regime_stop=None):
                """Write structured pipeline log to S3 (best-effort, non-fatal)."""
                try:
                    from zoneinfo import ZoneInfo
                    now_et = datetime.now(ZoneInfo('America/New_York'))
                    pipeline_log = {
                        "status": log_status,
                        "date": now_et.date().isoformat(),
                        "started_at": datetime.utcfromtimestamp(_scan_t0).isoformat() + "Z",
                        "completed_at": datetime.utcnow().isoformat() + "Z",
                        "duration_seconds": round(_time_mod.time() - _scan_t0, 1),
                        "market": {
                            "regime": data.get("regime_forecast", {}).get("current_regime") if data else None,
                            "spy_price": data.get("market_stats", {}).get("spy_price") if data else None,
                            "vix_level": data.get("market_stats", {}).get("vix_level") if data else None,
                            "signals": signals_count,
                        },
                        "portfolio": {
                            "live_value": snap_result.get("live", {}).get("total_value") if isinstance(snap_result, dict) else None,
                            "positions": snap_result.get("live", {}).get("num_positions") if isinstance(snap_result, dict) else None,
                            "entries": entry_result.get("entries", 0) if isinstance(entry_result, dict) else 0,
                            "exits": len(exit_result) if exit_result else 0,
                            "regime_stop_pct": regime_stop,
                        },
                        "steps": _steps,
                    }
                    import boto3 as _b3
                    import json as _pj
                    _b3.client('s3', region_name='us-east-1').put_object(
                        Bucket=os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179"),
                        Key="signals/pipeline_log.json",
                        Body=_pj.dumps(pipeline_log, default=str).encode('utf-8'),
                        ContentType='application/json',
                    )
                    print(f"📋 Pipeline log written: status={log_status}, {len(_steps)} steps, {round(_time_mod.time() - _scan_t0, 1)}s total")
                except Exception as pl_err:
                    print(f"⚠️ Pipeline log write failed (non-fatal): {pl_err}")

            # 1a. Ensure universe is loaded (may have new symbols since last pickle)
            await scanner_service.ensure_universe_loaded()

            # 1b. Log new symbols not in cache (added to universe since last pickle rebuild)
            existing_symbols = set(scanner_service.data_cache.keys())
            universe_symbols = set(scanner_service.universe)
            new_symbols = universe_symbols - existing_symbols
            if new_symbols:
                print(f"ℹ️ {len(new_symbols)} new symbols in universe not in cache (skipping — will be included on next pickle rebuild)")
            _log_step("Universe Check", "ok", f"{len(existing_symbols)} cached, {len(new_symbols)} new")

            # 1c. Incremental update for existing cached symbols (today's prices only)
            replace_days = event.get("replace_days", 0)
            force_source = event.get("force_source")  # "yfinance" or "alpaca"
            if force_source:
                from app.services.market_data_provider import market_data_provider as mdp
                mdp.force_source = force_source
                print(f"📡 Forcing data source: {force_source}")

            # 1c-pre. Pre-flight: wait for Alpaca bar settlement
            if not force_source:
                from app.services.market_data_provider import market_data_provider as mdp
                settlement = await _wait_for_alpaca_settlement(lambda_context=lambda_context)
                print(f"📡 Settlement result: {settlement}")
                if not settlement["settled"]:
                    print(f"⚠️ Alpaca not settled after {settlement['attempts']} attempts "
                          f"({settlement['elapsed_seconds']:.0f}s). Using yfinance for this scan.")
                    mdp.force_source = "yfinance"
            else:
                settlement = {"settled": "skipped", "reason": f"force_source={force_source}"}
            _log_step("Settlement Check",
                       "ok" if settlement.get("settled") in (True, "skipped") else "warning",
                       f"settled={settlement.get('settled')}, attempts={settlement.get('attempts', 0)}")

            import time as _time
            fetch_start_time = _time.time()
            print(f"📡 Incremental update for {len(existing_symbols)} cached symbols..." + (f" [replace_days={replace_days}]" if replace_days else ""))
            inc_result = await scanner_service.fetch_incremental(replace_days=replace_days)
            if force_source or (not settlement.get("settled") and settlement.get("fallback_to_yfinance")):
                mdp.force_source = None
            print(f"📡 Incremental: {inc_result}")

            _log_step("Incremental Update", "ok",
                       f"{inc_result.get('updated', 0)} updated, {inc_result.get('failed', 0)} failed, source={inc_result.get('source', '?')}")

            # 1d. Auto-retry with alternate source if >10% symbols failed
            if inc_result.get("failed", 0) > len(existing_symbols) * 0.1:
                from app.services.market_data_provider import market_data_provider
                alt = "alpaca" if market_data_provider._get_primary_source() == "yfinance" else "yfinance"
                print(f"⚠️ High failure rate ({inc_result['failed']} failed), retrying with {alt} fallback...")
                market_data_provider.force_source = alt
                retry_result = await scanner_service.fetch_incremental()
                market_data_provider.force_source = None
                print(f"📡 Retry result: {retry_result}")
                # Merge counts
                inc_result["updated"] += retry_result.get("updated", 0)
                inc_result["failed"] = retry_result.get("failed", 0)
                inc_result["source"] = f"{inc_result.get('source', 'unknown')}+{alt}_retry"
                _log_step("Auto-Retry", "warning", f"retried with {alt}: +{retry_result.get('updated', 0)} updated, {retry_result.get('failed', 0)} still failed")

            # 1e. Freshness gate: verify SPY has today's data before generating signals
            from zoneinfo import ZoneInfo
            from app.services.health_monitor_service import _last_market_day
            spy_df = scanner_service.data_cache.get('SPY')
            if spy_df is not None and len(spy_df) > 0:
                spy_last_date = spy_df.index[-1]
                if hasattr(spy_last_date, 'date'):
                    spy_last_date = spy_last_date.date()
                now_et = datetime.now(ZoneInfo('America/New_York'))
                expected_date = _last_market_day(now_et.date())
                if spy_last_date >= expected_date:
                    _log_step("SPY Freshness", "ok", f"SPY at {spy_last_date}")
                elif spy_last_date < expected_date:
                    print(f"⚠️ STALE DATA: SPY last date {spy_last_date}, expected {expected_date} — retrying with yfinance...")
                    from app.services.market_data_provider import market_data_provider
                    market_data_provider.force_source = "yfinance"
                    await scanner_service.fetch_incremental(symbols=["SPY", "^VIX"], replace_days=5)
                    market_data_provider.force_source = None
                    # Re-check
                    spy_df = scanner_service.data_cache.get('SPY')
                    if spy_df is not None and len(spy_df) > 0:
                        spy_last_date = spy_df.index[-1]
                        if hasattr(spy_last_date, 'date'):
                            spy_last_date = spy_last_date.date()
                    if spy_last_date < expected_date:
                        print(f"❌ STALE DATA ABORT: SPY still at {spy_last_date} after retry, expected {expected_date}")
                        from app.services.email_service import admin_email_service, ADMIN_EMAILS
                        from app.core.database import User
                        try:
                            async with async_session() as alert_db:
                                for email in ADMIN_EMAILS:
                                    admin_result = await alert_db.execute(
                                        select(User).where(User.email == email)
                                    )
                                    admin_user = admin_result.scalar_one_or_none()
                                    if admin_user:
                                        await admin_email_service.send_admin_alert(
                                            admin_user,
                                            "Daily scan ABORTED: SPY data stale",
                                            f"SPY last date: {spy_last_date}, expected: {expected_date}. "
                                            f"Both Alpaca and yfinance failed to return today's data. "
                                            f"Scan was aborted to prevent stale signals."
                                        )
                        except Exception as alert_err:
                            print(f"⚠️ Failed to send stale data admin alert: {alert_err}")
                        _log_step("SPY Freshness", "error", f"ABORT: SPY at {spy_last_date}, expected {expected_date}")
                        _write_pipeline_log("aborted")
                        return {"status": "aborted", "reason": f"stale_data: SPY at {spy_last_date}, expected {expected_date}"}
                    else:
                        print(f"✅ SPY freshness recovered after yfinance retry: {spy_last_date}")
                        _log_step("SPY Freshness", "ok", f"recovered via yfinance: {spy_last_date}")

            # 1f. Gap detection: find symbols with missing business days
            gapped = scanner_service.validate_data_continuity(lookback_days=30)
            if gapped:
                gapped_preview = list(gapped.keys())[:10]
                print(f"⚠️ Gap detected in {len(gapped)} symbols: {gapped_preview}")
                await scanner_service.fetch_incremental(
                    symbols=list(gapped.keys()), replace_days=45
                )
                print(f"✅ Re-fetched {len(gapped)} gapped symbols with 45-day lookback")

            # 1g. Persist fetch metadata to S3 for health monitoring
            try:
                import json as _json
                fetch_end_time = _time.time()
                from zoneinfo import ZoneInfo as _ZI
                now_et_str = datetime.now(_ZI('America/New_York')).strftime("%Y-%m-%d %H:%M:%S ET")
                # Determine which source actually delivered the data
                actual_source = inc_result.get("source", "unknown")
                used_fallback = settlement.get("fallback_to_yfinance", False) or "+retry" in str(actual_source)
                fetch_meta = {
                    "fetch_date": now_et_str,
                    "data_source": actual_source,
                    "settlement_check": settlement,
                    "used_fallback": used_fallback,
                    "fetch_start_utc": datetime.utcfromtimestamp(fetch_start_time).strftime("%Y-%m-%d %H:%M:%S"),
                    "fetch_end_utc": datetime.utcfromtimestamp(fetch_end_time).strftime("%Y-%m-%d %H:%M:%S"),
                    "fetch_duration_seconds": round(fetch_end_time - fetch_start_time, 1),
                    "symbols_updated": inc_result.get("updated", 0),
                    "symbols_failed": inc_result.get("failed", 0),
                }
                import boto3 as _boto3
                _boto3.client('s3', region_name='us-east-1').put_object(
                    Bucket=os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179"),
                    Key="signals/last_fetch_meta.json",
                    Body=_json.dumps(fetch_meta, default=str).encode('utf-8'),
                    ContentType='application/json',
                )
                print(f"📡 Fetch metadata saved: source={actual_source}, duration={fetch_meta['fetch_duration_seconds']}s, fallback={used_fallback}")
            except Exception as fm_err:
                print(f"⚠️ Failed to save fetch metadata (non-fatal): {fm_err}")
            _log_step("Fetch Metadata", "ok")

            # 2. Run scan on fresh data
            signals = await scanner_service.scan(refresh_data=False)
            print(f"📡 Scan complete: {len(signals)} signals")
            _log_step("Signal Scan", "ok", f"{len(signals)} signals from {len(scanner_service.data_cache)} symbols")

            # 2b. CANARY: indicator validity check. Catches cases where the
            # scan "succeeded" but most symbols silently have NaN indicators
            # on their latest bar (as happened in the Apr 2026 3.5-week
            # drought). Alert admin if <90% of the qualified universe has
            # valid dwap on today's bar.
            try:
                import pandas as _pd
                total_checked = 0
                valid_dwap = 0
                for _sym, _df in scanner_service.data_cache.items():
                    if _df is None or len(_df) < 200:
                        continue
                    total_checked += 1
                    _last = _df.iloc[-1]
                    _dwap = _last.get('dwap')
                    if _dwap is not None and not _pd.isna(_dwap) and _dwap > 0:
                        valid_dwap += 1
                validity_pct = (valid_dwap / total_checked * 100) if total_checked else 0
                canary_msg = f"{valid_dwap}/{total_checked} ({validity_pct:.1f}%) valid dwap on latest bar"
                if validity_pct < 90 and total_checked > 0:
                    print(f"🚨 INDICATOR CANARY FAIL: {canary_msg}")
                    _log_step("Indicator Canary", "critical", canary_msg)
                    # Fire admin alert asynchronously (don't block scan)
                    try:
                        from app.services.email_service import admin_email_service
                        await admin_email_service.send_admin_alert(
                            to_email="erik@rigacap.com",
                            subject=f"🚨 RigaCap Indicator Canary: {validity_pct:.0f}% valid",
                            message=(
                                f"Only {valid_dwap} of {total_checked} qualified symbols have "
                                f"valid DWAP on the latest bar ({validity_pct:.1f}%). "
                                f"Signals and watchlist may be silently empty. "
                                f"This is the same class of bug as the Apr 2026 drought. "
                                f"Run {{\"rebuild_indicators\": {{\"_\": 1}}}} on rigacap-prod-worker to fix."
                            ),
                        )
                    except Exception as _ae:
                        print(f"⚠️ Failed to send canary alert: {_ae}")
                else:
                    _log_step("Indicator Canary", "ok", canary_msg)
            except Exception as _ce:
                print(f"⚠️ Canary check errored: {_ce}")
                _log_step("Indicator Canary", "warning", f"canary errored: {_ce}")

            # 3. Store signals in DB + export to S3 (fast, do before time check)
            await store_signals_callback(signals)

            # 3b. Check remaining time — pickle export is slow (~3-5 min for 344 MB)
            # Defer it and dashboard export if running low on time
            remaining_ms = lambda_context.get_remaining_time_in_millis() if lambda_context else 900000
            print(f"⏱️ {remaining_ms/1000:.0f}s remaining after scan")

            if remaining_ms < 300000:  # < 5 minutes remaining
                print(f"⏰ Deferring pickle + dashboard export via async self-invoke...")

                # Export CSVs for critical symbols NOW (we have fresh data in memory)
                # This ensures charts + positions show today's data even though full export is deferred
                critical_symbols = set()
                # Today's signal symbols (SignalData dataclass objects)
                for sig in signals:
                    critical_symbols.add(sig.symbol)
                # SPY + VIX for market regime
                critical_symbols.update(['SPY', '^VIX'])
                # Open position symbols
                try:
                    async with async_session() as pos_db:
                        from sqlalchemy import text as _text
                        pos_rows = (await pos_db.execute(
                            _text("SELECT DISTINCT symbol FROM model_portfolio_positions WHERE status = 'open'")
                        )).fetchall()
                        critical_symbols.update(r[0] for r in pos_rows)
                except Exception as pe:
                    print(f"⚠️ Failed to get position symbols: {pe}")

                critical_cache = {s: scanner_service.data_cache[s] for s in critical_symbols if s in scanner_service.data_cache}
                if critical_cache:
                    csv_result = data_export_service.export_all(critical_cache)
                    print(f"📝 Exported {csv_result.get('count', 0)} critical CSVs (signals + positions)")

                import boto3, json as _json
                _lambda = boto3.client('lambda', region_name='us-east-1')
                _worker = os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker')
                # Defer pickle rebuild
                _lambda.invoke(
                    FunctionName=_worker,
                    InvocationType='Event',
                    Payload=_json.dumps({"pickle_rebuild_from_scan": True})
                )
                # Defer dashboard export
                _lambda.invoke(
                    FunctionName=_worker,
                    InvocationType='Event',
                    Payload=_json.dumps({
                        "export_dashboard_cache": True,
                        "include_snapshot": True,
                        "include_ensemble": True
                    })
                )
                _log_step("Deferred Export", "ok", "pickle + dashboard + CSV deferred to async invocations")
                _write_pipeline_log("success", signals_count=len(signals))
                return {
                    "status": "success",
                    "signals": len(signals),
                    "symbols_cached": len(scanner_service.data_cache),
                    "critical_csvs": len(critical_cache),
                    "pickle": {"deferred": True},
                    "dashboard": {"deferred": True},
                    "snapshot": {"deferred": True},
                    "ensemble_signals_persisted": "deferred",
                    "settlement_check": settlement,
                }

            # 4. Persist refreshed cache to S3 pickle (slow — only if time permits)
            export_result = data_export_service.export_pickle(scanner_service.data_cache)
            pkl_ok = export_result.get('success', True)
            pkl_status = "ok" if pkl_ok else "warning"
            pkl_detail = f"{export_result.get('count', 0)} symbols, {export_result.get('size_mb', '?')} MB"

            # 4b. SHADOW WRITE: parquet export (Parquet migration, Apr 2026).
            # Runs alongside pickle — pickle remains primary read path until
            # consumers are migrated. Any failure is logged but non-blocking.
            try:
                pq_result = data_export_service.export_parquet(scanner_service.data_cache)
                if pq_result.get('success'):
                    print(f"📦 Shadow parquet: {pq_result['count']} symbols, {pq_result['size_mb']} MB")
                else:
                    print(f"⚠️ Shadow parquet failed: {pq_result.get('message')}")
            except Exception as _e:
                print(f"⚠️ Shadow parquet error (non-blocking): {_e}")

            # 4c. PARALLEL-READ DIFF (Parquet migration Stage 3a, Apr 2026).
            # When PARQUET_PARALLEL_READ=true, compare pickle vs parquet and log
            # divergences to parquet_divergence_events. Gated behind env var so
            # it can be disabled instantly without redeploy. Wrapped in try/except
            # so it can NEVER break the daily scan — divergence logging is
            # observation only, not load-bearing. See project_parquet_stage3_plan.md.
            if os.environ.get("PARQUET_PARALLEL_READ", "").lower() in ("1", "true", "yes"):
                try:
                    diff_summary = await data_export_service.compare_pickle_to_parquet(
                        pickle_data=scanner_service.data_cache,
                    )
                    print(
                        f"🔬 Parquet diff: compared={diff_summary['compared']} "
                        f"diverged_symbols={diff_summary['diverged_symbols']} "
                        f"events={diff_summary['diverged']} "
                        f"by_type={diff_summary['by_type']}"
                    )
                except Exception as _diff_err:
                    print(f"⚠️ Parquet diff error (non-blocking): {_diff_err}")
            if not pkl_ok:
                pkl_detail = export_result.get('message', 'export failed')
                print(f"⚠️ Pickle export failed: {pkl_detail}")
            else:
                print(f"💾 Data cache persisted to S3: {export_result.get('count', 0)} symbols")
            _log_step("Pickle Export", pkl_status, pkl_detail)

            # GC after pickle export to reclaim serialization buffers
            import gc
            gc.collect()

            # 5. Export dashboard JSON + daily snapshot
            async with async_session() as db:
                data = await compute_shared_dashboard_data(db)
                dash_result = data_export_service.export_dashboard_json(data)
                # Use data_date (SPY's last bar date) or ET date — never UTC date.today()
                today_et = datetime.now(ZoneInfo('America/New_York')).date()
                today_str = data.get('data_date') or today_et.strftime("%Y-%m-%d")
                snap_result = data_export_service.export_snapshot(today_str, data)
            _log_step("Dashboard Export", "ok")

            # 5b. Persist market context to history table
            try:
                if data.get('market_context'):
                    from sqlalchemy import text as _sql_text
                    from datetime import date as _date
                    # market_context_history.date is a DATE column. asyncpg
                    # rejects bare strings here ("'str' has no attribute
                    # 'toordinal'") — convert YYYY-MM-DD to a date object.
                    ctx_date = _date.fromisoformat(today_str) if isinstance(today_str, str) else today_str
                    async with async_session() as ctx_db:
                        await ctx_db.execute(_sql_text(
                            "INSERT INTO market_context_history (date, context, regime, spy_price, vix_level, signal_count) "
                            "VALUES (:date, :context, :regime, :spy, :vix, :signals) "
                            "ON CONFLICT (date) DO UPDATE SET context = :context, regime = :regime, spy_price = :spy, vix_level = :vix, signal_count = :signals"
                        ), {
                            "date": ctx_date,
                            "context": data['market_context'],
                            "regime": data.get('regime_forecast', {}).get('current_regime', ''),
                            "spy": data.get('market_stats', {}).get('spy_price'),
                            "vix": data.get('market_stats', {}).get('vix_level'),
                            "signals": len(data.get('buy_signals', [])),
                        })
                        await ctx_db.commit()
            except Exception as ctx_err:
                print(f"⚠️ Market context history save failed (non-fatal): {ctx_err}")

            # 6. Persist ensemble signals to DB for audit trail + email consistency
            persisted = 0
            try:
                from app.services.ensemble_signal_service import ensemble_signal_service
                if data.get('buy_signals'):
                    async with async_session() as sig_db:
                        sig_result = await ensemble_signal_service.persist_signals(
                            sig_db, data['buy_signals'], today_et
                        )
                        await ensemble_signal_service.invalidate_stale_signals(
                            sig_db, today_et,
                            {s['symbol'] for s in data['buy_signals']}
                        )
                        persisted = sig_result['inserted']
                        print(f"📝 Persisted {persisted} ensemble signal(s)")
            except Exception as pe:
                print(f"⚠️ Signal persistence failed (non-fatal): {pe}")
            _log_step("Signal Persistence", "ok" if persisted > 0 or not data.get('buy_signals') else "warning",
                       f"{persisted} persisted")

            # 7a. Check model portfolio exits using closing prices (catches trailing stops
            # that triggered in the last 5 min after the final intraday check at 3:55 PM)
            exit_result = []
            try:
                from app.services.model_portfolio_service import model_portfolio_service, _get_regime_trailing_stop
                close_prices = {}
                for sym, df in scanner_service.data_cache.items():
                    if df is not None and not df.empty:
                        close_prices[sym] = float(df["close"].iloc[-1])
                regime_forecast = data.get("regime_forecast") if data else None
                regime_stop = _get_regime_trailing_stop(data)
                async with async_session() as exit_db:
                    exit_result = await model_portfolio_service.process_live_exits(
                        exit_db, close_prices, regime_forecast,
                        trailing_stop_pct=regime_stop,
                    )
                    if exit_result:
                        print(f"📈 [MODEL-LIVE] EOD exits: {len(exit_result)} closed — {[c.get('symbol') for c in exit_result]}")
                        await _notify_portfolio_change("SELL", exit_result)
            except Exception as pe:
                print(f"⚠️ Portfolio exit processing failed (non-fatal): {pe}")
                pipeline_failures.append(("Portfolio Exits", repr(pe)))
            _log_step("Portfolio Exits", "ok",
                       f"{len(exit_result) if exit_result else 0} exits, regime_stop={regime_stop if 'regime_stop' in dir() else '?'}%")

            # 7b. Auto-trigger model portfolio entries from fresh signals
            entry_result = None
            try:
                async with async_session() as mp_db:
                    entry_result = await model_portfolio_service.process_entries(mp_db, "live")
                    print(f"📈 Live portfolio entries: {entry_result}")
                    if entry_result and entry_result.get("entries", 0) > 0:
                        # Read back the newly opened positions for the notification
                        from app.core.database import ModelPosition as MPModel
                        new_pos = await mp_db.execute(
                            select(MPModel).where(
                                MPModel.portfolio_type == "live",
                                MPModel.status == "open",
                            ).order_by(MPModel.entry_date.desc()).limit(entry_result["entries"])
                        )
                        buy_trades = [
                            {"symbol": p.symbol, "entry_price": p.entry_price,
                             "shares": round(p.shares, 1), "cost_basis": round(p.cost_basis, 2)}
                            for p in new_pos.scalars().all()
                        ]
                        await _notify_portfolio_change("BUY", buy_trades)
            except Exception as pe:
                print(f"⚠️ Portfolio entry processing failed (non-fatal): {pe}")
                pipeline_failures.append(("Portfolio Entries", repr(pe)))
            _log_step("Portfolio Entries", "ok",
                       f"{entry_result.get('entries', 0) if isinstance(entry_result, dict) else 0} entries, cash={entry_result.get('remaining_cash', '?') if isinstance(entry_result, dict) else '?'}")

            # Silent-cash detector: fresh ensemble signals exist but live portfolio
            # opened zero positions AND has free slots. Flags cases like the Apr 6-15
            # IndentError where entries silently failed while signals kept firing.
            try:
                entries_opened = entry_result.get('entries', 0) if isinstance(entry_result, dict) else 0
                fresh_count = len([s for s in (data.get('buy_signals') or []) if s.get('is_fresh')])
                if fresh_count > 0 and entries_opened == 0:
                    from sqlalchemy import select as _sel, func as _fn
                    from app.core.database import ModelPosition as _MP
                    async with async_session() as _cap_db:
                        open_count = (await _cap_db.execute(
                            _sel(_fn.count(_MP.id)).where(
                                _MP.portfolio_type == "live",
                                _MP.status == "open",
                            )
                        )).scalar() or 0
                    if open_count < 6:  # MAX_POSITIONS
                        pipeline_failures.append((
                            "Silent Cash",
                            f"{fresh_count} fresh signals, 0 entries opened, "
                            f"{open_count}/6 positions held — entry pipeline may be silently broken"
                        ))
            except Exception as _cde:
                print(f"⚠️ Silent-cash detector failed (non-fatal): {_cde}")

            # 7c. Signal track record: enter ALL fresh signals + check exits (regime-aware)
            try:
                from app.services.model_portfolio_service import model_portfolio_service, _get_regime_trailing_stop
                regime_stop = _get_regime_trailing_stop(data)
                async with async_session() as st_db:
                    st_exits = await model_portfolio_service.process_signal_track_exits(
                        st_db, trailing_stop_pct=regime_stop
                    )
                    st_entries = await model_portfolio_service.process_signal_track_entries(st_db)
                    print(f"📊 [SIGNAL-TRACK] exits={len(st_exits)}, entries={st_entries} (stop={regime_stop}%)")
            except Exception as ste:
                print(f"⚠️ Signal track record processing failed (non-fatal): {ste}")
                pipeline_failures.append(("Signal Track Record", repr(ste)))
            _log_step("Signal Track Record", "ok",
                       f"exits={len(st_exits) if 'st_exits' in dir() else '?'}, entries={st_entries if 'st_entries' in dir() else '?'}")

            # 7d. Daily equity curve snapshot (for journey banner / what-if)
            try:
                async with async_session() as snap_db:
                    snap_result = await model_portfolio_service.take_daily_snapshot(snap_db)
                    print(f"📊 [SNAPSHOT] {snap_result}")
            except Exception as sne:
                print(f"⚠️ Daily snapshot failed (non-fatal): {sne}")
                pipeline_failures.append(("Daily Snapshot", repr(sne)))
            snap_detail = ""
            if isinstance(snap_result, dict) and snap_result.get("live"):
                snap_detail = f"live=${snap_result['live'].get('total_value', '?')}, {snap_result['live'].get('num_positions', '?')} positions"
            _log_step("Daily Snapshot", "ok", snap_detail)

            # 8. Regime forecast snapshot (writes to DB for weekly report)
            try:
                from app.services.regime_forecast_service import regime_forecast_service
                async with async_session() as rfs_db:
                    regime_snap = await regime_forecast_service.take_snapshot(rfs_db)
                    print(f"📊 Regime forecast snapshot: {regime_snap}")
            except Exception as rfe:
                print(f"⚠️ Regime forecast snapshot failed (non-fatal): {rfe}")

            # 8b. Regime history incremental update (for chart bands)
            try:
                from app.services.regime_forecast_service import regime_forecast_service
                async with async_session() as rh_db:
                    rh_result = await regime_forecast_service.update_regime_history(rh_db)
                    print(f"📊 Regime history update: {rh_result}")
            except Exception as rhe:
                print(f"⚠️ Regime history update failed (non-fatal): {rhe}")
            regime_name = data.get("regime_forecast", {}).get("current_regime", "?") if data else "?"
            _log_step("Regime Snapshot", "ok", f"regime={regime_name}")

            # 9. Chain daily WF cache refresh (async, separate Lambda invocation)
            try:
                import boto3, json as _json
                boto3.client('lambda', region_name='us-east-1').invoke(
                    FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                    InvocationType='Event',
                    Payload=_json.dumps({"daily_wf_cache": True})
                )
                print("📊 Chained daily WF cache refresh")
            except Exception as ce:
                print(f"⚠️ Failed to chain WF cache (non-fatal): {ce}")
            _log_step("WF Cache Chain", "ok", "async fire-and-forget")

            # 10. Chain CSV export (async, separate Lambda invocation)
            try:
                import boto3, json as _json
                boto3.client('lambda', region_name='us-east-1').invoke(
                    FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                    InvocationType='Event',
                    Payload=_json.dumps({"csv_export_from_scan": True})
                )
                print("📝 Chained CSV export")
            except Exception as ce:
                print(f"⚠️ Failed to chain CSV export: {ce}")
            _log_step("CSV Export Chain", "ok", "async fire-and-forget")

            # Write structured pipeline log to S3
            _write_pipeline_log(
                "success",
                signals_count=len(signals),
                data=data,
                snap_result=snap_result,
                entry_result=entry_result,
                exit_result=exit_result,
                regime_stop=regime_stop if 'regime_stop' in dir() else None,
            )

            # Consolidated admin alert for any non-fatal pipeline failures
            if pipeline_failures:
                try:
                    from app.services.email_service import admin_email_service, ADMIN_EMAILS
                    body_lines = [
                        f"Daily scan on {date.today().isoformat()} completed but "
                        f"{len(pipeline_failures)} pipeline step(s) failed non-fatally.",
                        "",
                        "Affected steps:",
                    ]
                    for step_name, err in pipeline_failures:
                        body_lines.append(f"  • {step_name}: {err}")
                    body_lines += [
                        "",
                        f"Scan summary: {len(signals)} signals, {persisted} ensemble persisted.",
                        "",
                        "Check CloudWatch /aws/lambda/rigacap-prod-worker for full tracebacks.",
                    ]
                    msg = "\n".join(body_lines)
                    subject = f"⚠️ Daily scan pipeline: {len(pipeline_failures)} step(s) failed"
                    for admin in ADMIN_EMAILS:
                        await admin_email_service.send_admin_alert(admin, subject, msg)
                except Exception as _ae:
                    print(f"⚠️ Failed to send pipeline-failure admin alert: {_ae}")

            return {
                "status": "success",
                "signals": len(signals),
                "symbols_cached": len(scanner_service.data_cache),
                "dashboard": dash_result,
                "snapshot": snap_result,
                "ensemble_signals_persisted": persisted,
                "portfolio_entries": entry_result,
                "settlement_check": settlement,
                "pipeline_failures": [f[0] for f in pipeline_failures] or None,
            }

        try:
            result = loop.run_until_complete(_run_daily_scan(lambda_context=context))
            print(f"📡 Daily scan result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Daily scan failed: {e}")
            traceback.print_exc()
            # Write error pipeline log to S3
            try:
                import boto3 as _b3e, json as _je, time as _te
                from zoneinfo import ZoneInfo
                _b3e.client('s3', region_name='us-east-1').put_object(
                    Bucket=os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179"),
                    Key="signals/pipeline_log.json",
                    Body=_je.dumps({
                        "status": "failed",
                        "date": datetime.now(ZoneInfo('America/New_York')).date().isoformat(),
                        "started_at": datetime.utcnow().isoformat() + "Z",
                        "completed_at": datetime.utcnow().isoformat() + "Z",
                        "duration_seconds": 0,
                        "error": str(e)[:500],
                        "market": {"regime": None, "spy_price": None, "vix_level": None, "signals": 0},
                        "portfolio": {"live_value": None, "positions": None, "entries": 0, "exits": 0, "regime_stop_pct": None},
                        "steps": [],
                    }, default=str).encode('utf-8'),
                    ContentType='application/json',
                )
            except Exception:
                pass
            return {"status": "failed", "error": str(e)}

    # Handle dashboard cache export
    if event.get("export_dashboard_cache"):
        print("📦 Dashboard cache export requested")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _export_dashboard():
            from app.api.signals import compute_shared_dashboard_data
            from app.services.data_export import data_export_service
            from datetime import date, datetime
            from zoneinfo import ZoneInfo

            async with async_session() as db:
                data = await compute_shared_dashboard_data(db)
                dash_result = data_export_service.export_dashboard_json(data)

            result = {"status": "success", **dash_result}

            # Export daily snapshot if requested (phase 2 of deferred daily scan)
            if event.get("include_snapshot"):
                today_et = datetime.now(ZoneInfo('America/New_York')).date()
                today_str = data.get('data_date') or today_et.strftime("%Y-%m-%d")
                snap_result = data_export_service.export_snapshot(today_str, data)
                result["snapshot"] = snap_result
                print(f"📸 Snapshot exported: {snap_result}")

            # Persist ensemble signals if requested (phase 2 of deferred daily scan)
            if event.get("include_ensemble"):
                try:
                    from app.services.ensemble_signal_service import ensemble_signal_service
                    today_et = datetime.now(ZoneInfo('America/New_York')).date()
                    if data.get('buy_signals'):
                        async with async_session() as sig_db:
                            sig_result = await ensemble_signal_service.persist_signals(
                                sig_db, data['buy_signals'], today_et
                            )
                            await ensemble_signal_service.invalidate_stale_signals(
                                sig_db, today_et,
                                {s['symbol'] for s in data['buy_signals']}
                            )
                            result["ensemble_signals_persisted"] = sig_result['inserted']
                            print(f"📝 Persisted {sig_result['inserted']} ensemble signal(s)")
                except Exception as pe:
                    print(f"⚠️ Signal persistence failed (non-fatal): {pe}")
                    result["ensemble_signals_error"] = str(pe)

            # Auto-trigger model portfolio entries (deferred phase 2)
            if event.get("include_ensemble"):
                try:
                    from app.services.model_portfolio_service import model_portfolio_service
                    async with async_session() as mp_db:
                        entry_result = await model_portfolio_service.process_entries(mp_db, "live")
                        result["portfolio_entries"] = entry_result
                        print(f"📈 Live portfolio entries: {entry_result}")
                        if entry_result and entry_result.get("entries", 0) > 0:
                            from app.core.database import ModelPosition as MPModel
                            new_pos = await mp_db.execute(
                                select(MPModel).where(
                                    MPModel.portfolio_type == "live",
                                    MPModel.status == "open",
                                ).order_by(MPModel.entry_date.desc()).limit(entry_result["entries"])
                            )
                            buy_trades = [
                                {"symbol": p.symbol, "entry_price": p.entry_price,
                                 "shares": round(p.shares, 1), "cost_basis": round(p.cost_basis, 2)}
                                for p in new_pos.scalars().all()
                            ]
                            await _notify_portfolio_change("BUY", buy_trades)
                except Exception as pe:
                    print(f"⚠️ Portfolio entry processing failed (non-fatal): {pe}")
                    result["portfolio_entries_error"] = str(pe)

                # Regime forecast snapshot
                try:
                    from app.services.regime_forecast_service import regime_forecast_service
                    async with async_session() as rfs_db:
                        regime_snap = await regime_forecast_service.take_snapshot(rfs_db)
                        result["regime_snapshot"] = regime_snap
                        print(f"📊 Regime forecast snapshot: {regime_snap}")
                except Exception as rfe:
                    print(f"⚠️ Regime forecast snapshot failed (non-fatal): {rfe}")

                # Regime history incremental update (for chart bands)
                try:
                    from app.services.regime_forecast_service import regime_forecast_service
                    async with async_session() as rh_db:
                        rh_result = await regime_forecast_service.update_regime_history(rh_db)
                        result["regime_history_update"] = rh_result
                        print(f"📊 Regime history update: {rh_result}")
                except Exception as rhe:
                    print(f"⚠️ Regime history update failed (non-fatal): {rhe}")

                # Chain daily WF cache refresh (async, separate Lambda invocation)
                try:
                    import boto3, json as _json
                    boto3.client('lambda', region_name='us-east-1').invoke(
                        FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                        InvocationType='Event',
                        Payload=_json.dumps({"daily_wf_cache": True})
                    )
                    print("📊 Chained daily WF cache refresh")
                except Exception as ce:
                    print(f"⚠️ Failed to chain WF cache (non-fatal): {ce}")

            return result

        try:
            result = loop.run_until_complete(_export_dashboard())
            print(f"📦 Dashboard cache export: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Dashboard cache export failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle pickle rebuild after daily scan (deferred from scan due to time constraints)
    # Fresh Lambda = fresh 900s budget. Two phases:
    #   Phase 1: incremental fetch + stream pickle to /tmp → S3 (avoids OOM from in-memory serialize)
    #   Phase 2: export individual CSVs (chained as separate invocation)
    if event.get("pickle_rebuild_from_scan"):
        print(f"🔨 Deferred pickle rebuild - {len(scanner_service.data_cache)} symbols in cache")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _deferred_pickle():
            import pickle, gzip, time as _time
            from app.services.data_export import data_export_service, S3_BUCKET

            # Skip incremental fetch — cold start loaded yesterday's pickle (7374 symbols).
            # This pickle is a warm cache for tomorrow's daily scan cold start.
            # Tomorrow's scan will do its own incremental fetch to get today's prices.
            print(f"📦 Using cold-start cache ({len(scanner_service.data_cache)} symbols, skipping incremental)")

            # Stream pickle to /tmp file to avoid OOM (pickle.dumps holds 2x in memory)
            # Use compresslevel=1 for speed (~5x faster than default 9, ~10% larger file)
            clean_cache = {s: df for s, df in scanner_service.data_cache.items() if len(df) >= 50}
            tmp_path = "/tmp/all_data.pkl.gz"
            print(f"💾 Writing {len(clean_cache)} symbols to {tmp_path}...")
            t0 = _time.time()
            with gzip.open(tmp_path, "wb", compresslevel=1) as f:
                pickle.dump(clean_cache, f, protocol=pickle.HIGHEST_PROTOCOL)
            file_size = os.path.getsize(tmp_path)
            print(f"💾 Pickle file: {file_size / 1024 / 1024:.1f} MB in {_time.time() - t0:.1f}s")

            # Upload to S3
            s3 = data_export_service._get_s3_client()
            s3.upload_file(tmp_path, S3_BUCKET, "prices/all_data.pkl.gz")
            os.remove(tmp_path)
            print(f"✅ Pickle uploaded to S3")

            # Chain CSV export as separate invocation (more time-consuming)
            try:
                import boto3, json as _json
                boto3.client('lambda', region_name='us-east-1').invoke(
                    FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                    InvocationType='Event',
                    Payload=_json.dumps({"csv_export_from_scan": True})
                )
                print("🔗 Chained CSV export")
            except Exception as ce:
                print(f"⚠️ Failed to chain CSV export: {ce}")

            return {
                "status": "success",
                "pickle_size_mb": round(file_size / 1024 / 1024, 2),
                "symbols": len(clean_cache),
            }

        try:
            result = loop.run_until_complete(_deferred_pickle())
            print(f"🔨 Deferred pickle result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Deferred pickle failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle CSV export (chained from pickle rebuild)
    if event.get("csv_export_from_scan"):
        print(f"📝 CSV export triggered - {len(scanner_service.data_cache)} symbols in cache")
        from app.services.data_export import data_export_service
        try:
            # Load pickle if cache is empty (cold start)
            if not scanner_service.data_cache:
                print("📦 Cache empty, loading pickle from S3 for CSV export...")
                loaded = data_export_service.import_all()
                scanner_service.data_cache.update(loaded)
                print(f"📦 Loaded {len(scanner_service.data_cache)} symbols from pickle")
            csv_result = data_export_service.export_all(scanner_service.data_cache)
            print(f"💾 CSVs saved: {csv_result.get('count', 0)} symbols")
            return {"status": "success", "csvs": csv_result}
        except Exception as e:
            import traceback
            print(f"❌ CSV export failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle data-only pickle update (no signals, no dashboard, no portfolio)
    if event.get("data_fill"):
        print(f"📡 Data fill triggered - {len(scanner_service.data_cache)} symbols in cache")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _data_fill():
            import pickle, gzip, time as _time
            from app.services.data_export import data_export_service, S3_BUCKET

            # 1. Load pickle if cache is empty (cold start)
            if not scanner_service.data_cache:
                print("📦 Cache empty, loading pickle from S3...")
                loaded = data_export_service.import_all()
                scanner_service.data_cache.update(loaded)
                print(f"📦 Loaded {len(scanner_service.data_cache)} symbols from pickle")

            if not scanner_service.data_cache:
                return {"status": "failed", "error": "No data in cache after load attempt"}

            # 2. Apply force_source if specified
            force_source = event.get("force_source")
            if force_source:
                from app.services.market_data_provider import market_data_provider as mdp
                mdp.force_source = force_source
                print(f"📡 Forcing data source: {force_source}")

            # 3. Incremental fetch — appends new bars to in-memory cache
            replace_days = event.get("replace_days", 0)
            print(f"📡 Running fetch_incremental (replace_days={replace_days})...")
            t0 = _time.time()
            inc_result = await scanner_service.fetch_incremental(replace_days=replace_days)
            fetch_time = _time.time() - t0
            print(f"📡 Fetch complete in {fetch_time:.1f}s: {inc_result}")

            # Reset force_source
            if force_source:
                from app.services.market_data_provider import market_data_provider as mdp
                mdp.force_source = None

            # 4. Stream pickle to /tmp → S3
            clean_cache = {s: df for s, df in scanner_service.data_cache.items() if len(df) >= 50}
            tmp_path = "/tmp/all_data.pkl.gz"
            print(f"💾 Writing {len(clean_cache)} symbols to {tmp_path}...")
            t0 = _time.time()
            with gzip.open(tmp_path, "wb", compresslevel=1) as f:
                pickle.dump(clean_cache, f, protocol=pickle.HIGHEST_PROTOCOL)
            file_size = os.path.getsize(tmp_path)
            print(f"💾 Pickle file: {file_size / 1024 / 1024:.1f} MB in {_time.time() - t0:.1f}s")

            s3 = data_export_service._get_s3_client()
            s3.upload_file(tmp_path, S3_BUCKET, "prices/all_data.pkl.gz")
            os.remove(tmp_path)
            print(f"✅ Pickle uploaded to S3")

            # 5. Chain CSV export if requested (default: true)
            if event.get("export_csvs", True):
                try:
                    import boto3, json as _json
                    boto3.client('lambda', region_name='us-east-1').invoke(
                        FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                        InvocationType='Event',
                        Payload=_json.dumps({"csv_export_from_scan": True})
                    )
                    print("🔗 Chained CSV export")
                except Exception as ce:
                    print(f"⚠️ Failed to chain CSV export: {ce}")

            return {
                "status": "success",
                "fetch_result": inc_result,
                "fetch_time_seconds": round(fetch_time, 1),
                "pickle_size_mb": round(file_size / 1024 / 1024, 2),
                "symbols": len(clean_cache),
                "export_csvs": event.get("export_csvs", True),
            }

        try:
            result = loop.run_until_complete(_data_fill())
            print(f"📡 Data fill result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Data fill failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle pickle rebuild (self-chaining catch-up queue for missing symbols)
    if event.get("pickle_rebuild"):
        print(f"🔨 Pickle rebuild triggered - {len(scanner_service.data_cache)} symbols in cache")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_pickle_rebuild():
            from app.services.data_export import data_export_service

            # 1. Ensure universe is loaded
            await scanner_service.ensure_universe_loaded()
            universe_symbols = set(scanner_service.universe)
            cached_symbols = set(scanner_service.data_cache.keys())
            missing = sorted(universe_symbols - cached_symbols)

            if not missing:
                print("✅ All universe symbols already in cache")
                return {
                    "status": "complete",
                    "fetched": 0,
                    "remaining": 0,
                    "total_cache": len(scanner_service.data_cache),
                }

            # 2. Take next chunk
            CHUNK_SIZE = 200
            chunk = missing[:CHUNK_SIZE]
            remaining_after = len(missing) - len(chunk)
            print(f"🔨 Fetching {len(chunk)} missing symbols ({remaining_after} remaining after this chunk)...")

            # 3. Fetch full 10y history for chunk
            await scanner_service.fetch_data(symbols=chunk)

            # 4. Merge with latest S3 pickle (prevent concurrent chains from clobbering progress)
            try:
                import pickle, gzip as _gzip
                import boto3 as _boto3
                _s3 = _boto3.client('s3', region_name='us-east-1')
                from app.services.data_export import S3_BUCKET as _bucket
                _resp = _s3.get_object(Bucket=_bucket, Key='prices/all_data.pkl.gz')
                s3_cache = pickle.loads(_gzip.decompress(_resp['Body'].read()))
                if len(s3_cache) > len(scanner_service.data_cache) - len(chunk):
                    # S3 has progress from another chain — merge our new symbols in
                    s3_cache.update({k: v for k, v in scanner_service.data_cache.items() if k not in s3_cache})
                    scanner_service.data_cache = s3_cache
                    print(f"🔀 Merged with S3 pickle ({len(s3_cache)} symbols)")
            except Exception as me:
                print(f"⚠️ Merge skipped (non-fatal): {me}")

            # 5. Persist progress to S3
            export_result = data_export_service.export_pickle(scanner_service.data_cache)
            print(f"💾 Pickle saved: {export_result.get('count', 0)} symbols")

            # 5. Self-chain if more remaining
            if remaining_after > 0:
                import boto3, json as _json
                print(f"🔗 Self-chaining for {remaining_after} remaining symbols...")
                boto3.client('lambda', region_name='us-east-1').invoke(
                    FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                    InvocationType='Event',  # async fire-and-forget
                    Payload=_json.dumps({"pickle_rebuild": True})
                )

            return {
                "status": "success" if remaining_after > 0 else "complete",
                "fetched": len(chunk),
                "remaining": remaining_after,
                "total_cache": len(scanner_service.data_cache),
            }

        try:
            result = loop.run_until_complete(_run_pickle_rebuild())
            print(f"🔨 Pickle rebuild result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Pickle rebuild failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle daily WF cache (chained from daily scan — refreshes simulated portfolio)
    if event.get("daily_wf_cache"):
        print(f"📊 Daily WF cache triggered - {len(scanner_service.data_cache)} symbols in cache")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_daily_wf_cache():
            from app.services.scheduler import scheduler_service
            await scheduler_service._run_daily_walk_forward()
            return {"status": "success"}

        try:
            result = loop.run_until_complete(_run_daily_wf_cache())
            print(f"📊 Daily WF cache result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Daily WF cache failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle regime forecast snapshot (writes to regime_forecast_snapshots table)
    if event.get("regime_forecast_snapshot"):
        print(f"📊 Regime forecast snapshot triggered - {len(scanner_service.data_cache)} symbols in cache")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _take_regime_snapshot():
            from app.services.regime_forecast_service import regime_forecast_service
            from app.services.data_export import data_export_service as _dex

            # Ensure SPY/VIX are in cache (cold start may have empty cache)
            if 'SPY' not in scanner_service.data_cache:
                print("📥 Loading price data from S3 for regime snapshot...")
                cached = _dex.import_all()
                if cached:
                    scanner_service.data_cache = cached
                    print(f"✅ Loaded {len(cached)} symbols")

            async with async_session() as db:
                return await regime_forecast_service.take_snapshot(db)

        try:
            result = loop.run_until_complete(_take_regime_snapshot())
            print(f"📊 Regime forecast snapshot result: {result}")
            return result
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"❌ Regime forecast snapshot failed: {e}\n{tb}")
            return {"status": "failed", "error": str(e), "traceback": tb}

    # Handle regime forecast backfill (populate historical snapshots)
    if event.get("regime_forecast_backfill"):
        params = event["regime_forecast_backfill"]
        days = params.get("days", 90)
        print(f"📊 Regime forecast backfill triggered for {days} days")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _regime_backfill():
            import json
            import pandas as pd
            from datetime import date, datetime, timedelta
            from app.services.regime_forecast_service import regime_forecast_service
            from app.services.market_regime import market_regime_service
            from app.services.data_export import data_export_service as _dex
            from app.core.database import RegimeForecastSnapshot

            # Ensure SPY/VIX are in cache
            if 'SPY' not in scanner_service.data_cache:
                print("📥 Loading price data from S3 for regime backfill...")
                cached = _dex.import_all()
                if cached:
                    scanner_service.data_cache = cached
                    print(f"✅ Loaded {len(cached)} symbols")

            spy_df = scanner_service.data_cache.get("SPY")
            if spy_df is None or spy_df.empty:
                return {"error": "SPY data not in cache"}

            vix_df = scanner_service.data_cache.get("^VIX")
            if vix_df is None:
                vix_df = scanner_service.data_cache.get("VIX")

            # Build list of trading days from SPY index
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            spy_dates = spy_df.index
            if spy_dates.tz is not None:
                start_ts = pd.Timestamp(start_date, tz=spy_dates.tz)
                end_ts = pd.Timestamp(end_date, tz=spy_dates.tz)
            else:
                start_ts = pd.Timestamp(start_date)
                end_ts = pd.Timestamp(end_date)

            trading_days = spy_dates[(spy_dates >= start_ts) & (spy_dates <= end_ts)]
            print(f"📅 Backfilling {len(trading_days)} trading days from {start_date} to {end_date}")

            success_count = 0
            error_count = 0

            async with async_session() as db:
                for ts in trading_days:
                    dt = ts.date() if hasattr(ts, 'date') else ts
                    try:
                        forecast = market_regime_service.predict_transitions(
                            spy_df, scanner_service.data_cache, vix_df,
                            as_of_date=datetime.combine(dt, datetime.min.time())
                        )
                        forecast_dict = forecast.to_dict() if hasattr(forecast, "to_dict") else {}
                        probabilities = forecast_dict.get("transition_probabilities", {})

                        # Get SPY/VIX close as of this date
                        if spy_dates.tz is not None:
                            dt_ts = pd.Timestamp(dt, tz=spy_dates.tz)
                        else:
                            dt_ts = pd.Timestamp(dt)
                        spy_on_date = spy_df[spy_df.index <= dt_ts]
                        spy_close = float(spy_on_date["close"].iloc[-1]) if len(spy_on_date) > 0 else None

                        vix_close = None
                        if vix_df is not None and not vix_df.empty:
                            vix_on_date = vix_df[vix_df.index <= dt_ts]
                            vix_close = float(vix_on_date["close"].iloc[-1]) if len(vix_on_date) > 0 else None

                        snap_dt = datetime.combine(dt, datetime.min.time())
                        existing = await db.execute(
                            select(RegimeForecastSnapshot).where(
                                RegimeForecastSnapshot.snapshot_date == snap_dt
                            )
                        )
                        snap = existing.scalar_one_or_none()

                        if snap:
                            snap.current_regime = forecast_dict.get("current_regime", "unknown")
                            snap.probabilities_json = json.dumps(probabilities)
                            snap.outlook = forecast_dict.get("outlook")
                            snap.recommended_action = forecast_dict.get("recommended_action")
                            snap.risk_change = forecast_dict.get("risk_change")
                            snap.spy_close = spy_close
                            snap.vix_close = vix_close
                        else:
                            snap = RegimeForecastSnapshot(
                                snapshot_date=snap_dt,
                                current_regime=forecast_dict.get("current_regime", "unknown"),
                                probabilities_json=json.dumps(probabilities),
                                outlook=forecast_dict.get("outlook"),
                                recommended_action=forecast_dict.get("recommended_action"),
                                risk_change=forecast_dict.get("risk_change"),
                                spy_close=spy_close,
                                vix_close=vix_close,
                            )
                            db.add(snap)

                        success_count += 1
                    except Exception as e:
                        print(f"⚠️ Failed for {dt}: {e}")
                        error_count += 1

                await db.commit()

            print(f"✅ Backfill complete: {success_count} snapshots, {error_count} errors")
            return {
                "status": "success",
                "days_requested": days,
                "trading_days": len(trading_days),
                "success": success_count,
                "errors": error_count,
            }

        try:
            result = loop.run_until_complete(_regime_backfill())
            print(f"📊 Regime backfill result: {result}")
            return result
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"❌ Regime forecast backfill failed: {e}\n{tb}")
            return {"status": "failed", "error": str(e), "traceback": tb}

    # Handle regime history backfill (populate regime_history table for chart bands)
    if event.get("backfill_regime_history"):
        print("📊 Regime history backfill triggered")
        config = event["backfill_regime_history"] if isinstance(event["backfill_regime_history"], dict) else {}
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _regime_history_backfill():
            from app.services.regime_forecast_service import regime_forecast_service
            from app.services.data_export import data_export_service as _dex
            from app.core.database import RegimeHistory
            from sqlalchemy import text

            # Option 1: fetch SPY/VIX from yfinance (lightweight, no pickle needed)
            fetch_years = config.get("fetch_years")
            # Option 2: load a specific pickle (e.g. 10yr) — needs 4096+ MB
            pickle_key = config.get("pickle_key")

            if fetch_years:
                import yfinance as yf
                import pandas as pd
                period = f"{fetch_years}y"
                print(f"📥 Fetching SPY + VIX from yfinance ({period})...")
                spy_raw = yf.download("SPY", period=period, progress=False)
                vix_raw = yf.download("^VIX", period=period, progress=False)
                # Normalize columns to lowercase (MultiIndex check FIRST)
                for df in [spy_raw, vix_raw]:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [c[0].lower() for c in df.columns]
                    else:
                        df.columns = [c.lower() for c in df.columns]
                # Replace full cache — avoids iterating 8k+ symbols for breadth calc
                scanner_service.data_cache = {"SPY": spy_raw, "^VIX": vix_raw}
                print(f"✅ SPY: {len(spy_raw)} bars, VIX: {len(vix_raw)} bars")
            elif pickle_key:
                import boto3
                import gzip
                import pickle as pkl
                bucket = os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
                print(f"📥 Loading pickle from s3://{bucket}/{pickle_key} ...")
                s3 = boto3.client("s3")
                response = s3.get_object(Bucket=bucket, Key=pickle_key)
                raw = response["Body"].read()
                data = pkl.loads(gzip.decompress(raw))
                scanner_service.data_cache = data
                print(f"✅ Loaded {len(data)} symbols from {pickle_key}")
            elif 'SPY' not in scanner_service.data_cache:
                print("📥 Loading price data from S3 for regime history backfill...")
                cached = _dex.import_all()
                if cached:
                    scanner_service.data_cache = cached
                    print(f"✅ Loaded {len(cached)} symbols")

            # Create table if not exists
            async with async_session() as db:
                await db.execute(text("""
                    CREATE TABLE IF NOT EXISTS regime_history (
                        id SERIAL PRIMARY KEY,
                        week_date TIMESTAMP NOT NULL UNIQUE,
                        regime_type VARCHAR(30) NOT NULL,
                        regime_name VARCHAR(50) NOT NULL,
                        confidence FLOAT,
                        risk_level VARCHAR(20),
                        color VARCHAR(20),
                        bg_color VARCHAR(50),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                await db.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_regime_history_week_date
                    ON regime_history (week_date)
                """))
                await db.commit()
                print("✅ regime_history table ensured")

                return await regime_forecast_service.backfill_regime_history(db)

        try:
            result = loop.run_until_complete(_regime_history_backfill())
            print(f"📊 Regime history backfill result: {result}")
            return result
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"❌ Regime history backfill failed: {e}\n{tb}")
            return {"status": "failed", "error": str(e), "traceback": tb}

    # Handle persist_signals (manual backfill or re-run)
    if event.get("persist_signals"):
        print("📝 Persist signals triggered")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _persist_signals():
            from app.services.ensemble_signal_service import ensemble_signal_service
            from app.services.data_export import data_export_service
            from datetime import date

            dashboard_data = data_export_service.read_dashboard_json()
            if not dashboard_data or not dashboard_data.get('buy_signals'):
                return {"status": "no_signals", "message": "No buy_signals in dashboard cache"}

            today = date.today()
            async with async_session() as db:
                result = await ensemble_signal_service.persist_signals(
                    db, dashboard_data['buy_signals'], today
                )
                invalidated = await ensemble_signal_service.invalidate_stale_signals(
                    db, today, {s['symbol'] for s in dashboard_data['buy_signals']}
                )
                return {
                    "status": "success",
                    "date": today.isoformat(),
                    "signals_persisted": result['inserted'],
                    "signals_invalidated": invalidated,
                    "symbols": [s['symbol'] for s in dashboard_data['buy_signals']],
                }

        try:
            result = loop.run_until_complete(_persist_signals())
            print(f"📝 Persist signals result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Persist signals failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle intraday position monitor (manual trigger for testing)
    if event.get("intraday_monitor"):
        print(f"📡 Intraday position monitor requested - {len(scanner_service.data_cache)} symbols in cache")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_intraday_monitor():
            from app.core.database import async_session as async_sess, Position as DBPosition, User as DBUser
            from app.services.email_service import email_service
            from app.services.data_export import data_export_service as des
            from app.services.scheduler import scheduler_service as sched
            from app.services.market_data_provider import market_data_provider
            from sqlalchemy import select
            from datetime import date

            # Load persisted dedup set from S3 (survives Lambda cold starts)
            def _load_alert_dedup():
                try:
                    import boto3, json, os
                    bucket = os.environ.get("PRICE_DATA_BUCKET")
                    if not bucket:
                        return set()
                    s3 = boto3.client("s3")
                    obj = s3.get_object(Bucket=bucket, Key="signals/alert_dedup.json")
                    data = json.loads(obj["Body"].read())
                    today_str = str(date.today())
                    # Only keep today's keys
                    return {k for k in data.get("keys", []) if k.endswith(today_str)}
                except Exception:
                    return set()

            def _save_alert_dedup(keys: set):
                try:
                    import boto3, json, os
                    bucket = os.environ.get("PRICE_DATA_BUCKET")
                    if not bucket:
                        return
                    s3 = boto3.client("s3")
                    s3.put_object(
                        Bucket=bucket,
                        Key="signals/alert_dedup.json",
                        Body=json.dumps({"keys": list(keys)}),
                        ContentType="application/json",
                    )
                except Exception:
                    pass

            persisted_dedup = _load_alert_dedup()
            sched._alerted_sell_positions.update(persisted_dedup)

            async with async_sess() as db:
                # Query all open user positions with user email
                result = await db.execute(
                    select(DBPosition, DBUser.email, DBUser.name)
                    .join(DBUser, DBPosition.user_id == DBUser.id)
                    .where(DBPosition.status == 'open')
                )
                rows = result.all()

                # Also include model portfolio symbols for exit checks
                from app.core.database import ModelPosition as MPModel
                mp_result = await db.execute(
                    select(MPModel.symbol).where(MPModel.status == "open", MPModel.portfolio_type == "live")
                )
                model_syms = {r[0] for r in mp_result.all()}

                if not rows and not model_syms:
                    return {"status": "success", "positions_checked": 0, "alerts_sent": 0, "model_closed": 0, "message": "No open positions"}

                # Fetch live prices via DualSourceProvider
                symbols = list({row[0].symbol for row in rows} | model_syms | {'SPY'})
                live_prices = {}
                day_highs = {}
                quote_data = await market_data_provider.fetch_quotes(symbols)
                for sym, qd in quote_data.items():
                    live_prices[sym] = qd.price
                    if qd.day_high:
                        day_highs[sym] = qd.day_high

                # Get regime forecast
                regime_forecast = None
                dashboard_data = des.read_dashboard_json()
                if dashboard_data:
                    regime_forecast = dashboard_data.get('regime_forecast')

                # Check positions
                alerts_sent = 0
                today = date.today()
                details = []

                for position, user_email, user_name in rows:
                    sym = position.symbol
                    if sym not in live_prices:
                        details.append({"symbol": sym, "status": "no_price"})
                        continue

                    live_price = live_prices[sym]

                    # Use day_high for HWM to capture peaks between 5-min checks
                    hwm_price = max(live_price, day_highs.get(sym, live_price))
                    if hwm_price > (position.highest_price or position.entry_price):
                        position.highest_price = hwm_price

                    guidance = sched._check_sell_trigger(position, live_price, regime_forecast)

                    if guidance and guidance['action'] in ('sell', 'warning'):
                        dedup_key = f"{position.id}_{guidance['action']}_{today}"
                        if dedup_key not in sched._alerted_sell_positions:
                            try:
                                await email_service.send_sell_alert(
                                    to_email=user_email,
                                    user_name=user_name or "",
                                    symbol=sym,
                                    action=guidance['action'],
                                    reason=guidance['reason'],
                                    current_price=live_price,
                                    entry_price=position.entry_price,
                                    stop_price=guidance.get('stop_price'),
                                    user_id=str(position.user_id),
                                )
                                sched._alerted_sell_positions.add(dedup_key)
                                alerts_sent += 1
                            except Exception as e:
                                print(f"Failed to send alert for {sym}: {e}")

                        details.append({
                            "symbol": sym,
                            "price": live_price,
                            "action": guidance['action'],
                            "reason": guidance['reason'],
                        })
                    else:
                        details.append({
                            "symbol": sym,
                            "price": live_price,
                            "action": "hold",
                        })

                await db.commit()

                # --- Model portfolio: check live trailing stop / regime exits ---
                model_closed = []
                try:
                    from app.services.model_portfolio_service import model_portfolio_service
                    model_closed = await model_portfolio_service.process_live_exits(
                        db, live_prices, regime_forecast, day_highs=day_highs
                    )
                    if model_closed:
                        print(f"📈 [MODEL-LIVE] Closed {len(model_closed)} position(s): {[c.get('symbol') for c in model_closed]}")
                        await _notify_portfolio_change("SELL", model_closed)
                except Exception as e:
                    print(f"⚠️ [MODEL-LIVE] Exit check failed: {e}")

                # --- Signal track record: check intraday exits ---
                try:
                    from app.services.model_portfolio_service import model_portfolio_service
                    st_closed = await model_portfolio_service.process_signal_track_exits(
                        db,
                        live_prices=live_prices, day_highs=day_highs,
                        regime_forecast=regime_forecast,
                    )
                    if st_closed:
                        print(f"📊 [SIGNAL-TRACK] Intraday closed {len(st_closed)} position(s): {[c.get('symbol') for c in st_closed]}")
                except Exception as e:
                    print(f"⚠️ [SIGNAL-TRACK] Intraday exit check failed: {e}")

                # --- Update S3 dashboard cache with live SPY/VIX prices ---
                try:
                    spy_qd = quote_data.get('SPY')
                    vix_price = None
                    try:
                        import yfinance as yf
                        vix_ticker = yf.Ticker('^VIX')
                        vix_price = round(vix_ticker.fast_info.last_price, 2)
                    except Exception:
                        pass

                    if spy_qd:
                        dash = des.read_dashboard_json()
                        if dash:
                            ms = dash.get('market_stats', {})
                            ms['spy_price'] = spy_qd.price
                            if spy_qd.change_pct is not None:
                                ms['spy_change_pct'] = spy_qd.change_pct
                            if vix_price:
                                ms['vix_level'] = vix_price
                            ms['live_updated_at'] = datetime.utcnow().isoformat()
                            dash['market_stats'] = ms
                            des.export_dashboard_json(dash)
                            print(f"📈 Live market stats updated: SPY={spy_qd.price}, VIX={vix_price}")
                except Exception as e:
                    print(f"⚠️ Live market stats update failed (non-fatal): {e}")

                # Persist dedup set to S3 so it survives Lambda cold starts
                if alerts_sent > 0:
                    _save_alert_dedup(sched._alerted_sell_positions)

                # --- VWAP Slippage Tracker: record post-publication prices ---
                slippage_recorded = 0
                try:
                    import boto3, os as _os
                    bucket = _os.environ.get("PRICE_DATA_BUCKET")
                    if bucket and dashboard_data:
                        generated_at_str = dashboard_data.get('generated_at', '')
                        if generated_at_str:
                            from dateutil import parser as dt_parser
                            pub_time = dt_parser.parse(generated_at_str).replace(tzinfo=None)
                            now = datetime.utcnow()
                            minutes_since_pub = (now - pub_time).total_seconds() / 60

                            # Only track for first 60 minutes after publication
                            if 0 < minutes_since_pub <= 60:
                                fresh_signals = [s for s in dashboard_data.get('buy_signals', []) if s.get('is_fresh')]
                                if fresh_signals:
                                    s3 = boto3.client("s3")
                                    snapshot_time = now.strftime('%H-%M-%S')
                                    pub_date = pub_time.strftime('%Y-%m-%d')

                                    snapshots = []
                                    for sig in fresh_signals:
                                        sym = sig.get('symbol', '')
                                        pub_price = sig.get('price', 0)
                                        live_price = live_prices.get(sym)
                                        if not live_price or not pub_price:
                                            continue
                                        slippage_bps = round((live_price - pub_price) / pub_price * 10000, 1)
                                        snapshots.append({
                                            'symbol': sym,
                                            'published_price': pub_price,
                                            'live_price': live_price,
                                            'slippage_bps': slippage_bps,
                                            'minutes_since_publication': round(minutes_since_pub, 1),
                                        })

                                    if snapshots:
                                        payload = {
                                            'published_at': generated_at_str,
                                            'snapshot_at': now.isoformat(),
                                            'minutes_since_publication': round(minutes_since_pub, 1),
                                            'signals': snapshots,
                                        }
                                        s3_key = f"signals/slippage/{pub_date}/{snapshot_time}.json"
                                        s3.put_object(
                                            Bucket=bucket,
                                            Key=s3_key,
                                            Body=json.dumps(payload),
                                            ContentType='application/json',
                                        )
                                        slippage_recorded = len(snapshots)
                                        avg_slip = sum(s['slippage_bps'] for s in snapshots) / len(snapshots)
                                        print(f"📊 Slippage tracker: {slippage_recorded} signals, avg {avg_slip:+.1f} bps, {minutes_since_pub:.0f} min post-pub")
                except Exception as e:
                    print(f"⚠️ Slippage tracker failed (non-fatal): {e}")

                return {
                    "status": "success",
                    "positions_checked": len(rows),
                    "symbols_priced": len(live_prices),
                    "alerts_sent": alerts_sent,
                    "model_closed": len(model_closed),
                    "slippage_tracked": slippage_recorded,
                    "regime": regime_forecast.get("recommended_action") if regime_forecast else None,
                    "details": details,
                }

        try:
            result = loop.run_until_complete(_run_intraday_monitor())
            print(f"📡 Intraday monitor: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Intraday monitor failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Query walk-forward job details (read-only)
    if event.get("wf_query"):
        config = event["wf_query"]
        job_id = config.get("job_id")

        async def _wf_query():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.get_simulation_details(db, job_id)

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_wf_query())
        return result or {"error": f"Job {job_id} not found"}

    # Handle model portfolio operations
    if event.get("model_portfolio"):
        config = event["model_portfolio"]
        action = config.get("action", "summary")
        portfolio_type = config.get("portfolio_type")  # None = both

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_model_portfolio():
            from app.services.model_portfolio_service import model_portfolio_service
            from app.core.database import async_session as mp_session

            async with mp_session() as db:
                if action == "process_entries":
                    results = {}
                    for ptype in ([portfolio_type] if portfolio_type else ["live", "walkforward"]):
                        results[ptype] = await model_portfolio_service.process_entries(db, ptype)
                    return {"action": action, "results": results}

                elif action == "process_exits":
                    results = {}
                    if not portfolio_type or portfolio_type == "walkforward":
                        results["walkforward"] = await model_portfolio_service.process_wf_exits(db)
                    if not portfolio_type or portfolio_type == "live":
                        results["live"] = {"note": "Live exits require live prices (intraday monitor)"}
                    return {"action": action, "results": results}

                elif action == "summary":
                    return await model_portfolio_service.get_portfolio_summary(db, portfolio_type)

                elif action == "reset":
                    return await model_portfolio_service.reset_portfolio(db, portfolio_type)

                elif action == "backfill":
                    as_of_date = config.get("as_of_date", "2026-02-01")
                    force = config.get("force", False)
                    return await model_portfolio_service.backfill_from_date(db, as_of_date, force)

                elif action == "backfill_signal_track":
                    as_of_date = config.get("as_of_date", "2026-02-01")
                    force = config.get("force", False)
                    return await model_portfolio_service.backfill_signal_track_record(db, as_of_date, force)

                elif action == "generate_autopsies":
                    from app.services.trade_autopsy_service import trade_autopsy_service
                    limit = config.get("limit", 20)
                    return await trade_autopsy_service.bulk_generate(db, portfolio_type, limit)

                else:
                    return {"error": f"Unknown action: {action}"}

        result = loop.run_until_complete(_run_model_portfolio())
        return result

    # Handle async walk-forward jobs (supports self-chaining via wf_state_key)
    if event.get("walk_forward_job"):
        wf_state_key = event.get("wf_state_key")
        print(f"📊 Walk-forward async job received - {len(scanner_service.data_cache)} symbols in cache, "
              f"SPY={'SPY' in scanner_service.data_cache}"
              + (f", continuation={wf_state_key}" if wf_state_key else ""))
        job_config = event["walk_forward_job"]
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_walk_forward_job(job_config, wf_state_key=wf_state_key))
        return result

    # Handle Step Functions walk-forward: init
    if event.get("wf_init"):
        print(f"📊 WF-INIT: Step Functions initialization")
        config = event["wf_init"]
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_wf_init():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.init_simulation(db, config)

        try:
            result = loop.run_until_complete(_run_wf_init())
            return result
        except Exception as e:
            import traceback
            print(f"❌ WF-INIT failed: {e}")
            print(traceback.format_exc())
            return {"error": str(e)}

    # Handle Step Functions walk-forward: single period
    if event.get("wf_period"):
        print(f"📊 WF-PERIOD: Processing period {event['wf_period'].get('period_index', '?')}")
        state = event["wf_period"]
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_wf_period():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.run_single_period(db, state)

        try:
            result = loop.run_until_complete(_run_wf_period())
            return result
        except Exception as e:
            import traceback
            print(f"❌ WF-PERIOD failed: {e}")
            print(traceback.format_exc())
            # Don't kill the whole simulation — increment period and continue
            return {
                **state,
                "period_index": state.get("period_index", 0) + 1,
                "error": str(e)
            }

    # Handle Step Functions walk-forward: finalize
    if event.get("wf_finalize"):
        print(f"📊 WF-FINALIZE: Computing final metrics")
        state = event["wf_finalize"]
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_wf_finalize():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.finalize_simulation(db, state)

        try:
            result = loop.run_until_complete(_run_wf_finalize())
            return result
        except Exception as e:
            import traceback
            print(f"❌ WF-FINALIZE failed: {e}")
            print(traceback.format_exc())
            return {"error": str(e), "simulation_id": state.get("simulation_id")}

    # Handle Step Functions walk-forward: mark failed
    if event.get("wf_fail"):
        print(f"📊 WF-FAIL: Marking simulation as failed")
        state = event["wf_fail"]
        error_msg = state.get("error", "Unknown error in Step Functions execution")
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_wf_fail():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.mark_simulation_failed(db, state, error_msg)

        try:
            result = loop.run_until_complete(_run_wf_fail())
            return result
        except Exception as e:
            print(f"❌ WF-FAIL handler itself failed: {e}")
            return {"error": str(e)}

    # Handle nightly walk-forward job (direct Lambda invocation)
    if "nightly_wf_job" in event:
        print(f"🌙 Nightly WF job received - {len(scanner_service.data_cache)} symbols in cache")
        config = event["nightly_wf_job"] or {}
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_nightly_wf():
            from datetime import timedelta
            from app.core.database import WalkForwardSimulation
            from app.services.walk_forward_service import walk_forward_service
            from sqlalchemy import select
            import json

            days_back = config.get("days_back", 90)
            strategy_id = config.get("strategy_id", 5)
            max_symbols = config.get("max_symbols", 500)

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            async with async_session() as db:
                # Append-only: never delete prior nightly cache rows. Readers
                # (signals.py, social_content_service.py) already do
                # ORDER BY simulation_date DESC LIMIT 1, so latest-cache
                # semantics are preserved without a DELETE that races with
                # the FK on walk_forward_period_results.

                job = WalkForwardSimulation(
                    simulation_date=datetime.utcnow(),
                    start_date=start_date,
                    end_date=end_date,
                    reoptimization_frequency="biweekly",
                    status="running",
                    is_nightly_missed_opps=True,
                    total_return_pct=0,
                    sharpe_ratio=0,
                    max_drawdown_pct=0,
                    num_strategy_switches=0,
                    benchmark_return_pct=0,
                )
                db.add(job)
                await db.commit()
                await db.refresh(job)
                job_id = job.id

                print(f"[NIGHTLY-WF] Starting {days_back}-day walk-forward (job {job_id})")

                result = await walk_forward_service.run_walk_forward_simulation(
                    db=db,
                    start_date=start_date,
                    end_date=end_date,
                    reoptimization_frequency="biweekly",
                    min_score_diff=10.0,
                    enable_ai_optimization=False,
                    max_symbols=max_symbols,
                    existing_job_id=job_id,
                    fixed_strategy_id=strategy_id,
                    carry_positions=True,
                )

                # Generate social content
                post_count = 0
                try:
                    from app.services.social_content_service import social_content_service
                    posts = await social_content_service.generate_from_nightly_wf(db, job_id)
                    post_count = len(posts)
                except Exception as e:
                    print(f"[NIGHTLY-WF] Social content error: {e}")

                return {
                    "status": "completed",
                    "job_id": job_id,
                    "total_return_pct": result.total_return_pct,
                    "total_trades": len(result.trades) if hasattr(result, 'trades') else 0,
                    "social_posts_generated": post_count,
                }

        try:
            result = loop.run_until_complete(_run_nightly_wf())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Nightly WF failed: {e}")
            print(traceback.format_exc())
            return {"status": "failed", "error": str(e)}

    # Handle backtest requests (direct Lambda invocation)
    if event.get("backtest_request"):
        print(f"📊 Backtest request received")
        req = event["backtest_request"]
        days = req.get("days", 252)
        strategy_type = req.get("strategy_type", "momentum")
        include_trades = req.get("include_trades", True)

        try:
            from app.services.backtester import backtester_service
            result = backtester_service.run_backtest(
                lookback_days=days,
                strategy_type=strategy_type
            )

            response = {
                "status": "success",
                "total_return_pct": result.total_return_pct,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown_pct": result.max_drawdown_pct,
                "win_rate": result.win_rate,
                "total_trades": result.total_trades,
                "total_pnl": result.total_pnl,
                "start_date": result.start_date,
                "end_date": result.end_date,
            }

            if include_trades:
                response["trades"] = [t.to_dict() for t in result.trades]

            print(f"📊 Backtest complete: {result.total_return_pct:.1f}% return, {result.total_trades} trades")
            return response

        except Exception as e:
            import traceback
            print(f"❌ Backtest failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle walk-forward history lookup (direct Lambda invocation)
    if event.get("walk_forward_history"):
        print("📊 Walk-forward history request received")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_get_walk_forward_history(event.get("limit", 10)))
            return result
        except Exception as e:
            import traceback
            print(f"❌ Walk-forward history failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle walk-forward trades lookup (direct Lambda invocation)
    if event.get("walk_forward_trades"):
        print("📊 Walk-forward trades request received")
        simulation_id = event.get("walk_forward_trades")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_get_walk_forward_trades(simulation_id))
            return result
        except Exception as e:
            import traceback
            print(f"❌ Walk-forward trades failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle volume data refresh (re-fetch recent days from primary source)
    # Supports optional "symbols" list to target specific tickers (avoids OOM on full universe)
    # and "detect_gaps" mode to scan for date gaps without re-fetching
    if event.get("refresh_volume_data"):
        config = event["refresh_volume_data"]
        replace_days = config.get("days", 5)
        target_symbols = config.get("symbols")  # Optional: list of specific tickers
        detect_only = config.get("detect_gaps", False)  # Just report gaps, don't fix
        print(f"🔄 Refreshing last {replace_days} days of volume data from primary source")
        if target_symbols:
            print(f"🎯 Targeting specific symbols: {target_symbols}")

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _refresh_volume():
            import pandas as pd
            from app.services.scanner import scanner_service
            from app.services.data_export import data_export_service

            # When targeting specific symbols, do a lightweight fresh fetch (no full pickle)
            if target_symbols and not detect_only:
                from app.services.market_data_provider import market_data_provider

                print(f"📦 Lightweight mode: fresh fetch for {len(target_symbols)} symbols...")

                # Try loading existing data from individual CSVs first
                cached_data = data_export_service.import_symbols(target_symbols)
                missing_syms = [s for s in target_symbols if s not in cached_data]

                if cached_data:
                    scanner_service.data_cache = cached_data
                    print(f"📦 Loaded {len(cached_data)} symbols from CSVs")

                # For symbols without CSVs, fetch full history directly
                if missing_syms:
                    start = (pd.Timestamp.now() - pd.Timedelta(days=800)).strftime('%Y-%m-%d')
                    print(f"📡 Fetching full history for {len(missing_syms)} symbols without CSVs: {missing_syms}")
                    bars = await market_data_provider.fetch_bars(missing_syms, start)
                    for sym, df in bars.items():
                        if df is not None and not df.empty:
                            if hasattr(df.index, 'tz') and df.index.tz is not None:
                                df.index = df.index.tz_localize(None)
                            scanner_service.data_cache[sym] = df[['open', 'high', 'low', 'close', 'volume']]
                            print(f"  ✅ {sym}: {len(df)} rows fetched")
                        else:
                            print(f"  ❌ {sym}: no data returned")

                # For symbols WITH existing CSVs, do incremental replace
                csv_syms = [s for s in target_symbols if s in cached_data]
                if csv_syms:
                    print(f"🔄 Incremental refresh for {len(csv_syms)} symbols with existing CSVs...")
                    result = await scanner_service.fetch_incremental(symbols=csv_syms, replace_days=replace_days)
                    print(f"🔄 Refresh result: {result}")

                # Save all targeted symbols as individual CSVs
                print("💾 Saving updated CSVs...")
                export = data_export_service.export_all(scanner_service.data_cache)
                print(f"💾 Export: {export}")

                return {
                    "status": "success",
                    "mode": "targeted",
                    "replace_days": replace_days,
                    "symbols": target_symbols,
                    "fresh_fetched": missing_syms,
                    "incremental_refreshed": csv_syms,
                    "total_in_cache": len(scanner_service.data_cache),
                }

            # Full mode: load entire cache for gap detection or bulk refresh
            print("📦 Loading full cached price data...")
            cached_data = data_export_service.import_all()
            if cached_data:
                scanner_service.data_cache = cached_data
            cache_size = len(scanner_service.data_cache)
            print(f"📦 Loaded {cache_size} symbols from cache")

            if cache_size == 0:
                return {"status": "error", "error": "No cached data to refresh"}

            # Detect gaps across all symbols
            gaps_found = {}
            check_days = replace_days + 5
            today = pd.Timestamp.now().normalize()
            cutoff = today - pd.Timedelta(days=check_days)
            expected_dates = set(d.date() for d in pd.bdate_range(cutoff, today))

            for sym, df in scanner_service.data_cache.items():
                if df.empty:
                    continue
                idx = df.index
                if hasattr(idx, 'tz') and idx.tz is not None:
                    idx = idx.tz_localize(None)
                actual_dates = set(d.date() for d in idx if d >= cutoff)
                last_date = idx.max()
                # Only check expected dates up to symbol's last date
                expected_for_sym = set(d for d in expected_dates if d <= last_date.date())
                missing = sorted(expected_for_sym - actual_dates)
                if len(missing) > 0:
                    gaps_found[sym] = {
                        "gap_days": len(missing),
                        "missing_dates": [str(d) for d in missing],
                        "last_date": str(last_date.date()),
                    }
                elif last_date.date() < min(expected_dates):
                    # Symbol's data ends before our check window entirely
                    gaps_found[sym] = {
                        "gap_days": len(expected_dates),
                        "last_date": str(last_date.date()),
                        "stale": True,
                    }

            print(f"🔍 Gap detection: {len(gaps_found)} symbols with gaps")
            for sym, info in sorted(gaps_found.items()):
                print(f"  ⚠️  {sym}: {info}")

            if detect_only:
                return {
                    "status": "success",
                    "mode": "detect_gaps",
                    "symbols_with_gaps": len(gaps_found),
                    "gaps": gaps_found,
                }

            # Auto-fix: refresh only symbols that have gaps
            refresh_syms = list(gaps_found.keys()) if gaps_found else []

            if not refresh_syms:
                return {"status": "success", "message": "No gaps found", "gaps": gaps_found}

            print(f"🔄 Refreshing {len(refresh_syms)} symbols with gaps...")

            # Re-fetch last N days
            result = await scanner_service.fetch_incremental(symbols=refresh_syms, replace_days=replace_days)
            print(f"🔄 Refresh result: {result}")

            # Save updated cache
            print("💾 Saving refreshed data...")
            export = data_export_service.export_consolidated(scanner_service.data_cache)
            print(f"💾 Export: {export}")

            # Also update individual CSVs for the fixed symbols
            fixed_cache = {s: scanner_service.data_cache[s] for s in refresh_syms if s in scanner_service.data_cache}
            if fixed_cache:
                csv_export = data_export_service.export_all(fixed_cache)
                print(f"💾 CSV export for fixed symbols: {csv_export}")

            return {
                "status": "success",
                "replace_days": replace_days,
                "symbols_refreshed": result.get("updated", 0),
                "source": result.get("source", "unknown"),
                "failed": result.get("failed", 0),
                "gaps_before_fix": gaps_found,
            }

        try:
            result = loop.run_until_complete(_refresh_volume())
            print(f"✅ Volume refresh complete: {result}")
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    # Handle data source comparison test (Alpaca vs yfinance)
    if event.get("compare_data_sources"):
        print("🔍 Data source comparison test")
        config = event["compare_data_sources"]
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _compare_sources():
            from app.services.market_data_provider import AlpacaProvider, YfinanceProvider
            import json

            symbols = config.get("symbols", ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "SPY", "XLK", "XLF", "META", "TSLA"])
            days_back = config.get("days_back", 5)

            start_date = (pd.Timestamp.now() - pd.Timedelta(days=days_back + 5)).strftime("%Y-%m-%d")

            alpaca = AlpacaProvider()
            yfinance = YfinanceProvider()

            print(f"📊 Comparing {len(symbols)} symbols, {days_back} days back from {start_date}")

            alpaca_bars = await alpaca.fetch_bars(symbols, start_date)
            yf_bars = await yfinance.fetch_bars(symbols, start_date)

            comparisons = []
            for sym in symbols:
                a_df = alpaca_bars.get(sym)
                y_df = yf_bars.get(sym)

                if a_df is None and y_df is None:
                    comparisons.append({"symbol": sym, "status": "both_missing"})
                    continue
                if a_df is None:
                    comparisons.append({"symbol": sym, "status": "alpaca_missing", "yfinance_rows": len(y_df)})
                    continue
                if y_df is None:
                    comparisons.append({"symbol": sym, "status": "yfinance_missing", "alpaca_rows": len(a_df)})
                    continue

                # Compare last N days where both have data
                # Normalize indices for comparison
                a_dates = set(a_df.index.normalize())
                y_dates = set(y_df.index.normalize())
                common_dates = sorted(a_dates & y_dates)[-days_back:]

                day_comparisons = []
                max_close_diff_pct = 0
                for dt in common_dates:
                    a_row = a_df.loc[a_df.index.normalize() == dt].iloc[-1]
                    y_row = y_df.loc[y_df.index.normalize() == dt].iloc[-1]

                    close_diff = abs(a_row['close'] - y_row['close'])
                    close_diff_pct = (close_diff / y_row['close'] * 100) if y_row['close'] > 0 else 0
                    vol_diff_pct = abs(a_row['volume'] - y_row['volume']) / max(y_row['volume'], 1) * 100

                    max_close_diff_pct = max(max_close_diff_pct, close_diff_pct)

                    day_comparisons.append({
                        "date": str(dt.date()),
                        "alpaca_close": round(float(a_row['close']), 4),
                        "yfinance_close": round(float(y_row['close']), 4),
                        "close_diff_pct": round(close_diff_pct, 4),
                        "alpaca_volume": int(a_row['volume']),
                        "yfinance_volume": int(y_row['volume']),
                        "volume_diff_pct": round(vol_diff_pct, 2),
                    })

                match = max_close_diff_pct < 0.1  # <0.1% diff = match
                comparisons.append({
                    "symbol": sym,
                    "status": "match" if match else "mismatch",
                    "max_close_diff_pct": round(max_close_diff_pct, 4),
                    "common_days": len(common_dates),
                    "alpaca_total_rows": len(a_df),
                    "yfinance_total_rows": len(y_df),
                    "days": day_comparisons,
                })

            matches = sum(1 for c in comparisons if c.get("status") == "match")
            mismatches = sum(1 for c in comparisons if c.get("status") == "mismatch")
            missing = sum(1 for c in comparisons if "missing" in c.get("status", ""))

            return {
                "status": "success",
                "summary": {
                    "symbols_tested": len(symbols),
                    "matches": matches,
                    "mismatches": mismatches,
                    "missing": missing,
                    "verdict": "PASS" if mismatches == 0 and missing == 0 else "REVIEW",
                },
                "comparisons": comparisons,
            }

        try:
            result = loop.run_until_complete(_compare_sources())
            print(f"🔍 Comparison result: {result['summary']}")
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    # Handle AI content generation test (direct Lambda invocation)
    if event.get("test_ai_content"):
        print("🤖 AI content generation test received")
        config = event["test_ai_content"]

        async def _test_ai_content():
            from app.services.ai_content_service import ai_content_service

            trade = config.get("trade", {
                "symbol": "NVDA",
                "entry_date": "2026-01-15",
                "exit_date": "2026-02-10",
                "entry_price": 125.50,
                "exit_price": 148.75,
                "pnl_pct": 18.5,
                "strategy": "DWAP+Momentum Ensemble",
            })
            platform = config.get("platform", "twitter")
            post_type = config.get("post_type", "trade_result")

            post = await ai_content_service.generate_post(
                trade=trade,
                post_type=post_type,
                platform=platform,
            )
            if not post:
                return {"status": "error", "error": "AI generation returned None — check ANTHROPIC_API_KEY"}

            return {
                "status": "success",
                "platform": platform,
                "post_type": post_type,
                "generated_text": post.text_content,
                "hashtags": post.hashtags,
                "char_count": len(post.text_content) if post.text_content else 0,
                "ai_model": post.ai_model,
            }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_test_ai_content())
            return result
        except Exception as e:
            import traceback
            print(f"❌ AI content test failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # HeyGen video generation
    if event.get("heygen_video"):
        config = event["heygen_video"]
        print(f"🎬 HeyGen video request: {config.get('script', '')[:80]}...")

        async def _heygen_video():
            from app.services.heygen_service import heygen_service
            action = config.get("action", "create")

            if action == "create":
                video_id = await heygen_service.create_video(
                    script=config["script"],
                    avatar_id=config.get("avatar_id"),
                    voice_id=config.get("voice_id"),
                    aspect_ratio=config.get("aspect_ratio", "9:16"),
                    resolution=config.get("resolution", "1080p"),
                    background_color=config.get("background_color", "#172554"),
                )
                return {"status": "queued" if video_id else "failed", "video_id": video_id}

            elif action == "status":
                result = await heygen_service.get_video_status(config["video_id"])
                return result or {"status": "error", "error": "Failed to get status"}

            elif action == "list_voices":
                voices = await heygen_service.list_voices()
                return {"voices": voices[:20] if voices else [], "total": len(voices) if voices else 0}

            elif action == "list_avatars":
                avatars = await heygen_service.list_avatars()
                return {"avatars": avatars[:20] if avatars else [], "total": len(avatars) if avatars else 0}

            return {"error": f"Unknown action: {action}"}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_heygen_video())
            return result
        except Exception as e:
            import traceback
            print(f"❌ HeyGen video failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Generate AI posts from real WF trades and save to DB (direct Lambda invocation)
    if event.get("generate_social_posts"):
        print("🤖 Generate social posts from signal track record trades")
        config = event["generate_social_posts"]

        async def _generate_social_posts():
            from app.core.database import ModelPosition, SocialPost
            from app.services.ai_content_service import ai_content_service
            from sqlalchemy import delete as sa_delete, or_

            # Delete draft posts by symbol list (cleanup tool)
            delete_symbols = config.get("delete_symbols")
            if delete_symbols:
                async with async_session() as db:
                    conditions = [SocialPost.text_content.ilike(f"%${s}%") | SocialPost.text_content.ilike(f"%{s} %") | SocialPost.text_content.ilike(f"%{s}:%") for s in delete_symbols]
                    result = await db.execute(
                        sa_delete(SocialPost).where(
                            SocialPost.status == "draft",
                            or_(*conditions),
                        )
                    )
                    deleted = result.rowcount
                    await db.commit()
                    return {"status": "success", "deleted": deleted, "symbols": delete_symbols}

            min_pnl = config.get("min_pnl_pct", 5.0)
            platforms = config.get("platforms", ["twitter", "instagram", "threads"])
            post_types = config.get("post_types", ["trade_result", "we_called_it"])
            max_trades = config.get("max_trades", 5)

            async with async_session() as db:
                # Query signal track record closed trades that haven't had posts generated yet
                result = await db.execute(
                    select(ModelPosition)
                    .where(
                        ModelPosition.portfolio_type == "signal_track_record",
                        ModelPosition.status == "closed",
                        ModelPosition.pnl_pct >= min_pnl,
                        ModelPosition.social_post_generated == False,
                    )
                    .order_by(ModelPosition.exit_date.desc())
                    .limit(max_trades)
                )
                positions = list(result.scalars().all())

                if not positions:
                    return {"status": "ok", "message": "No new signal track trades qualifying for social posts", "posts_created": 0}

                print(f"Found {len(positions)} qualifying signal track trades")

                # Generate posts for each trade x platform x post_type
                created = []
                for pos in positions:
                    trade_data = {
                        "symbol": pos.symbol,
                        "entry_price": pos.entry_price,
                        "exit_price": pos.exit_price,
                        "entry_date": str(pos.entry_date)[:10],
                        "exit_date": str(pos.exit_date)[:10],
                        "exit_reason": pos.exit_reason or "trailing_stop",
                        "pnl_pct": pos.pnl_pct,
                        "strategy": "DWAP+Momentum Ensemble",
                    }
                    for platform in platforms:
                        for post_type in post_types:
                            post = await ai_content_service.generate_post(
                                trade=trade_data,
                                post_type=post_type,
                                platform=platform,
                            )
                            if post:
                                db.add(post)
                                created.append({
                                    "symbol": pos.symbol,
                                    "platform": platform,
                                    "post_type": post_type,
                                    "text": post.text_content[:80] + "...",
                                    "chars": len(post.text_content),
                                })
                                print(f"  Created {platform}/{post_type} for {pos.symbol} ({len(post.text_content)} chars)")

                    # Mark position so we don't generate duplicate posts
                    pos.social_post_generated = True

                await db.commit()

                return {
                    "status": "success",
                    "trades_used": len(positions),
                    "posts_created": len(created),
                    "posts": created,
                }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_generate_social_posts())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Generate social posts failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Generate monthly recap social posts
    if event.get("monthly_recap"):
        config = event["monthly_recap"]
        print(f"📊 Generating monthly recap posts: {config}")

        async def _monthly_recap():
            from app.services.social_content_service import social_content_service
            from app.core.database import async_session

            async with async_session() as db:
                posts = await social_content_service.generate_monthly_recap(
                    db,
                    year=config.get("year"),
                    month=config.get("month"),
                )
                return {
                    "status": "ok",
                    "posts_generated": len(posts),
                    "post_ids": [p.id for p in posts],
                }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_monthly_recap())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Monthly recap failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Scan followed accounts for reply opportunities (direct Lambda invocation)
    if event.get("scan_replies"):
        print("🔍 Scanning for reply opportunities")
        config = event["scan_replies"]

        async def _scan_replies():
            from app.services.reply_scanner_service import reply_scanner_service
            from app.core.database import SocialPost as SocialPostModel
            from sqlalchemy import delete

            async with async_session() as db:
                # Optionally clear old reply drafts before regenerating
                if config.get("clear_existing"):
                    deleted = await db.execute(
                        delete(SocialPostModel).where(
                            SocialPostModel.post_type == "contextual_reply",
                            SocialPostModel.status.in_(["draft", "approved"]),
                        )
                    )
                    await db.commit()
                    print(f"🗑️ Cleared {deleted.rowcount} existing reply drafts")

                result = await reply_scanner_service.scan_and_generate(
                    db=db,
                    since_hours=config.get("since_hours", 4),
                    dry_run=config.get("dry_run", False),
                    accounts=config.get("accounts"),
                    platforms=config.get("platforms"),
                )
                return result

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_scan_replies())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Reply scan failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Scan Instagram comments for reply opportunities (direct Lambda invocation)
    if event.get("scan_instagram_comments"):
        print("💬 Scanning Instagram comments for reply opportunities")
        config = event.get("scan_instagram_comments") or {}

        async def _scan_ig_comments():
            from app.services.instagram_comment_service import instagram_comment_service

            async with async_session() as db:
                result = await instagram_comment_service.scan_and_reply(
                    db=db,
                    since_hours=config.get("since_hours", 4),
                )
                return result

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_scan_ig_comments())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Instagram comment scan failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Layer 2 data hygiene: nightly corp-actions + asset-ID integrity check.
    # Scheduled via EventBridge at 6 PM ET (between daily scan at 4:30 and
    # overnight emails). Chains: verify asset IDs → poll corp actions →
    # force-refetch on splits → parquet diagnose → admin digest.
    # {"nightly_data_hygiene": {"_": 1}} or {"symbols": [...]} for subset test
    if event.get("nightly_data_hygiene"):
        cfg = event.get("nightly_data_hygiene")
        cfg = cfg if isinstance(cfg, dict) else {}
        limit_symbols = cfg.get("symbols")  # optional subset for testing
        print("🧹 Nightly data hygiene pipeline")

        async def _hygiene():
            from app.services.symbol_metadata_service import symbol_metadata_service
            from app.services.data_export import data_export_service

            # 1. Determine which symbols to verify
            if limit_symbols:
                symbols = limit_symbols
            else:
                # Use the scanner cache as the canonical universe
                symbols = sorted(scanner_service.data_cache.keys()) if scanner_service.data_cache else []
            if not symbols:
                return {"error": "No symbols to verify"}

            # 2. Asset-ID verification
            print(f"🔍 Verifying asset IDs for {len(symbols)} symbols...")
            verify_summary = await symbol_metadata_service.verify_asset_ids(symbols)
            # Tally outcomes
            tally = {"ok": 0, "new": 0, "reused": 0, "missing_in_alpaca": 0}
            reused_symbols = []
            missing_symbols = []
            for sym, info in verify_summary.items():
                st = info.get("status", "?")
                if st in tally:
                    tally[st] += 1
                if st == "reused":
                    reused_symbols.append(sym)
                elif st == "missing_in_alpaca":
                    missing_symbols.append(sym)

            # 3. Corp-actions poll
            print("📰 Polling corp-actions...")
            corp_events = await symbol_metadata_service.poll_corp_actions(since_hours=36)
            # Find splits specifically — these need force refetch
            split_symbols = set()
            for ev in corp_events:
                if "split" in str(ev.get("event_type", "")).lower() and ev.get("symbol"):
                    split_symbols.add(ev["symbol"])

            # 4. Force refetch on detected splits (use the existing handler logic)
            refetch_result = None
            if split_symbols:
                print(f"🔧 Force-refetching {len(split_symbols)} split symbols")
                try:
                    from datetime import datetime as _dt, timedelta as _td
                    from alpaca.data.historical import StockHistoricalDataClient
                    from alpaca.data.requests import StockBarsRequest
                    from alpaca.data.timeframe import TimeFrame
                    from alpaca.data.enums import DataFeed, Adjustment
                    from app.core.config import settings as _settings
                    import pandas as _pd
                    client = StockHistoricalDataClient(
                        api_key=_settings.ALPACA_API_KEY,
                        secret_key=_settings.ALPACA_SECRET_KEY,
                    )
                    end = _dt.now()
                    start = end - _td(days=7 * 365 + 30)
                    req = StockBarsRequest(
                        symbol_or_symbols=list(split_symbols),
                        timeframe=TimeFrame.Day, start=start, end=end,
                        feed=DataFeed.SIP, adjustment=Adjustment.SPLIT,
                    )
                    bars = client.get_stock_bars(req)
                    refetched = 0
                    for sym in split_symbols:
                        rows = bars.data.get(sym, [])
                        if not rows:
                            continue
                        df = _pd.DataFrame([{
                            'open': b.open, 'high': b.high, 'low': b.low,
                            'close': b.close, 'volume': b.volume,
                            'date': b.timestamp.date(),
                        } for b in rows])
                        df['date'] = _pd.to_datetime(df['date'])
                        df = df.set_index('date').sort_index()
                        scanner_service.data_cache[sym] = df
                        refetched += 1
                    # Re-export pickle + parquet
                    if refetched > 0:
                        data_export_service.export_pickle(scanner_service.data_cache)
                        try:
                            data_export_service.export_parquet(scanner_service.data_cache)
                        except Exception as _pe:
                            print(f"⚠️ Shadow parquet after refetch failed: {_pe}")
                    refetch_result = {"split_symbols": len(split_symbols), "refetched": refetched}
                except Exception as e:
                    import traceback
                    print(f"❌ Split refetch failed: {e}")
                    refetch_result = {"error": str(e)[:300]}

            # 5. Post-actions diagnose (see what shape the universe is in)
            try:
                diag = data_export_service.diagnose_corruption()
            except Exception as e:
                diag = {"error": str(e)[:300]}

            # 6. Admin digest email
            try:
                from app.services.email_service import admin_email_service
                # Tier flags: critical ones escalate status; info items stay
                # in a separate section so "auto-fixed a split" doesn't read
                # like an emergency.
                critical_flags = []
                info_flags = []
                if tally["reused"] > 0:
                    critical_flags.append(f"🚨 {tally['reused']} ticker-reuse detected: {reused_symbols[:10]}")
                if tally["missing_in_alpaca"] > 20:
                    critical_flags.append(f"⚠️ {tally['missing_in_alpaca']} symbols missing in Alpaca (>20 threshold)")
                dirty_total = diag.get("total_dirty_symbols") if isinstance(diag, dict) else None
                if dirty_total and dirty_total > 1500:
                    critical_flags.append(f"⚠️ Universe dirty count {dirty_total} above 1500 threshold")

                if refetch_result and refetch_result.get("refetched", 0) > 0:
                    info_flags.append(f"🔧 Auto-fixed {refetch_result['refetched']} split(s) via SPLIT-adjusted refetch")
                if tally["new"] > 0:
                    info_flags.append(f"🆕 {tally['new']} new symbols added to metadata")
                if 0 < tally["missing_in_alpaca"] <= 20:
                    info_flags.append(f"ℹ️ {tally['missing_in_alpaca']} symbols missing in Alpaca (below alarm threshold)")

                status_word = "Healthy" if not critical_flags else "Attention Needed"
                emoji = "✅" if not critical_flags else "🚨"

                html_lines = [
                    f"<h2>{emoji} Data Hygiene: {status_word}</h2>",
                    "<h3>Asset-ID Verification</h3>",
                    f"<ul>",
                    f"<li>Verified: {len(symbols)}</li>",
                    f"<li>OK: {tally['ok']}</li>",
                    f"<li>New (first-seen): {tally['new']}</li>",
                    f"<li>Ticker-reuse (quarantined): {tally['reused']}</li>",
                    f"<li>Missing in Alpaca: {tally['missing_in_alpaca']}</li>",
                    f"</ul>",
                    "<h3>Corporate Actions</h3>",
                    f"<ul>",
                    f"<li>Events detected (last 36h): {len(corp_events)}</li>",
                    f"<li>Split symbols: {len(split_symbols)}</li>",
                    f"</ul>",
                ]
                if critical_flags:
                    html_lines.append("<h3>⚠️ Needs Attention</h3><ul>")
                    for f in critical_flags:
                        html_lines.append(f"<li>{f}</li>")
                    html_lines.append("</ul>")
                if info_flags:
                    html_lines.append("<h3>ℹ️ Auto-Remediated / Informational</h3><ul>")
                    for f in info_flags:
                        html_lines.append(f"<li>{f}</li>")
                    html_lines.append("</ul>")
                html = "\n".join(html_lines)

                await admin_email_service.send_admin_alert(
                    to_email="erik@rigacap.com",
                    subject=f"{emoji} RigaCap Data Hygiene ({status_word})",
                    message=html,
                )
            except Exception as _ee:
                print(f"⚠️ Admin digest failed: {_ee}")

            return {
                "status": "ok",
                "verified": len(symbols),
                "tally": tally,
                "corp_events": len(corp_events),
                "split_symbols": len(split_symbols),
                "refetch": refetch_result,
                "dirty_count": diag.get("total_dirty_symbols") if isinstance(diag, dict) else None,
                "reused_symbols": reused_symbols,
            }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(_hygiene())
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:800]}

    # DuckDB-powered diagnostic scan over the S3 parquet file.
    # {"parquet_diagnose": {"_": 1}}
    if event.get("parquet_diagnose"):
        print("🦆 Running DuckDB corruption diagnostic over parquet")
        try:
            from app.services.data_export import data_export_service
            return data_export_service.diagnose_corruption()
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:800]}

    # Arbitrary SQL against the parquet file.
    # {"parquet_query": {"sql": "SELECT ... FROM prices ..."}}
    if event.get("parquet_query"):
        cfg = event.get("parquet_query") or {}
        sql = cfg.get("sql")
        if not sql:
            return {"error": "sql required"}
        try:
            from app.services.data_export import data_export_service
            df = data_export_service.query_parquet(sql)
            # Convert to records, cap at 200 rows for safety
            records = df.head(200).to_dict(orient='records')
            # Handle non-JSON-serializable types (Timestamp, Decimal)
            for r in records:
                for k, v in list(r.items()):
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
                    elif hasattr(v, '__float__'):
                        try:
                            r[k] = float(v)
                        except Exception:
                            r[k] = str(v)
            return {"rows": records, "count": len(df), "truncated": len(df) > 200}
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:500]}

    # Test parquet shadow write — exports current cache to S3 parquet + verifies
    # round-trip read. {"test_parquet_roundtrip": {"_": 1}}
    if event.get("test_parquet_roundtrip"):
        print("🧪 Parquet round-trip test")
        try:
            from app.services.data_export import data_export_service
            cache = scanner_service.data_cache
            if not cache:
                return {"error": "No data in cache"}
            orig_symbols = set(cache.keys())
            orig_sample_sym = 'AAPL' if 'AAPL' in cache else next(iter(cache))
            orig_sample_rows = len(cache[orig_sample_sym])
            orig_sample_last_close = float(cache[orig_sample_sym]['close'].iloc[-1])

            # Export
            exp = data_export_service.export_parquet(cache)
            if not exp.get('success'):
                return {"stage": "export_failed", "result": exp}

            # Import back — full
            reimport = data_export_service.import_parquet()
            if not reimport:
                return {"stage": "import_failed", "export_result": exp}

            reimport_symbols = set(reimport.keys())
            roundtrip_sample_rows = len(reimport.get(orig_sample_sym, []))
            roundtrip_sample_last_close = float(reimport[orig_sample_sym]['close'].iloc[-1]) if orig_sample_sym in reimport else None

            # Test partial read (single symbol)
            partial = data_export_service.import_parquet(symbols=[orig_sample_sym])

            return {
                "export": exp,
                "roundtrip": {
                    "orig_symbol_count": len(orig_symbols),
                    "reimport_symbol_count": len(reimport_symbols),
                    "missing": list(orig_symbols - reimport_symbols)[:10],
                    "extra": list(reimport_symbols - orig_symbols)[:10],
                    "sample_symbol": orig_sample_sym,
                    "orig_rows": orig_sample_rows,
                    "roundtrip_rows": roundtrip_sample_rows,
                    "orig_last_close": orig_sample_last_close,
                    "roundtrip_last_close": roundtrip_sample_last_close,
                    "close_match": orig_sample_last_close == roundtrip_sample_last_close,
                },
                "partial_read": {
                    "requested": [orig_sample_sym],
                    "returned": list(partial.keys()),
                    "rows": len(partial.get(orig_sample_sym, [])),
                },
            }
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:1000]}

    # Force-refetch specific symbols with SPLIT adjustment, overwrite in pickle.
    # Used to fix known-split symbols (NVDA, CMG, WMT) that were cached with
    # unadjusted prices. {"refetch_split_adjusted": {"symbols": ["NVDA"]}}
    if event.get("refetch_split_adjusted"):
        cfg = event.get("refetch_split_adjusted") or {}
        symbols = cfg.get("symbols") or []
        if not symbols:
            return {"error": "symbols list required"}
        print(f"🔧 Refetching {len(symbols)} symbols with SPLIT adjustment")

        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            from alpaca.data.enums import DataFeed, Adjustment
            from app.services.data_export import data_export_service
            from app.core.config import settings as _settings
            import pandas as _pd
            import numpy as _np

            client = StockHistoricalDataClient(
                api_key=_settings.ALPACA_API_KEY,
                secret_key=_settings.ALPACA_SECRET_KEY,
            )
            end = datetime.now()
            start = end - timedelta(days=7 * 365 + 30)
            req = StockBarsRequest(
                symbol_or_symbols=symbols,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed=DataFeed.SIP,
                adjustment=Adjustment.SPLIT,
            )
            bars = client.get_stock_bars(req)
            results = {}
            for sym in symbols:
                if sym not in bars.data:
                    results[sym] = {"error": "no data"}
                    continue
                rows = bars.data[sym]
                df = _pd.DataFrame([{
                    'open': b.open, 'high': b.high, 'low': b.low,
                    'close': b.close, 'volume': b.volume,
                    'date': b.timestamp.date(),
                } for b in rows])
                df['date'] = _pd.to_datetime(df['date'])
                df = df.set_index('date').sort_index()
                # Verify fix: max daily abs log-return
                closes = df['close'].values
                if (closes > 0).all() and len(closes) > 1:
                    log_rets = _np.abs(_np.log(closes[1:] / closes[:-1]))
                    max_pct = (_np.exp(log_rets.max()) - 1) * 100
                else:
                    max_pct = None

                # Overwrite in cache (strip indicators so next scan recomputes)
                scanner_service.data_cache[sym] = df
                results[sym] = {
                    "bars_fetched": len(df),
                    "start": str(df.index[0].date()),
                    "end": str(df.index[-1].date()),
                    "max_daily_move_pct": round(max_pct, 2) if max_pct else None,
                    "cached": True,
                }

            # Export pickle back to S3 so next cold start has clean data
            export_result = data_export_service.export_all(scanner_service.data_cache)
            return {
                "status": "ok",
                "results": results,
                "pickle_export": export_result,
            }
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": str(e)[:500]}

    # Debug: raw Alpaca asset API probe — surfaces the exact error
    # {"alpaca_asset_probe": {"symbol": "AAPL"}}
    if event.get("alpaca_asset_probe"):
        cfg = event.get("alpaca_asset_probe") or {}
        symbol = cfg.get("symbol", "AAPL")
        paper = cfg.get("paper", False)
        try:
            from alpaca.trading.client import TradingClient
            from app.core.config import settings as _settings
            client = TradingClient(
                api_key=_settings.ALPACA_API_KEY,
                secret_key=_settings.ALPACA_SECRET_KEY,
                paper=paper,
            )
            asset = client.get_asset(symbol)
            return {
                "status": "ok",
                "symbol": symbol,
                "paper": paper,
                "asset_id": str(asset.id) if asset and asset.id else None,
                "class": str(asset.asset_class) if asset else None,
                "tradable": bool(getattr(asset, "tradable", False)),
                "name": getattr(asset, "name", None),
                "has_attributes": hasattr(asset, "attributes"),
                "attributes_type": type(getattr(asset, "attributes", None)).__name__,
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "symbol": symbol,
                "paper": paper,
                "error_type": type(e).__name__,
                "error": str(e)[:500],
                "trace": traceback.format_exc()[:800],
            }

    # Alpaca corporate actions API test — check if paid-tier access works
    # {"alpaca_corp_actions_test": {"symbols": ["NVDA", "AAPL"], "days_back": 365}}
    if event.get("alpaca_corp_actions_test"):
        cfg = event.get("alpaca_corp_actions_test") or {}
        symbols = cfg.get("symbols", ["NVDA"])
        days_back = cfg.get("days_back", 90)
        print(f"🧪 Alpaca corp-actions test: {symbols} last {days_back}d")

        try:
            from datetime import date as _date
            from alpaca.data.historical.corporate_actions import CorporateActionsClient
            from alpaca.data.requests import CorporateActionsRequest
            from app.core.config import settings as _settings

            client = CorporateActionsClient(
                api_key=_settings.ALPACA_API_KEY,
                secret_key=_settings.ALPACA_SECRET_KEY,
            )
            req = CorporateActionsRequest(
                symbols=symbols,
                start=_date.today() - timedelta(days=days_back),
                end=_date.today(),
            )
            result = client.get_corporate_actions(req)
            # Extract counts by type
            summary = {}
            if hasattr(result, 'data') and isinstance(result.data, dict):
                for action_type, actions in result.data.items():
                    summary[action_type] = len(actions) if actions else 0
            return {
                "status": "success",
                "has_access": True,
                "symbols_queried": symbols,
                "days_back": days_back,
                "action_type_counts": summary,
                "raw_keys": list(result.data.keys()) if hasattr(result, 'data') else [],
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "has_access": False,
                "error": str(e)[:500],
                "trace_hint": traceback.format_exc()[:400],
            }

    # Data-quality diagnostic — count universe rejections by reason
    # {"data_quality_diagnostic": {"_": 1}}
    if event.get("data_quality_diagnostic"):
        print("🔍 Data quality diagnostic")
        try:
            import pandas as _pd
            cache = scanner_service.data_cache
            stats = {
                "total_symbols": 0,
                "passed": 0,
                "rejected_short_history": 0,
                "rejected_zero_price_or_dwap": 0,
                "rejected_dwap_ratio_high": 0,
                "rejected_dwap_ratio_low": 0,
                "rejected_stale_volume": 0,
                "rejected_examples": [],
            }
            for sym, df in cache.items():
                stats["total_symbols"] += 1
                if df is None or len(df) < 252:
                    stats["rejected_short_history"] += 1
                    continue
                row = df.iloc[-1]
                price = float(row.get('close', 0) or 0)
                dwap = float(row.get('dwap', 0) or 0)
                vol_avg = float(row.get('vol_avg', 0) or 0)
                volume = float(row.get('volume', 0) or 0)
                if price <= 0 or dwap <= 0:
                    stats["rejected_zero_price_or_dwap"] += 1
                    continue
                ratio = price / dwap
                if ratio > 2.0:
                    stats["rejected_dwap_ratio_high"] += 1
                    if len(stats["rejected_examples"]) < 10:
                        stats["rejected_examples"].append(
                            {"symbol": sym, "reason": "dwap_too_low",
                             "price": round(price, 2), "dwap": round(dwap, 2),
                             "ratio": round(ratio, 2)}
                        )
                    continue
                if ratio < 0.5:
                    stats["rejected_dwap_ratio_low"] += 1
                    if len(stats["rejected_examples"]) < 10:
                        stats["rejected_examples"].append(
                            {"symbol": sym, "reason": "dwap_too_high",
                             "price": round(price, 2), "dwap": round(dwap, 2),
                             "ratio": round(ratio, 2)}
                        )
                    continue
                if vol_avg > 0 and volume > 0 and (volume / vol_avg) < 0.01:
                    stats["rejected_stale_volume"] += 1
                    continue
                stats["passed"] += 1
            return stats
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:1000]}

    # Replay historical scans over a date range to find fresh signals we missed
    # during the indicator-strip bug window. Returns fresh buy signals per date.
    # {"historical_fresh_signals": {"start_date": "2026-04-07", "end_date": "2026-04-13"}}
    if event.get("historical_fresh_signals"):
        cfg = event.get("historical_fresh_signals") or {}
        start_date = cfg.get("start_date")
        end_date = cfg.get("end_date")
        if not start_date or not end_date:
            return {"error": "start_date and end_date required (YYYY-MM-DD)"}
        print(f"🕰 Replaying fresh signals {start_date} → {end_date}")

        async def _replay():
            import pandas as _pd
            from app.api.signals import _compute_dashboard_live

            spy_df = scanner_service.data_cache.get('SPY')
            if spy_df is None:
                return {"error": "SPY not in cache"}

            start_ts = _pd.Timestamp(start_date)
            end_ts = _pd.Timestamp(end_date)
            if hasattr(spy_df.index, 'tz') and spy_df.index.tz is not None:
                start_ts = start_ts.tz_localize(spy_df.index.tz)
                end_ts = end_ts.tz_localize(spy_df.index.tz)
            trading_days = spy_df.loc[start_ts:end_ts].index

            by_date = {}
            async with async_session() as db:
                for ts in trading_days:
                    date_str = ts.strftime('%Y-%m-%d')
                    try:
                        data = await _compute_dashboard_live(
                            db=db, user=None, momentum_top_n=30,
                            fresh_days=5, as_of_date=date_str,
                        )
                        signals = data.get('buy_signals', [])
                        fresh = [
                            {k: s.get(k) for k in ['symbol','price','dwap','pct_above_dwap',
                                                   'ensemble_score','signal_strength_label',
                                                   'momentum_rank','is_fresh','days_since_entry']}
                            for s in signals if s.get('is_fresh')
                        ]
                        by_date[date_str] = {
                            "fresh_count": len(fresh),
                            "fresh_signals": fresh,
                        }
                    except Exception as e:
                        by_date[date_str] = {"error": str(e)[:200]}
            return {"dates": by_date}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(_replay())
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": str(e)}

    # One-time backfill: force-recompute indicators for all cached symbols
    # and re-export the pickle to S3. Use after fixing fetch_incremental
    # indicator-strip bug to repair the in-S3 pickle's NaN-tail rows.
    # {"rebuild_indicators": {"_": 1}}
    if event.get("rebuild_indicators"):
        print("🔧 Rebuild indicators across full cache")
        try:
            from app.services.data_export import data_export_service
            INDICATOR_COLS = [
                'dwap', 'ma_50', 'ma_200', 'vol_avg', 'high_52w',
                'short_mom', 'long_mom', 'volatility', 'ma_20', 'dist_from_50d_high',
            ]
            cache = scanner_service.data_cache
            recomputed = 0
            skipped = 0
            for symbol in list(cache.keys()):
                df = cache[symbol]
                if df is None or len(df) < 200:
                    skipped += 1
                    continue
                cols_to_drop = [c for c in INDICATOR_COLS if c in df.columns]
                if cols_to_drop:
                    df = df.drop(columns=cols_to_drop)
                df = scanner_service._ensure_indicators(df)
                cache[symbol] = df
                recomputed += 1
            print(f"✅ Recomputed indicators for {recomputed} symbols ({skipped} skipped)")
            # Re-export pickle so the fix persists
            export_result = data_export_service.export_all(cache)
            return {
                "status": "success",
                "recomputed": recomputed,
                "skipped": skipped,
                "pickle_export": export_result,
            }
        except Exception as e:
            import traceback
            print(f"❌ Rebuild indicators failed: {e}")
            print(traceback.format_exc())
            return {"error": str(e)}

    # Diagnostic: deep inspect a few specific symbols
    # {"symbol_inspect": {"symbols": ["AAPL", "MSFT", "NVDA"]}}
    if event.get("symbol_inspect"):
        cfg = event.get("symbol_inspect") or {}
        syms = cfg.get("symbols", ["AAPL", "MSFT", "NVDA", "EXAS", "AVGO"])
        out = {}
        try:
            cache = scanner_service.data_cache
            for s in syms:
                if s not in cache:
                    out[s] = "NOT_IN_CACHE"
                    continue
                df = cache[s]
                last5 = df.tail(5)
                cols_present = list(df.columns)
                # last row dwap details
                row = df.iloc[-1]
                out[s] = {
                    "rows": len(df),
                    "columns": cols_present,
                    "last_date": str(df.index[-1]),
                    "last_close": float(row.get('close', 0)) if row.get('close') is not None else None,
                    "last_dwap": (float(row.get('dwap')) if row.get('dwap') is not None and not __import__('pandas').isna(row.get('dwap')) else None),
                    "last_5_dwap": [
                        (None if __import__('pandas').isna(v) else float(v))
                        for v in last5.get('dwap', [None]*5).tolist()
                    ] if 'dwap' in df.columns else "NO_DWAP_COLUMN",
                }
            return out
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:1000]}

    # Diagnostic: signal pipeline distribution across the universe (admin/debug)
    # {"signal_diagnostic": {"min_volume": 500000, "min_price": 15.0}}
    if event.get("signal_diagnostic"):
        cfg = event.get("signal_diagnostic") or {}
        min_volume = cfg.get("min_volume", 500_000)
        min_price = cfg.get("min_price", 15.0)
        print(f"🔬 Signal diagnostic: min_vol={min_volume} min_price={min_price}")

        try:
            import pandas as _pd
            cache = scanner_service.data_cache
            buckets = {
                "below_dwap": 0,           # pct_above_dwap < 0
                "0_to_3_above": 0,
                "3_to_6_5_above": 0,       # current watchlist band
                "6_5_to_10_above": 0,      # past DWAP threshold but maybe failing other gates
                "over_10_above": 0,
                "no_dwap": 0,
            }
            high_buckets = {
                "within_3_pct_of_50dhi": 0,
                "3_to_5_pct_below_50dhi": 0,    # current confirmation band 5%
                "5_to_10_pct_below_50dhi": 0,
                "over_10_pct_below_50dhi": 0,
                "no_50d_data": 0,
            }
            both_pass = 0   # passes BOTH dwap AND near 50d high gates
            qualified_universe = 0   # passes price+volume universe filter
            top10_close_to_signal = []   # closest stocks not yet firing

            for symbol, df in cache.items():
                if len(df) < 200:
                    continue
                row = df.iloc[-1]
                price = float(row.get('close', 0))
                volume = float(row.get('volume', 0))
                if price < min_price or volume < min_volume:
                    continue
                qualified_universe += 1

                dwap = row.get('dwap')
                if _pd.isna(dwap) or dwap is None or dwap <= 0:
                    buckets["no_dwap"] += 1
                    pct_above_dwap = None
                else:
                    pct_above_dwap = (price / float(dwap) - 1) * 100
                    if pct_above_dwap < 0: buckets["below_dwap"] += 1
                    elif pct_above_dwap < 3: buckets["0_to_3_above"] += 1
                    elif pct_above_dwap < 6.5: buckets["3_to_6_5_above"] += 1
                    elif pct_above_dwap < 10: buckets["6_5_to_10_above"] += 1
                    else: buckets["over_10_above"] += 1

                hi52 = row.get('high_52w')
                # Compute 50-day high
                if len(df) >= 50:
                    hi50 = float(df['high'].iloc[-50:].max())
                    pct_below_hi50 = (1 - price / hi50) * 100 if hi50 > 0 else None
                else:
                    pct_below_hi50 = None

                if pct_below_hi50 is None:
                    high_buckets["no_50d_data"] += 1
                else:
                    if pct_below_hi50 < 3: high_buckets["within_3_pct_of_50dhi"] += 1
                    elif pct_below_hi50 < 5: high_buckets["3_to_5_pct_below_50dhi"] += 1
                    elif pct_below_hi50 < 10: high_buckets["5_to_10_pct_below_50dhi"] += 1
                    else: high_buckets["over_10_pct_below_50dhi"] += 1

                # Both gates pass? (DWAP > 6.5% AND within 5% of 50d high)
                if (pct_above_dwap is not None and pct_above_dwap > 6.5 and
                    pct_below_hi50 is not None and pct_below_hi50 < 5):
                    both_pass += 1

                # Score: how close to firing? lower is closer
                if pct_above_dwap is not None and pct_below_hi50 is not None:
                    dwap_gap = max(0, 6.5 - pct_above_dwap)
                    hi50_gap = max(0, pct_below_hi50 - 5)
                    total_gap = dwap_gap + hi50_gap
                    if total_gap < 5:  # within 5pts of firing on combined gates
                        top10_close_to_signal.append({
                            "symbol": symbol,
                            "price": round(price, 2),
                            "pct_above_dwap": round(pct_above_dwap, 1),
                            "pct_below_50d_high": round(pct_below_hi50, 1),
                            "gap_to_signal": round(total_gap, 1),
                        })

            top10_close_to_signal.sort(key=lambda x: x["gap_to_signal"])
            return {
                "qualified_universe_count": qualified_universe,
                "dwap_distribution": buckets,
                "high_50d_distribution": high_buckets,
                "passes_both_gates": both_pass,
                "top_20_closest_to_signal": top10_close_to_signal[:20],
            }
        except Exception as e:
            import traceback
            print(f"❌ Signal diagnostic failed: {e}")
            print(traceback.format_exc())
            return {"error": str(e)}

    # Create social post drafts directly (direct Lambda invocation)
    if event.get("create_drafts"):
        print("📝 Creating social post drafts")
        drafts_data = event["create_drafts"]

        async def _create_drafts():
            from app.core.database import SocialPost

            async with async_session() as db:
                created = []
                for p in drafts_data:
                    post = SocialPost(
                        platform=p.get("platform", "threads"),
                        text_content=p.get("text_content", ""),
                        hashtags=p.get("hashtags", ""),
                        post_type=p.get("post_type", "manual"),
                        status="draft",
                        image_s3_key=p.get("image_s3_key"),
                    )
                    db.add(post)
                    created.append({"platform": post.platform, "text": post.text_content[:60] + "..."})
                await db.commit()
                return {"status": "success", "created": len(created), "posts": created}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_create_drafts())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Create drafts failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Refresh Threads API token (direct Lambda invocation)
    if event.get("refresh_threads_token"):
        print("🔑 Refreshing Threads access token")

        async def _refresh_threads():
            from app.services.social_posting_service import social_posting_service
            return await social_posting_service.refresh_threads_token()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_refresh_threads())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Threads token refresh failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Send test emails for all templates (direct Lambda invocation)
    if event.get("test_emails"):
        print("📧 Test all email templates")
        config = event.get("test_emails") or {}

        async def _test_emails():
            from app.services.email_service import email_service, admin_email_service
            from types import SimpleNamespace

            to = config.get("to_email", "erik@rigacap.com")
            # Allow sending a subset: {"only": ["welcome", "sell_alert"]}
            only = config.get("only")
            results = {}

            # Look up user_id for footer links (accept override for mail-tester)
            test_user_id = config.get("user_id")
            if not test_user_id:
                try:
                    from app.core.database import async_session, User
                    from sqlalchemy import select
                    async with async_session() as db:
                        r = await db.execute(select(User.id).where(User.email == to))
                        row = r.scalar_one_or_none()
                        if row:
                            test_user_id = str(row)
                except Exception:
                    pass

            async def _try(name, coro):
                if only and name not in only:
                    return
                try:
                    ok = await coro
                    results[name] = "sent" if ok else "failed"
                    print(f"  {'✅' if ok else '❌'} {name}")
                except Exception as e:
                    results[name] = f"error: {e}"
                    print(f"  ❌ {name}: {e}")

            # --- Subscriber emails (EmailService) ---

            # 1. Daily Summary
            await _try("daily_summary", email_service.send_daily_summary(
                to_email=to,
                signals=[
                    {"symbol": "NVDA", "price": 156.20, "is_fresh": True, "is_strong": True,
                     "pct_above_dwap": 7.3, "momentum_rank": 2, "days_since_crossover": 0},
                    {"symbol": "PLTR", "price": 97.30, "is_fresh": True, "is_strong": False,
                     "pct_above_dwap": 5.8, "momentum_rank": 5, "days_since_crossover": 2},
                    {"symbol": "MSTR", "price": 341.50, "is_fresh": False, "is_strong": False,
                     "pct_above_dwap": 6.1, "momentum_rank": 8, "days_since_crossover": 12},
                    {"symbol": "COIN", "price": 267.80, "is_fresh": False, "is_strong": False,
                     "pct_above_dwap": 5.4, "momentum_rank": 14, "days_since_crossover": 18},
                ],
                market_regime={"regime": "weak_bull", "spy_price": 580.50, "vix_level": 16.3},
                positions=[
                    {"symbol": "AAPL", "entry_price": 228.0, "current_price": 245.50, "shares": 80},
                    {"symbol": "MSFT", "entry_price": 420.0, "current_price": 408.30, "shares": 45},
                ],
                missed_opportunities=[
                    {"symbol": "META", "would_be_pnl": 3200, "would_be_pct": 18.5, "signal_date": "2026-01-28"},
                    {"symbol": "AMZN", "would_be_pnl": 1850, "would_be_pct": 12.1, "signal_date": "2026-02-03"},
                ],
                watchlist=[
                    {"symbol": "TSLA", "price": 312.40, "pct_above_dwap": 3.8, "distance_to_trigger": 1.2},
                    {"symbol": "AMD", "price": 178.90, "pct_above_dwap": 4.1, "distance_to_trigger": 0.9},
                ],
                user_id=test_user_id,
            ))

            # 2. Welcome
            await _try("welcome", email_service.send_welcome_email(
                to_email=to, name="Erik Kinsman",
            ))

            # 3. Password Reset
            await _try("password_reset", email_service.send_password_reset_email(
                to_email=to, name="Erik Kinsman",
                reset_url="https://rigacap.com/reset-password?token=sample-test-token-abc123",
            ))

            # 4. Trial Ending
            await _try("trial_ending", email_service.send_trial_ending_email(
                to_email=to, name="Erik Kinsman",
                days_remaining=1, signals_generated=47, strong_signals_seen=12,
            ))

            # 5. Goodbye
            await _try("goodbye", email_service.send_goodbye_email(
                to_email=to, name="Erik Kinsman",
            ))

            # 6. Sell Alert
            await _try("sell_alert", email_service.send_sell_alert(
                to_email=to, user_name="Erik Kinsman",
                symbol="MSFT", action="sell",
                reason="Trailing stop triggered — 15% from high water mark",
                current_price=408.30, entry_price=420.00, stop_price=411.60,
                user_id=test_user_id,
            ))

            # 7. Double Signal Alert (breakout)
            await _try("double_signal_alert", email_service.send_double_signal_alert(
                to_email=to,
                new_signals=[
                    {"symbol": "NVDA", "price": 156.20, "pct_above_dwap": 7.3,
                     "momentum_rank": 2, "short_momentum": 12.4,
                     "dwap_crossover_date": "2026-02-17", "days_since_crossover": 0},
                    {"symbol": "PLTR", "price": 97.30, "pct_above_dwap": 5.8,
                     "momentum_rank": 5, "short_momentum": 9.1,
                     "dwap_crossover_date": "2026-02-15", "days_since_crossover": 2},
                ],
                approaching=[
                    {"symbol": "TSLA", "price": 312.40, "pct_above_dwap": 3.8, "distance_to_trigger": 1.2},
                    {"symbol": "AMD", "price": 178.90, "pct_above_dwap": 4.1, "distance_to_trigger": 0.9},
                ],
                market_regime={"regime": "weak_bull", "spy_price": 580.50},
                user_id=test_user_id,
            ))

            # 8. Intraday Signal Alert
            await _try("intraday_signal", email_service.send_intraday_signal_alert(
                to_email=to, user_name="Erik Kinsman",
                symbol="NVDA", live_price=156.20, dwap=145.50,
                pct_above_dwap=7.3, momentum_rank=2, sector="Technology",
                user_id=test_user_id,
            ))

            # --- Admin emails (AdminEmailService) ---

            # 9. Ticker Alert
            await _try("ticker_alert", admin_email_service.send_ticker_alert(
                to_email=to,
                issues=[
                    {"symbol": "TWTR", "issue": "Delisted — ticker changed to X",
                     "last_price": 53.70, "last_date": "2023-10-27",
                     "suggestion": "Remove TWTR, add X to universe"},
                    {"symbol": "SIVB", "issue": "No price data since March 2023",
                     "last_price": 106.04, "last_date": "2023-03-10"},
                ],
                check_type="universe",
            ))

            # 10. Strategy Analysis
            await _try("strategy_analysis", admin_email_service.send_strategy_analysis_email(
                to_email=to,
                analysis_results={
                    "evaluations": [
                        {"name": "DWAP+Momentum Ensemble", "recommendation_score": 87.2,
                         "sharpe_ratio": 1.48, "total_return_pct": 289.0},
                        {"name": "Concentrated Momentum", "recommendation_score": 72.1,
                         "sharpe_ratio": 1.15, "total_return_pct": 195.0},
                        {"name": "DWAP Classic", "recommendation_score": 45.8,
                         "sharpe_ratio": 0.19, "total_return_pct": 42.0},
                    ],
                    "analysis_date": datetime.now().isoformat(),
                    "lookback_days": 90,
                },
                recommendation="Ensemble continues to outperform. No switch recommended. "
                    "Sharpe ratio 1.48 is well above the 0.8 threshold.",
                switch_executed=False,
                switch_reason="Current strategy is top-ranked; no switch needed.",
            ))

            # 11. Strategy Switch
            await _try("switch_notification", admin_email_service.send_switch_notification_email(
                to_email=to,
                from_strategy="Concentrated Momentum",
                to_strategy="DWAP+Momentum Ensemble",
                reason="Ensemble outperformed by +15.1 points in 90-day backtest",
                metrics={"score_before": 72.1, "score_after": 87.2, "score_diff": 15.1},
            ))

            # 12. AI Generation Complete
            await _try("ai_generation_complete", admin_email_service.send_generation_complete_email(
                to_email=to,
                best_params={
                    "trailing_stop": "12%", "max_positions": 6,
                    "rebalance_freq": "biweekly", "dwap_threshold": "5%",
                    "momentum_window_short": "10d", "momentum_window_long": "60d",
                },
                expected_metrics={"sharpe": 1.48, "return": 31.0, "drawdown": -15.1},
                market_regime="weak_bull",
                created_strategy_name="AI-Optimized Ensemble v3",
            ))

            # 13. Social Post Notification (Twitter T-24h)
            twitter_post = SimpleNamespace(
                id=999, platform="twitter",
                text_content="NVDA called at $127.40 on Jan 15. Exited at $156.20 three weeks later.\n\n+22.6% while the market was flat.\n\nThe ensemble saw what pure momentum missed: DWAP breakout + top-5 ranking + volume surge.\n\nNot luck. Pattern recognition.",
                scheduled_for=datetime.utcnow() + timedelta(hours=24),
                post_type="we_called_it", ai_generated=True,
                ai_model="claude-sonnet-4-5-20250929",
                hashtags="#NVDA #TradingSignals #Momentum #RigaCap",
                image_s3_key=None,
            )
            await _try("post_notification_twitter", admin_email_service.send_post_approval_notification(
                to_email=to, post=twitter_post, hours_before=24,
                cancel_url="https://api.rigacap.com/api/admin/social/posts/999/cancel-email?token=test-preview",
            ))

            # 14. Social Post Notification (Instagram T-1h with chart)
            insta_post = SimpleNamespace(
                id=998, platform="instagram",
                text_content="We flagged PLTR at $78.50 when the ensemble fired all 3 signals.\n\nDWAP crossover confirmed. Momentum rank #2. Volume 1.6x average.\n\nThree weeks later: $97.30. That's +23.9%.",
                scheduled_for=datetime.utcnow() + timedelta(hours=1),
                post_type="trade_result", ai_generated=True,
                ai_model="claude-sonnet-4-5-20250929",
                hashtags="#PLTR #AlgoTrading #Ensemble #RigaCap #WalkForward",
                image_s3_key="social/images/75_SLV_20260116.png",
            )
            await _try("post_notification_instagram", admin_email_service.send_post_approval_notification(
                to_email=to, post=insta_post, hours_before=1,
                cancel_url="https://api.rigacap.com/api/admin/social/posts/998/cancel-email?token=test-preview",
            ))

            # 15-19. Onboarding drip emails (steps 1-5)
            for step in range(1, 6):
                await _try(f"onboarding_{step}", email_service.send_onboarding_email(
                    step=step, to_email=to, name="Erik Kinsman",
                    user_id=test_user_id,
                ))

            # 20. Referral Reward
            await _try("referral_reward", email_service.send_referral_reward_email(
                to_email=to, name="Erik Kinsman", friend_name="Jane Doe",
            ))

            sent_count = sum(1 for v in results.values() if v == "sent")
            return {"status": "success", "sent": sent_count, "total": len(results), "results": results, "to": to}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_test_emails())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Test emails failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle bulk chart card regeneration (direct Lambda invocation)
    if event.get("regenerate_charts"):
        print("🎨 Regenerate chart cards request received")

        async def _regenerate_charts():
            from sqlalchemy import select
            from app.core.database import async_session, SocialPost
            from app.services.chart_card_generator import chart_card_generator
            from app.services.scanner import scanner_service
            import json

            # Load price data so charts have real price lines
            if not scanner_service.data_cache:
                print("📊 Loading price data for chart rendering...")
                await scanner_service.fetch_data(period="1y")
                print(f"📊 Loaded {len(scanner_service.data_cache)} symbols")

            async with async_session() as db:
                result = await db.execute(
                    select(SocialPost).where(
                        SocialPost.platform == "instagram",
                        SocialPost.image_metadata_json.isnot(None),
                    )
                )
                posts = result.scalars().all()

                regenerated = 0
                errors = []
                for post in posts:
                    try:
                        meta = json.loads(post.image_metadata_json)
                        png_bytes = chart_card_generator.generate_trade_card(
                            symbol=meta.get("symbol", "???"),
                            entry_price=meta.get("entry_price", 0),
                            exit_price=meta.get("exit_price", 0),
                            entry_date=meta.get("entry_date", ""),
                            exit_date=meta.get("exit_date", ""),
                            pnl_pct=meta.get("pnl_pct", 0),
                            pnl_dollars=meta.get("pnl_dollars", 0),
                            exit_reason=meta.get("exit_reason", "trailing_stop"),
                            strategy_name=meta.get("strategy_name", "Ensemble"),
                            regime_name=meta.get("regime_name", ""),
                            company_name=meta.get("company_name", ""),
                        )
                        date_str = meta.get("exit_date", "")[:10].replace("-", "")
                        s3_key = chart_card_generator.upload_to_s3(
                            png_bytes, post.id, meta.get("symbol", "UNK"), date_str
                        )
                        if s3_key:
                            post.image_s3_key = s3_key
                            regenerated += 1
                            print(f"  ✅ Post {post.id} ({meta.get('symbol')}): {s3_key}")
                        else:
                            errors.append(f"Post {post.id}: S3 upload failed")
                    except Exception as e:
                        errors.append(f"Post {post.id}: {str(e)}")
                        print(f"  ❌ Post {post.id}: {e}")

                await db.commit()

            return {
                "status": "success",
                "total_posts": len(posts),
                "regenerated": regenerated,
                "errors": errors,
            }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_regenerate_charts())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Regenerate charts failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle track record chart generation (direct Lambda invocation)
    if event.get("generate_track_record_chart"):
        print("📈 Generate track record chart request received")

        async def _generate_track_record_chart():
            from sqlalchemy import select
            from app.core.database import async_session, WalkForwardSimulation
            from app.core.config import settings
            from app.services.chart_card_generator import chart_card_generator
            from app.services.regime_forecast_service import regime_forecast_service
            import json

            sim_ids = settings.TRACK_RECORD_SIM_IDS

            async with async_session() as db:
                result = await db.execute(
                    select(WalkForwardSimulation).where(
                        WalkForwardSimulation.id.in_(sim_ids)
                    )
                )
                sims = result.scalars().all()
                sims_by_id = {s.id: s for s in sims}
                ordered_sims = [sims_by_id[sid] for sid in sim_ids if sid in sims_by_id]

                # Stitch equity curves (same logic as API endpoint)
                stitched = []
                scale_factor = 1.0
                spy_scale_factor = 1.0

                for i, sim in enumerate(ordered_sims):
                    if not sim.equity_curve_json:
                        continue
                    curve = json.loads(sim.equity_curve_json)
                    if not curve:
                        continue

                    if i == 0:
                        for point in curve:
                            stitched.append({
                                "date": point["date"],
                                "equity": point["equity"],
                                "spy_equity": point.get("spy_equity", 100000),
                            })
                        if stitched:
                            scale_factor = stitched[-1]["equity"] / 100000
                            spy_scale_factor = stitched[-1]["spy_equity"] / 100000
                    else:
                        first_equity = curve[0]["equity"]
                        first_spy = curve[0].get("spy_equity", 100000)
                        year_eq_scale = (scale_factor * 100000) / first_equity if first_equity else 1
                        year_spy_scale = (spy_scale_factor * 100000) / first_spy if first_spy else 1
                        for point in curve[1:]:
                            stitched.append({
                                "date": point["date"],
                                "equity": point["equity"] * year_eq_scale,
                                "spy_equity": point.get("spy_equity", 100000) * year_spy_scale,
                            })
                        if stitched:
                            scale_factor = stitched[-1]["equity"] / 100000
                            spy_scale_factor = stitched[-1]["spy_equity"] / 100000

                # Get regime periods
                regime_data = await regime_forecast_service.get_regime_periods_from_db(
                    db, start_date="2021-02-01", end_date="2026-02-01"
                )
                regime_periods = regime_data.get("periods", []) if regime_data else []

            # Compute returns
            total_ret = (stitched[-1]["equity"] / stitched[0]["equity"] - 1) * 100 if stitched else 289
            bench_ret = (stitched[-1]["spy_equity"] / stitched[0]["spy_equity"] - 1) * 100 if stitched else 95

            # Generate chart (SVG vector)
            svg_bytes = chart_card_generator.generate_track_record_chart(
                equity_curve=stitched,
                regime_periods=regime_periods,
                total_return_pct=total_ret,
                benchmark_return_pct=bench_ret,
            )

            # Upload to S3
            s3_key = chart_card_generator.upload_track_record_chart(svg_bytes)
            presigned_url = chart_card_generator.get_presigned_url(s3_key, expires_in=86400)

            return {
                "status": "success",
                "s3_key": s3_key,
                "presigned_url": presigned_url,
                "equity_points": len(stitched),
                "regime_periods": len(regime_periods),
                "total_return_pct": round(total_ret, 1),
                "svg_size_bytes": len(svg_bytes),
            }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_generate_track_record_chart())
            print(f"📈 Track record chart: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Track record chart generation failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle daily email digest (EventBridge: 6 PM ET Mon-Fri)
    # Generate newsletter draft (Saturday evening cron or manual trigger)
    # {"generate_newsletter": true}
    if event.get("save_wf_from_s3"):
        cfg = event["save_wf_from_s3"]
        import boto3 as _b3
        _s3 = _b3.client("s3", region_name="us-east-1")
        _bucket = "rigacap-prod-price-data-149218244179"
        ec_json = _s3.get_object(Bucket=_bucket, Key=cfg["equity_curve_key"])["Body"].read().decode()
        trades_json = _s3.get_object(Bucket=_bucket, Key=cfg["trades_key"])["Body"].read().decode()
        switches_json = _s3.get_object(Bucket=_bucket, Key=cfg["switches_key"])["Body"].read().decode()

        async def _save_wf():
            from app.core.database import async_session, WalkForwardSimulation
            from datetime import datetime as _dt
            sim = WalkForwardSimulation(
                start_date=_dt.strptime(cfg["start_date"], "%Y-%m-%d"),
                end_date=_dt.strptime(cfg["end_date"], "%Y-%m-%d"),
                reoptimization_frequency="biweekly",
                status="completed",
                total_return_pct=cfg["total_return_pct"],
                sharpe_ratio=cfg["sharpe_ratio"],
                max_drawdown_pct=cfg["max_drawdown_pct"],
                benchmark_return_pct=cfg["benchmark_return_pct"],
                num_strategy_switches=cfg.get("num_strategy_switches", 0),
                equity_curve_json=ec_json,
                trades_json=trades_json,
                switch_history_json=switches_json,
                simulation_date=_dt.utcnow(),
                is_daily_cache=False,
            )
            async with async_session() as db:
                db.add(sim)
                await db.commit()
                await db.refresh(sim)
                return {"id": sim.id, "return": sim.total_return_pct}

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_save_wf())
        return {"status": "ok", "simulation": result}

    if event.get("generate_newsletter"):
        from app.services.newsletter_generator_service import newsletter_generator
        draft = newsletter_generator.generate_draft()
        return {
            "message": f"Newsletter draft generated: {draft['word_count']} words",
            "date": draft["date"],
            "status": draft["status"],
        }

    # Optional: {"daily_emails": {"target_emails": ["user@example.com"]}}
    # Weekly "Market, Measured." free-list email — Sunday evening.
    # {"market_measured": {"target_emails": ["erik@rigacap.com"]}} for testing,
    # or {"market_measured": {"_": 1}} for full free-list blast (future).
    # Optional: {"show_symbols": true} to show live watchlist/signal tickers
    # (for paid subscribers). Default False hides them and shows delayed-
    # reveal track record instead.
    if event.get("market_measured"):
        cfg = event.get("market_measured") or {}
        target_emails = cfg.get("target_emails") if isinstance(cfg, dict) else None
        show_symbols = cfg.get("show_symbols", False) if isinstance(cfg, dict) else False
        print(f"📨 Market, Measured triggered" + (f" for {target_emails}" if target_emails else " (full list)"))

        # Newsletter ONLY sends from a locked draft — never auto-generates
        try:
            from app.services.newsletter_generator_service import newsletter_generator
            from datetime import datetime as _dt
            today_str = _dt.now().strftime("%Y-%m-%d")
            draft = newsletter_generator.get_draft(today_str)
            if not draft:
                draft = newsletter_generator.get_latest_draft()
            if not draft or draft.get("status") != "locked":
                print("⚠️ No locked newsletter draft found — SKIPPING send")
                # Notify admin
                try:
                    from app.services.email_service import AdminEmailService
                    admin_svc = AdminEmailService()
                    import asyncio as _aio
                    _loop = _aio.get_event_loop()
                    if _loop.is_closed():
                        _loop = _aio.new_event_loop()
                        _aio.set_event_loop(_loop)
                    _loop.run_until_complete(admin_svc.send_admin_email(
                        subject="⚠️ Sunday newsletter SKIPPED — no locked draft",
                        body=f"The Market, Measured cron fired but no locked draft was found for {today_str}. "
                             f"The newsletter was NOT sent. Lock a draft in the admin editor before next Sunday.",
                    ))
                except Exception:
                    pass
                return {"status": "skipped", "reason": "No locked draft — newsletter requires editorial approval"}
            else:
                print(f"📨 Using locked newsletter draft from {draft.get('date')}")

                async def _send_from_draft():
                    from app.services.email_service import email_service
                    from app.core.database import NewsletterPreference, User as _NUser, Subscription
                    from sqlalchemy import select, and_

                    all_emails = set()
                    async with async_session() as db:
                        result = await db.execute(
                            select(NewsletterPreference).where(
                                NewsletterPreference.report_type == "market_measured",
                                NewsletterPreference.unsubscribed_at.is_(None),
                            )
                        )
                        for sub in result.scalars().all():
                            all_emails.add(sub.email.strip().lower())

                        result = await db.execute(
                            select(_NUser).join(Subscription, _NUser.id == Subscription.user_id).where(
                                and_(
                                    Subscription.status.in_(["active", "trialing"]),
                                    _NUser.is_active == True,
                                )
                            )
                        )
                        for user in result.scalars().all():
                            prefs = user.email_preferences or {}
                            if prefs.get("market_measured", True):
                                all_emails.add(user.email.strip().lower())

                    if target_emails:
                        all_emails = {e.strip().lower() for e in target_emails}

                    sent = 0
                    failed = 0
                    for email_addr in all_emails:
                        try:
                            ok = await email_service.send_newsletter_from_draft(
                                to_email=email_addr, draft=draft,
                            )
                            sent += 1 if ok else 0
                            failed += 0 if ok else 1
                        except Exception as e:
                            print(f"Newsletter send failed for {email_addr}: {e}")
                            failed += 1
                    return {"status": "ok", "sent": sent, "failed": failed, "source": "locked_draft"}

                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                return loop.run_until_complete(_send_from_draft())
        except Exception as e:
            print(f"❌ Locked draft send failed: {e}")
            return {"status": "error", "error": str(e)}

        async def _send_market_measured():
            import json as _json
            import boto3
            from datetime import datetime, timedelta
            from app.services.email_service import email_service
            from app.core.database import EnsembleSignal

            # Pull latest dashboard.json from S3 (legacy path — no locked draft found)
            bucket = "rigacap-prod-price-data-149218244179"
            try:
                s3 = boto3.client('s3', region_name='us-east-1')
                obj = s3.get_object(Bucket=bucket, Key='signals/dashboard.json')
                dashboard_data = _json.loads(obj['Body'].read())
            except Exception as e:
                return {"error": f"Failed to load dashboard.json: {e}"}

            # Query last 2 weeks of fresh signals for delayed-reveal track record.
            # Free-list recipients see this in place of live tickers. Paid
            # recipients get live tickers instead (last_weeks_fresh ignored
            # inside the template when show_symbols=True). Build it unconditionally
            # since a single run can mix paid and free recipients.
            last_weeks_fresh = []
            if True:
                try:
                    from sqlalchemy import select, and_, desc as sa_desc
                    today = datetime.now().date()
                    cutoff_old = today - timedelta(days=21)
                    cutoff_new = today - timedelta(days=3)
                    async with async_session() as db:
                        result = await db.execute(
                            select(EnsembleSignal)
                            .where(and_(
                                EnsembleSignal.signal_date >= cutoff_old,
                                EnsembleSignal.signal_date <= cutoff_new,
                                EnsembleSignal.is_fresh == True,
                            ))
                            .order_by(sa_desc(EnsembleSignal.signal_date))
                        )
                        sigs = result.scalars().all()
                    for s in sigs:
                        df = scanner_service.data_cache.get(s.symbol)
                        if df is None or len(df) == 0:
                            continue
                        curr = float(df['close'].iloc[-1])
                        entry = float(s.price) if s.price else None
                        if not entry:
                            continue
                        pnl = (curr / entry - 1) * 100
                        last_weeks_fresh.append({
                            "symbol": s.symbol,
                            "entry_date": s.signal_date.strftime("%b %-d") if s.signal_date else "",
                            "entry_price": entry,
                            "current_price": curr,
                            "pnl_pct": pnl,
                        })
                except Exception as _qe:
                    print(f"⚠️ last_weeks_fresh query failed: {_qe}")

            # Build per-recipient list with correct show_symbols decision.
            # Paid/trial subscribers (users table + active/trial Subscription)
            # get show_symbols=True. Free-list subscribers (newsletter_preferences)
            # get show_symbols=False. If someone's in both, paid wins (and they
            # get one email, not two).
            from sqlalchemy import select as _sel
            from app.core.database import (
                NewsletterPreference as _NP, User as _User,
                Subscription as _Sub,
            )
            paid_emails: set = set()
            free_emails: set = set()

            if target_emails:
                # Test mode: honor explicit show_symbols flag for test recipients
                if show_symbols:
                    paid_emails = {e.strip().lower() for e in target_emails}
                else:
                    free_emails = {e.strip().lower() for e in target_emails}
            else:
                async with async_session() as _q_db:
                    paid_rows = (await _q_db.execute(
                        _sel(_User.email).join(
                            _Sub, _Sub.user_id == _User.id
                        ).where(_Sub.status.in_(["active", "trial"]))
                    )).all()
                    paid_emails = {r[0].strip().lower() for r in paid_rows if r[0]}

                    free_rows = (await _q_db.execute(
                        _sel(_NP.email).where(
                            _NP.report_type == "market_measured",
                            _NP.unsubscribed_at.is_(None),
                        )
                    )).all()
                    free_emails = {r[0].strip().lower() for r in free_rows}

            # Paid wins on overlap — non-subscribers NEVER see tickers
            free_emails -= paid_emails
            per_recipient = (
                [(e, True) for e in sorted(paid_emails)]
                + [(e, False) for e in sorted(free_emails)]
            )
            if not per_recipient:
                print("📭 Market, Measured: no recipients, skipping send")
                return {"status": "ok", "sent": 0, "failed": [], "recipients": 0,
                        "paid_count": 0, "free_count": 0,
                        "track_record_entries": len(last_weeks_fresh)}
            print(f"📨 Market, Measured: {len(paid_emails)} paid + {len(free_emails)} free = {len(per_recipient)} total")
            sent = 0
            failed = []
            for email, recipient_show_symbols in per_recipient:
                try:
                    ok = await email_service.send_market_measured(
                        to_email=email,
                        dashboard_data=dashboard_data,
                        show_symbols=recipient_show_symbols,
                        last_weeks_fresh=last_weeks_fresh,
                    )
                    if ok:
                        sent += 1
                    else:
                        failed.append(email)
                except Exception as e:
                    failed.append(f"{email}: {e}")
            return {
                "status": "ok",
                "sent": sent,
                "failed": failed,
                "recipients": len(per_recipient),
                "paid_count": len(paid_emails),
                "free_count": len(free_emails),
                "track_record_entries": len(last_weeks_fresh),
            }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(_send_market_measured())
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": str(e)}

    # Biweekly TPE optimization — runs a single period of adaptive
    # optimization using the last 60 days of data, writes winning params
    # to strategy_adaptive_params table. The daily scan reads from this
    # table to get current strategy params.
    # {"biweekly_tpe": {"_": 1}} or {"biweekly_tpe": {"n_trials": 50}}
    if event.get("biweekly_tpe"):
        print("🧠 Biweekly TPE optimization")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def _run_biweekly_tpe():
                import json as _json
                from app.services.walk_forward_service import walk_forward_service
                from app.core.database import StrategyAdaptiveParams
                from app.services.email_service import admin_email_service

                cfg = event.get("biweekly_tpe") or {}
                n_trials = cfg.get("n_trials", 100)
                lookback = cfg.get("lookback_days", 60)

                # Get current date for optimization
                from zoneinfo import ZoneInfo
                now_et = datetime.now(ZoneInfo('America/New_York'))
                as_of_date = now_et.replace(hour=0, minute=0, second=0, microsecond=0)

                # Build ticker list from scanner cache
                top_symbols = sorted(
                    scanner_service.data_cache.keys(),
                    key=lambda s: scanner_service.data_cache[s]['volume'].iloc[-20:].mean()
                    if len(scanner_service.data_cache.get(s, [])) >= 20 else 0,
                    reverse=True
                )[:500]
                print(f"🧠 Running TPE: {n_trials} trials, {lookback}d lookback, "
                      f"{len(top_symbols)} symbols, as_of={as_of_date.date()}")

                # Run optimization
                result = walk_forward_service._run_ai_optimization_at_date(
                    as_of_date=as_of_date,
                    strategy_type="ensemble",
                    lookback_days=lookback,
                    ticker_list=top_symbols,
                    n_trials=n_trials,
                    optimizer_version="v2m",
                    risk_preference=0.8,
                )

                if not result or not result.best_params:
                    return {"status": "error", "error": "Optimization returned no params"}

                new_params = result.best_params
                print(f"🧠 Best params: {_json.dumps(new_params, indent=2, default=str)}")

                # Read previous params for diff
                async with async_session() as db:
                    prev_row = (await db.execute(
                        select(StrategyAdaptiveParams)
                        .where(StrategyAdaptiveParams.is_active == True)
                        .order_by(StrategyAdaptiveParams.effective_date.desc())
                        .limit(1)
                    )).scalar_one_or_none()

                    prev_params = prev_row.params_json if prev_row else {}

                    # Compute diff
                    changes = {}
                    user_facing_keys = {"trailing_stop_pct", "near_50d_high_pct",
                                        "max_positions", "position_size_pct",
                                        "dwap_threshold_pct", "profit_lock_pct"}
                    for k, v in new_params.items():
                        old_v = prev_params.get(k)
                        if old_v != v:
                            changes[k] = {"old": old_v, "new": v}

                    user_facing_changes = {k: v for k, v in changes.items()
                                          if k in user_facing_keys}

                    # Write new params
                    new_row = StrategyAdaptiveParams(
                        effective_date=as_of_date.date(),
                        params_json=new_params,
                        regime_at_optimization=result.market_regime,
                        lookback_days=lookback,
                        trials_completed=n_trials,
                        expected_return_pct=result.expected_return_pct,
                        expected_sharpe=result.expected_sharpe,
                        adaptive_score=result.adaptive_score,
                        previous_params_json=prev_params,
                        param_changes_json=changes,
                        source="biweekly_tpe",
                        is_active=True,
                    )
                    db.add(new_row)
                    await db.commit()
                    print(f"✅ Params saved (id={new_row.id}, {len(changes)} changes)")

                # Send guidance email if user-facing params changed
                if user_facing_changes:
                    guidance_lines = []
                    for k, v in user_facing_changes.items():
                        label = k.replace("_pct", "").replace("_", " ").title()
                        old_val = v["old"]
                        new_val = v["new"]
                        if isinstance(new_val, float):
                            guidance_lines.append(f"{label}: {old_val} → {new_val}")
                        else:
                            guidance_lines.append(f"{label}: {old_val} → {new_val}")

                    guidance_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:-apple-system,sans-serif;background:#f3f4f6;">
<table cellpadding="0" cellspacing="0" style="width:100%;max-width:560px;margin:0 auto;background:#fff;">
<tr><td style="background:#172554;padding:14px 20px;">
<h1 style="margin:0;color:#fff;font-size:17px;">🧠 Strategy Update — Biweekly Optimization</h1>
</td></tr>
<tr><td style="padding:16px 20px;">
<p style="margin:0 0 12px;font-size:14px;color:#374151;">
The system re-optimized using the last {lookback} days of market data.
Regime: <strong>{result.market_regime}</strong>.
</p>
<table cellpadding="0" cellspacing="0" style="width:100%;border:1px solid #e5e7eb;border-radius:8px;">
<tr style="background:#f9fafb;">
<th style="padding:8px 12px;text-align:left;font-size:12px;color:#6b7280;">Parameter</th>
<th style="padding:8px 12px;text-align:right;font-size:12px;color:#6b7280;">Previous</th>
<th style="padding:8px 12px;text-align:right;font-size:12px;color:#6b7280;">New</th>
</tr>
{''.join(f'<tr><td style="padding:6px 12px;font-size:13px;border-top:1px solid #f3f4f6;">{k.replace("_pct","").replace("_"," ").title()}</td><td style="padding:6px 12px;text-align:right;font-size:13px;color:#9ca3af;border-top:1px solid #f3f4f6;">{v["old"]}</td><td style="padding:6px 12px;text-align:right;font-size:13px;font-weight:600;border-top:1px solid #f3f4f6;">{v["new"]}</td></tr>' for k, v in user_facing_changes.items())}
</table>
<div style="margin-top:16px;background:#f0fdf4;border-left:3px solid #22c55e;padding:12px 16px;border-radius:4px;">
<p style="margin:0;font-size:13px;color:#374151;line-height:1.5;">
<strong>What to do:</strong>
{' Don' + "t add new positions — let exits naturally bring you down to " + str(new_params.get("max_positions", "?")) + " positions." if new_params.get("max_positions", 99) < prev_params.get("max_positions", 0) else " New entries should follow the updated sizing."}
New trailing stop: {new_params.get("trailing_stop_pct", "?")}%.
</p></div>
</td></tr>
<tr><td style="padding:10px 20px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center;">
RigaCap Admin · Biweekly TPE
</td></tr></table></body></html>"""

                    await admin_email_service.send_email(
                        to_email="erik@rigacap.com",
                        subject=f"🧠 Strategy Update: {len(user_facing_changes)} param(s) changed",
                        html_content=guidance_html,
                    )

                return {
                    "status": "ok",
                    "params": new_params,
                    "regime": result.market_regime,
                    "changes": len(changes),
                    "user_facing_changes": len(user_facing_changes),
                    "adaptive_score": result.adaptive_score,
                }

            result = loop.run_until_complete(_run_biweekly_tpe())
            print(f"🧠 TPE result: {result}")
            return result
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": str(e)}

    # Daily engagement opportunities — scans Twitter feeds from curated
    # finance accounts, filters for topics we have takes on, generates
    # Claude-drafted comment suggestions. Sent as admin email at 9 AM ET.
    # {"engagement_opportunities": {"_": 1}}
    if event.get("engagement_opportunities"):
        print("🎯 Engagement opportunities scan")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def _scan_engagement():
                from app.services.engagement_service import engagement_service
                from app.services.email_service import admin_email_service

                cfg = event.get("engagement_opportunities") or {}
                max_opps = cfg.get("max", 5)
                hours = cfg.get("hours", 24)

                opportunities = await engagement_service.scan_engagement_opportunities(
                    max_opportunities=max_opps,
                    since_hours=hours,
                )

                if not opportunities:
                    print("📭 No engagement opportunities found")
                    return {"status": "ok", "opportunities": 0}

                if opportunities and opportunities[0].get("error"):
                    return {"status": "error", "error": opportunities[0]["error"]}

                # Build email
                rows = []
                for i, opp in enumerate(opportunities, 1):
                    tweet_preview = opp["tweet_text"][:200]
                    if len(opp["tweet_text"]) > 200:
                        tweet_preview += "..."
                    topics = ", ".join(opp["matched_topics"][:4])
                    rows.append(f"""
                    <tr><td colspan="2" style="padding:12px 0 4px;border-top:1px solid #e5e7eb;">
                        <span style="font-size:11px;color:#6b7280;text-transform:uppercase;">#{i} &middot; @{opp['handle']} &middot; {topics}</span>
                    </td></tr>
                    <tr><td style="padding:4px 0;">
                        <p style="margin:0;font-size:14px;color:#374151;line-height:1.5;">"{tweet_preview}"</p>
                        <p style="margin:4px 0 0;font-size:12px;color:#9ca3af;">
                            ❤️ {opp.get('likes',0)} &middot; 🔄 {opp.get('retweets',0)} &middot; 💬 {opp.get('replies',0)}
                            &nbsp;&nbsp;<a href="{opp['tweet_url']}" style="color:#3b82f6;">View &rarr;</a>
                        </p>
                    </td></tr>
                    <tr><td style="padding:4px 0 8px;">
                        <div style="background:#f0fdf4;border-left:3px solid #22c55e;padding:8px 12px;border-radius:4px;">
                            <p style="margin:0;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">Suggested reply</p>
                            <p style="margin:4px 0 0;font-size:14px;color:#111827;line-height:1.5;">{opp['suggested_comment']}</p>
                        </div>
                    </td></tr>""")

                html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f3f4f6;">
<table cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;margin:0 auto;background:#fff;">
<tr><td style="background:#172554;padding:14px 20px;">
<h1 style="margin:0;color:#fff;font-size:17px;font-weight:700;">
🎯 Engagement Opportunities &middot; {len(opportunities)} posts
</h1></td></tr>
<tr><td style="padding:8px 20px;background:#f9fafb;border-bottom:1px solid #e5e7eb;">
<p style="margin:0;font-size:13px;color:#6b7280;">
Copy a suggested reply, tweak if needed, paste on the post. 5 minutes max.
</p></td></tr>
<tr><td style="padding:4px 20px 16px;">
<table cellpadding="0" cellspacing="0" style="width:100%;">
{''.join(rows)}
</table></td></tr>
<tr><td style="padding:10px 20px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center;">
RigaCap Admin &middot; Engagement Opportunities
</td></tr></table></body></html>"""

                ok = await admin_email_service.send_email(
                    to_email="erik@rigacap.com",
                    subject=f"🎯 {len(opportunities)} Engagement Opportunities",
                    html_content=html,
                )
                return {
                    "status": "ok" if ok else "email_failed",
                    "opportunities": len(opportunities),
                    "accounts_scanned": len([h for h, _, _ in __import__('app.services.engagement_service', fromlist=['MONITORED_ACCOUNTS']).MONITORED_ACCOUNTS]),
                }

            result = loop.run_until_complete(_scan_engagement())
            print(f"🎯 Engagement result: {result}")
            return result
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": str(e)}

    # Morning admin health check — scheduled 7 AM ET Mon-Fri.
    # Reads yesterday's pipeline log + dashboard + indicator validity and
    # emails Erik a concise status digest. Flags anything unusual.
    # {"admin_health_check": {"_": 1}}
    if event.get("admin_health_check"):
        print("🩺 Admin health check")

        async def _health_check():
            import pandas as _pd
            import json as _json
            from app.services.data_export import data_export_service
            from app.services.email_service import admin_email_service

            # 1. Indicator validity across cached symbols
            cache = scanner_service.data_cache
            total = 0
            valid_dwap = 0
            valid_ma50 = 0
            valid_ma200 = 0
            for _sym, _df in cache.items():
                if _df is None or len(_df) < 200:
                    continue
                total += 1
                _last = _df.iloc[-1]
                if not _pd.isna(_last.get('dwap')) and _last.get('dwap', 0) > 0:
                    valid_dwap += 1
                if not _pd.isna(_last.get('ma_50')) and _last.get('ma_50', 0) > 0:
                    valid_ma50 += 1
                if not _pd.isna(_last.get('ma_200')) and _last.get('ma_200', 0) > 0:
                    valid_ma200 += 1

            def _pct(n, d): return f"{(n/d*100):.1f}%" if d else "n/a"

            dwap_pct = (valid_dwap / total * 100) if total else 0
            indicator_healthy = dwap_pct >= 90

            # 2. Latest dashboard + pipeline log from S3
            bucket = "rigacap-prod-price-data-149218244179"
            dash = {}
            plog = {}
            try:
                import boto3
                s3 = boto3.client('s3', region_name='us-east-1')
                dash_obj = s3.get_object(Bucket=bucket, Key='signals/dashboard.json')
                dash = _json.loads(dash_obj['Body'].read())
            except Exception as _e:
                print(f"dash fetch err: {_e}")
            try:
                import boto3
                s3 = boto3.client('s3', region_name='us-east-1')
                plog_obj = s3.get_object(Bucket=bucket, Key='signals/pipeline_log.json')
                plog = _json.loads(plog_obj['Body'].read())
            except Exception as _e:
                print(f"plog fetch err: {_e}")

            buy_count = len(dash.get('buy_signals', []))
            fresh_count = sum(1 for s in dash.get('buy_signals', []) if s.get('is_fresh'))
            wl_count = len(dash.get('watchlist', []))
            regime = (dash.get('market_stats') or {}).get('regime_name', 'unknown')
            last_entry = dash.get('last_ensemble_entry_date') or 'n/a'

            pipeline_steps = plog.get('steps', [])
            bad_steps = [s for s in pipeline_steps if s.get('status') not in ('ok', 'success')]

            # 3. Determine overall health color
            flags = []
            if not indicator_healthy:
                flags.append(f"❌ Indicator validity {_pct(valid_dwap, total)} (below 90%)")
            if bad_steps:
                flags.append(f"⚠️ {len(bad_steps)} pipeline step(s) not ok: {', '.join(s.get('name','?') for s in bad_steps)}")
            if not dash.get('generated_at'):
                flags.append("❌ No dashboard.json generated_at timestamp")

            status_emoji = "✅" if not flags else "🚨"
            status_word = "Healthy" if not flags else "Attention Needed"
            header_bg = "#172554" if not flags else "#b45309"

            # Tight inline-styled rows. Previous template used <ul>+<pre>
            # which stacked >60px of browser-default margins per section.
            def _row(label, value, bold=False):
                v = f"<b>{value}</b>" if bold else value
                return (
                    '<tr>'
                    '<td style="padding:2px 12px;font-size:13px;color:#6b7280;white-space:nowrap;">'
                    f'{label}</td>'
                    '<td style="padding:2px 12px;font-size:13px;color:#111827;text-align:right;">'
                    f'{v}</td></tr>'
                )

            def _section(title, rows_html):
                return (
                    '<tr><td colspan="2" style="padding:10px 12px 2px;font-size:10px;'
                    'font-weight:700;text-transform:uppercase;color:#6b7280;'
                    'letter-spacing:0.05em;border-top:1px solid #e5e7eb;">'
                    f'{title}</td></tr>{rows_html}'
                )

            scan_rows = (
                _row("Universe", f"{total} symbols (200+ days)")
                + _row("DWAP valid", f"{valid_dwap}/{total} ({_pct(valid_dwap, total)})", bold=True)
                + _row("MA50 valid", _pct(valid_ma50, total))
                + _row("MA200 valid", _pct(valid_ma200, total))
            )
            signal_rows = (
                _row("Buy signals", f"{buy_count} ({fresh_count} fresh)")
                + _row("Watchlist", str(wl_count))
                + _row("Last ensemble entry", str(last_entry))
                + _row("Market regime", str(regime))
            )
            flags_html = ""
            if flags:
                flag_items = "".join(
                    f'<tr><td colspan="2" style="padding:3px 12px;font-size:13px;'
                    f'color:#991b1b;background:#fee2e2;">{f}</td></tr>' for f in flags
                )
                flags_html = _section("Flags", flag_items) + (
                    '<tr><td colspan="2" style="padding:8px 12px;font-size:12px;'
                    'color:#6b7280;background:#fffbeb;">'
                    'If indicator validity is low, run '
                    '<code style="background:#f3f4f6;padding:1px 4px;border-radius:3px;">'
                    '{"rebuild_indicators": {"_": 1}}</code> on worker.</td></tr>'
                )

            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f3f4f6;">
<table cellpadding="0" cellspacing="0" style="width:100%;max-width:560px;margin:0 auto;background:#fff;">
<tr><td style="background:{header_bg};padding:12px 16px;">
<h1 style="margin:0;color:#fff;font-size:16px;font-weight:700;">
{status_emoji} Morning Health &middot; <span style="font-weight:500;opacity:0.9;">{status_word}</span>
</h1></td></tr>
<tr><td style="padding:0;">
<table cellpadding="0" cellspacing="0" style="width:100%;">
{_section("Yesterday's Scan", scan_rows)}
{_section("Signals", signal_rows)}
{flags_html}
</table>
</td></tr>
<tr><td style="padding:8px 16px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center;">
RigaCap Admin
</td></tr>
</table></body></html>"""

            ok = await admin_email_service.send_email(
                to_email="erik@rigacap.com",
                subject=f"{status_emoji} RigaCap Morning Health ({status_word})",
                html_content=html,
            )
            return {
                "status": "ok" if ok else "email_failed",
                "indicator_validity_pct": dwap_pct,
                "buy_signals": buy_count,
                "fresh_signals": fresh_count,
                "watchlist": wl_count,
                "regime": regime,
                "flags": flags,
            }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(_health_check())
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": str(e)}

    if event.get("daily_emails"):
        daily_config = event.get("daily_emails") if isinstance(event.get("daily_emails"), dict) else {}
        target_emails = daily_config.get("target_emails")
        print(f"📧 Daily email digest triggered" + (f" for {target_emails}" if target_emails else ""))
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(scheduler_service.send_daily_emails(target_emails=target_emails))

            # NOTE: previously this handler re-computed dashboard.json from
            # scratch after sending emails. That caused the dashboard to diverge
            # from the email (different signal list, different AI briefing) because
            # each compute_shared_dashboard_data call can produce slightly different
            # results. The 4:30 PM daily scan is the single authoritative source
            # for dashboard.json — no other handler should overwrite it.

            return {"status": "success", "result": str(result)}
        except Exception as e:
            import traceback
            print(f"❌ Daily emails failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle double signal alerts (EventBridge: 5 PM ET Mon-Fri)
    if event.get("double_signal_alerts"):
        print("🔔 Double signal alerts triggered")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(scheduler_service.check_double_signal_alerts())
            return {"status": "success", "result": str(result)}
        except Exception as e:
            import traceback
            print(f"❌ Double signal alerts failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # New user notification — sends admin email if any users signed up today
    if event.get("new_user_check"):
        print("👤 New user check triggered")

        async def _check_new_users():
            from app.core.database import async_session, User, Subscription
            from app.services.email_service import admin_email_service, ADMIN_EMAILS
            from sqlalchemy import select, and_, func
            from datetime import datetime, timedelta

            async with async_session() as db:
                # Users created in the last 24 hours
                since = datetime.utcnow() - timedelta(hours=24)
                result = await db.execute(
                    select(User).where(User.created_at >= since).order_by(User.created_at.desc())
                )
                new_users = result.scalars().all()

                if not new_users:
                    print("👤 No new users in the last 24h")
                    return {"status": "ok", "new_users": 0}

                # Get subscription status for each
                user_lines = []
                for u in new_users:
                    sub_result = await db.execute(
                        select(Subscription).where(Subscription.user_id == u.id)
                    )
                    sub = sub_result.scalar_one_or_none()
                    sub_status = sub.status if sub else "no subscription"
                    auth_method = "Google" if u.google_id else "Apple" if u.apple_id else "email"
                    user_lines.append(f"• {u.name or u.email} ({u.email}) — {auth_method}, {sub_status}")

                body = f"<h2>🎉 {len(new_users)} New User{'s' if len(new_users) != 1 else ''} Today</h2>"
                body += "<div style='font-family:monospace; font-size:14px; line-height:2; padding:16px; background:#f3f4f6; border-radius:8px;'>"
                body += "<br>".join(user_lines)
                body += "</div>"

                subject = f"🎉 {len(new_users)} new user{'s' if len(new_users) != 1 else ''} signed up today"

                for admin in ADMIN_EMAILS:
                    await admin_email_service.send_admin_alert(admin, subject, body)

                print(f"👤 Notified admins: {len(new_users)} new users")
                return {"status": "ok", "new_users": len(new_users)}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_check_new_users())
            return result
        except Exception as e:
            import traceback
            print(f"❌ New user check failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle ticker health check (EventBridge: 7 AM ET Mon-Fri)
    if event.get("ticker_health_check"):
        print("🩺 Ticker health check triggered")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(scheduler_service.check_ticker_health())
            return {"status": "success", "result": str(result)}
        except Exception as e:
            import traceback
            print(f"❌ Ticker health check failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle publish scheduled posts (EventBridge: every 15 min)
    if event.get("publish_scheduled_posts"):
        print("📤 Publish scheduled posts triggered")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(scheduler_service._publish_scheduled_posts())
            return {"status": "success", "result": str(result)}
        except Exception as e:
            import traceback
            print(f"❌ Publish scheduled posts failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle post notifications (EventBridge: every hour)
    if event.get("post_notifications"):
        print("🔔 Post notifications triggered")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(scheduler_service._send_post_notifications())
            return {"status": "success", "result": str(result)}
        except Exception as e:
            import traceback
            print(f"❌ Post notifications failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle strategy auto-analysis (EventBridge: Fri 6:30 PM ET)
    if event.get("strategy_auto_analysis"):
        print("📊 Strategy auto-analysis triggered")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(scheduler_service._strategy_auto_analysis())
            return {"status": "success", "result": str(result)}
        except Exception as e:
            import traceback
            print(f"❌ Strategy auto-analysis failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle onboarding drip emails (EventBridge: 10 AM ET daily)
    # Optional: {"onboarding_drip": {"target_emails": ["user@example.com"]}}
    if event.get("onboarding_drip"):
        drip_config = event.get("onboarding_drip") if isinstance(event.get("onboarding_drip"), dict) else {}
        target_emails = drip_config.get("target_emails")
        print(f"📧 Onboarding drip emails triggered" + (f" for {target_emails}" if target_emails else ""))
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(scheduler_service.send_onboarding_drip_emails(target_emails=target_emails))
            return {"status": "success", "result": result}
        except Exception as e:
            import traceback
            print(f"❌ Onboarding drip failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle seed strategies (direct Lambda invocation)
    if event.get("seed_strategies"):
        print("🌱 Seed strategies request received")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_seed_and_list_strategies())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Seed strategies failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle list strategies (direct Lambda invocation)
    if event.get("list_strategies"):
        print("📋 List strategies request received")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_list_strategies())
            return result
        except Exception as e:
            import traceback
            print(f"❌ List strategies failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Handle snapshot backfill (direct Lambda invocation)
    if event.get("snapshot_backfill_job"):
        print(f"📸 Snapshot backfill job received - {len(scanner_service.data_cache)} symbols in cache")
        job_config = event["snapshot_backfill_job"]
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_snapshot_backfill():
            import pandas as pd
            from app.services.data_export import data_export_service
            from app.api.signals import _compute_dashboard_live

            spy_df = scanner_service.data_cache.get('SPY')
            if spy_df is None:
                return {"status": "failed", "error": "SPY data not in cache"}

            print(f"📸 SPY shape={spy_df.shape}, index type={type(spy_df.index).__name__}, "
                  f"tz={getattr(spy_df.index, 'tz', None)}, "
                  f"first={spy_df.index[0]}, last={spy_df.index[-1]}, "
                  f"cols={list(spy_df.columns[:5])}")

            start_ts = pd.Timestamp(job_config["start_date"])
            end_ts = pd.Timestamp(job_config["end_date"])

            if hasattr(spy_df.index, 'tz') and spy_df.index.tz is not None:
                start_ts = start_ts.tz_localize(spy_df.index.tz)
                end_ts = end_ts.tz_localize(spy_df.index.tz)

            trading_days = spy_df.loc[start_ts:end_ts].index
            total = len(trading_days)
            print(f"📸 Backfill: {total} trading days from {job_config['start_date']} to {job_config['end_date']}")

            saved = 0
            skipped = 0
            errors = 0

            async with async_session() as db:
                for i, ts in enumerate(trading_days):
                    date_str = ts.strftime('%Y-%m-%d')

                    existing = data_export_service.read_snapshot(date_str)
                    if existing:
                        skipped += 1
                        print(f"  [{i+1}/{total}] {date_str} — already exists, skipping")
                        continue

                    try:
                        data = await _compute_dashboard_live(
                            db=db, user=None, momentum_top_n=30,
                            fresh_days=5, as_of_date=date_str,
                        )
                        result = data_export_service.export_snapshot(date_str, data)
                        if result.get("success"):
                            saved += 1
                            print(f"  [{i+1}/{total}] {date_str} — saved")
                        else:
                            errors += 1
                            print(f"  [{i+1}/{total}] {date_str} — export failed: {result.get('message')}")
                    except Exception as e:
                        errors += 1
                        print(f"  [{i+1}/{total}] {date_str} — error: {e}")

            return {
                "status": "completed",
                "total_trading_days": total,
                "saved": saved,
                "skipped": skipped,
                "errors": errors,
            }

        try:
            result = loop.run_until_complete(_run_snapshot_backfill())
            print(f"📸 Snapshot backfill: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Snapshot backfill failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle ranking history generation for bar-chart-race visualization
    if event.get("ranking_history"):
        _rh_cfg = event["ranking_history"] if isinstance(event["ranking_history"], dict) else {}
        _rh_lookback = _rh_cfg.get("lookback_days", 365)
        _rh_top_n = _rh_cfg.get("top_n", 100)
        print(f"📊 Generating ranking history: lookback={_rh_lookback}d, top_n={_rh_top_n}")

        try:
            import pandas as pd, json as _rh_j2, boto3 as _rh_boto
            from datetime import datetime as _rh_datetime, timedelta as _rh_timedelta
            from app.services.data_export import S3_BUCKET as _rh_bucket

            # Get trading day calendar from SPY
            spy_df = scanner_service.data_cache.get("SPY")
            if spy_df is None or len(spy_df) < 60:
                return {"status": "error", "error": "SPY data not available"}

            cutoff = pd.Timestamp.now() - pd.Timedelta(days=_rh_lookback)
            trading_days = spy_df.index[spy_df.index >= cutoff]

            # Sample weekly (every Friday, or last trading day of each week)
            weekly_dates = []
            for d in trading_days:
                d_naive = d.tz_localize(None) if hasattr(d, 'tz') and d.tz else d
                if d_naive.weekday() == 4:  # Friday
                    weekly_dates.append(d_naive)
            # If last trading day isn't a Friday, include it
            last_td = trading_days[-1]
            last_td_naive = last_td.tz_localize(None) if hasattr(last_td, 'tz') and last_td.tz else last_td
            if not weekly_dates or weekly_dates[-1] != last_td_naive:
                weekly_dates.append(last_td_naive)

            print(f"📊 {len(weekly_dates)} weekly snapshots from {weekly_dates[0].date()} to {weekly_dates[-1].date()}")

            # Classify cap tiers from actual market cap data (S3 symbols_cache.json)
            # Standard boundaries: Mega >$200B, Large $10-200B, Mid $2-10B, Small <$2B
            _rh_s3 = _rh_boto.client("s3", region_name="us-east-1")
            try:
                _cache_resp = _rh_s3.get_object(Bucket=_rh_bucket, Key="universe/symbols_cache.json")
                _cache_data = _rh_j2.loads(_cache_resp["Body"].read().decode("utf-8"))
                _sym_info = _cache_data.get("symbol_info", {})
                print(f"📊 Loaded symbol_info for {len(_sym_info)} symbols from S3")
            except Exception as _ce:
                print(f"⚠️ Could not load symbols_cache.json: {_ce}, all tiers will be S")
                _sym_info = {}
            cap_tier_map = {}
            _tier_counts = {"M": 0, "L": 0, "D": 0, "S": 0}
            for sym in scanner_service.data_cache:
                info = _sym_info.get(sym, {})
                mc_str = info.get("market_cap", "") or ""
                try:
                    mc = int(mc_str.replace(",", ""))
                except (ValueError, AttributeError):
                    mc = 0
                if mc >= 200_000_000_000:
                    cap_tier_map[sym] = "M"
                elif mc >= 10_000_000_000:
                    cap_tier_map[sym] = "L"
                elif mc >= 2_000_000_000:
                    cap_tier_map[sym] = "D"
                else:
                    cap_tier_map[sym] = "S"
                _tier_counts[cap_tier_map[sym]] += 1
            print(f"📊 Cap tiers (market cap): M={_tier_counts['M']} L={_tier_counts['L']} D={_tier_counts['D']} S={_tier_counts['S']}")

            # Generate rankings for each weekly date
            rankings_out = {}
            dates_out = []
            for wdate in weekly_dates:
                try:
                    ranked = scanner_service.rank_stocks_momentum(
                        apply_market_filter=False, as_of_date=wdate
                    )
                    date_str = wdate.strftime("%Y-%m-%d")
                    dates_out.append(date_str)
                    top = ranked[:_rh_top_n]
                    # Clamp outlier scores: if #1 is >5x #2, cap at 2x #2
                    if len(top) >= 2 and top[0].composite_score > top[1].composite_score * 5:
                        score_cap = top[1].composite_score * 2
                    else:
                        score_cap = float("inf")
                    rankings_out[date_str] = [
                        {
                            "r": i + 1,
                            "s": r.symbol,
                            "sc": round(min(r.composite_score, score_cap), 2),
                            "sec": r.sector or "",
                            "t": cap_tier_map.get(r.symbol, "S"),
                        }
                        for i, r in enumerate(top)
                    ]
                except Exception as ex:
                    print(f"⚠️ Ranking failed for {wdate}: {ex}")

            payload = {
                "generated_at": _rh_datetime.utcnow().isoformat() + "Z",
                "dates": dates_out,
                "cap_tier_legend": {"M": "Mega Cap", "L": "Large Cap", "D": "Mid Cap", "S": "Small Cap"},
                "rankings": rankings_out,
            }

            body = _rh_j2.dumps(payload, separators=(",", ":"))
            s3 = _rh_boto.client("s3", region_name="us-east-1")
            s3.put_object(
                Bucket=_rh_bucket,
                Key="visualizations/ranking-history.json",
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )
            print(f"✅ Ranking history uploaded: {len(dates_out)} dates, {len(body)} bytes")
            return {"status": "ok", "dates": len(dates_out), "bytes": len(body)}

        except Exception as e:
            import traceback
            print(f"❌ Ranking history failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle intraday crossover simulation (direct Lambda invoke for testing)
    if event.get("simulate_intraday_crossover"):
        config = event["simulate_intraday_crossover"]
        as_of_date = config.get("as_of_date")
        do_send_email = config.get("send_email", False)
        print(f"📡 Simulating intraday crossover for {as_of_date}")

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _run_simulation():
            import pandas as pd
            from app.services.stock_universe import stock_universe_service
            from app.services.email_service import email_service

            effective_date = pd.Timestamp(as_of_date).normalize()

            def _truncate(df, ts):
                if hasattr(df.index, 'tz') and df.index.tz is not None and ts.tz is None:
                    ts = ts.tz_localize(df.index.tz)
                return df[df.index <= ts]

            spy_df = scanner_service.data_cache.get('SPY')
            if spy_df is None:
                return {"error": "SPY data not available"}

            spy_trunc = _truncate(spy_df, effective_date)
            if len(spy_trunc) < 2:
                return {"error": "Not enough data for this date"}

            prev_trading_day = spy_trunc.index[-2]
            prev_ts = prev_trading_day.tz_localize(None) if hasattr(prev_trading_day, 'tz') and prev_trading_day.tz else prev_trading_day

            # Watchlist as of previous trading day
            momentum_rankings = scanner_service.rank_stocks_momentum(
                apply_market_filter=True, as_of_date=prev_ts
            )
            top_momentum = {
                r.symbol: {'rank': i + 1, 'data': r}
                for i, r in enumerate(momentum_rankings[:30])
            }

            # Check ALL top-30 momentum stocks: below +5% prev day → above +5% today
            # This is broader than the narrow 3-5% watchlist to catch gap-ups
            prev_watchlist = []  # narrow 3-5% watchlist
            all_crossovers = []  # any stock that crossed +5% that day

            for symbol, mom in top_momentum.items():
                df = scanner_service.data_cache.get(symbol)
                if df is None or len(df) < 200:
                    continue
                df_prev = _truncate(df, prev_ts)
                if len(df_prev) < 1:
                    continue
                row = df_prev.iloc[-1]
                price = float(row['close'])
                dwap_val = row.get('dwap')
                if pd.isna(dwap_val) or dwap_val <= 0:
                    continue
                prev_pct = (price / dwap_val - 1) * 100

                # Track narrow watchlist (3-5%)
                if 3.0 <= prev_pct < 5.0:
                    prev_watchlist.append({
                        'symbol': symbol,
                        'prev_day_price': round(price, 2),
                        'dwap': round(float(dwap_val), 2),
                        'prev_day_pct_above': round(prev_pct, 2),
                        'distance_to_trigger': round(5.0 - prev_pct, 2),
                        'momentum_rank': mom['rank'],
                    })

                # Check if crossed +5% on as_of_date (broad check)
                if prev_pct < 5.0:
                    df_today = _truncate(df, effective_date)
                    if len(df_today) < 1:
                        continue
                    today_row = df_today.iloc[-1]
                    today_price = float(today_row['close'])
                    today_dwap = today_row.get('dwap')
                    if pd.isna(today_dwap) or today_dwap <= 0:
                        today_dwap = dwap_val
                    today_pct = (today_price / float(today_dwap) - 1) * 100
                    info = stock_universe_service.symbol_info.get(symbol, {})
                    all_crossovers.append({
                        'symbol': symbol,
                        'prev_day_price': round(price, 2),
                        'prev_day_pct_above': round(prev_pct, 2),
                        'as_of_date_price': round(today_price, 2),
                        'as_of_date_dwap': round(float(today_dwap), 2),
                        'as_of_date_pct_above': round(today_pct, 2),
                        'crossed': today_pct >= 5.0,
                        'was_on_watchlist': 3.0 <= prev_pct < 5.0,
                        'momentum_rank': mom['rank'],
                        'sector': info.get('sector', ''),
                    })

            prev_watchlist.sort(key=lambda x: x['distance_to_trigger'])
            prev_watchlist = prev_watchlist[:5]

            triggered = [c for c in all_crossovers if c['crossed']]

            # If force_example is set and no real crossovers found, create a
            # synthetic one using a specified symbol for email template testing
            example_symbol = config.get("force_example")
            if example_symbol and not triggered:
                df = scanner_service.data_cache.get(example_symbol)
                if df is not None and len(df) >= 200:
                    df_today = _truncate(df, effective_date)
                    if len(df_today) >= 2:
                        today_row = df_today.iloc[-1]
                        prev_row = df_today.iloc[-2]
                        today_dwap = today_row.get('dwap')
                        if not pd.isna(today_dwap) and today_dwap > 0:
                            info = stock_universe_service.symbol_info.get(example_symbol, {})
                            triggered.append({
                                'symbol': example_symbol,
                                'prev_day_price': round(float(prev_row['close']), 2),
                                'prev_day_pct_above': round((float(prev_row['close']) / float(prev_row.get('dwap', today_dwap)) - 1) * 100, 2),
                                'as_of_date_price': round(float(today_row['close']), 2),
                                'as_of_date_dwap': round(float(today_dwap), 2),
                                'as_of_date_pct_above': round((float(today_row['close']) / float(today_dwap) - 1) * 100, 2),
                                'crossed': True,
                                'was_on_watchlist': False,
                                'momentum_rank': 20,
                                'sector': info.get('sector', ''),
                                'synthetic': True,
                            })

            emails_sent = []
            if do_send_email and triggered:
                admin_email = config.get("email", "erik@rigacap.com")
                for sig in triggered:
                    success = await email_service.send_intraday_signal_alert(
                        to_email=admin_email,
                        user_name="Erik",
                        symbol=sig['symbol'],
                        live_price=sig['as_of_date_price'],
                        dwap=sig['as_of_date_dwap'],
                        pct_above_dwap=sig['as_of_date_pct_above'],
                        momentum_rank=sig['momentum_rank'],
                        sector=sig['sector'],
                    )
                    emails_sent.append({
                        'symbol': sig['symbol'],
                        'sent_to': admin_email,
                        'success': success,
                    })

            return {
                'simulation_date': as_of_date,
                'prev_trading_day': prev_ts.strftime('%Y-%m-%d'),
                'watchlist_prev_day': prev_watchlist,
                'all_crossovers': all_crossovers,
                'triggered': triggered,
                'triggered_count': len(triggered),
                'from_watchlist_count': len([t for t in triggered if t.get('was_on_watchlist')]),
                'gap_up_count': len([t for t in triggered if not t.get('was_on_watchlist')]),
                'emails_sent': emails_sent or None,
            }

        try:
            result = loop.run_until_complete(_run_simulation())
            print(f"📡 Simulation result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Intraday simulation failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle email template preview — send all templates to a given email
    if event.get("send_all_email_templates"):
        config = event["send_all_email_templates"]
        to_email = config.get("email", "erik@rigacap.com")
        print(f"📧 Sending all email templates to {to_email}")

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _send_all_templates():
            from app.services.email_service import email_service
            results = []

            # 1. Welcome email
            try:
                ok = await email_service.send_welcome_email(to_email, "Erik")
                results.append({"template": "welcome", "success": ok})
            except Exception as e:
                results.append({"template": "welcome", "error": str(e)})

            # 2. Daily summary
            try:
                sample_signals = [
                    {'symbol': 'NVDA', 'price': 142.50, 'pct_above_dwap': 8.2, 'is_strong': True,
                     'momentum_rank': 1, 'ensemble_score': 85.0, 'dwap_crossover_date': '2026-02-13',
                     'days_since_crossover': 0, 'is_fresh': True},
                    {'symbol': 'AVT', 'price': 58.30, 'pct_above_dwap': 5.4, 'is_strong': False,
                     'momentum_rank': 20, 'ensemble_score': 52.0, 'dwap_crossover_date': '2026-02-12',
                     'days_since_crossover': 1, 'is_fresh': True},
                ]
                ok = await email_service.send_daily_summary(
                    to_email=to_email,
                    signals=sample_signals,
                    market_regime={'regime': 'strong_bull', 'spy_price': 605.20},
                    watchlist=[{'symbol': 'KLAC', 'price': 810.50, 'pct_above_dwap': 4.2, 'distance_to_trigger': 0.8}],
                )
                results.append({"template": "daily_summary", "success": ok})
            except Exception as e:
                results.append({"template": "daily_summary", "error": str(e)})

            # 3. Double signal alert (breakout)
            try:
                ok = await email_service.send_double_signal_alert(
                    to_email=to_email,
                    new_signals=[
                        {'symbol': 'NVDA', 'price': 142.50, 'pct_above_dwap': 8.2,
                         'momentum_rank': 1, 'short_momentum': 12.5, 'dwap_crossover_date': '2026-02-13',
                         'days_since_crossover': 0},
                    ],
                    approaching=[
                        {'symbol': 'KLAC', 'price': 810.50, 'pct_above_dwap': 4.2, 'distance_to_trigger': 0.8},
                    ],
                    market_regime={'regime': 'strong_bull', 'spy_price': 605.20},
                )
                results.append({"template": "double_signal_alert", "success": ok})
            except Exception as e:
                results.append({"template": "double_signal_alert", "error": str(e)})

            # 4. Sell alert
            try:
                ok = await email_service.send_sell_alert(
                    to_email=to_email,
                    user_name="Erik",
                    symbol="TSLA",
                    action="sell",
                    reason="Trailing stop hit: price dropped 15% from high",
                    current_price=245.80,
                    entry_price=220.00,
                    stop_price=238.50,
                )
                results.append({"template": "sell_alert", "success": ok})
            except Exception as e:
                results.append({"template": "sell_alert", "error": str(e)})

            # 5. Sell warning
            try:
                ok = await email_service.send_sell_alert(
                    to_email=to_email,
                    user_name="Erik",
                    symbol="AAPL",
                    action="warning",
                    reason="Approaching trailing stop: 2% away",
                    current_price=198.50,
                    entry_price=185.00,
                    stop_price=195.00,
                )
                results.append({"template": "sell_warning", "success": ok})
            except Exception as e:
                results.append({"template": "sell_warning", "error": str(e)})

            # 6. Trial ending
            try:
                ok = await email_service.send_trial_ending_email(
                    to_email=to_email,
                    name="Erik",
                    days_remaining=3,
                )
                results.append({"template": "trial_ending", "success": ok})
            except Exception as e:
                results.append({"template": "trial_ending", "error": str(e)})

            # 7. Goodbye
            try:
                ok = await email_service.send_goodbye_email(to_email, "Erik")
                results.append({"template": "goodbye", "success": ok})
            except Exception as e:
                results.append({"template": "goodbye", "error": str(e)})

            # 8. Intraday signal alert (NEW)
            try:
                ok = await email_service.send_intraday_signal_alert(
                    to_email=to_email,
                    user_name="Erik",
                    symbol="AVT",
                    live_price=58.30,
                    dwap=55.20,
                    pct_above_dwap=5.6,
                    momentum_rank=20,
                    sector="Technology",
                )
                results.append({"template": "intraday_signal_alert", "success": ok})
            except Exception as e:
                results.append({"template": "intraday_signal_alert", "error": str(e)})

            return {"emails_sent_to": to_email, "results": results}

        try:
            result = loop.run_until_complete(_send_all_templates())
            print(f"📧 All templates sent: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Template send failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Social post admin (direct Lambda invocation)
    # Actions: list, approve, publish, approve_and_publish, delete, attach_image
    # Send a simple admin email (for notifications, alerts, etc.)
    if event.get("send_email"):
        config = event["send_email"]
        async def _send_email():
            from app.services.email_service import admin_email_service
            return await admin_email_service.send_admin_alert(
                to_email=config.get("to", "erik@rigacap.com"),
                subject=config.get("subject", "RigaCap Notification"),
                message=config.get("body", ""),
            )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_send_email())
            return {"status": "sent" if ok else "failed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # Read-only DB query for admin use (no mutations)
    if event.get("db_read"):
        query_sql = event["db_read"]
        print(f"📖 DB read query: {query_sql[:200]}")

        async def _db_read():
            from sqlalchemy import text
            async with async_session() as db:
                result = await db.execute(text(query_sql))
                # Auto-commit for write operations
                is_write = query_sql.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
                if is_write:
                    await db.commit()
                rows = result.fetchall()
                columns = result.keys() if hasattr(result, 'keys') else []
                return {
                    "rows": [dict(zip(columns, row)) for row in rows],
                    "count": len(rows),
                }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(_db_read())
        except Exception as e:
            return {"error": str(e)}

    if event.get("social_admin"):
        config = event["social_admin"]
        action = config.get("action", "list")

        async def _social_admin():
            from app.core.database import async_session, SocialPost
            from sqlalchemy import select, desc

            async with async_session() as db:
                if action == "list":
                    limit = config.get("limit", 20)
                    status_filter = config.get("status")
                    q = select(SocialPost).order_by(desc(SocialPost.id)).limit(limit)
                    if status_filter:
                        q = q.where(SocialPost.status == status_filter)
                    result = await db.execute(q)
                    posts = result.scalars().all()
                    return {
                        "posts": [
                            {
                                "id": p.id,
                                "platform": p.platform,
                                "post_type": p.post_type,
                                "status": p.status,
                                "text_preview": (p.text_content or "")[:100],
                                "scheduled_for": str(p.scheduled_for) if p.scheduled_for else None,
                                "created_at": str(p.created_at),
                            }
                            for p in posts
                        ]
                    }

                elif action in ("approve", "publish", "approve_and_publish"):
                    post_id = config.get("post_id")
                    if not post_id:
                        return {"error": "post_id required"}

                    result = await db.execute(
                        select(SocialPost).where(SocialPost.id == post_id)
                    )
                    post = result.scalar_one_or_none()
                    if not post:
                        return {"error": f"Post {post_id} not found"}

                    if action in ("approve", "approve_and_publish"):
                        if post.status not in ("draft", "rejected", "scheduled"):
                            return {"error": f"Cannot approve post with status '{post.status}'"}
                        post.status = "approved"
                        post.scheduled_for = None
                        await db.commit()
                        print(f"✅ Post {post_id} approved")

                    if action in ("publish", "approve_and_publish"):
                        if post.status != "approved":
                            return {"error": f"Post must be approved first (current: '{post.status}')"}
                        from app.services.social_posting_service import social_posting_service
                        pub_result = await social_posting_service.publish_post(post)
                        await db.commit()
                        if "error" in pub_result:
                            return {"error": pub_result["error"]}
                        return {"status": "published", "post_id": post_id, "platform": post.platform, **pub_result}

                    return {"status": post.status, "post_id": post_id}

                elif action == "requeue":
                    post_id = config.get("post_id")
                    if not post_id:
                        return {"error": "post_id required"}
                    result = await db.execute(
                        select(SocialPost).where(SocialPost.id == post_id)
                    )
                    post = result.scalar_one_or_none()
                    if not post:
                        return {"error": f"Post {post_id} not found"}
                    post.status = "draft"
                    post.scheduled_for = None
                    post.platform_post_id = None
                    await db.commit()
                    print(f"🔄 Requeued post {post_id} to draft")
                    return {"status": "requeued", "post_id": post_id}

                elif action == "delete":
                    post_ids = config.get("post_ids")
                    if not post_ids:
                        return {"error": "post_ids required (list of IDs)"}
                    from sqlalchemy import delete as sa_delete
                    await db.execute(sa_delete(SocialPost).where(SocialPost.id.in_(post_ids)))
                    await db.commit()
                    print(f"🗑️ Deleted {len(post_ids)} posts: {post_ids}")
                    return {"deleted": len(post_ids)}

                elif action == "attach_image":
                    post_id = config.get("post_id")
                    image_s3_key = config.get("image_s3_key")
                    if not post_id or not image_s3_key:
                        return {"error": "post_id and image_s3_key required"}
                    result = await db.execute(
                        select(SocialPost).where(SocialPost.id == post_id)
                    )
                    post = result.scalar_one_or_none()
                    if not post:
                        return {"error": f"Post {post_id} not found"}
                    post.image_s3_key = image_s3_key
                    await db.commit()
                    print(f"🖼️ Attached image to post {post_id}: {image_s3_key}")
                    return {"post_id": post_id, "image_s3_key": image_s3_key}

                elif action == "edit":
                    post_id = config.get("post_id")
                    if not post_id:
                        return {"error": "post_id required"}
                    result = await db.execute(
                        select(SocialPost).where(SocialPost.id == post_id)
                    )
                    post = result.scalar_one_or_none()
                    if not post:
                        return {"error": f"Post {post_id} not found"}
                    if config.get("text_content"):
                        post.text_content = config["text_content"]
                    if config.get("hashtags") is not None:
                        post.hashtags = config["hashtags"]
                    await db.commit()
                    print(f"✏️ Edited post {post_id}")
                    return {"status": "edited", "post_id": post_id, "text_preview": (post.text_content or "")[:100]}

                elif action == "bulk_schedule":
                    # Schedule multiple posts: [{"post_id": 97, "publish_at": "2026-02-19T14:00:00"}, ...]
                    schedule_list = config.get("posts", [])
                    if not schedule_list:
                        return {"error": "posts list required"}
                    results = []
                    for item in schedule_list:
                        pid = item.get("post_id")
                        pub_at = item.get("publish_at")
                        try:
                            publish_at = datetime.fromisoformat(pub_at)
                            r = await db.execute(
                                select(SocialPost).where(SocialPost.id == pid)
                            )
                            post = r.scalar_one_or_none()
                            if not post:
                                results.append({"post_id": pid, "scheduled": False, "error": "not found"})
                                continue
                            if post.status not in ("draft", "approved"):
                                results.append({"post_id": pid, "scheduled": False, "error": f"status is {post.status}"})
                                continue
                            post.status = "scheduled"
                            post.scheduled_for = publish_at
                            results.append({"post_id": pid, "scheduled": True, "publish_at": pub_at})
                        except Exception as e:
                            results.append({"post_id": pid, "scheduled": False, "error": str(e)})
                    await db.commit()
                    return {"scheduled": results}

                elif action == "follow_accounts":
                    # Batch follow Twitter accounts: {"usernames": ["unusual_whales", "PeterLBrandt", ...]}
                    usernames = config.get("usernames", [])
                    if not usernames:
                        return {"error": "usernames list required"}
                    from app.services.social_posting_service import social_posting_service
                    return await social_posting_service.batch_follow_twitter(usernames)

                else:
                    return {"error": f"Unknown action: {action}"}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_social_admin())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Social admin failed: {e}")
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    # Refresh Instagram long-lived token (scheduled weekly via EventBridge)
    if event.get("refresh_instagram_token"):
        print("🔄 Refreshing Instagram access token")
        import httpx

        from app.core.config import settings

        app_id = settings.META_APP_ID
        app_secret = settings.META_APP_SECRET
        current_token = settings.INSTAGRAM_ACCESS_TOKEN

        if not all([app_id, app_secret, current_token]):
            return {"status": "error", "error": "META_APP_ID, META_APP_SECRET, or INSTAGRAM_ACCESS_TOKEN not set"}

        try:
            resp = httpx.get(
                "https://graph.facebook.com/v24.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": current_token,
                },
                timeout=30,
            )
            data = resp.json()

            if "access_token" not in data:
                print(f"❌ Token refresh failed: {data}")
                # Send admin alert
                try:
                    from app.services.email_service import admin_email_service
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        admin_email_service.send_admin_alert(
                            "Instagram Token Refresh Failed",
                            f"Token refresh failed. Error: {data}. "
                            "Please manually regenerate at developers.facebook.com"
                        )
                    )
                except Exception:
                    pass
                return {"status": "error", "error": str(data)}

            new_token = data["access_token"]
            expires_in = data.get("expires_in", 0)
            expires_days = expires_in // 86400

            # Update Lambda env var with new token
            import os, boto3
            lambda_client = boto3.client("lambda", region_name=settings.AWS_REGION)
            func_config = lambda_client.get_function_configuration(
                FunctionName=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "rigacap-prod-api")
            )
            env_vars = func_config.get("Environment", {}).get("Variables", {})
            env_vars["INSTAGRAM_ACCESS_TOKEN"] = new_token
            lambda_client.update_function_configuration(
                FunctionName=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "rigacap-prod-api"),
                Environment={"Variables": env_vars},
            )

            print(f"✅ Instagram token refreshed, expires in {expires_days} days")
            return {
                "status": "refreshed",
                "expires_in_days": expires_days,
            }
        except Exception as e:
            import traceback
            print(f"❌ Token refresh error: {e}")
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    # Send test push notification (direct Lambda invocation)
    if event.get("test_push"):
        print("📱 Sending test push notification")
        config = event["test_push"]

        async def _test_push():
            from app.services.push_notification_service import push_notification_service
            from app.core.database import async_session, PushToken
            from sqlalchemy import select

            user_email = config.get("email", "erik@rigacap.com")
            title = config.get("title", "RigaCap")
            body = config.get("body", "Test push notification!")
            data = config.get("data", {"screen": "dashboard"})

            async with async_session() as db:
                # Look up user by email
                from app.core.database import User
                result = await db.execute(select(User).where(User.email == user_email))
                user = result.scalar_one_or_none()
                if not user:
                    return {"status": "error", "error": f"User not found: {user_email}"}

                # Check for active tokens
                tokens_result = await db.execute(
                    select(PushToken).where(
                        PushToken.user_id == user.id,
                        PushToken.is_active == True,
                    )
                )
                tokens = tokens_result.scalars().all()
                if not tokens:
                    return {"status": "error", "error": f"No active push tokens for {user_email}"}

                # Send push
                results = await push_notification_service.send_to_user(
                    db, user.id, title, body, data
                )
                return {
                    "status": "success",
                    "user": user_email,
                    "tokens_found": len(tokens),
                    "results": results,
                }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_test_push())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Test push failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    if event.get("weekly_regime_report"):
        print("📊 Weekly regime report triggered")
        cfg = event.get("weekly_regime_report") or {}
        target_emails = cfg.get("target_emails") if isinstance(cfg, dict) else None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def _send_regime_report():
                from app.core.database import async_session, EmailSubscriber, User, Subscription
                from app.services.regime_forecast_service import regime_forecast_service
                from app.services.email_service import email_service
                from sqlalchemy import select

                sent_count = 0
                error_count = 0

                async with async_session() as db:
                    history = await regime_forecast_service.get_forecast_history(db, days=30)
                    if not history:
                        return {"status": "skipped", "reason": "No regime history"}

                    # If target_emails specified, only send to those
                    if target_emails:
                        for email_addr in target_emails:
                            try:
                                html = email_service.generate_regime_report_html(history=history)
                                success = await email_service.send_weekly_regime_report(to_email=email_addr, html=html)
                                sent_count += 1 if success else 0
                                error_count += 0 if success else 1
                            except Exception as e:
                                print(f"Failed: {email_addr}: {e}")
                                error_count += 1
                        return {"status": "ok", "sent": sent_count, "errors": error_count, "target_only": True}

                    # Free subscribers
                    result = await db.execute(
                        select(EmailSubscriber).where(EmailSubscriber.is_active == True)
                    )
                    subscribers = result.scalars().all()

                    for sub in subscribers:
                        try:
                            html = email_service.generate_regime_report_html(
                                history=history, subscriber_id=sub.id
                            )
                            success = await email_service.send_weekly_regime_report(
                                to_email=sub.email, html=html, subscriber_id=sub.id
                            )
                            sent_count += 1 if success else 0
                            error_count += 0 if success else 1
                        except Exception as e:
                            print(f"Failed: {sub.email}: {e}")
                            error_count += 1

                    # Paid users
                    result = await db.execute(
                        select(User).join(Subscription, Subscription.user_id == User.id).where(
                            Subscription.status.in_(["active", "trial"]),
                            User.is_active == True,
                        )
                    )
                    users = result.scalars().all()
                    subscriber_emails = {s.email.lower() for s in subscribers}

                    for user in users:
                        if user.email.lower() in subscriber_emails:
                            continue
                        if not user.get_email_preference("regime_report"):
                            continue
                        try:
                            html = email_service.generate_regime_report_html(
                                history=history, user_id=str(user.id)
                            )
                            success = await email_service.send_weekly_regime_report(
                                to_email=user.email, html=html, user_id=str(user.id)
                            )
                            sent_count += 1 if success else 0
                            error_count += 0 if success else 1
                        except Exception as e:
                            print(f"Failed: {user.email}: {e}")
                            error_count += 1

                return {"status": "ok", "sent": sent_count, "errors": error_count}

            result = loop.run_until_complete(_send_regime_report())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Weekly regime report failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # For API Gateway events, use Mangum
    # Create a fresh Mangum handler to avoid event loop issues on warm Lambdas
    # Check if event loop is closed and reset if needed
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            asyncio.set_event_loop(asyncio.new_event_loop())
            _mangum_handler = None  # Force recreation
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
        _mangum_handler = None

    if _mangum_handler is None:
        _mangum_handler = Mangum(app, lifespan="off")

    return _mangum_handler(event, context)


# ============================================================================
# Health & Config Endpoints
# ============================================================================

@app.get("/")
async def root(admin: User = Depends(get_admin_user)):
    return {
        "name": "RigaCap API",
        "version": "2.0.0",
        "docs": "/docs",
        "data_loaded": len(scanner_service.data_cache),
        "last_scan": scanner_service.last_scan.isoformat() if scanner_service.last_scan else None
    }


@app.get("/health")
async def health(user: User = Depends(get_current_user)):
    from app.services.scheduler import scheduler_service
    scheduler_status = scheduler_service.get_status()

    # Use local cache if available, otherwise get metadata from S3
    symbols_loaded = len(scanner_service.data_cache)
    last_scan = scanner_service.last_scan.isoformat() if scanner_service.last_scan else None

    # If no local data, try to get metadata from S3
    if symbols_loaded == 0:
        try:
            status = data_export_service.get_status()
            symbols_loaded = status.get("files_count", 0)
            if status.get("last_export"):
                last_scan = status.get("last_export")
        except Exception:
            pass  # Ignore errors, just use default values

    return {
        "status": "healthy",
        "symbols_loaded": symbols_loaded,
        "last_scan": last_scan,
        "scheduler": {
            "running": scheduler_status["is_running"],
            "last_run": scheduler_status["last_run"],
            "next_runs": scheduler_status["next_runs"]
        }
    }


@app.post("/api/warmup")
async def warmup(admin: User = Depends(get_admin_user)):
    """
    Warm up Lambda by loading all data.
    Call this after deployment to preload data so user requests are fast.
    """
    results = {
        "universe": {"loaded": 0, "status": "pending"},
        "price_data": {"loaded": 0, "status": "pending"},
        "consolidated": {"status": "pending"}
    }

    # 1. Load universe
    try:
        await scanner_service.ensure_universe_loaded()
        results["universe"] = {
            "loaded": len(scanner_service.universe),
            "status": "success"
        }
    except Exception as e:
        results["universe"] = {"loaded": 0, "status": f"error: {e}"}

    # 2. Load price data from S3
    try:
        if not scanner_service.data_cache:
            cached_data = data_export_service.import_all()
            if cached_data:
                scanner_service.data_cache = cached_data
        results["price_data"] = {
            "loaded": len(scanner_service.data_cache),
            "status": "success"
        }
    except Exception as e:
        results["price_data"] = {"loaded": 0, "status": f"error: {e}"}

    # 3. Report consolidated status (don't export - could overwrite larger S3 file)
    if scanner_service.data_cache and len(scanner_service.data_cache) > 0:
        try:
            status = data_export_service.get_status()
            results["consolidated"] = {
                "success": True,
                "count": len(scanner_service.data_cache),
                "s3_status": status
            }
        except Exception as e:
            results["consolidated"] = {"status": f"error: {e}"}

    return {
        "status": "warmed",
        "results": results
    }


@app.post("/api/data/load-batch")
async def load_batch(batch_size: int = 50, admin: User = Depends(get_admin_user)):
    """
    Load a batch of stocks that aren't already cached.
    Call this repeatedly to gradually build up the full dataset.

    Args:
        batch_size: Number of stocks to load per call (default 50, max 100)
    """
    batch_size = min(batch_size, 100)  # Cap at 100 to avoid timeout

    # Ensure universe is loaded
    await scanner_service.ensure_universe_loaded()

    # Find symbols not yet cached
    cached_symbols = set(scanner_service.data_cache.keys())
    all_symbols = set(scanner_service.universe)
    missing_symbols = list(all_symbols - cached_symbols)

    if not missing_symbols:
        return {
            "status": "complete",
            "message": "All stocks already loaded",
            "total_cached": len(cached_symbols),
            "total_universe": len(all_symbols)
        }

    # Take a batch
    batch = missing_symbols[:batch_size]

    # Fetch data for this batch
    try:
        await scanner_service.fetch_data(batch)
        newly_loaded = len([s for s in batch if s in scanner_service.data_cache])

        # Save progress to S3
        export_result = data_export_service.export_consolidated(scanner_service.data_cache)

        return {
            "status": "progress",
            "batch_requested": len(batch),
            "batch_loaded": newly_loaded,
            "total_cached": len(scanner_service.data_cache),
            "total_universe": len(all_symbols),
            "remaining": len(missing_symbols) - newly_loaded,
            "export": export_result
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "total_cached": len(scanner_service.data_cache)
        }


@app.get("/api/data/status")
async def data_status(admin: User = Depends(get_admin_user)):
    """Get current data loading status"""
    await scanner_service.ensure_universe_loaded()

    cached_symbols = set(scanner_service.data_cache.keys())
    all_symbols = set(scanner_service.universe)

    return {
        "total_universe": len(all_symbols),
        "total_cached": len(cached_symbols),
        "remaining": len(all_symbols - cached_symbols),
        "percent_complete": round(len(cached_symbols) / len(all_symbols) * 100, 1) if all_symbols else 0,
        "cached_symbols_sample": list(cached_symbols)[:20]
    }


@app.get("/api/market-data-status")
async def get_market_data_status():
    """
    Public (unauthenticated) endpoint for frontend staleness banner.
    Returns data freshness status based on time of day and last dashboard update.
    """
    import pytz
    from app.services.market_data_provider import market_data_provider

    et = pytz.timezone("US/Eastern")
    now_et = datetime.now(et)
    hour = now_et.hour
    minute = now_et.minute
    weekday = now_et.weekday()  # 0=Mon, 6=Sun

    # Check last dashboard update time from S3
    last_updated = None
    source = market_data_provider.last_bars_source or "unknown"
    try:
        from app.services.data_export import data_export_service
        dashboard = data_export_service.read_dashboard_json()
        if dashboard and dashboard.get("generated_at"):
            last_updated = dashboard["generated_at"]
    except Exception:
        pass

    # Determine status based on time of day
    is_weekend = weekday >= 5

    if is_weekend:
        # Weekends: always fresh (Friday's data is expected)
        status = "fresh"
        message = None
    elif hour < 16:
        # Before 4 PM ET: yesterday's close is expected, always fresh
        status = "fresh"
        message = None
    else:
        # 4 PM ET onward: check if dashboard was already updated today
        updated_today = False
        if last_updated:
            try:
                updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                updated_et = updated_dt.astimezone(et)
                updated_today = updated_et.date() == now_et.date()
            except Exception:
                pass

        if updated_today:
            status = "fresh"
            message = None
        elif hour == 16 and minute < 15:
            # Brief processing window — scan typically finishes in ~5 min
            status = "processing"
            message = "Market data is being updated. Signals will refresh shortly."
        else:
            status = "stale"
            message = "Today's market data is delayed. Signals may not reflect current prices."

    # Extract data_date from dashboard JSON
    data_date = None
    if dashboard and dashboard.get("data_date"):
        data_date = dashboard["data_date"]

    return {
        "status": status,
        "last_updated": last_updated,
        "data_date": data_date,
        "source": source,
        "message": message,
        "health": market_data_provider.get_health_summary(),
    }


@app.get("/api/live-market-stats")
async def live_market_stats():
    """Live SPY/VIX quote — lightweight, no auth, no pickle."""
    from app.services.market_data_provider import market_data_provider
    import yfinance as yf

    result = {}
    try:
        quotes = await market_data_provider.fetch_quotes(['SPY'])
        if quotes.get('SPY'):
            q = quotes['SPY']
            result['spy_price'] = q.price
            result['spy_change_pct'] = q.change_pct
            result['spy_prev_close'] = q.prev_close
    except Exception:
        pass

    try:
        vix = yf.Ticker('^VIX')
        result['vix_level'] = round(vix.fast_info.last_price, 2)
    except Exception:
        pass

    result['timestamp'] = datetime.utcnow().isoformat()
    return result


@app.get("/api/config")
async def get_config(admin: User = Depends(get_admin_user)):
    return {
        "dwap_threshold_pct": settings.DWAP_THRESHOLD_PCT,
        "stop_loss_pct": settings.STOP_LOSS_PCT,
        "profit_target_pct": settings.PROFIT_TARGET_PCT,
        "max_positions": settings.MAX_POSITIONS,
        "position_size_pct": settings.POSITION_SIZE_PCT,
        "min_volume": settings.MIN_VOLUME,
        "min_price": settings.MIN_PRICE,
        "universe_size": len(scanner_service.universe),
        "full_universe_loaded": scanner_service.full_universe_loaded
    }


@app.get("/api/debug/yfinance")
async def debug_yfinance(admin: User = Depends(get_admin_user)):
    """Debug endpoint to test yfinance import"""
    result = {"yfinance_available": False, "error": None, "version": None}
    try:
        import yfinance as yf
        result["yfinance_available"] = True
        result["version"] = yf.__version__
        # Try a simple download
        ticker = yf.Ticker("AAPL")
        info = ticker.fast_info
        result["test_ticker"] = "AAPL"
        result["test_price"] = info.last_price if hasattr(info, 'last_price') else None
    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
    return result


@app.post("/api/universe/load-full")
async def load_full_universe(admin: User = Depends(get_admin_user)):
    """
    Load the full NASDAQ + NYSE stock universe (~6000 stocks)

    This replaces the default 80-stock curated list.
    Note: Initial data fetch will take several minutes.
    """
    try:
        symbols = await scanner_service.load_full_universe()
        return {
            "success": True,
            "universe_size": len(symbols),
            "message": f"Loaded {len(symbols)} stocks from NASDAQ + NYSE"
        }
    except Exception as e:
        logger.error(f"Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/universe/status")
async def get_universe_status(admin: User = Depends(get_admin_user)):
    """Get current universe status"""
    return {
        "universe_size": len(scanner_service.universe),
        "full_universe_loaded": scanner_service.full_universe_loaded,
        "symbols_with_data": len(scanner_service.data_cache),
        "sample_symbols": scanner_service.universe[:20] if scanner_service.universe else []
    }


@app.post("/api/data/load")
async def load_market_data(symbols: Optional[str] = None, period: str = "5y", admin: User = Depends(get_admin_user)):
    """
    Manually trigger market data loading

    Args:
        symbols: Optional comma-separated list of symbols (default: all in universe)
        period: Data period (1y, 2y, 5y)
    """
    try:
        # Parse comma-separated symbols
        symbol_list = None
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
        await scanner_service.fetch_data(symbols=symbol_list, period=period)
        return {
            "success": True,
            "symbols_loaded": len(scanner_service.data_cache),
            "message": f"Loaded data for {len(scanner_service.data_cache)} symbols"
        }
    except Exception as e:
        return {
            "success": False,
            "symbols_loaded": len(scanner_service.data_cache),
            "error": str(e),
            "message": "Partial load completed or Yahoo Finance rate limited"
        }


@app.get("/api/data/status")
async def get_data_status(admin: User = Depends(get_admin_user)):
    """Get current data loading status"""
    return {
        "data_available": len(scanner_service.data_cache) > 0,
        "symbols_loaded": len(scanner_service.data_cache),
        "universe_size": len(scanner_service.universe),
        "last_scan": scanner_service.last_scan.isoformat() if scanner_service.last_scan else None,
        "loaded_symbols": list(scanner_service.data_cache.keys())[:50] if scanner_service.data_cache else []
    }


@app.post("/api/data/export")
async def export_data(admin: User = Depends(get_admin_user)):
    """
    Export all cached price data to individual CSV files

    This saves historical data permanently so it never needs to be re-fetched.
    """
    if not scanner_service.data_cache:
        raise HTTPException(status_code=400, detail="No data to export. Load data first.")

    result = data_export_service.export_all(scanner_service.data_cache)
    return result


@app.post("/api/data/export-consolidated")
async def export_data_consolidated(admin: User = Depends(get_admin_user)):
    """
    Export all cached price data to a single consolidated gzipped CSV.

    Much faster to load than individual files. Use this before deployments
    to save the latest data, and call /api/warmup after deployment to reload.
    """
    if not scanner_service.data_cache:
        raise HTTPException(status_code=400, detail="No data to export. Load data first.")

    result = data_export_service.export_consolidated(scanner_service.data_cache)
    return result


@app.post("/api/data/pre-deploy")
async def pre_deploy_export(admin: User = Depends(get_admin_user)):
    """
    Pre-deployment export: Save all current price data to S3.

    Call this BEFORE deploying new code to ensure no data is lost.
    The warmup endpoint after deployment will reload this data.
    """
    if not scanner_service.data_cache:
        return {"status": "skip", "message": "No data in cache to export"}

    # Export consolidated file
    result = data_export_service.export_consolidated(scanner_service.data_cache)

    return {
        "status": "success" if result.get("success") else "failed",
        "symbols_exported": result.get("count", 0),
        "size_mb": result.get("total_size_mb", 0),
        "message": "Data saved to S3. Safe to deploy."
    }


@app.get("/api/data/export-status")
async def get_export_status(admin: User = Depends(get_admin_user)):
    """Get status of exported data files"""
    return data_export_service.get_status()


@app.post("/api/data/import")
async def import_data(admin: User = Depends(get_admin_user)):
    """
    Import price data from Parquet files into memory

    This is called automatically on startup, but can be triggered manually.
    """
    cached_data = data_export_service.import_all()
    if cached_data:
        scanner_service.data_cache = cached_data
        return {
            "success": True,
            "symbols_loaded": len(cached_data),
            "message": f"Imported {len(cached_data)} symbols from parquet files"
        }
    return {
        "success": False,
        "symbols_loaded": 0,
        "message": "No parquet files found to import"
    }


# ============================================================================
# Market Analysis Endpoints
# ============================================================================

@app.get("/api/market/regime")
async def get_market_regime(user: User = Depends(require_valid_subscription)):
    """
    Get current market regime and trading recommendation.

    Uses multi-factor analysis: SPY trend, VIX, breadth, momentum.
    Returns one of 6 regimes: strong_bull, weak_bull, range_bound, weak_bear, panic_crash, recovery.
    """
    from app.services.market_regime import market_regime_service

    try:
        # Load SPY and VIX from S3 if not already cached
        missing = [s for s in ['SPY', '^VIX'] if s not in scanner_service.data_cache]
        if missing:
            loaded = data_export_service.import_symbols(missing)
            scanner_service.data_cache.update(loaded)

        spy_df = scanner_service.data_cache.get('SPY')
        if spy_df is None or len(spy_df) < 200:
            raise HTTPException(status_code=503, detail="Insufficient SPY data")

        vix_df = scanner_service.data_cache.get('^VIX')

        # Use the 6-regime multi-factor detection
        regime = market_regime_service.detect_regime(
            spy_df=spy_df,
            universe_dfs=scanner_service.data_cache,
            vix_df=vix_df
        )

        regime_dict = regime.to_dict()

        # Map to format expected by frontend (backward compatibility)
        spy_price = spy_df.iloc[-1]['close'] if len(spy_df) > 0 else 0
        vix_level = vix_df.iloc[-1]['close'] if vix_df is not None and len(vix_df) > 0 else 20

        conditions = regime_dict.get('conditions', {})
        return {
            "regime": regime_dict.get('regime_type', regime_dict.get('name', 'neutral')),
            "regime_name": regime_dict.get('regime_name', regime_dict.get('name', 'Neutral').replace('_', ' ').title()),
            "spy_price": round(spy_price, 2),
            "spy_ma_200": round(conditions.get('spy_ma_200', 0), 2),
            "spy_ma_50": round(conditions.get('spy_ma_50', 0), 2),
            "spy_vs_200ma_pct": round(conditions.get('spy_vs_200ma_pct', 0), 2),
            "spy_pct_from_high": round(conditions.get('spy_pct_from_high', 0), 2),
            "vix_level": round(vix_level, 2),
            "vix_percentile": round(conditions.get('vix_percentile', 50), 1),
            "trend_strength": round(conditions.get('trend_strength', 0), 2),
            "long_term_trend": round(conditions.get('long_term_trend', 0), 2),
            "breadth_pct": round(conditions.get('breadth_pct', 50), 1),
            "new_highs_pct": round(conditions.get('new_highs_pct', 0), 1),
            "recommendation": regime_dict.get('description', ''),
            "risk_level": regime_dict.get('risk_level', 'medium'),
            "confidence": regime_dict.get('confidence', 0),
            "color": regime_dict.get('color', '#6B7280'),
            "updated": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/market/sectors")
async def get_sector_strength(admin: User = Depends(get_admin_user)):
    """
    Get sector strength rankings

    Returns sectors sorted by relative strength (0-100).
    """
    try:
        await market_analysis_service.update_sector_strength()
        return {
            "sectors": market_analysis_service.sector_strength,
            "strong_sectors": market_analysis_service.get_strong_sectors(),
            "weak_sectors": market_analysis_service.get_weak_sectors(),
            "updated": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/market/summary")
async def get_market_summary(admin: User = Depends(get_admin_user)):
    """
    Get complete market summary including regime and sectors
    """
    try:
        state = await market_analysis_service.update_market_state()
        await market_analysis_service.update_sector_strength()

        return {
            "regime": state.to_dict(),
            "sectors": {
                "rankings": market_analysis_service.sector_strength,
                "strong": market_analysis_service.get_strong_sectors(),
                "weak": market_analysis_service.get_weak_sectors()
            },
            "trading_guidance": {
                "regime": state.regime.value,
                "recommendation": state.recommendation,
                "vix_level": state.vix_level,
                "trend_strength": state.trend_strength
            }
        }
    except Exception as e:
        logger.error(f"Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Scheduler Endpoints
# ============================================================================

@app.get("/api/scheduler/status")
async def get_scheduler_status(admin: User = Depends(get_admin_user)):
    """Get scheduler status and next run times"""
    from app.services.scheduler import scheduler_service
    return scheduler_service.get_status()


@app.post("/api/scheduler/run")
async def trigger_manual_update(admin: User = Depends(get_admin_user)):
    """
    Manually trigger a market update (for testing)

    This runs the same job that runs daily at 4:30 PM ET
    """
    from app.services.scheduler import scheduler_service
    try:
        await scheduler_service.run_now()
        return {
            "message": "Manual update completed successfully",
            "status": scheduler_service.get_status()
        }
    except Exception as e:
        logger.error(f"Scheduler update failed: {e}")
        raise HTTPException(status_code=500, detail="Update failed")


# ============================================================================
# Backtest Endpoints
# ============================================================================

@app.get("/api/backtest/run")
async def run_backtest(days: int = 252, strategy: str = "momentum", max_symbols: int = 200, user: User = Depends(require_valid_subscription)):
    """
    Run backtest over historical data

    Returns simulated positions and trades based on the selected strategy.
    Default is momentum strategy (v2). Use strategy="dwap" for legacy.

    Args:
        days: Number of trading days to simulate (default 252 = 1 year)
        strategy: "momentum" (default) or "dwap" for legacy
        max_symbols: Limit symbols for faster response (default 200)

    """
    if not scanner_service.data_cache:
        raise HTTPException(
            status_code=400,
            detail="No market data loaded. Please wait for data to load or trigger a scan."
        )

    use_momentum = strategy.lower() != "dwap"

    # Use top liquid symbols for faster response
    from app.services.strategy_analyzer import get_top_liquid_symbols
    top_symbols = get_top_liquid_symbols(max_symbols=max_symbols)

    try:
        result = backtester_service.run_backtest(
            lookback_days=days,
            use_momentum_strategy=use_momentum,
            ticker_list=top_symbols
        )
        return {
            "success": True,
            "strategy": "momentum" if use_momentum else "dwap",
            "backtest": {
                "start_date": result.start_date,
                "end_date": result.end_date,
                "total_return_pct": result.total_return_pct,
                "win_rate": result.win_rate,
                "total_trades": result.total_trades,
                "open_positions": result.open_positions,
                "total_pnl": result.total_pnl,
                "max_drawdown_pct": result.max_drawdown_pct,
                "sharpe_ratio": result.sharpe_ratio
            },
            "positions": [p.to_dict() for p in result.positions],
            "trades": [t.to_dict() for t in result.trades]
        }
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise HTTPException(status_code=500, detail="Backtest failed")


@app.get("/api/backtest/positions")
async def get_backtest_positions(days: int = 252, admin: User = Depends(get_admin_user)):
    """
    Get simulated open positions from backtest

    These are positions we would currently hold if following the strategy.
    """
    if not scanner_service.data_cache:
        raise HTTPException(status_code=400, detail="No market data loaded")

    try:
        result = backtester_service.run_backtest(lookback_days=days)
        return {
            "positions": [p.to_dict() for p in result.positions],
            "total_value": sum(p.shares * p.current_price for p in result.positions),
            "total_pnl_pct": sum(p.pnl_pct * p.shares * p.entry_price for p in result.positions) /
                            sum(p.shares * p.entry_price for p in result.positions)
                            if result.positions else 0
        }
    except Exception as e:
        logger.error(f"Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/backtest/trades")
async def get_backtest_trades(days: int = 252, limit: int = 50, admin: User = Depends(get_admin_user)):
    """
    Get trade history from backtest
    """
    if not scanner_service.data_cache:
        raise HTTPException(status_code=400, detail="No market data loaded")

    try:
        result = backtester_service.run_backtest(lookback_days=days)
        return {
            "trades": [t.to_dict() for t in result.trades[:limit]],
            "total": len(result.trades),
            "win_rate": result.win_rate,
            "total_pnl": result.total_pnl
        }
    except Exception as e:
        logger.error(f"Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/backtest/walk-forward-cached")
async def get_cached_walk_forward(user: User = Depends(require_valid_subscription), db: AsyncSession = Depends(get_db)):
    """
    Get the latest cached daily walk-forward simulation results.

    This runs automatically once per day and provides more accurate simulated
    portfolio stats than a simple backtest (accounts for strategy switches).
    """
    from app.core.database import WalkForwardSimulation
    import json

    # Get the latest cached walk-forward result
    result = await db.execute(
        select(WalkForwardSimulation)
        .where(WalkForwardSimulation.is_daily_cache == True)
        .where(WalkForwardSimulation.status == "completed")
        .order_by(desc(WalkForwardSimulation.simulation_date))
        .limit(1)
    )
    cached = result.scalar_one_or_none()

    if not cached:
        # No cached result, return None so frontend can fall back to simple backtest
        return {
            "available": False,
            "message": "No cached walk-forward results available yet"
        }

    # Parse equity curve and switch history from JSON
    equity_curve = []
    switch_history = []
    try:
        if cached.equity_curve_json:
            equity_curve = json.loads(cached.equity_curve_json)
        if cached.switch_history_json:
            switch_history = json.loads(cached.switch_history_json)
    except json.JSONDecodeError:
        pass

    return {
        "available": True,
        "simulation_date": cached.simulation_date.isoformat(),
        "start_date": cached.start_date.isoformat(),
        "end_date": cached.end_date.isoformat(),
        "total_return_pct": cached.total_return_pct,
        "sharpe_ratio": cached.sharpe_ratio,
        "max_drawdown_pct": cached.max_drawdown_pct,
        "benchmark_return_pct": cached.benchmark_return_pct,
        "num_strategy_switches": cached.num_strategy_switches,
        "switch_history": switch_history,
        "equity_curve": equity_curve,
        "reoptimization_frequency": cached.reoptimization_frequency,
    }


# ============================================================================
# Portfolio Endpoints (with Database)
# ============================================================================

@app.get("/api/portfolio/positions", response_model=PositionsListResponse)
async def get_positions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all open positions with current prices (split-adjusted)"""

    result = await db.execute(
        select(DBPosition).where(DBPosition.status == "open", DBPosition.user_id == user.id).order_by(desc(DBPosition.created_at))
    )
    db_positions = result.scalars().all()

    # Load any missing position symbols from S3 CSVs (API Lambda has no pickle)
    missing_symbols = [p.symbol for p in db_positions if p.symbol not in scanner_service.data_cache]
    if missing_symbols:
        try:
            loaded = data_export_service.import_symbols(missing_symbols)
            scanner_service.data_cache.update(loaded)
        except Exception as e:
            logger.warning(f"Failed to load position symbols from S3: {e}")

    positions = []
    total_value = 0.0
    total_cost = 0.0

    # Trailing stop configuration (ensemble strategy uses 12%)
    TRAILING_STOP_PCT = 12.0

    for pos in db_positions:
        # Get split-adjusted entry price from historical data
        # This handles stock splits automatically - yfinance adjusts all historical prices
        adjusted_entry = get_split_adjusted_price(pos.symbol, pos.entry_date, pos.entry_price)

        # Get current price from cache if available
        current_price = adjusted_entry  # Default to entry if no live data
        if pos.symbol in scanner_service.data_cache:
            df = scanner_service.data_cache[pos.symbol]
            if len(df) > 0:
                current_price = float(df.iloc[-1]['close'])

        # Calculate high water mark from historical data since entry
        high_water_mark = adjusted_entry
        if pos.symbol in scanner_service.data_cache:
            df = scanner_service.data_cache[pos.symbol]
            # Filter to dates on or after entry (normalize to midnight so
            # the entry day itself is included regardless of time-of-day)
            entry_ts = pd.Timestamp(pos.entry_date).normalize()
            if hasattr(df.index, 'tz') and df.index.tz is not None:
                entry_ts = entry_ts.tz_localize(df.index.tz)
            mask = df.index >= entry_ts
            if mask.any():
                high_water_mark = max(adjusted_entry, float(df.loc[mask, 'close'].max()))

        # Update database with high water mark if it's higher
        if pos.highest_price is None or high_water_mark > pos.highest_price:
            pos.highest_price = high_water_mark

        # Calculate trailing stop from high water mark
        trailing_stop_price = round(high_water_mark * (1 - TRAILING_STOP_PCT / 100), 2)

        # Calculate distance to trailing stop (positive = above stop, negative = below)
        distance_to_stop_pct = ((current_price - trailing_stop_price) / trailing_stop_price) * 100

        # Determine sell signal
        if current_price <= trailing_stop_price:
            sell_signal = "sell"  # Already hit trailing stop
        elif distance_to_stop_pct <= 3.0:
            sell_signal = "warning"  # Within 3% of trailing stop
        else:
            sell_signal = "hold"

        # Calculate legacy stop/target for backwards compatibility
        stop_loss = round(adjusted_entry * (1 - settings.STOP_LOSS_PCT / 100), 2)
        profit_target = round(adjusted_entry * (1 + settings.PROFIT_TARGET_PCT / 100), 2)

        from app.core.timezone import days_since_et
        days_held = days_since_et(pos.entry_date)
        pnl_pct = ((current_price - adjusted_entry) / adjusted_entry) * 100
        position_value = pos.shares * current_price

        total_value += position_value
        total_cost += pos.shares * adjusted_entry

        positions.append(PositionResponse(
            id=pos.id,
            symbol=pos.symbol,
            shares=pos.shares,
            entry_price=round(adjusted_entry, 2),
            entry_date=pos.entry_date.strftime('%Y-%m-%d'),
            current_price=round(current_price, 2),
            stop_loss=stop_loss,
            profit_target=profit_target,
            pnl_pct=round(pnl_pct, 2),
            days_held=days_held,
            high_water_mark=round(high_water_mark, 2),
            trailing_stop_price=trailing_stop_price,
            trailing_stop_pct=TRAILING_STOP_PCT,
            distance_to_stop_pct=round(distance_to_stop_pct, 1),
            sell_signal=sell_signal
        ))

    # Commit any high water mark updates
    await db.commit()

    total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

    return PositionsListResponse(
        positions=positions,
        total_value=round(total_value, 2),
        total_pnl_pct=round(total_pnl_pct, 2)
    )


@app.post("/api/portfolio/positions")
async def open_position(request: OpenPositionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Open a new position"""
    symbol = request.symbol.upper()

    # Get current price from cache or use provided price
    price = request.price
    if not price and symbol in scanner_service.data_cache:
        df = scanner_service.data_cache[symbol]
        if len(df) > 0:
            price = float(df.iloc[-1]['close'])

    if not price:
        raise HTTPException(status_code=400, detail=f"Could not get price for {symbol}. Provide price or run scan first.")

    shares = request.shares or (10000 / price)  # Default ~$10k position

    # Use provided entry_date (time-travel mode) or default to now
    if request.entry_date:
        entry_date = datetime.strptime(request.entry_date, '%Y-%m-%d')
    else:
        entry_date = datetime.now()

    position = DBPosition(
        user_id=user.id,
        symbol=symbol,
        entry_date=entry_date,
        entry_price=price,
        shares=round(shares, 2),
        stop_loss=round(price * (1 - settings.STOP_LOSS_PCT / 100), 2),
        profit_target=round(price * (1 + settings.PROFIT_TARGET_PCT / 100), 2),
        highest_price=price,
        status="open"
    )

    db.add(position)
    await db.commit()
    await db.refresh(position)

    return {
        "message": f"Opened position in {symbol}",
        "position": {
            "id": position.id,
            "symbol": position.symbol,
            "shares": position.shares,
            "entry_price": position.entry_price,
            "stop_loss": position.stop_loss,
            "profit_target": position.profit_target
        }
    }


@app.delete("/api/portfolio/positions/{position_id}")
async def close_position(position_id: int, exit_price: Optional[float] = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Close a position and record the trade (with split-adjusted prices)"""

    result = await db.execute(select(DBPosition).where(DBPosition.id == position_id, DBPosition.user_id == user.id))
    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    # Get split-adjusted entry price
    adjusted_entry = get_split_adjusted_price(position.symbol, position.entry_date, position.entry_price)

    # Get exit price
    price = exit_price
    if not price and position.symbol in scanner_service.data_cache:
        df = scanner_service.data_cache[position.symbol]
        if len(df) > 0:
            price = float(df.iloc[-1]['close'])

    if not price:
        price = adjusted_entry  # Fallback

    # Calculate P&L using split-adjusted entry
    pnl = (price - adjusted_entry) * position.shares
    pnl_pct = ((price - adjusted_entry) / adjusted_entry) * 100

    # Calculate split-adjusted stop/target for exit reason
    stop_loss = adjusted_entry * (1 - settings.STOP_LOSS_PCT / 100)
    profit_target = adjusted_entry * (1 + settings.PROFIT_TARGET_PCT / 100)

    # Determine exit reason
    exit_reason = "manual"
    if price <= stop_loss:
        exit_reason = "stop_loss"
    elif price >= profit_target:
        exit_reason = "profit_target"

    # Record trade with split-adjusted entry price
    trade = DBTrade(
        user_id=user.id,
        position_id=position.id,
        symbol=position.symbol,
        entry_date=position.entry_date,
        entry_price=round(adjusted_entry, 2),
        exit_date=datetime.now(),
        exit_price=price,
        shares=position.shares,
        pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 2),
        exit_reason=exit_reason
    )
    db.add(trade)

    # Mark position as closed
    position.status = "closed"

    await db.commit()

    return {
        "message": f"Closed position in {position.symbol}",
        "trade": {
            "symbol": trade.symbol,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "pnl_pct": trade.pnl_pct,
            "exit_reason": trade.exit_reason
        }
    }


@app.get("/api/portfolio/trades")
async def get_trades(limit: int = 50, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get trade history"""

    result = await db.execute(
        select(DBTrade).where(DBTrade.user_id == user.id).order_by(desc(DBTrade.exit_date)).limit(limit)
    )
    trades = result.scalars().all()

    return {
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "entry_date": t.entry_date.strftime('%Y-%m-%d'),
                "entry_price": t.entry_price,
                "exit_date": t.exit_date.strftime('%Y-%m-%d'),
                "exit_price": t.exit_price,
                "shares": t.shares,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "exit_reason": t.exit_reason
            }
            for t in trades
        ],
        "total": len(trades)
    }


@app.get("/api/portfolio/equity")
async def get_equity_curve(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get equity curve based on trade history

    For now, returns cumulative P&L from trades.
    TODO: Implement proper daily equity tracking.
    """
    result = await db.execute(
        select(DBTrade).where(DBTrade.user_id == user.id).order_by(DBTrade.exit_date)
    )
    trades = result.scalars().all()

    if not trades:
        # Return empty curve if no trades yet
        return {"equity_curve": []}

    # Build cumulative equity curve
    initial_capital = 100000
    equity = initial_capital
    curve = []

    for trade in trades:
        equity += trade.pnl
        curve.append(EquityPoint(
            date=trade.exit_date.strftime('%Y-%m-%d'),
            equity=round(equity, 2)
        ))

    return {"equity_curve": curve}


@app.get("/api/stock/{symbol}/history")
async def get_stock_history(symbol: str, days: int = 252, user: User = Depends(require_valid_subscription)):
    """Get historical price data for a symbol from cache"""
    symbol = symbol.upper()

    # Load this symbol from S3 CSV if not already cached
    if symbol not in scanner_service.data_cache:
        try:
            loaded = data_export_service.import_symbols([symbol])
            scanner_service.data_cache.update(loaded)
        except Exception as e:
            logger.warning(f"Failed to load {symbol} from S3: {e}")

    if symbol not in scanner_service.data_cache:
        # Try to fetch it from yfinance
        try:
            await scanner_service.fetch_data([symbol], period="5y")
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Could not fetch data for {symbol}")

    if symbol not in scanner_service.data_cache:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    df = scanner_service.data_cache[symbol].copy()

    # Calculate indicators if they don't exist (e.g., for newly added symbols)
    if 'dwap' not in df.columns:
        # Calculate DWAP (Daily Weighted Average Price) - 200-day volume-weighted average
        df['dwap'] = (df['close'] * df['volume']).rolling(200).sum() / df['volume'].rolling(200).sum()
    if 'ma_50' not in df.columns:
        df['ma_50'] = df['close'].rolling(50).mean()
    if 'ma_200' not in df.columns:
        df['ma_200'] = df['close'].rolling(200).mean()

    df = df.tail(days)

    return {
        "symbol": symbol,
        "data": [
            {
                "date": idx.strftime('%Y-%m-%d'),
                "open": round(row['open'], 2),
                "high": round(row['high'], 2),
                "low": round(row['low'], 2),
                "close": round(row['close'], 2),
                "volume": int(row['volume']),
                "dwap": round(row['dwap'], 2) if pd.notna(row.get('dwap')) else None,
                "ma_50": round(row['ma_50'], 2) if pd.notna(row.get('ma_50')) else None,
                "ma_200": round(row['ma_200'], 2) if pd.notna(row.get('ma_200')) else None,
            }
            for idx, row in df.iterrows()
        ]
    }


# ============================================================================
# Live Quotes Endpoint (for real-time UI updates)
# ============================================================================

@app.get("/api/quotes/live")
async def get_live_quotes(symbols: str = "", user: User = Depends(get_current_user)):
    """
    Get live/current quotes for symbols.

    Uses DualSourceProvider (Alpaca SIP primary, yfinance fallback).
    Note: Signals are still based on daily CLOSE prices.

    Args:
        symbols: Comma-separated list of symbols, or empty for all positions

    Returns:
        Dict of symbol -> quote data
    """
    from app.services.market_data_provider import market_data_provider

    # Parse symbols or get from open positions
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        # Get symbols from user's open positions
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(DBPosition.symbol).where(DBPosition.status == 'open', DBPosition.user_id == user.id).distinct()
                )
                symbol_list = [row[0] for row in result.fetchall()]
        except:
            symbol_list = []

    if not symbol_list:
        return {"quotes": {}, "timestamp": datetime.now().isoformat()}

    # Fetch current quotes via DualSourceProvider
    quotes = {}
    try:
        quote_data = await market_data_provider.fetch_quotes(symbol_list)
        for symbol, qd in quote_data.items():
            quotes[symbol] = {
                "price": qd.price,
                "change": qd.change,
                "change_pct": qd.change_pct,
                "prev_close": qd.prev_close,
            }
    except Exception as e:
        logger.error(f"Failed to fetch live quotes: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch quotes")

    return {
        "quotes": quotes,
        "timestamp": datetime.now().isoformat(),
        "count": len(quotes),
        "source": market_data_provider.last_quotes_source,
    }


@app.post("/api/quotes/batch")
async def get_batch_quotes(symbols: List[str], admin: User = Depends(get_admin_user)):
    """
    Get live quotes for a batch of symbols (POST for larger lists).
    """
    from app.services.market_data_provider import market_data_provider

    if not symbols:
        return {"quotes": {}, "timestamp": datetime.now().isoformat()}

    symbol_list = [s.upper() for s in symbols[:100]]  # Limit to 100 symbols

    quotes = {}
    try:
        quote_data = await market_data_provider.fetch_quotes(symbol_list)
        for symbol, qd in quote_data.items():
            quotes[symbol] = {
                "price": qd.price,
                "change": qd.change,
                "change_pct": qd.change_pct,
                "prev_close": qd.prev_close,
            }
    except Exception as e:
        logger.error(f"Failed to fetch batch quotes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    return {
        "quotes": quotes,
        "timestamp": datetime.now().isoformat(),
        "count": len(quotes),
        "source": market_data_provider.last_quotes_source,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
