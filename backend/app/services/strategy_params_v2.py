"""
V2 Strategy Parameter Space Definitions + Indicator Helpers

Extends V1 with 7 new alpha levers:
1. Momentum lookback tuning (short_momentum_days, long_momentum_days)
2. Regime-conditional optimization (expanded constraints)
3. Entry timing signals (RSI filter, volume ratio threshold)
4. Exit strategy optimization (trailing vs hybrid vs time-capped)
5. Multi-objective Pareto (handled in optuna_optimizer_v2.py)
6. Lookback window tuning (optimization_lookback_days)
7. Sector rotation (sector_cap)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any


# === V2 Parameter Space Definitions ===

V2_PARAM_SPACES: Dict[str, Dict[str, Any]] = {
    "ensemble": {
        # --- V1 params (retained) ---
        "dwap_threshold_pct": {"low": 3.0, "high": 8.0, "step": 0.5},
        "trailing_stop_pct": {"low": 8.0, "high": 22.0, "step": 1.0},
        "max_positions": {"low": 3, "high": 8, "step": 1},
        "position_size_pct": {"low": 10.0, "high": 20.0, "step": 1.0},
        "near_50d_high_pct": {"low": 2.0, "high": 10.0, "step": 1.0},
        "short_mom_weight": {"low": 0.3, "high": 0.7, "step": 0.05},
        "long_mom_weight": {"low": 0.1, "high": 0.5, "step": 0.05},
        "volatility_penalty": {"low": 0.05, "high": 0.35, "step": 0.05},

        # --- Lever 1: Momentum lookback tuning ---
        "short_momentum_days": {"type": "categorical", "choices": [5, 10, 15, 20]},
        "long_momentum_days": {"type": "categorical", "choices": [40, 60, 90, 120]},

        # --- Lever 3: Entry timing signals ---
        "rsi_oversold_filter": {"low": 20, "high": 40, "step": 5},
        "volume_ratio_min": {"low": 0.8, "high": 2.0, "step": 0.1},

        # --- Lever 4: Exit strategy optimization ---
        "exit_type": {"type": "categorical", "choices": ["trailing_stop", "hybrid", "time_capped"]},
        "hybrid_initial_target_pct": {"low": 10.0, "high": 25.0, "step": 2.5},
        "hybrid_trailing_pct": {"low": 5.0, "high": 12.0, "step": 1.0},
        "max_hold_days": {"low": 20, "high": 120, "step": 10},

        # --- Lever 6: Lookback window tuning ---
        "optimization_lookback_days": {"type": "categorical", "choices": [126, 189, 252, 378, 504]},

        # --- Lever 7: Sector rotation ---
        "sector_cap": {"low": 1, "high": 4, "step": 1},
    },
}

# Conditional parameters: only sampled when parent param matches
V2_CONDITIONAL_PARAMS = {
    "hybrid_initial_target_pct": {"parent": "exit_type", "condition": "hybrid"},
    "hybrid_trailing_pct": {"parent": "exit_type", "condition": "hybrid"},
    "max_hold_days": {"parent": "exit_type", "condition": "time_capped"},
}

# V2 regime constraints (expanded from V1 for new params)
V2_REGIME_CONSTRAINTS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "extreme": {
        "trailing_stop_pct": {"low": 15.0},
        "max_positions": {"high": 4},
        "position_size_pct": {"high": 15.0},
        "exit_type": {"type": "categorical", "choices": ["trailing_stop"]},
        "max_hold_days": {"high": 30},
        "sector_cap": {"high": 2},
    },
    "high": {
        "trailing_stop_pct": {"low": 12.0},
        "max_positions": {"high": 6},
        "sector_cap": {"high": 3},
    },
    "low": {
        "trailing_stop_pct": {"high": 18.0},
        "max_positions": {"low": 4},
    },
    # "medium": no constraints (full space)
}


# === Indicator Computation Helpers ===

def compute_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute Relative Strength Index (RSI) from a close price series.

    Args:
        closes: Series of close prices (must have at least period+1 values)
        period: RSI period (default 14)

    Returns:
        Series of RSI values (0-100). NaN for first `period` entries.
    """
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # Wilder's smoothed moving average (exponential with alpha=1/period)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute Average True Range (ATR).

    Args:
        high: Series of high prices
        low: Series of low prices
        close: Series of close prices
        period: ATR period (default 14)

    Returns:
        Series of ATR values. NaN for first `period` entries.
    """
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr
