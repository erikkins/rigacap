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
from app.api.events import router as events_router
from app.api.email_tracking import router as email_tracking_router
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

    # Settlement probe symbol — must be an Alpaca-native, ultra-liquid name.
    # Was SPY (most-traded ETF) until May 19 2026 when we re-routed SPY
    # through yfinance for benchmark/regime use (see
    # market_data_provider.YFINANCE_PREFERRED — Alpaca is SIP-faithful and
    # preserves outlier ticks; yfinance applies outlier filtering, which
    # is what our 200MA regime detection needs). With SPY no longer on
    # Alpaca's side of the dual-source split, this settlement check hung
    # 5 min then fell back to yfinance, blowing the 15-min Lambda budget
    # — caused three consecutive daily_scan timeouts on May 20 2026
    # before this fix.
    # AAPL: stock (never routed), Alpaca-native, ~50M daily volume.
    PROBE_SYMBOL = "AAPL"
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
            bars = await alpaca.fetch_bars([PROBE_SYMBOL], start_date=five_days_ago)
            probe_df = bars.get(PROBE_SYMBOL)
            if probe_df is not None and len(probe_df) > 0:
                last_date = probe_df.index.max()
                last_date_normalized = pd.Timestamp(last_date).normalize().tz_localize(None)
                expected_ts = pd.Timestamp(expected_date)
                last_vol = int(probe_df.iloc[-1].get("volume", 0))
                # Keep field names spy_* for backward compat with consumers
                result["spy_date"] = str(last_date_normalized.date())
                result["spy_volume"] = last_vol

                if last_date_normalized >= expected_ts and last_vol >= min_spy_volume:
                    result["settled"] = True
                    print(f"📡 Alpaca settled: attempt {attempt}, "
                          f"{PROBE_SYMBOL} {last_date_normalized.date()}, vol={last_vol:,}")
                    break
                else:
                    print(f"📡 Settlement attempt {attempt}/{max_retries}: "
                          f"{PROBE_SYMBOL} date={last_date_normalized.date()} (need {expected_date}), "
                          f"vol={last_vol:,} (need {min_spy_volume:,}) — waiting {retry_interval}s...")
            else:
                print(f"📡 Settlement attempt {attempt}/{max_retries}: "
                      f"no {PROBE_SYMBOL} data from Alpaca — waiting {retry_interval}s...")
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
    source: Optional[str] = None  # 'preserver' (trailing) | 'breakout' (Maximizer hold) — scopes the exit rule


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
    allow_headers=["Authorization", "Content-Type", "Accept", "X-2FA-Trust"],
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


def _is_deadlock_exc(exc) -> bool:
    """True if this exception (or its chain) is a Postgres deadlock / serialization abort —
    transient DB lock contention that succeeds on retry."""
    seen = set()
    e = exc
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        if type(e).__name__ in ("DeadlockDetectedError", "SerializationError"):
            return True
        msg = str(e).lower()
        if "deadlock detected" in msg or "could not serialize" in msg:
            return True
        e = getattr(e, "__cause__", None) or getattr(e, "__context__", None)
    return False


class DeadlockRetryMiddleware(BaseHTTPMiddleware):
    """Postgres can abort a transaction when two collide (deadlock) — a transient error that
    succeeds on retry. Without this, the victim request 500s (and pages us). The aborted
    transaction never committed, so re-running the request is data-safe. Buffer the body so a
    POST can be re-read on retry. Happy path adds only a tiny body-read; retries fire only on
    an actual deadlock (cap 2, brief backoff)."""
    async def dispatch(self, request: StarletteRequest, call_next):
        try:
            await request.body()  # cache body so a retry can re-read it
        except Exception:
            pass
        import asyncio as _aio
        for attempt in range(3):
            try:
                return await call_next(request)
            except Exception as e:
                if _is_deadlock_exc(e) and attempt < 2:
                    try:
                        print(f"⚠️ DB deadlock on {request.method} {request.url.path} — retry {attempt + 1}/2")
                    except Exception:
                        pass
                    await _aio.sleep(0.05 * (attempt + 1))
                    continue
                raise

app.add_middleware(DeadlockRetryMiddleware)

# Reject requests that didn't come through CloudFront. Disabled when the
# env var is empty (so local dev doesn't need the header). See
# app/core/origin_guard.py for full rationale.
from app.core.origin_guard import OriginVerifyMiddleware
app.add_middleware(OriginVerifyMiddleware)

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
app.include_router(events_router, prefix="/api/events", tags=["events"])
app.include_router(email_tracking_router, prefix="/api/email", tags=["email-tracking"])

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
                vol_weight=job_config.get("vol_weight"),
                regime_reentry_mode=job_config.get("regime_reentry_mode", False),
                bear_keep_pct=job_config.get("bear_keep_pct", 0.0),
                graduated_reentry=job_config.get("graduated_reentry", False),
                param_smoothing=job_config.get("param_smoothing", 0.0),
                warmup_periods=job_config.get("warmup_periods", 0),
                ensemble_seeds=job_config.get("ensemble_seeds", 0),
                regime_fixed_params=job_config.get("regime_fixed_params"),
                intraday_aware=job_config.get("intraday_aware", False),
                hwm_from_day_high=job_config.get("hwm_from_day_high", False),
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

                # Post-completion hook for the nightly missed-opps job: regenerate
                # social posts from the trades. This used to live in the monolithic
                # nightly handler — moved here so it fires on the FINAL chunk of a
                # chained run. Best-effort: a failure here doesn't fail the job.
                if job_config.get("nightly_post_complete"):
                    try:
                        from app.services.social_content_service import social_content_service
                        posts = await social_content_service.generate_from_nightly_wf(db, job_id)
                        print(f"[ASYNC-WF] Nightly post-complete: generated {len(posts)} social posts")
                    except Exception as social_err:
                        print(f"[ASYNC-WF] Nightly social-content step failed: {social_err}")

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


