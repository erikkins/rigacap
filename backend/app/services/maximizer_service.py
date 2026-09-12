"""Maximizer book + shadow orchestration — the CERTIFIED construction.

MaximizerBook = a full-notional gated-BREAKOUT standing book + a CONTINUOUS book-level
VOL-TARGET (Barroso). Validated penny-to-penny vs maximizer_portfolio.replay_sleeve('breakout')
+ vol_scaled_returns (see project_tier_reconciliation_jul21 — 38.7%/79.1% survivorship-free).

  - Breakout sleeve holds real positions (hold-to-exit); entries fire ONLY on days routed to
    breakout (rotating_bull) — build_daily_signals returns src='breakout' only then, so in every
    other regime the book adds nothing and held names age out. That IS the regime gate.
  - Reported equity earns the sleeve's daily return SCALED by the vol-target (target / trailing
    realized vol, lagged, capped 1.0) — exposure-scaling on the return stream, which ports.
  - NO t30v leg (the earlier ad-hoc book had entry-time brake + a t30v leg — both wrong; the
    ungated/entry-brake version under-captured badly). The Preserver/t30v layer is served
    SEPARATELY: a Maximizer subscriber gets Preserver signals + this breakout layer, delineated.

Additive / offline-testable: takes prices + candidates as args, no DB. `run_shadow_day` wires
it into the daily scan behind the MAXIMIZER_SHADOW env flag.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from app.services.maximizer_sleeves import route, VOL_TARGET  # noqa: F401 (route used by run_shadow_day)

CAP0 = 100_000.0
COST = 0.0015
BREAKOUT_SOURCE = "breakout"
_VOL_WIN = 20  # trailing window for the book-level realized-vol target


class MaximizerBook:
    """CERTIFIED Maximizer construction (validated penny-to-penny vs maximizer_portfolio):
    a full-notional gated-BREAKOUT standing book + a CONTINUOUS book-level VOL-TARGET.

    - The breakout sleeve holds real positions (hold-to-exit); entries fire ONLY when the day
      is routed to breakout (rotating_bull, via route()/build_daily_signals) — in every other
      regime build_daily_signals returns a non-breakout source, so the book adds nothing and
      the held breakout names simply age out. That IS the regime gate (the earlier ungated /
      entry-time-braked ad-hoc book was wrong — see project_tier_reconciliation_jul21).
    - The reported Maximizer equity earns the breakout sleeve's daily return SCALED by the
      Barroso vol-target (target / trailing realized vol, lagged, capped 1.0). Exposure-scaling
      on the return stream = maximizer_portfolio.vol_scaled_returns, so it ports faithfully.
    - NO t30v leg here: the Preserver/t30v layer is served separately (a Maximizer subscriber
      gets Preserver signals + this breakout layer, delineated).
    `core_ret` is accepted but unused (interface compat with the shadow hook)."""

    def __init__(self, n_positions: int = 15, cap0: float = CAP0, cost: float = COST):
        self.n = n_positions
        self.cost = cost
        self.bk_cash = cap0              # full-notional breakout sleeve book (cash side)
        self.pos: Dict[str, dict] = {}   # breakout positions
        self.last: Dict[str, float] = {}
        self.bk_eq_hist: List[float] = []  # breakout sleeve equity history (r_bk + vol-target)
        self.max_value = cap0            # the vol-scaled Maximizer equity (what we report)
        self.day_fills: List[dict] = []  # discrete fills recorded on the most recent advance_day
        self._last_vol_scale = 1.0

    def _bk_equity(self) -> float:
        return self.bk_cash + sum(p["shares"] * self.last.get(s, p["last"]) for s, p in self.pos.items())

    def equity(self) -> float:
        return self.max_value

    def source_counts(self) -> Dict[str, int]:
        return {BREAKOUT_SOURCE: len(self.pos)} if self.pos else {}

    def _vol_scale(self, recent_closes: Dict[str, "pd.Series"] = None) -> float:
        """Barroso vol-target: target / trailing realized vol of the breakout sleeve (annualized,
        LAGGED — computed from history BEFORE today, so causal), capped at 1.0.

        WARM (>= _VOL_WIN+1 days of book equity): the CERTIFIED return-stream computation, kept
        BYTE-IDENTICAL — the marketed Maximizer walk-forward maps to this penny-to-penny; do NOT
        touch it.

        COLD WINDOW (first ~21 days, before the book has its own return stream): instead of the old
        vs=1.0 — brake OFF exactly when launch-timing risk bites (project_maximizer_coldstart_jul21)
        — estimate the SAME quantity from the ACTUAL held positions' recent REAL closes:
        value-weighted (by position value) daily returns over the last _VOL_WIN days, annualized,
        lagged (today excluded). Converges to the certified return-stream vol once warm. Empty book
        / no closes passed / no usable history → 1.0 (never fabricate)."""
        if len(self.bk_eq_hist) >= _VOL_WIN + 1:
            eq = pd.Series(self.bk_eq_hist[-(_VOL_WIN + 1):])
            rv = float(eq.pct_change().std() * (252 ** 0.5))
            if rv <= 0 or rv != rv:
                return 1.0
            return min(1.0, VOL_TARGET / rv)
        # cold-window real-holdings-vol estimator (only reached while len(bk_eq_hist) < _VOL_WIN+1)
        if not self.pos or not recent_closes:
            return 1.0
        cols, weights = {}, {}
        for s, p in self.pos.items():
            ser = recent_closes.get(s)
            if ser is None or len(ser) < _VOL_WIN + 2:
                continue
            cols[s] = ser.iloc[:-1].tail(_VOL_WIN + 1).pct_change()   # drop today (causal) → 20 returns
            weights[s] = p["shares"] * self.last.get(s, p["last"])
        tot = sum(weights.values()) if weights else 0.0
        if not cols or tot <= 0:
            return 1.0
        ret_df = pd.DataFrame(cols).dropna()
        if ret_df.empty:
            return 1.0
        w = pd.Series({s: weights[s] / tot for s in cols})
        rv = float(ret_df.mul(w, axis=1).sum(axis=1).std() * (252 ** 0.5))   # value-weighted port vol
        if rv <= 0 or rv != rv:
            return 1.0
        return min(1.0, VOL_TARGET / rv)

    def advance_day(self, today, active_source: str, candidates: List[dict],
                    price_of: Dict[str, float], core_ret: float = 0.0,
                    recent_closes: Dict[str, "pd.Series"] = None) -> float:
        """One trading day. candidates = ranked breakout names for today (empty unless the regime
        is routed to breakout). Returns the vol-scaled Maximizer equity. Records the day's discrete
        fills in self.day_fills (entries + hold-exits) for the per-tier STR log."""
        self.day_fills: List[dict] = []
        for s, px in price_of.items():
            if px == px:  # not NaN
                self.last[s] = px
        # exits — breakout positions by their own hold (time-stop)
        for p in self.pos.values():
            p["days_held"] += 1
        for s in [s for s, p in self.pos.items() if p["days_held"] >= p["hold"]]:
            p = self.pos[s]
            px = self.last.get(s, p["last"])
            proceeds = p["shares"] * px * (1 - self.cost)
            self.bk_cash += proceeds
            self.day_fills.append({
                "symbol": s, "side": "sell", "shares": p["shares"], "price": px,
                "cost": p["shares"] * px * self.cost, "source": BREAKOUT_SOURCE,
                "reason": "hold_exit", "days_held": p["days_held"],
                "realized_pnl": (px - p["entry"]) * p["shares"],
            })
            del self.pos[s]
        # entries — ONLY the gated breakout sleeve (fires only when routed to breakout)
        if active_source == BREAKOUT_SOURCE:
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
                alloc = min(self._bk_equity() / self.n, self.bk_cash / (1 + self.cost))
                if alloc <= 0:
                    break
                shares = alloc / price
                self.bk_cash -= alloc + alloc * self.cost
                self.pos[s] = {"shares": shares, "entry": price, "hold": int(cand.get("hold", 29)),
                               "days_held": 0, "source": BREAKOUT_SOURCE, "last": price}
                self.day_fills.append({
                    "symbol": s, "side": "buy", "shares": shares, "price": price,
                    "cost": alloc * self.cost, "source": BREAKOUT_SOURCE, "reason": "entry",
                })
                free -= 1
        # vol-target: scale today's breakout return into the reported Maximizer equity
        bk_eq = self._bk_equity()
        prev = self.bk_eq_hist[-1] if self.bk_eq_hist else CAP0
        r_bk = (bk_eq / prev - 1.0) if prev else 0.0
        vs = self._vol_scale(recent_closes)          # from PRIOR history (lagged), before append
        self.max_value *= (1.0 + vs * r_bk)
        self._last_vol_scale = vs                     # stamp on today's entry fills (STR)
        for f in self.day_fills:
            if f["side"] == "buy":
                f["vol_scale"] = vs
        self.bk_eq_hist.append(bk_eq)
        if len(self.bk_eq_hist) > 60:
            self.bk_eq_hist = self.bk_eq_hist[-60:]
        return self.max_value

    # ── persistence (shadow book survives across daily runs via a snapshot row) ──
    def to_positions(self) -> List[dict]:
        return [dict(symbol=s, **{k: p[k] for k in ("shares", "entry", "hold", "days_held", "source")})
                for s, p in self.pos.items()]

    @classmethod
    def from_state(cls, bk_cash: float, positions: List[dict], last: Dict[str, float] = None,
                   bk_eq_hist: List[float] = None, max_value: float = CAP0, **kw) -> "MaximizerBook":
        b = cls(**kw)
        b.bk_cash = bk_cash if bk_cash is not None else CAP0
        b.max_value = max_value if max_value is not None else CAP0
        b.last = dict(last or {})
        b.bk_eq_hist = list(bk_eq_hist or [])
        for p in positions or []:
            b.pos[p["symbol"]] = {"shares": p["shares"], "entry": p["entry"], "hold": p["hold"],
                                  "days_held": p["days_held"], "source": p.get("source", BREAKOUT_SOURCE),
                                  "last": (last or {}).get(p["symbol"], p["entry"])}
        return b


async def emit_tier_fills(db, tier: str, fill_date, regime: str, fills: List[dict]) -> int:
    """Persist a book's discrete fills into tier_fills (STR log). Idempotent per
    (tier, fill_date, symbol, side). Never raises into the caller (best-effort log)."""
    if not fills:
        return 0
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.core.database import TierFill
    n = 0
    for f in fills:
        try:
            shares = float(f.get("shares") or 0)
            price = float(f.get("price") or 0)
            stmt = pg_insert(TierFill).values(
                tier=tier, fill_date=fill_date, symbol=f["symbol"], side=f["side"],
                shares=shares, price=price, gross=shares * price, cost=f.get("cost"),
                source=f.get("source"), regime=regime, reason=f.get("reason"),
                days_held=f.get("days_held"), realized_pnl=f.get("realized_pnl"),
                vol_scale=f.get("vol_scale"))
            stmt = stmt.on_conflict_do_update(
                index_elements=["tier", "fill_date", "symbol", "side"],
                set_={"shares": stmt.excluded.shares, "price": stmt.excluded.price,
                      "gross": stmt.excluded.gross, "cost": stmt.excluded.cost,
                      "source": stmt.excluded.source, "regime": stmt.excluded.regime,
                      "reason": stmt.excluded.reason, "days_held": stmt.excluded.days_held,
                      "realized_pnl": stmt.excluded.realized_pnl, "vol_scale": stmt.excluded.vol_scale})
            await db.execute(stmt)
            n += 1
        except Exception as e:
            print(f"⚠️ tier_fills emit ({tier} {f.get('symbol')}): {e}")
    return n


def generate_maximizer_briefing(held: int, new_today: int, regime: str,
                                recent: List[str] = None, market_note: str = "") -> str:
    """AI daily briefing for the Maximizer book — book-posture voice (aggressive, breakout-
    hunting), generated once/day in the worker and cached in the snapshot. Fed its last few
    briefings so it doesn't read templated, plus deterministic SPY trend facts (market_note) so
    it's market-aware, not just regime-aware. Falls back to a deterministic line if AI is down.

    market_note: a real-data SPY facts line (from market_regime.spy_trend_facts) — the ONLY market
    numbers the briefing may cite; never let it invent figures."""
    recent = recent or []
    fallback = (
        f"Rotating-bull momentum is broad — your Maximizer book is riding {held} breakout "
        f"name{'s' if held != 1 else ''} into their hold windows"
        f"{f' and added {new_today} today' if new_today else ''}. Aggressive by design; each "
        f"name sells on time at day 29, no trailing stop. Expect chop."
    ) if regime == "rotating_bull" else (
        "Out of rotating-bull — the Maximizer book has paused breakout hunting and is in "
        "Preserver mode. Held breakouts wind down on their exit dates; new buys follow the "
        "Preserver book."
    )
    # Make even the deterministic fallback market-aware (real facts only).
    if market_note:
        fallback = f"{market_note}. {fallback}"
    try:
        import httpx
        from app.core.config import settings
        from app.services.voice_filters import generate_with_voice_filter, banned_summary_for_prompt
        if not settings.ANTHROPIC_API_KEY:
            return fallback
        base_system = (
            "You write the daily briefing for RigaCap's MAXIMIZER tier — an aggressive, "
            "systematic breakout book (momentum names bought on a same-day breakout, held 29 "
            "trading days, sold on a hard time-stop, no trailing stop; a book-level vol-target "
            "trims exposure when things get wild). Voice: a sharp, confident analyst friend who "
            "runs an aggressive book and owns it — not hype, not a robot.\n"
            "Rules: 1-2 sentences, max 280 chars. Plain text, no markdown/emoji. Never say "
            "'buy'/'sell' as advice. Never say 'algorithm'/'model' — say 'the book' or 'the "
            "ensemble'. NEVER use the word 'tape' for the market — say 'market', 'action', or "
            "'the session'. Convey the aggressive, time-boxed nature honestly (it's high-variance; "
            "don't oversell). Vary opening, structure, and rhythm every day — sound spontaneous.\n"
            "MARKET DATA HONESTY: if a 'Market facts:' line is provided, you may cite ONLY those "
            "exact SPY numbers/streaks; never invent, estimate, or recall a figure. If none is "
            "given, state no market numbers at all.\n"
            "SPY STREAK (mandatory): if the Market facts show a streak of 3+ straight sessions "
            "(up or down), you MUST reference it — a sustained index move is always material. A "
            "1-2 session wiggle is not a streak; don't force it.\n"
            + banned_summary_for_prompt()
        )
        avoid = ("\n\nYour last briefings (do NOT echo their opening, structure, or rhythm):\n"
                 + "\n".join(f"- {m}" for m in recent)) if recent else ""
        mkt = f"\nMarket facts (cite ONLY these exact numbers): {market_note}" if market_note else ""
        user_prompt = (
            f"Regime: {regime}. The book holds {held} breakout name(s)"
            f"{f' and entered {new_today} today' if new_today else ' (no new entries today)'}."
            f"{mkt}"
            f"{avoid}"
        )
        headers = {"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}

        def _call(extra):
            sys_p = base_system + (("\n" + extra) if extra else "")
            payload = {"model": "claude-sonnet-4-6", "max_tokens": 150,
                       "system": sys_p, "messages": [{"role": "user", "content": user_prompt}]}
            try:
                r = httpx.post("https://api.anthropic.com/v1/messages", headers=headers,
                               json=payload, timeout=15)
                if r.status_code == 200:
                    c = r.json().get("content", [])
                    if c and c[0].get("type") == "text":
                        return c[0]["text"].strip().strip('"')
            except Exception as _e:
                print(f"⚠️ Maximizer briefing call failed: {_e}")
            return None

        # Enforce the brand voice (negative prompts leak "tape" etc.) — retry, else clean fallback.
        clean = generate_with_voice_filter(_call, max_retries=2, label="maximizer-briefing")
        return clean if clean else fallback
    except Exception as e:
        print(f"⚠️ Maximizer briefing AI failed (fallback): {e}")
    return fallback


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
    if last_row and isinstance(last_row.positions_json, dict) and "bk_cash" in last_row.positions_json:
        st = last_row.positions_json
        book = MaximizerBook.from_state(bk_cash=st.get("bk_cash", CAP0), positions=st.get("positions", []),
                                        bk_eq_hist=st.get("bk_eq_hist", []), max_value=st.get("max_value", CAP0),
                                        n_positions=n_positions)
    else:
        # Start FRESH when there's no prior snapshot OR an old-format snapshot missing 'bk_cash'.
        # Historic footgun (Jul 24 2026): from_state defaulted bk_cash to CAP0 while inheriting the
        # retained positions from an old-format snapshot → the full $100k cash was double-counted on
        # top of ~$65k of positions, inflating the book's base to ~$146k. Requiring the 'bk_cash' key
        # means we never silently graft full capital onto inherited positions again.
        if last_row is not None:
            print("⚠️ Maximizer: last snapshot lacks 'bk_cash' (old format) — starting book fresh "
                  "at CAP0 rather than double-counting inherited positions.")
        book = MaximizerBook(n_positions=n_positions)

    # 2) route + today's routed candidates. Only the breakout sleeve feeds the Maximizer book
    #    (gated: build_daily_signals returns src='breakout' only in rotating_bull).
    src, cands = build_daily_signals(data_cache, regime, t30v_signals, sd, max_positions=n_positions)
    # Data-quality gate (ASST guard, Aug 25 2026): never enter a stale or split-broken series,
    # no matter how strong its (corrupt) signal looks. Same rule the momentum ranker uses.
    from app.services.scanner import is_series_tradeable, _universe_stale_cutoff
    _cut = _universe_stale_cutoff(data_cache)
    book_cands = ([{"symbol": c["symbol"], "hold": SLEEVE_HOLD[src]} for c in cands
                   if is_series_tradeable(data_cache.get(c["symbol"]), _cut)]
                  if src == BREAKOUT_SOURCE else [])

    # 3) today's prices (latest close per symbol from the shared cache)
    price_of = {}
    for s, df in data_cache.items():
        try:
            if df is not None and len(df):
                price_of[s] = float(df["close"].iloc[-1])
        except Exception:
            pass

    # 4) advance the book one trading day (gated breakout sleeve + book-level vol-target).
    #    COLD WINDOW only (fresh/rebased book, < _VOL_WIN+1 days of equity history): pass the held
    #    names' real closes so the vol-brake estimates exposure from actual-holdings vol instead of
    #    sitting at 1.0. Warm books use the certified return-stream path and ignore this, so skip
    #    the work then (never touches the marketed/penny-to-penny warm mapping).
    _rc = None
    if len(book.bk_eq_hist) < _VOL_WIN + 1:
        _rc = {s: df["close"] for s, df in data_cache.items()
               if df is not None and getattr(df, "columns", None) is not None and "close" in df.columns}
    equity = book.advance_day(sd, src, book_cands, price_of, recent_closes=_rc)

    # 4b) STR: persist today's discrete breakout fills (entries + hold-exits) to tier_fills.
    await emit_tier_fills(db, "maximizer", sd, regime, book.day_fills)

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

    # Daily AI briefing (book-posture voice), fed the last few briefings for anti-repetition.
    # Generated here in the worker where the book state is fresh; cached in the snapshot JSON
    # (no migration) and served by tier_serving. Never fatal.
    briefing = None
    try:
        recent_briefs = (await db.execute(
            select(MaximizerBookSnapshot.positions_json)
            .where(MaximizerBookSnapshot.snapshot_date < sd)
            .order_by(MaximizerBookSnapshot.snapshot_date.desc()).limit(8)
        )).scalars().all()
        recent = [pj.get("briefing") for pj in recent_briefs
                  if isinstance(pj, dict) and pj.get("briefing")]
        new_today = sum(1 for f in getattr(book, "day_fills", []) if f.get("side") == "buy")
        try:
            from app.services.market_regime import spy_trend_facts
            _mkt = spy_trend_facts(data_cache)
        except Exception:
            _mkt = ""
        briefing = generate_maximizer_briefing(len(book.pos), new_today, regime, recent, market_note=_mkt)
    except Exception as _be:
        print(f"⚠️ Maximizer briefing generate failed (non-fatal): {_be}")

    snap = {"bk_cash": book.bk_cash, "positions": book.to_positions(),
            "bk_eq_hist": book.bk_eq_hist, "max_value": book.max_value, "briefing": briefing}
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
