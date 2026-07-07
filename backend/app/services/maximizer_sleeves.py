"""Maximizer sleeve detectors + regime routing — production port of the validated research.

The Maximizer tier = the Preserver routing with ONE change: in the dominant rotating_bull
regime it swaps Core t30v for the momentum BREAKOUT sleeve (with a vol-scaling brake on the
momentum-crash tail). Everything else is identical to Preserver:

    calm_bull (strong_bull / weak_bull)           -> pullback_ma      (same as Preserver)
    capitulation (panic_crash/recovery/weak_bear) -> oversold_bounce  (same as Preserver)
    rotating_bull                                 -> breakout (NEW, vol-scaled)
    range_bound / unknown                         -> Core t30v

Breakout detector + params frozen from the TPE research (scripts/regime_allocator_v2.py
BREAKOUT + scripts/shape_tpe.py `_breakout`). The vol-brake is the Barroso-style factor-vol
scaling from scripts/tier_vintages_daily.py (`vol_scale`) — it halves the 2021 momentum
crash. PURE FUNCTIONS on price arrays: no DB, no live t30v path, no daily scan. Wiring comes
in later shadow-mode steps, mirroring the Preserver rollout.

Reuses the Preserver detectors verbatim (pullback_ma / oversold_bounce) so the shared legs
stay penny-identical across both tiers.
"""
from __future__ import annotations

from typing import Dict, Set

import numpy as np
import pandas as pd

# Reuse the validated Preserver legs unchanged (shared calm_bull / capitulation sleeves).
from app.services.preserver_sleeves import (  # noqa: F401
    PULLBACK_MA,
    OVERSOLD_BOUNCE,
    CALM_BULL,
    CAPITULATION,
    pullback_ma_signal,
    oversold_bounce_signal,
)

# ── validated breakout params (frozen; scripts/regime_allocator_v2.py BREAKOUT) ──────────
# regime="rotating" in research is the entry GATE — here the router enforces it, so the
# detector itself is gate-free and only fires on the breakout shape.
BREAKOUT = {"buffer": 0.014, "vol_mult": 1.38, "mom_min": -0.005, "hold": 29}

# ── vol-brake target (Barroso factor-vol scaling; scripts/tier_vintages_daily.py) ────────
VOL_TARGET = 0.20


def route(regime: str) -> str:
    """Given today's 7-regime label, which source drives the Maximizer book today.
    Identical to Preserver EXCEPT rotating_bull -> breakout (instead of Core t30v)."""
    if regime in CALM_BULL:
        return "pullback_ma"
    if regime in CAPITULATION:
        return "oversold_bounce"
    if regime == "rotating_bull":
        return "breakout"
    return "t30v"  # range_bound / unknown -> the Core engine


def breakout_signal(o, h, l, c, vol, p: Dict = BREAKOUT) -> np.ndarray:
    """Momentum breakout above the prior 50-day high on a volume spike (fires in
    rotating_bull). Rising trend (MA50>MA200, price>MA50); today closes above the prior
    50d high (excl. today) by `buffer`, and yesterday was AT/BELOW it (a FRESH cross);
    today's volume > vol_mult x 50d-avg volume; own 126d momentum above mom_min.

    Ported from scripts/shape_tpe.py `_breakout` — feature definitions match the research
    precompute exactly (ma50 mp10 / ma200 mp50 / vol50 mp10 / hi50_1 rolling50 mp15 shift1).
    """
    cs = pd.Series(c)
    ma50 = cs.rolling(50, min_periods=10).mean().to_numpy()
    ma200 = cs.rolling(200, min_periods=50).mean().to_numpy()
    hi50_1 = cs.rolling(50, min_periods=15).max().shift(1).to_numpy()  # prior 50d high, excl today
    c1 = cs.shift(1).to_numpy()
    vol50 = pd.Series(vol).rolling(50, min_periods=10).mean().to_numpy()
    mom126 = (cs / cs.shift(126) - 1.0).to_numpy()
    sig = ((ma50 > ma200) & (c > ma50)
           & (c > hi50_1 * (1 + p["buffer"]))    # broke above prior 50d high + buffer
           & (c1 <= hi50_1)                       # fresh cross (yesterday at/below the high)
           & (vol > p["vol_mult"] * vol50)        # volume spike
           & (mom126 > p["mom_min"])              # leadership
           & (c >= 15) & (vol >= 500_000))        # base universe filter (matches research detect)
    return np.nan_to_num(sig, nan=0.0).astype(bool)


def vol_scale(ret: pd.Series, target: float = VOL_TARGET) -> pd.Series:
    """Barroso factor-vol brake for the breakout leg. Scale exposure by target / realized
    vol (20d, annualized, LAGGED one day so it's causal), capped at 1.0. When the breakout
    leg's own volatility spikes (e.g. into the 2021 momentum crash), exposure is cut.
    Ported verbatim from scripts/tier_vintages_daily.py."""
    rv = (ret.rolling(20).std() * np.sqrt(252)).shift(1)
    return (target / rv).clip(upper=1.0).fillna(1.0)


SLEEVE_FNS = {
    "pullback_ma": pullback_ma_signal,
    "oversold_bounce": oversold_bounce_signal,
    "breakout": breakout_signal,
}
SLEEVE_HOLD = {
    "pullback_ma": PULLBACK_MA["hold"],
    "oversold_bounce": OVERSOLD_BOUNCE["hold"],
    "breakout": BREAKOUT["hold"],
}
