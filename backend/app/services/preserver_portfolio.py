"""Preserver portfolio replay — Phase 2 Step 3.

The Preserver is a HELD PORTFOLIO (entries carried per-sleeve `hold` days), not a daily
signal feed. This is the prod-style position-level simulator for a single sleeve book —
the mechanics that will eventually live in the model-portfolio service. It mirrors the
research `scripts/shapes_portfolio.simulate` exactly so we can prove the prod port is
faithful: identical detectors (parity-proven) + identical portfolio mechanics = identical
equity to the validated research Preserver.

Pure/additive: operates on a passed-in data_cache (dict[sym, OHLCV DataFrame]); touches no
live storage. RESEARCH-VALIDATION use for now; the live daily-scan wiring reuses `route()`
to pick which book (t30v vs a sleeve) is active each day.
"""
from __future__ import annotations

from typing import Dict
import numpy as np
import pandas as pd

from app.services.preserver_sleeves import SLEEVE_FNS, SLEEVE_HOLD

CAP0 = 100_000.0
COST = 0.0015   # per-side friction (matches research)
_MIN_BARS = 200


def replay_sleeve(data_cache: Dict[str, pd.DataFrame], sleeve: str, start, end,
                  n_positions: int = 15) -> pd.Series:
    """Position-level equity curve for a single sleeve book over [start, end].

    Each day: exit positions past their hold; fill free slots from today's firing names
    (excluding held), ranked by 20d avg $-volume; equal-weight; mark to market.
    Mirrors shapes_portfolio.simulate (top-by-$vol selection, hold-day exits, COST both sides).
    """
    fn = SLEEVE_FNS[sleeve]
    hold = SLEEVE_HOLD[sleeve]
    start, end = pd.Timestamp(start), pd.Timestamp(end)

    # precompute per-symbol: close series, signal array, 20d $-volume, valid calendar
    closes, sigs, dvols, valids = {}, {}, {}, {}
    for s, df in data_cache.items():
        if s.startswith("^") or df is None or len(df) < _MIN_BARS:
            continue
        if not {"open", "high", "low", "close", "volume"}.issubset(df.columns):
            continue
        o, h, l, c, vol = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
        closes[s] = df["close"]
        sigs[s] = pd.Series(fn(o, h, l, c, vol), index=df.index)
        dvols[s] = (df["close"] * df["volume"]).rolling(20, min_periods=5).mean()
        valids[s] = df["close"].dropna().index
    close = pd.DataFrame(closes).sort_index()
    sig = pd.DataFrame(sigs).reindex(close.index).fillna(False)
    dvol = pd.DataFrame(dvols).reindex(close.index)

    dates = close.index
    win = dates[(dates >= start) & (dates <= end)]
    pos: Dict[str, dict] = {}
    cash = CAP0
    last_px: Dict[str, float] = {}
    eq_d, eq_v = [], []
    for today in win:
        row = close.loc[today]
        for s in close.columns:
            px = row[s]
            if px == px:
                last_px[s] = px
        # exits
        for s in [s for s, p in pos.items() if p["exit_date"] <= today]:
            cash += pos[s]["shares"] * last_px.get(s, pos[s]["last"]) * (1 - COST)
            del pos[s]
        # entries
        free = n_positions - len(pos)
        if free > 0:
            cands = [s for s in close.columns
                     if bool(sig.loc[today, s]) and s not in pos and (row[s] == row[s])]
            cands.sort(key=lambda s: -(dvol.loc[today, s] if dvol.loc[today, s] == dvol.loc[today, s] else 0))
            for s in cands[:free]:
                price = row[s]
                alloc = (cash + sum(pos[x]["shares"] * last_px.get(x, pos[x]["last"]) for x in pos)) / n_positions
                alloc = min(alloc, cash)
                if alloc <= 0:
                    break
                shares = alloc / price
                cash -= alloc + alloc * COST
                vd = valids[s]
                j = vd.get_indexer([today])[0]
                exit_date = vd[min(j + hold, len(vd) - 1)] if j >= 0 else today
                pos[s] = {"shares": shares, "exit_date": exit_date, "last": price}
        mtm = cash + sum(pos[s]["shares"] * last_px.get(s, pos[s]["last"]) for s in pos)
        eq_d.append(today); eq_v.append(mtm)
    return pd.Series(eq_v, index=pd.DatetimeIndex(eq_d))
