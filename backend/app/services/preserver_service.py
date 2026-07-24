"""Preserver book + shadow orchestration — Phase 2.

`PreserverBook` is the single-capital-pool held portfolio implementing the **hold-to-exit +
layer** transition rule (Option B): on a regime flip, existing positions are NOT churned —
they exit by their own per-sleeve hold; NEW entries come only from the current regime's
active book. So during a transition the book naturally holds a MIX of sources, each with its
own exit — which smoothly approximates the research routing.

In production the t30v leg (rotating-bull / range-bound regimes, ~70% of days) is the live
t30v model portfolio (referenced read-only, not re-entered here); this class manages the
DEFENSIVE SLEEVE positions (pullback_ma / oversold_bounce) that layer in during calm-bull /
capitulation regimes. `run_shadow_day` wires it into the daily scan (see the design doc);
that wiring is gated on sign-off + the migration.

Additive / offline-testable: `PreserverBook` takes prices + candidates as args, no DB.
"""
from __future__ import annotations

from typing import Dict, List
import pandas as pd

from app.services.preserver_sleeves import route  # noqa: F401  (used by run_shadow_day)

CAP0 = 100_000.0
COST = 0.0015
SLEEVE_SOURCES = ("pullback_ma", "oversold_bounce")
# The t30v leg MIRRORS the live Core book in every NON-capitulation regime (~90%+ of days):
# the leg's dollar value rides Core's daily total return, so Preserver == Core there.
# OVERLAY construction (validated Jul 21 — robustly beats Core: ~+2pp return, ~5pp less
# drawdown, worst-case DD −18.8% vs Core −23.7%, at ~4 partial trims/yr, tax-light): in a
# CAPITULATION regime, keep the book but FAST-tilt to CAP_EXPOSURE of equity in the Core leg
# and put the freed capital into the oversold-bounce sleeve; switch fully back to Core the day
# the regime clears. (Fast engage/release is what delivers the edge — the earlier rule-B
# hold-to-exit trickle erased it: Preserver collapsed to ≈Core. See tier reconciliation.)
CAP_EXPOSURE = 0.25            # Core-leg exposure retained during capitulation (rest -> oversold)
DEFENSIVE_SOURCE = "oversold_bounce"
T30V_TURNOVER_DAYS = 85        # (legacy; superseded by the fast overlay)


