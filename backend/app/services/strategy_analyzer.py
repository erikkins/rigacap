"""
Strategy Analyzer Service

Evaluates trading strategies by running rolling backtests and generating
AI-powered recommendations for which strategy to activate.
"""

import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import StrategyDefinition, StrategyEvaluation
from app.services.backtester import BacktesterService
from app.services.scanner import scanner_service
from app.core.config import settings


@dataclass
class StrategyParams:
    """Strategy parameters parsed from JSON"""
    # Common
    max_positions: int = 5
    position_size_pct: float = 18.0
    min_volume: int = 500_000
    min_price: float = 20.0

    # DWAP-specific (used by dwap and dwap_hybrid)
    dwap_threshold_pct: float = 5.0
    stop_loss_pct: float = 8.0
    profit_target_pct: float = 20.0
    volume_spike_mult: float = 1.5

    # Momentum-specific
    short_momentum_days: int = 10
    long_momentum_days: int = 60
    trailing_stop_pct: float = 12.0
    market_filter_enabled: bool = True
    rebalance_frequency: str = "weekly"
    short_mom_weight: float = 0.5
    long_mom_weight: float = 0.3
    volatility_penalty: float = 0.2
    near_50d_high_pct: float = 5.0

    # DWAP Hybrid uses: dwap_threshold_pct (entry), trailing_stop_pct (exit)
    # It combines DWAP entry signals with momentum-style trailing stops

    # V2 params (backward compatible defaults = disabled/no-op)
    rsi_oversold_filter: int = 100          # RSI threshold; 100 = disabled
    volume_ratio_min: float = 0.0           # Min vol/20d avg ratio; 0 = disabled
    exit_type: str = "trailing_stop"        # "trailing_stop", "hybrid", "time_capped"
    hybrid_initial_target_pct: float = 15.0
    hybrid_trailing_pct: float = 8.0
    max_hold_days: int = 60
    sector_cap: int = 0                     # Max positions per sector; 0 = disabled

    # V2 lever 8: Profit-based stop tightening
    breakeven_pct: float = 0               # Move stop to entry once up X%; 0=disabled
    profit_lock_pct: float = 0             # Tighten trailing stop once up X%; 0=disabled
    profit_lock_stop_pct: float = 5.0      # Tightened trailing stop % from peak

    # Regime cooldown: days to stay in cash after regime exit (anti-whipsaw)
    regime_cooldown_days: int = 0          # 0=disabled, 10=wait 10 trading days before re-entry

    # V2 lever 10: Pyramiding (doubling down on winners)
    pyramid_threshold_pct: float = 0       # Add to position once up X%; 0=disabled
    pyramid_size_pct: float = 0.0          # Add-on size as % of initial capital
    pyramid_max_adds: int = 0              # Max pyramid adds per position; 0=disabled

    # V2 lever 9: Anti-squeeze filters (Apr 14 2026, after Feb 2021 damage)
    max_recent_return_pct: float = 1000    # Reject candidate if up > X% in last 30 days; 1000=disabled
    price_velocity_cap_pct: float = 1000   # Reject candidate if up > X% in last 5 days; 1000=disabled

    # V2 lever 10: Circuit breaker — halt entries on cascading same-day stops.
    # Defaults match BacktesterService.__init__ (stops=3, pause=10d, tighten=0).
    # When Lever 10 was added to V2_PARAM_SPACES (commit 0412009, Apr 19 2026),
    # these fields were NOT added here in lockstep — every Optuna trial after
    # that crashed on StrategyParams(**suggested_params) with "unexpected
    # keyword argument 'circuit_breaker_stops'", got swallowed by
    # _test_param_combination's broad except, and Optuna's multi-objective TPE
    # eventually choked on the all-pruned trial set. Silent AI failure for 8 days.
    circuit_breaker_stops: int = 3
    circuit_breaker_pause_days: int = 10
    circuit_breaker_tighten_pct: float = 0

    @classmethod
    def from_json(cls, json_str: str) -> "StrategyParams":
        """Create StrategyParams from JSON string"""
        data = json.loads(json_str)
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


def get_top_liquid_symbols(max_symbols: int = 100) -> list:
    """Get the most liquid symbols by average volume for faster analysis"""
    if not scanner_service.data_cache:
        return []

    symbol_volumes = []
    for symbol, df in scanner_service.data_cache.items():
        if len(df) >= 200:  # Need enough data
            avg_vol = df['volume'].tail(60).mean() if 'volume' in df.columns else 0
            symbol_volumes.append((symbol, avg_vol))

    # Sort by volume descending and take top N
    symbol_volumes.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in symbol_volumes[:max_symbols]]


