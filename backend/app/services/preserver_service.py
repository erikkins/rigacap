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


class PreserverBook:
    """Single-pool sleeve book. `advance_day` is one trading day. Rule B: never churn held
    positions on a regime flip — they exit by their own `exit_date`; new entries only from
    the active sleeve. Equity is the sleeve portion's mark-to-market (the t30v leg is added
    separately in prod from the live model portfolio)."""

    def __init__(self, n_positions: int = 15, cap0: float = CAP0, cost: float = COST):
        self.n = n_positions
        self.cash = cap0
        self.cost = cost
        self.pos: Dict[str, dict] = {}   # symbol -> {shares, entry, exit_date, source, last}
        self.last: Dict[str, float] = {}

    def equity(self) -> float:
        return self.cash + sum(p["shares"] * self.last.get(s, p["last"]) for s, p in self.pos.items())

    def source_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for p in self.pos.values():
            out[p["source"]] = out.get(p["source"], 0) + 1
        return out

    def advance_day(self, today, active_source: str, candidates: List[dict], price_of: Dict[str, float]) -> float:
        """One trading day. candidates: ranked [{symbol, hold}] for the active sleeve today.
        price_of: {symbol: today_close}. Returns end-of-day equity. Live-robust: positions age
        by a `days_held` counter (one per advance) and exit at their `hold` — no future-calendar
        dependency. Rule B: existing positions are never churned on a regime flip."""
        for s, px in price_of.items():
            if px == px:  # not NaN
                self.last[s] = px
        # 1) age + exits — each position by ITS OWN hold (rule B: mixed sources coexist)
        for p in self.pos.values():
            p["days_held"] += 1
        for s in [s for s, p in self.pos.items() if p["days_held"] >= p["hold"]]:
            self.cash += self.pos[s]["shares"] * self.last.get(s, self.pos[s]["last"]) * (1 - self.cost)
            del self.pos[s]
        # 2) entries — only when the active book is a defensive sleeve (t30v leg is live-referenced)
        if active_source in SLEEVE_SOURCES:
            free = self.n - len(self.pos)
            for cand in candidates:
                if free <= 0:
                    break
                s = cand["symbol"]
                if s in self.pos:
                    continue
                price = price_of.get(s)
                if price is None or price != price:
                    continue
                alloc = min(self.equity() / self.n, self.cash)
                if alloc <= 0:
                    break
                shares = alloc / price
                self.cash -= alloc + alloc * self.cost
                self.pos[s] = {"shares": shares, "entry": price, "hold": int(cand.get("hold", 20)),
                               "days_held": 0, "source": active_source, "last": price}
                free -= 1
        return self.equity()

    # ── persistence (shadow book survives across daily runs via a snapshot row) ──
    def to_positions(self) -> List[dict]:
        return [dict(symbol=s, **{k: p[k] for k in ("shares", "entry", "hold", "days_held", "source")})
                for s, p in self.pos.items()]

    @classmethod
    def from_state(cls, cash: float, positions: List[dict], last: Dict[str, float] = None, **kw) -> "PreserverBook":
        b = cls(**kw)
        b.cash = cash
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
                                        n_positions=n_positions)
    else:
        book = PreserverBook(n_positions=n_positions)

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

    # 4) advance the sleeve book one trading day
    equity = book.advance_day(sd, src, book_cands, price_of)

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

    snap = {"cash": book.cash, "positions": book.to_positions()}
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