class PreserverBook:
    """Single capital pool = mirrored t30v leg + defensive-sleeve positions. `advance_day` is
    one trading day. Rule B: never churn held positions on a regime flip — sleeve names exit by
    their own hold, the t30v leg rotates out over Core's turnover; new entries only from the
    active book. Equity = cash + t30v leg + sleeve marks."""

    def __init__(self, n_positions: int = 15, cap0: float = CAP0, cost: float = COST):
        self.n = n_positions
        self.cash = cap0
        self.cost = cost
        self.pos: Dict[str, dict] = {}   # (unused by the exposure overlay; kept for interface compat)
        self.last: Dict[str, float] = {}
        self.t30v_value = 0.0            # $ in the mirrored Core (t30v) leg (== book equity)
        self.exposure = 1.0              # current Core exposure (1.0, or CAP_EXPOSURE in capitulation)
        self.day_fills: List[dict] = []  # discrete overlay actions (exposure trim/restore) for the STR

    def equity(self) -> float:
        return (self.cash + self.t30v_value
                + sum(p["shares"] * self.last.get(s, p["last"]) for s, p in self.pos.items()))

    def source_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for p in self.pos.values():
            out[p["source"]] = out.get(p["source"], 0) + 1
        return out

    def advance_day(self, today, active_source: str, candidates: List[dict],
                    price_of: Dict[str, float], core_ret: float = 0.0) -> float:
        """One trading day. core_ret: the live Core book's daily total return. The book is the
        Core book scaled by a regime EXPOSURE (return = exposure × core_ret) — full Core normally,
        CAP_EXPOSURE in capitulation (raise the rest to cash). Returns end-of-day equity."""
        self.day_fills = []
        # initial deploy: put the pool into the mirrored Core leg on the first day
        if self.t30v_value == 0.0 and self.cash > 0:
            self.t30v_value = self.cash * (1 - self.cost)
            self.cash = 0.0
        # regime EXPOSURE: full Core normally; CAP_EXPOSURE in capitulation (raise the rest to cash)
        exposure = CAP_EXPOSURE if active_source == DEFENSIVE_SOURCE else 1.0
        if exposure != self.exposure:                     # one-time cost to trim / restore exposure
            moved = abs(exposure - self.exposure) * self.t30v_value  # $ shifted between Core and cash
            self.t30v_value *= (1.0 - abs(exposure - self.exposure) * self.cost)
            # STR: log the overlay action (defensive trim to cash, or restore to full Core).
            self.day_fills.append({
                # shares=1 so gross carries the $ amount shifted between Core and cash.
                "symbol": "PORTFOLIO",
                "side": "sell" if exposure < self.exposure else "buy",
                "shares": 1.0, "price": round(moved, 2),
                "cost": abs(exposure - self.exposure) * self.t30v_value * self.cost,
                "source": "exposure",
                "reason": "exposure_trim" if exposure < self.exposure else "exposure_restore",
            })
            self.exposure = exposure
        # the mirrored Core leg earns the EXPOSURE-SCALED Core return. This is exactly the
        # validated research return-stream (daily return = exposure × core_ret), so the served
        # book maps penny-to-penny with research — no cash-moving/hold-drag to diverge.
        if self.t30v_value and core_ret == core_ret:      # core_ret not NaN
            self.t30v_value *= (1.0 + exposure * core_ret)
        return self.equity()

    # ── persistence (shadow book survives across daily runs via a snapshot row) ──
    def to_positions(self) -> List[dict]:
        return [dict(symbol=s, **{k: p[k] for k in ("shares", "entry", "hold", "days_held", "source")})
                for s, p in self.pos.items()]

    @classmethod
    def from_state(cls, cash: float, positions: List[dict], last: Dict[str, float] = None,
                   t30v_value: float = 0.0, exposure: float = 1.0, **kw) -> "PreserverBook":
        b = cls(**kw)
        b.cash = cash
        b.t30v_value = t30v_value or 0.0
        b.exposure = exposure or 1.0
        b.last = dict(last or {})
        for p in positions or []:
            b.pos[p["symbol"]] = {"shares": p["shares"], "entry": p["entry"], "hold": p["hold"],
                                  "days_held": p["days_held"], "source": p["source"],
                                  "last": (last or {}).get(p["symbol"], p["entry"])}
        return b