class CustomBacktester(BacktesterService):
    """Backtester with customizable parameters"""

    def configure(self, params: StrategyParams):
        """Apply custom parameters to backtester"""
        self.max_positions = params.max_positions
        self.position_size_pct = params.position_size_pct / 100
        self.min_volume = params.min_volume
        self.min_price = params.min_price

        # DWAP settings
        self.dwap_threshold_pct = params.dwap_threshold_pct / 100
        self.stop_loss_pct = params.stop_loss_pct / 100
        self.profit_target_pct = params.profit_target_pct / 100
        self.volume_spike_mult = params.volume_spike_mult

        # Momentum settings
        self.short_mom_days = params.short_momentum_days
        self.long_mom_days = params.long_momentum_days
        self.trailing_stop_pct = params.trailing_stop_pct / 100

        # Momentum scoring weights
        self.short_mom_weight = params.short_mom_weight
        self.long_mom_weight = params.long_mom_weight
        self.volatility_penalty = params.volatility_penalty
        self.near_50d_high_pct = params.near_50d_high_pct

        # V2 params
        self.rsi_oversold_filter = params.rsi_oversold_filter
        self.volume_ratio_min = params.volume_ratio_min
        self.exit_type = params.exit_type
        self.hybrid_initial_target_pct = params.hybrid_initial_target_pct
        self.hybrid_trailing_pct = params.hybrid_trailing_pct
        self.max_hold_days = params.max_hold_days
        self.sector_cap = params.sector_cap

        # V2 lever 8: Profit-based stop tightening
        self.breakeven_pct = params.breakeven_pct
        self.profit_lock_pct = params.profit_lock_pct
        self.profit_lock_stop_pct = params.profit_lock_stop_pct

        # Regime cooldown
        self.regime_cooldown_days = params.regime_cooldown_days

        # V2 lever 10: Pyramiding
        self.pyramid_threshold_pct = params.pyramid_threshold_pct
        self.pyramid_size_pct = params.pyramid_size_pct
        self.pyramid_max_adds = params.pyramid_max_adds

        # V2 lever 9: Anti-squeeze filters
        self.max_recent_return_pct = params.max_recent_return_pct
        self.price_velocity_cap_pct = params.price_velocity_cap_pct


