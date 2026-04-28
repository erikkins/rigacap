"""Admin API endpoints for user management and service monitoring."""

import json
from datetime import datetime, timedelta
from app.core.timezone import trading_today_start
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.core.database import (
    get_db, User, Subscription, Signal, Position, StrategyDefinition, StrategyEvaluation,
    AutoSwitchConfig, StrategySwitchHistory, WalkForwardSimulation, StrategyGenerationRun,
    engine
)
from app.core.security import get_admin_user
from app.core.config import settings
# scheduler_service is deferred — only used by check_ticker_health admin
# endpoint. Avoiding the eager import shaves cold-start time off the API
# Lambda for routes that never touch the scheduler.
from app.services.strategy_analyzer import strategy_analyzer_service
from sqlalchemy import text

router = APIRouter()


# ============================================================================
# Database Migration
# ============================================================================

@router.get("/data-debug")
async def get_data_debug(admin: User = Depends(get_admin_user)):
    """Debug endpoint to check data availability."""
    from app.services.scanner import scanner_service

    if not scanner_service.data_cache:
        return {"error": "No data in cache", "cache_size": 0}

    # Sample a few symbols
    sample_symbols = list(scanner_service.data_cache.keys())[:5]
    samples = {}
    for sym in sample_symbols:
        df = scanner_service.data_cache[sym]
        samples[sym] = {
            "rows": len(df),
            "columns": list(df.columns),
            "index_type": str(type(df.index)),
            "date_range": f"{df.index[0]} to {df.index[-1]}" if len(df) > 0 else "empty"
        }

    # Count symbols with enough data for 90-day backtest
    min_data_points = 290  # 90 + 200
    enough_data_count = sum(1 for df in scanner_service.data_cache.values() if len(df) >= min_data_points)

    return {
        "cache_size": len(scanner_service.data_cache),
        "symbols_with_290_plus_rows": enough_data_count,
        "samples": samples
    }