async def _notify_tier_books(db):
    """Admin summary of the SHADOW tier books' activity today (Preserver + Maximizer), from
    tier_fills. Core t30v is covered separately by _notify_portfolio_change (the live model
    book). Together these give admin eyes on all three of the 'triple-threat' books each scan.
    Admin-only, non-fatal."""
    try:
        from sqlalchemy import text as _text
        from app.services.email_service import admin_email_service, ADMIN_EMAILS
        rows = (await db.execute(_text(
            "SELECT tier, side, symbol, reason, days_held, realized_pnl, price, shares "
            "FROM tier_fills WHERE fill_date = CURRENT_DATE ORDER BY tier, side, symbol"
        ))).all()
        if not rows:
            return
        by_tier = {}
        for r in rows:
            by_tier.setdefault(r[0], []).append(r)
        sections = []
        for tier in ("preserver", "maximizer"):
            frs = by_tier.get(tier, [])
            if not frs:
                continue
            lines = []
            for (_t, side, sym, reason, dh, pnl, price, shares) in frs:
                if reason in ("exposure_trim", "exposure_restore"):
                    lines.append(f"  {reason.replace('_', ' ')}: ${(price or 0):,.0f} shifted")
                elif side == "buy":
                    lines.append(f"  BUY {sym} @ ${(price or 0):.2f}")
                else:
                    # realized_pnl is DOLLARS — convert to a RETURN % off cost basis
                    # (cost = exit_gross - realized_pnl = shares*price - realized_pnl). The old
                    # code printed the dollar P&L with a "%" sign (e.g. -$443 shown as -443.5%).
                    _p = ""
                    if pnl is not None:
                        _basis = (shares or 0) * (price or 0) - pnl
                        _p = f", {(pnl / _basis * 100):+.1f}%" if _basis > 0 else f", ${pnl:+,.0f}"
                    lines.append(f"  SELL {sym} @ ${(price or 0):.2f} ({reason or 'exit'}{_p}, {dh or 0}d)")
            sections.append(f"{tier.upper()}:\n" + "\n".join(lines))
        if not sections:
            return
        body = ("Shadow tier books — today's activity (Core t30v is in the separate "
                "Portfolio BUY/SELL email):\n\n" + "\n\n".join(sections))
        subject = "Tier Books: " + " / ".join(t.upper() for t in ("preserver", "maximizer") if t in by_tier)
        for admin in ADMIN_EMAILS:
            await admin_email_service.send_admin_alert(admin, subject, body)
        print(f"📧 Tier-book notification sent ({len(sections)} book(s) active)")
    except Exception as e:
        print(f"⚠️ Tier-book notification failed (non-fatal): {e}")


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
    # event paths below (send_daily_emails, check_ticker_health, etc.)
    # plus the FastAPI /health endpoint which has its own inline import.
    # Keeping it out of module-level shaves ~235ms off API Lambda cold start.
    from app.services.scheduler import scheduler_service

    # Persistent event loop helper for warm Lambda invocations.
    # asyncio.run() closes its loop on return, which breaks asyncpg connection
    # pools on the *next* invocation (the pool is bound to the closed loop).
    # asyncio.get_event_loop() raises in Python 3.12+ when no current loop
    # exists. This helper threads the needle: get the existing loop if it's
    # alive, otherwise create + register a new one and reuse it. Never close.
    def _run_async(coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("loop closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    global _mangum_handler

    # Log every non-warmer event for debugging (EventBridge async invocations were failing silently)
    if not event.get("warmer"):
        event_keys = [k for k in event.keys() if not k.startswith("_")]
        print(f"🔔 Lambda handler invoked: keys={event_keys}")

    # Pipeline health report — runs WITHOUT pickle (lightweight S3/CW/DB checks only)
    # Must be handled BEFORE _ensure_lambda_data_loaded() to skip the 2+ GB pickle load
    if "pipeline_health_report" in event:
        print("🩺 Pipeline health report triggered")
        try:
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

            result = _run_async(_run_health_report())
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
            async def _run_migrations():  # noqa: E306
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

            result = _run_async(_run_migrations())
            print(f"🔧 Migration results: {result}")
            return {"statusCode": 200, "body": {"migrations": result}}
        except Exception as e:
            import traceback
            print(f"❌ Migration failed: {e}")
            print(traceback.format_exc())
            return {"statusCode": 500, "error": str(e)}

    # SnapTrade cost reconcile — deregister any 'active' PROD-key connection whose subscriber is no
    # longer currently-paid ('active' + valid), so we stop paying ~$1/user/day for them. Scoped to
    # st_env='prod' (the TEST key is a free demo, handled by snaptrade_free_test_slots) and admins
    # are exempt. Trials can't reach prod (the connect gate blocks them), so prod rows are only ever
    # real paying users. DEFAULTS TO DRY-RUN. Pass {"snaptrade_reconcile":{"apply":true}} to delete.
    if event.get("snaptrade_reconcile"):
        opts = event.get("snaptrade_reconcile")
        apply = bool(opts.get("apply")) if isinstance(opts, dict) else False
        print(f"🧹 SnapTrade reconcile (prod, apply={apply})")
        try:
            async def _reconcile():  # noqa: E306
                from sqlalchemy import select
                from app.core.database import async_session, SnaptradeUser, Subscription, User
                from app.services.snaptrade_lifecycle import deregister
                flagged = []
                async with async_session() as db:
                    rows = (await db.execute(
                        select(SnaptradeUser).where(
                            SnaptradeUser.status == "active", SnaptradeUser.st_env == "prod")
                    )).scalars().all()
                    for row in rows:
                        user = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
                        if user and user.is_admin():
                            continue     # never touch an admin's connection
                        sub = (await db.execute(
                            select(Subscription).where(Subscription.user_id == row.user_id)
                        )).scalar_one_or_none()
                        # Keep ONLY currently-paid subscribers (mirrors the connect gate).
                        keep = bool(sub and sub.status == "active" and sub.is_valid())
                        if keep:
                            continue
                        res = await deregister(db, row.user_id, reason="reconcile", apply=apply)
                        flagged.append({
                            "user_id": str(row.user_id),
                            "email": (user.email if user else None),
                            "sub_status": (sub.status if sub else None),
                            "is_valid": bool(sub and sub.is_valid()),
                            "action": res.get("action"),
                        })
                    return {"scanned_prod_active": len(rows), "flagged_count": len(flagged),
                            "flagged": flagged, "applied": apply}
            result = _run_async(_reconcile())
            print(f"🧹 SnapTrade reconcile results: {result}")
            return {"statusCode": 200, "body": result}
        except Exception as e:
            import traceback
            print(f"❌ SnapTrade reconcile failed: {e}")
            print(traceback.format_exc())
            return {"statusCode": 500, "error": str(e)}

    # Free TEST-key connection slots (the demo key is capped at 5). Deregister every 'active'
    # st_env='test' connection that is NOT an admin's — demo/gawker squatters left from before the
    # paid gate. Admins keep their demo connections. DEFAULTS TO DRY-RUN.
    if event.get("snaptrade_free_test_slots"):
        opts = event.get("snaptrade_free_test_slots")
        apply = bool(opts.get("apply")) if isinstance(opts, dict) else False
        print(f"🧹 SnapTrade free-test-slots (apply={apply})")
        try:
            async def _free_test():  # noqa: E306
                from sqlalchemy import select
                from app.core.database import async_session, SnaptradeUser, User
                from app.services.snaptrade_lifecycle import deregister
                freed = []
                async with async_session() as db:
                    rows = (await db.execute(
                        select(SnaptradeUser).where(
                            SnaptradeUser.status == "active", SnaptradeUser.st_env == "test")
                    )).scalars().all()
                    for row in rows:
                        user = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
                        if user and user.is_admin():
                            continue     # keep admin demo connections
                        res = await deregister(db, row.user_id, reason="test_slot", apply=apply)
                        freed.append({"user_id": str(row.user_id), "email": (user.email if user else None),
                                      "action": res.get("action")})
                    return {"scanned_test_active": len(rows), "freed_count": len(freed),
                            "freed": freed, "applied": apply}
            result = _run_async(_free_test())
            print(f"🧹 SnapTrade free-test-slots results: {result}")
            return {"statusCode": 200, "body": result}
        except Exception as e:
            import traceback
            print(f"❌ SnapTrade free-test-slots failed: {e}")
            print(traceback.format_exc())
            return {"statusCode": 500, "error": str(e)}

    # Admin peek: which tickers a connected user pulled (symbols + brokerage only — no balances, no
    # secrets ever leave the Lambda). Admin-gated by the fact that a direct Lambda invoke already
    # requires AWS creds. Usage: {"snaptrade_holdings_for": "<email or user_id>"}.
    if event.get("snaptrade_holdings_for"):
        ident = str(event.get("snaptrade_holdings_for"))
        print(f"🔎 SnapTrade holdings peek for {ident}")
        try:
            async def _peek():  # noqa: E306
                from sqlalchemy import select
                from app.core.database import async_session, SnaptradeUser, User
                from app.services import snaptrade_service as st
                import uuid as _u
                async with async_session() as db:
                    user = (await db.execute(select(User).where(User.email == ident))).scalar_one_or_none()
                    if not user:
                        try:
                            user = (await db.execute(select(User).where(User.id == _u.UUID(ident)))).scalar_one_or_none()
                        except Exception:
                            user = None
                    if not user:
                        return {"error": f"no user for {ident}"}
                    row = (await db.execute(select(SnaptradeUser).where(SnaptradeUser.user_id == user.id))).scalar_one_or_none()
                    if not row or row.status != "active" or not row.user_secret:
                        return {"email": user.email, "connected": False}
                    env = row.st_env or "prod"
                    h = await st.all_holdings(str(user.id), st.decrypt_secret(row.user_secret), env=env)
                    return {"email": user.email, "env": env,
                            "connected": h.get("account_count", 0) > 0,
                            "symbols": h.get("symbols", []), "sources": h.get("sources", [])}
            result = _run_async(_peek())
            print(f"🔎 holdings peek: {result}")
            return {"statusCode": 200, "body": result}
        except Exception as e:
            import traceback
            print(f"❌ holdings peek failed: {e}")
            print(traceback.format_exc())
            return {"statusCode": 500, "error": str(e)}

    # Unwind pre-universe-change model portfolio positions
    if event.get("unwind_old_positions"):
        print("🔄 Unwinding pre-universe-change model portfolio positions")
        try:
            cutoff_date = event.get("cutoff_date", "2026-03-09")
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

            result = _run_async(_unwind())
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

    # Test intraday cache fetch — verifies Alpaca minute-bar pipeline end-to-end.
    if event.get("test_intraday_fetch"):
        cfg = event["test_intraday_fetch"]
        symbol = cfg.get("symbol", "AAPL")
        date_str = cfg.get("date", "2024-03-15")
        import time as _time
        from app.services.intraday_cache import get_intraday_cache
        cache = get_intraday_cache()
        t0 = _time.time()
        df = _run_async(cache.get_or_fetch(symbol, date_str))
        t_first = _time.time() - t0
        if df is None or df.empty:
            return {"status": "no_data", "symbol": symbol, "date": date_str, "first_fetch_seconds": round(t_first, 2)}
        t0 = _time.time()
        df2 = _run_async(cache.get_or_fetch(symbol, date_str))
        t_second = _time.time() - t0
        # Diagnostic: compare in detail
        index_dtype_match = str(df.index.dtype) == str(df2.index.dtype)
        col_dtype_match = bool((df.dtypes.astype(str) == df2.dtypes.astype(str)).all())
        values_match = bool((df.values == df2.values).all())
        index_values_match = bool(df.index.equals(df2.index))
        return {
            "status": "ok",
            "symbol": symbol,
            "date": date_str,
            "rows": len(df),
            "first_minute": str(df.index.min()),
            "last_minute": str(df.index.max()),
            "columns": list(df.columns),
            "open_first_minute": round(float(df["open"].iloc[0]), 2),
            "close_last_minute": round(float(df["close"].iloc[-1]), 2),
            "intraday_high": round(float(df["high"].max()), 2),
            "intraday_low": round(float(df["low"].min()), 2),
            "total_volume": int(df["volume"].sum()),
            "first_fetch_seconds": round(t_first, 2),
            "cache_hit_seconds": round(t_second, 3),
            "data_match_strict": bool(df.equals(df2)),
            "index_dtype_orig": str(df.index.dtype),
            "index_dtype_cached": str(df2.index.dtype),
            "index_dtypes_equal": index_dtype_match,
            "col_dtypes_equal": col_dtype_match,
            "values_equal": values_match,
            "index_values_equal": index_values_match,
            "col_dtype_diff": {c: f"{df[c].dtype} -> {df2[c].dtype}" for c in df.columns if str(df[c].dtype) != str(df2[c].dtype)},
        }

    # Intraday WF reconciliation: re-run trailing-stop exits with minute-bar
    # accuracy. Closes the parity gap between WF (EOD-only) and production
    # (intraday). Payload: {"intraday_wf_validation": {"trades": [...], "trailing_stop_pct": 0.12}}
    if event.get("intraday_wf_validation"):
        cfg = event["intraday_wf_validation"]
        trades = cfg.get("trades", [])
        ts_pct = float(cfg.get("trailing_stop_pct", 0.12))
        s3_output_key = cfg.get("s3_output_key")  # optional S3 key to write full results

        from app.services.intraday_cache import get_intraday_cache
        from app.services.intraday_wf_validator import IntradayWFValidator
        # NOTE: scanner_service is already imported at module level (line 41).
        # Re-importing inside this if-block would shadow it as a local in the
        # entire handler() function, breaking warmer + every other path that
        # reads scanner_service before this branch runs (UnboundLocalError).

        # Daily bars come from the payload — caller pre-extracts them from the
        # local 11y pickle so the worker doesn't need to load any pickle or fetch
        # anything from Alpaca for daily data. Per the data-cache rule: never
        # re-fetch what we already have.
        # Payload format: daily_bars = {symbol: [{"date": ISO, "open": .., "high": .., "low": .., "close": ..}, ...]}
        import pandas as _pd
        daily_bars_payload = cfg.get("daily_bars", {})
        print(f"📊 Intraday WF validation starting: {len(trades)} trades, trailing_stop_pct={ts_pct}, daily-bar payload={len(daily_bars_payload)} symbols")

        # Materialize each symbol's daily bars as a DataFrame indexed by date
        daily_lookup_dict: dict = {}
        for sym, rows in daily_bars_payload.items():
            if not rows:
                continue
            df_d = _pd.DataFrame(rows)
            df_d["date"] = _pd.to_datetime(df_d["date"]).dt.normalize()
            df_d = df_d.set_index("date").sort_index()
            df_d = df_d[~df_d.index.duplicated(keep="last")]
            daily_lookup_dict[sym] = df_d

        cache = get_intraday_cache()
        cadence = int(cfg.get("check_cadence_minutes", 5))  # default matches production
        validator = IntradayWFValidator(trailing_stop_pct=ts_pct, check_cadence_minutes=cadence)
        print(f"📊 Cadence: {cadence}-min check (production = 5-min)")

        def daily_lookup(symbol):
            return daily_lookup_dict.get(symbol)

        result = _run_async(
            validator.validate_trades(trades, daily_lookup, cache)
        )

        # Optionally write full results to S3 (results list can be large)
        if s3_output_key:
            try:
                import boto3
                import json as _json
                s3 = boto3.client("s3")
                bucket = os.environ.get("PRICE_DATA_BUCKET")
                if bucket:
                    s3.put_object(
                        Bucket=bucket,
                        Key=s3_output_key,
                        Body=_json.dumps(result, default=str).encode(),
                        ContentType="application/json",
                    )
                    print(f"📦 Full results written to s3://{bucket}/{s3_output_key}")
            except Exception as e:
                print(f"⚠️ S3 write failed: {e}")

        return {
            "summary": result["summary"],
            "trailing_stop_pct": result["trailing_stop_pct"],
            "skipped": result["skipped"],
            "s3_output_key": s3_output_key,
            "result_count": len(result["results"]),
        }

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

            # 1-pre. Non-trading-day guard (Jun 20 2026). The EventBridge cron
            # fires Mon-Fri but doesn't know holidays. On a market holiday there
            # are no new bars, so the SPY freshness gate expected today's bar,
            # found yesterday's, and ABORTED with errors — after a 271s Alpaca
            # settlement stall + a wall of yfinance delisting noise (Juneteenth,
            # Jun 19 2026, which was also missing from the holiday calendar).
            # Skip cleanly instead: no scan, no abort, no held-email cascade.
            from app.services.health_monitor_service import is_us_trading_day
            from zoneinfo import ZoneInfo as _ZoneInfo  # local alias — ZoneInfo is re-imported later in this fn, which makes the bare name a function-local (UnboundLocalError here otherwise)
            _now_et = datetime.now(_ZoneInfo('America/New_York'))
            if not is_us_trading_day(_now_et.date()):
                print(f"📅 {_now_et.date()} is not a US trading day (weekend/holiday) — skipping daily scan cleanly.")
                _write_pipeline_log("skipped_non_trading_day")
                return {"status": "skipped", "reason": "non_trading_day", "date": _now_et.date().isoformat()}

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
                        try:
                            # send_admin_alert takes an email STRING, not a User
                            # object — passing the User 400'd with "'User' object
                            # has no attribute 'lower'" on Jun 19 2026, so the
                            # abort silently failed to notify. Pass the email.
                            for email in ADMIN_EMAILS:
                                await admin_email_service.send_admin_alert(
                                    to_email=email,
                                    subject="Daily scan ABORTED: SPY data stale",
                                    message=(f"SPY last date: {spy_last_date}, expected: {expected_date}. "
                                             f"Both Alpaca and yfinance failed to return today's data. "
                                             f"Scan was aborted to prevent stale signals."),
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
                _invalid_syms = []
                for _sym, _df in scanner_service.data_cache.items():
                    # Skip index symbols (^VIX, ^GSPC, …): they carry no volume, so DWAP
                    # (a volume-weighted average) is always NaN. They aren't tradeable and
                    # were the perpetual "1 invalid" in the Morning Health email.
                    if _sym.startswith('^'):
                        continue
                    if _df is None or len(_df) < 200:
                        continue
                    total_checked += 1
                    _last = _df.iloc[-1]
                    _dwap = _last.get('dwap')
                    if _dwap is not None and not _pd.isna(_dwap) and _dwap > 0:
                        valid_dwap += 1
                    else:
                        _invalid_syms.append(_sym)
                validity_pct = (valid_dwap / total_checked * 100) if total_checked else 0
                canary_msg = f"{valid_dwap}/{total_checked} ({validity_pct:.1f}%) valid dwap on latest bar"
                if _invalid_syms:
                    # Name the offenders so the count is actionable, never a bare "N-1/N".
                    canary_msg += f" — invalid: {', '.join(sorted(_invalid_syms)[:15])}"
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

            # 4. Export dashboard JSON + daily snapshot — BEFORE the heavy pickle/
            # parquet exports. MEMORY FIX (Jun 16 2026): the dashboard build
            # recomputes the momentum ranking across the whole universe; running
            # it AFTER export_pickle (695 MB decompressed) + export_parquet pushed
            # the worker to its 3008 MB cap, and under that pressure pandas
            # silently returned empty results → 0 buy_signals + 0 watchlist on the
            # Jun 15 first-live-entry scan (no exception, no OOM exit). Building
            # first — at ~2.3 GB with headroom — yields the correct set; the heavy
            # exports then run AFTER the decisions are already persisted. The cold
            # export_dashboard_cache path proved this (it produced the right 17).
            # See project_oom_scan_zero_jun15.
            import gc
            gc.collect()
            async with async_session() as db:
                data = await compute_shared_dashboard_data(db)

                # Safety alert — NOT a retry (Erik: no in-process reruns). With the
                # build now running pre-export with headroom, a 0-buy result on a
                # healthy non-bearish scan should no longer recur; if it does,
                # something new is wrong — surface it, don't paper over it.
                _raw_n = len(signals)
                _regime_now = (data.get('regime_forecast') or {}).get('current_regime', '')
                if not data.get('buy_signals') and _raw_n >= 10 and _regime_now not in ('weak_bear', 'panic_crash'):
                    print(f"⚠️ 0 buy_signals but raw scan had {_raw_n}, regime={_regime_now} — alerting admin (no retry)")
                    try:
                        from app.services.email_service import admin_email_service
                        await admin_email_service.send_admin_alert(
                            to_email="erik@rigacap.com",
                            subject="\U0001f6a8 RigaCap: 0 buy_signals despite healthy raw scan",
                            message=(f"Dashboard build returned 0 buy_signals; raw scan found {_raw_n}, "
                                     f"regime={_regime_now} (not bearish). The build now runs pre-export with "
                                     f"memory headroom, so this is NOT the OOM degradation — investigate the "
                                     f"signal pipeline (universe, near-high filter, DWAP)."),
                        )
                    except Exception as _ge:
                        print(f"⚠️ guard alert failed: {_ge}")
                dash_result = data_export_service.export_dashboard_json(data)
                # Use data_date (SPY's last bar date) or ET date — never UTC date.today()
                today_et = datetime.now(ZoneInfo('America/New_York')).date()
                today_str = data.get('data_date') or today_et.strftime("%Y-%m-%d")
                snap_result = data_export_service.export_snapshot(today_str, data)
            _log_step("Dashboard Export", "ok")

            # 5. Persist refreshed cache to S3 — SKIP in parquet (scoped) mode:
            # a partial cache would shrink/corrupt the full pickle+parquet stores.
            # Store freshness is handled separately during the migration. (Jun 17 2026)
            _parquet_mode = os.environ.get("PRICE_SOURCE", "pickle").lower() == "parquet"
            if _parquet_mode:
                print(f"📦 PRICE_SOURCE=parquet: skipping pickle/parquet export (scoped cache, {len(scanner_service.data_cache)} symbols)")
                export_result = {"success": True, "count": len(scanner_service.data_cache), "skipped": "parquet_mode"}
                pkl_ok = True; pkl_status = "ok"
                pkl_detail = f"skipped (parquet mode, {len(scanner_service.data_cache)} symbols)"
            else:
                export_result = data_export_service.export_pickle(scanner_service.data_cache)
                pkl_ok = export_result.get('success', True)
                pkl_status = "ok" if pkl_ok else "warning"
                pkl_detail = f"{export_result.get('count', 0)} symbols, {export_result.get('size_mb', '?')} MB"

                # 4b. SHADOW WRITE: parquet export (Parquet migration, Apr 2026).
                # Runs alongside pickle — pickle remains primary read path until
                # consumers are migrated. Any failure is logged but non-blocking.
                pq_result = {"success": False, "message": "not attempted"}
                try:
                    pq_result = data_export_service.export_parquet(scanner_service.data_cache)
                    if pq_result.get('success'):
                        print(f"📦 Shadow parquet: {pq_result['count']} symbols, {pq_result['size_mb']} MB")
                    else:
                        print(f"⚠️ Shadow parquet failed: {pq_result.get('message')}")
                except Exception as _e:
                    print(f"⚠️ Shadow parquet error (non-blocking): {_e}")
                    pq_result = {"success": False, "message": str(_e)[:200]}

                # 4c. PARALLEL-READ DIFF (Parquet migration Stage 3a, Apr 2026).
                # When PARQUET_PARALLEL_READ=true, compare pickle vs parquet and log
                # divergences to parquet_divergence_events. Gated behind env var so
                # it can be disabled instantly without redeploy. Wrapped in try/except
                # so it can NEVER break the daily scan — divergence logging is
                # observation only, not load-bearing. See project_parquet_stage3_plan.md.
                #
                # IMPORTANT: skip the diff if today's parquet export failed. The
                # diff would otherwise compare today's fresh pickle against
                # yesterday's stale parquet still in S3, false-positiving every
                # symbol with a 1-2 row delta (= the trading days yesterday's
                # pickle has that yesterday's parquet missed). Discovered May 8
                # 2026: a single EFAULT on the parquet upload generated 4597
                # row_count_diff events that triggered a Stage 3b 'pause' alarm.
                if not pq_result.get('success'):
                    print("⚠️ Skipping parquet diff harness — today's parquet export failed; "
                          "comparing against stale parquet would generate false-positive divergences.")
                elif os.environ.get("PARQUET_PARALLEL_READ", "").lower() in ("1", "true", "yes"):
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

            # (Dashboard build + snapshot moved ABOVE, before the pickle/parquet
            # exports — memory fix Jun 16 2026. See the block headed "# 4. Export
            # dashboard JSON". `data`, `today_str`, `today_et` are already defined.)

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
                # Always run BOTH steps — on zero-signal days the invalidation
                # is the important half (Jun 12 2026: the old `if buy_signals:`
                # gate skipped invalidation on empty days, leaving stale
                # 'active' rows that the email job then resurrected).
                async with async_session() as sig_db:
                    todays_syms = {s['symbol'] for s in data.get('buy_signals', [])}
                    if data.get('buy_signals'):
                        sig_result = await ensemble_signal_service.persist_signals(
                            sig_db, data['buy_signals'], today_et
                        )
                        persisted = sig_result['inserted']
                    await ensemble_signal_service.invalidate_stale_signals(
                        sig_db, today_et, todays_syms
                    )
                    print(f"📝 Persisted {persisted} ensemble signal(s); stale invalidation ran (today={len(todays_syms)})")
            except Exception as pe:
                print(f"⚠️ Signal persistence failed (non-fatal): {pe}")
            _log_step("Signal Persistence", "ok" if persisted > 0 or not data.get('buy_signals') else "warning",
                       f"{persisted} persisted")

            # 6b. Preserver SHADOW record (Phase 2) — ADDITIVE, records-only, NEVER served.
            # Fully isolated in try/except: it can never abort the live scan. Writes only to
            # the new preserver_* tables (migration preserver_shadow_tables.sql); the t30v
            # path above is untouched. Gated by PRESERVER_SHADOW env so it's a dark launch
            # until the migration is applied + we're ready to start the ~1wk shadow window.
            if os.getenv("PRESERVER_SHADOW", "").lower() in ("1", "true", "yes"):
                try:
                    from app.services.preserver_service import run_shadow_day
                    _regime = (data.get('regime_forecast') or {}).get('current_regime')
                    if _regime:
                        async with async_session() as _psh_db:
                            _psh = await run_shadow_day(
                                _psh_db, today_et, _regime,
                                data.get('buy_signals', []),
                                scanner_service.data_cache,
                            )
                        print(f"🕯️ Preserver shadow: {_psh}")
                    else:
                        print("🕯️ Preserver shadow skipped — no regime in dashboard data")
                except Exception as she:
                    print(f"⚠️ Preserver shadow failed (non-fatal, live scan unaffected): {she}")

            # 6c. Maximizer SHADOW record (Phase 2) — ADDITIVE, records-only, NEVER served.
            # Same isolation as the Preserver shadow above: fully wrapped in try/except (can
            # never abort the live scan), writes only to the new maximizer_* tables, t30v path
            # untouched. Gated by MAXIMIZER_SHADOW env (independent dark launch).
            if os.getenv("MAXIMIZER_SHADOW", "").lower() in ("1", "true", "yes"):
                try:
                    from app.services.maximizer_service import run_shadow_day as _run_max_shadow
                    _mregime = (data.get('regime_forecast') or {}).get('current_regime')
                    if _mregime:
                        async with async_session() as _msh_db:
                            _msh = await _run_max_shadow(
                                _msh_db, today_et, _mregime,
                                data.get('buy_signals', []),
                                scanner_service.data_cache,
                            )
                        print(f"🚀 Maximizer shadow: {_msh}")
                    else:
                        print("🚀 Maximizer shadow skipped — no regime in dashboard data")
                except Exception as mshe:
                    print(f"⚠️ Maximizer shadow failed (non-fatal, live scan unaffected): {mshe}")

            # Admin summary of the shadow tier books' activity today (Preserver + Maximizer).
            try:
                async with async_session() as _tb_db:
                    await _notify_tier_books(_tb_db)
            except Exception as _tbe:
                print(f"⚠️ Tier-book notify skipped (non-fatal): {_tbe}")

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
                        is_eod=True,
                    )
                    if exit_result:
                        print(f"📈 [MODEL-LIVE] EOD exits: {len(exit_result)} closed — {[c.get('symbol') for c in exit_result]}")
                        await _notify_portfolio_change("SELL", exit_result)

                # Circuit Breaker: count today's trailing-stop closures and
                # trigger CB pause if threshold (default 3 same-day) met.
                # No-op when CIRCUIT_BREAKER_ENABLED=false (default).
                try:
                    from app.services import circuit_breaker_state as cb
                    from datetime import date as _date
                    ts_symbols = [c.get("symbol") for c in (exit_result or []) if c.get("exit_reason") == "trailing_stop"]
                    if ts_symbols:
                        triggered = cb.record_eod_trailing_stops("live", _date.today(), ts_symbols)
                        if triggered:
                            print(f"🛑 [CB] Circuit breaker triggered for live: {triggered}")
                except Exception as cbe:
                    print(f"⚠️ CB record failed (non-fatal): {cbe}")
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
            # opened zero positions AND has free slots AND there's at least one fresh
            # signal that ISN'T already held. The "already held" check matters because
            # GOOG and GOOGL (or any signal where we already own the position) being
            # "fresh" but skipped is correct-by-design, not a broken pipeline.
            try:
                entries_opened = entry_result.get('entries', 0) if isinstance(entry_result, dict) else 0
                fresh_signals = [s for s in (data.get('buy_signals') or []) if s.get('is_fresh')]
                fresh_count = len(fresh_signals)
                if fresh_count > 0 and entries_opened == 0:
                    from sqlalchemy import select as _sel, func as _fn
                    from app.core.database import ModelPosition as _MP
                    async with async_session() as _cap_db:
                        open_positions = (await _cap_db.execute(
                            _sel(_MP.symbol).where(
                                _MP.portfolio_type == "live",
                                _MP.status == "open",
                            )
                        )).scalars().all()
                    open_count = len(open_positions)
                    held_symbols = {sym for sym in open_positions}
                    # Real broken-pipeline signal = at least one fresh signal we DON'T hold
                    actionable_fresh = [s for s in fresh_signals if s.get('symbol') not in held_symbols]
                    actionable_count = len(actionable_fresh)
                    # CB-aware: if the circuit breaker has paused entries, holding
                    # cash with actionable signals is EXPECTED behaviour, not a broken
                    # pipeline. Only flag Silent Cash when the CB is NOT the reason.
                    cb_paused = False
                    try:
                        from app.services.circuit_breaker_state import is_paused as _cb_is_paused
                        cb_paused = _cb_is_paused("live")
                    except Exception:
                        pass
                    if open_count < 20 and actionable_count > 0 and not cb_paused:
                        pipeline_failures.append((
                            "Silent Cash",
                            f"{actionable_count} actionable fresh signals (of {fresh_count} total), "
                            f"0 entries opened, {open_count}/20 positions held — entry pipeline may be silently broken. "
                            f"Skipped: {[s.get('symbol') for s in actionable_fresh]}"
                        ))
                    elif open_count < 20 and actionable_count > 0 and cb_paused:
                        print(f"🛡 Circuit breaker active — {actionable_count} fresh signal(s) correctly held back; cash position is expected, not a pipeline failure.")
            except Exception as _cde:
                print(f"⚠️ Silent-cash detector failed (non-fatal): {_cde}")

            # 7c. Signal track record: enter ALL fresh signals + check exits (regime-aware)
            #
            # STR is uncapped — every fresh signal enters, no 6-position constraint.
            # The circuit breaker concept (pause new entries after N same-day
            # stops) only makes sense for the constrained live portfolio. For
            # STR, same-day stop cascades are market noise across many
            # positions, not a signal-failure signal. CB recording/check
            # removed for STR (June 1 2026); CB remains active on `live`.
            try:
                from app.services.model_portfolio_service import model_portfolio_service, _get_regime_trailing_stop, SIGNAL_TRACK_RECORD
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

            # 9b. Chain PITFWU daily append (parquet mode — close-the-loop step 1).
            # Additive: keeps the per-symbol RAW store current so the read path can
            # move off the frozen all_data.parquet. Separate async invocation so it
            # adds no time/memory to the scan; can't affect signals.
            if os.environ.get("PRICE_SOURCE", "pickle").lower() == "parquet":
                try:
                    import boto3, json as _json
                    boto3.client('lambda', region_name='us-east-1').invoke(
                        FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                        InvocationType='Event',
                        Payload=_json.dumps({"pitfwu_append": True})
                    )
                    print("📈 Chained PITFWU daily append")
                except Exception as ce:
                    print(f"⚠️ Failed to chain PITFWU append (non-fatal): {ce}")

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

            # 11. Chain per-user portfolio recompute (async, separate Lambda)
            # Replays signals from each active subscriber's signup forward to
            # produce today's user_portfolio_state row. Powers the personalized
            # dashboard banner.
            try:
                import boto3, json as _json
                boto3.client('lambda', region_name='us-east-1').invoke(
                    FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                    InvocationType='Event',
                    Payload=_json.dumps({"user_portfolio_recompute": True})
                )
                print("📊 Chained user portfolio recompute")
            except Exception as ce:
                print(f"⚠️ Failed to chain user portfolio recompute: {ce}")
            _log_step("User Portfolio Recompute Chain", "ok", "async fire-and-forget")

            # Chain universe-history snapshot — captures today's full ranked
            # universe so future audits don't have to reconstruct it from the
            # pickle. Append-only, idempotent on re-invocation.
            # PARQUET MODE (Jun 23 2026): SKIP — data_cache holds only the scoped
            # ~603 symbols, so this would write a 603-symbol ranking that the
            # scoped LOAD then reads back to pick the top-600, ossifying the
            # universe (new liquid names never get discovered). The WEEKLY
            # `universe_refresh` job ranks the FULL universe from the parquet
            # instead. See project_oom_scan_zero_jun15 / parquet teething.
            try:
                import boto3, json as _json
                if os.environ.get("PRICE_SOURCE", "pickle").lower() == "parquet":
                    print("📚 Universe-history snapshot SKIPPED (parquet mode — weekly universe_refresh owns it)")
                else:
                    boto3.client('lambda', region_name='us-east-1').invoke(
                        FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                        InvocationType='Event',
                        Payload=_json.dumps({"universe_snapshot": {"_": 1}})
                    )
                    print("📚 Chained universe-history snapshot")
            except Exception as ce:
                print(f"⚠️ Failed to chain universe snapshot: {ce}")
            _log_step("Universe Snapshot Chain", "ok", "async fire-and-forget")

            # User-position EOD alert pass (Option C — May 18 2026).
            # Intraday monitor no longer emails warn/sell. Alerts fire only
            # here, on close-based trigger evaluation, matching WF parity.
            # One email per position per day max (dedup key omits action).
            try:
                from app.services.scheduler import scheduler_service as _sched
                from app.services.email_service import email_service as _es
                from app.core.database import Position as _Pos, User as _User
                from datetime import date as _today_d
                user_alert_count = 0
                async with async_session() as ua_db:
                    pos_q = await ua_db.execute(
                        select(_Pos, _User.email, _User.name)
                        .join(_User, _Pos.user_id == _User.id)
                        .where(_Pos.status == 'open')
                    )
                    today_d = _today_d.today().isoformat()
                    regime_forecast_for_ua = data.get("regime_forecast") if isinstance(data, dict) else None
                    regime_stop_pct_for_ua = _get_regime_trailing_stop(data) if isinstance(data, dict) else 12.0
                    for row in pos_q.all():
                        position, u_email, u_name = row
                        sym = position.symbol
                        df_sym = scanner_service.data_cache.get(sym)
                        if df_sym is None or df_sym.empty:
                            continue
                        close_price = float(df_sym['close'].iloc[-1])
                        # HWM update from close (matches Option B-shipped logic)
                        if close_price > (position.highest_price or position.entry_price):
                            position.highest_price = close_price
                        guidance_ua = _sched._check_sell_trigger(
                            position, close_price, regime_forecast_for_ua,
                            trailing_stop_pct=regime_stop_pct_for_ua or 12.0,
                        )
                        if not guidance_ua or guidance_ua['action'] not in ('sell', 'warning'):
                            continue
                        # Dedup by position+day (NOT action) so warn-then-sell
                        # in the same day fires ONE email, not two like the
                        # May 18 IONQ regression where warn fired at 9 AM and
                        # sell at 9:05 AM as price dropped further.
                        dedup_key = f"eod_{position.id}_{today_d}"
                        if dedup_key in _sched._alerted_sell_positions:
                            continue
                        try:
                            await _es.send_sell_alert(
                                to_email=u_email,
                                user_name=u_name or "",
                                symbol=sym,
                                action=guidance_ua['action'],
                                reason=guidance_ua['reason'],
                                current_price=close_price,
                                entry_price=position.entry_price,
                                stop_price=guidance_ua.get('stop_price'),
                                user_id=str(position.user_id),
                            )
                            _sched._alerted_sell_positions.add(dedup_key)
                            user_alert_count += 1
                        except Exception as ue:
                            print(f"⚠️ user-position EOD alert failed for {sym}: {ue}")
                    await ua_db.commit()
                print(f"📧 User-position EOD alerts: {user_alert_count} sent")
                _log_step("User Position EOD Alerts", "ok", f"{user_alert_count} sent")
            except Exception as ue_outer:
                print(f"⚠️ User-position EOD pass failed (non-fatal): {ue_outer}")
                _log_step("User Position EOD Alerts", "error", str(ue_outer)[:120])

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
            result = _run_async(_run_daily_scan(lambda_context=context))
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

    # [BACKFILL] Rebuild a past day's snapshot from the CURRENT cache truncated
    # to that date (so iloc[-1] == that day's bar, via the real production build).
    # Fixes Jun-15's snapshot (buy_signals=0, a scan bug) so the market-context
    # day-over-day read sees the real 17, not a phantom zero. Writes ONLY the one
    # snapshot, then clears the (truncated) cache so the next invocation reloads
    # fresh. Temporary — Jun 16 2026.
    if event.get("rebuild_snapshot"):
        _cfg = event.get("rebuild_snapshot") or {}
        _target = _cfg.get("date")
        print(f"🧩 Rebuild snapshot for {_target} (truncate cache -> build -> write snapshot)")
        async def _rebuild_snap():
            import pandas as _pd
            from app.api.signals import compute_shared_dashboard_data
            from app.services.data_export import data_export_service
            cutoff = _pd.Timestamp(_target).normalize()
            trunc = 0
            for _s, _df in list(scanner_service.data_cache.items()):
                if _df is None or len(_df) == 0:
                    continue
                _c = cutoff.tz_localize(_df.index.tz) if (hasattr(_df.index, 'tz') and _df.index.tz is not None) else cutoff
                if _df.index.max() > _c:
                    scanner_service.data_cache[_s] = _df[_df.index <= _c]
                    trunc += 1
            print(f"   truncated {trunc} symbols to <= {_target}")
            async with async_session() as db:
                data = await compute_shared_dashboard_data(db)
            n = len(data.get('buy_signals', []))
            snap = data_export_service.export_snapshot(_target, data)
            scanner_service.data_cache = {}  # force fresh reload next invocation
            return {"date": _target, "buy_signals": n,
                    "symbols": [s['symbol'] for s in data.get('buy_signals', [])], "snapshot": snap}
        try:
            result = _run_async(_rebuild_snap())
            print(f"🧩 Rebuild snapshot result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ rebuild_snapshot failed: {e}\n{traceback.format_exc()}")
            return {"error": str(e)}

    # [DIAG] Safe reproduction of the in-pipeline 0-signal bug: run scan() (sets
    # market_state, processes the cache — the condition the cold path skips) then
    # the dashboard build, emitting the [DASH-DIAG] gate counts. Writes NOTHING
    # (no pickle, no dashboard.json, no entries). Temporary — Jun 16 2026.
    if event.get("diag_scan_build"):
        _dcfg = event.get("diag_scan_build")
        _do_fetch = isinstance(_dcfg, dict) and _dcfg.get("fetch")
        print(f"🔬 DIAG: scan+build, no writes — tracing the 0-signal gate (fetch={_do_fetch})")
        async def _diag_scan_build():
            import numpy as _np
            from app.services.strategy_analyzer import get_top_liquid_symbols as _gtl
            def _lenstats(tag):
                items = [(s, d) for s, d in scanner_service.data_cache.items() if d is not None]
                lens = [len(d) for _, d in items]
                ge200 = sum(1 for l in lens if l >= 200)
                uni = len(_gtl(max_symbols=100))
                ex = [(s, len(d), round(float(d['close'].iloc[-1]), 2)) for s, d in items[:4]]
                print(f"[LEN-DIAG] {tag}: n={len(lens)} ge200={ge200} lt200={len(lens)-ge200} "
                      f"min={min(lens) if lens else 0} median={int(_np.median(lens)) if lens else 0} "
                      f"top_liquid_universe={uni} ex={ex}")
            _lenstats("after scoped load")
            if _do_fetch:
                r = await scanner_service.fetch_incremental(replace_days=0)
                print(f"[LEN-DIAG] fetch result: {r}")
                _lenstats("after fetch")
            sigs = await scanner_service.scan(refresh_data=False)
            print(f"[DASH-DIAG] scan() raw signals={len(sigs)}")
            _lenstats("after scan()")
            from app.api.signals import compute_shared_dashboard_data
            async with async_session() as db:
                data = await compute_shared_dashboard_data(db)
            return {"raw_signals": len(sigs),
                    "buy_signals": len(data.get('buy_signals', [])),
                    "watchlist": len(data.get('watchlist', []))}
        try:
            result = _run_async(_diag_scan_build())
            print(f"🔬 DIAG result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ DIAG failed: {e}\n{traceback.format_exc()}")
            return {"error": str(e)}

    if event.get("calendar_audit"):
        # READ-ONLY completeness check for the split calendar. The danger (ASST class):
        # a real split MISSING from our calendar on a symbol whose stored bars SPAN the
        # ex-date -> split_adjusted() is a no-op -> the served series has an unadjusted
        # step at the split -> phantom momentum. Pulls Alpaca's authoritative splits for
        # the live scoped universe, diffs vs our calendar, and flags only the missing ones
        # our PITFWU bars actually span (before AND after the ex-date). Writes nothing.
        cfg = event.get("calendar_audit") or {}
        years = int(cfg.get("years", 6)) if isinstance(cfg, dict) else 6
        topn = int(cfg.get("topn", 600)) if isinstance(cfg, dict) else 600
        print(f"🔍 CALENDAR AUDIT (read-only) — Alpaca splits vs calendar, top {topn}, {years}y")
        def _calendar_audit():
            import pandas as _pd, json as _json, boto3
            from datetime import date as _date, timedelta as _td
            from alpaca.data.historical.corporate_actions import CorporateActionsClient
            from alpaca.data.requests import CorporateActionsRequest
            from app.services.data_export import S3_BUCKET
            from app.services import pitfwu_store as ps
            from app.core.config import settings as _cfg
            s3 = boto3.client('s3', region_name='us-east-1')
            objs = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix='signals/universe-history/')
            keys = sorted(o['Key'] for o in objs.get('Contents', []) if o['Key'].endswith('.json'))
            syms = []
            if keys:
                uni = _json.loads(s3.get_object(Bucket=S3_BUCKET, Key=keys[-1])['Body'].read())
                for r in uni.get('rankings', []):
                    if len(syms) >= topn:
                        break
                    if not r.get('is_excluded') and r.get('symbol'):
                        syms.append(r['symbol'])
            cal = ps.load_corp_actions()
            cal_dates = {}
            if cal is not None and not cal.empty:
                sub = cal[cal['type'].isin(['forward_splits', 'reverse_splits'])].copy()
                sub['d'] = _pd.to_datetime(sub['date'], errors='coerce').dt.strftime('%Y-%m-%d')
                for sy, grp in sub.groupby('symbol'):
                    cal_dates[sy] = set(grp['d'].dropna())
            client = CorporateActionsClient(api_key=_cfg.ALPACA_API_KEY, secret_key=_cfg.ALPACA_SECRET_KEY)
            start, end = _date.today() - _td(days=365 * years + 30), _date.today()
            missing, alpaca_splits = [], 0
            BATCH = 50
            for i in range(0, len(syms), BATCH):
                chunk = syms[i:i + BATCH]
                try:
                    res = client.get_corporate_actions(CorporateActionsRequest(symbols=chunk, start=start, end=end))
                    data = getattr(res, 'data', {}) or {}
                    for atype, actions in data.items():
                        if atype not in ('forward_splits', 'reverse_splits'):
                            continue
                        for a in (actions or []):
                            ad = getattr(a, 'model_dump', lambda: dict(a))()
                            sym = ad.get('symbol')
                            exd = ad.get('ex_date') or ad.get('process_date') or ad.get('effective_date')
                            old, new = ad.get('old_rate'), ad.get('new_rate')
                            if not (sym and exd and old and new):
                                continue
                            alpaca_splits += 1
                            exs = _pd.Timestamp(exd).strftime('%Y-%m-%d')
                            if exs not in cal_dates.get(sym, set()):
                                missing.append({'symbol': sym, 'ex_date': exs, 'type': atype,
                                                'ratio': round(float(new) / float(old), 4)})
                except Exception as e:
                    print(f"audit batch {i // BATCH} failed: {str(e)[:150]}")
            # DANGER: our stored bars span a MISSING split's ex-date (before AND after)
            dangerous = []
            for m in missing:
                df = ps._read_pitfwu_bars(m['symbol'])
                if df is None or df.empty:
                    m['span'] = 'no_bars'
                    continue
                ex = _pd.Timestamp(m['ex_date'])
                before, after = bool((df.index < ex).any()), bool((df.index >= ex).any())
                m['span'] = 'SPANS' if (before and after) else ('after_only' if after else 'before_only')
                if before and after:
                    dangerous.append(m)
            return {'universe_checked': len(syms), 'alpaca_splits_seen': alpaca_splits,
                    'missing_count': len(missing), 'dangerous_count': len(dangerous),
                    'dangerous': dangerous, 'missing_sample': missing[:50]}
        try:
            r = _calendar_audit()
            print(f"🔍 audit: alpaca_splits={r['alpaca_splits_seen']} missing={r['missing_count']} DANGEROUS={r['dangerous_count']}")
            return r
        except Exception as e:
            import traceback
            print(f"❌ calendar_audit failed: {e}\n{traceback.format_exc()}")
            return {'error': str(e)}

    if event.get("maximizer_preview"):
        # READ-ONLY prediction of the Maximizer book's next breakout entries. The breakout
        # sleeve ONLY feeds the book in the rotating_bull regime (route()); in every other
        # regime build_daily_signals returns a non-breakout source and the book adds nothing.
        # Reports: current regime, active sleeve, breakout entries FIRING on today's close
        # (the best read on tomorrow's scan), and the radar of names APPROACHING a trigger.
        # Writes/sends nothing.
        print("🔭 MAXIMIZER BREAKOUT PREVIEW (read-only)")
        async def _max_preview():
            from app.services.market_regime import market_regime_service
            from app.services.maximizer_signal_service import build_daily_signals
            from app.services.maximizer_sleeves import route
            from app.services import tier_serving as _ts
            from app.core.database import MaximizerBookSnapshot as _MBS
            from app.core.timezone import trading_today
            cache = scanner_service.data_cache
            spy = cache.get('SPY'); vix = cache.get('^VIX')
            reg = market_regime_service.detect_regime(spy_df=spy, universe_dfs=cache, vix_df=vix)
            regime = reg.regime_type.value
            src = route(regime)
            today = trading_today()
            async with async_session() as db:
                snap = (await db.execute(select(_MBS).order_by(_MBS.snapshot_date.desc()).limit(1))).scalars().first()
            held = set()
            if snap and isinstance(snap.positions_json, dict):
                held = {p.get('symbol') for p in (snap.positions_json.get('positions') or []) if p.get('symbol')}
            _src, cands = build_daily_signals(cache, regime, [], today, max_positions=15)
            firing = ([{**c, 'already_held': c['symbol'] in held} for c in cands]
                      if _src == 'breakout' else [])
            radar = _ts.build_breakout_radar(cache, held)
            data_date = str(spy.index[-1].date()) if spy is not None and len(spy) else None
            return {'data_date': data_date, 'regime': regime, 'regime_name': reg.regime_name,
                    'active_sleeve': src, 'breakout_sleeve_active': src == 'breakout',
                    'breakout_firing_count': len(firing), 'breakout_firing': firing,
                    'radar_approaching_count': len(radar), 'radar_approaching': radar,
                    'held_count': len(held)}
        try:
            r = _run_async(_max_preview())
            print(f"🔭 maximizer_preview: regime={r.get('regime')} sleeve={r.get('active_sleeve')} "
                  f"firing={r.get('breakout_firing_count')} radar={r.get('radar_approaching_count')}")
            return r
        except Exception as e:
            import traceback
            print(f"❌ maximizer_preview failed: {e}\n{traceback.format_exc()}")
            return {'error': str(e)}

    if event.get("sector_rotation_study"):
        # READ-ONLY sector-rotation observatory + predictability test over full history.
        # Reuses the backtester's FAITHFUL per-sector median-return classifier
        # (_compute_sector_medians) and the 7-regime overlay (_get_regime_for, point-in-time
        # via as_of_date). Writes NOTHING to the book. Answers: how does sector leadership
        # rotate (esp. under Rotating Bull), does it PERSIST or REVERT, and do leading
        # indicators (RS acceleration / within-sector breadth) PRECEDE the RS-level turn —
        # i.e. is the NEXT hot sector forecastable at all. Full monthly series → S3 for charting.
        _cfg = event.get("sector_rotation_study")
        _cfg = _cfg if isinstance(_cfg, dict) else {}
        print(f"🧭 SECTOR ROTATION STUDY (read-only) cfg={_cfg}")

        def _sector_study():
            import os as _os, json as _json, boto3 as _b3
            from collections import Counter as _Counter
            from app.services.backtester import BacktesterService
            from app.services.data_export import data_export_service as _dex

            rs_lookback = int(_cfg.get("rs_lookback", 63))      # ~1 quarter sector momentum
            step_days = int(_cfg.get("step_days", 21))          # ~monthly grid
            breadth_ma = int(_cfg.get("breadth_ma", 50))
            min_names = int(_cfg.get("min_names_per_sector", 5))

            # 1) Warm the FULL universe cache (need every sector well-represented for breadth).
            if not scanner_service.data_cache:
                scanner_service.data_cache = _dex.import_all() or {}
            cache = scanner_service.data_cache
            spy = cache.get("SPY")
            if spy is None or len(spy) < 300:
                return {"error": "no SPY / insufficient history"}

            # 2) Sector map from S3 (yfinance .info sectors).
            _s3 = _b3.client("s3", region_name="us-east-1")
            _bkt = _os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
            _sec_raw = _json.loads(_s3.get_object(Bucket=_bkt, Key="universe/sectors_cache.json")["Body"].read())
            symbol_sectors = {s: d.get("sector") for s, d in _sec_raw.items()
                              if isinstance(d, dict) and d.get("sector")}
            sectors = sorted(set(symbol_sectors.values()))

            # 3) Backtester as the faithful sector/regime engine.
            bt = BacktesterService()
            bt.symbol_sectors = symbol_sectors
            bt.sector_rs_lookback_days = rs_lookback

            # 4) ~Monthly date grid over SPY history (need lookback + 250 bars for regime/MA).
            spy_idx = spy.index
            start_i = max(rs_lookback + 5, 250)
            dates = [spy_idx[i] for i in range(start_i, len(spy_idx), step_days)]

            # 4b) WEEKLY regime band FIRST, chronologically (hysteresis is built for fine steps;
            # monthly sampling misses fast crashes like COVID's ~5-week V — the panic bottoms
            # BETWEEN two monthly snapshots). Compute weekly, then derive each month's regime as
            # the most recent weekly reading so the ribbon AND the diagnostics stay consistent.
            import bisect as _bisect
            regime_step = int(_cfg.get("regime_step_days", 5))   # ~weekly
            regime_weekly = []
            for i in range(start_i, len(spy_idx), regime_step):
                dt = spy_idx[i]
                try:
                    rg = bt._get_regime_for(dt)                  # chronological order → hysteresis OK
                except Exception:
                    rg = None
                regime_weekly.append({"date": dt.strftime("%Y-%m-%d"), "regime": rg})
            _wk_dates = [w["date"] for w in regime_weekly]
            def _regime_asof(dstr):
                j = _bisect.bisect_right(_wk_dates, dstr) - 1
                return regime_weekly[j]["regime"] if j >= 0 else None

            series = []
            for dt in dates:
                medians = bt._compute_sector_medians(dt)          # {sector: median N-day ret} (faithful)
                regime = _regime_asof(dt.strftime("%Y-%m-%d"))    # weekly reading as-of this month
                # within-sector breadth: % of a sector's symbols above their breadth_ma MA
                above = {s: 0 for s in sectors}; total = {s: 0 for s in sectors}
                for sym, df in cache.items():
                    sec = symbol_sectors.get(sym)
                    if not sec:
                        continue
                    row = bt._get_row_for_date(df, dt)
                    if row is None:
                        continue
                    try:
                        idx = df.index.get_loc(row.name)
                    except (KeyError, TypeError):
                        continue
                    if idx < breadth_ma:
                        continue
                    ma = float(df['close'].iloc[idx - breadth_ma + 1: idx + 1].mean())
                    total[sec] += 1
                    if float(row['close']) > ma:
                        above[sec] += 1
                breadth = {s: (round(above[s] / total[s], 4) if total[s] >= min_names else None) for s in sectors}
                series.append({
                    "date": dt.strftime("%Y-%m-%d"), "regime": regime,
                    "median_ret": {s: (round(medians[s], 5) if s in medians else None) for s in sectors},
                    "breadth": breadth, "n": {s: total[s] for s in sectors},
                })

            # ---- Diagnostics (the predictability lens) ----
            def _rank(d):  # 1 = strongest median return that date
                vals = sorted([(s, d[s]) for s in sectors if d.get(s) is not None],
                              key=lambda kv: kv[1], reverse=True)
                return {s: i + 1 for i, (s, _v) in enumerate(vals)}
            ranks = [_rank(r["median_ret"]) for r in series]

            def _pearson(xs, ys):
                n = len(xs)
                if n < 4:
                    return None
                mx = sum(xs) / n; my = sum(ys) / n
                cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
                vx = sum((a - mx) ** 2 for a in xs) ** 0.5
                vy = sum((b - my) ** 2 for b in ys) ** 0.5
                return round(cov / (vx * vy), 3) if vx and vy else None

            # (a) Persistence: mean Spearman rank-autocorr of sector strength at horizons.
            persistence = {}
            for h in (1, 3, 6, 12):
                cs = []
                for t in range(len(ranks) - h):
                    keys = [k for k in ranks[t] if k in ranks[t + h]]
                    if len(keys) >= 4:
                        c = _pearson([ranks[t][k] for k in keys], [ranks[t + h][k] for k in keys])
                        if c is not None:
                            cs.append(c)
                persistence[f"{h}m"] = round(sum(cs) / len(cs), 3) if cs else None

            # (b) Leading indicators: does indicator_t predict forward rank IMPROVEMENT
            #     (rank_t − rank_{t+fwd}, +ve = climbed)? Cross-sectional over all sector-dates.
            def _lead_corr(ind_fn, fwd):
                xs, ys = [], []
                for t in range(1, len(series) - fwd):
                    for s in sectors:
                        v = ind_fn(t, s)
                        if v is None or s not in ranks[t] or s not in ranks[t + fwd]:
                            continue
                        xs.append(v); ys.append(ranks[t][s] - ranks[t + fwd][s])
                return _pearson(xs, ys) if len(xs) >= 30 else None
            _accel = lambda t, s: (None if series[t]["median_ret"].get(s) is None or series[t - 1]["median_ret"].get(s) is None
                                   else series[t]["median_ret"][s] - series[t - 1]["median_ret"][s])
            _breadth = lambda t, s: series[t]["breadth"].get(s)
            _level = lambda t, s: series[t]["median_ret"].get(s)
            leading = {}
            for fwd in (1, 3):
                leading[f"accel_to_fwd{fwd}m"] = _lead_corr(_accel, fwd)
                leading[f"breadth_to_fwd{fwd}m"] = _lead_corr(_breadth, fwd)
                leading[f"level_to_fwd{fwd}m"] = _lead_corr(_level, fwd)

            # (c) Rotation cadence: stickiness of the #1 sector.
            leaders = [min(r, key=r.get) if r else None for r in ranks]
            spans = len([l for l in leaders if l])
            switches = sum(1 for i in range(1, len(leaders)) if leaders[i] and leaders[i - 1] and leaders[i] != leaders[i - 1])
            lc = _Counter([l for l in leaders if l])
            cadence = {"avg_months_leader_holds": round(spans / max(1, switches), 2),
                       "distinct_leaders": len(lc),
                       "leader_share": {k: round(v / max(1, spans), 3) for k, v in lc.most_common()}}

            # (d) Regime-conditioned leaders (esp. rotating_bull).
            by_regime = {}
            for r, lead in zip(series, leaders):
                if r["regime"] and lead:
                    by_regime.setdefault(r["regime"], _Counter())[lead] += 1
            regime_leaders = {reg: {"n": sum(c.values()), "top": c.most_common(3)} for reg, c in by_regime.items()}

            # (e) Secular drift: slope of each sector's rank over time (negative = climbing).
            drift = {}
            for s in sectors:
                pts = [(i, ranks[i][s]) for i in range(len(ranks)) if s in ranks[i]]
                if len(pts) >= 12:
                    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
                    den = sum((x - mx) ** 2 for x in xs)
                    drift[s] = round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den, 4) if den else 0.0

            # (f) CLEAN mean-reversion / momentum test — bounded-rank-free.
            # Rank sectors by CURRENT trailing strength, then measure each group's ACTUAL
            # FORWARD median return over h months. spread = top-K fwd − bottom-K fwd:
            #   spread > 0 = momentum (strong keep winning); < 0 = mean-reversion (weak catch up).
            # Plus a FRESH cross-sectional corr (rank-now vs rank-by-forward-return), which
            # has no leader-ceiling artifact. Precompute each symbol's close at every grid date.
            import statistics as _stat
            closes = {}   # sym -> (sector, [close at each grid date or None])
            for sym, df in cache.items():
                sec = symbol_sectors.get(sym)
                if not sec:
                    continue
                arr = []
                for dt in dates:
                    row = bt._get_row_for_date(df, dt)
                    arr.append(float(row['close']) if row is not None else None)
                closes[sym] = (sec, arr)

            def _sector_fwd(gi, h):   # {sector: median forward return over h grid-steps}
                buckets = {}
                for _sym, (sec, arr) in closes.items():
                    if gi + h >= len(arr):
                        continue
                    c0, c1 = arr[gi], arr[gi + h]
                    if c0 and c1 and c0 > 0:
                        buckets.setdefault(sec, []).append(c1 / c0 - 1.0)
                return {s: _stat.median(v) for s, v in buckets.items() if len(v) >= min_names}

            def _agg(xs):
                if len(xs) < 4:
                    return None
                mu = sum(xs) / len(xs)
                sd = (sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
                se = sd / len(xs) ** 0.5
                return {"mean_spread_pct": round(mu * 100, 2),
                        "t_stat": round(mu / se, 2) if se else None,
                        "n": len(xs), "reversion_rate": round(sum(1 for x in xs if x < 0) / len(xs), 2)}

            K = int(_cfg.get("spread_k", 3))
            mean_rev = {}
            for h in (1, 3, 6):
                spreads, spreads_rb, spear = [], [], []
                for gi in range(len(dates) - h):
                    strength = series[gi]["median_ret"]
                    ranked = sorted([s for s in sectors if strength.get(s) is not None],
                                    key=lambda s: strength[s], reverse=True)
                    if len(ranked) < 2 * K:
                        continue
                    fwd = _sector_fwd(gi, h)
                    top = [s for s in ranked[:K] if s in fwd]
                    bot = [s for s in ranked[-K:] if s in fwd]
                    if len(top) >= 2 and len(bot) >= 2:
                        sp = sum(fwd[s] for s in top) / len(top) - sum(fwd[s] for s in bot) / len(bot)
                        spreads.append(sp)
                        if series[gi]["regime"] == "rotating_bull":
                            spreads_rb.append(sp)
                    common = [s for s in ranked if s in fwd]
                    if len(common) >= 5:
                        xr = {s: i + 1 for i, s in enumerate(common)}            # 1 = strongest NOW
                        ys = sorted(common, key=lambda s: fwd[s], reverse=True)
                        yr = {s: i + 1 for i, s in enumerate(ys)}                # 1 = best FORWARD
                        c = _pearson([xr[s] for s in common], [yr[s] for s in common])
                        if c is not None:
                            spear.append(c)
                mean_rev[f"{h}m"] = {"all": _agg(spreads), "rotating_bull": _agg(spreads_rb),
                                     "corr_now_vs_forward": round(sum(spear) / len(spear), 3) if spear else None}

            out = {
                "params": {"rs_lookback": rs_lookback, "step_days": step_days, "breadth_ma": breadth_ma,
                           "dates": len(series), "first": series[0]["date"] if series else None,
                           "last": series[-1]["date"] if series else None, "sectors": sectors},
                "persistence_spearman": persistence,
                "leading_indicator_corr": leading,
                "rotation_cadence": cadence,
                "regime_leaders": regime_leaders,
                "secular_drift_rank_slope": drift,
                "mean_reversion_spread": mean_rev,
                "regime_weekly": regime_weekly,
            }
            try:
                _s3.put_object(Bucket=_bkt, Key="research/sector_rotation_study.json",
                               Body=_json.dumps({"summary": out, "series": series}), ContentType="application/json")
                out["s3"] = f"s3://{_bkt}/research/sector_rotation_study.json"
            except Exception as _e:
                out["s3_error"] = str(_e)[:200]
            return out

        try:
            _r = _sector_study()
            print(f"🧭 sector_rotation_study done: {_r.get('params', {}).get('dates')} dates, "
                  f"persistence={_r.get('persistence_spearman')}, leading={_r.get('leading_indicator_corr')}")
            return _r
        except Exception as e:
            import traceback
            print(f"❌ sector_rotation_study failed: {e}\n{traceback.format_exc()}")
            return {"status": "error", "error": str(e)}

    if event.get("scan_preview"):
        # READ-ONLY preview of what the NEXT daily scan will surface, on the CURRENT
        # (fresh) universe snapshot. Runs the same scan()+compute_shared_dashboard_data
        # path but writes/sends NOTHING. Returns the candidate symbols PLUS a per-symbol
        # data-freshness check (last bar date, price, dwap ratio, is_series_tradeable) so
        # we can eyeball for ASST-style stale/mis-adjusted names BEFORE the automated send.
        _pcfg = event.get("scan_preview") or {}
        _pf = bool(_pcfg.get("fetch")) if isinstance(_pcfg, dict) else False
        print(f"🔭 SCAN PREVIEW (read-only, fetch={_pf}) — next scan's candidates on the fresh universe")
        async def _scan_preview():
            import pandas as _pd
            from app.services.scanner import is_series_tradeable, _universe_stale_cutoff
            if _pf:
                r = await scanner_service.fetch_incremental(replace_days=0)
                print(f"[PREVIEW] fetch: {r}")
            await scanner_service.scan(refresh_data=False)
            from app.api.signals import compute_shared_dashboard_data
            async with async_session() as db:
                data = await compute_shared_dashboard_data(db)
            cache = scanner_service.data_cache
            _cut = _universe_stale_cutoff(cache)
            def _sym(x):
                return x.get('symbol') if isinstance(x, dict) else x
            def _fresh(sym):
                df = cache.get(sym)
                if df is None or not len(df):
                    return {'symbol': sym, 'in_cache': False}
                row = df.iloc[-1]
                px = float(row.get('close', 0) or 0)
                dwap = row.get('dwap')
                dwap = float(dwap) if dwap is not None and not _pd.isna(dwap) and float(dwap) > 0 else None
                return {'symbol': sym, 'in_cache': True, 'bars': int(len(df)),
                        'last_date': str(_pd.Timestamp(df.index[-1]).date()),
                        'price': round(px, 2), 'dwap': round(dwap, 2) if dwap else None,
                        'px_dwap': round(px / dwap, 2) if dwap else None,
                        'tradeable': bool(is_series_tradeable(df, _cut))}
            buys = data.get('buy_signals', []) or []
            watch = data.get('watchlist', []) or []
            buy_syms = [_sym(x) for x in buys]
            watch_syms = [_sym(x) for x in watch]
            checks = {s: _fresh(s) for s in (buy_syms + watch_syms)}
            suspicious = [c for c in checks.values()
                          if not c.get('tradeable', True)
                          or (c.get('last_date') and c['last_date'] < str(_cut.date()))]
            return {'buy_count': len(buys), 'watch_count': len(watch),
                    'stale_cutoff': str(_cut.date()),
                    'buy_symbols': buy_syms, 'watch_symbols': watch_syms[:50],
                    'buy_freshness': [checks[s] for s in buy_syms],
                    'suspicious_count': len(suspicious), 'suspicious': suspicious}
        try:
            result = _run_async(_scan_preview())
            print(f"🔭 preview: buys={result.get('buy_count')} watch={result.get('watch_count')} "
                  f"suspicious={result.get('suspicious_count')}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ scan_preview failed: {e}\n{traceback.format_exc()}")
            return {"error": str(e)}

    # Handle dashboard cache export
    if event.get("patch_breakout_radar"):
        # Surgical: compute ONLY the Maximizer breakout radar and splice it into the EXISTING
        # dashboard.json — signals + market reads left byte-for-byte untouched. Lets us light up
        # the radar without a full scan / read regeneration.
        print("🎯 Patching breakout_radar into dashboard.json (reads/signals untouched)")
        async def _patch_radar():
            import json as _json, boto3
            from app.services.data_export import data_export_service
            from app.services import tier_serving
            from app.core.database import MaximizerBookSnapshot
            if 'SPY' not in scanner_service.data_cache:
                _c = data_export_service.import_all()
                if _c:
                    scanner_service.data_cache = _c
            held = set()
            async with async_session() as db:
                snap = (await db.execute(
                    select(MaximizerBookSnapshot).order_by(MaximizerBookSnapshot.snapshot_date.desc()).limit(1)
                )).scalars().first()
                if snap and isinstance(snap.positions_json, dict):
                    held = {p.get("symbol") for p in (snap.positions_json.get("positions") or []) if p.get("symbol")}
            radar = tier_serving.build_breakout_radar(scanner_service.data_cache, held)
            dash = data_export_service.read_dashboard_json() or {}
            _s3 = boto3.client('s3', region_name='us-east-1')
            _bucket = "rigacap-prod-price-data-149218244179"
            # Back up the CURRENT dashboard.json (exact bytes) BEFORE overwriting. Abort if the
            # backup fails. Restore = copy backup_key back to signals/dashboard.json.
            from datetime import datetime as _dt
            _bak = f"signals/backups/dashboard.json.bak-{_dt.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
            try:
                _s3.copy_object(Bucket=_bucket, Key=_bak,
                                CopySource={'Bucket': _bucket, 'Key': 'signals/dashboard.json'})
            except Exception as _be:
                return {"status": "failed", "error": f"backup failed, patch aborted: {_be}"}
            dash['breakout_radar'] = radar
            _s3.put_object(Bucket=_bucket, Key='signals/dashboard.json',
                           Body=_json.dumps(dash).encode(), ContentType='application/json')
            return {"status": "success", "radar_count": len(radar),
                    "sample": [r.get("symbol") for r in radar[:8]], "held_excluded": len(held),
                    "market_context_preserved": bool(dash.get('market_context')),
                    "backup_key": _bak}
        try:
            return _run_async(_patch_radar())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "tb": traceback.format_exc()[:1200]}

    if event.get("export_dashboard_cache"):
        print("📦 Dashboard cache export requested")
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
                    # Always invalidate, even on zero-signal days (Jun 12 2026 fix)
                    async with async_session() as sig_db:
                        todays_syms = {s['symbol'] for s in data.get('buy_signals', [])}
                        if data.get('buy_signals'):
                            sig_result = await ensemble_signal_service.persist_signals(
                                sig_db, data['buy_signals'], today_et
                            )
                            result["ensemble_signals_persisted"] = sig_result['inserted']
                            print(f"📝 Persisted {sig_result['inserted']} ensemble signal(s)")
                        await ensemble_signal_service.invalidate_stale_signals(
                            sig_db, today_et, todays_syms
                        )
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

                # Chain the daily book snapshot (Mirror day-over-day diff) — process_entries above
                # has finalized the live Preserver book, so the snapshot captures today's book.
                try:
                    import boto3, json as _json
                    boto3.client('lambda', region_name='us-east-1').invoke(
                        FunctionName=os.environ.get('WORKER_FUNCTION_NAME', 'rigacap-prod-worker'),
                        InvocationType='Event',
                        Payload=_json.dumps({"snapshot_book": True})
                    )
                    print("🌒 Chained book snapshot")
                except Exception as ce:
                    print(f"⚠️ Failed to chain book snapshot (non-fatal): {ce}")

            return result

        try:
            result = _run_async(_export_dashboard())
            print(f"📦 Dashboard cache export: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Dashboard cache export failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Daily book snapshot — a tiny rolling history of the model book's SYMBOLS (per tier) so the
    # Mirror cockpit can diff day-over-day ("the book entered OKTA / exited AAPL today") and chart
    # alignment drift over time. Pure DB reads (ModelPosition live/open = Preserver; latest
    # MaximizerBookSnapshot = breakout) — no data_cache, safe on a cold worker. Idempotent:
    # dedupes by date, so re-running (or a manual backfill invoke) is harmless.
    if event.get("snapshot_book"):
        print("🌒 Book snapshot requested")
        async def _snapshot_book():
            from app.core.database import MaximizerBookSnapshot, ModelPosition
            from app.services.data_export import data_export_service
            from datetime import datetime, timezone
            from zoneinfo import ZoneInfo
            async with async_session() as db:
                prows = (await db.execute(
                    select(ModelPosition).where(
                        ModelPosition.portfolio_type == "live",
                        ModelPosition.status == "open")
                )).scalars().all()
                preserver = sorted({(r.symbol or "").upper() for r in prows if r.symbol})
                msnap = (await db.execute(
                    select(MaximizerBookSnapshot).order_by(
                        MaximizerBookSnapshot.snapshot_date.desc()).limit(1)
                )).scalars().first()
                maximizer = []
                if msnap and isinstance(msnap.positions_json, dict):
                    maximizer = sorted({
                        (p.get("symbol") or "").upper()
                        for p in (msnap.positions_json.get("positions") or [])
                        if p.get("symbol")})
            today_str = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
            doc = data_export_service.read_json("mirror/book_history.json") or {}
            history = [h for h in (doc.get("history") or []) if h.get("date") != today_str]
            history.append({"date": today_str, "preserver": preserver, "maximizer": maximizer})
            history.sort(key=lambda h: h.get("date") or "")
            history = history[-120:]   # ~4 trading-months of daily book states
            out = {"updated_at": datetime.now(timezone.utc).isoformat(), "history": history}
            data_export_service.write_json("mirror/book_history.json", out)
            return {"status": "success", "date": today_str,
                    "preserver": len(preserver), "maximizer": len(maximizer),
                    "days_tracked": len(history)}
        try:
            result = _run_async(_snapshot_book())
            print(f"🌒 Book snapshot: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Book snapshot failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle pickle rebuild after daily scan (deferred from scan due to time constraints)
    # Fresh Lambda = fresh 900s budget. Two phases:
    #   Phase 1: incremental fetch + stream pickle to /tmp → S3 (avoids OOM from in-memory serialize)
    #   Phase 2: export individual CSVs (chained as separate invocation)
    if event.get("pickle_rebuild_from_scan"):
        # Obsolete in parquet mode (see pickle_rebuild guard above) — skip.
        if os.environ.get("PRICE_SOURCE", "pickle").lower() == "parquet":
            print("⏭️ pickle_rebuild_from_scan skipped — PRICE_SOURCE=parquet")
            return {"status": "skipped", "reason": "parquet_mode"}
        print(f"🔨 Deferred pickle rebuild - {len(scanner_service.data_cache)} symbols in cache")
        async def _deferred_pickle():
            import pickle, gzip, time as _time
            from app.services.data_export import data_export_service, S3_BUCKET

            # Skip incremental fetch — cold start loaded yesterday's pickle (7374 symbols).
            # This pickle is a warm cache for tomorrow's daily scan cold start.
            # Tomorrow's scan will do its own incremental fetch to get today's prices.
            print(f"📦 Using cold-start cache ({len(scanner_service.data_cache)} symbols, skipping incremental)")

            # Stream pickle to /tmp file to avoid OOM (pickle.dumps holds 2x in memory)
            # Use compresslevel=1 for speed (~5x faster than default 9, ~10% larger file).
            # Canonicalize at the storage boundary AND mutate the live cache
            # in-place — the diff harness reads scanner_service.data_cache,
            # not the S3 pickle, so without in-place mutation the on-disk
            # state can be canonical while the in-memory state isn't.
            expected_indicators = set(scanner_service.EXPECTED_INDICATORS)
            clean_cache = {}
            for s, df in scanner_service.data_cache.items():
                if df is None or len(df) < 50:
                    continue
                mutated = False
                if df.index.name != 'date':
                    df = df.copy()
                    df.index.name = 'date'
                    mutated = True
                if any(c not in df.columns for c in expected_indicators):
                    df = scanner_service._ensure_indicators(df)
                    mutated = True
                if mutated:
                    scanner_service.data_cache[s] = df
                clean_cache[s] = df
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
            result = _run_async(_deferred_pickle())
            print(f"🔨 Deferred pickle result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Deferred pickle failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle CSV export (chained from pickle rebuild)
    # Debug: run user_portfolio_simulator for one user and dump every trade.
    if event.get("debug_user_portfolio_simulate"):
        from datetime import date as _date
        from app.services import user_portfolio_simulator as ups
        async def _debug_sim():
            from app.core.database import async_session, User
            email = event.get("email") or "erik@rigacap.com"
            async with async_session() as db:
                row = await db.execute(select(User).where(User.email == email))
                user = row.scalar_one_or_none()
                if not user or not user.created_at:
                    return {"error": f"user {email} not found or no created_at"}
                signup = user.created_at.date()
                size = float(user.portfolio_size or 10000.0)
                trade_log = []
                sim = ups.simulate(signup, size, _date.today(), trade_log=trade_log)
                ups.clear_caches()
                return {
                    "email": email,
                    "signup": signup.isoformat(),
                    "portfolio_size": size,
                    "result": {
                        "portfolio_value": sim.portfolio_value,
                        "open_pnl_pct": sim.open_pnl_pct,
                        "open_positions_count": sim.open_positions_count,
                        "closed_trades_count": sim.closed_trades_count,
                        "winning_trades_count": sim.winning_trades_count,
                        "total_pnl_dollars": sim.total_pnl_dollars,
                        "open_positions": sim.open_positions,
                    },
                    "trade_log": trade_log,
                }

        try:
            return {"statusCode": 200, "body": _run_async(_debug_sim())}
        except Exception as e:
            import traceback
            print(f"❌ debug sim failed: {e}")
            traceback.print_exc()
            return {"statusCode": 500, "body": {"error": str(e)}}

    # Recompute per-user portfolio state for every active subscriber.
    # Chained from the daily-scan as step 11 — fires after dashboard +
    # snapshots are written so the simulator has fresh inputs.
    if event.get("user_portfolio_recompute"):
        from datetime import date as _date
        print("📊 User portfolio recompute triggered")
        async def _recompute_all_users():
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from app.core.database import (
                async_session, User, Subscription, UserPortfolioState,
            )
            from app.services import user_portfolio_simulator as ups

            today = _date.today()
            results = {"computed": 0, "skipped": 0, "errors": []}

            async with async_session() as db:
                # Active subscriber filter: trial / active / comped — anyone
                # whose subscription is still valid. Include admins so Erik
                # can preview the banner end-to-end.
                rows = await db.execute(
                    select(User, Subscription)
                    .join(Subscription, Subscription.user_id == User.id)
                    .where(
                        User.is_active == True,  # noqa: E712
                        Subscription.status.in_(("trial", "active", "comped")),
                    )
                )
                user_subs = list(rows.all())
                print(f"📊 Recomputing for {len(user_subs)} active subscribers")

                for user, sub in user_subs:
                    if not user.created_at:
                        results["skipped"] += 1
                        continue
                    try:
                        signup = user.created_at.date()
                        size = float(user.portfolio_size or 10000.0)
                        sim = ups.simulate(signup, size, today)

                        stmt = pg_insert(UserPortfolioState).values(
                            user_id=user.id,
                            as_of_date=today,
                            portfolio_value=sim.portfolio_value,
                            cost_basis=sim.cost_basis,
                            open_pnl_dollars=sim.open_pnl_dollars,
                            open_pnl_pct=sim.open_pnl_pct,
                            open_positions_count=sim.open_positions_count,
                            closed_trades_count=sim.closed_trades_count,
                            winning_trades_count=sim.winning_trades_count,
                            total_pnl_dollars=sim.total_pnl_dollars,
                            updated_at=datetime.utcnow(),
                        ).on_conflict_do_update(
                            index_elements=["user_id", "as_of_date"],
                            set_={
                                "portfolio_value": sim.portfolio_value,
                                "cost_basis": sim.cost_basis,
                                "open_pnl_dollars": sim.open_pnl_dollars,
                                "open_pnl_pct": sim.open_pnl_pct,
                                "open_positions_count": sim.open_positions_count,
                                "closed_trades_count": sim.closed_trades_count,
                                "winning_trades_count": sim.winning_trades_count,
                                "total_pnl_dollars": sim.total_pnl_dollars,
                                "updated_at": datetime.utcnow(),
                            },
                        )
                        await db.execute(stmt)
                        results["computed"] += 1
                    except Exception as e:
                        results["errors"].append({"user_id": str(user.id), "error": str(e)[:200]})

                await db.commit()

            ups.clear_caches()
            return results

        try:
            result = _run_async(_recompute_all_users())
            print(f"📊 User portfolio recompute done: {result}")
            return {"statusCode": 200, "body": result}
        except Exception as e:
            import traceback
            print(f"❌ User portfolio recompute failed: {e}")
            traceback.print_exc()
            return {"statusCode": 500, "body": {"error": str(e)}}

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
            result = _run_async(_data_fill())
            print(f"📡 Data fill result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Data fill failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle pickle rebuild (self-chaining catch-up queue for missing symbols)
    if event.get("pickle_rebuild"):
        # PARQUET MODE (Jun 21 2026): the full-pickle rebuild is OBSOLETE — and
        # actively harmful. In parquet mode each cold start loads only the scoped
        # ~603 symbols, so the chunked "fetch the missing 4421, self-chain" never
        # accumulates: every chained invocation reloads 603, sees ~4421 missing
        # again, fetches 200, OOMs at the 3008 MB cap, re-chains. The Jun 21
        # Sunday-00:00 cron spun this into a 27-hour infinite OOM loop (426 OOMs).
        # Skip cleanly and DO NOT self-chain — this also kills any in-flight loop
        # on its next iteration (new code, no chain). Pickle freshness is handled
        # by the parquet store now.
        if os.environ.get("PRICE_SOURCE", "pickle").lower() == "parquet":
            print("⏭️ pickle_rebuild skipped — PRICE_SOURCE=parquet (full-pickle rebuild obsolete; no self-chain)")
            return {"status": "skipped", "reason": "parquet_mode"}
        print(f"🔨 Pickle rebuild triggered - {len(scanner_service.data_cache)} symbols in cache")
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
            result = _run_async(_run_pickle_rebuild())
            print(f"🔨 Pickle rebuild result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Pickle rebuild failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Month-to-date signal analysis — answers "how many signals this month,
    # how many distinct names, how many respawns, regime context, and
    # what's the model portfolio actually holding right now?"
    # {"signal_month_analysis": {"year": 2026, "month": 5}}
    if event.get("signal_month_analysis"):
        cfg = event["signal_month_analysis"] or {}
        year = int(cfg.get("year", datetime.now().year))
        month = int(cfg.get("month", datetime.now().month))

        async def _analyze():
            from sqlalchemy import select, func, and_, or_, distinct
            from datetime import date as _date
            from calendar import monthrange
            from app.core.database import EnsembleSignal, ModelPosition

            start = _date(year, month, 1)
            end_day = monthrange(year, month)[1]
            end = _date(year, month, end_day)

            async with async_session() as db:
                # A "signal event" = one (symbol, ensemble_entry_date) tuple.
                # The ensemble_signals table records every (signal_date, symbol)
                # — so a name on the list 10 days has 10 rows sharing the same
                # ensemble_entry_date. Distinct on the entry tuple collapses
                # those to one event per actual fire.
                event_rows = (await db.execute(
                    select(
                        EnsembleSignal.symbol,
                        EnsembleSignal.ensemble_entry_date,
                        func.min(EnsembleSignal.signal_date).label("first_seen"),
                    )
                    .where(EnsembleSignal.ensemble_entry_date >= start)
                    .where(EnsembleSignal.ensemble_entry_date <= end)
                    .group_by(EnsembleSignal.symbol, EnsembleSignal.ensemble_entry_date)
                    .order_by(EnsembleSignal.ensemble_entry_date)
                )).all()

                # Each row is one fire event. Convert into a list of dicts.
                month_events = [
                    {"symbol": r.symbol, "ensemble_entry_date": r.ensemble_entry_date, "first_seen": r.first_seen}
                    for r in event_rows
                ]
                month_symbols = sorted({e["symbol"] for e in month_events})

                # For each symbol that fired this month, check whether it
                # had any PRIOR (symbol, ensemble_entry_date) distinct from
                # the ones in this month. Counts of distinct prior entries
                # = how many times this name has fired before.
                prior_count_by_symbol = {}
                if month_symbols:
                    prior_q = (
                        select(
                            EnsembleSignal.symbol,
                            func.count(distinct(EnsembleSignal.ensemble_entry_date)).label("n"),
                            func.min(EnsembleSignal.ensemble_entry_date).label("first_fired"),
                        )
                        .where(EnsembleSignal.symbol.in_(month_symbols))
                        .where(EnsembleSignal.ensemble_entry_date < start)
                        .group_by(EnsembleSignal.symbol)
                    )
                    prior_rows = (await db.execute(prior_q)).all()
                    for row in prior_rows:
                        prior_count_by_symbol[row.symbol] = {
                            "prior_fires": int(row.n),
                            "first_fired": row.first_fired.isoformat() if row.first_fired else None,
                        }

                # Model portfolio: every position that touched the month
                # (entered during the month OR opened before but closed during).
                # entry_date / exit_date are DateTime columns, so build datetime
                # boundaries from the start/end date objects for the compare.
                from datetime import datetime as _dt, time as _time
                start_dt = _dt.combine(start, _time.min)
                end_dt = _dt.combine(end, _time.max)
                pos_rows = (await db.execute(
                    select(ModelPosition)
                    .where(or_(
                        and_(ModelPosition.entry_date >= start_dt, ModelPosition.entry_date <= end_dt),
                        and_(ModelPosition.exit_date >= start_dt, ModelPosition.exit_date <= end_dt),
                        and_(ModelPosition.entry_date < start_dt, ModelPosition.exit_date.is_(None)),
                    ))
                    .order_by(ModelPosition.entry_date)
                )).scalars().all()

            # Build the per-signal summary
            new_names = []
            respawns = []
            for sym in month_symbols:
                if sym in prior_count_by_symbol:
                    p = prior_count_by_symbol[sym]
                    respawns.append({
                        "symbol": sym,
                        "prior_fires": p["prior_fires"],
                        "first_fired_ever": p["first_fired"],
                    })
                else:
                    new_names.append(sym)

            # Daily breakdown — keyed by ensemble_entry_date so each fire
            # event lands on the day the signal actually triggered.
            from collections import defaultdict
            by_day = defaultdict(list)
            for e in month_events:
                by_day[e["ensemble_entry_date"].isoformat()].append(e["symbol"])
            daily = [
                {"date": d, "count": len(syms), "symbols": syms}
                for d, syms in sorted(by_day.items())
            ]

            # Model portfolio breakdown (entry_date / exit_date are DateTime,
            # so compare with the datetime boundaries built above)
            open_now = [p for p in pos_rows if p.exit_date is None]
            closed_in_month = [p for p in pos_rows if p.exit_date and start_dt <= p.exit_date <= end_dt]
            entered_in_month = [p for p in pos_rows if start_dt <= p.entry_date <= end_dt]
            closed_winners = [p for p in closed_in_month if p.pnl_pct and p.pnl_pct > 0]
            closed_losers = [p for p in closed_in_month if p.pnl_pct and p.pnl_pct <= 0]
            win_rate = (len(closed_winners) / len(closed_in_month)) if closed_in_month else None

            return {
                "window": f"{start.isoformat()} → {end.isoformat()}",
                "month_label": start.strftime("%B %Y"),
                "signals_summary": {
                    "total_signal_events": len(month_events),
                    "distinct_symbols": len(month_symbols),
                    "genuinely_new_names": len(new_names),
                    "respawns_with_prior_history": len(respawns),
                },
                "new_names": new_names,
                "respawn_detail": sorted(respawns, key=lambda r: -r["prior_fires"]),
                "daily_signal_counts": daily,
                "model_portfolio": {
                    "currently_open": len(open_now),
                    "entered_this_month": len(entered_in_month),
                    "closed_this_month": len(closed_in_month),
                    "winners_closed": len(closed_winners),
                    "losers_closed": len(closed_losers),
                    "win_rate_closed_this_month": round(win_rate, 3) if win_rate is not None else None,
                    "open_symbols": [
                        {
                            "symbol": p.symbol,
                            "entry_date": p.entry_date.isoformat() if p.entry_date else None,
                            "entry_price": p.entry_price,
                            "shares": p.shares,
                        } for p in open_now
                    ],
                },
            }

        try:
            return _run_async(_analyze())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:600]}

    # Read-only inspection of strategy_definitions table — what params is
    # the WF backtester actually loading when we fire with --strategy-id N
    # but no CLI overrides? Used during the May 18 parity audit after job
    # 1253 returned terrible numbers; need to know if the DB row's params
    # are why.
    # {"strategy_def_get": {"id": 5}}
    if event.get("strategy_def_get"):
        cfg = event["strategy_def_get"] or {}
        sid = cfg.get("id")
        if sid is None:
            return {"error": "id required"}

        async def _get_strat():
            from sqlalchemy import select
            from app.core.database import StrategyDefinition
            async with async_session() as db:
                row = (await db.execute(
                    select(StrategyDefinition).where(StrategyDefinition.id == int(sid))
                )).scalar_one_or_none()
                if row is None:
                    return {"error": f"No strategy with id={sid}"}
                params = row.parameters
                # parameters column is JSON; might come back as dict or str
                if isinstance(params, str):
                    try:
                        import json as _j
                        params = _j.loads(params)
                    except Exception:
                        pass
                return {
                    "id": row.id,
                    "name": row.name,
                    "strategy_type": row.strategy_type,
                    "description": row.description,
                    "is_active": getattr(row, 'is_active', None),
                    "parameters": params,
                }
        try:
            return _run_async(_get_strat())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:500]}

    # Narrow write handler: set is_active on a single strategy_adaptive_params
    # row. Used May 18 2026 to deactivate the Run5 over-fit row (id=1) so
    # production falls back to config.py canonical values. Reversible by
    # re-invoking with is_active=true.
    # {"adaptive_params_set_active": {"id": 1, "is_active": false}}
    if event.get("adaptive_params_set_active"):
        cfg = event["adaptive_params_set_active"] or {}
        row_id = cfg.get("id")
        new_active = cfg.get("is_active")
        if row_id is None or new_active is None:
            return {"error": "id and is_active required"}
        if not isinstance(new_active, bool):
            return {"error": "is_active must be true or false (boolean)"}

        async def _set():
            from sqlalchemy import select
            from app.core.database import StrategyAdaptiveParams
            async with async_session() as db:
                row = (await db.execute(
                    select(StrategyAdaptiveParams).where(StrategyAdaptiveParams.id == int(row_id))
                )).scalar_one_or_none()
                if row is None:
                    return {"error": f"No row with id={row_id}"}
                before = row.is_active
                row.is_active = bool(new_active)
                await db.commit()
                return {
                    "id": row.id,
                    "effective_date": row.effective_date.isoformat() if row.effective_date else None,
                    "source": row.source,
                    "before": before,
                    "after": row.is_active,
                }
        try:
            return _run_async(_set())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:500]}

    # Read-only inspection of strategy_adaptive_params table — what's the
    # biweekly TPE cron currently feeding the scanner? Used during the
    # May 18 2026 parity audit to find the StrategyAdaptiveParams DB
    # override that was masking the config.py Path A revert.
    # {"adaptive_params_list": {"limit": 10}}
    if event.get("adaptive_params_list"):
        cfg = event["adaptive_params_list"] or {}
        limit = int(cfg.get("limit", 10))

        async def _list():
            from sqlalchemy import select, desc
            from app.core.database import StrategyAdaptiveParams
            async with async_session() as db:
                rows = (await db.execute(
                    select(StrategyAdaptiveParams)
                    .order_by(desc(StrategyAdaptiveParams.effective_date))
                    .limit(limit)
                )).scalars().all()
            return {
                "count": len(rows),
                "rows": [
                    {
                        "id": r.id,
                        "effective_date": r.effective_date.isoformat() if r.effective_date else None,
                        "optimization_date": r.optimization_date.isoformat() if r.optimization_date else None,
                        "is_active": r.is_active,
                        "source": r.source,
                        "regime_at_optimization": r.regime_at_optimization,
                        "expected_return_pct": r.expected_return_pct,
                        "expected_sharpe": r.expected_sharpe,
                        "params_json": r.params_json,
                    } for r in rows
                ]
            }
        try:
            return _run_async(_list())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:500]}

    # Quick symbol-signal-history lookup for ad-hoc questions like
    # "when did X show up on the dashboard?" — returns every ensemble_signal
    # row for the symbol so we can see signal_date, is_fresh per day, etc.
    # {"signal_history_for_symbol": {"symbol": "WULF", "limit": 200}}
    if event.get("signal_history_for_symbol"):
        cfg = event["signal_history_for_symbol"] or {}
        sym = cfg.get("symbol")
        limit = int(cfg.get("limit", 100))
        if not sym:
            return {"error": "symbol required"}

        async def _hist():
            from sqlalchemy import select, desc
            from app.core.database import EnsembleSignal
            async with async_session() as db:
                rows = (await db.execute(
                    select(EnsembleSignal)
                    .where(EnsembleSignal.symbol == sym)
                    .order_by(desc(EnsembleSignal.signal_date))
                    .limit(limit)
                )).scalars().all()
            return {
                "symbol": sym,
                "count": len(rows),
                "rows": [
                    {
                        "signal_date": r.signal_date.isoformat() if r.signal_date else None,
                        "ensemble_entry_date": r.ensemble_entry_date.isoformat() if r.ensemble_entry_date else None,
                        "is_fresh": r.is_fresh,
                        "ensemble_score": r.ensemble_score,
                        "momentum_rank": r.momentum_rank,
                        "status": r.status,
                        "price": r.price,
                    } for r in rows
                ]
            }

        try:
            return _run_async(_hist())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:500]}

    # Universe history snapshot — write today's full ranked liquidity
    # universe to s3://.../signals/universe-history/{date}.json. Append-only:
    # idempotent on re-invocation (returns "exists" without overwriting).
    # {"universe_snapshot": {"date": "2026-05-17"}}  (date optional, defaults to today)
    # WEEKLY universe refresh (Jun 23 2026) — re-rank the FULL ~5000-symbol
    # universe WITHOUT OOM, so the scoped parquet load's top-600 stays fresh
    # (the daily scan only sees 603 symbols and would ossify it). Memory-safe by
    # construction: reads ONLY [symbol, date, close, volume] for the last ~120
    # days from all_data.parquet (a thin slice — not the full OHLCV history that
    # caused the OOM), computes last_close + 60d avg volume per symbol, ranks,
    # and writes the authoritative universe-history snapshot the scoped load reads.
    # PITFWU daily append (Jun 24 2026, close-the-loop step 1) — keep the
    # per-symbol RAW bar store current so the read path can move off the frozen
    # all_data.parquet. ADDITIVE: writes pitfwu/bars/{sym}.parquet only; does NOT
    # touch the live read path or signals. Appends the gap (PITFWU last date ->
    # today) for the scoped symbols. Memory-safe (only touched symbols' recent
    # bars). {"pitfwu_append": {"symbols": [...]}} optional explicit list.
    if event.get("pitfwu_append"):
        _cfg = event.get("pitfwu_append") or {}
        def _do_pitfwu_append():
            import pandas as _pd
            from app.services import pitfwu_store as ps
            _execute = bool(_cfg.get("execute", True)) if isinstance(_cfg, dict) else True
            _max_lag = int(_cfg.get("max_lag_days", 4)) if isinstance(_cfg, dict) else 4
            # full_backfill: heal newcomers/stale files with a WIDE window + union merge
            # (fills history back so a re-entering symbol clears the >=250-bar rank gate).
            _full = bool(_cfg.get("full_backfill", False)) if isinstance(_cfg, dict) else False
            _bf_days = int(_cfg.get("backfill_days", 420)) if isinstance(_cfg, dict) else 420
            syms = _cfg.get("symbols") if isinstance(_cfg, dict) else None
            if not syms:
                # Daily append covers the SCOPED active universe (~600) only. The full store is ~21k
                # files (whole market) — appending all daily is infeasible (15-min timeout) AND
                # pointless (only the scoped set is scanned/traded/shown). A symbol RE-ENTERING the
                # scoped set with a stale file is healed by a targeted FULL backfill, not by appending
                # the whole store. Freeze detection below still flags any scoped symbol left stale.
                syms = [s for s in scanner_service.data_cache.keys() if not s.startswith("^")]
            if _full:
                start = (_pd.Timestamp.now().normalize() - _pd.Timedelta(days=_bf_days)).date().isoformat()
            else:
                last = ps.pitfwu_last_date()  # reference (AAPL) last bar
                if last is not None:
                    start = (last - _pd.Timedelta(days=5)).date().isoformat()   # small overlap; per-symbol dedupe handles it
                else:
                    start = (_pd.Timestamp.now().normalize() - _pd.Timedelta(days=400)).date().isoformat()
            end = _pd.Timestamp.now().date().isoformat()
            print(f"📈 PITFWU append: {len(syms)} symbols, {'FULL backfill' if _full else 'gap'} {start}..{end}, execute={_execute}")
            summary = ps.append_pitfwu_bars(syms, start, end, execute=_execute, full=_full)
            new_last = ps.pitfwu_last_date()
            # FREEZE DETECTION: any symbol whose last bar lags the market's last bar by > max_lag days
            # (still active in the store but not advancing) — surface it, never swallow.
            frozen = []
            try:
                if new_last is not None:
                    cutoff = _pd.Timestamp(new_last) - _pd.Timedelta(days=_max_lag)
                    for s, d in (summary.get("last_dates") or {}).items():
                        if _pd.Timestamp(d) < cutoff:
                            frozen.append(s)
                    frozen.sort()
            except Exception as _fe:
                print(f"⚠️ PITFWU freeze-detection failed: {_fe}")
            nf = summary.get("no_fetch_symbols") or []
            # Backfill health: which symbols STILL lack enough history to rank (>=250 bars)
            short_after = sorted(s for s, n in (summary.get("last_len") or {}).items() if n < 250)
            if frozen:
                print(f"🧊 PITFWU FROZEN ({len(frozen)}, last bar >{_max_lag}d behind market): {', '.join(frozen[:40])}")
            if nf:
                print(f"⚠️ PITFWU no-fetch ({len(nf)}): {', '.join(nf[:40])}")
            # Still-short symbols are NOT stitched (yfinance is split-adjusted; a merger
            # boundary must never be spanned). Classify WHY and leave them safely gated.
            short_reasons = {}
            if _full and short_after:
                print(f"📏 PITFWU still-short after Alpaca backfill ({len(short_after)}, <250 bars): {', '.join(short_after[:40])}")
                short_reasons = ps.classify_short_symbols(short_after)
            summary.pop("last_dates", None)   # keep the return compact
            summary.pop("last_len", None)
            return {"status": "success", "symbols": len(syms), "gap": f"{start}..{end}",
                    "execute": _execute, "summary": summary,
                    "frozen_count": len(frozen), "frozen": frozen[:60],
                    "short_after_count": len(short_after), "short_after": short_after[:60],
                    "short_reasons": short_reasons,   # gated, labeled; never stitched
                    "pitfwu_last_date": str(new_last.date()) if new_last is not None else None}
        try:
            result = _do_pitfwu_append()
            print(f"📈 PITFWU append result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ pitfwu_append failed: {e}\n{traceback.format_exc()}")
            return {"status": "error", "error": str(e)}

    # PITFWU shadow-diff (close-the-loop step 2) — validate the PITFWU read path
    # against the live all_data.parquet read for the scoped universe BEFORE any
    # cutover. Read-only. Compares latest-common-date close + volume per symbol;
    # if those match, every downstream indicator/signal (deterministic from the
    # bars) matches too. Reports coverage gaps (symbols missing from PITFWU).
    if event.get("pitfwu_shadow_diff"):
        print("🔬 PITFWU shadow-diff vs all_data.parquet")
        def _shadow():
            import json as _json, boto3
            from app.services.data_export import data_export_service, S3_BUCKET
            from app.services import pitfwu_store as ps
            # scoped universe = same selection as _scoped_parquet_load
            s3 = boto3.client("s3", region_name="us-east-1")
            objs = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="signals/universe-history/")
            keys = sorted(o["Key"] for o in objs.get("Contents", []) if o["Key"].endswith(".json"))
            scoped = []
            if keys:
                uni = _json.loads(s3.get_object(Bucket=S3_BUCKET, Key=keys[-1])["Body"].read())
                for r in uni.get("rankings", []):
                    if len(scoped) >= 600:
                        break
                    if not r.get("is_excluded") and r.get("symbol") and not r["symbol"].startswith("^"):
                        scoped.append(r["symbol"])
            cache_a = data_export_service.import_parquet(symbols=scoped)  # all_data.parquet
            ca = ps.load_corp_actions()
            checked = matched = 0
            missing, mism = [], []
            for s in scoped:
                a = cache_a.get(s)
                if a is None or len(a) == 0:
                    continue
                b = ps.split_adjusted(s, ca=ca)
                if b is None or len(b) == 0:
                    missing.append(s); continue
                common = a.index.intersection(b.index)
                if len(common) == 0:
                    missing.append(s); continue
                d = common.max()
                ac, bc = float(a.loc[d, "close"]), float(b.loc[d, "close"])
                av, bv = float(a.loc[d, "volume"]), float(b.loc[d, "volume"])
                checked += 1
                cl_ok = abs(ac - bc) < 0.01 or abs(ac - bc) / max(ac, 1e-9) < 0.001
                vol_ok = av == 0 or abs(av - bv) / max(av, 1e-9) < 0.02
                if cl_ok and vol_ok:
                    matched += 1
                elif len(mism) < 15:
                    mism.append({"sym": s, "date": str(d.date()), "close_a": round(ac, 2),
                                 "close_b": round(bc, 2), "vol_a": av, "vol_b": bv})
            return {"status": "success", "scoped": len(scoped), "checked": checked,
                    "matched": matched, "match_pct": round(100 * matched / checked, 2) if checked else None,
                    "missing_from_pitfwu": len(missing), "missing_sample": missing[:15],
                    "mismatches": mism}
        try:
            result = _shadow()
            print(f"🔬 PITFWU shadow-diff: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ pitfwu_shadow_diff failed: {e}\n{traceback.format_exc()}")
            return {"status": "error", "error": str(e)}

    if event.get("universe_refresh"):
        print("🌐 Universe refresh — full-universe ranking from a thin parquet slice")
        def _universe_refresh():
            import pandas as _pd, json as _json, boto3, tempfile, os as _os
            from datetime import date as _date, datetime as _dt
            from app.services.scanner import _EXCLUDED_SET
            from app.services.data_export import S3_BUCKET
            s3 = boto3.client('s3', region_name='us-east-1')
            tmp = _os.path.join(tempfile.gettempdir(), 'universe_refresh.parquet')
            with open(tmp, 'wb') as f:
                obj = s3.get_object(Bucket=S3_BUCKET, Key='prices/all_data.parquet')
                for chunk in obj['Body'].iter_chunks(chunk_size=8 * 1024 * 1024):
                    f.write(chunk)
            cutoff = (_pd.Timestamp.now().normalize() - _pd.Timedelta(days=120)).to_pydatetime()
            # Column projection + date predicate pushdown => tiny memory footprint
            df = _pd.read_parquet(tmp, columns=['symbol', 'date', 'close', 'volume'],
                                  filters=[('date', '>=', cutoff)])
            try:
                _os.remove(tmp)
            except Exception:
                pass
            df['date'] = _pd.to_datetime(df['date'])
            rankings = []
            for sym, g in df.groupby('symbol', sort=False):
                if len(g) < 60:
                    continue
                g = g.sort_values('date')
                rankings.append({
                    'symbol': sym,
                    'avg_volume_60d': float(g['volume'].tail(60).mean()),
                    'last_close': float(g['close'].iloc[-1]),
                    'last_date': g['date'].iloc[-1].strftime('%Y-%m-%d'),
                    'is_excluded': (sym in _EXCLUDED_SET) or sym.startswith('^'),
                })
            rankings.sort(key=lambda r: r['avg_volume_60d'], reverse=True)
            for i, r in enumerate(rankings, 1):
                r['rank'] = i
            snap_date = _date.today().isoformat()
            snapshot = {
                'snapshot_date': snap_date,
                'snapshot_time_utc': _dt.utcnow().isoformat() + 'Z',
                'total_eligible_symbols': len(rankings),
                'excluded_count': sum(1 for r in rankings if r['is_excluded']),
                'signal_universe_size_setting': int(_os.environ.get('SIGNAL_UNIVERSE_SIZE', '0')) or None,
                'excluded_symbols_in_universe': sorted(r['symbol'] for r in rankings if r['is_excluded']),
                'rankings': rankings,
                'source': 'universe_refresh_full_parquet',
            }
            s3.put_object(Bucket=S3_BUCKET, Key=f'signals/universe-history/{snap_date}.json',
                          Body=_json.dumps(snapshot).encode('utf-8'), ContentType='application/json')
            return {'status': 'success', 'ranked': len(rankings), 'date': snap_date,
                    'top8': [r['symbol'] for r in rankings[:8] if not r['is_excluded']][:8]}
        try:
            result = _universe_refresh()
            print(f"🌐 Universe refresh result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ universe_refresh failed: {e}\n{traceback.format_exc()}")
            return {'error': str(e)}

    if event.get("universe_refresh_v2"):
        # Fresh-fetch liquidity rank. Breaks the frozen-universe chicken-and-egg:
        # the OLD universe_refresh ranks 60d volume off the FROZEN all_data.parquet
        # (Jun 15), so a stock whose volume surged AFTER the freeze can never enter
        # the top-N scoped set → never loaded → never signals. This ranks the CLEAN
        # symbol list (stock_universe_service: NASDAQ/NYSE screener + EXCLUDED_PATTERNS,
        # weekly-fresh) off a FRESH raw-bar fetch (volume is split-invariant). Same
        # output artifact + same consumer as universe_refresh; only the input changes.
        # write:false (default) is read-only — ranks + DIFFs vs the current frozen
        # snapshot so we can see the surgers we've been blind to before flipping.
        cfg = event.get("universe_refresh_v2") or {}
        do_write = bool(cfg.get("write", False)) if isinstance(cfg, dict) else False
        do_heal = bool(cfg.get("heal_newcomers", False)) if isinstance(cfg, dict) else False
        lookback = int(cfg.get("lookback_days", 90)) if isinstance(cfg, dict) else 90
        bf_days = int(cfg.get("backfill_days", 420)) if isinstance(cfg, dict) else 420
        print(f"🌐 universe_refresh_v2 (fresh fetch, write={do_write}, heal={do_heal}, lookback={lookback}d)")
        def _universe_refresh_v2():
            import os as _os, json as _json, boto3
            from datetime import date as _date, datetime as _dt, timedelta as _td
            from app.services.scanner import _EXCLUDED_SET
            from app.services.data_export import S3_BUCKET
            from app.services.stock_universe import S3_UNIVERSE_KEY
            from app.services import pitfwu_store as _ps
            from app.core.config import settings as _cfg
            s3 = boto3.client('s3', region_name='us-east-1')

            # 1) CLEAN symbol list (already ETF/crypto-excluded, weekly-fresh)
            uni_cache = _json.loads(s3.get_object(Bucket=S3_BUCKET, Key=S3_UNIVERSE_KEY)['Body'].read())
            symbols = [s for s in uni_cache.get('symbols', [])
                       if s not in _EXCLUDED_SET and not s.startswith('^')]
            clean_age_days = None
            if uni_cache.get('updated'):
                try:
                    clean_age_days = (_dt.utcnow() - _dt.fromisoformat(
                        uni_cache['updated'].replace('Z', ''))).days
                except Exception:
                    pass

            # 2) FRESH raw bars (volume unaffected by split adjustment)
            end = _date.today()
            start = end - _td(days=lookback)
            bars = _ps.fetch_raw_bars(symbols, start, end)

            # 3) rank by FRESH 60d avg volume + MIN_PRICE gate
            rankings = []
            for sym, g in bars.items():
                if g is None or len(g) < 60:
                    continue
                g = g.sort_index()
                vol60 = float(g['volume'].tail(60).mean())
                last_close = float(g['close'].iloc[-1])
                if last_close < _cfg.MIN_PRICE:
                    continue
                rankings.append({'symbol': sym, 'avg_volume_60d': vol60,
                                 'last_close': last_close,
                                 'last_date': g.index[-1].strftime('%Y-%m-%d'),
                                 'is_excluded': False})
            rankings.sort(key=lambda r: r['avg_volume_60d'], reverse=True)
            for i, r in enumerate(rankings, 1):
                r['rank'] = i

            # 4) DIFF vs current frozen snapshot (top-N membership)
            topn = int(_os.environ.get('PARQUET_SCOPE_TOPN', '600'))
            fresh_top = [r['symbol'] for r in rankings[:topn]]
            fresh_set = set(fresh_top)
            frozen_top, frozen_date = [], None
            objs = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix='signals/universe-history/')
            keys = sorted(o['Key'] for o in objs.get('Contents', []) if o['Key'].endswith('.json'))
            if keys:
                old = _json.loads(s3.get_object(Bucket=S3_BUCKET, Key=keys[-1])['Body'].read())
                frozen_date = old.get('snapshot_date')
                for r in old.get('rankings', []):
                    if len(frozen_top) >= topn:
                        break
                    if not r.get('is_excluded') and r.get('symbol'):
                        frozen_top.append(r['symbol'])
            frozen_set = set(frozen_top)
            surgers_in = sorted(fresh_set - frozen_set)     # newly liquid — we were BLIND to these
            dropped_out = sorted(frozen_set - fresh_set)

            result = {
                'status': 'success', 'write': do_write,
                'clean_list_size': len(symbols), 'clean_list_age_days': clean_age_days,
                'fetched_ok': len(bars), 'ranked': len(rankings),
                'frozen_snapshot_date': frozen_date, 'topn': topn,
                'new_in_top': len(surgers_in), 'dropped_from_top': len(dropped_out),
                'sample_surgers': surgers_in[:40],
                'new_in_top_symbols': surgers_in,
                'fresh_top20': fresh_top[:20],
            }

            if do_write:
                snap_date = _date.today().isoformat()
                snapshot = {
                    'snapshot_date': snap_date,
                    'snapshot_time_utc': _dt.utcnow().isoformat() + 'Z',
                    'total_eligible_symbols': len(rankings),
                    'excluded_count': 0,
                    'signal_universe_size_setting': int(_os.environ.get('SIGNAL_UNIVERSE_SIZE', '0')) or None,
                    'excluded_symbols_in_universe': [],
                    'rankings': rankings,
                    'source': 'universe_refresh_v2_fresh_fetch',
                }
                s3.put_object(Bucket=S3_BUCKET, Key=f'signals/universe-history/{snap_date}.json',
                              Body=_json.dumps(snapshot).encode('utf-8'), ContentType='application/json')
                result['written_key'] = f'signals/universe-history/{snap_date}.json'

                # HEAL NEWCOMERS: the surgers just added to the top-N aren't in the
                # daily-append scope yet, so their PITFWU file is stale/absent → they'd
                # fall back to the frozen all_data.parquet + get rejected by the display
                # gate. Full-backfill them now (union merge, never deletes) so they clear
                # the >=250-bar rank gate and can signal on THIS cycle. Additive + idempotent.
                if do_heal and surgers_in:
                    end_h = _date.today()
                    start_h = end_h - _td(days=bf_days)
                    print(f"🩹 healing {len(surgers_in)} newcomers via FULL backfill {start_h}..{end_h}")
                    hsum = _ps.append_pitfwu_bars(surgers_in, start_h, end_h, execute=True, full=True)
                    short_after = sorted(s for s, n in (hsum.get("last_len") or {}).items() if n < 250)
                    # Still-short symbols are NOT stitched (yfinance is split-adjusted; and a
                    # merger boundary must never be spanned). Classify WHY they're short and
                    # leave them safely gated with a labeled reason.
                    short_reasons = {}
                    if short_after:
                        print(f"📏 still-short after Alpaca heal ({len(short_after)}): {', '.join(short_after[:40])}")
                        short_reasons = _ps.classify_short_symbols(short_after)
                        _brk = [s for s, r in short_reasons.items() if r.get('reason') == 'corporate_action_boundary']
                        print(f"🏷️ short reasons — merger/identity: {_brk} · young/gap: "
                              f"{[s for s in short_after if s not in _brk]}")
                    result['heal'] = {
                        'healed': len(surgers_in),
                        'new_symbol': hsum.get('new_symbol'),
                        'appended': hsum.get('appended'),
                        'no_fetch': hsum.get('no_fetch'),
                        'no_fetch_symbols': (hsum.get('no_fetch_symbols') or [])[:40],
                        'short_after_alpaca': short_after,
                        'short_reasons': short_reasons,   # gated, labeled; never stitched
                    }
            return result
        try:
            r = _universe_refresh_v2()
            print(f"🌐 universe_refresh_v2: {r}")
            return r
        except Exception as e:
            import traceback
            print(f"❌ universe_refresh_v2 failed: {e}\n{traceback.format_exc()}")
            return {'error': str(e)}

    if event.get("universe_snapshot"):
        cfg = event["universe_snapshot"] or {}
        snap_date = cfg.get("date") if isinstance(cfg, dict) else None
        try:
            from app.services.data_export import data_export_service
            return data_export_service.snapshot_universe_history(snapshot_date=snap_date)
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:500]}

    # Backfill universe-history snapshots across a date range. Walks every
    # weekday between start_date and end_date (inclusive) and writes a
    # snapshot if one doesn't already exist. Idempotent — re-runnable.
    # Chunked: stops after `max_per_run` to stay under Lambda timeout;
    # self-invoke or call repeatedly to finish.
    # {"universe_snapshot_backfill": {"start_date": "2019-06-03",
    #   "end_date": "2026-05-16", "max_per_run": 200}}
    if event.get("universe_snapshot_backfill"):
        cfg = event["universe_snapshot_backfill"] or {}
        from datetime import date as _date2, timedelta as _td2

        async def _backfill():
            from app.services.data_export import data_export_service
            start_s = cfg.get("start_date") or "2019-06-03"
            end_s = cfg.get("end_date") or _date2.today().isoformat()
            max_per_run = int(cfg.get("max_per_run", 200))

            start_d = _date2.fromisoformat(start_s)
            end_d = _date2.fromisoformat(end_s)

            written = 0
            skipped_existing = 0
            failed = 0
            current = start_d
            stopped_at = None

            while current <= end_d:
                # Skip weekends (no trading)
                if current.weekday() < 5:
                    if written + skipped_existing + failed >= max_per_run:
                        stopped_at = current.isoformat()
                        break
                    try:
                        res = data_export_service.snapshot_universe_history(
                            snapshot_date=current.isoformat()
                        )
                        if res.get("status") == "written":
                            written += 1
                        elif res.get("status") == "exists":
                            skipped_existing += 1
                        else:
                            failed += 1
                    except Exception as e:
                        failed += 1
                        print(f"⚠️ backfill {current}: {e}")
                current += _td2(days=1)

            return {
                "status": "stopped_at_limit" if stopped_at else "complete",
                "start_date": start_s, "end_date": end_s,
                "written": written, "skipped_existing": skipped_existing, "failed": failed,
                "next_start": stopped_at,
            }

        try:
            return _run_async(_backfill())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:500]}

    # One-shot diagnostic: for a completed WF job, classify each trade's
    # symbol by where it ranked in the liquidity universe AT ENTRY TIME.
    # Answers the question: would running production at SIGNAL_UNIVERSE_SIZE
    # = 100 vs 500 actually have changed which signals fired? If all
    # winners came from top-100, the parity gap is theoretical; if winners
    # came from 101-500, bumping is materially important.
    # {"wf_liquidity_rank_audit": {"job_id": 1248}}
    if event.get("wf_liquidity_rank_audit"):
        cfg = event["wf_liquidity_rank_audit"] or {}
        job_id = cfg.get("job_id")
        if not job_id:
            return {"error": "job_id required"}

        async def _audit():
            import json as _json
            from sqlalchemy import select
            from app.core.database import WalkForwardSimulation

            async with async_session() as db:
                row = (await db.execute(
                    select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
                )).scalar_one_or_none()
                if not row or not row.trades_json:
                    return {"error": f"No trades found for job {job_id}"}
                trades = _json.loads(row.trades_json)

            # For each trade, compute liquidity rank as of entry_date using
            # the same logic as walk_forward_service._get_top_symbols_as_of:
            # 60-day avg volume up to that date.
            from app.services.scanner import _EXCLUDED_SET
            import pandas as _pd

            results = {"top_100": 0, "rank_101_500": 0, "rank_501_plus": 0, "not_in_universe": 0}
            buckets = {"top_100": [], "rank_101_500": [], "rank_501_plus": []}

            for trade in trades:
                sym = trade.get("symbol")
                entry_date_str = trade.get("entry_date")
                if not sym or not entry_date_str:
                    continue
                try:
                    entry_ts = _pd.Timestamp(entry_date_str[:10])
                except Exception:
                    continue

                # Build ranking as of entry_date
                rankings = []
                for s, df in scanner_service.data_cache.items():
                    if s in _EXCLUDED_SET:
                        continue
                    hist = df[df.index <= entry_ts]
                    if len(hist) < 60 or 'volume' not in hist.columns:
                        continue
                    avg_vol = hist['volume'].tail(60).mean()
                    rankings.append((s, avg_vol))
                rankings.sort(key=lambda x: x[1], reverse=True)

                sym_rank = None
                for i, (s, _) in enumerate(rankings, start=1):
                    if s == sym:
                        sym_rank = i
                        break

                if sym_rank is None:
                    results["not_in_universe"] += 1
                    continue

                if sym_rank <= 100:
                    bucket = "top_100"
                elif sym_rank <= 500:
                    bucket = "rank_101_500"
                else:
                    bucket = "rank_501_plus"

                results[bucket] += 1
                if len(buckets.get(bucket, [])) < 15:
                    buckets[bucket].append({
                        "symbol": sym,
                        "entry_date": entry_date_str[:10],
                        "rank": sym_rank,
                        "pnl_pct": trade.get("pnl_pct"),
                        "pnl_dollars": trade.get("pnl_dollars"),
                    })

            total = sum(results.values())
            return {
                "job_id": job_id,
                "total_trades": total,
                "summary": results,
                "summary_pct": {k: round(v / total * 100, 1) if total else 0 for k, v in results.items()},
                "samples": buckets,
            }

        try:
            return _run_async(_audit())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:600]}

    # One-time HWM heal for ModelPosition rows. The pre-May-15 persistence
    # bug (commit gated on `if closed:`) silently discarded HWM updates for
    # 9+ days on positions where no exit fired. AMD's stored highest_price
    # was $358.23 while actual max close since entry was $458.79. This
    # handler walks every open ModelPosition, computes the true max close
    # since entry_date from the price cache, and persists the corrected
    # highest_price. Same pattern as parquet_alignment_heal but for the
    # positions table. Idempotent — safe to re-invoke.
    # {"hwm_heal": {"_": 1}}
    if event.get("hwm_heal"):
        print("🩹 HWM heal: correcting stored highest_price across all open ModelPositions")

        async def _heal_hwm():
            from sqlalchemy import select
            from app.core.database import ModelPosition

            async with async_session() as db:
                rows = (await db.execute(
                    select(ModelPosition).where(ModelPosition.status == "open")
                )).scalars().all()

                healed = []
                no_data = []
                already_correct = []

                for pos in rows:
                    df = scanner_service.data_cache.get(pos.symbol)
                    if df is None or len(df) == 0:
                        no_data.append(pos.symbol)
                        continue

                    # Filter to bars on or after entry_date (using close-only,
                    # matching post-Path-A WF parity behavior)
                    entry_date = pos.entry_date
                    if hasattr(entry_date, 'date'):
                        entry_date = entry_date.date()
                    # df.index is DatetimeIndex; compare on .date()
                    mask = df.index.date >= entry_date if hasattr(df.index, 'date') else None
                    if mask is None or not mask.any():
                        no_data.append(pos.symbol)
                        continue

                    max_close = float(df.loc[mask, "close"].max())
                    correct_hwm = max(max_close, pos.entry_price or 0)

                    stored = pos.highest_price or pos.entry_price or 0
                    # Only heal if correct HWM is HIGHER than stored — we
                    # never want to LOWER a previously-recorded peak (could
                    # have come from intraday data we don't see in close-only).
                    if correct_hwm > stored + 0.01:  # cent tolerance
                        healed.append({
                            "symbol": pos.symbol,
                            "portfolio_type": pos.portfolio_type,
                            "entry_date": str(entry_date),
                            "entry_price": pos.entry_price,
                            "stored_hwm": stored,
                            "correct_hwm": correct_hwm,
                            "delta": round(correct_hwm - stored, 2),
                        })
                        pos.highest_price = correct_hwm
                    else:
                        already_correct.append(pos.symbol)

                await db.commit()

                return {
                    "status": "completed",
                    "open_positions_scanned": len(rows),
                    "healed_count": len(healed),
                    "already_correct_count": len(already_correct),
                    "no_data_count": len(no_data),
                    "healed_detail": sorted(healed, key=lambda x: -x["delta"])[:30],
                    "no_data_symbols": no_data[:10],
                }

        try:
            return _run_async(_heal_hwm())
        except Exception as e:
            import traceback
            print(f"❌ HWM heal failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:600]}

    # Pickle health validator — runs against the actual pickle in S3 (not
    # parquet). Reports schema completeness, date freshness, index naming,
    # row-count distribution, and value sanity. Useful as a standalone
    # check between daily scans, or to verify a heal job worked.
    # {"pickle_validate": {"_": 1}}
    if event.get("pickle_validate"):
        print("🔬 Pickle validate: running standalone health check")

        async def _validate():
            import pandas as _pd
            import numpy as _np
            from datetime import datetime as _dt, timedelta as _td
            from app.services.data_export import data_export_service

            cache = data_export_service.import_all()
            if not cache:
                return {"status": "failed", "error": "Empty pickle"}

            # Use the canonical indicator set from the scanner so we never
            # drift from production's expectation.
            expected_indicators = set(scanner_service.EXPECTED_INDICATORS)
            expected_ohlcv = {'open', 'high', 'low', 'close', 'volume'}

            total = len(cache)
            today = _pd.Timestamp.now().normalize()
            # Trading-day tolerance: weekends + holidays + market still open
            stale_cutoff = today - _td(days=4)

            schema_issues = {
                'missing_indicators': {},   # indicator -> count of symbols missing it
                'missing_ohlcv': {},        # ohlcv col -> count of symbols missing it
                'bad_index_name': 0,        # symbols where index.name != 'date'
                'non_datetime_index': 0,    # symbols with non-DatetimeIndex
                'duplicate_dates': 0,       # symbols with duplicate index entries
            }
            freshness_buckets = {'today': 0, 'yesterday': 0, 'within_4d': 0, 'stale': 0, 'no_data': 0}
            row_count_dist = {'<50': 0, '50_252': 0, '252_1000': 0, '>1000': 0}
            value_issues = {
                'all_nan_close': 0,
                'negative_close': 0,
                'negative_volume': 0,
                'nan_tail_close': 0,
                'nan_tail_indicators': {ind: 0 for ind in expected_indicators},
            }
            stale_examples = []
            schema_examples = []

            for sym, df in cache.items():
                if df is None or len(df) == 0:
                    freshness_buckets['no_data'] += 1
                    row_count_dist['<50'] += 1
                    continue

                # Row count
                rc = len(df)
                if rc < 50: row_count_dist['<50'] += 1
                elif rc < 252: row_count_dist['50_252'] += 1
                elif rc < 1000: row_count_dist['252_1000'] += 1
                else: row_count_dist['>1000'] += 1

                # Index name
                if df.index.name != 'date':
                    schema_issues['bad_index_name'] += 1
                    if len(schema_examples) < 5:
                        schema_examples.append({"symbol": sym, "issue": f"index.name={df.index.name!r}"})

                # Index type + uniqueness
                if not isinstance(df.index, _pd.DatetimeIndex):
                    schema_issues['non_datetime_index'] += 1
                if df.index.duplicated().any():
                    schema_issues['duplicate_dates'] += 1

                # OHLCV completeness
                cols = set(df.columns)
                for c in expected_ohlcv:
                    if c not in cols:
                        schema_issues['missing_ohlcv'][c] = schema_issues['missing_ohlcv'].get(c, 0) + 1

                # Indicator completeness
                for ind in expected_indicators:
                    if ind not in cols:
                        schema_issues['missing_indicators'][ind] = schema_issues['missing_indicators'].get(ind, 0) + 1

                # Freshness (tz-naive comparison)
                try:
                    last_date = df.index.max()
                    if hasattr(last_date, 'tz') and last_date.tz is not None:
                        last_date = last_date.tz_localize(None)
                    days_old = (today - _pd.Timestamp(last_date).normalize()).days
                    if days_old == 0:
                        freshness_buckets['today'] += 1
                    elif days_old == 1:
                        freshness_buckets['yesterday'] += 1
                    elif days_old <= 4:
                        freshness_buckets['within_4d'] += 1
                    else:
                        freshness_buckets['stale'] += 1
                        if len(stale_examples) < 10:
                            stale_examples.append({
                                "symbol": sym, "last_date": str(last_date)[:10],
                                "days_old": days_old, "rows": rc,
                            })
                except Exception:
                    freshness_buckets['stale'] += 1

                # Value sanity (cheap checks only)
                if 'close' in cols:
                    close = df['close']
                    if close.isna().all():
                        value_issues['all_nan_close'] += 1
                    elif _pd.isna(close.iloc[-1]):
                        value_issues['nan_tail_close'] += 1
                    if (close.dropna() < 0).any():
                        value_issues['negative_close'] += 1
                if 'volume' in cols and (df['volume'].dropna() < 0).any():
                    value_issues['negative_volume'] += 1
                # NaN-tail per indicator (already-present indicators only)
                for ind in expected_indicators:
                    if ind in cols and _pd.isna(df[ind].iloc[-1]):
                        value_issues['nan_tail_indicators'][ind] += 1

            # Verdict
            structural_clean = (
                schema_issues['bad_index_name'] == 0
                and schema_issues['non_datetime_index'] == 0
                and schema_issues['duplicate_dates'] == 0
                and not schema_issues['missing_ohlcv']
                and not schema_issues['missing_indicators']
            )
            freshness_clean = (
                freshness_buckets['stale'] == 0
                and freshness_buckets['no_data'] == 0
            )

            return {
                "status": "ok" if (structural_clean and freshness_clean) else "issues_found",
                "total_symbols": total,
                "schema_issues": schema_issues,
                "schema_examples": schema_examples,
                "freshness": freshness_buckets,
                "stale_examples": stale_examples,
                "row_count_distribution": row_count_dist,
                "value_issues": value_issues,
                "verdict": {
                    "structural_clean": structural_clean,
                    "freshness_clean": freshness_clean,
                    "ready_for_parquet_cutover": structural_clean,
                },
            }

        try:
            return _run_async(_validate())
        except Exception as e:
            import traceback
            return {"status": "failed", "error": str(e), "trace": traceback.format_exc()[:600]}

    # One-time pickle-schema heal: rewrite the production pickle so every
    # symbol carries the full indicator column set AND has canonical
    # index.name='date'. Closes the column_set_diff gap that's been blocking
    # the Stage 3b parquet cutover gate. Safe to re-invoke — it's idempotent.
    # {"parquet_alignment_heal": {"_": 1}}
    if event.get("parquet_alignment_heal"):
        print("🩹 Parquet alignment heal: re-writing pickle with canonical schema")

        async def _heal():
            import time as _time
            from app.services.data_export import data_export_service

            # 1. Force-reload pickle from S3. This goes through _import_from_s3
            #    which now normalizes index.name='date' across all symbols
            #    on read. We need a fresh load — a warm worker may have a
            #    pre-fix cache.
            t0 = _time.time()
            fresh_cache = data_export_service.import_all()
            if not fresh_cache:
                return {"status": "failed", "error": "import_all returned empty cache"}
            print(f"📦 Loaded {len(fresh_cache)} symbols in {_time.time()-t0:.1f}s")

            # 2. Run _ensure_indicators on every symbol. With the new trigger,
            #    any symbol missing ANY indicator (atr in particular) will be
            #    recomputed in this pass.
            t0 = _time.time()
            healed = 0
            empty = 0
            for sym, df in list(fresh_cache.items()):
                if df is None or len(df) == 0:
                    empty += 1
                    continue
                # Track whether recompute fired so we can report progress
                before_cols = set(df.columns)
                new_df = scanner_service._ensure_indicators(df)
                if set(new_df.columns) != before_cols:
                    healed += 1
                fresh_cache[sym] = new_df
            print(f"🔧 _ensure_indicators ran in {_time.time()-t0:.1f}s "
                  f"({healed} symbols gained columns, {empty} empty)")

            # 3. Replace the live scanner cache so subsequent in-process
            #    reads see the canonical schema, then export. export_pickle
            #    applies the index.name='date' normalization on write.
            scanner_service.data_cache = fresh_cache
            t0 = _time.time()
            export_result = data_export_service.export_pickle(fresh_cache)
            print(f"💾 Pickle exported in {_time.time()-t0:.1f}s: {export_result}")

            return {
                "status": "completed" if export_result.get("success") else "export_blocked",
                "symbols_loaded": len(fresh_cache),
                "symbols_healed": healed,
                "empty_symbols": empty,
                "export": export_result,
            }

        try:
            result = _run_async(_heal())
            print(f"🩹 Heal result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Parquet alignment heal failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Handle daily WF cache (chained from daily scan — refreshes simulated portfolio)
    if event.get("daily_wf_cache"):
        print(f"📊 Daily WF cache triggered - {len(scanner_service.data_cache)} symbols in cache")
        async def _run_daily_wf_cache():
            from app.services.scheduler import scheduler_service
            await scheduler_service._run_daily_walk_forward()
            # Also refresh the rolling trailing-365 TIER walk-forward (Preserver/Maximizer) so
            # the Simulated Portfolio card moves daily. Best-effort — never fails the WF cache.
            try:
                from app.services.tier_walkforward_service import compute_tier_walkforward
                from app.services.data_export import data_export_service as _dex
                from sqlalchemy import text as _text
                if 'SPY' not in scanner_service.data_cache:
                    _c = _dex.import_all()
                    if _c:
                        scanner_service.data_cache = _c
                _rmap = {}
                async with async_session() as _rdb:
                    _rr = (await _rdb.execute(_text(
                        "SELECT snapshot_date, current_regime FROM regime_forecast_snapshots "
                        "WHERE snapshot_date >= NOW() - INTERVAL '400 days'"))).all()
                    for _d, _r in _rr:
                        _rmap[_d] = _r
                _tw = compute_tier_walkforward(scanner_service.data_cache, regime_map=_rmap)
                if _tw:
                    _tw["computed_at"] = datetime.now().isoformat()
                    _dex.write_json("tier_walkforward.json", _tw)
                    print(f"📊 Tier WF cached: P {_tw['preserver'].get('total_return_pct')}% / "
                          f"M {_tw['maximizer'].get('total_return_pct')}%")
            except Exception as _twe:
                print(f"⚠️ Tier WF refresh failed (non-fatal): {_twe}")
            return {"status": "success"}

        try:
            result = _run_async(_run_daily_wf_cache())
            print(f"📊 Daily WF cache result: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Daily WF cache failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Standalone rolling trailing-365 TIER walk-forward (manual invoke / validation).
    if event.get("tier_walkforward"):
        print(f"📊 Tier walk-forward triggered - {len(scanner_service.data_cache)} symbols in cache")
        async def _run_tier_wf():
            from app.services.tier_walkforward_service import compute_tier_walkforward
            from app.services.data_export import data_export_service as _dex
            from sqlalchemy import text as _text
            if 'SPY' not in scanner_service.data_cache:
                print("📥 Loading price data from S3 for tier WF...")
                _c = _dex.import_all()
                if _c:
                    scanner_service.data_cache = _c
                    print(f"✅ Loaded {len(_c)} symbols")
            # REAL recorded regime labels the live product uses (regime_forecast_snapshots).
            regime_map = {}
            async with async_session() as _db:
                rows = (await _db.execute(_text(
                    "SELECT snapshot_date, current_regime FROM regime_forecast_snapshots "
                    "WHERE snapshot_date >= NOW() - INTERVAL '400 days'"))).all()
                for d, r in rows:
                    regime_map[d] = r
            print(f"📊 regime_map: {len(regime_map)} recorded days")
            result = compute_tier_walkforward(scanner_service.data_cache, regime_map=regime_map)
            if not result:
                return {"status": "failed", "error": "compute returned None (no regime_map / insufficient data?)"}
            result["computed_at"] = datetime.now().isoformat()
            w = _dex.write_json("tier_walkforward.json", result) if event.get("write", True) else {"skipped": True}
            return {"status": "success", "write": w,
                    "preserver": result.get("preserver"), "maximizer": result.get("maximizer"),
                    "diag": result.get("diag")}
        try:
            result = _run_async(_run_tier_wf())
            print(f"📊 Tier WF result: {result}")
            return result
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"❌ Tier WF failed: {e}\n{tb}")
            return {"status": "failed", "error": str(e), "traceback": tb[:1500]}

    # READ-ONLY Maximizer start-date sweep — how much the (warm-braked) breakout book's current
    # return depends on LAUNCH DATE. Uses the CERTIFIED engine only (maximizer_portfolio.replay_sleeve
    # 'breakout' gated to rotating_bull + vol_scaled_returns) = the pure breakout book (the live
    # MaximizerBook object), NOT the Option-B tier blend. Each variant is WARMED by a ~30-td pre-roll
    # so the sweep isolates launch timing from the (separately fixed) cold-start. No writes/mutation;
    # calls the marketing/WF functions unchanged. Invoke: {"maximizer_start_sweep": {}}.
    if event.get("maximizer_start_sweep") is not None:
        cfg = event.get("maximizer_start_sweep") or {}
        print("📊 Maximizer start-date sweep triggered (read-only)")
        async def _run_sweep():
            import numpy as _np
            import pandas as _pd
            from app.services.data_export import data_export_service as _dex
            from app.services.maximizer_portfolio import replay_sleeve as _rs, vol_scaled_returns as _vsr
            from app.services.tier_walkforward_service import compute_tier_walkforward as _ctw, ROTATING as _ROT
            from sqlalchemy import text as _text
            if 'SPY' not in scanner_service.data_cache:
                _c = _dex.import_all()
                if _c:
                    scanner_service.data_cache = _c
            dc = scanner_service.data_cache
            spy = dc.get('SPY')
            if spy is None or len(spy) < 260:
                return {"status": "failed", "error": "no SPY / insufficient data"}
            idx = _pd.DatetimeIndex(spy.index).normalize()
            end = idx[-1]
            regime_map = {}
            async with async_session() as _db:
                rows = (await _db.execute(_text(
                    "SELECT snapshot_date, current_regime FROM regime_forecast_snapshots "
                    "WHERE snapshot_date >= NOW() - INTERVAL '400 days'"))).all()
                for d, r in rows:
                    regime_map[d] = r
            reg_by_date = {_pd.Timestamp(d).normalize(): v for d, v in regime_map.items()}
            # ANCHOR: run the canonical certified dashboard function in-worker (proves the engine
            # runs + gives the live trailing-365 tier number). NOTE: tier maximizer = Option-B BLEND,
            # which differs from the pure breakout book we sweep — reported side-by-side, not matched.
            anchor = None
            try:
                _tw = _ctw(dc, days=365, regime_map=regime_map)
                if _tw:
                    anchor = {"maximizer_blend": _tw["maximizer"], "preserver": _tw["preserver"],
                              "diag": _tw.get("diag")}
            except Exception as _ae:
                anchor = {"error": str(_ae)}
            def _breakout_vs_eq(start_ts):
                se = _rs(dc, "breakout", start_ts, end, n_positions=15,
                         entry_regimes={_ROT}, regime_by_date=reg_by_date)
                if se is None or len(se) < 5:
                    return None
                vr = _vsr(se).fillna(0.0)
                return _pd.Series((1.0 + vr).cumprod().values,
                                  index=_pd.DatetimeIndex(se.index).normalize())
            # pure-breakout trailing-365 (same object we sweep) — anchor cross-check for sanity
            _t365 = _breakout_vs_eq(end - _pd.Timedelta(days=365))
            breakout_365_total = round((_t365.iloc[-1] / _t365.iloc[0] - 1) * 100, 1) if _t365 is not None else None
            lstart = _pd.Timestamp(cfg.get("start", "2026-06-23")).normalize()
            lend = _pd.Timestamp(cfg.get("end", "2026-08-01")).normalize()
            warm = int(cfg.get("warm_lookback_td", 30))
            grid = [d for d in idx if lstart <= d <= lend]
            if len(grid) > 12:  # bound runtime; keep ~10 + always include the real launch date
                stride = max(1, len(grid) // 10)
                strided = grid[::stride]
                j8 = _pd.Timestamp("2026-07-08")
                if j8 in grid and j8 not in strided:
                    strided.append(j8); strided.sort()
                grid = strided
            results = []
            for L in grid:
                p = int(idx.get_indexer([L])[0])
                if p < 0:
                    continue
                vs = _breakout_vs_eq(idx[max(0, p - warm)])
                if vs is None:
                    continue
                base = vs.asof(L); tip = vs.asof(end)
                if base is None or tip is None or base <= 0 or base != base or tip != tip:
                    continue
                results.append({"launch": L.strftime("%Y-%m-%d"), "ret_pct": round((tip / base - 1) * 100, 2)})
            rets = _np.array([r["ret_pct"] for r in results], dtype=float)
            if len(rets) == 0:
                return {"status": "failed", "error": "no sweep results", "anchor": anchor}
            _pct = lambda q: round(float(_np.percentile(rets, q)), 2)
            spread = {"n": len(rets), "min": round(float(rets.min()), 2), "p25": _pct(25),
                      "median": _pct(50), "mean": round(float(rets.mean()), 2), "p75": _pct(75),
                      "max": round(float(rets.max()), 2),
                      "std": round(float(rets.std(ddof=1)), 2) if len(rets) > 1 else 0.0}
            usd_on_100k = {k: round(100000 * (1 + spread[k] / 100)) for k in ("min", "mean", "max")}
            j8 = next((r for r in results if r["launch"] == "2026-07-08"), None)
            j8_pct = round(float((rets < j8["ret_pct"]).mean() * 100)) if j8 else None
            return {"status": "success", "anchor": anchor,
                    "breakout_trailing365_total_pct": breakout_365_total,
                    "launch_window": [grid[0].strftime("%Y-%m-%d"), grid[-1].strftime("%Y-%m-%d")],
                    "warm_lookback_td": warm, "spread_pct": spread, "usd_on_100k": usd_on_100k,
                    "jul8": j8, "jul8_percentile": j8_pct, "by_launch": results}
        try:
            result = _run_async(_run_sweep())
            print(f"📊 sweep: {result.get('spread_pct')}")
            return result
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"❌ sweep failed: {e}\n{tb}")
            return {"status": "failed", "error": str(e), "traceback": tb[:1500]}

    # Handle regime forecast snapshot (writes to regime_forecast_snapshots table)
    if event.get("regime_forecast_snapshot"):
        print(f"📊 Regime forecast snapshot triggered - {len(scanner_service.data_cache)} symbols in cache")
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
            result = _run_async(_take_regime_snapshot())
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
            result = _run_async(_regime_backfill())
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
            result = _run_async(_regime_history_backfill())
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
            result = _run_async(_persist_signals())
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

                    # Option B (May 17 2026): HWM tracks CLOSE only — matches
                    # the WF-validated strategy. Trigger STILL fires on live
                    # price for intraday alerting. Path B WF test (jobs 1248
                    # vs 1251) confirmed day-high HWM cost -24 pp return.
                    # Pull latest close from cache: yesterday's during market
                    # hours; today's after the 4:30 PM daily scan refresh.
                    df_sym = scanner_service.data_cache.get(sym)
                    if df_sym is not None and not df_sym.empty:
                        latest_close = float(df_sym['close'].iloc[-1])
                        if latest_close > (position.highest_price or position.entry_price):
                            position.highest_price = latest_close

                    # Option C (May 18 2026): intraday monitor DOES NOT send
                    # warn or sell emails to subscribers. Both alert types are
                    # gated to the EOD pass (post-close, in daily_scan handler)
                    # to match WF parity — alerts only fire when CLOSE actually
                    # crosses the stop level. Today's IONQ case: intraday low
                    # tripped at $51.05 with stop $51.20, but the position
                    # closed above stop → model book held, but subscriber got
                    # alerted to sell mid-day and realized a -7.6% loss the
                    # system would have avoided. That's a parity break.
                    #
                    # The intraday monitor still computes guidance for the
                    # details payload (dashboard display) but doesn't email.
                    guidance = sched._check_sell_trigger(position, live_price, regime_forecast)

                    if guidance and guidance['action'] in ('sell', 'warning'):
                        # No email send here — EOD pass handles alerts.
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
                # Path A (May 15 2026): production runs CLOSE-ONLY HWM tracking
                # to match the WF backtester's default mode (intraday_aware=False).
                # The intraday_aware=True mode bundles day-high HWM AND day-low
                # trigger — that bundle showed -17pp ann in b-full validation.
                # The asymmetric "day-high HWM + close trigger" variant has NEVER
                # been WF-validated, so we don't run it in production. Until that
                # validation lands (Path B research), production uses close-only.
                model_closed = []
                try:
                    from app.services.model_portfolio_service import model_portfolio_service
                    model_closed = await model_portfolio_service.process_live_exits(
                        db, live_prices, regime_forecast
                    )
                    if model_closed:
                        print(f"📈 [MODEL-LIVE] Closed {len(model_closed)} position(s): {[c.get('symbol') for c in model_closed]}")
                        await _notify_portfolio_change("SELL", model_closed)
                except Exception as e:
                    print(f"⚠️ [MODEL-LIVE] Exit check failed: {e}")

                # --- Signal track record: check intraday exits ---
                try:
                    from app.services.model_portfolio_service import model_portfolio_service
                    # Same Path A close-only constraint as live portfolio above.
                    st_closed = await model_portfolio_service.process_signal_track_exits(
                        db,
                        live_prices=live_prices,
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
            result = _run_async(_run_intraday_monitor())
            print(f"📡 Intraday monitor: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ Intraday monitor failed: {e}")
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}

    # Inspect parquet divergence events — drills into the details_json for the
    # most recent N events of a given type. Used to verify what's actually
    # diverging before deciding whether to fix parquet, fix pickle, or
    # canonicalize the diff harness. Returns a deduplicated view of the
    # only_in_pickle / only_in_parquet column lists so we can see the shape
    # of the drift at a glance.
    # {"parquet_divergence_inspect": {"type": "column_set_diff", "limit": 50}}
    if event.get("parquet_divergence_inspect"):
        cfg = event["parquet_divergence_inspect"]
        div_type = cfg.get("type", "column_set_diff")
        limit = int(cfg.get("limit", 50))

        async def _inspect():
            from app.core.database import ParquetDivergenceEvent
            from sqlalchemy import select, desc
            import json as _json
            from collections import Counter

            async with async_session() as db:
                rows = (await db.execute(
                    select(ParquetDivergenceEvent)
                    .where(ParquetDivergenceEvent.divergence_type == div_type)
                    .order_by(desc(ParquetDivergenceEvent.detected_at))
                    .limit(limit)
                )).scalars().all()

            shape_counter: Counter = Counter()
            samples = []
            for r in rows:
                try:
                    details = _json.loads(r.details_json) if r.details_json else {}
                except Exception:
                    details = {}
                only_p = tuple(sorted(details.get("only_in_pickle", [])))
                only_q = tuple(sorted(details.get("only_in_parquet", [])))
                shape = (only_p, only_q)
                shape_counter[shape] += 1
                if len(samples) < 10:
                    samples.append({
                        "symbol": r.symbol,
                        "detected_at": r.detected_at.isoformat() if r.detected_at else None,
                        "only_in_pickle": list(only_p),
                        "only_in_parquet": list(only_q),
                        "pickle_rows": r.pickle_row_count,
                        "parquet_rows": r.parquet_row_count,
                    })

            shapes_summary = [
                {
                    "only_in_pickle": list(p),
                    "only_in_parquet": list(q),
                    "count": n,
                }
                for (p, q), n in shape_counter.most_common()
            ]
            return {
                "type": div_type,
                "events_inspected": len(rows),
                "distinct_shapes": shapes_summary,
                "sample_events": samples,
            }

        try:
            return _run_async(_inspect())
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:500]}

    # Query walk-forward job details (read-only)
    if event.get("wf_query"):
        config = event["wf_query"]
        job_id = config.get("job_id")

        async def _wf_query():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.get_simulation_details(db, job_id)

        result = _run_async(_wf_query())
        return result or {"error": f"Job {job_id} not found"}

    # Handle model portfolio operations
    if event.get("model_portfolio"):
        config = event["model_portfolio"]
        action = config.get("action", "summary")
        portfolio_type = config.get("portfolio_type")  # None = both

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

                elif action == "audit_str_resignals":
                    start_date = config.get("start_date", "2026-04-15")
                    end_date = config.get("end_date")
                    return await model_portfolio_service.audit_str_resignals(db, start_date, end_date)

                elif action == "backfill_str_resignals":
                    start_date = config.get("start_date", "2026-04-15")
                    end_date = config.get("end_date")
                    dry_run = config.get("dry_run", True)
                    return await model_portfolio_service.backfill_str_resignals(
                        db, start_date, end_date, dry_run
                    )

                elif action == "generate_autopsies":
                    from app.services.trade_autopsy_service import trade_autopsy_service
                    limit = config.get("limit", 20)
                    return await trade_autopsy_service.bulk_generate(db, portfolio_type, limit)

                else:
                    return {"error": f"Unknown action: {action}"}

        result = _run_async(_run_model_portfolio())
        return result

    # Methodology v2 — native standalone backtester invocation. Same code
    # path as scripts/wf_native_t3_sweep.py but runs in Lambda for true
    # production-runtime parity. Returns the same JSON shape the local
    # script writes, including the v2 MANIFEST fields.
    #
    # Payload schema:
    #   {"native_backtest": {
    #       "start_date": "YYYY-MM-DD",
    #       "end_date":   "YYYY-MM-DD",
    #       "max_symbols": 100,                       # required
    #       "dd_threshold_pct": 10.0,                 # optional, 0=off
    #       "tight_stop_pct":   8.0,                  # optional
    #       "baseline_stop_pct": 12.0,                # optional
    #       "dwap_threshold_pct": 5.0,                # optional override
    #       "near_50d_high_pct": 3.0,                 # optional override
    #       "max_positions":     6,                   # optional override
    #       "position_size_pct": 15.0,                # optional override
    #       "profit_lock_pct":   0.0,                 # optional, 0=off
    #       "profit_lock_stop_pct": 6.0,              # optional
    #       "strategy_type":     "ensemble"           # optional, default "ensemble"
    #   }}
    if event.get("native_backtest"):
        cfg = event["native_backtest"]
        async def _run_native_backtest():
            import hashlib, time as _t
            from app.services.backtester import BacktesterService
            from app.services.scanner import scanner_service
            from app.services.walk_forward_service import walk_forward_service

            start_date = datetime.strptime(cfg["start_date"], "%Y-%m-%d")
            end_date = datetime.strptime(cfg["end_date"], "%Y-%m-%d")
            max_symbols = int(cfg.get("max_symbols", 100))

            # Filter universe to top-N by liquidity as-of start (matches local script)
            top_symbols = walk_forward_service._get_top_symbols_as_of(start_date, max_symbols)
            full_cache = scanner_service.data_cache
            saved_cache = full_cache  # for restore
            scanner_service.data_cache = {s: full_cache[s] for s in top_symbols if s in full_cache}
            # SPY needed for market_regime check; ^VIX needed for vix_scale lever.
            # Both are index symbols (not in top-N by liquidity), force-add them.
            for ix_sym in ("SPY", "^VIX"):
                if ix_sym in full_cache and ix_sym not in scanner_service.data_cache:
                    scanner_service.data_cache[ix_sym] = full_cache[ix_sym]
            # Force-add any cb_pause_basket symbols not in top-N (so defensive
            # basket symbols like JPM/JNJ/PG that may not always be top-liquidity
            # are still tradable). Basket symbols come from cfg, fall back to
            # backtester defaults.
            basket_syms = cfg.get("cb_pause_basket_symbols")
            if not basket_syms:
                # Use defaults from a fresh backtester for force-add purposes
                from app.services.backtester import BacktesterService as _BS
                basket_syms = _BS().cb_pause_basket_symbols
            basket_syms = list(basket_syms)
            # Point-in-time basket: force-add the union of all snapshot symbols
            # so names that drop out of the live universe (BRK-B, JPM, ...) are
            # still tradable when a historical snapshot calls for them.
            for _d, _syms in (cfg.get("cb_pause_basket_dynamic") or []):
                basket_syms.extend(_syms)
            for bs in basket_syms:
                if bs in full_cache and bs not in scanner_service.data_cache:
                    scanner_service.data_cache[bs] = full_cache[bs]
            scanner_service.universe = list(scanner_service.data_cache.keys())
            print(f"[native_backtest] {len(scanner_service.data_cache)} symbols (top-{max_symbols})")

            try:
                bt = BacktesterService()
                bt.trailing_stop_pct = float(cfg.get("baseline_stop_pct", 12.0)) / 100.0
                bt.dd_tighten_threshold_pct = float(cfg.get("dd_threshold_pct", 0))
                bt.dd_tighten_stop_pct = float(cfg.get("tight_stop_pct", 8.0))
                if "dwap_threshold_pct" in cfg:
                    bt.dwap_threshold_pct = float(cfg["dwap_threshold_pct"]) / 100.0
                if "near_50d_high_pct" in cfg:
                    bt.near_50d_high_pct = float(cfg["near_50d_high_pct"])
                if "max_positions" in cfg:
                    bt.max_positions = int(cfg["max_positions"])
                if "position_size_pct" in cfg:
                    bt.position_size_pct = float(cfg["position_size_pct"]) / 100.0
                if "profit_lock_pct" in cfg:
                    bt.profit_lock_pct = float(cfg["profit_lock_pct"])
                if "profit_lock_stop_pct" in cfg:
                    bt.profit_lock_stop_pct = float(cfg["profit_lock_stop_pct"])
                # VIX-conditional sizing (A1)
                if "vix_scale_enabled" in cfg:
                    bt.vix_scale_enabled = bool(cfg["vix_scale_enabled"])
                if "vix_scale_threshold" in cfg:
                    bt.vix_scale_threshold = float(cfg["vix_scale_threshold"])
                if "vix_scale_factor" in cfg:
                    bt.vix_scale_factor = float(cfg["vix_scale_factor"])
                # Drawdown circuit breaker — size cut when portfolio DD ≥ threshold
                if "dd_cb_enabled" in cfg:
                    bt.dd_cb_enabled = bool(cfg["dd_cb_enabled"])
                if "dd_cb_threshold" in cfg:
                    bt.dd_cb_threshold = float(cfg["dd_cb_threshold"])
                if "dd_cb_size_factor" in cfg:
                    bt.dd_cb_size_factor = float(cfg["dd_cb_size_factor"])
                # Hard DD-exit (close all on portfolio DD ≥ threshold)
                if "hard_dd_exit_threshold_pct" in cfg:
                    bt.hard_dd_exit_threshold_pct = float(cfg["hard_dd_exit_threshold_pct"])
                if "hard_dd_exit_pause_days" in cfg:
                    bt.hard_dd_exit_pause_days = int(cfg["hard_dd_exit_pause_days"])
                # Profit-lock floor (different from B1's profit_lock trail-tighten)
                if "profit_lock_floor_trigger_pct" in cfg:
                    bt.profit_lock_floor_trigger_pct = float(cfg["profit_lock_floor_trigger_pct"])
                if "profit_lock_floor_pct" in cfg:
                    bt.profit_lock_floor_pct = float(cfg["profit_lock_floor_pct"])
                # Sector RS (orthogonal alpha — RS1 binary filter + RS3 additive)
                sector_rs_filter = bool(cfg.get("sector_rs_filter_enabled", False))
                sector_rs_score = bool(cfg.get("sector_rs_score_enabled", False))
                if sector_rs_filter or sector_rs_score:
                    # Load sectors from S3 once per Lambda invocation
                    try:
                        import boto3, json as _json
                        _s3 = boto3.client("s3", region_name="us-east-1")
                        _obj = _s3.get_object(
                            Bucket="rigacap-prod-price-data-149218244179",
                            Key="universe/sectors_cache.json")
                        _sectors = _json.loads(_obj["Body"].read())
                        bt.symbol_sectors = {sym: data.get("sector", "")
                                              for sym, data in _sectors.items()
                                              if data.get("sector")}
                        print(f"[native_backtest] Loaded sectors for {len(bt.symbol_sectors)} symbols")
                    except Exception as e:
                        print(f"[native_backtest] WARN sector load failed: {e}")
                        bt.symbol_sectors = {}
                    bt.sector_rs_filter_enabled = sector_rs_filter
                    bt.sector_rs_score_enabled = sector_rs_score
                    if "sector_rs_lookback_days" in cfg:
                        bt.sector_rs_lookback_days = int(cfg["sector_rs_lookback_days"])
                    if "sector_rs_min_threshold" in cfg:
                        bt.sector_rs_min_threshold = float(cfg["sector_rs_min_threshold"])
                    if "sector_rs_score_weight" in cfg:
                        bt.sector_rs_score_weight = float(cfg["sector_rs_score_weight"])
                    if "sector_rs_regime_gated" in cfg:
                        bt.sector_rs_regime_gated = bool(cfg["sector_rs_regime_gated"])
                # News-volume signal (NV1/NV2/NV3 — orthogonal alpha Jun 3 2026)
                nv_filter = bool(cfg.get("news_volume_filter_enabled", False))
                nv_score = bool(cfg.get("news_volume_score_enabled", False))
                if nv_filter or nv_score:
                    try:
                        import boto3, io as _io
                        import pandas as _pd
                        _s3 = boto3.client("s3", region_name="us-east-1")
                        _obj = _s3.get_object(
                            Bucket="rigacap-prod-price-data-149218244179",
                            Key="research/news_counts/counts.parquet")
                        _df = _pd.read_parquet(_io.BytesIO(_obj["Body"].read()))
                        _counts_by_sym = {}
                        for sym, grp in _df.groupby("symbol"):
                            _counts_by_sym[sym] = {
                                d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]: int(c)
                                for d, c in zip(grp["date"], grp["article_count"])
                            }
                        bt.symbol_news_counts = _counts_by_sym
                        print(f"[native_backtest] Loaded news counts for {len(bt.symbol_news_counts)} symbols")
                    except Exception as e:
                        print(f"[native_backtest] WARN news load failed: {e}")
                        bt.symbol_news_counts = {}
                    bt.news_volume_filter_enabled = nv_filter
                    bt.news_volume_score_enabled = nv_score
                    if "news_volume_threshold" in cfg:
                        bt.news_volume_threshold = float(cfg["news_volume_threshold"])
                    if "news_volume_score_threshold" in cfg:
                        bt.news_volume_score_threshold = float(cfg["news_volume_score_threshold"])
                    if "news_volume_score_weight" in cfg:
                        bt.news_volume_score_weight = float(cfg["news_volume_score_weight"])
                    if "news_volume_lookback_short" in cfg:
                        bt.news_volume_lookback_short = int(cfg["news_volume_lookback_short"])
                    if "news_volume_lookback_long" in cfg:
                        bt.news_volume_lookback_long = int(cfg["news_volume_lookback_long"])
                    if "news_volume_regime_gated" in cfg:
                        bt.news_volume_regime_gated = bool(cfg["news_volume_regime_gated"])
                # News-SENTIMENT (Path B — Haiku-scored polarity)
                ns_filter = bool(cfg.get("news_sentiment_filter_enabled", False))
                ns_score = bool(cfg.get("news_sentiment_score_enabled", False))
                ns_exit = bool(cfg.get("news_sentiment_exit_enabled", False))
                ns_trail = bool(cfg.get("news_sentiment_trail_enabled", False))
                ns_sizing = bool(cfg.get("news_sentiment_sizing_enabled", False))
                if ns_filter or ns_score or ns_exit or ns_trail or ns_sizing:
                    try:
                        import boto3, io as _io
                        import pandas as _pd
                        _s3 = boto3.client("s3", region_name="us-east-1")
                        _obj = _s3.get_object(
                            Bucket="rigacap-prod-price-data-149218244179",
                            Key="research/news_sentiment/sentiment_daily.parquet")
                        _df = _pd.read_parquet(_io.BytesIO(_obj["Body"].read()))
                        _sent_by_sym = {}
                        for sym, grp in _df.groupby("symbol"):
                            _sent_by_sym[sym] = {
                                d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]: float(s)
                                for d, s in zip(grp["date"], grp["sentiment_mean"])
                            }
                        bt.symbol_news_sentiment = _sent_by_sym
                        print(f"[native_backtest] Loaded sentiment for {len(bt.symbol_news_sentiment)} symbols")
                    except Exception as e:
                        print(f"[native_backtest] WARN sentiment load failed: {e}")
                        bt.symbol_news_sentiment = {}
                    bt.news_sentiment_filter_enabled = ns_filter
                    bt.news_sentiment_score_enabled = ns_score
                    if "news_sentiment_threshold" in cfg:
                        bt.news_sentiment_threshold = float(cfg["news_sentiment_threshold"])
                    if "news_sentiment_score_weight" in cfg:
                        bt.news_sentiment_score_weight = float(cfg["news_sentiment_score_weight"])
                    if "news_sentiment_lookback_days" in cfg:
                        bt.news_sentiment_lookback_days = int(cfg["news_sentiment_lookback_days"])
                    if "news_sentiment_regime_gated" in cfg:
                        bt.news_sentiment_regime_gated = bool(cfg["news_sentiment_regime_gated"])
                    if ns_exit:
                        bt.news_sentiment_exit_enabled = True
                        if "news_sentiment_exit_threshold" in cfg:
                            bt.news_sentiment_exit_threshold = float(cfg["news_sentiment_exit_threshold"])
                        if "news_sentiment_exit_lookback_days" in cfg:
                            bt.news_sentiment_exit_lookback_days = int(cfg["news_sentiment_exit_lookback_days"])
                    if ns_trail:
                        bt.news_sentiment_trail_enabled = True
                        if "news_sentiment_trail_scale" in cfg:
                            bt.news_sentiment_trail_scale = float(cfg["news_sentiment_trail_scale"])
                        if "news_sentiment_trail_lookback_days" in cfg:
                            bt.news_sentiment_trail_lookback_days = int(cfg["news_sentiment_trail_lookback_days"])
                        if "news_sentiment_trail_min_pct" in cfg:
                            bt.news_sentiment_trail_min_pct = float(cfg["news_sentiment_trail_min_pct"])
                        if "news_sentiment_trail_max_pct" in cfg:
                            bt.news_sentiment_trail_max_pct = float(cfg["news_sentiment_trail_max_pct"])
                    if ns_sizing:
                        bt.news_sentiment_sizing_enabled = True
                        if "news_sentiment_sizing_scale" in cfg:
                            bt.news_sentiment_sizing_scale = float(cfg["news_sentiment_sizing_scale"])
                        if "news_sentiment_sizing_lookback_days" in cfg:
                            bt.news_sentiment_sizing_lookback_days = int(cfg["news_sentiment_sizing_lookback_days"])
                        if "news_sentiment_sizing_min_factor" in cfg:
                            bt.news_sentiment_sizing_min_factor = float(cfg["news_sentiment_sizing_min_factor"])
                        if "news_sentiment_sizing_max_factor" in cfg:
                            bt.news_sentiment_sizing_max_factor = float(cfg["news_sentiment_sizing_max_factor"])
                # Cascade Guard pause basket (M1 — universal-rule compound)
                if "cb_pause_basket_enabled" in cfg:
                    bt.cb_pause_basket_enabled = bool(cfg["cb_pause_basket_enabled"])
                if "cb_pause_basket_symbols" in cfg:
                    bt.cb_pause_basket_symbols = list(cfg["cb_pause_basket_symbols"])
                if cfg.get("cb_pause_basket_dynamic"):
                    # Point-in-time basket: [[date_str, [syms]], ...] -> sorted
                    # [(Timestamp, [syms])]. Research look-ahead validation.
                    import pandas as _pd
                    bt.cb_pause_basket_dynamic = sorted(
                        [(_pd.Timestamp(_d), list(_syms)) for _d, _syms in cfg["cb_pause_basket_dynamic"]],
                        key=lambda x: x[0])
                if "cb_pause_basket_position_size_pct" in cfg:
                    bt.cb_pause_basket_position_size_pct = float(cfg["cb_pause_basket_position_size_pct"])
                if "cb_pause_basket_trail_pct" in cfg:
                    bt.cb_pause_basket_trail_pct = float(cfg["cb_pause_basket_trail_pct"])
                if "cb_pause_basket_vix_trigger" in cfg:
                    bt.cb_pause_basket_vix_trigger = float(cfg["cb_pause_basket_vix_trigger"])
                # Universe / entry filter overrides
                if "min_price" in cfg:
                    bt.min_price = float(cfg["min_price"])
                # Additive levers — breakeven floor + pyramid (already in backtester)
                if "breakeven_pct" in cfg:
                    bt.breakeven_pct = float(cfg["breakeven_pct"])
                if "pyramid_threshold_pct" in cfg:
                    bt.pyramid_threshold_pct = float(cfg["pyramid_threshold_pct"])
                if "pyramid_size_pct" in cfg:
                    bt.pyramid_size_pct = float(cfg["pyramid_size_pct"])
                if "pyramid_max_adds" in cfg:
                    bt.pyramid_max_adds = int(cfg["pyramid_max_adds"])

                strategy_type = cfg.get("strategy_type", "ensemble")
                print(f"[native_backtest] trail={bt.trailing_stop_pct*100:.1f}% baseline, "
                      f"dd_tighten={bt.dd_tighten_threshold_pct}%/{bt.dd_tighten_stop_pct}%, "
                      f"profit_lock={bt.profit_lock_pct}%/{bt.profit_lock_stop_pct}%, "
                      f"max_pos={bt.max_positions}, size={bt.position_size_pct*100:.1f}%, "
                      f"dwap={bt.dwap_threshold_pct*100:.1f}%, near50={bt.near_50d_high_pct}%")

                t0 = _t.time()
                result = bt.run_backtest(
                    start_date=start_date,
                    end_date=end_date,
                    strategy_type=strategy_type,
                    force_close_at_end=False,
                )
                dur = _t.time() - t0

                years = (end_date - start_date).days / 365.25
                ann = (1 + result.total_return_pct / 100) ** (1 / years) - 1
                mdd = result.max_drawdown_pct
                calmar = (ann * 100) / mdd if mdd else 0

                # Warmup metadata
                import pandas as pd
                spy_df = saved_cache.get("SPY")
                if spy_df is not None and not spy_df.empty:
                    pickle_first_date = pd.Timestamp(spy_df.index.min()).normalize()
                    warmup_calendar_days = max(0, (pd.Timestamp(start_date) - pickle_first_date).days)
                else:
                    warmup_calendar_days = 0
                warmup_trading_days_est = int(warmup_calendar_days * 252 / 365)

                return {
                    "start_date": cfg["start_date"],
                    "end_date": cfg["end_date"],
                    "dd_threshold_pct": bt.dd_tighten_threshold_pct,
                    "tight_stop_pct": bt.dd_tighten_stop_pct,
                    "baseline_stop_pct": bt.trailing_stop_pct * 100,
                    "dwap_threshold_pct": bt.dwap_threshold_pct * 100,
                    "near_50d_high_pct": bt.near_50d_high_pct,
                    "max_positions": bt.max_positions,
                    "position_size_pct": bt.position_size_pct * 100,
                    "profit_lock_pct": bt.profit_lock_pct,
                    "profit_lock_stop_pct": bt.profit_lock_stop_pct,
                    "cb_pause_basket_enabled": bt.cb_pause_basket_enabled,
                    "cb_pause_basket_symbols": list(bt.cb_pause_basket_symbols),
                    "cb_pause_basket_position_size_pct": bt.cb_pause_basket_position_size_pct,
                    "cb_pause_basket_trail_pct": bt.cb_pause_basket_trail_pct,
                    "cb_pause_basket_vix_trigger": bt.cb_pause_basket_vix_trigger,
                    "min_price": bt.min_price,
                    "breakeven_pct": bt.breakeven_pct,
                    "pyramid_threshold_pct": bt.pyramid_threshold_pct,
                    "pyramid_size_pct": bt.pyramid_size_pct,
                    "pyramid_max_adds": bt.pyramid_max_adds,
                    "vix_scale_enabled": bt.vix_scale_enabled,
                    "vix_scale_threshold": bt.vix_scale_threshold,
                    "vix_scale_factor": bt.vix_scale_factor,
                    "dd_cb_enabled": bt.dd_cb_enabled,
                    "dd_cb_threshold": bt.dd_cb_threshold,
                    "dd_cb_size_factor": bt.dd_cb_size_factor,
                    "hard_dd_exit_threshold_pct": bt.hard_dd_exit_threshold_pct,
                    "hard_dd_exit_pause_days": bt.hard_dd_exit_pause_days,
                    "profit_lock_floor_trigger_pct": bt.profit_lock_floor_trigger_pct,
                    "profit_lock_floor_pct": bt.profit_lock_floor_pct,
                    "sector_rs_filter_enabled": bt.sector_rs_filter_enabled,
                    "sector_rs_score_enabled": bt.sector_rs_score_enabled,
                    "sector_rs_lookback_days": bt.sector_rs_lookback_days,
                    "sector_rs_min_threshold": bt.sector_rs_min_threshold,
                    "sector_rs_score_weight": bt.sector_rs_score_weight,
                    "sector_rs_regime_gated": bt.sector_rs_regime_gated,
                    "sector_count_loaded": len(bt.symbol_sectors),
                    "news_volume_filter_enabled": bt.news_volume_filter_enabled,
                    "news_volume_score_enabled": bt.news_volume_score_enabled,
                    "news_volume_threshold": bt.news_volume_threshold,
                    "news_volume_score_threshold": bt.news_volume_score_threshold,
                    "news_volume_score_weight": bt.news_volume_score_weight,
                    "news_volume_regime_gated": bt.news_volume_regime_gated,
                    "news_symbol_count_loaded": len(bt.symbol_news_counts),
                    "news_sentiment_filter_enabled": bt.news_sentiment_filter_enabled,
                    "news_sentiment_score_enabled": bt.news_sentiment_score_enabled,
                    "news_sentiment_threshold": bt.news_sentiment_threshold,
                    "news_sentiment_score_weight": bt.news_sentiment_score_weight,
                    "news_sentiment_regime_gated": bt.news_sentiment_regime_gated,
                    "news_sentiment_exit_enabled": bt.news_sentiment_exit_enabled,
                    "news_sentiment_exit_threshold": bt.news_sentiment_exit_threshold,
                    "news_sentiment_exit_lookback_days": bt.news_sentiment_exit_lookback_days,
                    "news_sentiment_trail_enabled": bt.news_sentiment_trail_enabled,
                    "news_sentiment_trail_scale": bt.news_sentiment_trail_scale,
                    "news_sentiment_trail_lookback_days": bt.news_sentiment_trail_lookback_days,
                    "news_sentiment_trail_min_pct": bt.news_sentiment_trail_min_pct,
                    "news_sentiment_trail_max_pct": bt.news_sentiment_trail_max_pct,
                    "news_sentiment_sizing_enabled": bt.news_sentiment_sizing_enabled,
                    "news_sentiment_sizing_scale": bt.news_sentiment_sizing_scale,
                    "news_sentiment_sizing_lookback_days": bt.news_sentiment_sizing_lookback_days,
                    "news_sentiment_sizing_min_factor": bt.news_sentiment_sizing_min_factor,
                    "news_sentiment_sizing_max_factor": bt.news_sentiment_sizing_max_factor,
                    "news_sentiment_symbol_count_loaded": len(bt.symbol_news_sentiment),
                    "universe_size": max_symbols,
                    "strategy_type": strategy_type,
                    "total_return_pct": result.total_return_pct,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown_pct": mdd,
                    "calmar": calmar,
                    "annualized_pct": ann * 100,
                    "trades_count": len(result.trades),
                    "duration_sec": dur,
                    "warmup_calendar_days_available": warmup_calendar_days,
                    "warmup_trading_days_est": warmup_trading_days_est,
                    "warmup_v2_target_met": warmup_trading_days_est >= 130,
                    "methodology_version": "v2",
                    "runtime": "lambda_worker",
                    "lambda_function_version": os.environ.get("AWS_LAMBDA_FUNCTION_VERSION", "$LATEST"),
                }
            finally:
                # Restore full data_cache for any subsequent invocations on warm container
                scanner_service.data_cache = saved_cache
                scanner_service.universe = list(saved_cache.keys())

        result = _run_async(_run_native_backtest())
        return result

    # Handle async walk-forward jobs (supports self-chaining via wf_state_key)
    if event.get("walk_forward_job"):
        wf_state_key = event.get("wf_state_key")
        print(f"📊 Walk-forward async job received - {len(scanner_service.data_cache)} symbols in cache, "
              f"SPY={'SPY' in scanner_service.data_cache}"
              + (f", continuation={wf_state_key}" if wf_state_key else ""))
        job_config = event["walk_forward_job"]
        result = _run_async(_run_walk_forward_job(job_config, wf_state_key=wf_state_key))
        return result

    # Handle Step Functions walk-forward: init
    if event.get("wf_init"):
        print(f"📊 WF-INIT: Step Functions initialization")
        config = event["wf_init"]
        async def _run_wf_init():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.init_simulation(db, config)

        try:
            result = _run_async(_run_wf_init())
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
        async def _run_wf_period():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.run_single_period(db, state)

        try:
            result = _run_async(_run_wf_period())
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
        async def _run_wf_finalize():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.finalize_simulation(db, state)

        try:
            result = _run_async(_run_wf_finalize())
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
        async def _run_wf_fail():
            from app.services.walk_forward_service import walk_forward_service
            async with async_session() as db:
                return await walk_forward_service.mark_simulation_failed(db, state, error_msg)

        try:
            result = _run_async(_run_wf_fail())
            return result
        except Exception as e:
            print(f"❌ WF-FAIL handler itself failed: {e}")
            return {"error": str(e)}

    # Handle nightly walk-forward job (direct Lambda invocation).
    #
    # Previously this ran as a single monolithic call to the WF service. With
    # the larger universe + per-period optimizer work it now exceeds Lambda's
    # 900s ceiling, AWS auto-retries the same RequestId twice, all three time
    # out, and the simulation row is stranded at status='running' — starving
    # both the dashboard's Missed Opportunities widget and the social-content
    # AI pipeline (next-day fallback to yesterday's data masks but doesn't fix
    # the silent failure).
    #
    # Fix: bootstrap the simulation row here, then delegate to the chunked,
    # self-chaining _run_walk_forward_job. The runner processes `periods_limit`
    # periods per Lambda invocation, persists continuation state to S3, and
    # async-invokes itself for the next chunk until done. The social-content
    # step fires from _run_walk_forward_job's final-chunk completion path when
    # nightly_post_complete=True (see the post-completion hook there).
    if "nightly_wf_job" in event:
        print(f"🌙 Nightly WF job received - {len(scanner_service.data_cache)} symbols in cache")
        config = event["nightly_wf_job"] or {}

        async def _bootstrap_nightly_wf():
            from datetime import timedelta
            from app.core.database import WalkForwardSimulation

            days_back = config.get("days_back", 90)
            strategy_id = config.get("strategy_id", 5)
            max_symbols = config.get("max_symbols", 500)
            # 1 biweekly period per chunk = ~3-5 min per Lambda + ~half the
            # peak memory footprint of the 2-period chunks. Reduced from 2
            # after May 13 OOM kill (3008/3008 MB peak). A 90-day window
            # produces ~7 periods so 7 chunks total — well under the 15-min
            # ceiling, and each chunk has plenty of memory headroom.
            # Parquet migration will further reduce this since each chunk
            # can partial-read by symbol rather than holding the full pickle.
            periods_limit = config.get("periods_limit", 1)

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            async with async_session() as db:
                # Append-only: never delete prior nightly cache rows. Readers
                # do ORDER BY simulation_date DESC LIMIT 1 with status='completed',
                # so latest-completed semantics are preserved without a DELETE
                # that would race the FK on walk_forward_period_results.
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
                print(f"[NIGHTLY-WF] Created job {job_id} ({days_back}d, biweekly, "
                      f"periods_limit={periods_limit}, max_symbols={max_symbols})")

            return {
                "job_id": job_id,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "frequency": "biweekly",
                "strategy_id": strategy_id,
                "max_symbols": max_symbols,
                "carry_positions": True,
                "min_score_diff": 10.0,
                "enable_ai": False,
                "periods_limit": periods_limit,
                "nightly_post_complete": True,  # trigger social-content step on final chunk
            }

        try:
            job_config = _run_async(_bootstrap_nightly_wf())
            # Hand off to the chunked, self-chaining runner. The first chunk
            # runs in this same Lambda invocation; subsequent chunks are
            # async-invoked by the runner itself.
            result = _run_async(_run_walk_forward_job(job_config))
            return result
        except Exception as e:
            import traceback
            print(f"❌ Nightly WF bootstrap failed: {e}")
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
            result = _run_async(_get_walk_forward_history(event.get("limit", 10)))
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
            result = _run_async(_get_walk_forward_trades(simulation_id))
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
            result = _run_async(_refresh_volume())
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
            result = _run_async(_compare_sources())
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
            result = _run_async(_test_ai_content())
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
            result = _run_async(_heygen_video())
            return result
        except Exception as e:
            import traceback
            print(f"❌ HeyGen video failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Generate AI posts from real WF trades and save to DB (direct Lambda invocation)
    # Weekly-ish original research-insight posts (Jun 24 2026). Fires DAILY but a
    # random gate means some days produce a draft and some don't → naturally
    # varying 1-4/week (never a fixed day). Each lands as a DRAFT in the Social
    # tab for Erik to approve -> schedule or post-now. {"prob": 0.4} overrides
    # the daily probability; {"force": true} always generates (for testing).
    # DR: snapshot both Lambdas' live env to encrypted S3 (mirror of
    # scripts/backup-lambda-env.sh, runnable on a schedule). Env is managed
    # out-of-band + terraform-ignored, so this is the recovery artifact.
    if event.get("backup_lambda_env"):
        print("💾 DR: backing up Lambda env to S3")

        def _backup_lambda_env():
            import boto3, json as _json
            from datetime import datetime as _dt
            lam = boto3.client("lambda")
            s3 = boto3.client("s3")
            bucket = os.environ.get("PRICE_DATA_BUCKET")
            if not bucket:
                return {"status": "error", "error": "PRICE_DATA_BUCKET not set"}
            worker_fn = os.environ.get("WORKER_FUNCTION_NAME", "rigacap-prod-worker")
            api_fn = worker_fn.replace("-worker", "-api")
            stamp = _dt.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
            out = {}
            for fn in (worker_fn, api_fn):
                cfg = lam.get_function_configuration(FunctionName=fn)
                envv = (cfg.get("Environment") or {}).get("Variables") or {}
                if len(envv) < 30:
                    out[fn] = {"error": f"only {len(envv)} keys — refused (partial)"}
                    continue
                body = _json.dumps(envv, indent=2).encode()
                for key in (f"dr/lambda-env/{fn}-{stamp}.json", f"dr/lambda-env/{fn}-latest.json"):
                    s3.put_object(Bucket=bucket, Key=key, Body=body,
                                  ServerSideEncryption="AES256", ContentType="application/json")
                out[fn] = {"keys": len(envv), "snapshot": f"dr/lambda-env/{fn}-{stamp}.json"}
            return {"status": "ok", "backed_up": out}

        try:
            return _backup_lambda_env()
        except Exception as e:
            import traceback
            print(f"❌ backup_lambda_env failed: {e}\n{traceback.format_exc()}")
            return {"status": "error", "error": str(e)}

    # AUTOPOST own-social cadence (Mon/Wed/Fri): generate ONE tier-forked research-insight,
    # schedule it a few hours out, and email Erik a heads-up with a one-click KILL link.
    # Auto-publishes unless killed (own-posts are not 403-blocked like replies). 8-day
    # anti-repeat lookback so the feed doesn't sound like a machine.
    if "autopost_own_social" in event:
        _acfg = event.get("autopost_own_social") if isinstance(event.get("autopost_own_social"), dict) else {}
        print(f"📣 Autopost own-social: {_acfg}")

        async def _autopost_own_social():
            from datetime import datetime, timedelta
            from sqlalchemy import select, desc
            from app.services.ai_content_service import ai_content_service
            from app.services.post_scheduler_service import post_scheduler_service
            from app.services.email_service import admin_email_service
            from app.core.database import SocialPost as _SP
            try:
                import pytz as _pytz
            except Exception:
                _pytz = None

            now = datetime.utcnow()
            # Alternate Preserver/Maximizer across posting days (iso-week * 3 + M/W/F slot).
            tier = _acfg.get("tier")
            if tier not in ("preserver", "maximizer"):
                slot = {0: 0, 2: 1, 4: 2}.get(now.weekday(), 0)
                occ = now.isocalendar()[1] * 3 + slot
                tier = "preserver" if occ % 2 == 0 else "maximizer"

            platforms = _acfg.get("platforms", ["twitter", "threads", "instagram"])
            window_hours = _acfg.get("window_hours", 4)
            dry_run = _acfg.get("dry_run", False)

            async with async_session() as db:
                # 8-day anti-repeat lookback (dedup identical cross-posts across platforms).
                cutoff = now - timedelta(days=8)
                recent = (await db.execute(
                    select(_SP.text_content).where(
                        _SP.post_type == "research_insight",
                        _SP.created_at >= cutoff,
                    ).order_by(desc(_SP.created_at)).limit(40)
                )).scalars().all()
                avoid_texts = list(dict.fromkeys([r for r in recent if r]))

                seed_idx = now.timetuple().tm_yday  # rotate material day to day
                # Generate ONCE at Twitter's tightest limit so identical copy fits all 3.
                base = await ai_content_service.generate_research_insight(
                    platform="twitter", seed_idx=seed_idx, tier=tier, avoid_texts=avoid_texts,
                )
                if not base or not base.text_content:
                    return {"status": "error", "error": "generation failed"}
                text = base.text_content

                if dry_run:
                    return {"status": "ok", "dry_run": True, "tier": tier, "platforms": platforms,
                            "text": text, "chars": len(text)}

                # Schedule to auto-publish a few hours out (kill window). One post per
                # platform, identical copy, same scheduled_for (so one kill cancels all).
                publish_at = now + timedelta(hours=window_hours)
                created, primary = [], None
                for p in platforms:
                    sp = _SP(
                        post_type="research_insight", platform=p, status="scheduled",
                        text_content=text, scheduled_for=publish_at,
                        ai_generated=True, ai_model=base.ai_model,
                    )
                    db.add(sp)
                    created.append(sp)
                await db.commit()
                for sp in created:
                    await db.refresh(sp)
                    if sp.platform == "twitter" or primary is None:
                        primary = sp

                # Human "today at 1:00 PM ET" for the heads-up.
                if _pytz:
                    et = publish_at.replace(tzinfo=_pytz.UTC).astimezone(_pytz.timezone("US/Eastern"))
                    post_when = et.strftime("today at %-I:%M %p ET") if et.date() == datetime.now(_pytz.timezone("US/Eastern")).date() else et.strftime("%a %-I:%M %p ET")
                else:
                    post_when = f"in {window_hours}h"

                # One kill link (cancels all siblings) + one edit link (tweak copy on all
                # platforms) — both authorized by the same 48h token.
                kill_token = post_scheduler_service.generate_cancel_token(primary.id)
                base = f"https://api.rigacap.com/api/admin/social/posts/{primary.id}"
                kill_url = f"{base}/cancel-email?token={kill_token}"
                edit_url = f"{base}/edit-email?token={kill_token}"
                try:
                    await admin_email_service.send_autopost_notice(
                        to_email="erik@rigacap.com", post=primary, kill_url=kill_url,
                        tier=tier, post_when=post_when, platforms=platforms, edit_url=edit_url,
                    )
                except Exception as _e:
                    print(f"⚠️ autopost heads-up email failed: {_e}")

                return {"status": "ok", "tier": tier, "platforms": platforms,
                        "post_ids": [sp.id for sp in created], "scheduled_for": str(publish_at)}

        try:
            return _run_async(_autopost_own_social())
        except Exception as e:
            import traceback
            print(f"❌ autopost_own_social failed: {e}\n{traceback.format_exc()}")
            return {"status": "error", "error": str(e)}

    if event.get("generate_research_insight"):
        _cfg = event.get("generate_research_insight") if isinstance(event.get("generate_research_insight"), dict) else {}
        async def _gen_insight():
            import random as _random
            from datetime import datetime as _dt
            from sqlalchemy import delete as _sa_delete, select as _sa_select
            from app.core.database import async_session, SocialPost
            from app.services.ai_content_service import ai_content_service
            # Cleanup tool: drop today's research_insight DRAFTS (e.g. to clear a
            # test-generated pile). {"clear_today": true}. Only ever touches
            # status='draft' so an approved/published post is never removed.
            if _cfg.get("clear_today"):
                async with async_session() as db:
                    res = await db.execute(
                        _sa_select(SocialPost).where(
                            SocialPost.post_type == "research_insight",
                            SocialPost.status == "draft",
                        )
                    )
                    _today = _dt.utcnow().date()
                    ids = [p.id for p in res.scalars().all()
                           if p.created_at and p.created_at.date() == _today]
                    if ids:
                        await db.execute(_sa_delete(SocialPost).where(SocialPost.id.in_(ids)))
                        await db.commit()
                    return {"status": "cleared", "deleted": len(ids), "ids": ids}
            prob = float(_cfg.get("prob", 0.4))
            if not _cfg.get("force") and _random.random() > prob:
                return {"status": "skipped_today", "prob": prob}
            seed_idx = _random.randrange(len(ai_content_service.INSIGHT_SEEDS))
            made = []
            async with async_session() as db:
                for platform in ("twitter", "threads"):
                    post = await ai_content_service.generate_research_insight(platform=platform, seed_idx=seed_idx)
                    if post:
                        db.add(post)
                        made.append({"platform": platform, "text": (post.text_content or "")[:120]})
                if made:
                    await db.commit()
            return {"status": "generated" if made else "no_post", "seed_idx": seed_idx, "drafts": made}
        try:
            result = _run_async(_gen_insight())
            print(f"💡 Research insight: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ generate_research_insight failed: {e}\n{traceback.format_exc()}")
            return {"status": "error", "error": str(e)}

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
            # Discipline-led default (Jun 2026 repositioning): lead with the
            # process, not hot picks. trade_result is reframed to lead with the
            # discipline behind a trade; discipline_win is the pure-process angle.
            # we_called_it (big-winner-vs-news) is now OPT-IN — fine for the
            # occasional social splash, but no longer the default story.
            # loss_review activates via the winner-threshold gate below.
            post_types = config.get("post_types", ["trade_result", "discipline_win"])
            max_trades = config.get("max_trades", 5)
            # loss_review gate: don't post about losses until the track record
            # has at least N winners. Posting "system was wrong but trailing
            # stop did its job" makes sense as a discipline-narrative move
            # AFTER the winners establish that the system has been right too.
            # Without that context, the loss posts read as a system that only
            # loses. Default threshold: 3 winners. Override via config.
            min_winners_for_loss_review = int(config.get("min_winners_for_loss_review", 3))
            include_loss_review = config.get("force_loss_review", False) or \
                (config.get("auto_loss_review", True) and "loss_review" not in post_types)

            async with async_session() as db:
                # Query signal track record closed WINNERS that haven't had posts generated yet
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

                # Loss-review gate: count all STR winners ever (regardless of
                # whether they've been posted). If we have enough cumulative
                # wins on record, the discipline-loss narrative becomes
                # credible. Then pull losses not yet posted.
                loss_positions = []
                if include_loss_review:
                    winner_count_q = await db.execute(
                        select(func.count()).select_from(ModelPosition)
                        .where(
                            ModelPosition.portfolio_type == "signal_track_record",
                            ModelPosition.status == "closed",
                            ModelPosition.pnl_pct > 0,
                        )
                    )
                    winner_count = winner_count_q.scalar() or 0
                    print(f"loss_review gate: {winner_count} STR winners on record "
                          f"(threshold: {min_winners_for_loss_review})")
                    if winner_count >= min_winners_for_loss_review:
                        loss_q = await db.execute(
                            select(ModelPosition)
                            .where(
                                ModelPosition.portfolio_type == "signal_track_record",
                                ModelPosition.status == "closed",
                                ModelPosition.pnl_pct < 0,
                                ModelPosition.social_post_generated == False,
                            )
                            .order_by(ModelPosition.exit_date.desc())
                            .limit(max_trades)
                        )
                        loss_positions = list(loss_q.scalars().all())
                        print(f"loss_review gate OPEN: queued {len(loss_positions)} losses")
                    else:
                        print(f"loss_review gate CLOSED: need {min_winners_for_loss_review - winner_count} "
                              f"more winners before loss posts activate")

                if not positions and not loss_positions:
                    return {"status": "ok", "message": "No new signal track trades qualifying for social posts", "posts_created": 0}

                print(f"Found {len(positions)} winners + {len(loss_positions)} losses for social-post generation")

                # 8-day anti-repeat: load our recent own-posts so the generator varies
                # opening line / framing instead of sounding like a template.
                from datetime import timedelta as _td8
                _cut8 = datetime.utcnow() - _td8(days=8)
                _recent_rows = (await db.execute(
                    select(SocialPost.text_content).where(
                        SocialPost.post_type.in_([
                            "trade_result", "we_called_it", "missed_opportunity",
                            "discipline_win", "loss_review", "research_insight",
                        ]),
                        SocialPost.created_at >= _cut8,
                    ).order_by(SocialPost.created_at.desc()).limit(25)
                )).scalars().all()
                recent_posts = [r for r in _recent_rows if r]

                # Generate posts for each trade x platform x post_type.
                # Winners get the configured post_types (trade_result / we_called_it).
                # Losses ONLY get loss_review — the other types assume a winner
                # and their templates would read absurd for a stopped-out trade.
                created = []
                for pos, types_for_pos in (
                    [(p, post_types) for p in positions] +
                    [(p, ["loss_review"]) for p in loss_positions]
                ):
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
                        for post_type in types_for_pos:
                            post = await ai_content_service.generate_post(
                                trade=trade_data,
                                post_type=post_type,
                                platform=platform,
                                avoid_texts=recent_posts,
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
            result = _run_async(_generate_social_posts())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Generate social posts failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # One-time setup of long-lived Meta tokens. Replaces the manual chain
    # of curl URLs we had to walk through in the May 6 incident — feed it
    # short-lived tokens straight from Graph API Explorer plus the app
    # credentials, and it does the full exchange end-to-end in one call:
    #   1. fb_exchange_token: short-lived USER → long-lived USER (60 days)
    #   2. /me/accounts: long-lived USER → PAGE access token (effectively
    #      permanent while the user token is alive)
    #   3. Resolves the Instagram Business Account ID from the page's
    #      instagram_business_account field
    #   4. (Threads) th_exchange_token: short-lived → long-lived (60 days)
    #   5. Persists EVERYTHING needed to refresh later: page tokens, the
    #      long-lived user token, app credentials. Both Lambdas updated.
    #
    # After this runs once, the weekly meta_token_refresh cron keeps the
    # tokens alive indefinitely without any further OAuth.
    #
    # Payload (all fields optional except app credentials per platform):
    #   {"meta_token_setup": {
    #       "fb_app_id": "...", "fb_app_secret": "...",
    #       "fb_short_lived_token": "EAA...",        # from Graph API Explorer
    #       "fb_page_id": "971214166079229",         # which page to use (optional, picks first if absent)
    #       "threads_app_id": "...", "threads_app_secret": "...",
    #       "threads_short_lived_token": "THA..."   # from Threads OAuth flow
    #   }}
    if event.get("meta_token_setup"):
        config = event["meta_token_setup"]
        print("🔐 Meta token setup (long-lived exchange)")
        try:
            import httpx, boto3 as _boto
            updates = {}    # env_var_name -> new_value
            results = {}    # operator-facing summary

            # ─ Facebook / Instagram ────────────────────────────────
            fb_short = config.get("fb_short_lived_token")
            fb_app_id = config.get("fb_app_id")
            fb_app_secret = config.get("fb_app_secret")
            if fb_short and fb_app_id and fb_app_secret:
                # Step 1: short-lived → long-lived USER token
                with httpx.Client(timeout=15) as client:
                    exch = client.get(
                        "https://graph.facebook.com/v19.0/oauth/access_token",
                        params={
                            "grant_type": "fb_exchange_token",
                            "client_id": fb_app_id,
                            "client_secret": fb_app_secret,
                            "fb_exchange_token": fb_short,
                        },
                    )
                if exch.status_code != 200:
                    return {"status": "error", "stage": "fb_exchange_token", "detail": exch.text}
                exch_data = exch.json()
                long_user = exch_data.get("access_token")
                long_expiry = exch_data.get("expires_in", 0)
                if not long_user:
                    return {"status": "error", "stage": "fb_exchange_token", "detail": "no access_token in response"}
                results["fb_long_lived_expires_in_days"] = long_expiry // 86400

                # Step 2: long-lived USER → PAGE access token
                with httpx.Client(timeout=15) as client:
                    accts = client.get(
                        "https://graph.facebook.com/v19.0/me/accounts",
                        params={
                            "access_token": long_user,
                            "fields": "id,name,access_token,instagram_business_account",
                        },
                    )
                if accts.status_code != 200:
                    return {"status": "error", "stage": "me/accounts", "detail": accts.text}
                pages = accts.json().get("data", [])
                if not pages:
                    return {"status": "error", "stage": "me/accounts", "detail": "no pages returned — user may not admin any FB Page"}
                # Pick the page: explicit fb_page_id if provided, else first
                preferred = config.get("fb_page_id")
                page = None
                if preferred:
                    page = next((p for p in pages if p.get("id") == preferred), None)
                page = page or pages[0]
                page_token = page.get("access_token")
                ig_account = (page.get("instagram_business_account") or {}).get("id")
                results["fb_page"] = {"id": page.get("id"), "name": page.get("name"), "ig_business_account_id": ig_account}

                updates["INSTAGRAM_ACCESS_TOKEN"] = page_token
                updates["META_LONG_LIVED_USER_TOKEN"] = long_user
                updates["META_FB_APP_ID"] = fb_app_id
                updates["META_FB_APP_SECRET"] = fb_app_secret
                updates["META_FB_PAGE_ID"] = page.get("id")
                if ig_account:
                    updates["INSTAGRAM_BUSINESS_ACCOUNT_ID"] = ig_account

            # ─ Threads ─────────────────────────────────────────────
            th_short = config.get("threads_short_lived_token")
            th_app_id = config.get("threads_app_id")
            th_app_secret = config.get("threads_app_secret")
            if th_short and th_app_secret:
                with httpx.Client(timeout=15) as client:
                    th_exch = client.get(
                        "https://graph.threads.net/access_token",
                        params={
                            "grant_type": "th_exchange_token",
                            "client_secret": th_app_secret,
                            "access_token": th_short,
                        },
                    )
                if th_exch.status_code != 200:
                    return {"status": "error", "stage": "th_exchange_token", "detail": th_exch.text}
                th_data = th_exch.json()
                long_th = th_data.get("access_token")
                if not long_th:
                    return {"status": "error", "stage": "th_exchange_token", "detail": "no access_token in response"}
                results["threads_long_lived_expires_in_days"] = th_data.get("expires_in", 0) // 86400
                updates["THREADS_ACCESS_TOKEN"] = long_th
                if th_app_id:
                    updates["META_THREADS_APP_ID"] = th_app_id
                updates["META_THREADS_APP_SECRET"] = th_app_secret

            if not updates:
                return {"status": "error", "detail": "no exchange performed — provide fb_short_lived_token+credentials and/or threads_short_lived_token+credentials"}

            # Persist to BOTH Lambdas (api + worker). Read current env each
            # time, modify only the keys we own, write back the full dict.
            lambda_client = _boto.client("lambda", region_name="us-east-1")
            persisted = []
            for fn in ["rigacap-prod-api", "rigacap-prod-worker"]:
                cfg = lambda_client.get_function_configuration(FunctionName=fn)
                env = cfg.get("Environment", {}).get("Variables", {})
                env.update(updates)
                lambda_client.update_function_configuration(
                    FunctionName=fn, Environment={"Variables": env},
                )
                persisted.append({"function": fn, "wrote": list(updates.keys())})

            return {"status": "success", "results": results, "persisted": persisted}
        except Exception as e:
            import traceback
            print(f"❌ meta_token_setup failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Weekly refresh of long-lived Meta tokens. Extends both the FB user
    # token (which keeps the IG Page token alive) and the Threads long-lived
    # token, calling Meta's refresh endpoints. Idempotent — safe to run any
    # time; failure on either side falls through to admin alert.
    #
    # Triggered by EventBridge cron weekly. Manual: {"meta_token_refresh": true}
    if event.get("meta_token_refresh"):
        print("🔁 Meta token refresh (weekly lifecycle)")
        try:
            import httpx, boto3 as _boto
            results = {}
            updates = {}

            ig_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
            if ig_token and ig_token.startswith("IGAA"):
                # Instagram-with-Instagram-Login flow: refresh via
                # /refresh_access_token?grant_type=ig_refresh_token. The
                # endpoint accepts a still-valid long-lived token and
                # returns a fresh 60-day token. No app secret needed for
                # the refresh — it's authenticated by the token itself.
                with httpx.Client(timeout=15) as client:
                    r = client.get(
                        "https://graph.instagram.com/refresh_access_token",
                        params={"grant_type": "ig_refresh_token", "access_token": ig_token},
                    )
                if r.status_code != 200:
                    results["instagram"] = {"status": "error", "detail": r.text}
                else:
                    new_ig = r.json().get("access_token")
                    if new_ig:
                        updates["INSTAGRAM_ACCESS_TOKEN"] = new_ig
                        results["instagram"] = {"status": "success", "expires_in_days": r.json().get("expires_in", 0) // 86400}
                    else:
                        results["instagram"] = {"status": "error", "detail": "no access_token in refresh response"}
            else:
                results["instagram"] = {"status": "skipped", "detail": "INSTAGRAM_ACCESS_TOKEN missing or not an IG-native (IGAA…) token"}

            th_token = os.environ.get("THREADS_ACCESS_TOKEN")
            if th_token:
                with httpx.Client(timeout=15) as client:
                    r = client.get(
                        "https://graph.threads.net/refresh_access_token",
                        params={"grant_type": "th_refresh_token", "access_token": th_token},
                    )
                if r.status_code != 200:
                    results["threads"] = {"status": "error", "detail": r.text}
                else:
                    new_th = r.json().get("access_token")
                    if new_th:
                        updates["THREADS_ACCESS_TOKEN"] = new_th
                        results["threads"] = {"status": "success", "expires_in_days": r.json().get("expires_in", 0) // 86400}
                    else:
                        results["threads"] = {"status": "error", "detail": "no access_token in refresh response"}
            else:
                results["threads"] = {"status": "skipped", "detail": "no THREADS_ACCESS_TOKEN configured"}

            # Persist any updates
            if updates:
                lambda_client = _boto.client("lambda", region_name="us-east-1")
                for fn in ["rigacap-prod-api", "rigacap-prod-worker"]:
                    cfg = lambda_client.get_function_configuration(FunctionName=fn)
                    env = cfg.get("Environment", {}).get("Variables", {})
                    env.update(updates)
                    lambda_client.update_function_configuration(
                        FunctionName=fn, Environment={"Variables": env},
                    )

            # Email admin on any errors so we get warning before the cliff
            errored_platforms = [k for k, v in results.items() if v.get("status") == "error"]
            if errored_platforms:
                try:
                    from app.services.admin_email_service import admin_email_service
                    body_lines = ["Meta token refresh ran with errors — manual recovery may be needed:\n"]
                    for k, v in results.items():
                        body_lines.append(f"  {k}: {v}")
                    _run_async(admin_email_service.send(
                        subject="[RigaCap] Meta token refresh failure",
                        body="\n".join(body_lines),
                    ))
                except Exception as ee:
                    print(f"Admin alert send also failed: {ee}")

            return {"status": "success" if not errored_platforms else "partial", "results": results, "persisted": list(updates.keys())}
        except Exception as e:
            import traceback
            print(f"❌ meta_token_refresh failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Quick set-only of Meta tokens (no exchange / no refresh logic).
    # Used as the manual escape hatch when the operator already has a
    # long-lived token in hand and just needs to push it to the env.
    # Kept for emergencies — prefer meta_token_setup for new tokens.
    #
    # Payload:
    #   {"refresh_meta_tokens": {
    #       "instagram_access_token": "EAAB...",   # optional
    #       "threads_access_token": "THAA...",     # optional
    #   }}
    if event.get("refresh_meta_tokens"):
        config = event["refresh_meta_tokens"]
        print("🔑 Refresh Meta access tokens")
        try:
            import boto3 as _boto
            function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
            if not function_name:
                return {"status": "error", "error": "AWS_LAMBDA_FUNCTION_NAME not set"}
            lambda_client = _boto.client("lambda", region_name="us-east-1")

            # Update BOTH Lambdas (api + worker) so HTTP-triggered publishes
            # and cron-triggered publishes both see the new tokens.
            updated = []
            errors = []
            for fn in ["rigacap-prod-api", "rigacap-prod-worker"]:
                try:
                    cfg = lambda_client.get_function_configuration(FunctionName=fn)
                    env_vars = cfg.get("Environment", {}).get("Variables", {})
                    changed = []
                    if config.get("instagram_access_token"):
                        env_vars["INSTAGRAM_ACCESS_TOKEN"] = config["instagram_access_token"]
                        changed.append("INSTAGRAM_ACCESS_TOKEN")
                    if config.get("threads_access_token"):
                        env_vars["THREADS_ACCESS_TOKEN"] = config["threads_access_token"]
                        changed.append("THREADS_ACCESS_TOKEN")
                    if not changed:
                        continue
                    # CRITICAL: pass the FULL env_vars dict (we read it via
                    # get_function_configuration above so DATABASE_URL,
                    # JWT secrets, etc. are preserved). Never call
                    # update_function_configuration with a partial dict.
                    lambda_client.update_function_configuration(
                        FunctionName=fn,
                        Environment={"Variables": env_vars},
                    )
                    updated.append({"function": fn, "vars": changed})
                except Exception as ex:
                    errors.append({"function": fn, "error": str(ex)})
            return {"status": "success" if updated else "error", "updated": updated, "errors": errors}
        except Exception as e:
            import traceback
            print(f"❌ refresh_meta_tokens failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Schedule the launch announcement sequence — 5 cards × N platforms with
    # specific publish dates. Idempotent: any existing draft/scheduled posts
    # whose text matches a launch headline are deleted before re-inserting.
    if event.get("schedule_launch_sequence"):
        config = event["schedule_launch_sequence"]
        print(f"🚀 Schedule launch sequence: {config}")

        async def _schedule_launch():
            from app.core.database import SocialPost
            from sqlalchemy import delete as sa_delete

            # Editorial copy mirrors frontend/src/components/SocialTab.jsx LAUNCH_POSTS
            cards = [
                {
                    "id": "launch-1",
                    "image_s3_key": "social/images/launch-1.png",
                    "twitter": "RigaCap is live.\n\nFifteen years of building, rebuilt this year on honest data, now running with real capital.\n\nA momentum strategy designed around one number: the worst drawdown. 19% across a 21-year backtest — through 2008, COVID, and 2022 — while the index lost half its value twice.\n\nrigacap.com",
                    "instagram": "RigaCap is live.\n\nFifteen years of nights-and-weekends building, rebuilt this year from scratch on honest data, now running with real capital.\n\nIt is a momentum strategy designed around one number: the worst drawdown. Across a 21-year walk-forward backtest — through the 2008 financial crisis, COVID, and the 2022 bear — the worst peak-to-trough loss was 19%. The index lost half its value twice in that span.\n\nDiversified across ~20 names, sized by risk, with wide trailing stops and a regime filter that moves the whole book to cash when markets turn hostile. Selective, not silent.\n\nNo minimums. No performance fees. Same signals for everyone.\n\nrigacap.com",
                    "instagram_tags": "#investing #momentum #riskmanagement #rigacap",
                    "threads": "RigaCap is live.\n\nFifteen years of building, rebuilt this year on honest data, now running with real capital.\n\nDesigned around one number: the worst drawdown. 19% across 21 backtested years — the index lost half its value twice.\n\nrigacap.com",
                },
                {
                    "id": "launch-2",
                    "image_s3_key": "social/images/launch-2.png",
                    "twitter": "Most backtests cherry-pick the start date that flatters them. Ours runs 21 years, continuous, no hindsight — and when cleaner data made our numbers smaller, we published the smaller numbers.\n\n8.3% a year. Worst drawdown 19% — a third of raw momentum's 57%.\n\nThe honest version: rigacap.com/track-record",
                    "instagram": "Most backtests show you the result that flatters the strategy. Ours runs twenty-one years, continuous, with no hindsight — and when cleaner data made our numbers smaller, we published the smaller numbers.\n\nThe 21-year walk-forward backtest:\n\nReturn: 8.3% a year\nWorst drawdown: 19% — a third of raw momentum's 57%, while the index lost 55%\nLast 24 months (held-out): +32% annualized\n\nThe point was never the biggest number. It's a drawdown you can actually hold through — because the return you can hold through is the only one you collect.\n\nFull methodology, including the numbers that don't flatter us, on the track record page.\n\nrigacap.com/track-record",
                    "instagram_tags": "#investing #riskmanagement #walkforward #trackrecord #rigacap",
                    "threads": "Most backtests cherry-pick the start date that flatters them.\n\nOurs runs 21 years, continuous, no hindsight — and when cleaner data made our numbers smaller, we published the smaller numbers.\n\n8.3% a year. Worst drawdown 19% — a third of raw momentum's 57%.\n\nrigacap.com/track-record",
                },
                {
                    "id": "launch-3",
                    "image_s3_key": "social/images/launch-3.png",
                    "twitter": "Three things must align before RigaCap signals a buy:\n\nI. Timing — the right breakout. Don't chase.\nII. Quality — accelerating strength in an established trend. Leaders, not laggards.\nIII. Confirmation — strength near highs. Never a falling knife.\n\nWhen they don't align, the system stays quiet. Some weeks, cash is the position.",
                    "instagram": "A signal is not a single indicator firing. It is three things going right at once.\n\nI. TIMING. The right breakout, not a chased one. Patience over impulse.\n\nII. QUALITY. Accelerating strength inside an established trend — leaders proving themselves, not laggards looking cheap.\n\nIII. CONFIRMATION. Strength near recent highs, in an uptrend. The system never catches falling knives.\n\nWhen all three align, RigaCap signals. When they don't, it does nothing — and when the market itself turns hostile, the whole book goes to cash.\n\nSome weeks, nothing is the right answer.\n\nrigacap.com",
                    "instagram_tags": "#investing #ensemble #systematictrading #rigacap",
                    "threads": "Three things must align before RigaCap signals a buy:\n\nI. Timing — the right breakout. Don't chase.\nII. Quality — accelerating strength in an established trend.\nIII. Confirmation — strength near highs. Never a falling knife.\n\nWhen they don't align, the system stays quiet.\n\nrigacap.com",
                },
                {
                    "id": "launch-4",
                    "image_s3_key": "social/images/launch-4.png",
                    "twitter": "The index's six worst months of the last 21 years:\n\nOct 2008: −16.5%. Mar 2020: −13.1%. Feb 2009: −10.7%. Sep 2008: −9.9%. Sep 2022: −9.6%. Dec 2018: −9.3%.\n\nOur backtest's same months: 0.0%, −4.7%, 0.0%, 0.0%, 0.0%, −1.3%.\n\nFour of the six, it had already gone to cash.\n\nrigacap.com/track-record",
                    "instagram": "The index's six worst months of the last twenty-one years — and where our backtest was when they hit:\n\nOct 2008: index −16.5% · system 0.0% (in cash)\nMar 2020: index −13.1% · system −4.7%\nFeb 2009: index −10.7% · system 0.0% (in cash)\nSep 2008: index −9.9% · system 0.0% (in cash)\nSep 2022: index −9.6% · system 0.0% (in cash)\nDec 2018: index −9.3% · system −1.3%\n\nFour of the six, the regime filter had already moved the entire book to cash before the month began. That is the whole design: participate in trends, step aside in storms.\n\nBacktested monthly returns, 2007–2026. Every number labeled on the track record page.\n\nrigacap.com/track-record",
                    "instagram_tags": "#investing #marketregime #riskmanagement #rigacap",
                    "threads": "The index's six worst months in 21 years: −16.5%, −13.1%, −10.7%, −9.9%, −9.6%, −9.3%.\n\nOur backtest's same months: 0.0%, −4.7%, 0.0%, 0.0%, 0.0%, −1.3%.\n\nFour of the six, it had already gone to cash.\n\nrigacap.com/track-record",
                },
                {
                    "id": "launch-5",
                    "image_s3_key": "social/images/launch-5.png",
                    "twitter": "You can find signals anywhere. Discipline is harder.\n\nSitting in cash when nothing's working. Honoring stops without second-guessing. Not doubling down on losers.\n\nRigaCap is an external discipline layer — it removes your own behavior as the biggest risk in your portfolio.\n\n$59/mo founding rate (first 100). 7-day trial.\n\nrigacap.com",
                    "instagram": "You can find signals anywhere. The internet is full of them.\n\nWhat is harder to find is the discipline to follow them. To sit in cash when nothing is working. To honor a stop without second-guessing it. To not double down on a loser because the chart looks oversold.\n\nRigaCap is an external discipline layer. It tells you when to enter, when to exit, and — just as importantly — when to do nothing. It removes your own behavior as the biggest risk in your portfolio.\n\nFounding rate: $59 per month for the first 100 members.\nStandard: $129 per month. Annual: $1,099.\nTrial: 7 days, full access.\n\nrigacap.com",
                    "instagram_tags": "#investing #disciplinedtrading #signals #rigacap",
                    "threads": "You can find signals anywhere. Discipline is harder.\n\nSitting in cash when nothing's working. Honoring stops without second-guessing. Not doubling down on losers.\n\nRigaCap is an external discipline layer.\n\n$59/mo founding rate, first 100 members. 7-day trial.\n\nrigacap.com",
                },
            ]

            # Caller passes ISO datetimes (UTC) for each card's publish time.
            # Example: schedules = ["2026-05-06T20:00:00Z", "2026-05-07T13:00:00Z", ...]
            schedules = config.get("schedules", [])
            if len(schedules) != len(cards):
                return {"status": "error", "error": f"Need {len(cards)} schedules, got {len(schedules)}"}

            platforms = config.get("platforms", ["twitter", "instagram", "threads"])

            from datetime import datetime as _dt
            schedule_dts = [_dt.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None) for s in schedules]

            async with async_session() as db:
                # Idempotency: delete prior launch posts (any status that's
                # not yet published) whose text starts with one of our
                # canonical prefixes. Don't touch already-published posts.
                prefixes = []
                for card in cards:
                    for plat in platforms:
                        prefix = card[plat][:60].replace("'", "''")
                        prefixes.append(prefix)

                from sqlalchemy import or_ as sa_or
                conds = [SocialPost.text_content.like(f"{p}%") for p in prefixes]
                delete_result = await db.execute(
                    sa_delete(SocialPost).where(
                        SocialPost.status.in_(["draft", "approved", "scheduled"]),
                        sa_or(*conds),
                    )
                )
                deleted = delete_result.rowcount
                await db.commit()

                # Insert fresh rows
                created = 0
                for card, sched_dt in zip(cards, schedule_dts):
                    for plat in platforms:
                        text = card[plat]
                        hashtags = card.get(f"{plat}_tags", "") if plat == "instagram" else ""
                        image_key = card["image_s3_key"]
                        post = SocialPost(
                            platform=plat,
                            text_content=text,
                            hashtags=hashtags or None,
                            post_type="launch_announcement",
                            status="scheduled",
                            scheduled_for=sched_dt,
                            image_s3_key=image_key,
                            reviewed_by="schedule_launch_sequence",
                            reviewed_at=_dt.utcnow(),
                        )
                        db.add(post)
                        created += 1
                await db.commit()

            return {
                "status": "success",
                "deleted_prior": deleted,
                "created": created,
                "schedules": schedules,
                "platforms": platforms,
            }

        try:
            result = _run_async(_schedule_launch())
            print(f"✅ schedule_launch_sequence: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ schedule_launch_sequence failed: {e}")
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
            result = _run_async(_monthly_recap())
            return result
        except Exception as e:
            import traceback
            print(f"❌ Monthly recap failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

    # Scan followed accounts for reply opportunities (direct Lambda invocation)
    if event.get("resend_reply_approvals"):
        print("✉️ Resending pending reply-approval email with corrected links")

        async def _resend_approvals():
            from app.services.reply_scanner_service import reply_scanner_service
            async with async_session() as db:
                n = await reply_scanner_service.resend_pending_approvals(db)
                return {"status": "ok", "resent": n}

        try:
            return _run_async(_resend_approvals())
        except Exception as e:
            import traceback
            print(f"❌ Resend approvals failed: {e}")
            print(traceback.format_exc())
            return {"status": "error", "error": str(e)}

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
            result = _run_async(_scan_replies())
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
            result = _run_async(_scan_ig_comments())
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
    # Force-refetch SPY from yfinance with auto_adjust=True, replace in cache,
    # re-export pickle + parquet. One-time migration to outlier-filtered,
    # dividend-adjusted SPY for benchmark/regime use. Alpaca's SPY series is
    # SIP-faithful (preserves every trade including anomalous outliers like
    # the 2026-02-02 $69.005 print — confirmed real, never SIP-corrected);
    # yfinance applies outlier filtering and dividend adjustment. See
    # market_data_provider.YFINANCE_PREFERRED for the philosophy.
    # Idempotent — safe to re-run.
    # Payload: {"force_refetch_spy": true}
    if event.get("force_refetch_spy"):
        print("🔄 Force-refetching SPY from yfinance (auto_adjust=True)")

        async def _refetch_spy():
            import yfinance as yf
            import pandas as _pd
            from app.services.market_data_provider import _validate_bar_sanity
            from app.services.data_export import data_export_service

            # Pull SPY full history with dividend + split adjustment applied
            start = "2019-06-01"  # Matches production pickle's existing range
            df = yf.download('SPY', start=start, progress=False, auto_adjust=True)
            if df is None or df.empty:
                return {"status": "failed", "error": "yfinance returned no data"}

            # Flatten yfinance's MultiIndex columns to lowercase scalars
            if isinstance(df.columns, _pd.MultiIndex):
                df.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in df.columns]
            else:
                df.columns = [str(c).lower() for c in df.columns]

            # Normalize index — tz-naive midnight
            if hasattr(df.index, 'tz') and df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            df.index = df.index.normalize()

            # Sanity check before touching anything
            violations = _validate_bar_sanity('SPY', df)
            if violations:
                print(f"❌ ABORT — yfinance SPY data failed sanity check: {violations}")
                return {"status": "failed", "error": "sanity violations", "violations": violations}

            # Capture key diagnostic values for the response
            sample_dates = ['2026-02-02', '2025-03-10', '2024-01-02', '2021-01-04']
            samples = {}
            for d in sample_dates:
                ts = _pd.Timestamp(d)
                if ts in df.index:
                    samples[d] = {
                        "open": float(df.loc[ts, 'open']),
                        "high": float(df.loc[ts, 'high']),
                        "low": float(df.loc[ts, 'low']),
                        "close": float(df.loc[ts, 'close']),
                    }

            # Compute indicators using the scanner's canonical pipeline (same
            # math as everywhere else — keeps dwap/ma_50/ma_200/etc consistent
            # across symbols)
            df = scanner_service._ensure_indicators(df)

            # Snapshot existing SPY for diff logging
            old_spy = scanner_service.data_cache.get('SPY')
            old_low = None
            if old_spy is not None and _pd.Timestamp('2026-02-02') in old_spy.index:
                old_low = float(old_spy.loc[_pd.Timestamp('2026-02-02'), 'low'])

            # Swap in
            scanner_service.data_cache['SPY'] = df
            print(f"✅ Replaced SPY in cache: {len(df)} bars, "
                  f"{df.index.min().date()} → {df.index.max().date()}")
            print(f"   2026-02-02 low: old={old_low}  new={samples.get('2026-02-02', {}).get('low')}")

            # Re-export pickle + parquet (sister writes from same in-memory cache)
            try:
                data_export_service.export_pickle(scanner_service.data_cache)
                print("✅ Pickle re-exported")
            except Exception as e:
                return {"status": "partial", "error": f"pickle export failed: {e}", "samples": samples}
            try:
                data_export_service.export_parquet(scanner_service.data_cache)
                print("✅ Parquet re-exported")
            except Exception as e:
                # Parquet failure is non-fatal — pickle is the read source today
                print(f"⚠️ Parquet export failed (non-fatal): {e}")

            return {
                "status": "ok",
                "bars": len(df),
                "first_date": str(df.index.min().date()),
                "last_date": str(df.index.max().date()),
                "old_2026_02_02_low": old_low,
                "new_2026_02_02_low": samples.get('2026-02-02', {}).get('low'),
                "samples": samples,
            }

        try:
            return _run_async(_refetch_spy())
        except Exception as e:
            import traceback
            return {"status": "error", "error": str(e), "trace": traceback.format_exc()[:600]}

    # {"nightly_data_hygiene": {"_": 1}} or {"symbols": [...]} for subset test
    # Admin one-off: reactivate a newsletter subscriber whose row got
    # unsubscribed (e.g. corporate email auto-processing the one-click
    # List-Unsubscribe). Same effect as the public subscribe endpoint minus the
    # Turnstile bot check (which blocks server-side calls). (Jun 23 2026)
    #   {"reactivate_newsletter": {"email": "...", "report_type": "market_measured"}}
    if event.get("reactivate_newsletter"):
        _cfg = event.get("reactivate_newsletter") or {}
        _email = (_cfg.get("email") or "").strip().lower()
        _rtype = _cfg.get("report_type") or "market_measured"
        async def _reactivate():
            from app.core.database import async_session, NewsletterPreference
            from sqlalchemy import select as _sel
            from datetime import datetime as _dt
            if not _email:
                return {"status": "error", "reason": "no email"}
            async with async_session() as db:
                row = (await db.execute(_sel(NewsletterPreference).where(
                    NewsletterPreference.email == _email,
                    NewsletterPreference.report_type == _rtype,
                ))).scalar_one_or_none()
                if row is None:
                    db.add(NewsletterPreference(email=_email, report_type=_rtype,
                                                subscribed_at=_dt.utcnow(), source="admin_reactivate"))
                    await db.commit()
                    return {"status": "created", "email": _email, "report_type": _rtype}
                _was = row.unsubscribed_at
                row.unsubscribed_at = None
                row.subscribed_at = _dt.utcnow()
                await db.commit()
                return {"status": "reactivated", "email": _email, "report_type": _rtype,
                        "was_unsubscribed_at": str(_was)}
        try:
            result = _run_async(_reactivate())
            print(f"📧 reactivate_newsletter: {result}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ reactivate_newsletter failed: {e}\n{traceback.format_exc()}")
            return {"status": "error", "error": str(e)}

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
            corp_events = await symbol_metadata_service.poll_corp_actions(since_hours=192)  # 8-day window (was 36h) so a split isn't missed if a night is skipped
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
                        # Compute indicators on the freshly-refetched bars
                        # before assigning to the cache. Without this, the
                        # split-refetch lands a bare-OHLCV DataFrame in
                        # cache; the next daily scan's fetch_incremental
                        # skips it (last_date is current) and the bare
                        # state persists into pickle, triggering parquet
                        # column_set_diff. Surfaced by SMX/KALA/DKI/ASBP/
                        # AIXI on May 13 2026.
                        df = scanner_service._ensure_indicators(df)
                        scanner_service.data_cache[sym] = df
                        refetched += 1
                    # Re-export pickle ONLY (persists the split fix). MEMORY FIX
                    # (Jun 16 2026): the inline export_parquet here built a full-
                    # universe Arrow table on top of the 695 MB cache + the asset-
                    # verification working set, pushing the worker past its 3008 MB
                    # cap -> Runtime.OutOfMemory + retry storm (the Jun 15 alarm
                    # emails). Parquet is shadow/observation only and is regenerated
                    # by the next daily scan, so we drop it here; gc first to reclaim
                    # the verify/refetch buffers. See project_oom_scan_zero_jun15.
                    if refetched > 0:
                        import gc as _gc
                        _gc.collect()
                        data_export_service.export_pickle(scanner_service.data_cache)
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

            # 5b. Rebuild the split calendar from Alpaca (ASST guard, Aug 2026). split_adjusted()
            # reads a static calendar.parquet with no other refresh path — a new split (ASST reverse
            # split) was therefore never applied → raw unadjusted bars → phantom breakout. Rebuild
            # nightly so a split is reflected within a day. Non-fatal; refuses to write on empty fetch.
            ca_rebuild = None
            try:
                from app.services import pitfwu_store as _ps_cal
                ca_rebuild = _ps_cal.rebuild_calendar(symbols)
                print(f"🗓️ split calendar rebuild: {ca_rebuild}")
            except Exception as e:
                ca_rebuild = {"error": str(e)[:200]}
                print(f"⚠️ split calendar rebuild failed: {e}")

            # 5c. Icicle detection — symbols whose BARS have frozen (last bar lagging the freshest
            # universe bar by > 7d) though the asset is still valid in Alpaca (what let ASST rot,
            # frozen Jun 15). Detect + surface here; the rank/entry gate (is_series_tradeable)
            # already blocks signals on them.
            icicles = []
            try:
                import pandas as _pd_ic
                lasts = {}
                for _s, _df in scanner_service.data_cache.items():
                    if _df is not None and len(_df):
                        _l = _pd_ic.Timestamp(_df.index.max())
                        if getattr(_l, "tzinfo", None) is not None:
                            _l = _l.tz_localize(None)
                        lasts[_s] = _l
                if lasts:
                    _fresh = max(lasts.values())
                    _cut = _fresh - _pd_ic.Timedelta(days=7)
                    icicles = sorted([(s, d) for s, d in lasts.items() if d < _cut], key=lambda x: x[1])
                    print(f"🧊 icicle scan: freshest={_fresh.date()}, {len(icicles)} frozen symbol(s)")
            except Exception as e:
                print(f"⚠️ icicle detection failed: {e}")

            # 6. Confidence-tier scoring + AUTO tier execution.
            # The hygiene scorer classifies every flagged item as AUTO /
            # RECOMMEND / EXCEPTION using rules + cached AI verdicts. AUTO
            # items execute here (no cap); RECOMMEND + EXCEPTION surface in
            # the admin Hygiene tab. The email becomes a summary + link.
            from app.services.hygiene_scorer import (
                score_missing, score_reuse, execute_auto_tier,
                TIER_AUTO, TIER_RECOMMEND, TIER_EXCEPTION,
            )

            scorer_missing = await score_missing(run_ai=True)
            scorer_reuse = await score_reuse()
            all_items = scorer_missing + scorer_reuse

            auto_summary = await execute_auto_tier(all_items)

            recommend_count = sum(1 for it in all_items if it.tier == TIER_RECOMMEND)
            exception_count = sum(1 for it in all_items
                                   if it.tier == TIER_EXCEPTION
                                   and (it.days_missing or 0) >= 7)
            urgent_held = [it.symbol for it in all_items
                            if it.in_open_position and it.category == "missing"]
            reuse_total = len(scorer_reuse)

            try:
                from app.services.email_service import admin_email_service
                critical_flags = []
                info_flags = []

                # Icicle + calendar-rebuild surfacing (steps 5b/5c). Icicles holding a live position
                # are critical; otherwise informational.
                if icicles:
                    _held_ic = [s for s, _ in icicles if s in (urgent_held or [])]
                    _lst = ", ".join(f"{s}({d.date()})" for s, d in icicles[:10])
                    _icemsg = (f"🧊 {len(icicles)} icicle(s) — bars frozen >7d, still valid in Alpaca: {_lst}"
                               + (f" (+{len(icicles)-10} more)" if len(icicles) > 10 else ""))
                    (critical_flags if _held_ic else info_flags).append(_icemsg)
                if isinstance(ca_rebuild, dict) and ca_rebuild.get("status") == "success":
                    info_flags.append(f"🗓️ Split calendar refreshed: {ca_rebuild.get('splits_total')} splits, "
                                      f"{ca_rebuild.get('symbols_with_splits')} symbols")
                elif isinstance(ca_rebuild, dict) and ca_rebuild.get("error"):
                    info_flags.append(f"⚠️ Split calendar rebuild: {ca_rebuild.get('error')}")

                if urgent_held:
                    critical_flags.append(
                        f"🚨 {len(urgent_held)} held position(s) gone missing in Alpaca — manual close needed: "
                        f"{', '.join(urgent_held[:8])}"
                        + (f" (+{len(urgent_held)-8} more)" if len(urgent_held) > 8 else "")
                    )
                # Missing-in-Alpaca: alarm on rate-of-change, not absolute count.
                # The chronic count drifts up slowly as ETFs and edge-case symbols
                # accumulate; firing on 'current > 20' was a permanent warning the
                # operator couldn't act on. What matters is a sudden spike: today's
                # count jumping materially over yesterday's. Persist baseline to S3;
                # alert only when delta > 15 symbols OR > 25%.
                missing_alpaca_now = tally["missing_in_alpaca"]
                missing_alpaca_prev = None
                try:
                    import boto3 as _boto, json as _json
                    s3c = _boto.client("s3", region_name="us-east-1")
                    bkt = "rigacap-prod-price-data-149218244179"
                    key = "hygiene/last_missing_alpaca_count.json"
                    try:
                        obj = s3c.get_object(Bucket=bkt, Key=key)
                        prev_data = _json.loads(obj["Body"].read())
                        missing_alpaca_prev = prev_data.get("count")
                    except s3c.exceptions.NoSuchKey:
                        missing_alpaca_prev = None
                    if missing_alpaca_prev is not None:
                        delta = missing_alpaca_now - missing_alpaca_prev
                        pct = (delta / missing_alpaca_prev * 100) if missing_alpaca_prev > 0 else 0
                        if delta > 15 or pct > 25:
                            critical_flags.append(
                                f"⚠️ Missing-in-Alpaca count jumped {missing_alpaca_prev} → {missing_alpaca_now} "
                                f"(+{delta}, {pct:+.1f}%). Investigate data pipeline."
                            )
                        else:
                            info_flags.append(
                                f"ℹ️ Missing-in-Alpaca: {missing_alpaca_now} ({delta:+d} vs yesterday)"
                            )
                    else:
                        info_flags.append(f"ℹ️ Missing-in-Alpaca: {missing_alpaca_now} (no prior baseline; recording for tomorrow)")
                    # Persist today's count as tomorrow's baseline
                    s3c.put_object(
                        Bucket=bkt, Key=key,
                        Body=_json.dumps({"count": missing_alpaca_now, "recorded_at": datetime.utcnow().isoformat()}).encode("utf-8"),
                        ContentType="application/json",
                    )
                except Exception as _e:
                    info_flags.append(f"ℹ️ Missing-in-Alpaca: {missing_alpaca_now} (rate-of-change unavailable: {_e})")
                # Universe dirty count: alarm on rate-of-change, not absolute level.
                # The absolute count drifts up slowly with universe expansion and
                # historical-data quirks; firing on "current > 1500" means a chronic
                # warning the operator can't act on. What matters is a sudden spike:
                # if today's dirty count jumps materially over yesterday's baseline,
                # something changed in the data pipeline. Persist yesterday's baseline
                # to S3; alert only when the delta exceeds +50 symbols OR +5%.
                dirty_total = diag.get("total_dirty_symbols") if isinstance(diag, dict) else None
                dirty_delta = None
                dirty_prev = None
                if dirty_total is not None:
                    try:
                        import boto3 as _boto, json as _json
                        s3c = _boto.client("s3", region_name="us-east-1")
                        bkt = "rigacap-prod-price-data-149218244179"
                        key = "hygiene/last_dirty_count.json"
                        try:
                            obj = s3c.get_object(Bucket=bkt, Key=key)
                            prev_data = _json.loads(obj["Body"].read())
                            dirty_prev = prev_data.get("count")
                        except s3c.exceptions.NoSuchKey:
                            dirty_prev = None
                        if dirty_prev is not None:
                            dirty_delta = dirty_total - dirty_prev
                            pct_change = (dirty_delta / dirty_prev * 100) if dirty_prev > 0 else 0
                            if dirty_delta > 50 or pct_change > 5:
                                critical_flags.append(
                                    f"⚠️ Universe dirty count jumped {dirty_prev} → {dirty_total} "
                                    f"(+{dirty_delta}, {pct_change:+.1f}%). Investigate data pipeline."
                                )
                            else:
                                info_flags.append(
                                    f"ℹ️ Universe dirty count: {dirty_total} ({dirty_delta:+d} vs yesterday)"
                                )
                        else:
                            info_flags.append(f"ℹ️ Universe dirty count: {dirty_total} (no prior baseline; recording for tomorrow)")
                        # Persist today's count as tomorrow's baseline
                        s3c.put_object(
                            Bucket=bkt, Key=key,
                            Body=_json.dumps({"count": dirty_total, "recorded_at": datetime.utcnow().isoformat()}).encode("utf-8"),
                            ContentType="application/json",
                        )
                    except Exception as ee:
                        # Don't fail the email on an S3 error — fall back to absolute alarm
                        info_flags.append(f"ℹ️ Universe dirty count: {dirty_total} (rate-of-change unavailable: {ee})")

                if refetch_result and refetch_result.get("refetched", 0) > 0:
                    info_flags.append(f"🔧 Auto-fixed {refetch_result['refetched']} split(s) via SPLIT-adjusted refetch")
                if tally["new"] > 0:
                    info_flags.append(f"🆕 {tally['new']} new symbols added to metadata")

                # Summary-only email: counts + a single link to the admin
                # Hygiene tab. No per-symbol triage links — the queue lives
                # in one consolidated UI now.
                auto_delisted_total = len(auto_summary.get("delisted", []))
                auto_migrated_total = len(auto_summary.get("migrated", []))
                auto_errors = len(auto_summary.get("errors", []))

                needs_eyes = recommend_count + exception_count + len(urgent_held)
                status_word = "All Clear" if not critical_flags and needs_eyes == 0 else (
                    "Attention Needed" if critical_flags else "Review Queue"
                )
                emoji = "✅" if status_word == "All Clear" else ("🚨" if critical_flags else "👀")

                H2 = "margin:0 0 12px 0;font-size:18px;font-weight:600;"
                H3 = "margin:18px 0 6px 0;font-size:14px;font-weight:600;color:#141210;"
                UL = "margin:0 0 12px 0;padding:0 0 0 18px;list-style:disc;line-height:1.45;"
                LI = "margin:1px 0;padding:0;"
                P  = "margin:6px 0;line-height:1.45;"
                BTN = (
                    "display:inline-block;background:#7A2430;color:#FFF;"
                    "padding:10px 18px;text-decoration:none;font-weight:600;"
                    "border-radius:4px;margin:8px 0;"
                )

                html_lines = [
                    f"<h2 style='{H2}'>{emoji} Data Hygiene — {status_word}</h2>",
                ]

                # Headline summary line — what got done last night, and what's left.
                summary_bits = []
                if auto_delisted_total:
                    summary_bits.append(f"<b>{auto_delisted_total}</b> auto-delisted")
                if auto_migrated_total:
                    summary_bits.append(f"<b>{auto_migrated_total}</b> ticker-reuse migrated")
                if refetch_result and refetch_result.get("refetched", 0) > 0:
                    summary_bits.append(f"<b>{refetch_result['refetched']}</b> splits auto-fixed")
                summary_line = "; ".join(summary_bits) if summary_bits else "no auto-actions"
                html_lines.append(
                    f"<p style='{P}'>Last night: {summary_line}.</p>"
                )

                # The only inline data: held-position emergencies and any
                # rate-of-change spike that fired. Everything else is one
                # click away.
                if critical_flags:
                    html_lines.append(f"<h3 style='{H3}'>⚠️ Needs Attention</h3><ul style='{UL}'>")
                    for fl in critical_flags:
                        html_lines.append(f"<li style='{LI}'>{fl}</li>")
                    html_lines.append("</ul>")

                # The CTA: open the admin Hygiene tab. No per-row links.
                if needs_eyes > 0:
                    queue_lines = []
                    if recommend_count:
                        queue_lines.append(f"<b>{recommend_count}</b> one-click recommendations")
                    if exception_count:
                        queue_lines.append(f"<b>{exception_count}</b> exceptions")
                    if reuse_total and any(
                        it.tier != TIER_AUTO for it in scorer_reuse
                    ):
                        queue_lines.append(f"<b>{sum(1 for it in scorer_reuse if it.tier != TIER_AUTO)}</b> ticker-reuse review")
                    html_lines.append(f"<h3 style='{H3}'>Queue</h3>")
                    html_lines.append(f"<p style='{P}'>{'; '.join(queue_lines)}.</p>")
                    html_lines.append(
                        f"<p style='margin:8px 0;'><a href='https://rigacap.com/admin?tab=hygiene' style='{BTN}'>Open Hygiene Tab</a></p>"
                    )
                else:
                    html_lines.append(
                        f"<p style='{P}'>Queue is empty. Nothing requires review.</p>"
                    )

                if info_flags:
                    html_lines.append(f"<h3 style='{H3}'>ℹ️ Informational</h3><ul style='{UL}'>")
                    for fl in info_flags:
                        html_lines.append(f"<li style='{LI}'>{fl}</li>")
                    html_lines.append("</ul>")
                if auto_errors:
                    html_lines.append(
                        f"<p style='{P}font-size:12px;color:#5A544E;'>"
                        f"{auto_errors} AUTO-tier action(s) failed — see Hygiene tab → Recent actions for details.</p>"
                    )

                html = "".join(html_lines)

                await admin_email_service.send_admin_alert(
                    to_email="erik@rigacap.com",
                    subject=f"{emoji} RigaCap Data Hygiene — {status_word}",
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
                "missing_symbols": missing_symbols,
                "auto_executed": {
                    "delisted": len(auto_summary.get("delisted", [])),
                    "migrated": len(auto_summary.get("migrated", [])),
                    "errors": len(auto_summary.get("errors", [])),
                },
                "queue": {
                    "recommend": recommend_count,
                    "exception": exception_count,
                    "urgent_held": len(urgent_held),
                },
            }

        try:
            return _run_async(_hygiene())
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:800]}

    # Monthly full-universe reconciliation. Belt-and-suspenders check that
    # the nightly delta didn't quietly miss anything: bulk-fetch every
    # active US equity from Alpaca, cross-reference against our DB, and
    # surface gaps. Auto-acts where confidence is unambiguous.
    # {"monthly_universe_audit": {"_": 1}}
    if event.get("monthly_universe_audit"):
        print("📅 Monthly universe reconciliation starting")

        async def _monthly_audit():
            from app.services.symbol_metadata_service import symbol_metadata_service
            from app.services.hygiene_scorer import (
                score_missing, score_reuse, execute_auto_tier,
            )
            from app.services.scanner import scanner_service
            from app.services.email_service import admin_email_service

            # Verify the full pickle universe in one shot — this re-runs
            # asset_id checks for every symbol, including ones the nightly
            # cadence may have skipped (e.g., excluded from scanner cache).
            all_syms = sorted(scanner_service.data_cache.keys()) if scanner_service.data_cache else []
            verify_summary = await symbol_metadata_service.verify_asset_ids(all_syms)

            # Score + execute AUTO tier (uncapped, all confidence-passes act)
            missing = await score_missing(run_ai=True)
            reuse = await score_reuse()
            auto_summary = await execute_auto_tier(missing + reuse)

            # Count remaining queue
            remaining_reco = sum(1 for it in (missing + reuse) if it.tier == "RECOMMEND")
            remaining_exc = sum(1 for it in (missing + reuse)
                                 if it.tier == "EXCEPTION" and (it.days_missing or 0) >= 7)

            # Summary email
            H2 = "margin:0 0 12px 0;font-size:18px;font-weight:600;"
            P  = "margin:6px 0;line-height:1.45;"
            BTN = (
                "display:inline-block;background:#7A2430;color:#FFF;"
                "padding:10px 18px;text-decoration:none;font-weight:600;"
                "border-radius:4px;margin:8px 0;"
            )
            body = (
                f"<h2 style='{H2}'>📅 Monthly Universe Audit</h2>"
                f"<p style='{P}'>Verified <b>{len(all_syms)}</b> symbols against the full Alpaca universe.</p>"
                f"<p style='{P}'>Auto-resolved: <b>{len(auto_summary.get('delisted', []))}</b> delisted, "
                f"<b>{len(auto_summary.get('migrated', []))}</b> ticker-reuse migrated.</p>"
                f"<p style='{P}'>Queue after audit: <b>{remaining_reco}</b> recommend, "
                f"<b>{remaining_exc}</b> exception.</p>"
                f"<p><a href='https://rigacap.com/admin?tab=hygiene' style='{BTN}'>Open Hygiene Tab</a></p>"
            )
            try:
                await admin_email_service.send_admin_alert(
                    to_email="erik@rigacap.com",
                    subject="📅 RigaCap Monthly Universe Audit",
                    message=body,
                )
            except Exception as ee:
                print(f"⚠️ Monthly audit email failed: {ee}")

            return {
                "status": "ok",
                "verified": len(all_syms),
                "auto": auto_summary,
                "queue": {"recommend": remaining_reco, "exception": remaining_exc},
            }

        try:
            return _run_async(_monthly_audit())
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:800]}

    # Quarterly deep audit. Monthly reconciliation + 90-day corp-actions
    # replay + split-adjustment spot-check. {"quarterly_deep_audit": {"_": 1}}
    if event.get("quarterly_deep_audit"):
        print("📆 Quarterly deep audit starting")

        async def _quarterly_audit():
            from app.services.symbol_metadata_service import symbol_metadata_service
            from app.services.hygiene_scorer import (
                score_missing, score_reuse, execute_auto_tier,
            )
            from app.services.scanner import scanner_service
            from app.services.email_service import admin_email_service

            all_syms = sorted(scanner_service.data_cache.keys()) if scanner_service.data_cache else []

            # Same full-verify as monthly
            await symbol_metadata_service.verify_asset_ids(all_syms)

            # 90-day corp-actions replay — catches anything the 36h window
            # missed during the quarter. Persists each event; duplicates
            # are harmless (idempotent on (symbol, event_type, event_date)).
            corp_events_90 = await symbol_metadata_service.poll_corp_actions(since_hours=90 * 24)

            missing = await score_missing(run_ai=True)
            reuse = await score_reuse()
            auto_summary = await execute_auto_tier(missing + reuse)

            H2 = "margin:0 0 12px 0;font-size:18px;font-weight:600;"
            P  = "margin:6px 0;line-height:1.45;"
            body = (
                f"<h2 style='{H2}'>📆 Quarterly Deep Audit</h2>"
                f"<p style='{P}'>Verified <b>{len(all_syms)}</b> symbols.</p>"
                f"<p style='{P}'>90-day corp-actions replay: <b>{len(corp_events_90)}</b> events touched.</p>"
                f"<p style='{P}'>Auto-resolved: <b>{len(auto_summary.get('delisted', []))}</b> delisted, "
                f"<b>{len(auto_summary.get('migrated', []))}</b> migrated.</p>"
            )
            try:
                await admin_email_service.send_admin_alert(
                    to_email="erik@rigacap.com",
                    subject="📆 RigaCap Quarterly Deep Audit",
                    message=body,
                )
            except Exception as ee:
                print(f"⚠️ Quarterly audit email failed: {ee}")

            return {
                "status": "ok",
                "verified": len(all_syms),
                "corp_events_90d": len(corp_events_90),
                "auto": auto_summary,
            }

        try:
            return _run_async(_quarterly_audit())
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

    if event.get("build_signaled_symbols_5y"):
        cfg = event.get("build_signaled_symbols_5y")
        cfg = cfg if isinstance(cfg, dict) else {}
        years = int(cfg.get("years", 5))
        print(f"🧭 Building {years}yr signaled-symbols artifact (entered + ever_qualified)")

        async def _build_signaled():
            import pandas as _pd, json as _json, boto3 as _b3
            from app.services.backtester import BacktesterService
            if not scanner_service.data_cache:
                try:
                    _c = data_export_service.import_all()
                    if _c:
                        scanner_service.data_cache = _c
                except Exception as _e:
                    return {"error": f"data load failed: {_e}"}
            if not scanner_service.data_cache:
                return {"error": "data_cache empty after import_all"}
            spy = scanner_service.data_cache.get("SPY")
            if spy is None or len(spy) < 260:
                return {"error": "no SPY / insufficient history"}
            end = _pd.Timestamp(spy.index[-1]).normalize()
            start = end - _pd.Timedelta(days=365 * years + 5)

            # 1) ENTERED — the model's actual 5yr picks, via the VALIDATED t30v/ensemble config
            #    (identical to tier_walkforward_service so the entered set is production-faithful).
            bt = BacktesterService()
            bt.trailing_stop_pct = 0.30
            bt.dd_tighten_threshold_pct = 0
            bt.dwap_threshold_pct = 0.05
            bt.near_50d_high_pct = 3.0
            bt.max_positions = 20
            bt.position_size_pct = 0.045
            bt.min_price = 15.0
            bt.cb_pause_basket_enabled = True
            bt.cb_pause_basket_position_size_pct = 10.0
            bt.cb_pause_basket_trail_pct = 8.0
            bt.cb_pause_basket_vix_trigger = 30.0
            res = bt.run_backtest(start_date=start.to_pydatetime(), end_date=end.to_pydatetime(),
                                  strategy_type="ensemble", force_close_at_end=True)
            core_entered = {t.symbol for t in (getattr(res, "trades", []) or [])
                            if getattr(t, "symbol", None)}

            # 2) PRESERVER/CORE ever-qualified — the ranker POOL: step the PRODUCTION ranker weekly
            #    with time-travel, regime filter OFF (a name qualified even on cash days). Union all.
            core_qualified = set()
            d = start + _pd.Timedelta(days=300)   # warmup before the first rank
            n_dates = 0
            while d <= end:
                try:
                    cands = scanner_service.rank_stocks_momentum(
                        as_of_date=d.to_pydatetime(), apply_market_filter=False)
                    for c in (cands or []):
                        if getattr(c, "symbol", None):
                            core_qualified.add(c.symbol)
                    n_dates += 1
                except Exception as _e:
                    pass
                d += _pd.Timedelta(days=7)

            # 3) MAXIMIZER breakout sleeve — the tier the Preserver core never takes. Replay the
            #    PRODUCTION breakout sleeve gated to rotating_bull (5yr regime series from the live
            #    detector), collecting the names it signaled/entered. Read-only (equity discarded).
            bk_entered, bk_qualified = set(), set()
            try:
                from app.services.maximizer_portfolio import replay_sleeve as _replay
                from app.services.market_regime import market_regime_service as _mrs
                _spy = scanner_service.data_cache.get("SPY")
                _vix = scanner_service.data_cache.get("^VIX")
                _hist = _mrs.get_regime_history(_spy, scanner_service.data_cache, _vix,
                                                start_date=start.to_pydatetime(), end_date=end.to_pydatetime(),
                                                sample_frequency="weekly")
                _reg = _pd.Series({_pd.Timestamp(h.date).normalize(): h.regime_type.value
                                   for h in _hist}).sort_index()
                _reg_daily = _reg.reindex(_spy.index, method="ffill").bfill()
                _reg_by_date = {_pd.Timestamp(dd).normalize(): v for dd, v in _reg_daily.items()}
                _collect = {}
                _replay(scanner_service.data_cache, "breakout", start, end, n_positions=15,
                        entry_regimes={"rotating_bull"}, regime_by_date=_reg_by_date, collect=_collect)
                bk_entered = set(_collect.get("entered", set()))
                bk_qualified = set(_collect.get("qualified", set()))
                # Persist the breakout sleeve's DATED WF trades (collect side-channel) → the
                # artifact the previous-holds endpoint reads for the cross-tier Maximizer teaser.
                # These are Maximizer-only by construction (breakout fires only in rotating_bull;
                # the t30v core never uses this sleeve) → no dedup vs the core WF needed.
                _bk_trades = _collect.get("trades", []) or []
                if _bk_trades:
                    _by_sym = {}
                    for _t in _bk_trades:
                        _by_sym.setdefault(_t["symbol"], []).append(_t)
                    _mx_art = {"window_years": years, "start": start.strftime("%Y-%m-%d"),
                               "end": end.strftime("%Y-%m-%d"), "tier": "maximizer", "source": "breakout",
                               "generated_at": end.strftime("%Y-%m-%d"), "trade_count": len(_bk_trades),
                               "symbols": len(_by_sym), "by_symbol": _by_sym}
                    _b3.client("s3", region_name="us-east-1").put_object(
                        Bucket=os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179"),
                        Key="signals/maximizer_wf_trades.json",
                        Body=_json.dumps(_mx_art).encode("utf-8"), ContentType="application/json")
                    print(f"🧭 maximizer_wf_trades: {len(_bk_trades)} trades / {len(_by_sym)} symbols")
            except Exception as _e:
                print(f"⚠️ breakout sleeve pass failed (core-only artifact): {_e}")

            # 4) UNION both tiers → the true Preserver ∪ Maximizer signaled universe
            entered = sorted(core_entered | bk_entered)
            qualified = sorted(core_qualified | bk_qualified | set(entered))

            artifact = {
                "window_years": years,
                "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"),
                "entered": entered, "ever_qualified": qualified,
                "counts": {"entered": len(entered), "ever_qualified": len(qualified),
                           "core_entered": len(core_entered), "breakout_entered": len(bk_entered),
                           "core_qualified": len(core_qualified), "breakout_qualified": len(bk_qualified)},
                "rank_dates": n_dates, "generated_at": end.strftime("%Y-%m-%d"),
            }
            bucket = os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
            _b3.client("s3", region_name="us-east-1").put_object(
                Bucket=bucket, Key="signals/signaled_symbols_5y.json",
                Body=_json.dumps(artifact).encode("utf-8"), ContentType="application/json")
            return {"status": "success", "entered": len(entered), "ever_qualified": len(qualified),
                    "core_entered": len(core_entered), "breakout_entered": len(bk_entered),
                    "core_qualified": len(core_qualified), "breakout_qualified": len(bk_qualified),
                    "rank_dates": n_dates, "start": artifact["start"], "end": artifact["end"]}

        result = _run_async(_build_signaled())
        print(f"🧭 signaled-symbols artifact: {result}")
        return {"statusCode": 200, "body": result}

    if event.get("rebuild_corp_actions_calendar"):
        cfg = event.get("rebuild_corp_actions_calendar")
        cfg = cfg if isinstance(cfg, dict) else {}
        from app.services import pitfwu_store as _ps_rb
        syms = cfg.get("symbols")
        scope = cfg.get("scope")
        # scope="full": the whole clean universe (stock_universe_service cache) — comprehensive,
        # so a name that enters the scoped set later already has its splits. This is what the
        # WEEKLY cron uses (get_universe is only ~150 curated names → would miss small-caps like
        # WETO/REAX). scope="snapshot": just the live scoped top-N.
        if not syms and scope in ("full", "snapshot"):
            try:
                import json as _cj, boto3 as _cb
                from app.services.data_export import S3_BUCKET as _CB
                _cs = _cb.client('s3', region_name='us-east-1')
                if scope == "full":
                    from app.services.stock_universe import S3_UNIVERSE_KEY as _UK
                    uni = _cj.loads(_cs.get_object(Bucket=_CB, Key=_UK)['Body'].read())
                    syms = [s for s in uni.get('symbols', []) if not s.startswith('^')]
                else:
                    _objs = _cs.list_objects_v2(Bucket=_CB, Prefix='signals/universe-history/')
                    _keys = sorted(o['Key'] for o in _objs.get('Contents', []) if o['Key'].endswith('.json'))
                    _topn = int(cfg.get('topn', 600))
                    if _keys:
                        _snap = _cj.loads(_cs.get_object(Bucket=_CB, Key=_keys[-1])['Body'].read())
                        syms = [r['symbol'] for r in _snap.get('rankings', [])
                                if not r.get('is_excluded') and r.get('symbol')][:_topn]
                print(f"🗓️ calendar rebuild scope={scope}: {len(syms or [])} symbols")
            except Exception as _se:
                print(f"⚠️ calendar rebuild scope={scope} load failed: {_se}")
        if not syms:
            syms = sorted(scanner_service.data_cache.keys()) if scanner_service.data_cache else []
        if not syms:
            try:
                from app.core.config import get_universe as _gu
                syms = _gu()
            except Exception:
                syms = []
        res = _ps_rb.rebuild_calendar(syms, years=int(cfg.get("years", 9)))
        print(f"🗓️ corp-actions calendar rebuild: {res}")
        return {"statusCode": 200, "body": res}

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
            return _run_async(_replay())
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
            result = _run_async(_create_drafts())
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
            result = _run_async(_refresh_threads())
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

            # 2. Welcome (paid conversion)
            await _try("welcome", email_service.send_welcome_email(
                to_email=to, name="Erik Kinsman",
            ))

            # 2b. Free welcome (at-signup "you're in")
            await _try("free_welcome", email_service.send_free_welcome_email(
                to_email=to, name="Erik Kinsman", user_id=test_user_id,
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

            # 15-20. Onboarding drip emails (steps 1-6)
            for step in range(1, 7):
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
            result = _run_async(_test_emails())
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
            result = _run_async(_regenerate_charts())
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
            result = _run_async(_generate_track_record_chart())
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

        result = _run_async(_save_wf())
        return {"status": "ok", "simulation": result}

    if event.get("set_newsletter_lead_story"):
        from app.services.newsletter_generator_service import newsletter_generator
        concept = (event["set_newsletter_lead_story"] or {}).get("concept", "")
        if not concept:
            return {"status": "error", "error": "concept required"}
        newsletter_generator.set_lead_story(concept)
        print(f"📰 Newsletter lead story set ({len(concept)} chars)")
        return {"status": "success", "lead_story_set": True, "chars": len(concept)}

    if event.get("generate_newsletter"):
        from app.services.newsletter_generator_service import newsletter_generator
        from app.services.email_service import admin_email_service
        import re as _re

        ADMIN_EMAIL = "erik@rigacap.com"

        def _strip_html(s):
            return _re.sub(r"<[^>]+>", "", s or "") if s else ""

        _nl_cfg = event["generate_newsletter"] if isinstance(event["generate_newsletter"], dict) else {}
        try:
            draft = newsletter_generator.generate_draft(
                force=bool(_nl_cfg.get("force")),
                lead_story=_nl_cfg.get("lead_story"),
                topic_id=_nl_cfg.get("topic_id"),
            )
        except ValueError as ve:
            # Lock-protection guardrail — refusing to overwrite a locked draft
            print(f"⚠️ Newsletter generate refused: {ve}")
            try:
                _run_async(admin_email_service.send_admin_alert(
                    to_email=ADMIN_EMAIL,
                    subject="ℹ️ Newsletter generate skipped — draft already locked",
                    message=f"The Saturday cron tried to generate this week's draft but it's already locked.\n\n{ve}\n\nNo action needed — your locked version will publish Sunday.",
                ))
            except Exception as _e:
                print(f"⚠️ Admin notify (lock-skip) failed: {_e}")
            return {"status": "skipped", "reason": "draft already locked"}

        # Build full-copy body so Erik can read on phone without opening admin
        # UI. Plain text + section dividers; admin_alert wraps in <pre> so
        # whitespace + line breaks render correctly.
        section_blocks = []
        for sec in draft.get("sections", []):
            num = sec.get("num", "??")
            label = sec.get("label", "")
            title = _strip_html(sec.get("title")) if sec.get("title") else ""
            header = f"§{num} · {label.upper()}"
            if title:
                header += f"\n{title}"
            if sec.get("body"):
                section_blocks.append(f"{header}\n\n{sec['body']}")
            elif sec.get("items"):
                items_text = "\n".join(f"  · {_strip_html(i)}" for i in sec["items"])
                section_blocks.append(f"{header}\n\n{items_text}")
            else:
                section_blocks.append(header)

        full_body = "\n\n" + ("\n\n" + ("─" * 60) + "\n\n").join(section_blocks)

        message = f"""The Saturday cron generated this week's Market, Measured draft.

Date: {draft.get('date_display', draft['date'])}
Word count: {draft['word_count']}
Regime: {draft.get('regime', 'unknown')}
SPY: ${draft.get('spy_price', '?')} ({draft.get('spy_change', '?')}%)

To approve and lock: https://rigacap.com/admin (Newsletter tab)
The cron will publish your LOCKED version Sunday 7 PM ET.
If you don't lock by Sunday 7 PM, the send is skipped and you'll get another email.

{"=" * 60}
DRAFT COPY ({draft['word_count']} words)
{"=" * 60}
{full_body}

{"=" * 60}
End of draft. Edit + lock at https://rigacap.com/admin
"""

        try:
            _run_async(admin_email_service.send_admin_alert(
                to_email=ADMIN_EMAIL,
                subject=f"📝 Newsletter draft ready — review + lock by Sunday 7 PM ET ({draft.get('date_display', draft['date'])})",
                message=message,
            ))
            print(f"✉️ Admin notified: draft ready for {draft['date']}")
        except Exception as e:
            print(f"⚠️ Admin notify failed: {e}")

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

        # Newsletter ONLY sends from a locked draft for TODAY'S date. No
        # fallback to the most-recent draft across weeks — that path caused
        # the May 10 incident where a missed Saturday notification meant
        # the Sunday cron fell back to and RE-SENT the May 3 locked issue.
        # If today's draft doesn't exist or isn't locked, the publish
        # window was missed: skip the send, alert admin, leave any unlocked
        # draft sitting in S3 for historical reference.
        try:
            from app.services.newsletter_generator_service import newsletter_generator
            from datetime import datetime as _dt
            today_str = _dt.now().strftime("%Y-%m-%d")
            draft = newsletter_generator.get_draft(today_str)

            # Build a precise skip-reason so the admin email is actionable
            # rather than generic.
            skip_reason = None
            if not draft:
                skip_reason = (
                    f"No draft file exists for {today_str}. The Saturday "
                    f"generator either didn't run or failed to save. "
                    f"Newsletter NOT sent. Investigate worker logs around "
                    f"the most recent Saturday 14:00 UTC cron."
                )
            elif draft.get("status") != "locked":
                skip_reason = (
                    f"Draft for {today_str} exists but is in '{draft.get('status', 'unknown')}' "
                    f"status (not 'locked'). The editorial lock window was "
                    f"missed. Newsletter NOT sent. The unlocked draft is "
                    f"preserved at newsletter/drafts/{today_str}.json for "
                    f"historical reference."
                )

            if skip_reason:
                print(f"⚠️ Sunday newsletter SKIPPED — {skip_reason}")
                try:
                    from app.services.email_service import admin_email_service
                    _run_async(admin_email_service.send_admin_alert(
                        to_email="erik@rigacap.com",
                        subject=f"⚠️ Sunday newsletter SKIPPED ({today_str}) — editorial window missed",
                        message=skip_reason + "\n\nNo fallback re-send of a prior week's issue will occur. To resume normal cadence, lock next Saturday's draft before Sunday 7 PM ET.",
                    ))
                except Exception as _e:
                    print(f"⚠️ Admin notify (sunday-skip) failed: {_e}")
                return {"status": "skipped", "reason": skip_reason}
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
                    # Publish to the public web archive AFTER the email send, so
                    # the public page appears together with the email (lock no
                    # longer auto-publishes — Jun 13 2026).
                    published = False
                    try:
                        _pub_date = draft.get("date")
                        if _pub_date:
                            newsletter_generator.publish_issue(_pub_date)
                            published = True
                    except Exception as _pe:
                        print(f"Newsletter publish_issue failed: {_pe}")
                    return {"status": "ok", "sent": sent, "failed": failed, "published": published, "source": "locked_draft"}

                return _run_async(_send_from_draft())
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
            return _run_async(_send_market_measured())
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

            result = _run_async(_run_biweekly_tpe())
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
    # Direct voice tester — runs the reply generator against canned tweets (no live
    # Twitter scan), so we can iterate on the reply voice instantly and repeatably.
    # {"test_engagement_reply": {}} uses the flagged-example set; pass {"tweets": [
    # {"author":"x","text":"...","topics":["fear"]}]} to test your own.
    if "test_engagement_reply" in event:
        _cfg = event.get("test_engagement_reply")
        _cfg = _cfg if isinstance(_cfg, dict) else {}
        from app.services.engagement_service import engagement_service
        DEFAULT_TWEETS = [
            {"author": "sentimentrader", "topics": ["signal", "fear"],
             "text": "SPX is near 7365, but the NYSE Arms Index sits at 1.14. Some selling pressure is evident, but this is not a panic reading. For traders waiting for a fear-driven entry, the key signal would be a more extreme washout."},
            {"author": "RyanDetrick", "topics": ["breadth", "signal"],
             "text": "Heads up: we just saw a breadth divergence with the S&P near highs but fewer stocks participating. These have preceded some choppy stretches historically."},
            {"author": "unusual_whales", "topics": ["bull market"],
             "text": "Jamie Dimon says this is the best economy he's seen in decades and the bull market has years left to run."},
            {"author": "PeterLBrandt", "topics": ["silver", "prediction"],
             "text": "Silver is coiling for a massive move. My target is $75 by year end. Chart never lies."},
        ]
        tweets = _cfg.get("tweets") or DEFAULT_TWEETS
        out = []
        for t in tweets:
            try:
                reply = engagement_service._generate_comment(
                    tweet_text=t.get("text", ""), author=t.get("author", ""),
                    matched_topics=t.get("topics", []),
                )
            except Exception as _e:
                reply = f"(error: {_e})"
            out.append({"author": t.get("author"), "skip": (reply == ""), "reply": reply})
        for o in out:
            print(f"[VOICE-TEST] @{o['author']}: {'SKIP' if o['skip'] else o['reply']}")
        return {"status": "ok", "results": out}

    if event.get("engagement_opportunities"):
        print("🎯 Engagement opportunities scan")
        try:
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

                if opportunities and opportunities[0].get("error"):
                    return {"status": "error", "error": opportunities[0]["error"]}

                # --- Original research-insight drafts (the "randos") ---
                # Folded into THIS daily email so Erik approves everything in one
                # place. A random gate fires the generator some days, not others →
                # naturally 1-4/week (this job runs Mon-Fri); never a fixed day.
                # {"force_insight": true} / {"insight_prob": x} override for tests.
                async def _build_insight_section(_cfg):
                    import random as _rnd
                    from datetime import datetime as _dt
                    from sqlalchemy import select as _select
                    from app.core.database import async_session as _async_session, SocialPost
                    from app.services.ai_content_service import ai_content_service
                    from app.services.post_scheduler_service import post_scheduler_service
                    from app.core.config import settings as _settings

                    # Build TODAY's real, SANITIZED market state for grounded randos.
                    # Aggregate/generic facts only — NEVER the specific buy-signal
                    # tickers (those are the paywalled product). Best-effort; if it
                    # fails we fall back to the static canon seeds.
                    async def _build_rando_market_state():
                        try:
                            from app.services.data_export import data_export_service as _dx
                            dash = _dx.read_dashboard_json() or {}
                            ms = dash.get("market_stats", {}) or {}
                            rf = dash.get("regime_forecast", {}) or {}
                            bs = dash.get("buy_signals", []) or []
                            sect = {}
                            for s in bs:
                                sc = s.get("sector")
                                if sc:
                                    sect[sc] = sect.get(sc, 0) + 1
                            top_sectors = [k for k, _ in sorted(sect.items(), key=lambda x: -x[1])[:3]]
                            # live book posture (count + cash %), best-effort
                            positions = cash_pct = None
                            try:
                                from app.core.database import ModelPosition, ModelPortfolioState
                                from sqlalchemy import select as _sel, func as _func
                                async with _async_session() as _db2:
                                    pc = await _db2.execute(
                                        _sel(_func.count()).select_from(ModelPosition).where(
                                            ModelPosition.status == "open",
                                            ModelPosition.portfolio_type == "live"))
                                    positions = pc.scalar()
                                    st = await _db2.execute(_sel(ModelPortfolioState).where(
                                        ModelPortfolioState.portfolio_type == "live"))
                                    stobj = st.scalar_one_or_none()
                                    if stobj and stobj.starting_capital:
                                        cash_pct = round(stobj.current_cash / stobj.starting_capital * 100)
                            except Exception:
                                pass
                            # cross-asset moves — generic public market data (no signal leak)
                            cross = []
                            try:
                                import yfinance as _yf
                                _ct = {'TLT': '20Y Treasuries', 'GLD': 'Gold', 'QQQ': 'Nasdaq-100',
                                       'IWM': 'Small caps', 'XLE': 'Energy', 'XLK': 'Tech'}
                                _cd = _yf.download(list(_ct.keys()), period='5d', progress=False)
                                _cl = _cd['Close'] if _cd is not None and 'Close' in _cd.columns.get_level_values(0) else None
                                if _cl is not None and len(_cl) >= 2:
                                    _t, _p = _cl.iloc[-1], _cl.iloc[-2]
                                    for tk, nm in _ct.items():
                                        if tk in _t and tk in _p:
                                            ch = (_t[tk] / _p[tk] - 1) * 100
                                            if not (ch != ch):  # not NaN
                                                cross.append(f"{nm} {'+' if ch >= 0 else ''}{ch:.1f}%")
                            except Exception:
                                pass
                            return {
                                "regime": rf.get("current_regime_name") or ms.get("regime_name"),
                                "outlook": rf.get("outlook"),
                                "spy_change_pct": ms.get("spy_change_pct"),
                                "vix": ms.get("vix_level"),
                                "signal_count": ms.get("signal_count"),
                                "fresh_count": ms.get("fresh_count"),
                                "top_sectors": top_sectors,
                                "positions": positions,
                                "cash_pct": cash_pct,
                                "cross_asset": cross,
                                "data_date": dash.get("data_date"),
                            }
                        except Exception as _e:
                            print(f"⚠️ rando market_state build failed: {_e}")
                            return None

                    try:
                        prob = float(_cfg.get("insight_prob", 0.4))
                        if _cfg.get("force_insight") or _rnd.random() <= prob:
                            mstate = await _build_rando_market_state()
                            use_dynamic = bool(mstate and mstate.get("regime"))
                            async with _async_session() as _db:
                                if use_dynamic:
                                    # mix per post: usually honest-state, sometimes a soft read
                                    lesson = _rnd.choice(ai_content_service.CANON_LESSONS)
                                    lean = "soft_read" if _rnd.random() < 0.25 else "state"
                                    print(f"[RANDO] dynamic (lean={lean}, date={mstate.get('data_date')}, "
                                          f"regime={mstate.get('regime')}, signals={mstate.get('signal_count')})")
                                    for platform in ("twitter", "threads"):
                                        p = await ai_content_service.generate_dynamic_insight(
                                            mstate, platform=platform, lesson=lesson, lean=lean)
                                        if p:
                                            _db.add(p)
                                else:
                                    # fallback: static canon seed
                                    seed_idx = _rnd.randrange(len(ai_content_service.INSIGHT_SEEDS))
                                    print("[RANDO] static seed fallback (no market_state)")
                                    for platform in ("twitter", "threads"):
                                        p = await ai_content_service.generate_research_insight(
                                            platform=platform, seed_idx=seed_idx)
                                        if p:
                                            _db.add(p)
                                await _db.commit()
                        # Render today's research-insight drafts (whatever exists)
                        async with _async_session() as _db:
                            _res = await _db.execute(
                                _select(SocialPost)
                                .where(SocialPost.post_type == "research_insight",
                                       SocialPost.status == "draft")
                                .order_by(SocialPost.id.desc()).limit(12)
                            )
                            _today = _dt.utcnow().date()
                            drafts = [d for d in _res.scalars().all()
                                      if d.created_at and d.created_at.date() == _today]
                        if not drafts:
                            return "", 0
                        blocks = []
                        for d in drafts:
                            tok = post_scheduler_service.generate_approve_token(d.id)
                            post_now = f"https://api.rigacap.com/api/admin/social/posts/{d.id}/approve-email?token={tok}"
                            review = f"{_settings.FRONTEND_URL}/app"
                            txt = (d.text_content or "").replace("\n", "<br>")
                            tags = f"<span style='color:#9ca3af;'>{d.hashtags}</span>" if d.hashtags else ""
                            blocks.append(f"""
                    <tr><td style="padding:8px 0 0;">
                        <div style="background:#fffbeb;border-left:3px solid #f59e0b;padding:12px 14px;border-radius:4px;">
                            <p style="margin:0 0 6px;font-size:11px;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;">
                                ✨ {d.platform} &middot; #{d.id}</p>
                            <p style="margin:0 0 8px;font-size:14px;color:#111827;line-height:1.55;">{txt} {tags}</p>
                            <a href="{post_now}" style="display:inline-block;background:#059669;color:#fff;text-decoration:none;font-size:13px;font-weight:600;padding:7px 16px;border-radius:6px;margin-right:8px;">Post now &rarr;</a>
                            <a href="{review}" style="display:inline-block;color:#6b7280;text-decoration:none;font-size:13px;padding:7px 4px;">Schedule / edit in dashboard</a>
                        </div>
                    </td></tr>""")
                        section = f"""
                    <tr><td style="padding:12px 0 4px;">
                        <span style="font-size:11px;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">
                            Original content &middot; ready to publish</span>
                    </td></tr>
                    {''.join(blocks)}
                    <tr><td style="padding:10px 0;"><div style="border-top:2px solid #e5e7eb;"></div></td></tr>"""
                        return section, len(drafts)
                    except Exception as _e:
                        print(f"⚠️ research-insight section failed: {_e}")
                        return "", 0

                insight_html, insight_count = await _build_insight_section(cfg)

                if not opportunities and not insight_html:
                    print("📭 No engagement opportunities or insights")
                    return {"status": "ok", "opportunities": 0, "insights": 0}

                # Build email
                rows = []
                import html as _html
                for i, opp in enumerate(opportunities, 1):
                    # Show the ENTIRE original post (no truncation) — Erik needs full context
                    # to judge the suggested reply. HTML-escape: external/untrusted tweet text.
                    tweet_preview = _html.escape(opp["tweet_text"] or "").replace("\n", "<br>")
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

                _reply_n = len(opportunities)
                _hdr_bits = []
                if _reply_n:
                    _hdr_bits.append(f"{_reply_n} reply opp{'s' if _reply_n != 1 else ''}")
                if insight_count:
                    _hdr_bits.append(f"{insight_count} draft{'s' if insight_count != 1 else ''}")
                _hdr = " &middot; ".join(_hdr_bits) or "nothing today"

                _reply_block = (f"""
<tr><td style="padding:8px 20px;background:#f9fafb;border-bottom:1px solid #e5e7eb;">
<p style="margin:0;font-size:13px;color:#6b7280;">
Copy a suggested reply, tweak if needed, paste on the post. 5 minutes max.
</p></td></tr>
<tr><td style="padding:4px 20px 16px;">
<table cellpadding="0" cellspacing="0" style="width:100%;">
{''.join(rows)}
</table></td></tr>""" if _reply_n else "")

                _insight_block = (f"""
<tr><td style="padding:4px 20px 0;">
<table cellpadding="0" cellspacing="0" style="width:100%;">
{insight_html}
</table></td></tr>""" if insight_html else "")

                html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f3f4f6;">
<table cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;margin:0 auto;background:#fff;">
<tr><td style="background:#172554;padding:14px 20px;">
<h1 style="margin:0;color:#fff;font-size:17px;font-weight:700;">
🎯 Engagement &amp; Content &middot; {_hdr}
</h1></td></tr>
{_insight_block}
{_reply_block}
<tr><td style="padding:10px 20px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center;">
RigaCap Admin &middot; "Post now" publishes the draft immediately (one click, no login)
</td></tr></table></body></html>"""

                _subj_bits = []
                if _reply_n:
                    _subj_bits.append(f"{_reply_n} engagement")
                if insight_count:
                    _subj_bits.append(f"{insight_count} ready-to-post draft{'s' if insight_count != 1 else ''}")
                _subject = "🎯 " + " + ".join(_subj_bits) if _subj_bits else "🎯 RigaCap daily engagement"

                ok = await admin_email_service.send_email(
                    to_email="erik@rigacap.com",
                    subject=_subject,
                    html_content=html,
                )
                return {
                    "status": "ok" if ok else "email_failed",
                    "opportunities": _reply_n,
                    "insights": insight_count,
                    "accounts_scanned": len([h for h, _, _ in __import__('app.services.engagement_service', fromlist=['MONITORED_ACCOUNTS']).MONITORED_ACCOUNTS]),
                }

            result = _run_async(_scan_engagement())
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
            _invalid_dwap_syms = []
            for _sym, _df in cache.items():
                # Index symbols (^VIX, ^GSPC, …) carry no volume, so DWAP — a volume-weighted
                # average — is always NaN for them. They aren't tradeable and were the perpetual
                # "1 invalid DWAP" in this email. Exclude indices from the indicator-validity counts.
                if _sym.startswith('^'):
                    continue
                if _df is None or len(_df) < 200:
                    continue
                total += 1
                _last = _df.iloc[-1]
                if not _pd.isna(_last.get('dwap')) and _last.get('dwap', 0) > 0:
                    valid_dwap += 1
                else:
                    _invalid_dwap_syms.append(_sym)
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

            # Maximizer book status — give the breakout tier its due in the Signals section
            # (the rows above are all Core/Preserver). Snapshot-only, no price data needed.
            _max = None
            try:
                from app.services import tier_serving as _ts_h
                from app.core.database import async_session as _hsess
                async with _hsess() as _hdb:
                    _max = await _ts_h.tier_public_summary(_hdb, 'maximizer')
            except Exception as _me:
                print(f"maximizer health summary err: {_me}")
            radar_count = len(dash.get('breakout_radar', []) or [])

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
                + _row("DWAP valid", f"{valid_dwap}/{total} ({_pct(valid_dwap, total)})"
                       + (f" — invalid: {', '.join(sorted(_invalid_dwap_syms)[:10])}" if _invalid_dwap_syms else ""), bold=True)
                + _row("MA50 valid", _pct(valid_ma50, total))
                + _row("MA200 valid", _pct(valid_ma200, total))
            )
            signal_rows = (
                _row("Buy signals (Preserver)", f"{buy_count} ({fresh_count} fresh)")
                + _row("Watchlist", str(wl_count))
                + _row("Last ensemble entry", str(last_entry))
                + _row("Market regime", str(regime))
            )
            if _max:
                _mexp = _max.get('exposure')
                _mexp_s = f"{_mexp*100:.0f}%" if isinstance(_mexp, (int, float)) else "n/a"
                signal_rows += (
                    _row("Maximizer book", f"{_max.get('holdings_count', 0)} holdings ({_max.get('new_today', 0)} new today)")
                    + _row("Breakout radar", f"{radar_count} approaching")
                    + _row("Maximizer exposure", _mexp_s)
                )
            else:
                signal_rows += _row("Maximizer book", f"n/a (breakout radar {radar_count} approaching)")
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
            return _run_async(_health_check())
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": str(e)}

    if event.get("daily_emails"):
        daily_config = event.get("daily_emails") if isinstance(event.get("daily_emails"), dict) else {}
        target_emails = daily_config.get("target_emails")
        force_tier = daily_config.get("force_tier")  # admin sample sends: 'preserver' | 'maximizer'
        print(f"📧 Daily email digest triggered" + (f" for {target_emails}" if target_emails else "")
              + (f" [force_tier={force_tier}]" if force_tier else ""))
        try:
            result = _run_async(scheduler_service.send_daily_emails(target_emails=target_emails, force_tier=force_tier))

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

    # Tier announcement campaign (beta testers pick a tier). Test:
    # {"tier_announcement": {"target_emails": ["erik@rigacap.com"]}}
    if event.get("tier_announcement"):
        cfg = event.get("tier_announcement") if isinstance(event.get("tier_announcement"), dict) else {}
        target_emails = cfg.get("target_emails") or []
        print(f"📢 Tier announcement campaign -> {target_emails}")
        async def _send_tier_ann():
            from app.core.database import User as _U
            from app.services.email_service import email_service
            from sqlalchemy import select as _sel, func as _func
            sent, failed = 0, []
            async with async_session() as db:
                for em in target_emails:
                    e = (em or "").strip()
                    if not e:
                        continue
                    try:
                        u = (await db.execute(
                            _sel(_U).where(_func.lower(_U.email) == e.lower()))).scalars().first()
                        ok = await email_service.send_tier_announcement(
                            to_email=e,
                            first_name=(u.name if u and u.name else "there"),
                            user_id=str(u.id) if u else None)
                        sent += 1 if ok else 0
                        if not ok:
                            failed.append(e)
                    except Exception as _e:
                        failed.append(f"{e}: {_e}")
            return {"sent": sent, "failed": failed}
        try:
            res = _run_async(_send_tier_ann())
            print(f"📢 Tier announcement result: {res}")
            return {"status": "success", **res}
        except Exception as e:
            import traceback
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
            result = _run_async(_check_new_users())
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
            result = _run_async(scheduler_service.check_ticker_health())
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
            result = _run_async(scheduler_service._publish_scheduled_posts())
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
            result = _run_async(scheduler_service._send_post_notifications())
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
            result = _run_async(scheduler_service._strategy_auto_analysis())
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
            result = _run_async(scheduler_service.send_onboarding_drip_emails(target_emails=target_emails))
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
            result = _run_async(_seed_and_list_strategies())
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
            result = _run_async(_list_strategies())
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
            result = _run_async(_run_snapshot_backfill())
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
            result = _run_async(_run_simulation())
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
            result = _run_async(_send_all_templates())
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
            ok = _run_async(_send_email())
            return {"status": "sent" if ok else "failed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # Read-only DB query for admin use (no mutations)
    if event.get("maximizer_rebase"):
        # One-time correction (Jul 30 2026): the Maximizer shadow book's base was inflated to
        # ~$146k on Jul 24 by a format-migration double-count (from_state defaulted bk_cash to the
        # full CAP0 while inheriting the old snapshot's positions). The book's returns are
        # scale-invariant (cash, position shares, and vol-target all scale together), so we rescale
        # every new-format snapshot's monetary state by a single factor to put it back on a clean
        # $100k inception WITHOUT altering any inter-day return. Old-format snapshots (Jul 8-23,
        # no bk_cash key) are left untouched — they already tracked ~$98-100k. Dry-run by default;
        # pass {"maximizer_rebase": {"write": true}} to persist.
        cfg = event.get("maximizer_rebase") or {}
        do_write = bool(cfg.get("write", False)) if isinstance(cfg, dict) else False
        target_base = float(cfg.get("target_base", 100000.0)) if isinstance(cfg, dict) else 100000.0

        async def _max_rebase():
            from app.core.database import async_session, MaximizerBookSnapshot
            from sqlalchemy import select
            async with async_session() as db:
                rows = (await db.execute(
                    select(MaximizerBookSnapshot).order_by(MaximizerBookSnapshot.snapshot_date.asc())
                )).scalars().all()
                newfmt = [r for r in rows if isinstance(r.positions_json, dict) and "bk_cash" in r.positions_json]
                if not newfmt:
                    return {"error": "no new-format snapshots found"}
                first = newfmt[0].positions_json
                base = float(first.get("bk_cash") or 0) + sum(
                    float(p.get("shares") or 0) * float(p.get("entry") or 0)
                    for p in (first.get("positions") or [])
                )
                if base <= 0:
                    return {"error": f"bad inception base {base}"}
                f = target_base / base
                preview = []
                for r in newfmt:
                    pj = dict(r.positions_json)
                    old_mv = float(pj.get("max_value") or 0)
                    pj["bk_cash"] = round(float(pj.get("bk_cash") or 0) * f, 6)
                    pj["max_value"] = round(old_mv * f, 6)
                    pj["bk_eq_hist"] = [round(float(x) * f, 6) for x in (pj.get("bk_eq_hist") or [])]
                    pj["positions"] = [
                        {**p, "shares": round(float(p.get("shares") or 0) * f, 8)}
                        for p in (pj.get("positions") or [])
                    ]
                    preview.append({"date": r.snapshot_date.isoformat(),
                                    "old_equity": round(old_mv, 0), "new_equity": round(old_mv * f, 0)})
                    if do_write:
                        r.positions_json = pj
                        r.equity = round(float(r.equity or 0) * f, 6)
                if do_write:
                    await db.commit()
                return {"inception_base": round(base, 0), "factor": round(f, 6),
                        "target_base": target_base, "wrote": do_write,
                        "n_snapshots": len(newfmt), "preview": preview}

        try:
            return _run_async(_max_rebase())
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"error": str(e)}

    if event.get("preserver_rederive"):
        # One-time correction (Jul 30 2026): the Preserver book used to run a parallel return-chain
        # that drifted from Core even with the overlay dormant. It's been rewritten to Core×factor
        # (factor moves only on capitulation days). Preserver has had ZERO capitulation events since
        # inception (every day exposure 1.0), so its correct equity == Core's equity for the entire
        # history → re-derive each snapshot to the Core (live) total_value with factor 1.0. Dry-run
        # by default; pass {"preserver_rederive": {"write": true}} to persist.
        cfg = event.get("preserver_rederive") or {}
        do_write = bool(cfg.get("write", False)) if isinstance(cfg, dict) else False

        async def _pres_rederive():
            from app.core.database import async_session, PreserverBookSnapshot, ModelPortfolioSnapshot
            from sqlalchemy import select
            async with async_session() as db:
                core_rows = (await db.execute(
                    select(ModelPortfolioSnapshot.snapshot_date, ModelPortfolioSnapshot.total_value)
                    .where(ModelPortfolioSnapshot.portfolio_type == "live")
                )).all()
                core_by_date = {}
                for d, v in core_rows:
                    dd = d.date() if hasattr(d, "date") else d
                    core_by_date[dd] = float(v) if v is not None else None
                pres = (await db.execute(
                    select(PreserverBookSnapshot).order_by(PreserverBookSnapshot.snapshot_date.asc())
                )).scalars().all()
                preview, last_core = [], None
                for r in pres:
                    cv = core_by_date.get(r.snapshot_date) or last_core
                    if cv is None:
                        continue
                    last_core = cv
                    preview.append({"date": r.snapshot_date.isoformat(),
                                    "old": round(float(r.equity or 0), 0), "new": round(cv, 0)})
                    if do_write:
                        r.positions_json = {"factor": 1.0, "exposure": 1.0, "core_equity": cv, "positions": []}
                        r.equity = cv
                if do_write:
                    await db.commit()
                return {"wrote": do_write, "n": len(preview), "preview": preview[-6:]}

        try:
            return _run_async(_pres_rederive())
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"error": str(e)}

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
            return _run_async(_db_read())
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
            result = _run_async(_social_admin())
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
                    _run_async(
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
            result = _run_async(_test_push())
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

            result = _run_async(_send_regime_report())
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


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """Tell crawlers to leave the API subdomain alone.

    The marketing site at rigacap.com has its own robots.txt that
    points at the sitemap. api.rigacap.com is for authenticated app
    traffic only — no public pages, no indexable content. Without
    this, Google Search Console reports the subdomain as "Blocked
    due to unauthorized request (401)" because the crawler hits
    auth-required endpoints. Serving an explicit Disallow stops
    the crawler before it tries.
    """
    from fastapi.responses import PlainTextResponse
    body = "User-agent: *\nDisallow: /\n"
    return PlainTextResponse(
        body,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


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


@app.get("/api/market/summary")
async def get_market_summary(admin: User = Depends(get_admin_user)):
    """
    Get complete market summary including regime and sectors
    """
    try:
        state = await market_analysis_service.update_market_state()

        return {
            "regime": state.to_dict(),
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

    # Scope the trade to the strategy that opened it so the exit rule follows the trade,
    # not the user's current tier. Only accept the known sources; anything else = preserver.
    src = request.source if request.source in ("preserver", "breakout") else "preserver"

    position = DBPosition(
        user_id=user.id,
        symbol=symbol,
        entry_date=entry_date,
        entry_price=price,
        stop_loss=round(price * (1 - settings.STOP_LOSS_PCT / 100), 2),
        profit_target=round(price * (1 + settings.PROFIT_TARGET_PCT / 100), 2),
        shares=round(shares, 2),
        highest_price=price,
        source=src,
        status="open"
    )

    db.add(position)

    # Remember the dollar amount for this BUY so the next BuyModal pre-fills
    # the user's actual sizing pattern (a $5K user converges on $5K-shaped
    # defaults, a $20K user on $20K). Falls back to $10K in the frontend if
    # this is null (first ever BUY).
    user.last_position_dollars = round(position.shares * price, 2)

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


@app.get("/api/stock/{symbol}/previous-holds")
async def get_stock_previous_holds(
    symbol: str,
    response: Response,
    include_walkforward: bool = True,
    limit: int = 50,
    user: User = Depends(require_valid_subscription),
    db: AsyncSession = Depends(get_db),
):
    """Prior entry→exit holds for a symbol — powers the chart 'previous holds' overlay.
    Sources (no double-count): Preserver = live model book (ModelPosition); Maximizer =
    tier fills (TierFill tier='maximizer', paired buy→sell); optionally the walk-forward
    backtest (WalkForwardSimulation.trades_json, flagged is_walkforward). gain/loss is
    computed from prices consistently ((exit/entry-1)*100) to avoid pct/fraction ambiguity."""
    from app.core.database import ModelPosition, TierFill, WalkForwardSimulation
    symbol = symbol.upper()
    holds = []

    def _pnl(entry, exit_):
        return round((exit_ / entry - 1) * 100, 1) if entry and exit_ else None

    # Preserver / t30v — the live model book (closed holds)
    try:
        rows = (await db.execute(
            select(ModelPosition).where(
                ModelPosition.symbol == symbol,
                ModelPosition.portfolio_type == "live",
                ModelPosition.exit_date.isnot(None),
            ).order_by(ModelPosition.entry_date.desc()).limit(limit)
        )).scalars().all()
        for r in rows:
            holds.append({
                "entry_date": r.entry_date.strftime('%Y-%m-%d') if r.entry_date else None,
                "entry_price": round(r.entry_price, 2) if r.entry_price else None,
                "exit_date": r.exit_date.strftime('%Y-%m-%d') if r.exit_date else None,
                "exit_price": round(r.exit_price, 2) if r.exit_price else None,
                "pnl_pct": _pnl(r.entry_price, r.exit_price),
                "exit_reason": r.exit_reason,
                "tier": "preserver", "source": "preserver", "is_walkforward": False,
            })
    except Exception as e:
        logger.warning(f"previous-holds ModelPosition failed for {symbol}: {e}")

    # Maximizer — tier fills, pair buy→sell chronologically
    try:
        fills = (await db.execute(
            select(TierFill).where(
                TierFill.symbol == symbol, TierFill.tier == "maximizer"
            ).order_by(TierFill.fill_date)
        )).scalars().all()
        open_buy = None
        for f in fills:
            if f.side == "buy":
                open_buy = f
            elif f.side == "sell" and open_buy is not None:
                holds.append({
                    "entry_date": open_buy.fill_date.strftime('%Y-%m-%d'),
                    "entry_price": round(open_buy.price, 2),
                    "exit_date": f.fill_date.strftime('%Y-%m-%d'),
                    "exit_price": round(f.price, 2),
                    "pnl_pct": _pnl(open_buy.price, f.price),
                    "exit_reason": f.reason,
                    "tier": "maximizer", "source": open_buy.source or "breakout",
                    "is_walkforward": False,
                })
                open_buy = None
    except Exception as e:
        logger.warning(f"previous-holds TierFill failed for {symbol}: {e}")

    # Walk-forward backtest — latest completed sim, parse trades_json, filter this symbol
    if include_walkforward:
        try:
            # Prefer the canonical dashboard walk-forward (is_daily_cache) — the strategy's
            # simulated HOLDS over the full period. Exclude the nightly missed-opportunities
            # run (is_nightly_missed_opps), which is the OPPOSITE of holds.
            wf = (await db.execute(
                select(WalkForwardSimulation).where(
                    WalkForwardSimulation.status == "completed",
                    WalkForwardSimulation.trades_json.isnot(None),
                    WalkForwardSimulation.is_nightly_missed_opps.isnot(True),
                ).order_by(WalkForwardSimulation.is_daily_cache.desc(),
                           WalkForwardSimulation.simulation_date.desc()).limit(1)
            )).scalars().first()
            if wf and wf.trades_json:
                import json as _json
                for t in _json.loads(wf.trades_json):
                    if (t.get("symbol") or "").upper() != symbol:
                        continue
                    ep, xp = t.get("entry_price"), t.get("exit_price")
                    holds.append({
                        "entry_date": (t.get("entry_date") or "")[:10] or None,
                        "entry_price": round(ep, 2) if ep else None,
                        "exit_date": (t.get("exit_date") or "")[:10] or None,
                        "exit_price": round(xp, 2) if xp else None,
                        "pnl_pct": _pnl(ep, xp),
                        "exit_reason": t.get("exit_reason"),
                        # NEVER pass the raw strategy_name — it contains the internal "t30v" term.
                        # These are the core/Preserver momentum strategy's holds.
                        "tier": "preserver", "source": "preserver",
                        "is_walkforward": True,
                    })
        except Exception as e:
            logger.warning(f"previous-holds WF failed for {symbol}: {e}")

    # Maximizer breakout WF trades (signals/maximizer_wf_trades.json) — the divergent holds the
    # breakout sleeve caught that the t30v core never takes. Breakout is Maximizer-only, so no
    # dedup vs the core WF. Flagged is_walkforward + tier='maximizer' for the cross-tier teaser.
    if include_walkforward:
        try:
            import json as _mj, boto3 as _mb, os as _mo
            _s3 = _mb.client("s3", region_name="us-east-1")
            _bkt = _mo.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
            _raw = _s3.get_object(Bucket=_bkt, Key="signals/maximizer_wf_trades.json")["Body"].read()
            _art = _mj.loads(_raw)
            _bysym = _art.get("by_symbol", {})
            _mrows = _bysym.get(symbol, []) or []
            for t in _mrows:
                ep, xp = t.get("entry_price"), t.get("exit_price")
                holds.append({
                    "entry_date": (t.get("entry_date") or "")[:10] or None,
                    "entry_price": round(ep, 2) if ep else None,
                    "exit_date": (t.get("exit_date") or "")[:10] or None,
                    "exit_price": round(xp, 2) if xp else None,
                    "pnl_pct": _pnl(ep, xp),
                    "exit_reason": "time_stop",
                    "tier": "maximizer", "source": "breakout", "is_walkforward": True,
                })
        except Exception as e:
            logger.warning(f"previous-holds maximizer WF failed for {symbol}: {e}")

    holds.sort(key=lambda h: h.get("entry_date") or "", reverse=True)
    response.headers["Cache-Control"] = "no-store"   # never cache — data updates as the book/WF do
    return {"symbol": symbol, "count": len(holds), "holds": holds[:limit]}


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
