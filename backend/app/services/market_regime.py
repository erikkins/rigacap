"""
Market Regime Detection Service

Detects market regimes based on multiple factors:
- SPY price vs moving averages
- VIX level and trend
- Market breadth
- Sector rotation

Provides regime-specific parameter recommendations for strategy optimization.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum


class RegimeType(str, Enum):
    """Market regime classifications"""
    STRONG_BULL = "strong_bull"      # Strong uptrend, low volatility
    WEAK_BULL = "weak_bull"          # Mild uptrend, moderate volatility
    ROTATING_BULL = "rotating_bull"  # Uptrend with sector rotation, event-driven vol
    RANGE_BOUND = "range_bound"      # True sideways, no long-term trend
    WEAK_BEAR = "weak_bear"          # Mild downtrend, elevated volatility
    PANIC_CRASH = "panic_crash"      # Sharp decline, high volatility
    RECOVERY = "recovery"            # Bouncing from lows, falling volatility


@dataclass
class MarketConditions:
    """Raw market condition indicators"""
    date: str
    spy_price: float
    spy_vs_200ma_pct: float      # % above/below 200MA
    spy_vs_50ma_pct: float       # % above/below 50MA
    spy_vs_20ma_pct: float       # % above/below 20MA
    vix_level: float             # Current VIX (or estimated volatility)
    vix_percentile: float        # VIX vs 1-year range (0-100)
    trend_strength: float        # Short-term momentum (-100 to +100)
    long_term_trend: float       # 252-day (1-year) SPY return
    breadth_pct: float           # % of universe above 50MA
    new_highs_pct: float         # % of universe at 52-week highs
    spy_20d_return: float        # 20-day SPY return
    spy_60d_return: float        # 60-day SPY return
    spy_ma_200: float = 0.0      # 200-day MA value
    spy_ma_50: float = 0.0       # 50-day MA value
    spy_pct_from_high: float = 0.0  # % from 52-week high


@dataclass
class MarketRegime:
    """Classified market regime with recommendations"""
    date: str
    regime_type: RegimeType
    regime_name: str
    risk_level: str              # "low", "medium", "high", "extreme"
    confidence: float            # 0-100 confidence score
    conditions: MarketConditions
    param_adjustments: Dict      # Suggested parameter changes
    scoring_weights: Dict        # Metric weights for this regime
    description: str             # Human-readable description

    def to_dict(self):
        regime_def = REGIME_DEFINITIONS.get(self.regime_type, {})
        return {
            **asdict(self),
            'regime_type': self.regime_type.value,
            'conditions': asdict(self.conditions),
            'color': regime_def.get('color', '#6B7280'),
            'bg_color': regime_def.get('bg_color', 'rgba(107, 114, 128, 0.1)')
        }


# Regime definitions with condition ranges and recommendations
REGIME_DEFINITIONS = {
    RegimeType.STRONG_BULL: {
        "name": "Strong Bull",
        "description": "Strong uptrend with low volatility. Favor momentum, let winners run.",
        "conditions": {
            "spy_vs_200ma_pct": (5, 100),
            "spy_vs_50ma_pct": (0, 100),
            "vix_percentile": (0, 40),
            "trend_strength": (20, 100),
            "long_term_trend": (10, 100),     # Strong 1-year gains
        },
        "risk_level": "low",
        "param_adjustments": {
            "trailing_stop_pct": -2,
            "max_positions": +1,
            "position_size_pct": +2,
        },
        "scoring_weights": {
            "sharpe_ratio": 0.25,
            "total_return": 0.35,
            "max_drawdown": 0.15,
            "sortino_ratio": 0.15,
            "profit_factor": 0.10,
        },
        "color": "#10B981",
        "bg_color": "rgba(16, 185, 129, 0.1)"
    },
    RegimeType.WEAK_BULL: {
        "name": "Weak Bull",
        "description": "Mild uptrend with moderate volatility. Balance risk and reward.",
        "conditions": {
            "spy_vs_200ma_pct": (0, 10),
            "spy_vs_50ma_pct": (-5, 10),
            "vix_percentile": (20, 50),
            "trend_strength": (5, 30),
            "long_term_trend": (5, 20),
        },
        "risk_level": "medium",
        "param_adjustments": {},
        "scoring_weights": {
            "sharpe_ratio": 0.30,
            "total_return": 0.25,
            "max_drawdown": 0.20,
            "sortino_ratio": 0.15,
            "profit_factor": 0.10,
        },
        "color": "#84CC16",
        "bg_color": "rgba(132, 204, 22, 0.1)"
    },
    RegimeType.ROTATING_BULL: {
        "name": "Rotating Bull",
        "description": "Uptrend with sector rotation and event-driven volatility. Stay invested but diversify.",
        "conditions": {
            "spy_vs_200ma_pct": (-3, 15),       # Near or above 200MA
            "long_term_trend": (5, 100),        # Positive 1-year return (key!)
            "trend_strength": (-20, 20),        # Choppy short-term (rotation)
            "vix_percentile": (30, 70),         # Elevated but not extreme vol
            "new_highs_pct": (5, 40),           # Some stocks making new highs
            "breadth_pct": (40, 70),            # Mixed breadth (rotation)
        },
        "risk_level": "medium",
        "param_adjustments": {
            "max_positions": 0,                 # Keep normal position count
            "trailing_stop_pct": +1,            # Slightly wider stops for rotation
        },
        "scoring_weights": {
            "sharpe_ratio": 0.25,
            "total_return": 0.30,
            "max_drawdown": 0.20,
            "sortino_ratio": 0.15,
            "profit_factor": 0.10,
        },
        "color": "#8B5CF6",                     # Purple - distinct from other bulls
        "bg_color": "rgba(139, 92, 246, 0.1)"
    },
    RegimeType.RANGE_BOUND: {
        "name": "Range-Bound",
        "description": "True sideways market with no long-term trend. Favor mean reversion.",
        "conditions": {
            "spy_vs_200ma_pct": (-5, 5),
            "spy_vs_50ma_pct": (-5, 5),
            "long_term_trend": (-10, 10),       # Flat 1-year return (key!)
            "vix_percentile": (20, 50),
            "trend_strength": (-15, 15),
        },
        "risk_level": "medium",
        "param_adjustments": {
            "max_positions": -1,
            "near_50d_high_pct": +3,
            "profit_target_pct": -5,
        },
        "scoring_weights": {
            "sharpe_ratio": 0.35,
            "total_return": 0.15,
            "max_drawdown": 0.20,
            "sortino_ratio": 0.20,
            "profit_factor": 0.10,
        },
        "color": "#F59E0B",
        "bg_color": "rgba(245, 158, 11, 0.1)"
    },
    RegimeType.WEAK_BEAR: {
        "name": "Weak Bear",
        "description": "Mild downtrend with elevated volatility. Reduce exposure, tighter risk.",
        "conditions": {
            "spy_vs_200ma_pct": (-15, 0),
            "spy_vs_50ma_pct": (-10, 0),
            "vix_percentile": (40, 70),
            "trend_strength": (-30, -5),
            "long_term_trend": (-20, 10),     # Flat or negative 1-year
        },
        "risk_level": "high",
        "param_adjustments": {
            "trailing_stop_pct": +3,
            "max_positions": -2,
            "position_size_pct": -3,
        },
        "scoring_weights": {
            "sharpe_ratio": 0.20,
            "total_return": 0.15,
            "max_drawdown": 0.35,
            "sortino_ratio": 0.20,
            "profit_factor": 0.10,
        },
        "color": "#F97316",
        "bg_color": "rgba(249, 115, 22, 0.1)"
    },
    RegimeType.PANIC_CRASH: {
        "name": "Panic/Crash",
        "description": "Sharp decline with extreme volatility. Preserve capital, go to cash.",
        "conditions": {
            "spy_vs_200ma_pct": (-100, -10),
            "vix_percentile": (70, 100),
            "trend_strength": (-100, -30),
        },
        "risk_level": "extreme",
        "param_adjustments": {
            "trailing_stop_pct": +5,
            "max_positions": -3,
            "position_size_pct": -5,
        },
        "scoring_weights": {
            "sharpe_ratio": 0.15,
            "total_return": 0.10,
            "max_drawdown": 0.40,
            "sortino_ratio": 0.25,
            "profit_factor": 0.10,
        },
        "color": "#EF4444",
        "bg_color": "rgba(239, 68, 68, 0.15)"
    },
    RegimeType.RECOVERY: {
        "name": "Recovery",
        "description": "Bouncing from lows. Opportunity for early entry, but stay cautious.",
        "conditions": {
            "spy_vs_200ma_pct": (-10, 5),
            "spy_vs_50ma_pct": (0, 15),
            "vix_percentile": (40, 70),
            "trend_strength": (10, 40),
            "spy_20d_return": (5, 30),
        },
        "risk_level": "medium",
        "param_adjustments": {
            "trailing_stop_pct": +2,
            "near_50d_high_pct": -2,
        },
        "scoring_weights": {
            "sharpe_ratio": 0.25,
            "total_return": 0.30,
            "max_drawdown": 0.20,
            "sortino_ratio": 0.15,
            "profit_factor": 0.10,
        },
        "color": "#06B6D4",
        "bg_color": "rgba(6, 182, 212, 0.1)"
    }
}


@dataclass
class RegimeForecast:
    """Regime transition forecast with recommended actions."""
    current_regime: str              # Current regime type value
    current_regime_name: str         # Human-readable name
    transition_probabilities: Dict[str, float]  # regime_name → probability (0-100)
    outlook: str                     # "stable", "deteriorating", "improving"
    outlook_detail: str              # Human-readable explanation
    risk_change: str                 # "increasing", "stable", "decreasing"
    recommended_action: str          # "stay_invested", "tighten_stops", "reduce_exposure", "go_to_cash"

    def to_dict(self):
        return asdict(self)


class MarketRegimeService:
    """Detects and tracks market regimes over time."""

    # A new regime must outscore the current regime by this margin to trigger
    # a switch. Prevents noisy flipping at regime boundaries.
    HYSTERESIS_THRESHOLD = 8  # points on 0-100 scale

    def __init__(self):
        self._cache: Dict[str, MarketRegime] = {}
        self._regime_history: List[MarketRegime] = []
        self._current_regime_type: Optional[object] = None  # sticky regime for hysteresis
        self._last_detected_regime: Optional[MarketRegime] = None

    def get_current_regime(self) -> Optional[MarketRegime]:
        """Return the most recently detected MarketRegime from cache.
        predict_transitions() / detect_regime() must be called first."""
        return self._last_detected_regime

    def calculate_conditions(
        self,
        spy_df: pd.DataFrame,
        universe_dfs: Optional[Dict[str, pd.DataFrame]] = None,
        vix_df: Optional[pd.DataFrame] = None,
        as_of_date: Optional[datetime] = None
    ) -> MarketConditions:
        """Calculate market condition indicators for a given date."""
        if as_of_date:
            # Align as_of_ts to spy_df's index tz semantics. Pandas (newer
            # versions, AL2023 stack) raises TypeError on tz-naive vs tz-aware
            # comparison. as_of_date arrives tz-aware from cron callers; pickle
            # SPY index is typically tz-naive — handle both directions.
            as_of_ts = pd.Timestamp(as_of_date)
            if spy_df.index.tz is not None:
                as_of_ts = as_of_ts.tz_localize(spy_df.index.tz) if as_of_ts.tz is None else as_of_ts.tz_convert(spy_df.index.tz)
            elif as_of_ts.tz is not None:
                as_of_ts = as_of_ts.tz_localize(None)
            spy_df = spy_df[spy_df.index <= as_of_ts]

        if len(spy_df) < 200:
            raise ValueError("Need at least 200 days of SPY data")

        latest = spy_df.iloc[-1]
        spy_price = latest['close']
        date_str = spy_df.index[-1].strftime('%Y-%m-%d')

        ma_20 = spy_df['close'].tail(20).mean()
        ma_50 = spy_df['close'].tail(50).mean()
        ma_200 = spy_df['close'].tail(200).mean()

        spy_vs_20ma = (spy_price / ma_20 - 1) * 100
        spy_vs_50ma = (spy_price / ma_50 - 1) * 100
        spy_vs_200ma = (spy_price / ma_200 - 1) * 100

        # Short-term momentum
        spy_20d_return = (spy_price / spy_df.iloc[-20]['close'] - 1) * 100 if len(spy_df) >= 20 else 0
        spy_60d_return = (spy_price / spy_df.iloc[-60]['close'] - 1) * 100 if len(spy_df) >= 60 else 0
        trend_strength = spy_20d_return * 2  # Short-term momentum score

        # Long-term trend (1-year return) - KEY for detecting rotating bull vs range
        spy_252d_return = 0.0
        if len(spy_df) >= 252:
            spy_252d_return = (spy_price / spy_df.iloc[-252]['close'] - 1) * 100

        # 52-week high calculation for SPY
        spy_52w_high = spy_df['close'].tail(252).max() if len(spy_df) >= 252 else spy_df['close'].max()
        spy_pct_from_high = ((spy_price / spy_52w_high) - 1) * 100

        if vix_df is not None and len(vix_df) > 0:
            if as_of_date:
                vix_ts = pd.Timestamp(as_of_date)
                if vix_df.index.tz is not None:
                    vix_ts = vix_ts.tz_localize(vix_df.index.tz) if vix_ts.tz is None else vix_ts.tz_convert(vix_df.index.tz)
                elif vix_ts.tz is not None:
                    vix_ts = vix_ts.tz_localize(None)
                vix_df = vix_df[vix_df.index <= vix_ts]
            vix_level = vix_df.iloc[-1]['close'] if len(vix_df) > 0 else 20
            vix_1y = vix_df['close'].tail(252)
            vix_percentile = (vix_level <= vix_1y).sum() / len(vix_1y) * 100
        else:
            spy_returns = spy_df['close'].pct_change().tail(20)
            implied_vix = spy_returns.std() * np.sqrt(252) * 100
            vix_level = implied_vix
            hist_vol = spy_df['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            vix_percentile = (implied_vix <= hist_vol.tail(252)).sum() / min(252, len(hist_vol)) * 100

        # Market breadth and new highs
        breadth_pct = 50.0
        new_highs_pct = 10.0  # Default
        if universe_dfs:
            above_50ma_count = 0
            new_highs_count = 0
            total_count = 0
            for symbol, df in universe_dfs.items():
                if symbol in ['SPY', '^VIX']:
                    continue
                if as_of_date:
                    sym_ts = pd.Timestamp(as_of_date)
                    if df.index.tz is not None:
                        sym_ts = sym_ts.tz_localize(df.index.tz) if sym_ts.tz is None else sym_ts.tz_convert(df.index.tz)
                    elif sym_ts.tz is not None:
                        sym_ts = sym_ts.tz_localize(None)
                    df = df[df.index <= sym_ts]
                if len(df) >= 252:
                    latest_price = df.iloc[-1]['close']
                    ma_50_sym = df['close'].tail(50).mean()
                    high_52w = df['close'].tail(252).max()

                    if latest_price > ma_50_sym:
                        above_50ma_count += 1
                    # Within 2% of 52-week high = making new highs
                    if latest_price >= high_52w * 0.98:
                        new_highs_count += 1
                    total_count += 1
                elif len(df) >= 50:
                    latest_price = df.iloc[-1]['close']
                    ma_50_sym = df['close'].tail(50).mean()
                    if latest_price > ma_50_sym:
                        above_50ma_count += 1
                    total_count += 1

            if total_count > 0:
                breadth_pct = (above_50ma_count / total_count) * 100
                new_highs_pct = (new_highs_count / total_count) * 100

        return MarketConditions(
            date=date_str,
            spy_price=round(spy_price, 2),
            spy_vs_200ma_pct=round(spy_vs_200ma, 2),
            spy_vs_50ma_pct=round(spy_vs_50ma, 2),
            spy_vs_20ma_pct=round(spy_vs_20ma, 2),
            vix_level=round(vix_level, 2),
            vix_percentile=round(vix_percentile, 1),
            trend_strength=round(trend_strength, 1),
            long_term_trend=round(spy_252d_return, 1),
            breadth_pct=round(breadth_pct, 1),
            new_highs_pct=round(new_highs_pct, 1),
            spy_20d_return=round(spy_20d_return, 2),
            spy_60d_return=round(spy_60d_return, 2),
            spy_ma_200=round(ma_200, 2),
            spy_ma_50=round(ma_50, 2),
            spy_pct_from_high=round(spy_pct_from_high, 2)
        )

    def _score_regime_match(self, conditions: MarketConditions, regime_def: Dict) -> float:
        """Score how well current conditions match a regime definition."""
        required_conditions = regime_def.get("conditions", {})
        if not required_conditions:
            return 0

        scores = []
        condition_values = {
            "spy_vs_200ma_pct": conditions.spy_vs_200ma_pct,
            "spy_vs_50ma_pct": conditions.spy_vs_50ma_pct,
            "spy_vs_20ma_pct": conditions.spy_vs_20ma_pct,
            "vix_percentile": conditions.vix_percentile,
            "trend_strength": conditions.trend_strength,
            "long_term_trend": conditions.long_term_trend,
            "breadth_pct": conditions.breadth_pct,
            "new_highs_pct": conditions.new_highs_pct,
            "spy_20d_return": conditions.spy_20d_return,
        }

        # Weight certain conditions more heavily
        # Long-term trend is THE key differentiator between rotating bull and range-bound
        condition_weights = {
            "long_term_trend": 2.5,  # Long-term trend is critical for bull vs range
            "spy_vs_200ma_pct": 1.5,
            "new_highs_pct": 1.5,
            "breadth_pct": 1.2,
        }

        for cond_name, (min_val, max_val) in required_conditions.items():
            actual = condition_values.get(cond_name)
            if actual is None:
                continue

            if min_val <= actual <= max_val:
                # Inside range = full score (100)
                # Only use center-distance for narrow ranges (<30 units)
                range_size = max_val - min_val
                if range_size < 30:
                    # Narrow range: prefer center
                    center = (min_val + max_val) / 2
                    dist_from_center = abs(actual - center)
                    score = 100 * (1 - dist_from_center / (range_size / 2) * 0.3)
                else:
                    # Wide range: full credit for being inside
                    score = 100
            else:
                # Penalty for being outside range - aggressive (10 per unit)
                if actual < min_val:
                    dist = min_val - actual
                else:
                    dist = actual - max_val
                score = max(0, 100 - dist * 10)

            # Apply weight
            weight = condition_weights.get(cond_name, 1.0)
            scores.append(score * weight)

        # Normalize by total weight
        if scores:
            total_weight = sum(condition_weights.get(c, 1.0) for c in required_conditions.keys() if c in condition_values)
            return sum(scores) / total_weight if total_weight > 0 else np.mean(scores)
        return 0

    def detect_regime(
        self,
        spy_df: pd.DataFrame,
        universe_dfs: Optional[Dict[str, pd.DataFrame]] = None,
        vix_df: Optional[pd.DataFrame] = None,
        as_of_date: Optional[datetime] = None
    ) -> MarketRegime:
        """Detect the current market regime with hysteresis to prevent noisy flipping."""
        conditions = self.calculate_conditions(spy_df, universe_dfs, vix_df, as_of_date)

        regime_scores = {}
        for regime_type, regime_def in REGIME_DEFINITIONS.items():
            score = self._score_regime_match(conditions, regime_def)
            regime_scores[regime_type] = score

        best_regime = max(regime_scores, key=regime_scores.get)
        best_score = regime_scores[best_regime]

        # Hysteresis: stick with current regime unless new one wins by a margin
        if self._current_regime_type is not None and best_regime != self._current_regime_type:
            current_score = regime_scores.get(self._current_regime_type, 0)
            if best_score - current_score < self.HYSTERESIS_THRESHOLD:
                # Not enough margin — stay with current regime
                best_regime = self._current_regime_type
                best_score = current_score

        self._current_regime_type = best_regime
        regime_def = REGIME_DEFINITIONS[best_regime]

        regime = MarketRegime(
            date=conditions.date,
            regime_type=best_regime,
            regime_name=regime_def["name"],
            risk_level=regime_def["risk_level"],
            confidence=round(best_score, 1),
            conditions=conditions,
            param_adjustments=regime_def["param_adjustments"],
            scoring_weights=regime_def["scoring_weights"],
            description=regime_def["description"]
        )

        self._cache[conditions.date] = regime
        self._last_detected_regime = regime
        return regime

    def predict_transitions(
        self,
        spy_df: pd.DataFrame,
        universe_dfs: Optional[Dict[str, pd.DataFrame]] = None,
        vix_df: Optional[pd.DataFrame] = None,
        as_of_date: Optional[datetime] = None
    ) -> RegimeForecast:
        """
        Predict regime transitions using current scores + indicator trajectory.

        Combines the existing regime scoring with momentum/trajectory of key
        indicators to estimate where the market is heading.
        """
        # Get current regime and conditions
        regime = self.detect_regime(spy_df, universe_dfs, vix_df, as_of_date)
        conditions = regime.conditions

        # Score all regimes (raw scores)
        regime_scores = {}
        for regime_type, regime_def in REGIME_DEFINITIONS.items():
            score = self._score_regime_match(conditions, regime_def)
            regime_scores[regime_type] = max(score, 0)

        # Calculate indicator trajectories from SPY data
        if as_of_date:
            as_of_ts = pd.Timestamp(as_of_date)
            if spy_df.index.tz is not None:
                as_of_ts = as_of_ts.tz_localize(spy_df.index.tz) if as_of_ts.tz is None else as_of_ts.tz_convert(spy_df.index.tz)
            elif as_of_ts.tz is not None:
                as_of_ts = as_of_ts.tz_localize(None)
            spy_slice = spy_df[spy_df.index <= as_of_ts]
        else:
            spy_slice = spy_df

        trajectory = self._compute_trajectory(spy_slice, vix_df, as_of_date)

        # Adjust scores based on trajectory
        adjusted_scores = self._adjust_scores_by_trajectory(regime_scores, trajectory)

        # Normalize to probabilities (sum to 100)
        total = sum(adjusted_scores.values())
        if total > 0:
            probabilities = {
                rt.value: round(s / total * 100, 1)
                for rt, s in adjusted_scores.items()
            }
        else:
            probabilities = {rt.value: round(100 / len(adjusted_scores), 1) for rt in adjusted_scores}

        # Determine outlook
        outlook, outlook_detail = self._determine_outlook(
            regime.regime_type, probabilities, trajectory, conditions
        )

        # Determine risk change
        risk_change = self._determine_risk_change(trajectory)

        # Determine recommended action
        recommended_action = self._determine_recommended_action(
            regime.regime_type, probabilities, outlook, risk_change
        )

        return RegimeForecast(
            current_regime=regime.regime_type.value,
            current_regime_name=regime.regime_name,
            transition_probabilities=probabilities,
            outlook=outlook,
            outlook_detail=outlook_detail,
            risk_change=risk_change,
            recommended_action=recommended_action
        )

    def _compute_trajectory(
        self,
        spy_df: pd.DataFrame,
        vix_df: Optional[pd.DataFrame] = None,
        as_of_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Compute indicator deltas over recent periods."""
        if len(spy_df) < 30:
            return {}

        close = spy_df['close']

        # VIX trajectory
        vix_delta_5d = 0.0
        if vix_df is not None and len(vix_df) >= 10:
            if as_of_date:
                vix_ts = pd.Timestamp(as_of_date)
                if vix_df.index.tz is not None:
                    vix_ts = vix_ts.tz_localize(vix_df.index.tz) if vix_ts.tz is None else vix_ts.tz_convert(vix_df.index.tz)
                vix_slice = vix_df[vix_df.index <= vix_ts]
            else:
                vix_slice = vix_df
            if len(vix_slice) >= 6:
                vix_now = vix_slice['close'].iloc[-1]
                vix_5d_ago = vix_slice['close'].iloc[-6]
                vix_delta_5d = vix_now - vix_5d_ago
        else:
            # Use realized vol as proxy
            vol_now = close.pct_change().tail(5).std() * np.sqrt(252) * 100
            vol_prev = close.pct_change().iloc[-11:-6].std() * np.sqrt(252) * 100
            vix_delta_5d = vol_now - vol_prev if not np.isnan(vol_now) and not np.isnan(vol_prev) else 0

        # SPY trend acceleration: is the trend strengthening or weakening?
        ret_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0
        ret_10d = (close.iloc[-1] / close.iloc[-11] - 1) * 100 if len(close) >= 11 else 0
        ret_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0
        # Acceleration: recent momentum stronger or weaker than prior?
        trend_acceleration = ret_5d - (ret_10d - ret_5d) if len(close) >= 11 else 0

        # Distance to 200MA (how close to regime boundary)
        ma_200 = close.tail(200).mean() if len(close) >= 200 else close.mean()
        spy_distance_to_200ma = (close.iloc[-1] / ma_200 - 1) * 100

        # Breadth delta (approximate with SPY internals)
        breadth_delta_10d = ret_10d  # Simplified: SPY return as breadth proxy

        return {
            'vix_delta_5d': round(vix_delta_5d, 2),
            'trend_acceleration': round(trend_acceleration, 2),
            'spy_distance_to_200ma': round(spy_distance_to_200ma, 2),
            'breadth_delta_10d': round(breadth_delta_10d, 2),
            'ret_5d': round(ret_5d, 2),
            'ret_20d': round(ret_20d, 2),
        }

    def _adjust_scores_by_trajectory(
        self,
        raw_scores: Dict[RegimeType, float],
        trajectory: Dict[str, float]
    ) -> Dict[RegimeType, float]:
        """Adjust regime scores based on where indicators are heading."""
        adjusted = dict(raw_scores)
        if not trajectory:
            return adjusted

        vix_delta = trajectory.get('vix_delta_5d', 0)
        trend_accel = trajectory.get('trend_acceleration', 0)
        dist_200ma = trajectory.get('spy_distance_to_200ma', 0)
        ret_5d = trajectory.get('ret_5d', 0)

        # Rising VIX → boost bearish regimes
        if vix_delta > 2:
            boost = min(vix_delta * 5, 25)
            adjusted[RegimeType.WEAK_BEAR] = adjusted.get(RegimeType.WEAK_BEAR, 0) + boost
            adjusted[RegimeType.PANIC_CRASH] = adjusted.get(RegimeType.PANIC_CRASH, 0) + boost * 0.5
            adjusted[RegimeType.STRONG_BULL] = max(0, adjusted.get(RegimeType.STRONG_BULL, 0) - boost * 0.5)

        # Falling VIX → boost bullish regimes
        if vix_delta < -2:
            boost = min(abs(vix_delta) * 5, 25)
            adjusted[RegimeType.STRONG_BULL] = adjusted.get(RegimeType.STRONG_BULL, 0) + boost
            adjusted[RegimeType.RECOVERY] = adjusted.get(RegimeType.RECOVERY, 0) + boost * 0.5

        # Negative trend acceleration → market weakening
        if trend_accel < -2:
            boost = min(abs(trend_accel) * 3, 20)
            adjusted[RegimeType.WEAK_BEAR] = adjusted.get(RegimeType.WEAK_BEAR, 0) + boost
            adjusted[RegimeType.RANGE_BOUND] = adjusted.get(RegimeType.RANGE_BOUND, 0) + boost * 0.5

        # Positive trend acceleration → market strengthening
        if trend_accel > 2:
            boost = min(trend_accel * 3, 20)
            adjusted[RegimeType.STRONG_BULL] = adjusted.get(RegimeType.STRONG_BULL, 0) + boost

        # Near 200MA boundary (within 2%) → higher transition uncertainty
        if abs(dist_200ma) < 2:
            if ret_5d < 0:
                adjusted[RegimeType.WEAK_BEAR] = adjusted.get(RegimeType.WEAK_BEAR, 0) + 15
            else:
                adjusted[RegimeType.RECOVERY] = adjusted.get(RegimeType.RECOVERY, 0) + 10

        # Sharp recent drop → boost crash/recovery
        if ret_5d < -5:
            adjusted[RegimeType.PANIC_CRASH] = adjusted.get(RegimeType.PANIC_CRASH, 0) + 20
        elif ret_5d > 5:
            adjusted[RegimeType.RECOVERY] = adjusted.get(RegimeType.RECOVERY, 0) + 15

        return adjusted

    def _determine_outlook(
        self,
        current_regime: RegimeType,
        probabilities: Dict[str, float],
        trajectory: Dict[str, float],
        conditions: MarketConditions
    ) -> Tuple[str, str]:
        """Determine overall market outlook."""
        bullish_regimes = ['strong_bull', 'weak_bull', 'rotating_bull', 'recovery']
        bearish_regimes = ['weak_bear', 'panic_crash']

        bullish_prob = sum(probabilities.get(r, 0) for r in bullish_regimes)
        bearish_prob = sum(probabilities.get(r, 0) for r in bearish_regimes)

        vix_delta = trajectory.get('vix_delta_5d', 0)
        trend_accel = trajectory.get('trend_acceleration', 0)

        details = []
        if vix_delta > 3:
            details.append("VIX rising")
        elif vix_delta < -3:
            details.append("VIX falling")

        if trend_accel < -2:
            details.append("momentum weakening")
        elif trend_accel > 2:
            details.append("momentum strengthening")

        current_is_bullish = current_regime.value in bullish_regimes

        if current_is_bullish and bearish_prob > 30:
            outlook = "deteriorating"
            top_risk = max(bearish_regimes, key=lambda r: probabilities.get(r, 0))
            risk_name = top_risk.replace('_', ' ').title()
            risk_pct = probabilities.get(top_risk, 0)
            detail_str = ", ".join(details) if details else "indicators shifting"
            detail = f"{detail_str} — {risk_pct:.0f}% chance of {risk_name} in 1-2 weeks"
        elif not current_is_bullish and bullish_prob > 50:
            outlook = "improving"
            top_bull = max(bullish_regimes, key=lambda r: probabilities.get(r, 0))
            bull_name = top_bull.replace('_', ' ').title()
            bull_pct = probabilities.get(top_bull, 0)
            detail_str = ", ".join(details) if details else "conditions easing"
            detail = f"{detail_str} — {bull_pct:.0f}% chance of {bull_name} in 1-2 weeks"
        else:
            outlook = "stable"
            current_prob = probabilities.get(current_regime.value, 0)
            detail_str = ", ".join(details) if details else "no significant shifts detected"
            detail = f"{detail_str} — {current_prob:.0f}% chance regime holds"

        return outlook, detail

    def _determine_risk_change(self, trajectory: Dict[str, float]) -> str:
        """Determine if risk is increasing, stable, or decreasing."""
        if not trajectory:
            return "stable"

        vix_delta = trajectory.get('vix_delta_5d', 0)
        trend_accel = trajectory.get('trend_acceleration', 0)
        ret_5d = trajectory.get('ret_5d', 0)

        risk_score = 0
        if vix_delta > 2:
            risk_score += 1
        elif vix_delta < -2:
            risk_score -= 1
        if trend_accel < -2:
            risk_score += 1
        elif trend_accel > 2:
            risk_score -= 1
        if ret_5d < -3:
            risk_score += 1
        elif ret_5d > 3:
            risk_score -= 1

        if risk_score >= 2:
            return "increasing"
        elif risk_score <= -2:
            return "decreasing"
        return "stable"

    def _determine_recommended_action(
        self,
        current_regime: RegimeType,
        probabilities: Dict[str, float],
        outlook: str,
        risk_change: str
    ) -> str:
        """Determine recommended portfolio action."""
        panic_prob = probabilities.get('panic_crash', 0)
        weak_bear_prob = probabilities.get('weak_bear', 0)
        bearish_total = panic_prob + weak_bear_prob

        # Go to cash if in panic or high crash probability
        if current_regime == RegimeType.PANIC_CRASH or panic_prob > 30:
            return "go_to_cash"

        # Reduce exposure if in bear or high bearish probability
        if current_regime == RegimeType.WEAK_BEAR or bearish_total > 50:
            return "reduce_exposure"

        # Tighten stops if outlook deteriorating
        if outlook == "deteriorating" or risk_change == "increasing":
            return "tighten_stops"

        return "stay_invested"

    def get_regime_history(
        self,
        spy_df: pd.DataFrame,
        universe_dfs: Optional[Dict[str, pd.DataFrame]] = None,
        vix_df: Optional[pd.DataFrame] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sample_frequency: str = 'weekly'
    ) -> List[MarketRegime]:
        """Get regime classification history over a date range."""
        if start_date:
            start_ts = pd.Timestamp(start_date)
            if spy_df.index.tz is not None:
                start_ts = start_ts.tz_localize(spy_df.index.tz) if start_ts.tz is None else start_ts.tz_convert(spy_df.index.tz)
            spy_df = spy_df[spy_df.index >= start_ts]
        if end_date:
            end_ts = pd.Timestamp(end_date)
            if spy_df.index.tz is not None:
                end_ts = end_ts.tz_localize(spy_df.index.tz) if end_ts.tz is None else end_ts.tz_convert(spy_df.index.tz)
            spy_df = spy_df[spy_df.index <= end_ts]

        if sample_frequency == 'daily':
            dates = spy_df.index.tolist()
        elif sample_frequency == 'weekly':
            dates = spy_df.resample('W-FRI').last().dropna().index.tolist()
        else:
            dates = spy_df.resample('M').last().dropna().index.tolist()

        history = []
        for date in dates:
            try:
                regime = self.detect_regime(spy_df, universe_dfs, vix_df, as_of_date=date)
                history.append(regime)
            except Exception:
                continue

        self._regime_history = history
        return history

    def get_regime_changes(self, history: Optional[List[MarketRegime]] = None) -> List[Dict]:
        """Extract regime change points from history."""
        if history is None:
            history = self._regime_history

        if not history or len(history) < 2:
            return []

        changes = []
        prev_regime = history[0]

        for regime in history[1:]:
            if regime.regime_type != prev_regime.regime_type:
                changes.append({
                    "date": regime.date,
                    "from_regime": prev_regime.regime_type.value,
                    "from_name": prev_regime.regime_name,
                    "to_regime": regime.regime_type.value,
                    "to_name": regime.regime_name,
                    "from_color": REGIME_DEFINITIONS[prev_regime.regime_type]["color"],
                    "to_color": REGIME_DEFINITIONS[regime.regime_type]["color"]
                })
            prev_regime = regime

        return changes

    def get_regime_periods(self, history: Optional[List[MarketRegime]] = None) -> List[Dict]:
        """Get list of regime periods with start/end dates for chart backgrounds."""
        if history is None:
            history = self._regime_history

        if not history:
            return []

        periods = []
        current_period = {
            "start_date": history[0].date,
            "regime_type": history[0].regime_type.value,
            "regime_name": history[0].regime_name,
            "color": REGIME_DEFINITIONS[history[0].regime_type]["color"],
            "bg_color": REGIME_DEFINITIONS[history[0].regime_type]["bg_color"]
        }

        for regime in history[1:]:
            if regime.regime_type.value != current_period["regime_type"]:
                current_period["end_date"] = regime.date
                periods.append(current_period)
                current_period = {
                    "start_date": regime.date,
                    "regime_type": regime.regime_type.value,
                    "regime_name": regime.regime_name,
                    "color": REGIME_DEFINITIONS[regime.regime_type]["color"],
                    "bg_color": REGIME_DEFINITIONS[regime.regime_type]["bg_color"]
                }
            else:
                current_period["end_date"] = regime.date

        if history:
            current_period["end_date"] = history[-1].date
            periods.append(current_period)

        return periods