@router.post("/migrate")
async def run_database_migration(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """
    Run database migrations to add new tables and columns.
    Safe to run multiple times - uses IF NOT EXISTS.
    """
    migrations = []

    async def run_migration(sql: str, description: str):
        """Run a single migration with its own connection"""
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
            migrations.append(description)
        except Exception as e:
            migrations.append(f"{description}: {str(e)}")

    try:
        # Add new columns to strategy_definitions if they don't exist
        await run_migration("""
            ALTER TABLE strategy_definitions
            ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'manual'
        """, "Added 'source' column to strategy_definitions")

        await run_migration("""
            ALTER TABLE strategy_definitions
            ADD COLUMN IF NOT EXISTS is_custom BOOLEAN DEFAULT FALSE
        """, "Added 'is_custom' column to strategy_definitions")

        # Create strategy_evaluations table
        await run_migration("""
            CREATE TABLE IF NOT EXISTS strategy_evaluations (
                id SERIAL PRIMARY KEY,
                strategy_id INTEGER REFERENCES strategy_definitions(id),
                evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lookback_days INTEGER DEFAULT 90,
                total_return_pct FLOAT,
                sharpe_ratio FLOAT,
                max_drawdown_pct FLOAT,
                win_rate FLOAT,
                total_trades INTEGER,
                recommendation_score FLOAT,
                recommendation_notes TEXT
            )
        """, "Created strategy_evaluations table")

        # Create auto_switch_config table
        await run_migration("""
            CREATE TABLE IF NOT EXISTS auto_switch_config (
                id SERIAL PRIMARY KEY,
                is_enabled BOOLEAN DEFAULT FALSE,
                analysis_frequency VARCHAR(20) DEFAULT 'biweekly',
                min_score_diff_to_switch FLOAT DEFAULT 10.0,
                min_days_since_last_switch INTEGER DEFAULT 14,
                notify_on_analysis BOOLEAN DEFAULT TRUE,
                notify_on_switch BOOLEAN DEFAULT TRUE,
                admin_email VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """, "Created auto_switch_config table")

        # Create strategy_switch_history table
        await run_migration("""
            CREATE TABLE IF NOT EXISTS strategy_switch_history (
                id SERIAL PRIMARY KEY,
                switch_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                from_strategy_id INTEGER REFERENCES strategy_definitions(id),
                to_strategy_id INTEGER REFERENCES strategy_definitions(id),
                trigger VARCHAR(50),
                reason TEXT,
                score_before FLOAT,
                score_after FLOAT
            )
        """, "Created strategy_switch_history table")

        # Create walk_forward_simulations table
        await run_migration("""
            CREATE TABLE IF NOT EXISTS walk_forward_simulations (
                id SERIAL PRIMARY KEY,
                simulation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                reoptimization_frequency VARCHAR(20),
                total_return_pct FLOAT,
                sharpe_ratio FLOAT,
                max_drawdown_pct FLOAT,
                num_strategy_switches INTEGER,
                benchmark_return_pct FLOAT,
                switch_history_json TEXT,
                equity_curve_json TEXT,
                status VARCHAR(20) DEFAULT 'completed'
            )
        """, "Created walk_forward_simulations table")

        # Add status column if table already exists
        await run_migration("""
            ALTER TABLE walk_forward_simulations
            ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'completed'
        """, "Added 'status' column to walk_forward_simulations")

        # Create strategy_generation_runs table
        await run_migration("""
            CREATE TABLE IF NOT EXISTS strategy_generation_runs (
                id SERIAL PRIMARY KEY,
                run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lookback_weeks INTEGER,
                strategy_type VARCHAR(50),
                optimization_metric VARCHAR(50),
                market_regime_detected VARCHAR(50),
                best_params_json TEXT,
                expected_sharpe FLOAT,
                expected_return_pct FLOAT,
                expected_drawdown_pct FLOAT,
                combinations_tested INTEGER,
                status VARCHAR(20) DEFAULT 'completed',
                created_strategy_id INTEGER REFERENCES strategy_definitions(id)
            )
        """, "Created strategy_generation_runs table")

        # Add missing columns to strategy_generation_runs if table already exists
        await run_migration("""
            ALTER TABLE strategy_generation_runs
            ADD COLUMN IF NOT EXISTS expected_drawdown_pct FLOAT
        """, "Added 'expected_drawdown_pct' column to strategy_generation_runs")

        await run_migration("""
            ALTER TABLE strategy_generation_runs
            ADD COLUMN IF NOT EXISTS created_strategy_id INTEGER REFERENCES strategy_definitions(id)
        """, "Added 'created_strategy_id' column to strategy_generation_runs")

        # Comp tracking on subscriptions
        await run_migration("""
            ALTER TABLE subscriptions
            ADD COLUMN IF NOT EXISTS comped_at TIMESTAMP
        """, "Added 'comped_at' column to subscriptions")

        await run_migration("""
            ALTER TABLE subscriptions
            ADD COLUMN IF NOT EXISTS comped_by UUID REFERENCES users(id)
        """, "Added 'comped_by' column to subscriptions")

    except Exception as e:
        import traceback
        print(f"Migration error: {traceback.format_exc()}")
        return {
            "success": False,
            "error": "Migration failed",
            "migrations": migrations
        }

    # Seed strategies if needed
    try:
        seeded = await seed_strategies(db)
        if seeded > 0:
            migrations.append(f"Seeded {seeded} initial strategies")
    except Exception as e:
        migrations.append(f"Seeding error: {str(e)}")

    return {
        "success": True,
        "migrations": migrations
    }


# ============================================================================
# Initial Strategy Definitions
# ============================================================================

INITIAL_STRATEGIES = [
    {
        "name": "DWAP Classic",
        "description": "Buy when price > DWAP x 1.05, fixed 8% stop loss, 20% profit target",
        "strategy_type": "dwap",
        "parameters": {
            "dwap_threshold_pct": 5.0,
            "stop_loss_pct": 8.0,
            "profit_target_pct": 20.0,
            "max_positions": 15,
            "position_size_pct": 6.6,
            "min_volume": 500000,
            "min_price": 20.0,
            "volume_spike_mult": 1.5
        },
        "is_active": False
    },
    {
        "name": "Momentum v2",
        "description": "10/60 day momentum ranking, 15% trailing stop, SPY market filter",
        "strategy_type": "momentum",
        "parameters": {
            "max_positions": 5,
            "position_size_pct": 18.0,
            "short_momentum_days": 10,
            "long_momentum_days": 60,
            "trailing_stop_pct": 15.0,
            "market_filter_enabled": True,
            "rebalance_frequency": "weekly",
            "short_mom_weight": 0.5,
            "long_mom_weight": 0.3,
            "volatility_penalty": 0.2,
            "near_50d_high_pct": 5.0,
            "min_volume": 500000,
            "min_price": 20.0
        },
        "is_active": True
    },
    {
        "name": "DWAP Hybrid (Rocket Catcher)",
        "description": "DWAP entry (+5% cross) with trailing stop exit. Catches breakouts early, lets winners run.",
        "strategy_type": "dwap_hybrid",
        "parameters": {
            "dwap_threshold_pct": 5.0,      # Entry: 5% above DWAP
            "trailing_stop_pct": 10.0,      # Exit: 10% trailing stop (no profit cap)
            "stop_loss_pct": 0.0,           # No fixed stop loss (trailing handles it)
            "max_positions": 8,             # More positions since daily scanning
            "position_size_pct": 12.0,      # Smaller positions, more diversification
            "min_volume": 500000,
            "min_price": 10.0,              # Lower min price to catch more rockets
            "volume_spike_mult": 1.5,
            "market_filter_enabled": True   # Use SPY > 200MA filter
        },
        "is_active": False
    },
    {
        "name": "Concentrated Momentum",
        "description": "Fewer positions, larger bets. AI-discovered parameters optimized for high-conviction plays.",
        "strategy_type": "momentum",
        "parameters": {
            "max_positions": 4,             # Concentrated: fewer positions
            "position_size_pct": 20.0,      # Larger position sizes
            "short_momentum_days": 10,
            "long_momentum_days": 60,
            "trailing_stop_pct": 15.0,
            "market_filter_enabled": True,
            "rebalance_frequency": "weekly",
            "short_mom_weight": 0.5,
            "long_mom_weight": 0.3,
            "volatility_penalty": 0.2,
            "near_50d_high_pct": 5.0,
            "min_volume": 500000,
            "min_price": 20.0
        },
        "is_active": False
    },
    {
        "name": "DWAP+Momentum Ensemble",
        "description": "DWAP timing entry (catches early breakouts) + momentum quality filter (only top-ranked stocks) + trailing stop exit (lets winners run). TPE Trial 37 optimized.",
        "strategy_type": "ensemble",
        "parameters": {
            "dwap_threshold_pct": 6.5,      # TPE Trial 37
            "volume_spike_mult": 1.3,
            "short_momentum_days": 10,
            "long_momentum_days": 60,
            "near_50d_high_pct": 5.0,
            "max_positions": 8,             # TPE Trial 37 (was 6)
            "position_size_pct": 17.0,      # TPE Trial 37 (was 15)
            "trailing_stop_pct": 13.0,      # TPE Trial 37 (was 12)
            "market_filter_enabled": True,
            "min_volume": 500000,
            "min_price": 15.0
        },
        "is_active": False
    }
]


async def seed_strategies(db: AsyncSession) -> int:
    """Seed initial strategies if none exist. Returns count of created strategies."""
    result = await db.execute(select(func.count(StrategyDefinition.id)))
    count = result.scalar()

    if count > 0:
        added = 0

        # Check if DWAP Hybrid exists, add if not (migration for existing DBs)
        hybrid_check = await db.execute(
            select(StrategyDefinition).where(StrategyDefinition.strategy_type == "dwap_hybrid")
        )
        if hybrid_check.scalar_one_or_none() is None:
            hybrid_data = next(
                (s for s in INITIAL_STRATEGIES if s["strategy_type"] == "dwap_hybrid"),
                None
            )
            if hybrid_data:
                strategy = StrategyDefinition(
                    name=hybrid_data["name"],
                    description=hybrid_data["description"],
                    strategy_type=hybrid_data["strategy_type"],
                    parameters=json.dumps(hybrid_data["parameters"]),
                    is_active=hybrid_data["is_active"],
                    activated_at=datetime.utcnow() if hybrid_data["is_active"] else None
                )
                db.add(strategy)
                added += 1

        # Check if Concentrated Momentum exists, add if not
        concentrated_check = await db.execute(
            select(StrategyDefinition).where(StrategyDefinition.name == "Concentrated Momentum")
        )
        if concentrated_check.scalar_one_or_none() is None:
            concentrated_data = next(
                (s for s in INITIAL_STRATEGIES if s["name"] == "Concentrated Momentum"),
                None
            )
            if concentrated_data:
                strategy = StrategyDefinition(
                    name=concentrated_data["name"],
                    description=concentrated_data["description"],
                    strategy_type=concentrated_data["strategy_type"],
                    parameters=json.dumps(concentrated_data["parameters"]),
                    is_active=concentrated_data["is_active"],
                    activated_at=datetime.utcnow() if concentrated_data["is_active"] else None
                )
                db.add(strategy)
                added += 1

        # Check if DWAP+Momentum Ensemble exists, add if not
        ensemble_check = await db.execute(
            select(StrategyDefinition).where(StrategyDefinition.strategy_type == "ensemble")
        )
        if ensemble_check.scalar_one_or_none() is None:
            ensemble_data = next(
                (s for s in INITIAL_STRATEGIES if s["strategy_type"] == "ensemble"),
                None
            )
            if ensemble_data:
                strategy = StrategyDefinition(
                    name=ensemble_data["name"],
                    description=ensemble_data["description"],
                    strategy_type=ensemble_data["strategy_type"],
                    parameters=json.dumps(ensemble_data["parameters"]),
                    is_active=ensemble_data["is_active"],
                    activated_at=datetime.utcnow() if ensemble_data["is_active"] else None
                )
                db.add(strategy)
                added += 1

        if added > 0:
            await db.commit()
        return added

    created = 0
    for strat_data in INITIAL_STRATEGIES:
        strategy = StrategyDefinition(
            name=strat_data["name"],
            description=strat_data["description"],
            strategy_type=strat_data["strategy_type"],
            parameters=json.dumps(strat_data["parameters"]),
            is_active=strat_data["is_active"],
            activated_at=datetime.utcnow() if strat_data["is_active"] else None
        )
        db.add(strategy)
        created += 1

    await db.commit()
    return created


# Response schemas
class UserSummary(BaseModel):
    id: str
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    created_at: str
    last_login: Optional[str]
    subscription_status: Optional[str]
    trial_days_remaining: Optional[int]


class UserListResponse(BaseModel):
    users: List[UserSummary]
    total: int
    page: int
    per_page: int


class ServiceStatus(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    last_check: Optional[str] = None
    error: Optional[str] = None


class AdminStatsResponse(BaseModel):
    total_users: int
    active_trials: int
    paid_subscribers: int
    expired_trials: int
    disabled_users: int
    new_users_today: int
    new_users_week: int
    mrr: float  # Monthly recurring revenue


class ServiceStatusResponse(BaseModel):
    overall_status: str
    services: dict
    metrics: dict


# Strategy Management Schemas
class EvaluationSummary(BaseModel):
    date: Optional[str] = None
    sharpe_ratio: Optional[float] = None
    total_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    win_rate: Optional[float] = None
    recommendation_score: Optional[float] = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    strategy_type: str
    parameters: Dict[str, Any]
    is_active: bool
    created_at: Optional[str] = None
    activated_at: Optional[str] = None
    latest_evaluation: Optional[EvaluationSummary] = None


class StrategyEvaluationDetail(BaseModel):
    strategy_id: int
    name: str
    strategy_type: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    recommendation_score: float
    lookback_days: int


class StrategyAnalysisResponse(BaseModel):
    analysis_date: str
    lookback_days: int
    evaluations: List[StrategyEvaluationDetail]
    recommended_strategy_id: Optional[int] = None
    recommendation_notes: str
    current_active_strategy_id: Optional[int] = None


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users with pagination and filtering."""
    # Base query
    query = select(User).order_by(User.created_at.desc())

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_term)) | (User.name.ilike(search_term))
        )

    # Get total count
    count_query = select(func.count(User.id))
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            (User.email.ilike(search_term)) | (User.name.ilike(search_term))
        )
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    # Get subscription status for each user
    user_summaries = []
    for user in users:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        subscription = sub_result.scalar_one_or_none()

        user_summaries.append(UserSummary(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
            last_login=user.last_login.isoformat() if user.last_login else None,
            subscription_status=subscription.status if subscription else None,
            trial_days_remaining=subscription.days_remaining() if subscription else None
        ))

    return UserListResponse(
        users=user_summaries,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific user."""
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = sub_result.scalar_one_or_none()

    user_dict = user.to_dict()
    if subscription:
        user_dict["subscription"] = subscription.to_dict()

    return user_dict


@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Disable a user account."""
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    user.is_active = False
    await db.commit()

    return {"message": f"User {user.email} has been disabled"}


@router.post("/users/{user_id}/enable")
async def enable_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable a user account."""
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    await db.commit()

    return {"message": f"User {user.email} has been enabled"}


@router.post("/users/{user_id}/extend-trial")
async def extend_trial(
    user_id: str,
    days: int = Query(7, ge=1, le=90),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Extend a user's trial period."""
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = sub_result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=400, detail="User has no subscription")

    if subscription.status not in ["trial", "expired"]:
        raise HTTPException(status_code=400, detail="Can only extend trial subscriptions")

    # Extend trial
    if subscription.trial_end:
        subscription.trial_end = subscription.trial_end + timedelta(days=days)
    else:
        subscription.trial_end = datetime.utcnow() + timedelta(days=days)

    subscription.status = "trial"
    await db.commit()

    return {
        "message": f"Trial extended by {days} days",
        "new_trial_end": subscription.trial_end.isoformat()
    }


@router.post("/users/{user_id}/comp")
async def comp_subscription(
    user_id: str,
    days: int = Query(90, ge=1, le=365),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Grant a complimentary active subscription (no Stripe required)."""
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = sub_result.scalar_one_or_none()

    now = datetime.utcnow()

    if subscription:
        subscription.status = "active"
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=days)
        subscription.cancel_at_period_end = False
        subscription.comped_at = now
        subscription.comped_by = admin.id
    else:
        subscription = Subscription(
            user_id=user.id,
            status="active",
            trial_start=now,
            trial_end=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=days),
            comped_at=now,
            comped_by=admin.id,
        )
        db.add(subscription)

    user.is_active = True
    await db.commit()

    return {
        "message": f"Comp subscription granted for {days} days",
        "expires": subscription.current_period_end.isoformat()
    }


@router.post("/users/{user_id}/revoke-comp")
async def revoke_comp(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke a comped subscription."""
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = sub_result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=400, detail="User has no subscription")

    if subscription.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="Cannot revoke a Stripe-managed subscription. Cancel via Stripe instead.")

    subscription.status = "expired"
    subscription.current_period_end = datetime.utcnow()
    await db.commit()

    return {"message": "Comp subscription revoked"}


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics."""
    now = datetime.utcnow()
    today_start = trading_today_start()
    week_ago = now - timedelta(days=7)

    # Total users
    total_result = await db.execute(select(func.count(User.id)))
    total_users = total_result.scalar()

    # Active trials
    trials_result = await db.execute(
        select(func.count(Subscription.id)).where(
            and_(
                Subscription.status == "trial",
                Subscription.trial_end > now
            )
        )
    )
    active_trials = trials_result.scalar()

    # Paid subscribers
    paid_result = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == "active")
    )
    paid_subscribers = paid_result.scalar()

    # Expired trials
    expired_result = await db.execute(
        select(func.count(Subscription.id)).where(
            and_(
                Subscription.status == "trial",
                Subscription.trial_end <= now
            )
        )
    )
    expired_trials = expired_result.scalar()

    # Disabled users
    disabled_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == False)
    )
    disabled_users = disabled_result.scalar()

    # New users today
    today_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )
    new_users_today = today_result.scalar()

    # New users this week
    week_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )
    new_users_week = week_result.scalar()

    # MRR (Monthly Recurring Revenue) - $10 per subscriber
    mrr = paid_subscribers * 10.0

    return AdminStatsResponse(
        total_users=total_users,
        active_trials=active_trials,
        paid_subscribers=paid_subscribers,
        expired_trials=expired_trials,
        disabled_users=disabled_users,
        new_users_today=new_users_today,
        new_users_week=new_users_week,
        mrr=mrr
    )


@router.get("/service-status", response_model=ServiceStatusResponse)
async def get_service_status(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get service health status."""
    import time

    services = {}
    overall_healthy = True

    # Database check
    try:
        start = time.time()
        await db.execute(select(func.count(User.id)))
        latency = (time.time() - start) * 1000
        services["database"] = ServiceStatus(
            status="ok",
            latency_ms=round(latency, 2)
        ).model_dump()
    except Exception as e:
        services["database"] = ServiceStatus(
            status="error",
            error=str(e)
        ).model_dump()
        overall_healthy = False

    # Market Data (combined Alpaca + yfinance)
    try:
        from app.services.market_data_provider import market_data_provider
        from app.services.scanner import scanner_service
        from app.core.config import settings

        health = market_data_provider.get_health_summary()
        alpaca_health = health.get("alpaca", {})
        yfinance_health = health.get("yfinance", {})

        # Determine overall status
        alpaca_ok = alpaca_health.get("status") != "red"
        yfinance_ok = yfinance_health.get("status") != "red"
        if alpaca_ok and yfinance_ok:
            data_status = "ok"
        elif alpaca_ok or yfinance_ok:
            data_status = "degraded"
        else:
            data_status = "error"

        symbols_loaded = len(scanner_service.data_cache)
        services["market_data"] = {
            "status": data_status,
            "primary": settings.DATA_SOURCE_PRIMARY,
            "symbols_loaded": symbols_loaded,
            "last_fetch": scanner_service.last_fetch_time.isoformat() if hasattr(scanner_service, 'last_fetch_time') and scanner_service.last_fetch_time else None,
            "last_bars_source": market_data_provider.last_bars_source,
            "last_quotes_source": market_data_provider.last_quotes_source,
            "alpaca": {
                "status": alpaca_health.get("status", "unknown"),
                "consecutive_failures": alpaca_health.get("consecutive_failures", 0),
                "last_success": alpaca_health.get("last_success"),
                "total_requests": alpaca_health.get("total_requests", 0),
                "total_failures": alpaca_health.get("total_failures", 0),
            },
            "yfinance": {
                "status": yfinance_health.get("status", "unknown"),
                "consecutive_failures": yfinance_health.get("consecutive_failures", 0),
                "last_success": yfinance_health.get("last_success"),
                "total_requests": yfinance_health.get("total_requests", 0),
                "total_failures": yfinance_health.get("total_failures", 0),
            },
        }
    except Exception as e:
        services["market_data"] = {
            "status": "error",
            "error": str(e)
        }

    # Stripe check
    if settings.STRIPE_SECRET_KEY:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe.Account.retrieve()
            services["stripe"] = {"status": "ok"}
        except Exception as e:
            services["stripe"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        services["stripe"] = {"status": "not_configured"}

    # Scanner status
    try:
        from app.services.scanner import scanner_service

        # Count today's signals
        today_start = trading_today_start()
        signals_result = await db.execute(
            select(func.count(Signal.id)).where(Signal.created_at >= today_start)
        )
        signals_today = signals_result.scalar()

        services["scanner"] = {
            "status": "ok",
            "signals_today": signals_today,
            "cached_symbols": len(scanner_service.data_cache)
        }

        # Add data history info for first few symbols
        if scanner_service.data_cache:
            sample_symbols = list(scanner_service.data_cache.keys())[:3]
            data_samples = {}
            for sym in sample_symbols:
                df = scanner_service.data_cache[sym]
                data_samples[sym] = {
                    "rows": len(df),
                    "date_range": f"{df.index[0]} to {df.index[-1]}" if len(df) > 0 else "empty"
                }
            services["scanner"]["data_samples"] = data_samples
    except Exception as e:
        services["scanner"] = {
            "status": "error",
            "error": str(e)
        }

    # Get metrics
    stats_result = await db.execute(select(func.count(User.id)))
    total_users = stats_result.scalar()

    paid_result = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == "active")
    )
    paid_subscribers = paid_result.scalar()

    trials_result = await db.execute(
        select(func.count(Subscription.id)).where(
            and_(
                Subscription.status == "trial",
                Subscription.trial_end > datetime.utcnow()
            )
        )
    )
    active_trials = trials_result.scalar()

    metrics = {
        "total_users": total_users,
        "active_trials": active_trials,
        "paid_subscribers": paid_subscribers,
        "mrr": paid_subscribers * 10.0
    }

    return ServiceStatusResponse(
        overall_status="healthy" if overall_healthy else "degraded",
        services=services,
        metrics=metrics
    )


@router.get("/pipeline-log")
async def get_pipeline_log(admin: User = Depends(get_admin_user)):
    """Get the structured log from the last daily scan pipeline run."""
    import os
    import boto3
    bucket = os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
    try:
        resp = boto3.client('s3', region_name='us-east-1').get_object(
            Bucket=bucket, Key="signals/pipeline_log.json"
        )
        return json.loads(resp["Body"].read())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"No pipeline log found: {str(e)[:100]}")