class StrategyAnalyzerService:
    """
    Service for evaluating and comparing trading strategies

    Runs backtests on all strategies and generates recommendations
    based on performance metrics.
    """

    def calculate_recommendation_score(self, metrics: dict) -> float:
        """
        Calculate composite recommendation score (0-100)

        Scoring weights:
        - Sharpe ratio: 40% weight (normalized 0-2 -> 0-40)
        - Total return: 30% weight (normalized 0-50% -> 0-30)
        - Max drawdown: 30% weight (lower is better, 0-20% -> 30-0)
        """
        sharpe = metrics.get('sharpe_ratio', 0)
        total_return = metrics.get('total_return_pct', 0)
        max_drawdown = metrics.get('max_drawdown_pct', 0)

        # Normalize and weight
        sharpe_score = min(max(sharpe / 2, 0), 1) * 40
        return_score = min(max(total_return / 50, 0), 1) * 30
        dd_score = max(1 - max_drawdown / 20, 0) * 30

        return round(sharpe_score + return_score + dd_score, 1)

    def generate_recommendation_notes(
        self,
        evaluations: list[dict],
        recommended_id: int,
        current_active_id: Optional[int]
    ) -> str:
        """
        Generate natural language recommendation notes

        Args:
            evaluations: List of evaluation dicts with strategy info
            recommended_id: ID of recommended strategy
            current_active_id: ID of currently active strategy

        Returns:
            Human-readable recommendation text
        """
        if not evaluations:
            return "No strategies evaluated."

        # Sort by score
        sorted_evals = sorted(evaluations, key=lambda x: x['recommendation_score'], reverse=True)
        best = sorted_evals[0]
        runner_up = sorted_evals[1] if len(sorted_evals) > 1 else None

        notes = []

        # Header with recommendation
        notes.append(f"{best['name']} (score: {best['recommendation_score']:.0f})")
        if runner_up:
            notes.append(f" outperformed {runner_up['name']} (score: {runner_up['recommendation_score']:.0f})")
        notes.append(f" over the last {best.get('lookback_days', 90)} days.\n\n")

        # Performance comparison
        notes.append(f"{best['name']} delivered {best['total_return_pct']:.1f}% return ")
        notes.append(f"with {best['sharpe_ratio']:.2f} Sharpe ratio")
        if runner_up:
            notes.append(f" vs {runner_up['name']}'s {runner_up['total_return_pct']:.1f}% return ")
            notes.append(f"with {runner_up['sharpe_ratio']:.2f} Sharpe.")
        else:
            notes.append(".")

        # Recommendation
        notes.append("\n\n")
        if recommended_id == current_active_id:
            notes.append(f"Recommendation: Keep {best['name']} active.")
        else:
            current_name = next((e['name'] for e in evaluations if e['strategy_id'] == current_active_id), "current strategy")
            score_diff = best['recommendation_score'] - next(
                (e['recommendation_score'] for e in evaluations if e['strategy_id'] == current_active_id),
                0
            )
            if score_diff > 10:
                notes.append(f"Recommendation: Switch from {current_name} to {best['name']} (+{score_diff:.0f} points).")
            else:
                notes.append(f"Recommendation: Consider switching to {best['name']}, but difference is marginal ({score_diff:.0f} points).")

        return "".join(notes)

    async def evaluate_strategy(
        self,
        strategy: StrategyDefinition,
        lookback_days: int = 90
    ) -> dict:
        """
        Run backtest for a single strategy

        Args:
            strategy: Strategy definition from DB
            lookback_days: Number of days to backtest

        Returns:
            Dict with performance metrics
        """
        # Parse parameters
        params = StrategyParams.from_json(strategy.parameters)

        # Create custom backtester with strategy parameters
        backtester = CustomBacktester()
        backtester.configure(params)

        # Run backtest
        try:
            # Debug: check data availability
            from app.services.scanner import scanner_service
            cache_size = len(scanner_service.data_cache)
            if cache_size == 0:
                raise RuntimeError(f"No data in scanner cache (cache_size={cache_size})")

            # Get top liquid symbols for faster analysis (100 for speed)
            top_symbols = get_top_liquid_symbols(max_symbols=100)

            # Check how many symbols have enough data
            min_data_points = lookback_days + 200
            symbols_with_enough_data = sum(
                1 for sym in top_symbols
                if sym in scanner_service.data_cache and len(scanner_service.data_cache[sym]) >= min_data_points
            )

            if symbols_with_enough_data == 0:
                # Get actual data lengths for debugging
                sample_lengths = {
                    sym: len(df) for sym, df in list(scanner_service.data_cache.items())[:5]
                }
                raise RuntimeError(
                    f"No symbols have {min_data_points}+ data points. "
                    f"Sample lengths: {sample_lengths}"
                )

            result = backtester.run_backtest(
                lookback_days=lookback_days,
                strategy_type=strategy.strategy_type,
                ticker_list=top_symbols if top_symbols else None
            )

            return {
                'strategy_id': strategy.id,
                'name': strategy.name,
                'strategy_type': strategy.strategy_type,
                'total_return_pct': result.total_return_pct,
                'sharpe_ratio': result.sharpe_ratio,
                'max_drawdown_pct': result.max_drawdown_pct,
                'win_rate': result.win_rate,
                'total_trades': result.total_trades,
                'lookback_days': lookback_days,
                'symbols_evaluated': symbols_with_enough_data,
                # Enhanced metrics
                'sortino_ratio': result.sortino_ratio,
                'calmar_ratio': result.calmar_ratio,
                'profit_factor': result.profit_factor,
                'avg_win_pct': result.avg_win_pct,
                'avg_loss_pct': result.avg_loss_pct,
                'win_loss_ratio': result.win_loss_ratio,
                'recovery_factor': result.recovery_factor,
                'max_consecutive_losses': result.max_consecutive_losses,
                'ulcer_index': result.ulcer_index,
            }
        except Exception as e:
            import traceback
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            print(f"Strategy evaluation error for {strategy.name}: {error_details}")
            return {
                'strategy_id': strategy.id,
                'name': strategy.name,
                'strategy_type': strategy.strategy_type,
                'error': str(e),
                'total_return_pct': 0,
                'sharpe_ratio': 0,
                'max_drawdown_pct': 0,
                'win_rate': 0,
                'total_trades': 0,
                'lookback_days': lookback_days
            }

    async def evaluate_all_strategies(
        self,
        db: AsyncSession,
        lookback_days: int = 90
    ) -> dict:
        """
        Evaluate all strategies and generate recommendations

        Args:
            db: Database session
            lookback_days: Number of days to backtest

        Returns:
            Dict with evaluations, recommendation, and notes
        """
        # Load all strategies
        result = await db.execute(
            select(StrategyDefinition).order_by(StrategyDefinition.id)
        )
        strategies = result.scalars().all()

        if not strategies:
            return {
                'evaluations': [],
                'recommended_strategy_id': None,
                'recommendation_notes': "No strategies found in database.",
                'current_active_strategy_id': None
            }

        # Find currently active strategy
        active_strategy = next((s for s in strategies if s.is_active), None)
        current_active_id = active_strategy.id if active_strategy else None

        # Evaluate each strategy
        evaluations = []
        for strategy in strategies:
            metrics = await self.evaluate_strategy(strategy, lookback_days)
            metrics['recommendation_score'] = self.calculate_recommendation_score(metrics)
            evaluations.append(metrics)

        # Find best strategy
        best_eval = max(evaluations, key=lambda x: x['recommendation_score'])
        recommended_id = best_eval['strategy_id']

        # Generate notes
        notes = self.generate_recommendation_notes(evaluations, recommended_id, current_active_id)

        # Save evaluations to database
        for eval_data in evaluations:
            db_eval = StrategyEvaluation(
                strategy_id=eval_data['strategy_id'],
                evaluation_date=datetime.utcnow(),
                lookback_days=lookback_days,
                total_return_pct=eval_data['total_return_pct'],
                sharpe_ratio=eval_data['sharpe_ratio'],
                max_drawdown_pct=eval_data['max_drawdown_pct'],
                win_rate=eval_data['win_rate'],
                total_trades=eval_data['total_trades'],
                recommendation_score=eval_data['recommendation_score'],
                recommendation_notes=notes if eval_data['strategy_id'] == recommended_id else None
            )
            db.add(db_eval)

        await db.commit()

        return {
            'analysis_date': datetime.utcnow().isoformat(),
            'lookback_days': lookback_days,
            'evaluations': evaluations,
            'recommended_strategy_id': recommended_id,
            'recommendation_notes': notes,
            'current_active_strategy_id': current_active_id
        }

    async def get_latest_analysis(self, db: AsyncSession) -> Optional[dict]:
        """
        Get the most recent strategy analysis results

        Returns:
            Dict with latest evaluations or None if no analysis exists
        """
        # Get latest evaluation date
        result = await db.execute(
            select(StrategyEvaluation)
            .order_by(desc(StrategyEvaluation.evaluation_date))
            .limit(1)
        )
        latest = result.scalar_one_or_none()

        if not latest:
            return None

        # Get all evaluations from that date
        result = await db.execute(
            select(StrategyEvaluation)
            .where(StrategyEvaluation.evaluation_date == latest.evaluation_date)
        )
        evaluations = result.scalars().all()

        # Get strategy details
        strategy_ids = [e.strategy_id for e in evaluations]
        result = await db.execute(
            select(StrategyDefinition).where(StrategyDefinition.id.in_(strategy_ids))
        )
        strategies = {s.id: s for s in result.scalars().all()}

        # Find active strategy
        result = await db.execute(
            select(StrategyDefinition).where(StrategyDefinition.is_active == True)
        )
        active = result.scalar_one_or_none()

        # Build response
        eval_data = []
        recommended_id = None
        recommendation_notes = ""

        for e in evaluations:
            strategy = strategies.get(e.strategy_id)
            eval_dict = {
                'strategy_id': e.strategy_id,
                'name': strategy.name if strategy else f"Strategy {e.strategy_id}",
                'strategy_type': strategy.strategy_type if strategy else "unknown",
                'total_return_pct': e.total_return_pct,
                'sharpe_ratio': e.sharpe_ratio,
                'max_drawdown_pct': e.max_drawdown_pct,
                'win_rate': e.win_rate,
                'total_trades': e.total_trades,
                'recommendation_score': e.recommendation_score,
                'lookback_days': e.lookback_days
            }
            eval_data.append(eval_dict)

            if e.recommendation_notes:
                recommendation_notes = e.recommendation_notes
                recommended_id = e.strategy_id

        # If no recommendation notes found, determine recommended from scores
        if not recommended_id and eval_data:
            best = max(eval_data, key=lambda x: x['recommendation_score'])
            recommended_id = best['strategy_id']

        return {
            'analysis_date': latest.evaluation_date.isoformat(),
            'lookback_days': latest.lookback_days,
            'evaluations': eval_data,
            'recommended_strategy_id': recommended_id,
            'recommendation_notes': recommendation_notes,
            'current_active_strategy_id': active.id if active else None
        }


# Singleton instance
strategy_analyzer_service = StrategyAnalyzerService()