# Singleton instance
market_regime_service = MarketRegimeService()


def get_regime_adjusted_params(regime: MarketRegime) -> dict:
    """
    Apply regime param_adjustments offsets to base config values.

    Returns dict with:
      - 'effective': {param: adjusted_value} for each adjustable param
      - 'changes': list of {param, base, offset, effective, description} for non-zero offsets
      - 'regime_name': current regime name
      - 'risk_level': current risk level
    """
    from app.core.config import settings

    # Base values from global config
    base_params = {
        'trailing_stop_pct': settings.TRAILING_STOP_PCT,
        'near_50d_high_pct': settings.NEAR_50D_HIGH_PCT,
        'max_positions': settings.MAX_POSITIONS,
        'position_size_pct': settings.POSITION_SIZE_PCT,
    }

    # Safety bounds
    bounds = {
        'trailing_stop_pct': (5.0, 25.0),
        'near_50d_high_pct': (1.0, 15.0),
        'max_positions': (2, 10),
        'position_size_pct': (5.0, 30.0),
    }

    # Human-readable descriptions for each parameter change direction
    descriptions = {
        'trailing_stop_pct': {'+': 'widened', '-': 'tightened'},
        'near_50d_high_pct': {'+': 'relaxed', '-': 'tightened'},
        'max_positions': {'+': 'increased', '-': 'reduced'},
        'position_size_pct': {'+': 'increased', '-': 'reduced'},
    }

    labels = {
        'trailing_stop_pct': 'Trailing Stop',
        'near_50d_high_pct': 'Breakout Filter',
        'max_positions': 'Max Positions',
        'position_size_pct': 'Position Size',
    }

    adjustments = regime.param_adjustments or {}
    effective = {}
    changes = []

    for param, base_val in base_params.items():
        offset = adjustments.get(param, 0)
        adjusted = base_val + offset
        lo, hi = bounds[param]
        # Preserve int type for max_positions
        if isinstance(base_val, int):
            adjusted = int(max(lo, min(hi, adjusted)))
        else:
            adjusted = round(max(lo, min(hi, adjusted)), 1)
        effective[param] = adjusted

        if offset != 0:
            direction = '+' if offset > 0 else '-'
            desc_word = descriptions.get(param, {}).get(direction, 'adjusted')
            unit = '%' if 'pct' in param else ''
            sign = '+' if offset > 0 else ''
            changes.append({
                'param': param,
                'label': labels.get(param, param),
                'base': base_val,
                'offset': offset,
                'effective': adjusted,
                'description': f"{labels.get(param, param)} {desc_word} to {adjusted}{unit}",
            })

    return {
        'effective': effective,
        'changes': changes,
        'regime_name': regime.regime_name,
        'risk_level': regime.risk_level,
    }