@router.get("/parquet-divergence")
async def get_parquet_divergence(
    days: int = Query(7, ge=1, le=90, description="Window in days"),
    recent_limit: int = Query(20, ge=0, le=200, description="Number of recent raw events to return"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Summary of parquet vs pickle divergences from the Stage 3a observation
    window. Counts by divergence_type, top symbols by event count, and a
    sample of the most recent raw events for drill-down.

    Used to gate the cutover from pickle to parquet — see
    project_parquet_stage3_plan.md. Acceptance for moving to Stage 3b is
    zero divergences on close/volume/indicator columns for 7 consecutive
    days, OR all observed divergences are explainable + filterable.
    """
    from app.core.database import ParquetDivergenceEvent
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Total + breakdown by type
    by_type_rows = (await db.execute(
        select(
            ParquetDivergenceEvent.divergence_type,
            func.count(ParquetDivergenceEvent.id).label("n"),
        )
        .where(ParquetDivergenceEvent.detected_at >= cutoff)
        .group_by(ParquetDivergenceEvent.divergence_type)
        .order_by(desc("n"))
    )).all()
    by_type = {row.divergence_type: row.n for row in by_type_rows}
    total = sum(by_type.values())

    # Top symbols by event count
    by_symbol_rows = (await db.execute(
        select(
            ParquetDivergenceEvent.symbol,
            func.count(ParquetDivergenceEvent.id).label("n"),
        )
        .where(ParquetDivergenceEvent.detected_at >= cutoff)
        .group_by(ParquetDivergenceEvent.symbol)
        .order_by(desc("n"))
        .limit(20)
    )).all()
    top_symbols = [{"symbol": row.symbol, "events": row.n} for row in by_symbol_rows]

    # Day-by-day counts so we can spot a flaky day vs a chronic divergence
    by_day_rows = (await db.execute(
        select(
            func.date(ParquetDivergenceEvent.detected_at).label("day"),
            func.count(ParquetDivergenceEvent.id).label("n"),
        )
        .where(ParquetDivergenceEvent.detected_at >= cutoff)
        .group_by("day")
        .order_by(desc("day"))
    )).all()
    by_day = [{"date": str(row.day), "events": row.n} for row in by_day_rows]

    # Recent raw events for drill-down
    recent = []
    if recent_limit > 0:
        recent_rows = (await db.execute(
            select(ParquetDivergenceEvent)
            .order_by(desc(ParquetDivergenceEvent.detected_at))
            .limit(recent_limit)
        )).scalars().all()
        for ev in recent_rows:
            details = None
            if ev.details_json:
                try:
                    details = json.loads(ev.details_json)
                except Exception:
                    details = ev.details_json[:500]
            recent.append({
                "id": ev.id,
                "detected_at": ev.detected_at.isoformat() if ev.detected_at else None,
                "symbol": ev.symbol,
                "type": ev.divergence_type,
                "pickle_rows": ev.pickle_row_count,
                "parquet_rows": ev.parquet_row_count,
                "details": details,
            })

    return {
        "window_days": days,
        "total_events": total,
        "by_type": by_type,
        "top_symbols": top_symbols,
        "by_day": by_day,
        "recent_events": recent,
        "stage_status": _interpret_divergence_status(by_type, by_day),
    }


def _interpret_divergence_status(by_type: dict, by_day: list) -> dict:
    """
    Compute a quick verdict on whether we're ready to advance to Stage 3b.
    Mirrors the acceptance criteria in project_parquet_stage3_plan.md.
    """
    total = sum(by_type.values())
    structural_count = sum(
        n for t, n in by_type.items()
        if t in ("missing_in_pickle", "missing_in_parquet", "row_count_diff",
                 "column_set_diff", "value_diff", "compare_error")
    )
    consecutive_clean_days = 0
    for d in by_day:
        if d["events"] == 0:
            consecutive_clean_days += 1
        else:
            break
    return {
        "total_events": total,
        "structural_events": structural_count,
        "consecutive_clean_days": consecutive_clean_days,
        "ready_for_stage_3b": structural_count == 0 and consecutive_clean_days >= 7,
    }


@router.post("/ticker-health-check")
async def run_ticker_health_check(
    admin: User = Depends(get_admin_user)
):
    """
    Manually trigger the ticker health check.

    Checks:
    - All open positions for valid data
    - Must-include symbols from stock universe

    Sends alert email if issues found.
    """
    from app.services.scheduler import scheduler_service
    try:
        await scheduler_service.check_ticker_health()
        return {
            "status": "completed",
            "message": "Health check completed. Alert email sent if issues found."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Health check failed"
        )


@router.get("/ticker-health-check")
async def get_ticker_health(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current ticker health status without sending alerts.

    Returns list of any problematic tickers.
    """
    from app.services.scanner import scanner_service
    from app.services.stock_universe import MUST_INCLUDE
    import yfinance as yf

    issues = []

    # Check open positions
    result = await db.execute(
        select(Position).where(Position.status == "open")
    )
    positions = result.scalars().all()

    for pos in positions:
        symbol = pos.symbol

        # Check if in cache with recent data
        has_data = False
        if symbol in scanner_service.data_cache:
            df = scanner_service.data_cache[symbol]
            if not df.empty:
                last_date = df.index[-1]
                days_old = (datetime.utcnow() - last_date.to_pydatetime().replace(tzinfo=None)).days
                if days_old <= 7:
                    has_data = True

        if not has_data:
            # Try yfinance
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="5d")
                if hist.empty:
                    issues.append({
                        "symbol": symbol,
                        "type": "position",
                        "issue": "No data available",
                        "entry_date": pos.entry_date.strftime('%Y-%m-%d') if pos.entry_date else None,
                        "entry_price": pos.entry_price
                    })
            except Exception as e:
                issues.append({
                    "symbol": symbol,
                    "type": "position",
                    "issue": f"Fetch failed: {str(e)[:50]}",
                    "entry_date": pos.entry_date.strftime('%Y-%m-%d') if pos.entry_date else None,
                    "entry_price": pos.entry_price
                })

    # Check sample of must-includes
    must_check = MUST_INCLUDE[:10]
    for symbol in must_check:
        if any(i['symbol'] == symbol for i in issues):
            continue

        has_data = symbol in scanner_service.data_cache and not scanner_service.data_cache[symbol].empty
        if not has_data:
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="5d")
                if hist.empty:
                    issues.append({
                        "symbol": symbol,
                        "type": "must_include",
                        "issue": "No data available"
                    })
            except Exception as e:
                issues.append({
                    "symbol": symbol,
                    "type": "must_include",
                    "issue": f"Fetch failed: {str(e)[:50]}"
                })

    return {
        "status": "healthy" if not issues else "issues_found",
        "positions_checked": len(positions),
        "must_includes_checked": len(must_check),
        "issues_count": len(issues),
        "issues": issues
    }


# ============================================================================
# Strategy Management Endpoints
# ============================================================================

@router.get("/strategies", response_model=List[StrategyResponse])
async def list_strategies(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all trading strategies with their latest evaluation.

    Returns all strategies in the library with performance metrics
    from the most recent evaluation.
    """
    # Seed strategies if needed
    seeded = await seed_strategies(db)
    if seeded > 0:
        print(f"Seeded {seeded} initial strategies")

    # Get all strategies
    result = await db.execute(
        select(StrategyDefinition).order_by(StrategyDefinition.id)
    )
    strategies = result.scalars().all()

    responses = []
    for strat in strategies:
        # Get latest evaluation
        eval_result = await db.execute(
            select(StrategyEvaluation)
            .where(StrategyEvaluation.strategy_id == strat.id)
            .order_by(desc(StrategyEvaluation.evaluation_date))
            .limit(1)
        )
        latest_eval = eval_result.scalar_one_or_none()

        latest_eval_summary = None
        if latest_eval:
            latest_eval_summary = EvaluationSummary(
                date=latest_eval.evaluation_date.isoformat() if latest_eval.evaluation_date else None,
                sharpe_ratio=latest_eval.sharpe_ratio,
                total_return_pct=latest_eval.total_return_pct,
                max_drawdown_pct=latest_eval.max_drawdown_pct,
                win_rate=latest_eval.win_rate,
                recommendation_score=latest_eval.recommendation_score
            )

        responses.append(StrategyResponse(
            id=strat.id,
            name=strat.name,
            description=strat.description,
            strategy_type=strat.strategy_type,
            parameters=json.loads(strat.parameters),
            is_active=strat.is_active,
            created_at=strat.created_at.isoformat() if strat.created_at else None,
            activated_at=strat.activated_at.isoformat() if strat.activated_at else None,
            latest_evaluation=latest_eval_summary
        ))

    return responses


@router.get("/strategies/active", response_model=StrategyResponse)
async def get_active_strategy(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the currently active trading strategy."""
    # Seed strategies if needed
    await seed_strategies(db)

    result = await db.execute(
        select(StrategyDefinition).where(StrategyDefinition.is_active == True)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="No active strategy found")

    # Get latest evaluation
    eval_result = await db.execute(
        select(StrategyEvaluation)
        .where(StrategyEvaluation.strategy_id == strategy.id)
        .order_by(desc(StrategyEvaluation.evaluation_date))
        .limit(1)
    )
    latest_eval = eval_result.scalar_one_or_none()

    latest_eval_summary = None
    if latest_eval:
        latest_eval_summary = EvaluationSummary(
            date=latest_eval.evaluation_date.isoformat() if latest_eval.evaluation_date else None,
            sharpe_ratio=latest_eval.sharpe_ratio,
            total_return_pct=latest_eval.total_return_pct,
            max_drawdown_pct=latest_eval.max_drawdown_pct,
            win_rate=latest_eval.win_rate,
            recommendation_score=latest_eval.recommendation_score
        )

    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        strategy_type=strategy.strategy_type,
        parameters=json.loads(strategy.parameters),
        is_active=strategy.is_active,
        created_at=strategy.created_at.isoformat() if strategy.created_at else None,
        activated_at=strategy.activated_at.isoformat() if strategy.activated_at else None,
        latest_evaluation=latest_eval_summary
    )


