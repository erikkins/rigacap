"""Preserver sleeve detectors + regime routing — production port of the validated research.

The Preserver tier = the t30v momentum engine (Core) + regime-adaptive defensive overlays.
In the market's dominant rotating-bull regime (~70% of days) it runs Core t30v; in the
other regimes it routes to a defensive sleeve:

    calm_bull (strong_bull / weak_bull)          -> pullback_ma   (orderly-trend dip buy)
    capitulation (panic_crash/recovery/weak_bear) -> oversold_bounce (deep RSI reclaim)
    everything else (rotating_bull / range_bound) -> Core t30v

Detector logic + params below are frozen from the TPE research (validated cross-half +
EXT holdout + daily-DD). This module is PURE FUNCTIONS on price arrays — it does not touch
the live t30v signal path, the DB, or the daily scan. Wiring comes in later, shadow-mode
steps. See docs/… Phase 2 plan.

NOTE: the Maximizer++ add-on's breakout sleeve + momentum-factor vol-scaling live in a
separate module (not here) — Preserver base ships first.
"""
from __future__ import annotations

from typing import Dict, Set
import numpy as np
import pandas as pd

# ── validated params (frozen from research; see scripts/shape_tpe.py winners) ────────────
PULLBACK_MA = {"depth_min": 0.034, "depth_band": 0.057, "dryup": 1.106, "mom_min": 0.457, "hold": 40}
OVERSOLD_BOUNCE = {"rsi_max": 15.07, "drop_min": 0.209, "mom_min": 0.30, "hold": 11}

# ── regime routing: which signal source is live in each of the 7 production regimes ──────
CALM_BULL: Set[str] = {"strong_bull", "weak_bull"}
CAPITULATION: Set[str] = {"panic_crash", "recovery", "weak_bear"}
# rotating_bull, range_bound -> Core t30v (handled by the existing pipeline)


def route(regime: str) -> str:
    """Given today's 7-regime label, which source drives the Preserver book today."""
    if regime in CALM_BULL:
        return "pullback_ma"
    if regime in CAPITULATION:
        return "oversold_bounce"
    return "t30v"  # rotating_bull / range_bound / unknown -> the Core engine


# ── feature helpers (match the research precompute in scripts/shape_tpe.py) ──────────────
def _rsi14(close: pd.Series) -> np.ndarray:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=5).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=5).mean()
    return (100 - 100 / (1 + gain / loss.replace(0, np.nan))).to_numpy()


def pullback_ma_signal(o, h, l, c, vol, p: Dict = PULLBACK_MA) -> np.ndarray:
    """Trend-continuation dip buy (fires in calm_bull). o/h/l/c/vol = float numpy arrays.
    Rising uptrend (MA50>MA200, MA50 climbing, price>MA50); yesterday dipped to/through the
    rising 20-MA by depth_min..depth_min+band off the prior 20d high on dried-up volume;
    today reclaims the MA on an up day; own 126d momentum above mom_min (leadership)."""
    cs = pd.Series(c)
    ma50 = cs.rolling(50, min_periods=10).mean().to_numpy()
    ma200 = cs.rolling(200, min_periods=50).mean().to_numpy()
    ma50_10 = pd.Series(ma50).shift(10).to_numpy()
    ma20 = cs.rolling(20, min_periods=5).mean().to_numpy()
    hi20 = cs.rolling(20, min_periods=5).max().to_numpy()
    hi20_1 = pd.Series(hi20).shift(1).to_numpy()
    c1 = cs.shift(1).to_numpy()
    vol50 = pd.Series(vol).rolling(50, min_periods=10).mean().to_numpy()
    vol50_1 = pd.Series(vol50).shift(1).to_numpy()
    vol1 = pd.Series(vol).shift(1).to_numpy()
    mom126 = (cs / cs.shift(126) - 1.0).to_numpy()
    dmin, dmax = p["depth_min"], p["depth_min"] + p["depth_band"]
    depth_y = np.where(hi20_1 > 0, (hi20_1 - c1) / hi20_1, 0.0)
    sig = ((ma50 > ma200) & (ma50 > ma50_10) & (c > ma50)
           & (depth_y >= dmin) & (depth_y <= dmax)
           & (vol1 < p["dryup"] * vol50_1)
           & (mom126 > p["mom_min"])
           & (c > c1) & (c > o)
           & (c >= 15) & (vol >= 500_000))
    return np.nan_to_num(sig, nan=0.0).astype(bool)


def oversold_bounce_signal(o, h, l, c, vol, p: Dict = OVERSOLD_BOUNCE) -> np.ndarray:
    """Deep capitulation reclaim (fires in capitulation regimes). Dip within a longer-term
    uptrend (price>MA200); yesterday RSI14 < rsi_max (oversold) AND pulled back >= drop_min
    off the prior 20d high; today reclaims on an up day; own 126d momentum above mom_min."""
    cs = pd.Series(c)
    ma200 = cs.rolling(200, min_periods=50).mean().to_numpy()
    hi20 = cs.rolling(20, min_periods=5).max().to_numpy()
    hi20_1 = pd.Series(hi20).shift(1).to_numpy()
    c1 = cs.shift(1).to_numpy()
    rsi1 = pd.Series(_rsi14(cs)).shift(1).to_numpy()
    mom126 = (cs / cs.shift(126) - 1.0).to_numpy()
    depth_y = np.where(hi20_1 > 0, (hi20_1 - c1) / hi20_1, 0.0)
    sig = ((c > ma200)
           & (rsi1 < p["rsi_max"])
           & (depth_y >= p["drop_min"])
           & (mom126 > p["mom_min"])
           & (c > c1) & (c > o)
           & (c >= 15) & (vol >= 500_000))
    return np.nan_to_num(sig, nan=0.0).astype(bool)


SLEEVE_FNS = {"pullback_ma": pullback_ma_signal, "oversold_bounce": oversold_bounce_signal}
SLEEVE_HOLD = {"pullback_ma": PULLBACK_MA["hold"], "oversold_bounce": OVERSOLD_BOUNCE["hold"]}
