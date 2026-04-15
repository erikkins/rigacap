"""
V2 Strategy Parameter Space Definitions + Indicator Helpers

Extends V1 with 7 new alpha levers:
1. Momentum lookback tuning (short_momentum_days, long_momentum_days)
2. Regime-conditional optimization (expanded constraints)
3. Entry timing signals (RSI filter, volume ratio threshold)
4. Exit strategy optimization (trailing vs hybrid vs time-capped)
5. Multi-objective Pareto (handled in optuna_optimizer_v2.py)
6. Lookback window (fixed at 252 days — removed from search space)
7. Sector rotation (sector_cap)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any


# === V2 Parameter Space Definitions ===

V2_PARAM_SPACES: Dict[str, Dict[str, Any]] = {
    "ensemble": {
        # --- V1 params (retained, bounds tightened from V2 benchmark lessons) ---
        "dwap_threshold_pct": {"low": 3.0, "high": 7.0, "step": 0.5},
        "trailing_stop_pct": {"low": 10.0, "high": 20.0, "step": 1.0},  # Min 10% — 8% killed winners
        "max_positions": {"low": 4, "high": 8, "step": 1},  # Min 4 — 3 is too concentrated
        "position_size_pct": {"low": 12.0, "high": 20.0, "step": 1.0},
        "near_50d_high_pct": {"low": 2.0, "high": 10.0, "step": 1.0},
        "short_mom_weight": {"low": 0.3, "high": 0.7, "step": 0.05},
        "long_mom_weight": {"low": 0.1, "high": 0.5, "step": 0.05},
        "volatility_penalty": {"low": 0.05, "high": 0.30, "step": 0.05},

        # --- Lever 1: Momentum lookback tuning ---
        "short_momentum_days": {"type": "categorical", "choices": [5, 10, 15, 20]},
        "long_momentum_days": {"type": "categorical", "choices": [40, 60, 90, 120]},

        # --- Lever 3: Entry timing signals ---
        # RSI: 60-100 range (100=disabled). Previous 20-40 was too restrictive.
        "rsi_oversold_filter": {"low": 60, "high": 100, "step": 10},
        # Volume ratio: 0.0=disabled. Previous 0.8-2.0 forced high selectivity.
        "volume_ratio_min": {"low": 0.0, "high": 1.5, "step": 0.3},

        # --- Lever 4: Exit strategy optimization ---
        "exit_type": {"type": "categorical", "choices": ["trailing_stop", "hybrid", "time_capped"]},
        "hybrid_initial_target_pct": {"low": 10.0, "high": 25.0, "step": 2.5},
        "hybrid_trailing_pct": {"low": 5.0, "high": 12.0, "step": 1.0},
        "max_hold_days": {"low": 30, "high": 120, "step": 10},

        # --- Lever 6: Lookback window --- REMOVED from search space (fixed at 252 in WF service)
        # optimization_lookback_days was the most expensive param (504-day backtests = 4x slower),
        # causing Lambda 900s timeouts. Fixed at 252 to allow 100 trials per period.

        # --- Lever 7: Sector rotation ---
        # 0=disabled. Previous min=1 was always-on, reducing opportunity set.
        "sector_cap": {"low": 0, "high": 4, "step": 1},

        # --- Lever 8: Profit-based stop tightening ---
        # As profit grows, tighten trailing stop to protect gains.
        # breakeven_pct: once up X%, move stop to entry price (0=disabled)
        # profit_lock_pct: once up X%, tighten trailing stop (0=disabled)
        # profit_lock_stop_pct: what the tightened trailing stop becomes (% from peak)
        "breakeven_pct": {"low": 0, "high": 10, "step": 2},
        "profit_lock_pct": {"low": 0, "high": 20, "step": 2},
        "profit_lock_stop_pct": {"low": 3.0, "high": 8.0, "step": 1.0},

        # --- Lever 9: Anti-squeeze filters (added Apr 14 2026 after Feb 2021
        # meme-stock squeeze damage analysis: EH -58%, TLRY -50%, LCID -39%).
        # These filters reject candidates that are already parabolic.
        # 1000 = disabled sentinel.
        "max_recent_return_pct": {"low": 30, "high": 1000, "step": 10},   # reject if up > X% in last 30 days
        "price_velocity_cap_pct": {"low": 15, "high": 1000, "step": 5},    # reject if up > X% in last 5 days
    },
}

# === V2 CONSTRAINED Parameter Space ===
# Tight bounds around proven winners from A/B testing (Mar 25-28 2026).
# Reduces optimizer variance while preserving ability to adapt.
# Use via optimizer_version="v2c" in WF payload.
V2_CONSTRAINED_PARAM_SPACES: Dict[str, Dict[str, Any]] = {
    "ensemble": {
        # Core params: narrow bands around proven values
        "dwap_threshold_pct": {"low": 4.0, "high": 6.0, "step": 0.5},       # proven: 5%
        "trailing_stop_pct": {"low": 10.0, "high": 14.0, "step": 1.0},      # proven: 12%
        "max_positions": {"low": 5, "high": 7, "step": 1},                   # proven: 6
        "position_size_pct": {"low": 13.0, "high": 18.0, "step": 1.0},      # proven: 15%
        "near_50d_high_pct": {"low": 3.0, "high": 7.0, "step": 1.0},        # proven: 5%

        # Momentum weights: narrow
        "short_mom_weight": {"low": 0.4, "high": 0.6, "step": 0.05},
        "long_mom_weight": {"low": 0.2, "high": 0.4, "step": 0.05},
        "volatility_penalty": {"low": 0.10, "high": 0.25, "step": 0.05},

        # Momentum lookback: keep flexible (these have less variance impact)
        "short_momentum_days": {"type": "categorical", "choices": [5, 10, 15, 20]},
        "long_momentum_days": {"type": "categorical", "choices": [40, 60, 90, 120]},

        # Entry filters: keep loose (don't over-filter)
        "rsi_oversold_filter": {"low": 80, "high": 100, "step": 10},         # mostly disabled
        "volume_ratio_min": {"low": 0.0, "high": 0.6, "step": 0.3},         # mostly disabled

        # Exit: trailing stop ONLY (hybrid/time_capped both tested worse)
        "exit_type": {"type": "categorical", "choices": ["trailing_stop"]},
        "hybrid_initial_target_pct": {"low": 15.0, "high": 15.0, "step": 2.5},  # unused
        "hybrid_trailing_pct": {"low": 8.0, "high": 8.0, "step": 1.0},          # unused
        "max_hold_days": {"low": 60, "high": 60, "step": 10},                   # unused

        # Sector cap: disabled (proven best)
        "sector_cap": {"low": 0, "high": 2, "step": 1},

        # Profit-based stop tightening (constrained: narrower)
        "breakeven_pct": {"low": 4, "high": 8, "step": 2},
        "profit_lock_pct": {"low": 8, "high": 16, "step": 2},
        "profit_lock_stop_pct": {"low": 4.0, "high": 7.0, "step": 1.0},
    },
}

# === V2M (Medium Constrained) — wider than v2c, exit type locked ===
# Theory: exit_type=trailing_stop is the key guardrail. Let other params breathe.
V2_MEDIUM_PARAM_SPACES: Dict[str, Dict[str, Any]] = {
    "ensemble": {
        "dwap_threshold_pct": {"low": 3.0, "high": 7.0, "step": 0.5},       # full range
        "trailing_stop_pct": {"low": 10.0, "high": 18.0, "step": 1.0},      # wider than v2c (was 10-14)
        "max_positions": {"low": 4, "high": 8, "step": 1},                   # full range
        "position_size_pct": {"low": 12.0, "high": 20.0, "step": 1.0},      # full range
        "near_50d_high_pct": {"low": 2.0, "high": 8.0, "step": 1.0},        # slightly narrowed
        "short_mom_weight": {"low": 0.3, "high": 0.7, "step": 0.05},
        "long_mom_weight": {"low": 0.1, "high": 0.5, "step": 0.05},
        "volatility_penalty": {"low": 0.05, "high": 0.30, "step": 0.05},
        "short_momentum_days": {"type": "categorical", "choices": [5, 10, 15, 20]},
        "long_momentum_days": {"type": "categorical", "choices": [40, 60, 90, 120]},
        "rsi_oversold_filter": {"low": 80, "high": 100, "step": 10},         # mostly disabled
        "volume_ratio_min": {"low": 0.0, "high": 0.6, "step": 0.3},         # mostly disabled
        # EXIT TYPE LOCKED: trailing_stop only (proven best, removes worst outcomes)
        "exit_type": {"type": "categorical", "choices": ["trailing_stop"]},
        "hybrid_initial_target_pct": {"low": 15.0, "high": 15.0, "step": 2.5},
        "hybrid_trailing_pct": {"low": 8.0, "high": 8.0, "step": 1.0},
        "max_hold_days": {"low": 60, "high": 60, "step": 10},
        "sector_cap": {"low": 0, "high": 3, "step": 1},

        # Profit-based stop tightening
        "breakeven_pct": {"low": 0, "high": 10, "step": 2},
        "profit_lock_pct": {"low": 0, "high": 20, "step": 2},
        "profit_lock_stop_pct": {"low": 3.0, "high": 8.0, "step": 1.0},

        # Anti-squeeze (same bounds as V2)
        "max_recent_return_pct": {"low": 30, "high": 1000, "step": 10},
        "price_velocity_cap_pct": {"low": 15, "high": 1000, "step": 5},
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
