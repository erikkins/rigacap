"""
Walk-Forward Simulation Service

Simulates the auto-switch logic over a historical period to evaluate
how automated strategy switching would have performed.

Enhanced with AI optimization at each reoptimization period to detect
emerging trends and adapt parameters dynamically.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
import pandas as pd
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import StrategyDefinition, WalkForwardSimulation, WalkForwardPeriodResult
from app.services.backtester import BacktesterService
from app.services.strategy_analyzer import StrategyAnalyzerService, CustomBacktester, StrategyParams, get_top_liquid_symbols
from app.services.scanner import scanner_service
from app.services.market_regime import market_regime_service, MarketRegime, REGIME_DEFINITIONS
from app.services.optuna_optimizer import StrategyOptimizer


@dataclass
class AIOptimizationResult:
    """Result from AI optimization at a reoptimization point"""
    date: str
    best_params: Dict[str, Any]
    expected_sharpe: float
    expected_return_pct: float
    strategy_type: str
    market_regime: str
    was_adopted: bool
    reason: str
    # Enhanced metrics
    expected_sortino: float = 0.0
    expected_calmar: float = 0.0
    expected_profit_factor: float = 0.0
    expected_max_dd: float = 0.0
    combinations_tested: int = 0
    regime_confidence: float = 0.0
    regime_risk_level: str = "medium"
    adaptive_score: float = 0.0


@dataclass
class ParameterSnapshot:
    """Snapshot of active parameters at a point in time"""
    date: str
    strategy_name: str
    strategy_type: str
    params: Dict[str, Any]
    source: str  # "existing" or "ai_generated"


@dataclass
class SimulationPeriod:
    """A single period in the walk-forward simulation"""
    start_date: datetime
    end_date: datetime
    active_strategy_id: Optional[int]
    active_strategy_name: str
    period_return_pct: float
    cumulative_equity: float
    ai_optimization: Optional[AIOptimizationResult] = None


@dataclass
class SwitchEvent:
    """Record of a strategy switch during simulation"""
    date: str
    from_strategy_id: Optional[int]
    from_strategy_name: Optional[str]
    to_strategy_id: Optional[int]  # None if AI-generated
    to_strategy_name: str
    reason: str
    score_before: Optional[float]
    score_after: float
    is_ai_generated: bool = False
    ai_params: Optional[Dict[str, Any]] = None


@dataclass
class PeriodTrade:
    """A trade executed during walk-forward simulation"""
    period_start: str
    period_end: str
    strategy_name: str
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    pnl_pct: float
    pnl_dollars: float
    exit_reason: str
    momentum_score: float = 0
    momentum_rank: int = 0
    pct_above_dwap_at_entry: float = 0
    num_candidates: int = 0
    dwap_at_entry: float = 0
    # Signal strength metadata fields
    dwap_age: int = 0
    short_mom: float = 0
    long_mom: float = 0
    volatility: float = 0
    dist_from_high: float = 0
    vol_ratio: float = 0
    spy_trend: float = 0


@dataclass
class WalkForwardResult:
    """Complete walk-forward simulation result"""
    start_date: str
    end_date: str
    reoptimization_frequency: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    num_strategy_switches: int
    benchmark_return_pct: float
    switch_history: List[SwitchEvent]
    equity_curve: List[Dict]
    period_details: List[SimulationPeriod]
    ai_optimizations: List[AIOptimizationResult] = field(default_factory=list)
    parameter_evolution: List[ParameterSnapshot] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)  # Simulation errors for debugging
    trades: List[PeriodTrade] = field(default_factory=list)  # All trades across all periods
    continuation_state: Optional[Dict] = None  # Non-None if more chunks remain (self-chaining)


class WalkForwardService:
    """
    Walk-forward analysis service with AI optimization.

    Simulates what would have happened if we ran the auto-switch logic
    throughout a historical period, making decisions only with data
    available at each point in time.

    Enhanced features:
    - AI parameter optimization at each reoptimization period
    - Multi-factor market regime detection (6 regimes)
    - Expanded parameter grid with smart reduction
    - Adaptive scoring based on market regime
    - Enhanced metrics (Sortino, Calmar, Profit Factor, etc.)
    """

    def __init__(self):
        self.analyzer = StrategyAnalyzerService()
        self.initial_capital = 100000

    def _get_period_dates(
        self,
        start_date: datetime,
        end_date: datetime,
        frequency: str
    ) -> List[Tuple[datetime, datetime]]:
        """
        Generate list of (period_start, period_end) tuples.

        Args:
            start_date: Simulation start
            end_date: Simulation end
            frequency: "weekly", "biweekly", or "monthly"

        Returns:
            List of (start, end) tuples for each reoptimization period
        """
        periods = []
        current_start = start_date

        if frequency in ("weekly", "fast"):
            delta = timedelta(days=7)
        elif frequency == "biweekly":
            delta = timedelta(days=14)
        else:  # monthly
            delta = timedelta(days=30)

        while current_start < end_date:
            period_end = min(current_start + delta, end_date)
            periods.append((current_start, period_end))
            current_start = period_end

        return periods

    def _evaluate_strategy_at_date(
        self,
        strategy: StrategyDefinition,
        as_of_date: datetime,
        lookback_days: int = 90,
        ticker_list: List[str] = None
    ) -> Optional[Dict]:
        """
        Evaluate a strategy using only data available up to as_of_date.

        This is crucial for walk-forward validity - we can only use
        information that was available at the decision point.
        """
        params = StrategyParams.from_json(strategy.parameters)

        backtester = CustomBacktester()
        backtester.configure(params)

        try:
            result = backtester.run_backtest(
                lookback_days=lookback_days,
                end_date=as_of_date,
                strategy_type=strategy.strategy_type,
                ticker_list=ticker_list
            )

            return {
                "strategy_id": strategy.id,
                "name": strategy.name,
                "sharpe_ratio": result.sharpe_ratio,
                "total_return_pct": result.total_return_pct,
                "max_drawdown_pct": result.max_drawdown_pct,
                "win_rate": result.win_rate,
            }
        except Exception as e:
            return None

    def _calculate_recommendation_score(self, metrics: Dict) -> float:
        """Calculate composite score (same logic as strategy analyzer)"""
        sharpe = metrics.get('sharpe_ratio', 0)
        total_return = metrics.get('total_return_pct', 0)
        max_drawdown = metrics.get('max_drawdown_pct', 0)

        sharpe_score = min(max(sharpe / 2, 0), 1) * 40
        return_score = min(max(total_return / 50, 0), 1) * 30
        dd_score = max(1 - max_drawdown / 20, 0) * 30

        return sharpe_score + return_score + dd_score

    def _calculate_adaptive_score(
        self,
        metrics: Dict[str, float],
        regime: MarketRegime
    ) -> float:
        """
        Calculate score using regime-specific weights.

        All metrics normalized to 0-1 scale, then weighted based on
        current market regime priorities.
        """
        weights = regime.scoring_weights

        # Normalize each metric to 0-1 scale
        normalized = {
            "sharpe_ratio": min(max(metrics.get("sharpe_ratio", 0) / 2, 0), 1),
            "total_return": min(max(metrics.get("total_return_pct", 0) / 50, 0), 1),
            "max_drawdown": max(1 - metrics.get("max_drawdown_pct", 0) / 25, 0),
            "sortino_ratio": min(max(metrics.get("sortino_ratio", 0) / 2.5, 0), 1),
            "profit_factor": min(max((metrics.get("profit_factor", 1) - 1) / 2, 0), 1),
            "calmar_ratio": min(max(metrics.get("calmar_ratio", 0) / 3, 0), 1),
        }

        # Weighted sum
        score = sum(
            normalized.get(metric, 0) * weight
            for metric, weight in weights.items()
        ) * 100  # Scale to 0-100

        return round(score, 2)

    def _detect_market_regime_at_date(self, as_of_date: datetime) -> MarketRegime:
        """
        Detect market regime using multi-factor analysis.

        Uses SPY trend, VIX, trend strength, and breadth to classify
        into one of seven regimes: strong_bull, weak_bull, rotating_bull,
        range_bound, weak_bear, panic_crash, recovery.

        Returns: MarketRegime object with name, risk level, and recommendations
        """
        spy_df = scanner_service.data_cache.get('SPY')
        vix_df = scanner_service.data_cache.get('^VIX')

        if spy_df is None or len(spy_df) < 200:
            # Return a default regime if no data
            from app.services.market_regime import RegimeType, MarketConditions
            return MarketRegime(
                date=as_of_date.strftime('%Y-%m-%d'),
                regime_type=RegimeType.RANGE_BOUND,
                regime_name="Range-Bound",
                risk_level="medium",
                confidence=50.0,
                conditions=None,
                param_adjustments={},
                scoring_weights=REGIME_DEFINITIONS[RegimeType.RANGE_BOUND]["scoring_weights"],
                description="Insufficient data for regime detection"
            )

        return market_regime_service.detect_regime(
            spy_df=spy_df,
            universe_dfs=scanner_service.data_cache,
            vix_df=vix_df,
            as_of_date=as_of_date
        )

    def _run_ai_optimization_at_date(
        self,
        as_of_date: datetime,
        strategy_type: str,
        lookback_days: int,
        ticker_list: List[str],
        warm_start_params: Optional[Dict[str, Any]] = None,
        n_trials: int = 30
    ) -> Optional[AIOptimizationResult]:
        """
        Run AI parameter optimization using Optuna Bayesian search.

        Uses TPE (Tree-structured Parzen Estimator) over a continuous
        parameter space with regime-specific constraints and warm-starting
        from the previous period's best params.
        """
        regime = self._detect_market_regime_at_date(as_of_date)

        # Build base params (non-tuned parameters)
        if strategy_type in ("momentum", "ensemble"):
            base_params = {
                "long_momentum_days": 60,
                "min_volume": 500_000,
                "min_price": 20.0,
                "market_filter_enabled": True,
            }
        else:
            base_params = {
                "min_volume": 500_000,
                "min_price": 20.0,
            }

        # Objective: merge Optuna-suggested params with base, run backtest, return score
        combinations_tested = 0
        best_full_result = {"data": None}

        def objective(suggested_params: Dict[str, Any]) -> Optional[float]:
            nonlocal combinations_tested
            test_params = {**base_params, **suggested_params}
            result_data = self._test_param_combination(
                test_params, strategy_type, as_of_date, lookback_days, ticker_list, regime
            )
            combinations_tested += 1
            if result_data is None:
                return None
            # Track the full result for the best trial
            if best_full_result["data"] is None or result_data["adaptive_score"] > best_full_result["data"]["adaptive_score"]:
                best_full_result["data"] = result_data
            return result_data["adaptive_score"]

        optimizer = StrategyOptimizer()
        opt_result = optimizer.optimize(
            strategy_type=strategy_type,
            objective_fn=objective,
            regime_risk_level=regime.risk_level,
            warm_start_params=warm_start_params,
            n_trials=n_trials,
            seed_date=as_of_date,
        )

        if opt_result and best_full_result["data"]:
            best = best_full_result["data"]
            return AIOptimizationResult(
                date=as_of_date.strftime('%Y-%m-%d'),
                best_params=best["full_params"],
                expected_sharpe=best["sharpe_ratio"],
                expected_return_pct=best["total_return_pct"],
                strategy_type=strategy_type,
                market_regime=regime.regime_type.value,
                was_adopted=False,
                reason="",
                expected_sortino=best.get("sortino_ratio", 0),
                expected_calmar=best.get("calmar_ratio", 0),
                expected_profit_factor=best.get("profit_factor", 0),
                expected_max_dd=best.get("max_drawdown_pct", 0),
                combinations_tested=combinations_tested,
                regime_confidence=regime.confidence,
                regime_risk_level=regime.risk_level,
                adaptive_score=opt_result["best_score"]
            )

        return None

    def _test_param_combination(
        self,
        test_params: Dict[str, Any],
        strategy_type: str,
        as_of_date: datetime,
        lookback_days: int,
        ticker_list: List[str],
        regime: MarketRegime
    ) -> Optional[Dict]:
        """
        Test a single parameter combination and return metrics with adaptive score.
        """
        try:
            params = StrategyParams(**test_params)
            backtester = CustomBacktester()
            backtester.configure(params)

            result = backtester.run_backtest(
                lookback_days=lookback_days,
                end_date=as_of_date,
                strategy_type=strategy_type,
                ticker_list=ticker_list
            )

            metrics = {
                "sharpe_ratio": result.sharpe_ratio,
                "total_return_pct": result.total_return_pct,
                "max_drawdown_pct": result.max_drawdown_pct,
                "sortino_ratio": result.sortino_ratio,
                "calmar_ratio": result.calmar_ratio,
                "profit_factor": result.profit_factor,
                "win_rate": result.win_rate,
            }

            adaptive_score = self._calculate_adaptive_score(metrics, regime)

            return {
                "full_params": test_params,
                "sharpe_ratio": result.sharpe_ratio,
                "total_return_pct": result.total_return_pct,
                "max_drawdown_pct": result.max_drawdown_pct,
                "sortino_ratio": result.sortino_ratio,
                "calmar_ratio": result.calmar_ratio,
                "profit_factor": result.profit_factor,
                "adaptive_score": adaptive_score,
            }
        except Exception:
            return None

    def _simulate_period_with_params(
        self,
        params: Dict[str, Any],
        strategy_type: str,
        start_date: datetime,
        end_date: datetime,
        starting_capital: float,
        ticker_list: List[str] = None,
        strategy_name: str = "AI-Optimized",
        initial_positions: Optional[Dict[str, dict]] = None,
        force_close_at_end: bool = True,
        max_positions_override: Optional[int] = None,
        position_size_pct_override: Optional[float] = None
    ) -> Tuple[float, float, str, List[PeriodTrade], Dict[str, dict]]:
        """
        Simulate trading for a period using custom parameters (for AI-generated strategies).

        Returns:
            Tuple of (ending_capital, period_return_pct, info_string, trades, raw_positions)
        """
        try:
            strategy_params = StrategyParams(**params)
            backtester = CustomBacktester()
            backtester.configure(strategy_params)
            backtester.initial_capital = starting_capital
            if max_positions_override is not None:
                backtester.max_positions = max_positions_override
            if position_size_pct_override is not None:
                backtester.position_size_pct = position_size_pct_override / 100

            result = backtester.run_backtest(
                start_date=start_date,
                end_date=end_date,
                strategy_type=strategy_type,
                ticker_list=ticker_list,
                force_close_at_end=force_close_at_end,
                initial_positions=initial_positions
            )

            ending_capital = starting_capital * (1 + result.total_return_pct / 100)

            # Use debug_info from BacktestResult if available
            backtest_debug = getattr(result, 'debug_info', '') or ''

            print(f"[WF-SIM] Period {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}: "
                  f"{result.total_return_pct:.2f}% return, {result.total_trades} trades. {backtest_debug}")

            # Convert trades to PeriodTrade objects
            period_trades = [
                PeriodTrade(
                    period_start=start_date.strftime('%Y-%m-%d'),
                    period_end=end_date.strftime('%Y-%m-%d'),
                    strategy_name=strategy_name,
                    symbol=t.symbol,
                    entry_date=t.entry_date,
                    exit_date=t.exit_date,
                    entry_price=round(t.entry_price, 2),
                    exit_price=round(t.exit_price, 2),
                    shares=round(t.shares, 2),
                    pnl_pct=round(t.pnl_pct, 2),
                    pnl_dollars=round(t.pnl, 2),
                    exit_reason=t.exit_reason,
                    momentum_score=getattr(t, 'momentum_score', 0),
                    momentum_rank=getattr(t, 'momentum_rank', 0),
                    pct_above_dwap_at_entry=getattr(t, 'pct_above_dwap_at_entry', 0),
                    num_candidates=getattr(t, 'num_candidates', 0),
                    dwap_at_entry=getattr(t, 'dwap_at_entry', 0),
                    dwap_age=getattr(t, 'dwap_age', 0),
                    short_mom=getattr(t, 'short_mom', 0),
                    long_mom=getattr(t, 'long_mom', 0),
                    volatility=getattr(t, 'volatility', 0),
                    dist_from_high=getattr(t, 'dist_from_high', 0),
                    vol_ratio=getattr(t, 'vol_ratio', 0),
                    spy_trend=getattr(t, 'spy_trend', 0),
                )
                for t in result.trades
            ]

            # Always return info about the period for debugging
            info = (f"Period {start_date.strftime('%Y-%m-%d')}: {backtest_debug}")
            return ending_capital, result.total_return_pct, info, period_trades, result.raw_positions
        except Exception as e:
            error_msg = f"Period {start_date.strftime('%Y-%m-%d')}: ERROR {str(e)}"
            print(f"[WF-SIM] ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return starting_capital, 0.0, error_msg, [], {}

    def _simulate_period_trading(
        self,
        strategy: StrategyDefinition,
        start_date: datetime,
        end_date: datetime,
        starting_capital: float,
        ticker_list: List[str] = None,
        initial_positions: Optional[Dict[str, dict]] = None,
        force_close_at_end: bool = True,
        max_positions_override: Optional[int] = None,
        position_size_pct_override: Optional[float] = None
    ) -> Tuple[float, List[Dict], float, str, List[PeriodTrade], Dict[str, dict]]:
        """
        Simulate trading for a single period using a specific strategy.

        Returns:
            Tuple of (ending_capital, equity_points, period_return_pct, info, trades, raw_positions)
        """
        params = StrategyParams.from_json(strategy.parameters)

        backtester = CustomBacktester()
        backtester.configure(params)
        backtester.initial_capital = starting_capital
        if max_positions_override is not None:
            backtester.max_positions = max_positions_override
        if position_size_pct_override is not None:
            backtester.position_size_pct = position_size_pct_override / 100

        try:
            result = backtester.run_backtest(
                start_date=start_date,
                end_date=end_date,
                strategy_type=strategy.strategy_type,
                ticker_list=ticker_list,
                force_close_at_end=force_close_at_end,
                initial_positions=initial_positions
            )

            ending_capital = starting_capital * (1 + result.total_return_pct / 100)
            print(f"[WF-SIM] Period {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}: {result.total_return_pct:.2f}% return, {result.total_trades} trades (strategy: {strategy.name})")
            # Always return info about the period for debugging
            info = f"Period {start_date.strftime('%Y-%m-%d')}: {result.total_trades} trades, {result.total_return_pct:.1f}% ({strategy.name})"

            # Build equity curve points for this period
            # We don't have detailed daily data, so approximate
            equity_points = [
                {
                    "date": result.start_date,
                    "equity": starting_capital,
                    "strategy": strategy.name
                },
                {
                    "date": result.end_date,
                    "equity": ending_capital,
                    "strategy": strategy.name
                }
            ]

            # Convert trades to PeriodTrade objects
            period_trades = [
                PeriodTrade(
                    period_start=start_date.strftime('%Y-%m-%d'),
                    period_end=end_date.strftime('%Y-%m-%d'),
                    strategy_name=strategy.name,
                    symbol=t.symbol,
                    entry_date=t.entry_date,
                    exit_date=t.exit_date,
                    entry_price=round(t.entry_price, 2),
                    exit_price=round(t.exit_price, 2),
                    shares=round(t.shares, 2),
                    pnl_pct=round(t.pnl_pct, 2),
                    pnl_dollars=round(t.pnl, 2),
                    exit_reason=t.exit_reason,
                    momentum_score=getattr(t, 'momentum_score', 0),
                    momentum_rank=getattr(t, 'momentum_rank', 0),
                    pct_above_dwap_at_entry=getattr(t, 'pct_above_dwap_at_entry', 0),
                    num_candidates=getattr(t, 'num_candidates', 0),
                    dwap_at_entry=getattr(t, 'dwap_at_entry', 0),
                    dwap_age=getattr(t, 'dwap_age', 0),
                    short_mom=getattr(t, 'short_mom', 0),
                    long_mom=getattr(t, 'long_mom', 0),
                    volatility=getattr(t, 'volatility', 0),
                    dist_from_high=getattr(t, 'dist_from_high', 0),
                    vol_ratio=getattr(t, 'vol_ratio', 0),
                    spy_trend=getattr(t, 'spy_trend', 0),
                )
                for t in result.trades
            ]

            return ending_capital, equity_points, result.total_return_pct, info, period_trades, result.raw_positions

        except Exception as e:
            # If backtest fails, assume flat return
            error_msg = f"Period {start_date.strftime('%Y-%m-%d')}: {str(e)}"
            print(f"[WF-SIM] ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return starting_capital, [], 0.0, error_msg, [], {}

    async def run_walk_forward_simulation(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        reoptimization_frequency: str = "biweekly",
        min_score_diff: float = 10.0,
        lookback_days: int = 60,
        enable_ai_optimization: bool = True,
        max_symbols: int = 50,
        existing_job_id: int = None,
        fixed_strategy_id: int = None,  # If set, use only this strategy (no switching)
        n_trials: int = 30,  # Number of Optuna optimization trials per period
        carry_positions: bool = False,  # Carry positions across periods (default: force-close each period)
        max_positions: Optional[int] = None,  # Override strategy's max_positions for A/B testing
        position_size_pct: Optional[float] = None,  # Override strategy's position_size_pct for A/B testing
        periods_limit: int = 0,  # Max periods per chunk (0 = unlimited, for self-chaining)
        continuation_state: Optional[Dict] = None  # Restored state from previous chunk
    ) -> WalkForwardResult:
        """
        Run walk-forward simulation with AI optimization over a historical period.

        Enhanced Algorithm:
        1. Start at start_date with the best strategy/params at that point
        2. Every reoptimization period:
           a. Evaluate existing strategies using ONLY data available at that point
           b. Run AI optimization to find optimal params for current conditions
           c. Compare AI-optimized params against existing strategies
           d. Switch to best option if it beats current by min_score_diff
           e. Track parameter evolution and AI recommendations
           f. Simulate trading until next period
        3. Return full equity curve, switch timeline, AI recommendations, and param evolution

        Args:
            db: Database session
            start_date: Simulation start date
            end_date: Simulation end date
            reoptimization_frequency: "weekly", "biweekly", or "monthly"
            min_score_diff: Minimum score difference to trigger switch
            lookback_days: Days of data for strategy evaluation
            enable_ai_optimization: Whether to run AI param optimization each period
            fixed_strategy_id: If provided, use only this strategy (disables switching and AI)

        Returns:
            WalkForwardResult with complete simulation data including AI insights
        """
        import logging
        logger = logging.getLogger()
        is_continuation = continuation_state is not None
        start_period = continuation_state.get("period_index", 0) if is_continuation else 0
        print(f"[WF-SERVICE] {'Resuming' if is_continuation else 'Starting'} simulation: {start_date} to {end_date}, "
              f"ai={enable_ai_optimization}, fixed_strategy={fixed_strategy_id}, "
              f"max_positions={max_positions}, position_size_pct={position_size_pct}"
              + (f", resuming from period {start_period}" if is_continuation else "")
              + (f", periods_limit={periods_limit}" if periods_limit else ""))

        # Load all strategies
        result = await db.execute(
            select(StrategyDefinition).order_by(StrategyDefinition.id)
        )
        strategies = result.scalars().all()
        print(f"[WF-SERVICE] Loaded {len(strategies)} strategies")

        if not strategies:
            raise RuntimeError("No strategies found in database")

        # If fixed_strategy_id is set, find that strategy and disable switching
        # AI optimization still runs if enabled (optimizes the fixed strategy's type)
        fixed_strategy = None
        if fixed_strategy_id:
            fixed_strategy = next((s for s in strategies if s.id == fixed_strategy_id), None)
            if not fixed_strategy:
                raise RuntimeError(f"Strategy with id {fixed_strategy_id} not found")
            print(f"[WF-SERVICE] Using FIXED strategy: {fixed_strategy.name} (id={fixed_strategy_id}), ai={enable_ai_optimization}")

        # Get symbol universe for simulation
        # max_symbols=0 means use full production universe: all symbols that could plausibly
        # pass the ensemble entry criteria (volume >= 500K, price >= $15 on any recent day).
        # This is NOT a signal filter — the backtester still applies the full entry criteria
        # on every date. This just avoids iterating ~5000 symbols that always fail immediately.
        if max_symbols == 0:
            from app.services.scanner import _EXCLUDED_SET
            top_symbols = [s for s, df in scanner_service.data_cache.items()
                           if s not in _EXCLUDED_SET and len(df) >= 200
                           and 'volume' in df.columns and 'close' in df.columns
                           and df['volume'].max() >= 500_000 and df['close'].max() >= 15.0]
            print(f"[WF-SERVICE] Using PRODUCTION universe: {len(top_symbols)} symbols "
                  f"(from {len(scanner_service.data_cache)} total, filtered by entry criteria eligibility)")
        else:
            top_symbols = get_top_liquid_symbols(max_symbols=max_symbols)
            print(f"[WF-SERVICE] Got {len(top_symbols) if top_symbols else 0} top symbols (by volume)")
        if not top_symbols:
            raise RuntimeError("No liquid symbols found. Ensure data is loaded.")

        # Get period boundaries
        periods = self._get_period_dates(start_date, end_date, reoptimization_frequency)
        print(f"[WF-SERVICE] Processing {len(periods)} periods (starting at {start_period})")

        # Initialize or restore simulation state
        if is_continuation:
            # Restore accumulated state from previous chunk
            capital = continuation_state["capital"]
            carried_positions = continuation_state.get("carried_positions", {})
            equity_curve = continuation_state.get("equity_curve", [])
            all_trades_raw = continuation_state.get("all_trades", [])
            # Reconstruct PeriodTrade objects from dicts
            all_trades: List[PeriodTrade] = [PeriodTrade(**t) for t in all_trades_raw]
            switch_history_raw = continuation_state.get("switch_history", [])
            switch_history: List[SwitchEvent] = [SwitchEvent(**s) for s in switch_history_raw]
            simulation_errors = continuation_state.get("simulation_errors", [])
            spy_start_price = continuation_state.get("spy_start_price")
            previous_best_params = continuation_state.get("warm_start_params")

            # Restore active strategy state
            _active_id = continuation_state.get("active_strategy_id")
            active_strategy_score = continuation_state.get("active_strategy_score", 0.0)
            active_strategy_type = continuation_state.get("active_strategy_type", "ensemble")
            active_params = continuation_state.get("active_params")
            using_ai_params = continuation_state.get("using_ai_params", False)

            if _active_id and not using_ai_params:
                active_strategy = next((s for s in strategies if s.id == _active_id), strategies[0])
            else:
                active_strategy = None if using_ai_params else strategies[0]

            prev_active_strategy_id = continuation_state.get("prev_active_strategy_id")
            prev_using_ai_params = continuation_state.get("prev_using_ai_params", False)

            print(f"[WF-SERVICE] Restored state: capital=${capital:,.2f}, {len(equity_curve)} equity points, "
                  f"{len(all_trades)} trades, {len(carried_positions)} carried positions")
        else:
            # Fresh start
            capital = self.initial_capital
            active_strategy = strategies[0]  # Will be replaced by first analysis
            active_strategy_score = 0.0
            active_strategy_type = strategies[0].strategy_type
            active_params: Optional[Dict] = None  # None means using existing strategy
            using_ai_params = False

            switch_history: List[SwitchEvent] = []
            equity_curve: List[Dict] = []
            all_trades: List[PeriodTrade] = []  # All trades across all periods
            simulation_errors: List[str] = []  # Track errors for debugging
            previous_best_params: Optional[Dict[str, Any]] = None
            carried_positions: Dict[str, dict] = {}
            prev_active_strategy_id = None
            prev_using_ai_params = False

            # Get SPY starting price for benchmark line
            spy_start_price = None

        # These are per-chunk only (not persisted across chunks)
        period_details: List[SimulationPeriod] = []
        ai_optimizations: List[AIOptimizationResult] = []
        parameter_evolution: List[ParameterSnapshot] = []

        # SPY benchmark setup
        spy_df = None
        if 'SPY' in scanner_service.data_cache:
            spy_df = scanner_service.data_cache['SPY']
            if spy_start_price is None:
                start_ts = pd.Timestamp(start_date)
                if spy_df.index.tz is not None:
                    start_ts = start_ts.tz_localize(spy_df.index.tz) if start_ts.tz is None else start_ts.tz_convert(spy_df.index.tz)
                spy_at_start = spy_df[spy_df.index >= start_ts]
                if len(spy_at_start) > 0:
                    spy_start_price = spy_at_start.iloc[0]['close']
                    print(f"[WF-SERVICE] SPY start price: ${spy_start_price:.2f}")

        def get_spy_equity(date_str: str) -> float:
            """Get SPY equity normalized to initial capital"""
            if spy_start_price is None or spy_df is None:
                return None
            try:
                date_ts = pd.Timestamp(date_str)
                # Handle timezone-aware index
                if spy_df.index.tz is not None:
                    date_ts = date_ts.tz_localize(spy_df.index.tz) if date_ts.tz is None else date_ts.tz_convert(spy_df.index.tz)
                spy_at_date = spy_df[spy_df.index <= date_ts]
                if len(spy_at_date) > 0:
                    spy_price = spy_at_date.iloc[-1]['close']
                    return self.initial_capital * (spy_price / spy_start_price)
            except:
                pass
            return None

        # Add initial equity point (only on fresh start)
        if not is_continuation:
            equity_curve.append({
                "date": start_date.strftime('%Y-%m-%d'),
                "equity": capital,
                "spy_equity": self.initial_capital,
                "strategy": "Initial",
                "is_switch": False
            })

        # Process each period (skip already-completed periods on continuation)
        periods_processed_this_chunk = 0
        print(f"[WF-SERVICE] Starting simulation loop: {len(periods)} total periods, "
              f"starting at {start_period}, initial capital=${capital:,.2f}")
        for i, (period_start, period_end) in enumerate(periods):
            # Skip already-completed periods
            if i < start_period:
                continue

            # Check chunk limit
            if periods_limit > 0 and periods_processed_this_chunk >= periods_limit:
                print(f"[WF-SERVICE] Chunk limit reached ({periods_limit} periods). "
                      f"Saving state for continuation at period {i}/{len(periods)}.")
                # Build continuation state
                cont_state = {
                    "period_index": i,
                    "capital": capital,
                    "carried_positions": carried_positions,
                    "equity_curve": equity_curve,
                    "all_trades": [
                        {
                            "period_start": t.period_start, "period_end": t.period_end,
                            "strategy_name": t.strategy_name, "symbol": t.symbol,
                            "entry_date": t.entry_date, "exit_date": t.exit_date,
                            "entry_price": t.entry_price, "exit_price": t.exit_price,
                            "shares": t.shares, "pnl_pct": t.pnl_pct,
                            "pnl_dollars": t.pnl_dollars, "exit_reason": t.exit_reason,
                            "momentum_score": t.momentum_score, "momentum_rank": t.momentum_rank,
                            "pct_above_dwap_at_entry": t.pct_above_dwap_at_entry,
                            "num_candidates": t.num_candidates,
                            "dwap_at_entry": t.dwap_at_entry, "dwap_age": t.dwap_age,
                            "short_mom": t.short_mom, "long_mom": t.long_mom,
                            "volatility": t.volatility, "dist_from_high": t.dist_from_high,
                            "vol_ratio": t.vol_ratio, "spy_trend": t.spy_trend,
                        }
                        for t in all_trades
                    ],
                    "switch_history": [
                        {
                            "date": s.date, "from_strategy_id": s.from_strategy_id,
                            "from_strategy_name": s.from_strategy_name,
                            "to_strategy_id": s.to_strategy_id,
                            "to_strategy_name": s.to_strategy_name,
                            "reason": s.reason, "score_before": s.score_before,
                            "score_after": s.score_after,
                            "is_ai_generated": s.is_ai_generated,
                            "ai_params": s.ai_params,
                        }
                        for s in switch_history
                    ],
                    "simulation_errors": simulation_errors,
                    "spy_start_price": spy_start_price,
                    "active_strategy_id": active_strategy.id if active_strategy else None,
                    "active_strategy_name": active_strategy.name if active_strategy else "AI-Optimized",
                    "active_strategy_type": active_strategy_type,
                    "active_strategy_score": active_strategy_score,
                    "active_params": active_params,
                    "using_ai_params": using_ai_params,
                    "warm_start_params": previous_best_params,
                    "prev_active_strategy_id": prev_active_strategy_id,
                    "prev_using_ai_params": prev_using_ai_params,
                }
                return WalkForwardResult(
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d'),
                    reoptimization_frequency=reoptimization_frequency,
                    total_return_pct=0, sharpe_ratio=0, max_drawdown_pct=0,
                    num_strategy_switches=0, benchmark_return_pct=0,
                    switch_history=switch_history, equity_curve=equity_curve,
                    period_details=period_details,
                    errors=simulation_errors[:10],
                    trades=all_trades,
                    continuation_state=cont_state,
                )

            periods_processed_this_chunk += 1
            print(f"[WF-SERVICE] Period {i+1}/{len(periods)}: {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}")
            period_ai_opt = None

            # If using fixed strategy, skip strategy evaluation (but AI optimization still runs)
            if fixed_strategy:
                if i == 0:
                    # First period - set the fixed strategy as active
                    active_strategy = fixed_strategy
                    active_strategy_type = fixed_strategy.strategy_type
                    active_strategy_score = 0.0  # Let AI params beat this easily
                    switch_history.append(SwitchEvent(
                        date=period_start.strftime('%Y-%m-%d'),
                        from_strategy_id=None,
                        from_strategy_name="Initial",
                        to_strategy_id=fixed_strategy.id,
                        to_strategy_name=fixed_strategy.name,
                        reason="fixed_strategy_selected",
                        score_before=0,
                        score_after=0.0,
                        is_ai_generated=False
                    ))
                    print(f"[WF-SERVICE] Using fixed strategy: {fixed_strategy.name}")
                # Skip strategy evaluation but allow AI optimization below
                evaluations = []
            else:
                # Step 1: Evaluate all existing strategies
                evaluations = []
                for strategy in strategies:
                    metrics = self._evaluate_strategy_at_date(
                        strategy, period_start, lookback_days, ticker_list=top_symbols
                    )
                    if metrics:
                        metrics["score"] = self._calculate_recommendation_score(metrics)
                        metrics["is_ai"] = False
                        evaluations.append(metrics)

            # Step 2: Run AI optimization if enabled
            if enable_ai_optimization:
                try:
                    # Use the active strategy's type for AI optimization
                    ai_strategy_type = active_strategy_type if active_strategy_type else "ensemble"
                    print(f"[WF-SERVICE] Running AI optimization ({ai_strategy_type}) for period {i+1}/{len(periods)}")
                    ai_result = self._run_ai_optimization_at_date(
                        period_start, ai_strategy_type, lookback_days, top_symbols,
                        warm_start_params=previous_best_params,
                        n_trials=n_trials
                    )
                    if ai_result:
                        period_ai_opt = ai_result
                        # Add AI result to evaluations for comparison
                        # Use adaptive score for AI, calculated with regime-specific weights
                        evaluations.append({
                            "strategy_id": None,
                            "name": f"AI-{ai_result.market_regime.replace('_', '-').title()}",
                            "strategy_type": ai_result.strategy_type,
                            "sharpe_ratio": ai_result.expected_sharpe,
                            "total_return_pct": ai_result.expected_return_pct,
                            "max_drawdown_pct": ai_result.expected_max_dd,
                            "sortino_ratio": ai_result.expected_sortino,
                            "calmar_ratio": ai_result.expected_calmar,
                            "profit_factor": ai_result.expected_profit_factor,
                            "score": ai_result.adaptive_score,  # Use adaptive score
                            "is_ai": True,
                            "ai_params": ai_result.best_params,
                            "market_regime": ai_result.market_regime,
                            "regime_risk_level": ai_result.regime_risk_level,
                            "regime_confidence": ai_result.regime_confidence,
                            "combinations_tested": ai_result.combinations_tested
                        })
                        print(f"[WF-SERVICE] AI optimization complete: regime={ai_result.market_regime} "
                              f"(risk={ai_result.regime_risk_level}, conf={ai_result.regime_confidence:.0%}), "
                              f"tested={ai_result.combinations_tested}, adaptive_score={ai_result.adaptive_score:.1f}")
                except Exception as ai_err:
                    print(f"[WF-SERVICE] AI optimization failed for period {i+1}: {ai_err}")
                    import traceback
                    print(f"[WF-SERVICE] AI traceback: {traceback.format_exc()}")
                    # Continue without AI for this period

            if evaluations:
                # Find best option (existing strategy or AI-optimized)
                best = max(evaluations, key=lambda x: x["score"])
                score_diff = best["score"] - active_strategy_score

                # Determine if we should switch
                should_switch = False
                switch_reason = ""

                if i == 0:
                    # First period - always pick best
                    should_switch = True
                    switch_reason = "initial_selection"
                elif score_diff >= min_score_diff:
                    # Score improvement meets threshold
                    if best.get("is_ai"):
                        if not using_ai_params:
                            should_switch = True
                            switch_reason = f"ai_optimization_+{score_diff:.1f}pts"
                    elif best["strategy_id"] != (active_strategy.id if active_strategy else None):
                        should_switch = True
                        switch_reason = f"strategy_switch_+{score_diff:.1f}pts"

                if should_switch:
                    if best.get("is_ai"):
                        # Switching to AI-optimized params
                        switch_history.append(SwitchEvent(
                            date=period_start.strftime('%Y-%m-%d'),
                            from_strategy_id=active_strategy.id if active_strategy else None,
                            from_strategy_name=active_strategy.name if active_strategy else "AI-Params",
                            to_strategy_id=None,
                            to_strategy_name=best["name"],
                            reason=switch_reason,
                            score_before=active_strategy_score,
                            score_after=best["score"],
                            is_ai_generated=True,
                            ai_params=best.get("ai_params")
                        ))
                        active_params = best.get("ai_params")
                        active_strategy_type = best.get("strategy_type", active_strategy_type)
                        using_ai_params = True
                        active_strategy = None
                        active_strategy_score = best["score"]

                        if period_ai_opt:
                            period_ai_opt.was_adopted = True
                            period_ai_opt.reason = switch_reason
                    else:
                        # Switching to existing strategy
                        best_strategy = next(s for s in strategies if s.id == best["strategy_id"])
                        switch_history.append(SwitchEvent(
                            date=period_start.strftime('%Y-%m-%d'),
                            from_strategy_id=active_strategy.id if active_strategy else None,
                            from_strategy_name=active_strategy.name if active_strategy else "AI-Params",
                            to_strategy_id=best_strategy.id,
                            to_strategy_name=best_strategy.name,
                            reason=switch_reason,
                            score_before=active_strategy_score,
                            score_after=best["score"],
                            is_ai_generated=False
                        ))
                        active_strategy = best_strategy
                        active_strategy_score = best["score"]
                        active_params = None
                        using_ai_params = False

                        if period_ai_opt:
                            period_ai_opt.was_adopted = False
                            period_ai_opt.reason = "existing_strategy_better"

            # Record AI optimization result and update warm-start params
            if period_ai_opt:
                ai_optimizations.append(period_ai_opt)
                previous_best_params = period_ai_opt.best_params

            # Record parameter snapshot
            if using_ai_params and active_params:
                parameter_evolution.append(ParameterSnapshot(
                    date=period_start.strftime('%Y-%m-%d'),
                    strategy_name="AI-Optimized",
                    strategy_type=active_strategy_type,
                    params=active_params,
                    source="ai_generated"
                ))
            elif active_strategy:
                parameter_evolution.append(ParameterSnapshot(
                    date=period_start.strftime('%Y-%m-%d'),
                    strategy_name=active_strategy.name,
                    strategy_type=active_strategy.strategy_type,
                    params=json.loads(active_strategy.parameters),
                    source="existing"
                ))

            # Determine if strategy changed (force-close carried positions on switch)
            is_last_period = (i == len(periods) - 1)
            current_strategy_id = active_strategy.id if active_strategy else None
            strategy_changed = (i > 0 and (
                current_strategy_id != prev_active_strategy_id or
                using_ai_params != prev_using_ai_params
            ))

            if not carry_positions:
                # Old behavior: force-close every period
                force_close = True
                carry_in = None
            elif strategy_changed and carried_positions:
                # Strategy switched: force-close carried positions (different exit rules)
                force_close = True
                carry_in = carried_positions
                print(f"[WF-SERVICE] Strategy changed, force-closing {len(carried_positions)} carried positions")
            else:
                force_close = is_last_period  # Only force-close on final period
                carry_in = carried_positions

            # Simulate trading for this period
            if using_ai_params and active_params:
                new_capital, period_return, error, period_trades, new_carried = self._simulate_period_with_params(
                    active_params, active_strategy_type, period_start, period_end,
                    capital, ticker_list=top_symbols, strategy_name="AI-Optimized",
                    initial_positions=carry_in if carry_in else None,
                    force_close_at_end=force_close,
                    max_positions_override=max_positions,
                    position_size_pct_override=position_size_pct
                )
                strategy_name = "AI-Optimized"
                if error:
                    simulation_errors.append(error)
                all_trades.extend(period_trades)
            else:
                new_capital, period_equity, period_return, error, period_trades, new_carried = self._simulate_period_trading(
                    active_strategy, period_start, period_end, capital, ticker_list=top_symbols,
                    initial_positions=carry_in if carry_in else None,
                    force_close_at_end=force_close,
                    max_positions_override=max_positions,
                    position_size_pct_override=position_size_pct
                )
                strategy_name = active_strategy.name
                if error:
                    simulation_errors.append(error)
                all_trades.extend(period_trades)

            # Update carried positions for next period
            if force_close or strategy_changed:
                carried_positions = {}
            else:
                carried_positions = new_carried if new_carried else {}

            if carried_positions:
                print(f"[WF-SERVICE] Carrying {len(carried_positions)} positions to next period: "
                      f"{list(carried_positions.keys())}")

            # Track for detecting strategy switches next period
            prev_active_strategy_id = current_strategy_id
            prev_using_ai_params = using_ai_params

            period_details.append(SimulationPeriod(
                start_date=period_start,
                end_date=period_end,
                active_strategy_id=active_strategy.id if active_strategy else None,
                active_strategy_name=strategy_name,
                period_return_pct=period_return,
                cumulative_equity=new_capital,
                ai_optimization=period_ai_opt
            ))

            # Determine if this is a switch point for the chart
            is_switch = len(switch_history) > 0 and switch_history[-1].date == period_start.strftime('%Y-%m-%d')

            # Add to equity curve with strategy info and SPY benchmark
            date_str = period_end.strftime('%Y-%m-%d')
            equity_curve.append({
                "date": date_str,
                "equity": new_capital,
                "spy_equity": get_spy_equity(date_str),
                "strategy": strategy_name,
                "is_switch": is_switch,
                "is_ai": using_ai_params
            })

            capital = new_capital

        # Calculate final metrics
        print(f"[WF-SERVICE] Simulation complete: final capital=${capital:,.2f}, initial=${self.initial_capital:,.2f}")
        print(f"[WF-SERVICE] Equity curve has {len(equity_curve)} points")
        if len(equity_curve) > 0:
            equities = [p['equity'] for p in equity_curve]
            print(f"[WF-SERVICE] Equity range: ${min(equities):,.2f} to ${max(equities):,.2f}")
        total_return_pct = (capital - self.initial_capital) / self.initial_capital * 100

        # Calculate Sharpe ratio from equity curve
        if len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                ret = (equity_curve[i]["equity"] - equity_curve[i-1]["equity"]) / equity_curve[i-1]["equity"]
                returns.append(ret)
            if returns:
                # Annualize based on frequency
                periods_per_year = {"weekly": 52, "fast": 52, "biweekly": 26, "monthly": 12}.get(reoptimization_frequency, 26)
                avg_return = np.mean(returns) * periods_per_year
                std_return = np.std(returns) * np.sqrt(periods_per_year)
                sharpe_ratio = avg_return / std_return if std_return > 0 else 0
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        # Calculate max drawdown
        peak = equity_curve[0]["equity"]
        max_dd = 0
        for point in equity_curve:
            if point["equity"] > peak:
                peak = point["equity"]
            dd = (peak - point["equity"]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Calculate SPY benchmark return
        benchmark_return_pct = 0.0
        if 'SPY' in scanner_service.data_cache:
            spy_df = scanner_service.data_cache['SPY']
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
            # Handle timezone-aware index
            if spy_df.index.tz is not None:
                start_ts = start_ts.tz_localize(spy_df.index.tz) if start_ts.tz is None else start_ts.tz_convert(spy_df.index.tz)
                end_ts = end_ts.tz_localize(spy_df.index.tz) if end_ts.tz is None else end_ts.tz_convert(spy_df.index.tz)
            spy_data = spy_df[(spy_df.index >= start_ts) & (spy_df.index <= end_ts)]
            if len(spy_data) >= 2:
                spy_start = spy_data.iloc[0]['close']
                spy_end = spy_data.iloc[-1]['close']
                benchmark_return_pct = (spy_end - spy_start) / spy_start * 100
                print(f"[BENCHMARK] SPY {spy_start:.2f} -> {spy_end:.2f} = {benchmark_return_pct:.2f}%")
            else:
                print(f"[BENCHMARK] Warning: Only {len(spy_data)} SPY data points for {start_date} to {end_date}")
        else:
            print("[BENCHMARK] Warning: SPY not in data cache")

        # Count AI-generated switches
        ai_switches = sum(1 for s in switch_history if s.is_ai_generated)

        # Build JSON data
        switch_history_data = json.dumps([
            {
                "date": s.date,
                "from_id": s.from_strategy_id,
                "from_name": s.from_strategy_name,
                "to_id": s.to_strategy_id,
                "to_name": s.to_strategy_name,
                "reason": s.reason,
                "score_before": s.score_before,
                "score_after": s.score_after,
                "is_ai_generated": s.is_ai_generated,
                "ai_params": s.ai_params
            }
            for s in switch_history
        ])
        equity_curve_data = json.dumps(equity_curve)
        errors_data = json.dumps(simulation_errors[:20])  # Store up to 20 period info strings
        trades_data = json.dumps([
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
                "exit_reason": t.exit_reason,
                "momentum_score": t.momentum_score,
                "momentum_rank": t.momentum_rank,
                "pct_above_dwap_at_entry": t.pct_above_dwap_at_entry,
                "num_candidates": t.num_candidates,
                "dwap_at_entry": t.dwap_at_entry,
                "dwap_age": t.dwap_age,
                "short_mom": t.short_mom,
                "long_mom": t.long_mom,
                "volatility": t.volatility,
                "dist_from_high": t.dist_from_high,
                "vol_ratio": t.vol_ratio,
                "spy_trend": t.spy_trend,
            }
            for t in all_trades
        ])

        # Save or update simulation in database
        if existing_job_id:
            # Update existing record (async job flow)
            result = await db.execute(
                select(WalkForwardSimulation).where(WalkForwardSimulation.id == existing_job_id)
            )
            sim_record = result.scalar_one_or_none()
            if sim_record:
                sim_record.total_return_pct = total_return_pct
                sim_record.sharpe_ratio = sharpe_ratio
                sim_record.max_drawdown_pct = max_dd
                sim_record.num_strategy_switches = len(switch_history) - 1
                sim_record.benchmark_return_pct = benchmark_return_pct
                sim_record.switch_history_json = switch_history_data
                sim_record.equity_curve_json = equity_curve_data
                sim_record.errors_json = errors_data
                sim_record.trades_json = trades_data
                sim_record.status = "completed"
        else:
            # Create new record (sync flow)
            sim_record = WalkForwardSimulation(
                simulation_date=datetime.utcnow(),
                start_date=start_date,
                end_date=end_date,
                reoptimization_frequency=reoptimization_frequency,
                total_return_pct=total_return_pct,
                sharpe_ratio=sharpe_ratio,
                max_drawdown_pct=max_dd,
                num_strategy_switches=len(switch_history) - 1,
                benchmark_return_pct=benchmark_return_pct,
                switch_history_json=switch_history_data,
                equity_curve_json=equity_curve_data,
                errors_json=errors_data,
                trades_json=trades_data,
                status="completed"
            )
            db.add(sim_record)

        await db.commit()

        # Log error summary
        if simulation_errors:
            print(f"[WF-SERVICE] {len(simulation_errors)} errors during simulation")
            for err in simulation_errors[:5]:  # Log first 5 errors
                print(f"  - {err}")

        return WalkForwardResult(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            reoptimization_frequency=reoptimization_frequency,
            total_return_pct=round(total_return_pct, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            max_drawdown_pct=round(max_dd, 2),
            num_strategy_switches=len(switch_history) - 1,
            benchmark_return_pct=round(benchmark_return_pct, 2),
            switch_history=switch_history,
            equity_curve=equity_curve,
            period_details=period_details,
            ai_optimizations=ai_optimizations,
            parameter_evolution=parameter_evolution,
            errors=simulation_errors[:10],  # Include up to 10 errors
            trades=all_trades  # All trades across all periods
        )

    # ========================================================================
    # Step Functions methods: init, run_single_period, finalize
    # ========================================================================

    async def init_simulation(self, db: AsyncSession, config: dict) -> dict:
        """
        Initialize a walk-forward simulation for Step Functions execution.

        Creates/updates the DB record, computes period dates, returns initial state.
        The state dict is small (~2KB) and passes between Step Functions steps.

        Args:
            db: Database session
            config: Dict with start_date, end_date, frequency, min_score_diff,
                    enable_ai, max_symbols, strategy_id, n_trials, job_id

        Returns:
            State dict for Step Functions: simulation_id, period_index, total_periods,
            capital, active_strategy_*, config, etc.
        """
        from datetime import datetime
        import logging
        logger = logging.getLogger()

        start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")
        frequency = config.get("frequency", "biweekly")
        fixed_strategy_id = config.get("strategy_id")
        enable_ai = config.get("enable_ai", True)

        print(f"[WF-INIT] Initializing: {start_date} to {end_date}, freq={frequency}, "
              f"ai={enable_ai}, fixed_strategy={fixed_strategy_id}")

        # Load all strategies
        result = await db.execute(
            select(StrategyDefinition).order_by(StrategyDefinition.id)
        )
        strategies = result.scalars().all()
        if not strategies:
            raise RuntimeError("No strategies found in database")

        # Validate fixed strategy
        if fixed_strategy_id:
            fixed = next((s for s in strategies if s.id == fixed_strategy_id), None)
            if not fixed:
                raise RuntimeError(f"Strategy with id {fixed_strategy_id} not found")
            initial_strategy_id = fixed.id
            initial_strategy_name = fixed.name
            initial_strategy_type = fixed.strategy_type
        else:
            initial_strategy_id = strategies[0].id
            initial_strategy_name = strategies[0].name
            initial_strategy_type = strategies[0].strategy_type

        # Compute period dates
        periods = self._get_period_dates(start_date, end_date, frequency)
        total_periods = len(periods)
        print(f"[WF-INIT] {total_periods} periods, {len(strategies)} strategies")

        # Get symbol universe
        _max_symbols = config.get("max_symbols", 50)
        if _max_symbols == 0:
            from app.services.scanner import _EXCLUDED_SET
            top_symbols = [s for s, df in scanner_service.data_cache.items()
                           if s not in _EXCLUDED_SET and len(df) >= 200
                           and 'volume' in df.columns and 'close' in df.columns
                           and df['volume'].max() >= 500_000 and df['close'].max() >= 15.0]
            print(f"[WF-INIT] Using PRODUCTION universe: {len(top_symbols)} symbols")
        else:
            top_symbols = get_top_liquid_symbols(max_symbols=_max_symbols)
        if not top_symbols:
            raise RuntimeError("No liquid symbols found. Ensure data is loaded.")

        # Create or update simulation record
        job_id = config.get("job_id")
        if job_id:
            result = await db.execute(
                select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
            )
            sim = result.scalar_one_or_none()
            if sim:
                sim.status = "running"
                await db.commit()
            else:
                raise RuntimeError(f"Simulation job {job_id} not found")
        else:
            sim = WalkForwardSimulation(
                simulation_date=datetime.utcnow(),
                start_date=start_date,
                end_date=end_date,
                reoptimization_frequency=frequency,
                status="running",
                total_return_pct=0,
                sharpe_ratio=0,
                max_drawdown_pct=0,
                num_strategy_switches=0,
                benchmark_return_pct=0,
            )
            db.add(sim)
            await db.commit()
            await db.refresh(sim)
            job_id = sim.id

        print(f"[WF-INIT] Simulation {job_id} initialized with {total_periods} periods")

        # Return compact state for Step Functions (~2KB)
        return {
            "simulation_id": job_id,
            "period_index": 0,
            "total_periods": total_periods,
            "capital": self.initial_capital,
            "active_strategy_id": initial_strategy_id,
            "active_strategy_name": initial_strategy_name,
            "active_strategy_type": initial_strategy_type,
            "active_strategy_score": 0.0,
            "active_params": None,
            "using_ai_params": False,
            "warm_start_params": None,
            "config": {
                "start_date": config["start_date"],
                "end_date": config["end_date"],
                "frequency": frequency,
                "min_score_diff": config.get("min_score_diff", 10.0),
                "enable_ai": enable_ai,
                "max_symbols": config.get("max_symbols", 50),
                "strategy_id": fixed_strategy_id,
                "n_trials": config.get("n_trials", 30),
                "lookback_days": config.get("lookback_days", 60),
            }
        }

    async def run_single_period(self, db: AsyncSession, state: dict) -> dict:
        """
        Run a single period of the walk-forward simulation.

        Deterministically recomputes the period dates from config, evaluates
        strategies, runs AI optimization if enabled, simulates trading,
        and writes results to walk_forward_period_results table.

        Args:
            db: Database session
            state: Current state dict from Step Functions

        Returns:
            Updated state dict with incremented period_index and new capital
        """
        import logging
        logger = logging.getLogger()

        period_index = state["period_index"]
        simulation_id = state["simulation_id"]
        capital = state["capital"]
        config = state["config"]

        start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")
        frequency = config["frequency"]
        min_score_diff = config["min_score_diff"]
        enable_ai = config["enable_ai"]
        fixed_strategy_id = config.get("strategy_id")
        n_trials = config.get("n_trials", 30)
        lookback_days = config.get("lookback_days", 60)

        # Recompute period dates (deterministic from config)
        periods = self._get_period_dates(start_date, end_date, frequency)
        period_start, period_end = periods[period_index]

        print(f"[WF-PERIOD] Period {period_index + 1}/{len(periods)}: "
              f"{period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}, "
              f"capital=${capital:,.2f}")

        # Load strategies from DB
        result = await db.execute(
            select(StrategyDefinition).order_by(StrategyDefinition.id)
        )
        strategies = result.scalars().all()

        # Get symbol universe
        _max_symbols = config.get("max_symbols", 50)
        if _max_symbols == 0:
            from app.services.scanner import _EXCLUDED_SET
            top_symbols = [s for s, df in scanner_service.data_cache.items()
                           if s not in _EXCLUDED_SET and len(df) >= 200
                           and 'volume' in df.columns and 'close' in df.columns
                           and df['volume'].max() >= 500_000 and df['close'].max() >= 15.0]
        else:
            top_symbols = get_top_liquid_symbols(max_symbols=_max_symbols)

        # Reconstruct active state from state dict
        active_strategy = None
        active_strategy_id = state["active_strategy_id"]
        active_strategy_name = state["active_strategy_name"]
        active_strategy_type = state["active_strategy_type"]
        active_strategy_score = state["active_strategy_score"]
        active_params = state.get("active_params")
        using_ai_params = state.get("using_ai_params", False)
        warm_start_params = state.get("warm_start_params")

        if active_strategy_id and not using_ai_params:
            active_strategy = next((s for s in strategies if s.id == active_strategy_id), None)

        fixed_strategy = None
        if fixed_strategy_id:
            fixed_strategy = next((s for s in strategies if s.id == fixed_strategy_id), None)

        # Track outputs for this period
        switch_event = None
        period_ai_opt = None
        error_info = None

        try:
            # -- Strategy evaluation (same logic as run_walk_forward_simulation) --
            if fixed_strategy:
                if period_index == 0:
                    active_strategy = fixed_strategy
                    active_strategy_type = fixed_strategy.strategy_type
                    active_strategy_score = 0.0
                    switch_event = {
                        "date": period_start.strftime('%Y-%m-%d'),
                        "from_id": None,
                        "from_name": "Initial",
                        "to_id": fixed_strategy.id,
                        "to_name": fixed_strategy.name,
                        "reason": "fixed_strategy_selected",
                        "score_before": 0,
                        "score_after": 0.0,
                        "is_ai_generated": False,
                        "ai_params": None
                    }
                evaluations = []
            else:
                evaluations = []
                for strategy in strategies:
                    metrics = self._evaluate_strategy_at_date(
                        strategy, period_start, lookback_days, ticker_list=top_symbols
                    )
                    if metrics:
                        metrics["score"] = self._calculate_recommendation_score(metrics)
                        metrics["is_ai"] = False
                        evaluations.append(metrics)

            # -- AI optimization --
            if enable_ai:
                try:
                    ai_strategy_type = active_strategy_type if active_strategy_type else "ensemble"
                    print(f"[WF-PERIOD] Running AI optimization ({ai_strategy_type})")
                    ai_result = self._run_ai_optimization_at_date(
                        period_start, ai_strategy_type, lookback_days, top_symbols,
                        warm_start_params=warm_start_params,
                        n_trials=n_trials
                    )
                    if ai_result:
                        period_ai_opt = ai_result
                        evaluations.append({
                            "strategy_id": None,
                            "name": f"AI-{ai_result.market_regime.replace('_', '-').title()}",
                            "strategy_type": ai_result.strategy_type,
                            "sharpe_ratio": ai_result.expected_sharpe,
                            "total_return_pct": ai_result.expected_return_pct,
                            "max_drawdown_pct": ai_result.expected_max_dd,
                            "sortino_ratio": ai_result.expected_sortino,
                            "calmar_ratio": ai_result.expected_calmar,
                            "profit_factor": ai_result.expected_profit_factor,
                            "score": ai_result.adaptive_score,
                            "is_ai": True,
                            "ai_params": ai_result.best_params,
                            "market_regime": ai_result.market_regime,
                            "regime_risk_level": ai_result.regime_risk_level,
                            "regime_confidence": ai_result.regime_confidence,
                            "combinations_tested": ai_result.combinations_tested
                        })
                except Exception as ai_err:
                    print(f"[WF-PERIOD] AI optimization failed: {ai_err}")

            # -- Switching logic --
            if evaluations:
                best = max(evaluations, key=lambda x: x["score"])
                score_diff = best["score"] - active_strategy_score

                should_switch = False
                switch_reason = ""

                if period_index == 0 and not fixed_strategy:
                    should_switch = True
                    switch_reason = "initial_selection"
                elif score_diff >= min_score_diff:
                    if best.get("is_ai"):
                        if not using_ai_params:
                            should_switch = True
                            switch_reason = f"ai_optimization_+{score_diff:.1f}pts"
                    elif best["strategy_id"] != active_strategy_id:
                        should_switch = True
                        switch_reason = f"strategy_switch_+{score_diff:.1f}pts"

                if should_switch:
                    if best.get("is_ai"):
                        switch_event = {
                            "date": period_start.strftime('%Y-%m-%d'),
                            "from_id": active_strategy_id,
                            "from_name": active_strategy_name,
                            "to_id": None,
                            "to_name": best["name"],
                            "reason": switch_reason,
                            "score_before": active_strategy_score,
                            "score_after": best["score"],
                            "is_ai_generated": True,
                            "ai_params": best.get("ai_params")
                        }
                        active_params = best.get("ai_params")
                        active_strategy_type = best.get("strategy_type", active_strategy_type)
                        using_ai_params = True
                        active_strategy = None
                        active_strategy_id = None
                        active_strategy_name = best["name"]
                        active_strategy_score = best["score"]
                        if period_ai_opt:
                            period_ai_opt.was_adopted = True
                            period_ai_opt.reason = switch_reason
                    else:
                        best_strategy = next(s for s in strategies if s.id == best["strategy_id"])
                        switch_event = {
                            "date": period_start.strftime('%Y-%m-%d'),
                            "from_id": active_strategy_id,
                            "from_name": active_strategy_name,
                            "to_id": best_strategy.id,
                            "to_name": best_strategy.name,
                            "reason": switch_reason,
                            "score_before": active_strategy_score,
                            "score_after": best["score"],
                            "is_ai_generated": False,
                            "ai_params": None
                        }
                        active_strategy = best_strategy
                        active_strategy_id = best_strategy.id
                        active_strategy_name = best_strategy.name
                        active_strategy_score = best["score"]
                        active_params = None
                        using_ai_params = False
                        if period_ai_opt:
                            period_ai_opt.was_adopted = False
                            period_ai_opt.reason = "existing_strategy_better"

            # Update warm-start params
            if period_ai_opt:
                warm_start_params = period_ai_opt.best_params

            # -- Determine position carry-over --
            is_last_period = (period_index == state["total_periods"] - 1)
            carried_positions = state.get("carried_positions") or {}
            prev_strategy_id = state.get("prev_active_strategy_id")
            prev_ai = state.get("prev_using_ai_params", False)

            strategy_changed = (period_index > 0 and (
                active_strategy_id != prev_strategy_id or
                using_ai_params != prev_ai
            ))

            if strategy_changed and carried_positions:
                force_close = True
                carry_in = carried_positions
                print(f"[WF-PERIOD] Strategy changed, force-closing {len(carried_positions)} carried positions")
            else:
                force_close = is_last_period
                carry_in = carried_positions

            # -- Simulate trading --
            strategy_name = active_strategy_name
            period_trades = []
            equity_points = []
            new_carried = {}

            if using_ai_params and active_params:
                new_capital, period_return, info, period_trades, new_carried = self._simulate_period_with_params(
                    active_params, active_strategy_type, period_start, period_end,
                    capital, ticker_list=top_symbols, strategy_name="AI-Optimized",
                    initial_positions=carry_in if carry_in else None,
                    force_close_at_end=force_close
                )
                strategy_name = "AI-Optimized"
                if info:
                    error_info = info
                equity_points = [
                    {"date": period_start.strftime('%Y-%m-%d'), "equity": capital, "strategy": strategy_name},
                    {"date": period_end.strftime('%Y-%m-%d'), "equity": new_capital, "strategy": strategy_name}
                ]
            elif active_strategy:
                new_capital, eq_pts, period_return, info, period_trades, new_carried = self._simulate_period_trading(
                    active_strategy, period_start, period_end, capital, ticker_list=top_symbols,
                    initial_positions=carry_in if carry_in else None,
                    force_close_at_end=force_close
                )
                strategy_name = active_strategy.name
                if info:
                    error_info = info
                equity_points = eq_pts if eq_pts else [
                    {"date": period_start.strftime('%Y-%m-%d'), "equity": capital, "strategy": strategy_name},
                    {"date": period_end.strftime('%Y-%m-%d'), "equity": new_capital, "strategy": strategy_name}
                ]
            else:
                # No active strategy (shouldn't happen), keep capital flat
                new_capital = capital
                period_return = 0.0
                error_info = f"Period {period_start.strftime('%Y-%m-%d')}: No active strategy"

            # Update carried positions for next period
            if force_close or strategy_changed:
                carried_positions_out = {}
            else:
                carried_positions_out = new_carried if new_carried else {}

            # Build parameter snapshot
            param_snapshot = None
            if using_ai_params and active_params:
                param_snapshot = {
                    "date": period_start.strftime('%Y-%m-%d'),
                    "strategy_name": "AI-Optimized",
                    "strategy_type": active_strategy_type,
                    "params": active_params,
                    "source": "ai_generated"
                }
            elif active_strategy:
                param_snapshot = {
                    "date": period_start.strftime('%Y-%m-%d'),
                    "strategy_name": active_strategy.name,
                    "strategy_type": active_strategy.strategy_type,
                    "params": json.loads(active_strategy.parameters),
                    "source": "existing"
                }

        except Exception as e:
            import traceback
            error_info = f"Period {period_start.strftime('%Y-%m-%d')}: ERROR {str(e)}"
            print(f"[WF-PERIOD] ERROR: {error_info}")
            print(traceback.format_exc())
            new_capital = capital
            period_return = 0.0
            period_trades = []
            equity_points = []
            param_snapshot = None
            carried_positions_out = {}

        # -- Write period result to DB --
        trades_data = json.dumps([
            {
                "period_start": t.period_start, "period_end": t.period_end,
                "strategy_name": t.strategy_name, "symbol": t.symbol,
                "entry_date": t.entry_date, "exit_date": t.exit_date,
                "entry_price": t.entry_price, "exit_price": t.exit_price,
                "shares": t.shares, "pnl_pct": t.pnl_pct,
                "pnl_dollars": t.pnl_dollars, "exit_reason": t.exit_reason,
                "momentum_score": t.momentum_score, "momentum_rank": t.momentum_rank,
                "pct_above_dwap_at_entry": t.pct_above_dwap_at_entry,
                "num_candidates": t.num_candidates, "dwap_at_entry": t.dwap_at_entry,
                "dwap_age": t.dwap_age, "short_mom": t.short_mom,
                "long_mom": t.long_mom, "volatility": t.volatility,
                "dist_from_high": t.dist_from_high, "vol_ratio": t.vol_ratio,
                "spy_trend": t.spy_trend,
            }
            for t in period_trades
        ]) if period_trades else "[]"

        ai_opt_data = None
        if period_ai_opt:
            ai_opt_data = json.dumps({
                "date": period_ai_opt.date,
                "best_params": period_ai_opt.best_params,
                "expected_sharpe": period_ai_opt.expected_sharpe,
                "expected_return_pct": period_ai_opt.expected_return_pct,
                "strategy_type": period_ai_opt.strategy_type,
                "market_regime": period_ai_opt.market_regime,
                "was_adopted": period_ai_opt.was_adopted,
                "reason": period_ai_opt.reason,
                "adaptive_score": period_ai_opt.adaptive_score,
                "combinations_tested": period_ai_opt.combinations_tested,
            })

        period_result = WalkForwardPeriodResult(
            simulation_id=simulation_id,
            period_index=period_index,
            period_start=period_start,
            period_end=period_end,
            starting_capital=capital,
            ending_capital=new_capital,
            period_return_pct=period_return,
            strategy_name=strategy_name,
            strategy_type=active_strategy_type,
            is_ai_params=using_ai_params,
            switch_event_json=json.dumps(switch_event) if switch_event else None,
            trades_json=trades_data,
            equity_points_json=json.dumps(equity_points) if equity_points else None,
            ai_optimization_json=ai_opt_data,
            parameter_snapshot_json=json.dumps(param_snapshot) if param_snapshot else None,
            error_info=error_info
        )
        db.add(period_result)
        await db.commit()

        print(f"[WF-PERIOD] Period {period_index + 1} done: ${capital:,.2f} -> ${new_capital:,.2f} "
              f"({period_return:+.2f}%), {len(period_trades)} trades")

        # Return updated state
        return {
            "simulation_id": simulation_id,
            "period_index": period_index + 1,
            "total_periods": state["total_periods"],
            "capital": new_capital,
            "active_strategy_id": active_strategy_id,
            "active_strategy_name": active_strategy_name,
            "active_strategy_type": active_strategy_type,
            "active_strategy_score": active_strategy_score,
            "active_params": active_params,
            "using_ai_params": using_ai_params,
            "warm_start_params": warm_start_params,
            "carried_positions": carried_positions_out,
            "prev_active_strategy_id": active_strategy_id,
            "prev_using_ai_params": using_ai_params,
            "config": config
        }

    async def finalize_simulation(self, db: AsyncSession, state: dict) -> dict:
        """
        Finalize a Step Functions walk-forward simulation.

        Reads all period results from DB, computes aggregate metrics,
        updates the simulation record, and cleans up period results.

        Args:
            db: Database session
            state: Final state dict from Step Functions

        Returns:
            Summary dict with total_return, sharpe, max_dd, etc.
        """
        simulation_id = state["simulation_id"]
        config = state["config"]
        frequency = config["frequency"]

        print(f"[WF-FINALIZE] Finalizing simulation {simulation_id}")

        # Read all period results
        result = await db.execute(
            select(WalkForwardPeriodResult)
            .where(WalkForwardPeriodResult.simulation_id == simulation_id)
            .order_by(WalkForwardPeriodResult.period_index)
        )
        period_results = result.scalars().all()

        if not period_results:
            raise RuntimeError(f"No period results found for simulation {simulation_id}")

        # Rebuild combined data from period results
        equity_curve = []
        switch_history = []
        all_trades = []
        simulation_errors = []
        initial_capital = self.initial_capital

        # Add initial equity point
        start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")

        # Get SPY benchmark data
        spy_start_price = None
        spy_df = None
        if 'SPY' in scanner_service.data_cache:
            spy_df = scanner_service.data_cache['SPY']
            start_ts = pd.Timestamp(start_date)
            if spy_df.index.tz is not None:
                start_ts = start_ts.tz_localize(spy_df.index.tz) if start_ts.tz is None else start_ts.tz_convert(spy_df.index.tz)
            spy_at_start = spy_df[spy_df.index >= start_ts]
            if len(spy_at_start) > 0:
                spy_start_price = spy_at_start.iloc[0]['close']

        def get_spy_equity(date_str: str) -> float:
            if spy_start_price is None or spy_df is None:
                return None
            try:
                date_ts = pd.Timestamp(date_str)
                if spy_df.index.tz is not None:
                    date_ts = date_ts.tz_localize(spy_df.index.tz) if date_ts.tz is None else date_ts.tz_convert(spy_df.index.tz)
                spy_at_date = spy_df[spy_df.index <= date_ts]
                if len(spy_at_date) > 0:
                    spy_price = spy_at_date.iloc[-1]['close']
                    return initial_capital * (spy_price / spy_start_price)
            except:
                pass
            return None

        equity_curve.append({
            "date": config["start_date"],
            "equity": initial_capital,
            "spy_equity": initial_capital,
            "strategy": "Initial",
            "is_switch": False
        })

        for pr in period_results:
            # Collect switch events
            if pr.switch_event_json:
                switch_event = json.loads(pr.switch_event_json)
                switch_history.append(switch_event)

            # Collect trades
            if pr.trades_json:
                trades = json.loads(pr.trades_json)
                all_trades.extend(trades)

            # Collect errors
            if pr.error_info:
                simulation_errors.append(pr.error_info)

            # Add equity curve point
            date_str = pr.period_end.strftime('%Y-%m-%d') if pr.period_end else None
            is_switch = pr.switch_event_json is not None
            equity_curve.append({
                "date": date_str,
                "equity": pr.ending_capital,
                "spy_equity": get_spy_equity(date_str) if date_str else None,
                "strategy": pr.strategy_name,
                "is_switch": is_switch,
                "is_ai": pr.is_ai_params
            })

        # Calculate final metrics
        final_capital = period_results[-1].ending_capital
        total_return_pct = (final_capital - initial_capital) / initial_capital * 100

        # Sharpe ratio from equity curve
        if len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                prev_eq = equity_curve[i-1]["equity"]
                curr_eq = equity_curve[i]["equity"]
                if prev_eq > 0:
                    returns.append((curr_eq - prev_eq) / prev_eq)
            if returns:
                periods_per_year = {"weekly": 52, "fast": 52, "biweekly": 26, "monthly": 12}.get(frequency, 26)
                avg_return = np.mean(returns) * periods_per_year
                std_return = np.std(returns) * np.sqrt(periods_per_year)
                sharpe_ratio = avg_return / std_return if std_return > 0 else 0
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        # Max drawdown
        peak = equity_curve[0]["equity"]
        max_dd = 0
        for point in equity_curve:
            if point["equity"] > peak:
                peak = point["equity"]
            dd = (peak - point["equity"]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # SPY benchmark return
        benchmark_return_pct = 0.0
        if spy_df is not None:
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
            if spy_df.index.tz is not None:
                start_ts = start_ts.tz_localize(spy_df.index.tz) if start_ts.tz is None else start_ts.tz_convert(spy_df.index.tz)
                end_ts = end_ts.tz_localize(spy_df.index.tz) if end_ts.tz is None else end_ts.tz_convert(spy_df.index.tz)
            spy_data = spy_df[(spy_df.index >= start_ts) & (spy_df.index <= end_ts)]
            if len(spy_data) >= 2:
                spy_start = spy_data.iloc[0]['close']
                spy_end = spy_data.iloc[-1]['close']
                benchmark_return_pct = (spy_end - spy_start) / spy_start * 100

        # Serialize to JSON
        switch_history_data = json.dumps(switch_history)
        equity_curve_data = json.dumps(equity_curve)
        errors_data = json.dumps(simulation_errors[:20])
        trades_data = json.dumps(all_trades)

        # Update simulation record
        result = await db.execute(
            select(WalkForwardSimulation).where(WalkForwardSimulation.id == simulation_id)
        )
        sim = result.scalar_one_or_none()
        if sim:
            sim.total_return_pct = round(total_return_pct, 2)
            sim.sharpe_ratio = round(sharpe_ratio, 2)
            sim.max_drawdown_pct = round(max_dd, 2)
            sim.num_strategy_switches = len(switch_history) - 1 if switch_history else 0
            sim.benchmark_return_pct = round(benchmark_return_pct, 2)
            sim.switch_history_json = switch_history_data
            sim.equity_curve_json = equity_curve_data
            sim.errors_json = errors_data
            sim.trades_json = trades_data
            sim.status = "completed"

        # Clean up period results (data now lives in simulation record)
        for pr in period_results:
            await db.delete(pr)

        await db.commit()

        summary = {
            "simulation_id": simulation_id,
            "status": "completed",
            "total_return_pct": round(total_return_pct, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "num_strategy_switches": len(switch_history) - 1 if switch_history else 0,
            "total_trades": len(all_trades),
            "total_periods": len(period_results),
            "errors": len(simulation_errors),
        }
        print(f"[WF-FINALIZE] Complete: {summary}")
        return summary

    async def mark_simulation_failed(self, db: AsyncSession, state: dict, error: str = None) -> dict:
        """Mark a simulation as failed in the database."""
        simulation_id = state.get("simulation_id")
        if not simulation_id:
            return {"status": "error", "message": "No simulation_id in state"}

        result = await db.execute(
            select(WalkForwardSimulation).where(WalkForwardSimulation.id == simulation_id)
        )
        sim = result.scalar_one_or_none()
        if sim:
            sim.status = "failed"
            if error:
                sim.switch_history_json = json.dumps({"error": error})
            await db.commit()

        return {"status": "failed", "simulation_id": simulation_id, "error": error}

    async def get_simulation_history(
        self,
        db: AsyncSession,
        limit: int = 10
    ) -> List[Dict]:
        """Get recent walk-forward simulations"""
        from sqlalchemy import desc

        result = await db.execute(
            select(WalkForwardSimulation)
            .order_by(desc(WalkForwardSimulation.simulation_date))
            .limit(limit)
        )
        sims = result.scalars().all()

        return [
            {
                "id": s.id,
                "simulation_date": s.simulation_date.isoformat() if s.simulation_date else None,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "reoptimization_frequency": s.reoptimization_frequency,
                "total_return_pct": s.total_return_pct,
                "sharpe_ratio": s.sharpe_ratio,
                "max_drawdown_pct": s.max_drawdown_pct,
                "num_strategy_switches": s.num_strategy_switches,
                "benchmark_return_pct": s.benchmark_return_pct,
                "status": s.status
            }
            for s in sims
        ]

    async def get_simulation_details(
        self,
        db: AsyncSession,
        simulation_id: int
    ) -> Optional[Dict]:
        """Get detailed results for a specific simulation"""
        result = await db.execute(
            select(WalkForwardSimulation).where(WalkForwardSimulation.id == simulation_id)
        )
        sim = result.scalar_one_or_none()

        if not sim:
            return None

        return {
            "id": sim.id,
            "simulation_date": sim.simulation_date.isoformat() if sim.simulation_date else None,
            "start_date": sim.start_date.isoformat() if sim.start_date else None,
            "end_date": sim.end_date.isoformat() if sim.end_date else None,
            "reoptimization_frequency": sim.reoptimization_frequency,
            "total_return_pct": sim.total_return_pct,
            "sharpe_ratio": sim.sharpe_ratio,
            "max_drawdown_pct": sim.max_drawdown_pct,
            "num_strategy_switches": sim.num_strategy_switches,
            "benchmark_return_pct": sim.benchmark_return_pct,
            "switch_history": json.loads(sim.switch_history_json) if sim.switch_history_json else [],
            "equity_curve": json.loads(sim.equity_curve_json) if sim.equity_curve_json else [],
            "errors": json.loads(sim.errors_json) if sim.errors_json else [],
            "trades": json.loads(sim.trades_json) if sim.trades_json else [],
            "status": sim.status
        }


# Singleton instance
walk_forward_service = WalkForwardService()
