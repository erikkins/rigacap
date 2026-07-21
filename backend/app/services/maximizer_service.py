"""Maximizer book + shadow orchestration — mirrors preserver_service.

MaximizerBook == PreserverBook (single capital pool, hold-to-exit rule B) with TWO additions:
  1. `breakout` is an active sleeve source (rotating_bull entries), alongside pullback_ma
     (calm_bull) and oversold_bounce (capitulation). range_bound routes to Core t30v (the live
     model portfolio, referenced read-only — not re-entered here), same as Preserver's rotating
     leg.
  2. The breakout leg wears the Barroso VOL-BRAKE: breakout entries are scaled down when the
     book's own recent realized vol spikes (the momentum-crash "seatbelt"). This is an
     ENTRY-TIME exposure approximation of the research return-stream brake
     (scripts/tier_vintages_daily.py `vol_scale`) — rule B forbids continuously rescaling held
     positions, so the book scales exposure at entry only. Faithful-in-RANGE, not penny-exact
     (same modeling posture as the Preserver single-pool book).

Additive / offline-testable: takes prices + candidates as args, no DB. `run_shadow_day` wires
it into the daily scan behind the MAXIMIZER_SHADOW env flag (dark until enabled).
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from app.services.maximizer_sleeves import route, VOL_TARGET  # noqa: F401 (route used by run_shadow_day)

CAP0 = 100_000.0
COST = 0.0015
SLEEVE_SOURCES = ("pullback_ma", "oversold_bounce", "breakout")
_BRAKE_SOURCE = "breakout"
_VOL_WIN = 20  # trailing daily returns for the realized-vol brake input
# Maximizer mirrors Core (t30v leg) ONLY in range_bound (rotating_bull routes to breakout).
# Same rule-B turnover release as Preserver when a t30v leg exists and the regime flips.
T30V_TURNOVER_DAYS = 85


class MaximizerBook:
    """Single-pool sleeve book with the breakout leg + vol-brake. `advance_day` is one trading
    day. Rule B: held positions exit by their own hold, never churned on a regime flip."""

    def __init__(self, n_positions: int = 15, cap0: float = CAP0, cost: float = COST):
        self.n = n_positions
        self.cash = cap0
        self.cost = cost
        self.pos: Dict[str, dict] = {}
        self.last: Dict[str, float] = {}
        self.eq_hist: List[float] = []   # trailing book equity, for the vol-brake (causal)
        self.t30v_value = 0.0            # $ in the mirrored Core (t30v) leg — funded only in range_bound

    def equity(self) -> float:
        return (self.cash + self.t30v_value
                + sum(p["shares"] * self.last.get(s, p["last"]) for s, p in self.pos.items()))

    def source_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for p in self.pos.values():
            out[p["source"]] = out.get(p["source"], 0) + 1
        return out

    def _vol_scale_factor(self) -> float:
        """Barroso brake: target / trailing-realized-vol (annualized), capped at 1.0. Computed
        from the book's OWN prior daily returns (causal — uses history BEFORE today's entries),
        mirroring the research `vol_scale` lag. Returns 1.0 (no brake) until enough history."""
        if len(self.eq_hist) < _VOL_WIN + 1:
            return 1.0
        eq = pd.Series(self.eq_hist[-(_VOL_WIN + 1):])
        rv = float(eq.pct_change().std() * (252 ** 0.5))
        if rv <= 0 or rv != rv:
            return 1.0
        return min(1.0, VOL_TARGET / rv)

    def advance_day(self, today, active_source: str, candidates: List[dict],
                    price_of: Dict[str, float], core_ret: float = 0.0) -> float:
        """One trading day. candidates: ranked [{symbol, hold}] for the active sleeve today.
        price_of: {symbol: today_close}. core_ret: live Core book daily total return — the
        mirrored t30v leg earns it (Maximizer == Core in range_bound). Returns EOD equity."""
        for s, px in price_of.items():
            if px == px:  # not NaN
                self.last[s] = px
        # 0) the mirrored t30v leg earns the live Core book's return for the day
        if self.t30v_value and core_ret == core_ret:  # core_ret not NaN
            self.t30v_value *= (1.0 + core_ret)
        # 1) age + exits — each position by ITS OWN hold (rule B: mixed sources coexist)
        for p in self.pos.values():
            p["days_held"] += 1
        for s in [s for s, p in self.pos.items() if p["days_held"] >= p["hold"]]:
            self.cash += self.pos[s]["shares"] * self.last.get(s, self.pos[s]["last"]) * (1 - self.cost)
            del self.pos[s]
        # 2a) range_bound (t30v-routed): mirror Core — pour any free cash into the t30v leg.
        if active_source == "t30v":
            if self.cash > 0:
                self.t30v_value += self.cash * (1 - self.cost)
                self.cash = 0.0
        # 2b) sleeve regime (breakout / pullback_ma / oversold_bounce): rule B — release any
        #     t30v leg to cash over turnover, then enter names. Breakout wears the vol-brake.
        elif active_source in SLEEVE_SOURCES:
            if self.t30v_value > 0:
                rel = self.t30v_value / T30V_TURNOVER_DAYS
                self.cash += rel
                self.t30v_value -= rel
            brake = self._vol_scale_factor() if active_source == _BRAKE_SOURCE else 1.0
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
                # reserve entry cost so cash can't go negative when cash-bound; then vol-brake scale
                alloc = min(self.equity() / self.n, self.cash / (1 + self.cost)) * brake
                if alloc <= 0:
                    break
                shares = alloc / price
                self.cash -= alloc + alloc * self.cost
                self.pos[s] = {"shares": shares, "entry": price, "hold": int(cand.get("hold", 20)),
                               "days_held": 0, "source": active_source, "last": price}
                free -= 1
        eq = self.equity()
        self.eq_hist.append(eq)
        if len(self.eq_hist) > 60:      # cap history (brake only needs ~21)
            self.eq_hist = self.eq_hist[-60:]
        return eq

    # ── persistence (shadow book survives across daily runs via a snapshot row) ──
    def to_positions(self) -> List[dict]:
        return [dict(symbol=s, **{k: p[k] for k in ("shares", "entry", "hold", "days_held", "source")})
                for s, p in self.pos.items()]

    @classmethod
    def from_state(cls, cash: float, positions: List[dict], last: Dict[str, float] = None,
                   eq_hist: List[float] = None, t30v_value: float = 0.0, **kw) -> "MaximizerBook":
        b = cls(**kw)
        b.cash = cash
        b.t30v_value = t30v_value or 0.0
        b.last = dict(last or {})
        b.eq_hist = list(eq_hist or [])
        for p in positions or []:
            b.pos[p["symbol"]] = {"shares": p["shares"], "entry": p["entry"], "hold": p["hold"],
                                  "days_held": p["days_held"], "source": p["source"],
                                  "last": (last or {}).get(p["symbol"], p["entry"])}
        return b


async def run_shadow_day(db, signal_date, regime, t30v_signals, data_cache, n_positions: int = 15):
    """MAXIMIZER SHADOW daily hook — records only, never served; ADDITIVE (new tables, t30v path
    untouched). Wired into _run_daily_scan AFTER compute_shared_dashboard_data, INSIDE try/except,
    behind the MAXIMIZER_SHADOW env flag. Reconstruct book from the last snapshot -> route by
    regime -> advance one day (rule B + vol-brake) -> persist today's routed candidates + a fresh
    book snapshot. Requires the migration (maximizer_shadow_tables.sql). Returns a summary dict.
    """
    from datetime import date as _date
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.core.database import MaximizerSignal, MaximizerBookSnapshot
    from app.services.maximizer_signal_service import build_daily_signals
    from app.services.maximizer_sleeves import SLEEVE_HOLD

    sd = signal_date
    if isinstance(sd, str):
        sd = _date.fromisoformat(sd[:10])
    elif hasattr(sd, "date") and not isinstance(sd, _date):
        sd = sd.date()

    # 1) reconstruct the sleeve book from the latest snapshot (or start fresh)
    last_row = (await db.execute(
        select(MaximizerBookSnapshot).order_by(MaximizerBookSnapshot.snapshot_date.desc()).limit(1)
    )).scalars().first()
    if last_row and isinstance(last_row.positions_json, dict):
        st = last_row.positions_json
        book = MaximizerBook.from_state(cash=st.get("cash", CAP0), positions=st.get("positions", []),
                                        eq_hist=st.get("eq_hist", []), t30v_value=st.get("t30v_value", 0.0),
                                        n_positions=n_positions)
    else:
        book = MaximizerBook(n_positions=n_positions)

    # Core's daily total return for the mirrored t30v leg (funded only in range_bound).
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
        print(f"⚠️ Maximizer shadow: core_ret fetch failed (leg flat today): {_cre}")

    # 2) route + today's routed candidates
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

    # 4) advance the book one trading day (t30v leg earns core_ret; breakout leg per rule B)
    equity = book.advance_day(sd, src, book_cands, price_of, core_ret=core_ret)

    # 5) persist today's routed candidates (upsert) + the book snapshot (upsert)
    for c in cands:
        if not c.get("symbol"):
            continue
        stmt = pg_insert(MaximizerSignal).values(
            signal_date=sd, symbol=c["symbol"], price=c.get("price"), source=src, regime=regime,
            dollar_volume=c.get("dollar_volume"), hold_days=c.get("hold_days"), status="active")
        stmt = stmt.on_conflict_do_update(
            constraint="uq_maximizer_signal_date_symbol",
            set_={"price": stmt.excluded.price, "source": stmt.excluded.source,
                  "regime": stmt.excluded.regime, "dollar_volume": stmt.excluded.dollar_volume,
                  "hold_days": stmt.excluded.hold_days, "status": stmt.excluded.status})
        await db.execute(stmt)

    snap = {"cash": book.cash, "positions": book.to_positions(), "eq_hist": book.eq_hist,
            "t30v_value": book.t30v_value}
    snap_stmt = pg_insert(MaximizerBookSnapshot).values(
        snapshot_date=sd, regime=regime, active_source=src, equity=equity, positions_json=snap)
    snap_stmt = snap_stmt.on_conflict_do_update(
        index_elements=[MaximizerBookSnapshot.snapshot_date],
        set_={"regime": snap_stmt.excluded.regime, "active_source": snap_stmt.excluded.active_source,
              "equity": snap_stmt.excluded.equity, "positions_json": snap_stmt.excluded.positions_json})
    await db.execute(snap_stmt)
    await db.commit()
    return {"source": src, "regime": regime, "equity": round(equity, 2),
            "held": len(book.pos), "signals": len(cands)}