async def run_shadow_day(db, signal_date, regime, t30v_signals, data_cache, n_positions: int = 15):
    """SHADOW daily hook — records only, never served; ADDITIVE (new tables, t30v path untouched).

    Wired into _run_daily_scan AFTER compute_shared_dashboard_data, INSIDE a try/except so it can
    never abort the live pipeline. Requires the migration (preserver_shadow_tables.sql) applied.
    Each run: reconstruct the sleeve book from the last snapshot -> route by regime -> advance one
    day (rule B) -> persist today's routed candidates + a fresh book snapshot. The t30v leg in
    rotating/range regimes is the live model portfolio (referenced elsewhere), not re-entered here.
    Returns a small summary dict. NEEDS testing against a real DB before deploy.
    """
    from datetime import date as _date
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.core.database import PreserverSignal, PreserverBookSnapshot
    from app.services.preserver_signal_service import build_daily_signals
    from app.services.preserver_sleeves import SLEEVE_HOLD

    sd = signal_date
    if isinstance(sd, str):
        sd = _date.fromisoformat(sd[:10])
    elif hasattr(sd, "date") and not isinstance(sd, _date):
        sd = sd.date()

    # 1) reconstruct the sleeve book from the latest snapshot (or start fresh)
    last_row = (await db.execute(
        select(PreserverBookSnapshot).order_by(PreserverBookSnapshot.snapshot_date.desc()).limit(1)
    )).scalars().first()
    if last_row and isinstance(last_row.positions_json, dict):
        st = last_row.positions_json
        book = PreserverBook.from_state(cash=st.get("cash", CAP0), positions=st.get("positions", []),
                                        t30v_value=st.get("t30v_value", 0.0),
                                        exposure=st.get("exposure", 1.0), n_positions=n_positions)
    else:
        book = PreserverBook(n_positions=n_positions)

    # Core's daily total return for the mirrored t30v leg (portfolio_type='live'). Two most
    # recent snapshots as-of today; if today's isn't written yet the leg picks it up next day.
    core_ret = 0.0
    try:
        from app.core.database import ModelPortfolioSnapshot
        from datetime import datetime as _dtm, time as _tm
        _cut = _dtm.combine(sd, _tm(23, 59, 59))
        _tv = (await db.execute(
            select(ModelPortfolioSnapshot.total_value)
            .where(ModelPortfolioSnapshot.portfolio_type == "live",
                   ModelPortfolioSnapshot.snapshot_date <= _cut)
            .order_by(ModelPortfolioSnapshot.snapshot_date.desc()).limit(2)
        )).scalars().all()
        if len(_tv) == 2 and _tv[1]:
            core_ret = _tv[0] / _tv[1] - 1.0
    except Exception as _cre:
        print(f"⚠️ Preserver shadow: core_ret fetch failed (leg flat today): {_cre}")

    # 2) route + today's routed candidates (sleeve regimes feed the book; t30v leg is live-referenced)
    src, cands = build_daily_signals(data_cache, regime, t30v_signals, sd, max_positions=n_positions)
    book_cands = ([{"symbol": c["symbol"], "hold": SLEEVE_HOLD[src]} for c in cands]
                  if src in SLEEVE_SOURCES else [])

    # 3) today's prices (latest close per symbol from the shared cache)
    price_of = {}
    for s, df in data_cache.items():
        try:
            if df is not None and len(df):
                price_of[s] = float(df["close"].iloc[-1])
        except Exception:
            pass

    # 4) advance the book one trading day (t30v leg earns core_ret; sleeve leg per rule B)
    equity = book.advance_day(sd, src, book_cands, price_of, core_ret=core_ret)

    # 4b) STR: persist Preserver-specific overlay actions (exposure trim/restore) to tier_fills.
    # (Per-name Preserver trades == the Core t30v book's trades — not duplicated here.)
    try:
        from app.services.maximizer_service import emit_tier_fills
        await emit_tier_fills(db, "preserver", sd, regime, book.day_fills)
    except Exception as _fe:
        print(f"⚠️ Preserver tier_fills emit: {_fe}")

    # 5) persist today's routed candidates (upsert) + the book snapshot (upsert)
    for c in cands:
        if not c.get("symbol"):
            continue
        stmt = pg_insert(PreserverSignal).values(
            signal_date=sd, symbol=c["symbol"], price=c.get("price"), source=src, regime=regime,
            dollar_volume=c.get("dollar_volume"), hold_days=c.get("hold_days"), status="active")
        stmt = stmt.on_conflict_do_update(
            constraint="uq_preserver_signal_date_symbol",
            set_={"price": stmt.excluded.price, "source": stmt.excluded.source,
                  "regime": stmt.excluded.regime, "dollar_volume": stmt.excluded.dollar_volume,
                  "hold_days": stmt.excluded.hold_days, "status": stmt.excluded.status})
        await db.execute(stmt)

    snap = {"cash": book.cash, "positions": book.to_positions(),
            "t30v_value": book.t30v_value, "exposure": book.exposure}
    snap_stmt = pg_insert(PreserverBookSnapshot).values(
        snapshot_date=sd, regime=regime, active_source=src, equity=equity, positions_json=snap)
    snap_stmt = snap_stmt.on_conflict_do_update(
        index_elements=[PreserverBookSnapshot.snapshot_date],
        set_={"regime": snap_stmt.excluded.regime, "active_source": snap_stmt.excluded.active_source,
              "equity": snap_stmt.excluded.equity, "positions_json": snap_stmt.excluded.positions_json})
    await db.execute(snap_stmt)
    await db.commit()
    return {"source": src, "regime": regime, "equity": round(equity, 2),
            "held": len(book.pos), "signals": len(cands)}
