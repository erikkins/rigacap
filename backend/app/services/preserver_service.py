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


def run_shadow_day(db, signal_date, regime, t30v_signals, data_cache):
    """SHADOW daily hook (wired into _run_daily_scan after compute_shared_dashboard_data).

    Skeleton — final wiring gated on the migration + sign-off (see
    design/documents/preserver-productionization-design.md). Must be called inside a
    try/except in the daily scan so it can never abort the live pipeline.
    """
    raise NotImplementedError("Wired in the shadow-deploy step, after the migration + sign-off.")