@router.post("/strategies/{strategy_id}/activate", response_model=StrategyResponse)
async def activate_strategy(
    strategy_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Activate a strategy (deactivates current active strategy).

    Only one strategy can be active at a time.
    """
    # Find the strategy to activate
    result = await db.execute(
        select(StrategyDefinition).where(StrategyDefinition.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Deactivate all other strategies
    all_strategies = await db.execute(select(StrategyDefinition))
    for strat in all_strategies.scalars():
        strat.is_active = False

    # Activate the selected strategy
    strategy.is_active = True
    strategy.activated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(strategy)

    # Get latest evaluation
    eval_result = await db.execute(
        select(StrategyEvaluation)
        .where(StrategyEvaluation.strategy_id == strategy.id)
        .order_by(desc(StrategyEvaluation.evaluation_date))
        .limit(1)
    )
    latest_eval = eval_result.scalar_one_or_none()

    latest_eval_summary = None
    if latest_eval:
        latest_eval_summary = EvaluationSummary(
            date=latest_eval.evaluation_date.isoformat() if latest_eval.evaluation_date else None,
            sharpe_ratio=latest_eval.sharpe_ratio,
            total_return_pct=latest_eval.total_return_pct,
            max_drawdown_pct=latest_eval.max_drawdown_pct,
            win_rate=latest_eval.win_rate,
            recommendation_score=latest_eval.recommendation_score
        )

    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        strategy_type=strategy.strategy_type,
        parameters=json.loads(strategy.parameters),
        is_active=strategy.is_active,
        created_at=strategy.created_at.isoformat() if strategy.created_at else None,
        activated_at=strategy.activated_at.isoformat() if strategy.activated_at else None,
        latest_evaluation=latest_eval_summary
    )


@router.post("/strategies/analyze", response_model=StrategyAnalysisResponse)
async def run_strategy_analysis(
    lookback_days: int = Query(30, ge=20, le=365),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Run backtest analysis on all strategies.

    Backtests each strategy over the specified lookback period
    and generates AI-powered recommendations based on performance.

    Args:
        lookback_days: Number of days to backtest (default: 90, 3 months)

    Returns:
        Performance comparison and recommendation
    """
    # Seed strategies if needed
    await seed_strategies(db)

    try:
        result = await strategy_analyzer_service.evaluate_all_strategies(
            db=db,
            lookback_days=lookback_days
        )

        return StrategyAnalysisResponse(
            analysis_date=result['analysis_date'],
            lookback_days=result['lookback_days'],
            evaluations=[
                StrategyEvaluationDetail(
                    strategy_id=e['strategy_id'],
                    name=e['name'],
                    strategy_type=e['strategy_type'],
                    total_return_pct=e['total_return_pct'],
                    sharpe_ratio=e['sharpe_ratio'],
                    max_drawdown_pct=e['max_drawdown_pct'],
                    win_rate=e['win_rate'],
                    total_trades=e['total_trades'],
                    recommendation_score=e['recommendation_score'],
                    lookback_days=e['lookback_days']
                )
                for e in result['evaluations']
            ],
            recommended_strategy_id=result['recommended_strategy_id'],
            recommendation_notes=result['recommendation_notes'],
            current_active_strategy_id=result['current_active_strategy_id']
        )
    except Exception as e:
        import traceback
        error_detail = str(e) if str(e) else type(e).__name__
        print(f"Strategy analysis error: {error_detail}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {error_detail}"
        )


@router.get("/strategies/analysis", response_model=StrategyAnalysisResponse)
async def get_latest_analysis(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the most recent strategy analysis results.

    Returns cached results from the last analysis run.
    """
    result = await strategy_analyzer_service.get_latest_analysis(db)

    if not result:
        raise HTTPException(
            status_code=404,
            detail="No analysis results found. Run /strategies/analyze first."
        )

    return StrategyAnalysisResponse(
        analysis_date=result['analysis_date'],
        lookback_days=result['lookback_days'],
        evaluations=[
            StrategyEvaluationDetail(
                strategy_id=e['strategy_id'],
                name=e['name'],
                strategy_type=e['strategy_type'],
                total_return_pct=e['total_return_pct'],
                sharpe_ratio=e['sharpe_ratio'],
                max_drawdown_pct=e['max_drawdown_pct'],
                win_rate=e['win_rate'],
                total_trades=e['total_trades'],
                recommendation_score=e['recommendation_score'],
                lookback_days=e['lookback_days']
            )
            for e in result['evaluations']
        ],
        recommended_strategy_id=result['recommended_strategy_id'],
        recommendation_notes=result['recommendation_notes'],
        current_active_strategy_id=result['current_active_strategy_id']
    )


@router.post("/strategies/seed")
async def seed_strategies_endpoint(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually seed initial strategies.

    This is called automatically when listing strategies,
    but can be triggered manually if needed.
    """
    count = await seed_strategies(db)
    return {
        "message": f"Seeded {count} strategies" if count > 0 else "Strategies already exist",
        "count": count
    }


# ============================================================================
# Strategy Generation Endpoints
# ============================================================================

@router.post("/strategies/generate")
async def generate_strategy(
    lookback_weeks: int = Query(6, ge=4, le=52),
    strategy_type: str = Query("momentum"),
    optimization_metric: str = Query("sharpe"),
    auto_create: bool = Query(False),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    AI-powered strategy parameter optimization.

    Runs grid search over parameter ranges adapted to current market conditions.

    Args:
        lookback_weeks: Weeks of data for optimization (4-52)
        strategy_type: "momentum" or "dwap"
        optimization_metric: "sharpe", "return", or "calmar"
        auto_create: Whether to automatically create a strategy from results

    Returns:
        Best parameters found and expected metrics
    """
    from app.services.strategy_generator import strategy_generator_service

    try:
        result = await strategy_generator_service.generate_optimized_strategy(
            db=db,
            lookback_weeks=lookback_weeks,
            strategy_type=strategy_type,
            optimization_metric=optimization_metric,
            auto_create=auto_create
        )

        return {
            "success": True,
            "best_params": result.best_params,
            "expected_sharpe": result.expected_sharpe,
            "expected_return_pct": result.expected_return_pct,
            "expected_drawdown_pct": result.expected_drawdown_pct,
            "combinations_tested": result.combinations_tested,
            "market_regime": result.market_regime,
            "top_5_results": result.top_5_results
        }
    except Exception as e:
        import traceback
        error_msg = str(e) if str(e) else type(e).__name__
        print(f"Strategy generation error: {error_msg}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {error_msg}")


@router.get("/strategies/generations")
async def list_generation_runs(
    limit: int = Query(10, ge=1, le=50),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List recent AI strategy generation runs."""
    from app.services.strategy_generator import strategy_generator_service

    runs = await strategy_generator_service.get_generation_history(db, limit=limit)
    return {"runs": runs, "total": len(runs)}


# ============================================================================
# Walk-Forward Simulation Endpoints
# ============================================================================

@router.post("/strategies/walk-forward/start")
async def start_walk_forward_async(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    frequency: str = Query("biweekly", description="Reoptimization frequency"),
    min_score_diff: float = Query(10.0, ge=0, le=50),
    enable_ai: bool = Query(True, description="Enable AI optimization at each period"),
    max_symbols: int = Query(50, ge=10, le=500, description="Max symbols to use (50=fast, 500=full)"),
    strategy_id: int = Query(None, description="Fixed strategy ID (if set, uses only this strategy, no switching)"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a walk-forward simulation asynchronously.

    Creates a job record and invokes Lambda asynchronously. Use the status
    endpoint to poll for completion.

    If strategy_id is provided, uses only that strategy (no auto-switching or AI).
    """
    print(f"[WALK-FORWARD] Endpoint called: start={start_date}, end={end_date}, ai={enable_ai}, symbols={max_symbols}")

    from datetime import datetime
    from app.services.walk_forward_service import walk_forward_service
    import boto3
    import os

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if end <= start:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # Create a pending job record in the database
    job = WalkForwardSimulation(
        simulation_date=datetime.utcnow(),
        start_date=start,
        end_date=end,
        reoptimization_frequency=frequency,
        status="pending",
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

    print(f"[WALK-FORWARD] Created job {job_id}, invoking Lambda async...")

    # Check pre-requisites before running
    from app.services.scanner import scanner_service
    if not scanner_service.data_cache:
        job.status = "failed"
        job.switch_history_json = json.dumps({"error": "No market data loaded. Please wait for data to load or trigger /warmup."})
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="No market data loaded. Please wait for data to load or run /api/warmup first."
        )

    # Check if strategies exist
    strat_count = await db.execute(select(func.count(StrategyDefinition.id)))
    if strat_count.scalar() == 0:
        await seed_strategies(db)  # Auto-seed if none exist
        print("[WALK-FORWARD] Auto-seeded strategies")

    print(f"[WALK-FORWARD] Pre-checks passed: {len(scanner_service.data_cache)} symbols loaded, SPY={'SPY' in scanner_service.data_cache}")

    # Try Step Functions first (handles long simulations), fall back to Lambda async, then sync
    sfn_arn = os.environ.get('STEP_FUNCTIONS_ARN')
    sfn_input = {
        "job_id": job_id,
        "start_date": start_date,
        "end_date": end_date,
        "frequency": frequency,
        "min_score_diff": min_score_diff,
        "enable_ai": enable_ai,
        "max_symbols": max_symbols,
        "strategy_id": strategy_id,
        "n_trials": 30
    }

    if sfn_arn:
        try:
            sfn_client = boto3.client('stepfunctions', region_name='us-east-1')
            import time
            execution = sfn_client.start_execution(
                stateMachineArn=sfn_arn,
                name=f"wf-sim-{job_id}-{int(time.time())}",
                input=json.dumps(sfn_input)
            )
            job.step_functions_arn = execution['executionArn']
            await db.commit()
            print(f"[WALK-FORWARD] Step Functions started for job {job_id}: {execution['executionArn']}")
            return {
                "job_id": job_id,
                "status": "pending",
                "execution_arn": execution['executionArn'],
                "message": "Simulation started via Step Functions. Poll /status/{job_id} for results."
            }
        except Exception as sfn_err:
            print(f"[WALK-FORWARD] Step Functions failed: {sfn_err}, falling back to Lambda async...")

    # Fallback: invoke Lambda asynchronously
    try:
        lambda_client = boto3.client('lambda', region_name='us-east-1')
        payload = {
            "walk_forward_job": {
                "job_id": job_id,
                "start_date": start_date,
                "end_date": end_date,
                "frequency": frequency,
                "min_score_diff": min_score_diff,
                "enable_ai": enable_ai,
                "max_symbols": max_symbols,
                "strategy_id": strategy_id
            }
        }
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'rigacap-prod-api'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        print(f"[WALK-FORWARD] Lambda invoked async for job {job_id}, strategy_id={strategy_id}")
    except Exception as e:
        print(f"[WALK-FORWARD] Failed to invoke Lambda async: {e}, running synchronously...")
        # Fallback: run synchronously (for local dev)
        try:
            result = await walk_forward_service.run_walk_forward_simulation(
                db=db,
                start_date=start,
                end_date=end,
                reoptimization_frequency=frequency,
                min_score_diff=min_score_diff,
                enable_ai_optimization=enable_ai,
                max_symbols=max_symbols,
                existing_job_id=job_id,
                fixed_strategy_id=strategy_id
            )
            return {
                "job_id": job_id,
                "status": "completed",
                "total_return_pct": result.total_return_pct,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown_pct": result.max_drawdown_pct,
                "num_strategy_switches": result.num_strategy_switches,
                "benchmark_return_pct": result.benchmark_return_pct,
                "equity_curve": result.equity_curve,
                "switch_history": [
                    {
                        "date": s.date,
                        "from_strategy": s.from_strategy_name,
                        "to_strategy": s.to_strategy_name,
                        "reason": s.reason,
                        "score_before": s.score_before,
                        "score_after": s.score_after,
                        "is_ai_generated": s.is_ai_generated,
                        "ai_params": s.ai_params if s.is_ai_generated else None,
                    }
                    for s in result.switch_history
                ],
                "errors": result.errors if hasattr(result, 'errors') else [],
                "trades": [
                    {
                        "period_start": t.period_start,
                        "period_end": t.period_end,
                        "strategy_name": t.strategy_name,
                        "symbol": t.symbol,
                        "entry_date": t.entry_date,
                        "exit_date": t.exit_date,
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "shares": t.shares,
                        "pnl_pct": t.pnl_pct,
                        "pnl_dollars": t.pnl_dollars,
                        "exit_reason": t.exit_reason
                    }
                    for t in (result.trades if hasattr(result, 'trades') else [])
                ],
            }
        except Exception as sync_err:
            import traceback
            error_detail = f"{str(sync_err)}"
            print(f"[WALK-FORWARD] Sync execution failed: {error_detail}")
            print(f"[WALK-FORWARD] Traceback: {traceback.format_exc()}")
            job.status = "failed"
            job.switch_history_json = json.dumps({"error": error_detail})
            await db.commit()
            raise HTTPException(status_code=500, detail=f"Simulation failed: {error_detail}")

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Simulation started. Poll /status/{job_id} for results."
    }


@router.get("/strategies/walk-forward/status/{job_id}")
async def get_walk_forward_status(
    job_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check status of a walk-forward simulation job.

    Returns status and results when complete.
    """
    from app.services.walk_forward_service import walk_forward_service

    result = await db.execute(
        select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": job_id,
        "status": job.status,
        "started_at": job.simulation_date.isoformat() if job.simulation_date else None,
    }

    if job.status == "completed":
        # Get full details
        details = await walk_forward_service.get_simulation_details(db, job_id)
        if details:
            response.update(details)
    elif job.status == "failed":
        # Return error info
        if job.switch_history_json:
            error_info = json.loads(job.switch_history_json)
            response["error"] = error_info.get("error", "Unknown error")

    return response


@router.post("/strategies/walk-forward")
async def run_walk_forward(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    frequency: str = Query("biweekly", description="Reoptimization frequency"),
    min_score_diff: float = Query(10.0, ge=0, le=50),
    enable_ai: bool = Query(True, description="Enable AI optimization at each period"),
    max_symbols: int = Query(50, ge=10, le=500, description="Max symbols to use"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Run walk-forward simulation with AI optimization over a historical period.

    NOTE: When enable_ai=true, this endpoint automatically uses async processing
    to avoid API Gateway timeout. Poll the returned job_id for results.

    At each reoptimization period:
    1. Evaluates existing strategies using data available at that point
    2. Runs AI parameter optimization to detect emerging trends
    3. Compares AI-optimized params against existing strategies
    4. Switches to best option if it beats current by min_score_diff

    Args:
        start_date: Simulation start date (YYYY-MM-DD)
        end_date: Simulation end date (YYYY-MM-DD)
        frequency: "weekly", "biweekly", or "monthly"
        min_score_diff: Minimum score difference to trigger switch
        enable_ai: Whether to run AI param optimization each period
        max_symbols: Max symbols to use in backtest

    Returns:
        If enable_ai=false: Complete simulation results
        If enable_ai=true: Job ID to poll for results
    """
    from app.services.walk_forward_service import walk_forward_service
    from datetime import datetime
    import asyncio

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if end <= start:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # If AI is enabled, use async processing to avoid timeout
    if enable_ai:
        # Create a pending simulation record
        sim_record = WalkForwardSimulation(
            simulation_date=datetime.utcnow(),
            start_date=start,
            end_date=end,
            reoptimization_frequency=frequency,
            status="pending"
        )
        db.add(sim_record)
        await db.commit()
        await db.refresh(sim_record)
        job_id = sim_record.id

        # Start background task
        async def run_simulation_background():
            from app.core.database import async_session

            async with async_session() as bg_db:
                try:
                    # Update status to running
                    result = await bg_db.execute(
                        select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
                    )
                    job = result.scalar_one()
                    job.status = "running"
                    await bg_db.commit()

                    # Run the actual simulation
                    await walk_forward_service.run_walk_forward_simulation(
                        db=bg_db,
                        start_date=start,
                        end_date=end,
                        reoptimization_frequency=frequency,
                        min_score_diff=min_score_diff,
                        enable_ai_optimization=enable_ai,
                        max_symbols=max_symbols,
                        existing_job_id=job_id
                    )

                except Exception as e:
                    import traceback
                    try:
                        result = await bg_db.execute(
                            select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
                        )
                        job = result.scalar_one_or_none()
                        if job:
                            job.status = "failed"
                            job.switch_history_json = json.dumps({"error": str(e), "traceback": traceback.format_exc()})
                            await bg_db.commit()
                    except Exception:
                        pass

        asyncio.create_task(run_simulation_background())

        return {
            "async": True,
            "job_id": job_id,
            "status": "pending",
            "message": f"AI-enabled simulation runs async to avoid timeout. Poll /strategies/walk-forward/status/{job_id} for results.",
            "poll_url": f"/api/admin/strategies/walk-forward/status/{job_id}",
            "config": {
                "start_date": start_date,
                "end_date": end_date,
                "frequency": frequency,
                "max_symbols": max_symbols,
                "enable_ai": enable_ai
            }
        }

    # Non-AI simulation can run synchronously
    try:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db,
            start_date=start,
            end_date=end,
            reoptimization_frequency=frequency,
            min_score_diff=min_score_diff,
            enable_ai_optimization=enable_ai,
            max_symbols=max_symbols
        )

        # Count AI-driven switches
        ai_switches = sum(1 for s in result.switch_history if s.is_ai_generated)

        return {
            "success": True,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "reoptimization_frequency": result.reoptimization_frequency,
            "total_return_pct": result.total_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown_pct": result.max_drawdown_pct,
            "num_strategy_switches": result.num_strategy_switches,
            "num_ai_switches": ai_switches,
            "benchmark_return_pct": result.benchmark_return_pct,
            "switch_history": [
                {
                    "date": s.date,
                    "from_strategy": s.from_strategy_name,
                    "to_strategy": s.to_strategy_name,
                    "reason": s.reason,
                    "score_before": s.score_before,
                    "score_after": s.score_after,
                    "is_ai_generated": s.is_ai_generated,
                    "ai_params": s.ai_params
                }
                for s in result.switch_history
            ],
            "equity_curve": result.equity_curve,
            "ai_optimizations": [
                {
                    "date": ai.date,
                    "best_params": ai.best_params,
                    "expected_sharpe": ai.expected_sharpe,
                    "expected_return_pct": ai.expected_return_pct,
                    "strategy_type": ai.strategy_type,
                    "market_regime": ai.market_regime,
                    "was_adopted": ai.was_adopted,
                    "reason": ai.reason
                }
                for ai in result.ai_optimizations
            ],
            "parameter_evolution": [
                {
                    "date": p.date,
                    "strategy_name": p.strategy_name,
                    "strategy_type": p.strategy_type,
                    "params": p.params,
                    "source": p.source
                }
                for p in result.parameter_evolution
            ],
            "errors": result.errors if hasattr(result, 'errors') else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Simulation failed")


@router.get("/strategies/walk-forward/history")
async def get_walk_forward_history(
    limit: int = Query(10, ge=1, le=50),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of previous walk-forward simulations."""
    from app.services.walk_forward_service import walk_forward_service

    sims = await walk_forward_service.get_simulation_history(db, limit=limit)
    return {"simulations": sims, "total": len(sims)}


@router.get("/strategies/walk-forward/{simulation_id}")
async def get_walk_forward_details(
    simulation_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed results for a specific walk-forward simulation."""
    from app.services.walk_forward_service import walk_forward_service

    details = await walk_forward_service.get_simulation_details(db, simulation_id)
    if not details:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return details


@router.get("/strategies/walk-forward/{simulation_id}/trades")
async def get_walk_forward_trades(
    simulation_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get just the trades from a walk-forward simulation.

    Returns a detailed trade report with:
    - Symbol, entry/exit dates and prices
    - P&L (dollars and percentage)
    - Exit reason (trailing_stop, profit_target, etc.)
    - Period info (which optimization period the trade occurred in)

    Use this endpoint instead of the full details endpoint when you only need trades.
    """
    result = await db.execute(
        select(WalkForwardSimulation).where(WalkForwardSimulation.id == simulation_id)
    )
    sim = result.scalars().first()

    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

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


# ============================================================================
# Auto-Switch Configuration Endpoints
# ============================================================================

@router.get("/strategies/auto-switch/config")
async def get_auto_switch_config(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current auto-switch configuration."""
    from app.services.auto_switch_service import auto_switch_service

    config = await auto_switch_service.get_config(db)
    return {
        "is_enabled": config.is_enabled,
        "analysis_frequency": config.analysis_frequency,
        "min_score_diff_to_switch": config.min_score_diff_to_switch,
        "min_days_since_last_switch": config.min_days_since_last_switch,
        "notify_on_analysis": config.notify_on_analysis,
        "notify_on_switch": config.notify_on_switch,
        "admin_email": config.admin_email
    }


@router.patch("/strategies/auto-switch/config")
async def update_auto_switch_config(
    is_enabled: bool = None,
    analysis_frequency: str = None,
    min_score_diff: float = None,
    min_days_cooldown: int = None,
    notify_on_analysis: bool = None,
    notify_on_switch: bool = None,
    admin_email: str = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update auto-switch configuration."""
    from app.services.auto_switch_service import auto_switch_service

    config = await auto_switch_service.update_config(
        db=db,
        is_enabled=is_enabled,
        analysis_frequency=analysis_frequency,
        min_score_diff=min_score_diff,
        min_days_cooldown=min_days_cooldown,
        notify_on_analysis=notify_on_analysis,
        notify_on_switch=notify_on_switch,
        admin_email=admin_email
    )

    return {
        "success": True,
        "config": {
            "is_enabled": config.is_enabled,
            "analysis_frequency": config.analysis_frequency,
            "min_score_diff_to_switch": config.min_score_diff_to_switch,
            "min_days_since_last_switch": config.min_days_since_last_switch,
            "notify_on_analysis": config.notify_on_analysis,
            "notify_on_switch": config.notify_on_switch,
            "admin_email": config.admin_email
        }
    }


@router.get("/strategies/switch-history")
async def get_switch_history(
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get audit log of strategy switches."""
    from app.services.auto_switch_service import auto_switch_service

    history = await auto_switch_service.get_switch_history(db, limit=limit)
    return {"history": history, "total": len(history)}


@router.post("/strategies/auto-switch/trigger")
async def trigger_auto_analysis(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger auto-switch analysis.

    Returns recommendation without executing switch (for review).
    """
    from app.services.auto_switch_service import auto_switch_service

    result = await auto_switch_service.manual_trigger_analysis(db)
    return result


# ============================================================================
# Custom Strategy CRUD Endpoints
# ============================================================================

@router.post("/strategies")
async def create_strategy(
    name: str = Query(..., min_length=3, max_length=100),
    strategy_type: str = Query(...),
    parameters: str = Query(..., description="JSON string of parameters"),
    description: str = Query(None),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new custom strategy.

    Args:
        name: Strategy name (unique)
        strategy_type: "momentum" or "dwap"
        parameters: JSON string of strategy parameters
        description: Optional description
    """
    # Validate parameters JSON
    try:
        params_dict = json.loads(parameters)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON for parameters")

    # Check for existing strategy with same name
    result = await db.execute(
        select(StrategyDefinition).where(StrategyDefinition.name == name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Strategy with this name already exists")

    strategy = StrategyDefinition(
        name=name,
        description=description,
        strategy_type=strategy_type,
        parameters=parameters,
        is_active=False,
        source="manual",
        is_custom=True
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)

    return {
        "success": True,
        "strategy": {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "strategy_type": strategy.strategy_type,
            "parameters": params_dict,
            "is_active": strategy.is_active,
            "is_custom": strategy.is_custom
        }
    }


@router.put("/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: int,
    name: str = None,
    description: str = None,
    parameters: str = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a custom strategy's parameters."""
    result = await db.execute(
        select(StrategyDefinition).where(StrategyDefinition.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Only allow updating custom strategies or AI-generated ones
    if not strategy.is_custom and strategy.source != "ai_generated":
        raise HTTPException(status_code=400, detail="Cannot modify built-in strategies")

    if name:
        # Check for name collision
        name_check = await db.execute(
            select(StrategyDefinition).where(
                and_(StrategyDefinition.name == name, StrategyDefinition.id != strategy_id)
            )
        )
        if name_check.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Strategy with this name already exists")
        strategy.name = name

    if description is not None:
        strategy.description = description

    if parameters:
        try:
            json.loads(parameters)  # Validate JSON
            strategy.parameters = parameters
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON for parameters")

    await db.commit()
    await db.refresh(strategy)

    return {
        "success": True,
        "strategy": {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "strategy_type": strategy.strategy_type,
            "parameters": json.loads(strategy.parameters),
            "is_active": strategy.is_active
        }
    }


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a custom strategy (cannot delete built-in strategies)."""
    result = await db.execute(
        select(StrategyDefinition).where(StrategyDefinition.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if not strategy.is_custom and strategy.source != "ai_generated":
        raise HTTPException(status_code=400, detail="Cannot delete built-in strategies")

    if strategy.is_active:
        raise HTTPException(status_code=400, detail="Cannot delete active strategy")

    await db.delete(strategy)
    await db.commit()

    return {"success": True, "message": f"Strategy '{strategy.name}' deleted"}


# ============================================================================
# Market Regime Endpoints
# ============================================================================

@router.get("/market-regime/current")
async def get_current_regime(
    admin: User = Depends(get_admin_user)
):
    """
    Get the current market regime classification.

    Returns:
        Current regime with conditions, risk level, and recommendations.
    """
    from app.services.market_regime import market_regime_service
    from app.services.scanner import scanner_service

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    spy_df = scanner_service.data_cache.get('SPY')
    if spy_df is None or len(spy_df) < 200:
        raise HTTPException(status_code=503, detail="Insufficient SPY data")

    vix_df = scanner_service.data_cache.get('^VIX')

    try:
        regime = market_regime_service.detect_regime(
            spy_df=spy_df,
            universe_dfs=scanner_service.data_cache,
            vix_df=vix_df
        )
        return regime.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Regime detection failed")


@router.get("/market-regime/history")
async def get_regime_history(
    start_date: str = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str = Query(None, description="End date YYYY-MM-DD"),
    frequency: str = Query("weekly", description="Sample frequency: daily, weekly, monthly"),
    admin: User = Depends(get_admin_user)
):
    """
    Get market regime history over a date range.

    Returns:
        List of regime classifications with dates and conditions.
    """
    from app.services.market_regime import market_regime_service
    from app.services.scanner import scanner_service
    from datetime import datetime

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    spy_df = scanner_service.data_cache.get('SPY')
    if spy_df is None or len(spy_df) < 200:
        raise HTTPException(status_code=503, detail="Insufficient SPY data")

    vix_df = scanner_service.data_cache.get('^VIX')

    parsed_start = None
    parsed_end = None

    if start_date:
        try:
            parsed_start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")

    if end_date:
        try:
            parsed_end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    if frequency not in ["daily", "weekly", "monthly"]:
        raise HTTPException(status_code=400, detail="Invalid frequency. Use: daily, weekly, monthly")

    try:
        history = market_regime_service.get_regime_history(
            spy_df=spy_df,
            universe_dfs=scanner_service.data_cache,
            vix_df=vix_df,
            start_date=parsed_start,
            end_date=parsed_end,
            sample_frequency=frequency
        )

        return {
            "start_date": start_date or spy_df.index[0].strftime("%Y-%m-%d"),
            "end_date": end_date or spy_df.index[-1].strftime("%Y-%m-%d"),
            "frequency": frequency,
            "total_samples": len(history),
            "regimes": [r.to_dict() for r in history]
        }
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail="Regime history failed")


@router.get("/market-regime/periods")
async def get_regime_periods(
    start_date: str = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str = Query(None, description="End date YYYY-MM-DD"),
    admin: User = Depends(get_admin_user)
):
    """
    Get regime periods for chart background visualization.

    Primary: queries regime_history DB table (persisted, no cache dependency).
    Fallback: on-the-fly computation from data_cache if DB has no data.
    """
    from app.services.regime_forecast_service import regime_forecast_service
    from app.core.database import async_session

    # Try DB first (fast, no cache dependency)
    try:
        async with async_session() as db:
            db_result = await regime_forecast_service.get_regime_periods_from_db(
                db, start_date=start_date, end_date=end_date
            )
            if db_result:
                return db_result
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"DB regime periods query failed, falling back: {e}")

    # Fallback: on-the-fly computation (requires data_cache)
    from app.services.market_regime import market_regime_service
    from app.services.scanner import scanner_service
    from datetime import datetime

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded and no regime history in DB")

    spy_df = scanner_service.data_cache.get('SPY')
    if spy_df is None or len(spy_df) < 200:
        raise HTTPException(status_code=503, detail="Insufficient SPY data")

    vix_df = scanner_service.data_cache.get('^VIX')

    parsed_start = None
    parsed_end = None

    if start_date:
        try:
            parsed_start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")

    if end_date:
        try:
            parsed_end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    try:
        history = market_regime_service.get_regime_history(
            spy_df=spy_df,
            universe_dfs=scanner_service.data_cache,
            vix_df=vix_df,
            start_date=parsed_start,
            end_date=parsed_end,
            sample_frequency='weekly'
        )

        periods = market_regime_service.get_regime_periods(history)
        changes = market_regime_service.get_regime_changes(history)

        return {
            "start_date": start_date or spy_df.index[0].strftime("%Y-%m-%d"),
            "end_date": end_date or spy_df.index[-1].strftime("%Y-%m-%d"),
            "periods": periods,
            "regime_changes": changes,
            "total_changes": len(changes)
        }
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail="Regime periods failed")


@router.get("/market-regime/conditions")
async def get_current_conditions(
    admin: User = Depends(get_admin_user)
):
    """
    Get detailed current market conditions without regime classification.

    Returns raw indicator values for debugging and display.
    """
    from app.services.market_regime import market_regime_service
    from app.services.scanner import scanner_service
    from dataclasses import asdict

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    spy_df = scanner_service.data_cache.get('SPY')
    if spy_df is None or len(spy_df) < 200:
        raise HTTPException(status_code=503, detail="Insufficient SPY data")

    vix_df = scanner_service.data_cache.get('^VIX')

    try:
        conditions = market_regime_service.calculate_conditions(
            spy_df=spy_df,
            universe_dfs=scanner_service.data_cache,
            vix_df=vix_df
        )
        return asdict(conditions)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Condition calculation failed")


# ============================================================================
# Double Signal Analysis
# ============================================================================

@router.get("/signals/double-signal-analysis")
async def analyze_double_signals(
    lookback_days: int = Query(252, ge=60, le=504, description="Days of history to analyze"),
    sample_every_n: int = Query(5, ge=1, le=50, description="Sample every N trading days"),
    admin: User = Depends(get_admin_user),
):
    """
    Analyze performance of Double Signals (DWAP + Momentum) vs single signals.

    Compares:
    - Double: Stocks with BOTH DWAP trigger AND top-20 momentum
    - DWAP-only: DWAP trigger but NOT in momentum top 20
    - Momentum-only: Top-20 momentum but NO DWAP trigger

    Returns average returns at 5/10/20 day horizons and win rates.
    """
    import numpy as np
    import pandas as pd
    from collections import defaultdict
    from app.services.scanner import scanner_service

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    spy_df = scanner_service.data_cache.get('SPY')
    if spy_df is None:
        raise HTTPException(status_code=503, detail="SPY data not available")

    # Helper: filter dataframe to dates <= given date, handling timezone mismatches
    def filter_to_date(df, date):
        """Filter dataframe to rows where index <= date, handling tz differences."""
        date_ts = pd.Timestamp(date)
        idx = df.index
        # If df index is tz-aware and date is naive, localize date to index's tz
        if hasattr(idx, 'tz') and idx.tz is not None:
            if date_ts.tz is None:
                date_ts = date_ts.tz_localize(idx.tz)
        # If df index is tz-naive and date is tz-aware, convert date to naive
        elif date_ts.tz is not None:
            date_ts = date_ts.tz_localize(None)
        return df[idx <= date_ts]

    # Helper: filter dataframe to dates > given date, handling timezone mismatches
    def filter_after_date(df, date):
        """Filter dataframe to rows where index > date, handling tz differences."""
        date_ts = pd.Timestamp(date)
        idx = df.index
        if hasattr(idx, 'tz') and idx.tz is not None:
            if date_ts.tz is None:
                date_ts = date_ts.tz_localize(idx.tz)
        elif date_ts.tz is not None:
            date_ts = date_ts.tz_localize(None)
        return df[idx > date_ts]

    # Helper: get momentum rankings for a date
    def get_momentum_rankings(date, top_n=20):
        candidates = []
        for symbol, df in scanner_service.data_cache.items():
            df_to_date = filter_to_date(df, date)
            if len(df_to_date) < 60:
                continue
            try:
                row = df_to_date.iloc[-1]
                price = row['close']
                ma_20 = df_to_date['close'].tail(20).mean()
                ma_50 = df_to_date['close'].tail(50).mean()
                high_50d = df_to_date['close'].tail(50).max()
                volume = row['volume']

                if price < 20 or volume < 500000:
                    continue
                if price < ma_20 or price < ma_50:
                    continue
                dist_from_high = (high_50d - price) / high_50d * 100
                if dist_from_high > 5:
                    continue

                price_10d_ago = df_to_date.iloc[-10]['close'] if len(df_to_date) >= 10 else price
                price_60d_ago = df_to_date.iloc[-60]['close'] if len(df_to_date) >= 60 else price
                short_mom = (price / price_10d_ago - 1) * 100
                long_mom = (price / price_60d_ago - 1) * 100
                returns = df_to_date['close'].pct_change().tail(20)
                volatility = returns.std() * np.sqrt(252) * 100
                score = short_mom * 0.5 + long_mom * 0.3 - volatility * 0.2

                candidates.append({'symbol': symbol, 'score': score})
            except Exception:
                continue

        candidates.sort(key=lambda x: x['score'], reverse=True)
        return {c['symbol']: {'rank': i + 1, 'score': c['score']} for i, c in enumerate(candidates[:top_n])}

    # Helper: get DWAP signals for a date
    def get_dwap_signals(date, threshold_pct=5.0):
        date_ts = pd.Timestamp(date)
        signals = {}
        for symbol, df in scanner_service.data_cache.items():
            df_to_date = filter_to_date(df, date)
            if len(df_to_date) < 200:
                continue
            try:
                row = df_to_date.iloc[-1]
                row_date = pd.Timestamp(row.name)
                if row_date.tz is not None:
                    row_date = row_date.tz_localize(None)
                date_check = pd.Timestamp(date)
                if date_check.tz is not None:
                    date_check = date_check.tz_localize(None)
                if row_date.date() != date_check.date():
                    continue
                price = row['close']
                volume = row['volume']
                dwap = row.get('dwap', np.nan)
                if pd.isna(dwap) or dwap <= 0 or price < 20 or volume < 500000:
                    continue
                pct_above = (price / dwap - 1) * 100
                if pct_above >= threshold_pct:
                    signals[symbol] = {'pct_above_dwap': pct_above, 'price': price}
            except Exception:
                continue
        return signals

    # Helper: calculate forward returns
    def calc_returns(symbol, entry_date, entry_price):
        df = scanner_service.data_cache.get(symbol)
        if df is None:
            return {}
        df_after = filter_after_date(df, entry_date)
        if len(df_after) < 20:
            return {}
        results = {}
        if len(df_after) >= 5:
            results['r5'] = (df_after.iloc[4]['close'] / entry_price - 1) * 100
        if len(df_after) >= 10:
            results['r10'] = (df_after.iloc[9]['close'] / entry_price - 1) * 100
        if len(df_after) >= 20:
            results['r20'] = (df_after.iloc[19]['close'] / entry_price - 1) * 100
        return results

    # Get trading days
    end_date = spy_df.index[-21]
    start_date = pd.Timestamp(end_date) - pd.Timedelta(days=int(lookback_days * 1.5))
    trading_days = [d for d in spy_df.index if start_date <= pd.Timestamp(d) <= end_date]
    trading_days = trading_days[::sample_every_n]

    # Collect signals
    results_by_type = defaultdict(list)

    for date in trading_days:
        momentum_top20 = get_momentum_rankings(date)
        dwap_signals = get_dwap_signals(date)

        momentum_symbols = set(momentum_top20.keys())
        dwap_symbols = set(dwap_signals.keys())

        double_symbols = momentum_symbols & dwap_symbols
        dwap_only_symbols = dwap_symbols - momentum_symbols
        momentum_only_symbols = momentum_symbols - dwap_symbols

        for symbol in double_symbols:
            entry_price = dwap_signals[symbol]['price']
            rets = calc_returns(symbol, date, entry_price)
            if rets:
                results_by_type['double'].append(rets)

        for symbol in dwap_only_symbols:
            entry_price = dwap_signals[symbol]['price']
            rets = calc_returns(symbol, date, entry_price)
            if rets:
                results_by_type['dwap_only'].append(rets)

        for symbol in momentum_only_symbols:
            df = scanner_service.data_cache.get(symbol)
            if df is None:
                continue
            df_to_date = filter_to_date(df, date)
            if len(df_to_date) == 0:
                continue
            entry_price = df_to_date.iloc[-1]['close']
            rets = calc_returns(symbol, date, entry_price)
            if rets:
                results_by_type['momentum_only'].append(rets)

    # Calculate stats
    def calc_stats(signals_list):
        if not signals_list:
            return None
        r5 = [s['r5'] for s in signals_list if 'r5' in s]
        r10 = [s['r10'] for s in signals_list if 'r10' in s]
        r20 = [s['r20'] for s in signals_list if 'r20' in s]
        return {
            'count': len(signals_list),
            'avg_5d': round(np.mean(r5), 2) if r5 else None,
            'avg_10d': round(np.mean(r10), 2) if r10 else None,
            'avg_20d': round(np.mean(r20), 2) if r20 else None,
            'win_rate_5d': round(len([x for x in r5 if x > 0]) / len(r5) * 100, 1) if r5 else None,
            'win_rate_10d': round(len([x for x in r10 if x > 0]) / len(r10) * 100, 1) if r10 else None,
            'win_rate_20d': round(len([x for x in r20 if x > 0]) / len(r20) * 100, 1) if r20 else None,
            'std_20d': round(np.std(r20), 2) if r20 else None,
        }

    analysis = {
        'double': calc_stats(results_by_type['double']),
        'dwap_only': calc_stats(results_by_type['dwap_only']),
        'momentum_only': calc_stats(results_by_type['momentum_only']),
    }

    # Conclusion
    double_avg = analysis['double']['avg_20d'] if analysis['double'] else 0
    dwap_avg = analysis['dwap_only']['avg_20d'] if analysis['dwap_only'] else 0
    mom_avg = analysis['momentum_only']['avg_20d'] if analysis['momentum_only'] else 0

    conclusion = "inconclusive"
    if double_avg and double_avg > dwap_avg and double_avg > mom_avg:
        conclusion = "double_outperforms"
    elif dwap_avg and dwap_avg > double_avg and dwap_avg > mom_avg:
        conclusion = "dwap_only_outperforms"
    elif mom_avg and mom_avg > double_avg and mom_avg > dwap_avg:
        conclusion = "momentum_only_outperforms"

    # Log result for CloudWatch (in case API Gateway times out)
    import json
    result = {
        'lookback_days': lookback_days,
        'trading_days_analyzed': len(trading_days),
        'analysis': analysis,
        'conclusion': conclusion,
        'recommendation': (
            "Consolidate to single Ensemble Signals view" if conclusion == "double_outperforms"
            else "Keep separate views or investigate further"
        )
    }
    print(f"[DOUBLE-SIGNAL-ANALYSIS] {json.dumps(result)}")
    return result


# ============================================================================
# Strategy Comparison Endpoint
# ============================================================================

@router.get("/strategies/compare")
async def compare_strategies(
    lookback_years: int = Query(5, ge=1, le=15, description="Years of history to compare"),
    strategies: str = Query("all", description="Comma-separated strategy IDs or 'all'"),
    include_spy: bool = Query(True, description="Include SPY benchmark"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Compare multiple strategies over a historical period.

    Returns performance metrics for each strategy and SPY benchmark.
    Useful for evaluating which strategy performs best over long periods.
    """
    from app.services.backtester import BacktesterService
    from app.services.strategy_analyzer import CustomBacktester, StrategyParams
    from app.services.scanner import scanner_service

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    lookback_days = lookback_years * 252

    results = {}

    # Get SPY benchmark
    if include_spy:
        spy_df = scanner_service.data_cache.get('SPY')
        if spy_df is not None and len(spy_df) >= lookback_days:
            spy_start_price = spy_df.iloc[-lookback_days]['close']
            spy_end_price = spy_df.iloc[-1]['close']
            spy_return = (spy_end_price / spy_start_price - 1) * 100

            # Calculate SPY max drawdown
            spy_equity = spy_df['close'].iloc[-lookback_days:]
            spy_peak = spy_equity.cummax()
            spy_drawdown = ((spy_peak - spy_equity) / spy_peak * 100)
            spy_max_dd = spy_drawdown.max()

            results['SPY'] = {
                'total_return_pct': round(spy_return, 2),
                'sharpe_ratio': None,
                'max_drawdown_pct': round(spy_max_dd, 2),
                'win_rate': None,
                'total_trades': None,
                'type': 'benchmark'
            }

    # Load strategies
    query = select(StrategyDefinition)
    if strategies != "all":
        try:
            ids = [int(x.strip()) for x in strategies.split(',')]
            query = query.where(StrategyDefinition.id.in_(ids))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid strategy IDs")
    result = await db.execute(query)
    strats = result.scalars().all()

    if not strats:
        raise HTTPException(status_code=404, detail="No strategies found")

    # Get top liquid symbols for consistent comparison
    from app.services.strategy_analyzer import get_top_liquid_symbols
    top_symbols = get_top_liquid_symbols(max_symbols=100)

    # Run backtest for each strategy
    for strat in strats:
        try:
            params = StrategyParams.from_json(strat.parameters)
            backtester = CustomBacktester()
            backtester.configure(params)

            bt_result = backtester.run_backtest(
                lookback_days=lookback_days,
                strategy_type=strat.strategy_type,
                ticker_list=top_symbols
            )

            results[strat.name] = {
                'strategy_id': strat.id,
                'strategy_type': strat.strategy_type,
                'total_return_pct': bt_result.total_return_pct,
                'sharpe_ratio': bt_result.sharpe_ratio,
                'max_drawdown_pct': bt_result.max_drawdown_pct,
                'win_rate': bt_result.win_rate,
                'total_trades': bt_result.total_trades,
                'calmar_ratio': bt_result.calmar_ratio,
                'sortino_ratio': bt_result.sortino_ratio,
                'type': 'strategy'
            }
        except Exception as e:
            results[strat.name] = {
                'strategy_id': strat.id,
                'strategy_type': strat.strategy_type,
                'error': str(e),
                'type': 'strategy'
            }

    return {
        'lookback_years': lookback_years,
        'lookback_days': lookback_days,
        'symbols_tested': len(top_symbols),
        'results': results
    }


# ============================================================================
# Flexible Backtesting Endpoint
# ============================================================================

class FlexibleBacktestRequest(BaseModel):
    strategy_id: Optional[int] = None
    strategy_type: str = "momentum"
    custom_params: Optional[Dict[str, Any]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    lookback_days: int = 60
    ticker_list: Optional[List[str]] = None
    ticker_universe: Optional[str] = None
    # Exit strategy parameters
    exit_strategy_type: Optional[str] = None  # trailing_stop, fixed_target, hybrid, time_based, stop_loss_target
    trailing_stop_pct: Optional[float] = None
    profit_target_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    hybrid_initial_target_pct: Optional[float] = None
    hybrid_trailing_pct: Optional[float] = None
    max_hold_days: Optional[int] = None


class ExitStrategyComparisonRequest(BaseModel):
    """Request model for exit strategy comparison"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    lookback_days: int = 252  # 1 year default
    ticker_list: Optional[List[str]] = None
    # List of exit strategies to compare
    strategies: Optional[List[Dict[str, Any]]] = None


@router.post("/strategies/backtest")
async def run_flexible_backtest(
    request: FlexibleBacktestRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Run backtest with custom date range and ticker list.

    Accepts JSON body with:
        strategy_id: Use existing strategy (optional)
        strategy_type: "momentum" or "dwap" (if no strategy_id)
        custom_params: Dict of custom parameters (if no strategy_id)
        start_date: Start date YYYY-MM-DD (optional)
        end_date: End date YYYY-MM-DD (default: today)
        lookback_days: Days to backtest (default: 60)
        ticker_list: List of tickers (optional)
        ticker_universe: "nasdaq100" or "sp500" (optional)

    Returns:
        Backtest results with positions, trades, and metrics
    """
    from app.services.backtester import BacktesterService
    from app.services.strategy_analyzer import CustomBacktester, StrategyParams
    from datetime import datetime

    # Parse dates
    parsed_start = None
    parsed_end = None

    if request.start_date:
        try:
            parsed_start = datetime.strptime(request.start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")

    if request.end_date:
        try:
            parsed_end = datetime.strptime(request.end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    # Parse ticker list or use top liquid symbols for speed
    from app.services.strategy_analyzer import get_top_liquid_symbols

    tickers = None
    if request.ticker_list:
        tickers = [t.strip().upper() for t in request.ticker_list if t.strip()]
    else:
        # Use top 100 liquid symbols for speed when no tickers specified
        tickers = get_top_liquid_symbols(max_symbols=100)

    # Get or build strategy parameters
    if request.strategy_id:
        result = await db.execute(
            select(StrategyDefinition).where(StrategyDefinition.id == request.strategy_id)
        )
        strategy = result.scalar_one_or_none()
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        params = StrategyParams.from_json(strategy.parameters)
        use_momentum = strategy.strategy_type == "momentum"
    elif request.custom_params:
        try:
            params = StrategyParams(**request.custom_params)
        except TypeError as e:
            raise HTTPException(status_code=400, detail="Invalid custom_params")
        use_momentum = request.strategy_type == "momentum"
    else:
        # Use defaults based on strategy_type
        params = StrategyParams()
        use_momentum = request.strategy_type == "momentum"

    # Build exit strategy config if parameters provided
    from app.services.backtester import ExitStrategyConfig, ExitStrategyType

    exit_strategy = None
    if request.exit_strategy_type:
        try:
            exit_type = ExitStrategyType(request.exit_strategy_type)
            exit_strategy = ExitStrategyConfig(
                strategy_type=exit_type,
                trailing_stop_pct=request.trailing_stop_pct or 12.0,
                profit_target_pct=request.profit_target_pct or 20.0,
                stop_loss_pct=request.stop_loss_pct or 0.0,
                hybrid_initial_target_pct=request.hybrid_initial_target_pct or 15.0,
                hybrid_trailing_pct=request.hybrid_trailing_pct or 8.0,
                max_hold_days=request.max_hold_days or 60
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid exit_strategy_type. Must be one of: trailing_stop, fixed_target, hybrid, time_based, stop_loss_target"
            )

    # Create and configure backtester
    backtester = CustomBacktester()
    backtester.configure(params)

    try:
        result = backtester.run_backtest(
            lookback_days=request.lookback_days,
            start_date=parsed_start,
            end_date=parsed_end,
            use_momentum_strategy=use_momentum,
            ticker_list=tickers,
            exit_strategy=exit_strategy
        )

        # Transform trades to match frontend field names
        # Backend has: symbol, pnl_pct | Frontend expects: ticker, return_pct
        trades_list = []
        for t in result.trades:
            trade_dict = t.to_dict()
            trade_dict['ticker'] = trade_dict.get('symbol')  # Add ticker alias
            trade_dict['return_pct'] = trade_dict.get('pnl_pct')  # Add return_pct alias
            trades_list.append(trade_dict)

        # Calculate additional metrics from trades
        closed_trades = [t for t in trades_list if t.get('return_pct') is not None]

        winning_trades = [t for t in closed_trades if t.get('return_pct', 0) > 0]
        losing_trades = [t for t in closed_trades if t.get('return_pct', 0) <= 0]

        avg_win_pct = sum(t.get('return_pct', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss_pct = sum(t.get('return_pct', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0

        total_wins = sum(t.get('return_pct', 0) for t in winning_trades) if winning_trades else 0
        total_losses = abs(sum(t.get('return_pct', 0) for t in losing_trades)) if losing_trades else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else total_wins

        # Return flat structure matching frontend expectations
        return {
            "success": True,
            "strategy_type": "momentum" if use_momentum else "dwap",
            "start_date": result.start_date,
            "end_date": result.end_date,
            "tickers_used": len(tickers) if tickers else "all",
            # Metrics at top level for frontend
            "total_return_pct": result.total_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown_pct": result.max_drawdown_pct,
            "win_rate_pct": result.win_rate * 100,  # Convert to percentage
            "total_trades": result.total_trades,
            "open_positions": result.open_positions,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "profit_factor": profit_factor,
            # Lists
            "positions": [p.to_dict() for p in result.positions],
            "trades": trades_list[:50]  # Limit to 50 trades
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Backtest failed")


@router.post("/strategies/backtest/compare-exits")
async def compare_exit_strategies(
    request: ExitStrategyComparisonRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Compare different exit strategies head-to-head.

    Runs the same backtest with different exit strategies to compare performance.
    This helps determine the optimal exit strategy for the momentum strategy.

    Default strategies compared:
    - Trailing Stop 15% (current default)
    - Trailing Stop 10%
    - Trailing Stop 20%
    - Fixed Target 20%
    - Fixed Target 30%
    - Hybrid 15%/8% (hit 15% target, then 8% trailing)
    - Stop Loss 8% + Target 20% (legacy DWAP)

    Returns:
        Comparison of all exit strategies with performance metrics
    """
    from app.services.backtester import backtester_service, ExitStrategyConfig, ExitStrategyType
    from app.services.strategy_analyzer import get_top_liquid_symbols
    from datetime import datetime

    # Parse dates
    parsed_start = None
    parsed_end = None

    if request.start_date:
        try:
            parsed_start = datetime.strptime(request.start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")

    if request.end_date:
        try:
            parsed_end = datetime.strptime(request.end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    # Get tickers
    tickers = None
    if request.ticker_list:
        tickers = [t.strip().upper() for t in request.ticker_list if t.strip()]
    else:
        tickers = get_top_liquid_symbols(max_symbols=100)

    # Define exit strategies to compare
    if request.strategies:
        # Use custom strategies from request
        exit_configs = []
        for s in request.strategies:
            try:
                config = ExitStrategyConfig.from_dict(s)
                exit_configs.append({
                    "name": s.get("name", s.get("strategy_type", "Custom")),
                    "config": config
                })
            except Exception as e:
                raise HTTPException(status_code=400, detail="Invalid strategy config")
    else:
        # Default comparison set
        exit_configs = [
            {
                "name": "Trailing 12% (Current)",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.TRAILING_STOP,
                    trailing_stop_pct=12.0
                )
            },
            {
                "name": "Trailing 10%",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.TRAILING_STOP,
                    trailing_stop_pct=10.0
                )
            },
            {
                "name": "Trailing 20%",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.TRAILING_STOP,
                    trailing_stop_pct=20.0
                )
            },
            {
                "name": "Fixed Target 20%",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.FIXED_TARGET,
                    profit_target_pct=20.0
                )
            },
            {
                "name": "Fixed Target 30%",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.FIXED_TARGET,
                    profit_target_pct=30.0
                )
            },
            {
                "name": "Hybrid 15%→8%",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.HYBRID,
                    hybrid_initial_target_pct=15.0,
                    hybrid_trailing_pct=8.0
                )
            },
            {
                "name": "Hybrid 20%→10%",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.HYBRID,
                    hybrid_initial_target_pct=20.0,
                    hybrid_trailing_pct=10.0
                )
            },
            {
                "name": "Stop 8% + Target 20% (Legacy)",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.STOP_LOSS_TARGET,
                    stop_loss_pct=8.0,
                    profit_target_pct=20.0
                )
            },
            {
                "name": "Time-Based 60 Days",
                "config": ExitStrategyConfig(
                    strategy_type=ExitStrategyType.TIME_BASED,
                    max_hold_days=60
                )
            },
        ]

    # Run backtest for each exit strategy
    results = []
    for exit_config in exit_configs:
        try:
            result = backtester_service.run_backtest(
                lookback_days=request.lookback_days,
                start_date=parsed_start,
                end_date=parsed_end,
                use_momentum_strategy=True,
                ticker_list=tickers,
                exit_strategy=exit_config["config"]
            )

            # Calculate additional metrics
            winning_trades = [t for t in result.trades if t.pnl > 0]
            losing_trades = [t for t in result.trades if t.pnl <= 0]

            avg_days_held = sum(t.days_held for t in result.trades) / len(result.trades) if result.trades else 0

            results.append({
                "name": exit_config["name"],
                "exit_type": exit_config["config"].strategy_type.value,
                "config": exit_config["config"].to_dict(),
                "metrics": {
                    "total_return_pct": result.total_return_pct,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown_pct": result.max_drawdown_pct,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                    "avg_win_pct": result.avg_win_pct,
                    "avg_loss_pct": result.avg_loss_pct,
                    "profit_factor": result.profit_factor,
                    "calmar_ratio": result.calmar_ratio,
                    "sortino_ratio": result.sortino_ratio,
                    "avg_days_held": round(avg_days_held, 1),
                    "winning_trades": len(winning_trades),
                    "losing_trades": len(losing_trades),
                }
            })
        except Exception as e:
            results.append({
                "name": exit_config["name"],
                "exit_type": exit_config["config"].strategy_type.value,
                "error": str(e)
            })

    # Sort by Sharpe ratio (best first)
    successful_results = [r for r in results if "metrics" in r]
    failed_results = [r for r in results if "error" in r]
    successful_results.sort(key=lambda x: x["metrics"]["sharpe_ratio"], reverse=True)

    # Determine best strategy
    best_strategy = successful_results[0] if successful_results else None

    return {
        "success": True,
        "start_date": request.start_date or (parsed_start.strftime("%Y-%m-%d") if parsed_start else None),
        "end_date": request.end_date or (parsed_end.strftime("%Y-%m-%d") if parsed_end else datetime.now().strftime("%Y-%m-%d")),
        "lookback_days": request.lookback_days,
        "tickers_used": len(tickers) if tickers else "all",
        "strategies_compared": len(exit_configs),
        "best_strategy": best_strategy["name"] if best_strategy else None,
        "results": successful_results + failed_results,
        "ranking": [
            {
                "rank": i + 1,
                "name": r["name"],
                "sharpe": r["metrics"]["sharpe_ratio"],
                "return": r["metrics"]["total_return_pct"],
                "drawdown": r["metrics"]["max_drawdown_pct"],
                "win_rate": r["metrics"]["win_rate"]
            }
            for i, r in enumerate(successful_results)
        ]
    }


# ============================================================================
# AWS Health Dashboard
# ============================================================================

_cloudwatch_client = None

def _get_cloudwatch_client():
    global _cloudwatch_client
    if _cloudwatch_client is None:
        import boto3
        _cloudwatch_client = boto3.client('cloudwatch', region_name='us-east-1')
    return _cloudwatch_client


@router.get("/aws-health")
async def get_aws_health(admin: User = Depends(get_admin_user)):
    """Get CloudWatch alarm states and key infrastructure metrics."""
    import os
    is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

    if not is_lambda:
        return {
            "alarms": [],
            "metrics": {},
            "local_dev": True,
        }

    try:
        cw = _get_cloudwatch_client()
        from datetime import datetime, timedelta, timezone

        # 1. Alarm states
        alarm_response = cw.describe_alarms(AlarmNamePrefix="rigacap-prod-")
        alarms = [
            {
                "name": a["AlarmName"],
                "state": a["StateValue"],
                "updated_at": a["StateUpdatedTimestamp"].isoformat(),
            }
            for a in alarm_response.get("MetricAlarms", [])
        ]

        # 2. Key metrics
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)
        five_min_ago = now - timedelta(minutes=5)

        def get_metric(namespace, metric_name, stat, dimensions, start, end, period):
            result = cw.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Statistics=[stat],
                Dimensions=dimensions,
                StartTime=start,
                EndTime=end,
                Period=period,
            )
            datapoints = result.get("Datapoints", [])
            if not datapoints:
                return None
            # For Sum, add all datapoints; for Average, take the latest
            if stat == "Sum":
                return sum(dp[stat] for dp in datapoints)
            # Average — return latest datapoint
            latest = max(datapoints, key=lambda dp: dp["Timestamp"])
            return latest[stat]

        lambda_dims = [{"Name": "FunctionName", "Value": "rigacap-prod-api"}]
        rds_dims = [{"Name": "DBInstanceIdentifier", "Value": "rigacap-prod-db-v2"}]

        # Lambda metrics (24h)
        invocations = get_metric("AWS/Lambda", "Invocations", "Sum", lambda_dims, day_ago, now, 86400)
        errors = get_metric("AWS/Lambda", "Errors", "Sum", lambda_dims, day_ago, now, 86400)
        duration = get_metric("AWS/Lambda", "Duration", "Average", lambda_dims, day_ago, now, 86400)

        # API Gateway metrics (24h) — use ApiId from env or try without dimensions
        api_id = os.environ.get("API_GATEWAY_ID", "")
        api_dims = [{"Name": "ApiId", "Value": api_id}] if api_id else []
        requests_24h = get_metric("AWS/ApiGateway", "Count", "Sum", api_dims, day_ago, now, 86400) if api_dims else None

        # RDS metrics (last 5 min)
        cpu = get_metric("AWS/RDS", "CPUUtilization", "Average", rds_dims, five_min_ago, now, 300)
        storage = get_metric("AWS/RDS", "FreeStorageSpace", "Average", rds_dims, five_min_ago, now, 300)
        connections = get_metric("AWS/RDS", "DatabaseConnections", "Average", rds_dims, five_min_ago, now, 300)

        metrics = {
            "lambda": {
                "invocations_24h": int(invocations) if invocations is not None else None,
                "errors_24h": int(errors) if errors is not None else None,
                "avg_duration_ms": round(duration, 1) if duration is not None else None,
            },
            "api_gateway": {
                "requests_24h": int(requests_24h) if requests_24h is not None else None,
            },
            "rds": {
                "cpu_percent": round(cpu, 1) if cpu is not None else None,
                "free_storage_gb": round(storage / (1024 ** 3), 1) if storage is not None else None,
                "connections": int(connections) if connections is not None else None,
            },
        }

        return {"alarms": alarms, "metrics": metrics}

    except Exception as e:
        print(f"[AWS-HEALTH] Error fetching CloudWatch data: {e}")
        return {"alarms": [], "metrics": {}, "error": str(e)}


@router.get("/model-portfolio")
async def get_model_portfolio(
    portfolio_type: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get model portfolio summary (live, walkforward, or both)."""
    from app.services.model_portfolio_service import model_portfolio_service
    return await model_portfolio_service.get_portfolio_summary(db, portfolio_type)


@router.post("/model-portfolio/action")
async def model_portfolio_action(
    body: dict,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Run a model portfolio action: process_entries, process_exits, reset."""
    from app.services.model_portfolio_service import model_portfolio_service

    action = body.get("action", "")
    portfolio_type = body.get("portfolio_type")

    if action == "process_entries":
        results = {}
        for ptype in ([portfolio_type] if portfolio_type else ["live", "walkforward"]):
            results[ptype] = await model_portfolio_service.process_entries(db, ptype)
        return {"action": action, "results": results}

    elif action == "process_exits":
        results = {}
        if not portfolio_type or portfolio_type == "walkforward":
            results["walkforward"] = await model_portfolio_service.process_wf_exits(db)
        return {"action": action, "results": results}

    elif action == "reset":
        result = await model_portfolio_service.reset_portfolio(db, portfolio_type)
        return {"action": action, **result}

    elif action == "backfill":
        as_of_date = body.get("as_of_date", "2026-02-01")
        force = body.get("force", False)
        result = await model_portfolio_service.backfill_from_date(db, as_of_date, force)
        return {"action": action, **result}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


@router.get("/model-portfolio/equity-curve")
async def get_equity_curve(
    portfolio_type: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get equity curve data for charting (live, walkforward, or both + SPY)."""
    from app.services.model_portfolio_service import model_portfolio_service
    return await model_portfolio_service.get_equity_curve(db, portfolio_type)


@router.get("/model-portfolio/trades")
async def get_model_trades(
    portfolio_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get trade journal for model portfolios."""
    from app.services.model_portfolio_service import model_portfolio_service
    return await model_portfolio_service.get_all_trades(db, portfolio_type, limit)


@router.get("/model-portfolio/trades/{trade_id}")
async def get_model_trade_detail(
    trade_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full signal replay detail for a single model portfolio trade."""
    from app.services.model_portfolio_service import model_portfolio_service
    detail = await model_portfolio_service.get_trade_detail(db, trade_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Trade not found")
    return detail


@router.get("/model-portfolio/subscriber-preview")
async def get_subscriber_preview(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview what subscribers would see from the model portfolio."""
    from app.services.model_portfolio_service import model_portfolio_service
    return await model_portfolio_service.get_subscriber_view(db)


# ============================================================================
# Trade Autopsies
# ============================================================================

@router.post("/model-portfolio/trades/{trade_id}/autopsy")
async def generate_trade_autopsy(
    trade_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate AI autopsy for a single closed trade."""
    from app.services.trade_autopsy_service import trade_autopsy_service
    return await trade_autopsy_service.generate_autopsy(db, trade_id)


@router.post("/model-portfolio/autopsies/bulk")
async def bulk_generate_autopsies(
    body: dict = {},
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate autopsies for all un-autopsied closed trades."""
    from app.services.trade_autopsy_service import trade_autopsy_service
    portfolio_type = body.get("portfolio_type") if body else None
    limit = body.get("limit", 20) if body else 20
    return await trade_autopsy_service.bulk_generate(db, portfolio_type, limit)


# ============================================================================
# Regime Forecast
# ============================================================================

@router.get("/regime-forecast/history")
async def get_regime_forecast_history(
    days: int = Query(default=90, le=365),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get regime forecast history."""
    from app.services.regime_forecast_service import regime_forecast_service
    return await regime_forecast_service.get_forecast_history(db, days)


@router.get("/regime-forecast/accuracy")
async def get_regime_forecast_accuracy(
    days: int = Query(default=90, le=365),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get regime forecast accuracy with confusion matrix."""
    from app.services.regime_forecast_service import regime_forecast_service
    return await regime_forecast_service.get_forecast_accuracy(db, days)


@router.get("/regime-forecast/heatmap")
async def get_regime_forecast_heatmap(
    days: int = Query(default=60, le=365),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get transition probability heatmap data."""
    from app.services.regime_forecast_service import regime_forecast_service
    return await regime_forecast_service.get_transition_heatmap(db, days)


# ============================================================================
# What-If Calculator
# ============================================================================

@router.get("/model-portfolio/what-if")
async def calculate_what_if(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    capital: float = Query(default=10000, ge=100, le=10000000),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Calculate hypothetical returns from a start date with given capital."""
    from app.services.model_portfolio_service import model_portfolio_service
    return await model_portfolio_service.calculate_what_if(db, start_date, capital)


# ============================================================================
# Newsletter Management
# ============================================================================

@router.post("/newsletter/generate")
async def generate_newsletter_draft(
    admin: User = Depends(get_admin_user),
):
    """Generate a new newsletter draft using Claude via worker Lambda."""
    import boto3, os
    worker_fn = os.environ.get("WORKER_FUNCTION_NAME", "rigacap-prod-worker")
    try:
        lam = boto3.client("lambda", region_name="us-east-1")
        lam.invoke(
            FunctionName=worker_fn,
            InvocationType="Event",
            Payload=json.dumps({"generate_newsletter": True}).encode(),
        )
        return {"status": "generating", "message": "Newsletter generation started. Refresh in ~30 seconds."}
    except Exception as e:
        logger.warning(f"Failed to invoke worker for newsletter: {e}")
        from app.services.newsletter_generator_service import newsletter_generator
        draft = newsletter_generator.generate_draft()
        return draft


@router.get("/newsletter/draft")
async def get_newsletter_draft(
    date: Optional[str] = None,
    admin: User = Depends(get_admin_user),
):
    """Get the latest or a specific newsletter draft."""
    from app.services.newsletter_generator_service import newsletter_generator
    if date:
        draft = newsletter_generator.get_draft(date)
    else:
        draft = newsletter_generator.get_latest_draft()
    if not draft:
        raise HTTPException(status_code=404, detail="No draft found")
    return draft


@router.put("/newsletter/draft/{date}")
async def update_newsletter_draft(
    date: str,
    body: dict,
    admin: User = Depends(get_admin_user),
):
    """Update newsletter draft sections (admin editing)."""
    from app.services.newsletter_generator_service import newsletter_generator
    sections = body.get("sections")
    if not sections:
        raise HTTPException(status_code=400, detail="sections required")
    try:
        draft = newsletter_generator.update_draft(date, sections)
        return draft
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/newsletter/unlock/{date}")
async def unlock_newsletter_draft(
    date: str,
    admin: User = Depends(get_admin_user),
):
    """Unlock a locked draft for further editing."""
    from app.services.newsletter_generator_service import newsletter_generator
    try:
        draft = newsletter_generator.unlock_draft(date)
        return draft
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/newsletter/lock/{date}")
async def lock_newsletter_draft(
    date: str,
    admin: User = Depends(get_admin_user),
):
    """Lock a newsletter draft — no more edits allowed."""
    from app.services.newsletter_generator_service import newsletter_generator
    try:
        draft = newsletter_generator.lock_draft(date)
        return draft
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/newsletter/test/{date}")
async def send_newsletter_test(
    date: str,
    admin: User = Depends(get_admin_user),
):
    """Send the newsletter draft to admin only for preview."""
    from app.services.newsletter_generator_service import newsletter_generator
    from app.services.email_service import email_service

    draft = newsletter_generator.get_draft(date)
    if not draft:
        raise HTTPException(status_code=404, detail="No draft found")

    ok = await email_service.send_newsletter_from_draft(
        to_email=admin.email,
        draft=draft,
    )
    return {"sent": 1 if ok else 0, "to": admin.email}


@router.post("/newsletter/send/{date}")
async def send_newsletter_now(
    date: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Send the locked newsletter to all subscribers."""
    from app.services.newsletter_generator_service import newsletter_generator
    from app.services.email_service import email_service

    draft = newsletter_generator.get_draft(date)
    if not draft:
        raise HTTPException(status_code=404, detail="No draft found")
    if draft.get("status") != "locked":
        raise HTTPException(status_code=400, detail="Draft must be locked before sending")

    # Collect all recipients: free list + paid subscribers who haven't opted out
    all_emails = set()

    # Free newsletter subscribers
    from app.core.database import NewsletterPreference, User as _User, Subscription
    result = await db.execute(
        select(NewsletterPreference).where(
            NewsletterPreference.report_type == "market_measured",
            NewsletterPreference.unsubscribed_at.is_(None),
        )
    )
    for sub in result.scalars().all():
        all_emails.add(sub.email.strip().lower())

    # Paid subscribers who haven't opted out of market_measured
    from sqlalchemy import and_
    result = await db.execute(
        select(_User).join(Subscription, _User.id == Subscription.user_id).where(
            and_(
                Subscription.status.in_(["active", "trialing"]),
                _User.is_active == True,
            )
        )
    )
    for user in result.scalars().all():
        prefs = user.email_preferences or {}
        if prefs.get("market_measured", True):
            all_emails.add(user.email.strip().lower())

    sent = 0
    failed = 0
    for email_addr in all_emails:
        try:
            ok = await email_service.send_newsletter_from_draft(
                to_email=email_addr,
                draft=draft,
            )
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f"Newsletter send failed for {email_addr}: {e}")
            failed += 1

    return {"sent": sent, "failed": failed, "total": len(all_emails)}
