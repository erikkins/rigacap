"""Tier-aware serving (WS3) — ADDITIVE, reversible, live-Core-path untouched.

Serving model (Option-B, locked Jul 24 2026):
  - EVERYONE is served the PRESERVER base: the live t30v buy_signals (same names as Core)
    plus a capitulation exposure note. Nobody is served raw "Core" labeling — Core stays
    the internal model book.
  - MAXIMIZER-entitled users (subscription.has_maxpp_addon [paid] OR subscription.compmax
    [admin comp]) see the BREAKOUT BOOK in rotating_bull INSTEAD of the t30v list: the held
    breakout positions (day X/29 hold countdown) + today's fresh breakout buys. In every
    other regime Maximizer == Preserver (that's Option B — "really is Preserver aside from
    rotating bull"), so they get the Preserver base too.

Gated by the TIER_SERVING env flag (default OFF) so rollout is reversible; when off, callers
serve the legacy Core payload unchanged. This module never mutates the user's own positions
panel or the S3 dashboard cache — it only reshapes the served buy_signals list + adds tier
metadata. Breakout book/signals come from the shadow tables already populated daily behind
MAXIMIZER_SHADOW (maximizer_book_snapshots, maximizer_signals).
"""
from __future__ import annotations

import os
from datetime import date as _date, timedelta as _timedelta
from typing import Dict, List, Optional

from sqlalchemy import select

from app.services.perf_numbers import PERF as _PERF

# Regimes where the Preserver overlay raises cash (exposure -> ~25%). Mirrors
# preserver_service CAP / maximizer_blend_certify CAPIT.
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}
ROTATING = "rotating_bull"
BREAKOUT_HOLD = 29  # trading days (maximizer_sleeves.BREAKOUT["hold"])
CAP0 = 100_000.0    # book inception capital (matches maximizer/preserver book CAP0)

# Served "Simulated Portfolio (Walk-Forward)" card. HEADLINE = the REAL trailing-365-day ROLLING
# walk-forward (recomputed nightly by the tier_walkforward worker → S3 cache) so subscribers see
# recent ACTUAL performance. Beneath it, the 5-year AND 21-year overlay FOUNDATIONS from the single
# SSOT (perf_numbers.PERF) — same figures as public /track-record, so the long-term numbers can't
# drift (Gate B). If the rolling cache isn't populated yet, the card leads with the 5-year overlay
# (annualized) and shows the 21-year foundation beneath.
def _overlay_line(tier: str, key: str, window: str) -> dict:
    p = _PERF.get(tier, _PERF["preserver"])[key]
    return {
        "total_return_pct": p["cagr"], "sharpe_ratio": p["sharpe"],
        "max_drawdown_pct": p["maxdd"], "window": window, "annualized": True,
    }


def _read_rolling_wf(tier: str):
    """Nightly trailing-365 tier walk-forward from the S3 cache (written by the tier_walkforward
    worker). Returns None if absent → caller leads with the 5-year overlay instead."""
    try:
        from app.services.data_export import data_export_service
        cache = data_export_service.read_json("tier_walkforward.json") if hasattr(
            data_export_service, "read_json") else None
        row = (cache or {}).get(tier)
        if row and row.get("total_return_pct") is not None:
            return {**row, "rolling": True}
    except Exception:
        pass
    return None


# Back-compat alias (SSOT-derived); some callers referenced CERTIFIED_WF.
CERTIFIED_WF = {
    t: {**_overlay_line(t, "yr5", "5-year · modern market"),
        "label": _PERF[t]["label"].replace("RigaCap ", "")}
    for t in ("maximizer", "preserver")
}


def tier_backtest(tier: str):
    """Simulated Portfolio card: the REAL trailing-365 ROLLING walk-forward as the headline, with
    the 5-year + 21-year overlay foundations (SSOT) beneath. Falls back to the 5-year overlay as the
    headline if the nightly rolling cache isn't populated yet."""
    tier = tier if tier in _PERF else "preserver"
    name = _PERF[tier]["label"].replace("RigaCap ", "")
    foundations = [
        _overlay_line(tier, "yr5", "5-year"),
        _overlay_line(tier, "yr21", "21-year foundation"),
    ]
    rolling = _read_rolling_wf(tier)
    if rolling:
        # Real trailing-365 actual — a 12-month total return (not annualized).
        return {**rolling, "label": rolling.get("label") or name,
                "window": rolling.get("window") or "trailing 12 months",
                "annualized": False, "foundations": foundations}
    # No rolling cache yet → lead with the 5-year overlay; foundations = 21-year only (avoid dup).
    head = _overlay_line(tier, "yr5", "5-year · modern market")
    return {**head, "label": name, "rolling": False,
            "foundations": [_overlay_line(tier, "yr21", "21-year foundation")]}


def tier_serving_enabled() -> bool:
    """Global kill-switch. Off => callers serve the legacy Core payload unchanged."""
    return os.getenv("TIER_SERVING", "").lower() in ("1", "true", "yes")


def resolve_tier(subscription, is_admin: bool = False, preview_tier: Optional[str] = None) -> str:
    """'preserver' | 'maximizer'. Entitlement = paid add-on OR admin comp. Admins may
    force a view with ?preview_tier= for dark-launch verification."""
    if preview_tier in ("preserver", "maximizer"):
        return preview_tier
    if subscription is not None and (
        subscription.has_maximizer_access() if hasattr(subscription, "has_maximizer_access")
        else (getattr(subscription, "has_maxpp_addon", False) or getattr(subscription, "compmax", False))
    ):
        return "maximizer"
    return "preserver"


def _approx_exit_date(days_left: int) -> str:
    """Approx calendar exit date from trading days remaining (~5 trading days / 7 calendar)."""
    return (_date.today() + _timedelta(days=int(round(max(0, days_left) * 7 / 5)))).isoformat()


def _current_price(sym: str, data_cache: dict, fallback: float) -> float:
    df = data_cache.get(sym)
    try:
        if df is not None and len(df):
            return float(df["close"].iloc[-1])
    except Exception:
        pass
    return fallback


async def _load_prices(symbols: List[str], data_cache: dict) -> None:
    """Lazily hydrate data_cache for symbols the API Lambda hasn't loaded (mirrors
    _get_positions_with_guidance) so held-book marks aren't stuck at entry price."""
    missing = [s for s in symbols if s and s not in data_cache]
    if not missing:
        return
    try:
        from app.services.data_export import data_export_service
        data_cache.update(data_export_service.import_symbols(missing))
    except Exception as e:  # non-fatal: cards fall back to entry price
        print(f"⚠️ tier_serving: price hydrate failed: {e}")


async def build_maximizer_breakout_view(db, data_cache: dict) -> List[dict]:
    """The breakout BOOK as buy_signal-shaped cards, derived SOLELY from the latest book
    snapshot — the single source of truth, so the email and the site's book view always agree.
    A position entered today (days_held==0) is 'new'; the rest are 'holding'.

    NOTE: we intentionally do NOT read the maximizer_signals candidate table here — it lists
    candidates that the book may not have actually entered (e.g. it showed 'BAX' while the book
    held KO/PM/MMM/GM/KHC), which made the email diverge from the site. The book snapshot is
    what the subscriber mirrors; that's what we render everywhere."""
    from app.core.database import MaximizerBookSnapshot

    snap = (await db.execute(
        select(MaximizerBookSnapshot).order_by(MaximizerBookSnapshot.snapshot_date.desc()).limit(1)
    )).scalars().first()
    if not snap or not isinstance(snap.positions_json, dict):
        return []

    positions = snap.positions_json.get("positions", []) or []
    await _load_prices([p.get("symbol") for p in positions if p.get("symbol")], data_cache)
    cards: List[dict] = []
    for p in positions:
        sym = p.get("symbol")
        if not sym:
            continue
        entry = float(p.get("entry") or 0) or 0.0
        days_held = int(p.get("days_held") or 0)
        hold = int(p.get("hold") or BREAKOUT_HOLD)
        days_left = max(0, hold - days_held)
        cur = _current_price(sym, data_cache, entry)
        is_new = days_held == 0
        cards.append({
            "symbol": sym,
            "price": round(cur, 2),
            "entry_price": round(entry, 2),
            "source": "breakout",
            "exit_rule": "hold",
            "hold_days": hold,
            "days_held": days_held,
            "days_left": days_left,
            "exit_date_approx": _approx_exit_date(days_left),
            "pnl_pct": round(((cur / entry - 1) * 100) if entry else 0.0, 1),
            "status": "new" if is_new else "holding",
            "is_fresh": is_new,          # entered today
            "in_user_position": False,
            "ensemble_score": 0,
            "signal_strength_label": "New breakout" if is_new else "Holding",
            # Actionability for the 29-day TIME-stop: the exit date is fixed by the
            # BOOK's entry, so mirroring a holding late means you only get the days
            # that remain, not a fresh 29. New = full runway; a holding with < ~10
            # days left is 'late' (you'd buy days before the book sells it).
            "entry_status": "fresh" if is_new else ("actionable" if days_left >= 10 else "extended"),
            "still_actionable": bool(is_new or days_left >= 10),
        })
    # New (entered today) first, then holdings nearest to their time-stop exit.
    cards.sort(key=lambda c: (0 if c["status"] == "new" else 1, c["days_left"]))
    return cards


async def build_maximizer_missed(db, limit: int = 5) -> List[dict]:
    """Maximizer missed-opps = profitable CLOSED breakout trades from the book's real fill log
    (tier_fills), i.e. breakout winners a subscriber could have mirrored. Real trades, not a
    re-backtest — so the numbers are penny-honest. Empty until breakout exits accumulate."""
    from app.core.database import TierFill
    rows = (await db.execute(
        select(TierFill).where(
            TierFill.tier == "maximizer", TierFill.side == "sell",
            TierFill.reason == "hold_exit", TierFill.realized_pnl > 0,
        ).order_by(TierFill.fill_date.desc()).limit(limit)
    )).scalars().all()
    out = []
    for r in rows:
        entry_px = (r.price - (r.realized_pnl / r.shares)) if r.shares else r.price
        ret_pct = ((r.price / entry_px - 1) * 100) if entry_px else 0.0
        out.append({
            "symbol": r.symbol,
            "entry_price": round(entry_px, 2),
            "sell_price": round(r.price, 2),
            "sell_date": r.fill_date.isoformat() if r.fill_date else None,
            "would_be_return": round(ret_pct, 1),
            "would_be_pnl": round(r.realized_pnl, 2),
            "days_held": r.days_held,
            "source": "breakout",
        })
    return out


def build_breakout_radar(data_cache: dict, held_syms=None, limit: int = 8) -> List[dict]:
    """Breakout Radar — names APPROACHING a 50-day-high breakout (the premium 'what's next'
    for Maximizer, replacing the watchlist). Same trend/leadership filters as
    maximizer_sleeves.breakout_signal, but the price is in the band just UNDER the trigger and
    hasn't broken out yet. Returns [{symbol, price, pct_below_50d_high, vol_ratio}] nearest first."""
    import numpy as np  # noqa: F401
    import pandas as pd
    from app.services.maximizer_sleeves import BREAKOUT
    held_syms = held_syms or set()
    try:
        from app.services.scanner import _EXCLUDED_SET
        excluded = set(_EXCLUDED_SET)
    except Exception:
        excluded = set()
    buffer = BREAKOUT["buffer"]
    mom_min = BREAKOUT["mom_min"]
    NEAR_BAND = 0.03  # within 3% below the prior 50d high
    # Same data-quality gate the ranker/entry use — a stale or split-broken series must NEVER even
    # SHOW as a candidate (a frozen, unadjusted reverse split reads as fake momentum otherwise).
    try:
        from app.services.scanner import is_series_tradeable, _universe_stale_cutoff
        _cut = _universe_stale_cutoff(data_cache)
    except Exception:
        is_series_tradeable, _cut = (lambda *_a, **_k: True), None
    out: List[dict] = []
    for sym, df in data_cache.items():
        if sym in excluded or sym.startswith("^") or sym in held_syms:
            continue
        if df is None or len(df) < 200 or not {"close", "volume"}.issubset(df.columns):
            continue
        if not is_series_tradeable(df, _cut):
            continue   # stale / split-broken — never surface on the candidates radar
        try:
            c = df["close"]; v = df["volume"]
            price = float(c.iloc[-1]); vol = float(v.iloc[-1])
            if price < 15 or vol < 500_000:
                continue
            ma50 = c.rolling(50, min_periods=10).mean().iloc[-1]
            ma200 = c.rolling(200, min_periods=50).mean().iloc[-1]
            hi50_1 = c.rolling(50, min_periods=15).max().shift(1).iloc[-1]  # prior 50d high, excl today
            vol50 = v.rolling(50, min_periods=10).mean().iloc[-1]
            mom126 = (c.iloc[-1] / c.iloc[-127] - 1.0) if len(c) > 127 else float("nan")
        except Exception:
            continue
        if any(pd.isna(x) for x in (ma50, ma200, hi50_1, vol50, mom126)) or hi50_1 <= 0 or vol50 <= 0:
            continue
        trigger = hi50_1 * (1 + buffer)
        # Approaching: uptrend + leadership + volume building + price in the band just under the
        # trigger and not yet broken through.
        if (ma50 > ma200 and price > ma50 and mom126 > mom_min
                and hi50_1 * (1 - NEAR_BAND) < price <= trigger and vol > vol50):
            out.append({
                "symbol": sym, "price": round(price, 2),
                "pct_below_50d_high": round((hi50_1 - price) / hi50_1 * 100, 1),
                "vol_ratio": round(vol / vol50, 2),
                # Actionable extras (already computed above, previously discarded): the breakout
                # TRIGGER level (buy-above price), how far price must rise to hit it, and 6-mo
                # momentum as a strength read — so the radar table is as rich as Preserver signals.
                "trigger": round(trigger, 2),
                "pct_to_trigger": round((trigger / price - 1) * 100, 1),
                "mom_6mo_pct": round(mom126 * 100, 1),
            })
    out.sort(key=lambda x: x["pct_to_trigger"])  # nearest to firing first
    return out[:limit]


async def build_todays_actions(db) -> dict:
    """Today's Actions — the book's fills DATED TODAY only (BUY = new breakout entries, SELL =
    day-29 hold-exits). Drives the 'sync your broker' ribbon. ONLY true same-day fills appear;
    if the book didn't trade today the ribbon is empty. (Previously showed the latest fill day
    even if weeks old, so it told users to '+ Enter' names already in the book — confusing.)"""
    from app.core.database import TierFill
    from app.core.timezone import trading_today
    today = trading_today()
    rows = (await db.execute(
        select(TierFill).where(TierFill.tier == "maximizer", TierFill.fill_date == today)
    )).scalars().all()
    if not rows:
        return {"buys": [], "sells": [], "as_of": None}
    buys = [{"symbol": r.symbol, "price": r.price} for r in rows if r.side == "buy"]
    sells = [{"symbol": r.symbol, "price": r.price, "days_held": r.days_held,
              "realized_pnl": r.realized_pnl} for r in rows if r.side == "sell"]
    return {"buys": buys, "sells": sells, "as_of": today.isoformat()}


async def build_preserver_todays_actions(db) -> dict:
    """Today's PRESERVER (live t30v model book) moves — BUY = entries dated today, SELL = exits
    dated today (30% trailing / regime). Sourced from ModelPosition (the Preserver book uses the
    live model portfolio, not TierFill). Parallels build_todays_actions (Maximizer) so the email
    can show a per-book "Today's moves" for BOTH books a Maximizer subscriber mirrors."""
    from app.core.database import ModelPosition
    from app.core.timezone import trading_today
    today = trading_today()
    rows = (await db.execute(
        select(ModelPosition).where(ModelPosition.portfolio_type == "live")
    )).scalars().all()
    buys, sells = [], []
    for r in rows:
        _ed = r.entry_date.date() if getattr(r, "entry_date", None) else None
        _xd = r.exit_date.date() if getattr(r, "exit_date", None) else None
        if _ed == today and r.status == "open":
            buys.append({"symbol": r.symbol, "price": round(float(r.entry_price or 0), 2)})
        if _xd == today and r.status == "closed":
            sells.append({"symbol": r.symbol, "price": round(float(r.exit_price or 0), 2),
                          "pnl_pct": r.pnl_pct, "exit_reason": r.exit_reason})
    return {"buys": buys, "sells": sells, "as_of": today.isoformat() if (buys or sells) else None}


def _vol_scale_from_hist(bk_eq_hist) -> float:
    """The book's current Barroso vol-brake factor (target / trailing realized vol, capped 1.0)
    — SAME formula as MaximizerBook._vol_scale. 1.0 until warm."""
    try:
        import pandas as pd
        if not bk_eq_hist or len(bk_eq_hist) < 21:
            return 1.0
        eq = pd.Series(bk_eq_hist[-21:])
        rv = float(eq.pct_change().std() * (252 ** 0.5))
        if rv <= 0 or rv != rv:
            return 1.0
        return round(min(1.0, 0.20 / rv), 2)
    except Exception:
        return 1.0


async def build_tier_book(db, tier: str, capital: float, data_cache: dict,
                          trailing_stop_pct: float = 30.0) -> Optional[dict]:
    """Capital-scaled MIRROR of a tier's model book. Scales the book's positions to the user's
    capital (implied_shares = book_shares × capital/book_value) so their portfolio auto-mirrors
    the book with zero per-trade entry. Maximizer = breakout book (day-X/29 exits); Preserver =
    live t30v model book (30% trailing). Returns None if the book has no data."""
    from app.core.database import MaximizerBookSnapshot, ModelPosition, ModelPortfolioSnapshot

    capital = float(capital or 100000.0)
    holdings: List[dict] = []
    invested = 0.0
    book_cash = 0.0
    as_of = None
    regime = None
    book_equity = None
    preserver_exposure = None  # set in the preserver branch; drives the cash-raise overlay
    book_vol_scale = None      # maximizer only: current Barroso vol-brake exposure

    if tier == "maximizer":
        snap = (await db.execute(
            select(MaximizerBookSnapshot).order_by(MaximizerBookSnapshot.snapshot_date.desc()).limit(1)
        )).scalars().first()
        if not snap or not isinstance(snap.positions_json, dict):
            return None
        pj = snap.positions_json
        positions = pj.get("positions", []) or []
        book_cash = float(pj.get("bk_cash") or 0.0)
        as_of, regime = snap.snapshot_date, snap.regime
        book_equity = float(snap.equity) if snap.equity else None
        book_vol_scale = _vol_scale_from_hist(pj.get("bk_eq_hist"))
        await _load_prices([p.get("symbol") for p in positions if p.get("symbol")], data_cache)
        for p in positions:
            sym = p.get("symbol")
            if not sym:
                continue
            entry = float(p.get("entry") or 0) or 0.0
            cur = _current_price(sym, data_cache, entry)
            shares = float(p.get("shares") or 0)
            val = shares * cur
            invested += val
            days_held = int(p.get("days_held") or 0)
            hold = int(p.get("hold") or BREAKOUT_HOLD)
            days_left = max(0, hold - days_held)
            # entry date ≈ days_held trading days ago (so the chart's entry marker positions).
            entry_date = (_date.today() - _timedelta(days=int(round(days_held * 7 / 5)))).isoformat()
            holdings.append({
                "symbol": sym, "shares": shares, "price": round(cur, 2),
                "entry_price": round(entry, 2), "value": val, "source": "breakout",
                "entry_date": entry_date,
                "exit_rule": "hold", "days_held": days_held, "hold_days": hold,
                "days_left": days_left, "exit_date_approx": _approx_exit_date(days_left),
                "pnl_pct": round((cur / entry - 1) * 100, 1) if entry else 0.0,
                "is_new": days_held == 0,   # entered today
            })
    else:  # preserver (and any non-maximizer) = live t30v model book
        rows = (await db.execute(
            select(ModelPosition).where(
                ModelPosition.portfolio_type == "live", ModelPosition.status == "open")
        )).scalars().all()
        snap = (await db.execute(
            select(ModelPortfolioSnapshot).where(ModelPortfolioSnapshot.portfolio_type == "live")
            .order_by(ModelPortfolioSnapshot.snapshot_date.desc()).limit(1)
        )).scalars().first()
        if not rows and not snap:
            return None
        book_cash = float(snap.cash) if snap and snap.cash is not None else 0.0
        as_of = snap.snapshot_date if snap else None
        book_equity = float(snap.total_value) if snap and snap.total_value else None
        # Preserver is the t30v names at the book's REGIME EXPOSURE (cash-raise in capitulation).
        # Read the Preserver book's exposure (1.0 normally, 0.25 in capitulation) + its own
        # exposure-adjusted equity — so the book view is genuinely Preserver, not raw Core.
        from app.core.database import PreserverBookSnapshot
        _psnap = (await db.execute(
            select(PreserverBookSnapshot).order_by(PreserverBookSnapshot.snapshot_date.desc()).limit(1)
        )).scalars().first()
        if _psnap and isinstance(_psnap.positions_json, dict):
            try:
                preserver_exposure = float(_psnap.positions_json.get("exposure", 1.0))
            except (TypeError, ValueError):
                preserver_exposure = 1.0
            if _psnap.equity:
                book_equity = float(_psnap.equity)
            if _psnap.snapshot_date:
                as_of = _psnap.snapshot_date
        await _load_prices([r.symbol for r in rows], data_cache)
        _today = _date.today()
        for r in rows:
            entry = float(r.entry_price or 0) or 0.0
            cur = _current_price(r.symbol, data_cache, entry)
            val = float(r.shares or 0) * cur
            invested += val
            hwm = max(entry, float(r.highest_price or 0) or entry, cur)
            stop = hwm * (1 - trailing_stop_pct / 100.0)
            _edate = r.entry_date.date() if getattr(r, "entry_date", None) else None
            holdings.append({
                "symbol": r.symbol, "shares": float(r.shares or 0), "price": round(cur, 2),
                "entry_price": round(entry, 2), "value": val, "source": "preserver",
                "entry_date": _edate.isoformat() if _edate else None,
                "exit_rule": "trailing", "trailing_stop_pct": trailing_stop_pct,
                "trailing_stop_level": round(stop, 2),
                # HWM the trailing stop rides off (max of entry, stored high, current) — so the
                # chart/modal can show it and confirm the 30% trail is off the HIGH, not entry.
                "high_water_mark": round(hwm, 2),
                "pnl_pct": round((cur / entry - 1) * 100, 1) if entry else 0.0,
                "is_new": _edate == _today,   # entered today
            })

    book_value = invested + book_cash
    if book_value <= 0:
        return None

    if preserver_exposure is not None:
        # PRESERVER: hold `exposure` of capital across the t30v names (proportional to their
        # book weights), the rest in cash. exposure=1.0 in normal regimes (== fully mirrored
        # Core); exposure=0.25 in capitulation (75% cash raised). This is what makes the
        # served book genuinely Preserver rather than raw t30v.
        exp = max(0.0, min(1.0, preserver_exposure))
        invested_cap = capital * exp
        cash_cap = capital * (1 - exp)
        for h in holdings:
            w = (h["value"] / invested) if invested else 0.0   # name's weight within the book
            h["implied_value"] = round(invested_cap * w, 2)
            h["implied_shares"] = round((invested_cap * w) / h["price"], 2) if h["price"] else 0.0
            h["weight_pct"] = round(w * exp * 100)              # weight of TOTAL capital (whole %, app+email consistent)
        holdings.sort(key=lambda h: -h["implied_value"])
        return {
            "tier": tier,
            "capital": round(capital, 2),
            "holdings": holdings,
            "new_today": sum(1 for h in holdings if h.get("is_new")),
            "invested_value": round(invested_cap, 2),
            "cash_value": round(cash_cap, 2),
            "cash_pct": round((1 - exp) * 100, 1),
            "invested_pct": round(exp * 100, 1),
            "exposure": round(exp, 2),
            "as_of": as_of.isoformat() if hasattr(as_of, "isoformat") else (str(as_of) if as_of else None),
            "regime": regime,
            "book_return_pct": round((book_equity / CAP0 - 1) * 100, 1) if book_equity else None,
        }

    scale = capital / book_value
    for h in holdings:
        h["implied_shares"] = round(h["shares"] * scale, 2)
        h["implied_value"] = round(h["value"] * scale, 2)
        h["weight_pct"] = round(h["value"] / book_value * 100)   # whole % (app+email consistent)
    holdings.sort(key=lambda h: -h["implied_value"])
    return {
        "tier": tier,
        "capital": round(capital, 2),
        "holdings": holdings,
        "new_today": sum(1 for h in holdings if h.get("is_new")),
        "invested_value": round(invested * scale, 2),
        "cash_value": round(book_cash * scale, 2),
        "cash_pct": round(book_cash / book_value * 100, 1),
        "invested_pct": round(invested / book_value * 100, 1),
        "as_of": as_of.isoformat() if hasattr(as_of, "isoformat") else (str(as_of) if as_of else None),
        "regime": regime,
        "vol_scale": book_vol_scale,   # maximizer vol-target exposure gauge (None for preserver)
        # Since-inception return of the model book (live shadow window — label as such in UI).
        "book_return_pct": round((book_equity / CAP0 - 1) * 100, 1) if book_equity else None,
    }


async def tier_public_summary(db, tier: str) -> Optional[dict]:
    """FREE-tier proof payload: a tier's current open-book COUNTS + aggregate performance, with
    NO names, prices, weights, or exit levels. Snapshot/DB-only — reads the same book snapshots
    build_tier_book does and computes book_return_pct / new_today / exposure identically, but
    emits zero position detail and needs NO price data (parquet/PITFWU) so it runs cheaply on the
    API Lambda and can never leak an actionable name. (project_free_first_spec §2/§4)"""
    from app.core.database import (MaximizerBookSnapshot, ModelPosition,
                                   PreserverBookSnapshot)
    from datetime import date as _d

    if tier == "maximizer":
        snap = (await db.execute(
            select(MaximizerBookSnapshot).order_by(MaximizerBookSnapshot.snapshot_date.desc()).limit(1)
        )).scalars().first()
        if not snap or not isinstance(snap.positions_json, dict):
            return None
        pj = snap.positions_json
        positions = pj.get("positions", []) or []
        book_equity = float(snap.equity) if snap.equity else None
        return {
            "tier": "maximizer",
            "holdings_count": len(positions),
            "new_today": sum(1 for p in positions if int(p.get("days_held") or 0) == 0),
            "book_return_pct": round((book_equity / CAP0 - 1) * 100, 1) if book_equity else None,
            "exposure": _vol_scale_from_hist(pj.get("bk_eq_hist")),
            "regime": snap.regime,
            "as_of": snap.snapshot_date.isoformat() if snap.snapshot_date else None,
        }

    # preserver (and any non-maximizer): live t30v model book + Preserver exposure snapshot
    rows = (await db.execute(
        select(ModelPosition).where(
            ModelPosition.portfolio_type == "live", ModelPosition.status == "open")
    )).scalars().all()
    psnap = (await db.execute(
        select(PreserverBookSnapshot).order_by(PreserverBookSnapshot.snapshot_date.desc()).limit(1)
    )).scalars().first()
    if not rows and not psnap:
        return None
    exposure, book_equity, as_of = 1.0, None, None
    if psnap and isinstance(psnap.positions_json, dict):
        try:
            exposure = max(0.0, min(1.0, float(psnap.positions_json.get("exposure", 1.0))))
        except (TypeError, ValueError):
            exposure = 1.0
        if psnap.equity:
            book_equity = float(psnap.equity)
        as_of = psnap.snapshot_date
    _today = _d.today()
    return {
        "tier": "preserver",
        "holdings_count": len(rows),
        "new_today": sum(1 for r in rows if getattr(r, "entry_date", None)
                         and r.entry_date.date() == _today),
        "book_return_pct": round((book_equity / CAP0 - 1) * 100, 1) if book_equity else None,
        "exposure": round(exposure, 2),
        "cash_pct": round((1 - exposure) * 100, 1),
        "regime": None,
        "as_of": as_of.isoformat() if hasattr(as_of, "isoformat") else (str(as_of) if as_of else None),
    }


async def current_book_phase(db) -> Optional[dict]:
    """Dynamic 'where we are right now' readout from the live book's OWN daily equity — a readout
    of the present, never a claim, so it stays honest and swings positive on its own when the book
    recovers. Below the trailing peak → soft patch (down X% over N weeks); at/near a new high off a
    recent low → upswing (up X% off the low). Uses the Preserver book series (the base both tiers
    hold, longest history). (project_free_first_spec — honest dynamic proof.)"""
    from app.core.database import PreserverBookSnapshot

    rows = (await db.execute(
        select(PreserverBookSnapshot).order_by(PreserverBookSnapshot.snapshot_date.asc())
    )).scalars().all()
    series = [(r.snapshot_date, float(r.equity)) for r in rows if r.equity]
    if len(series) < 5:
        return None
    dates = [d for d, _ in series]
    eq = [e for _, e in series]
    last = eq[-1]

    def _dur(i):
        days = max(1, (dates[-1] - dates[i]).days)
        if days >= 55:
            m = max(1, round(days / 30.4))
            return f"{m} month" + ("s" if m != 1 else "")
        w = max(1, round(days / 7))
        return f"{w} week" + ("s" if w != 1 else "")

    # trailing peak (last occurrence of the running max) and its date
    peak, peak_i = eq[0], 0
    for i, e in enumerate(eq):
        if e >= peak:
            peak, peak_i = e, i
    dd = last / peak - 1.0

    if dd <= -0.005:  # currently in a drawdown from the peak → soft patch
        return {
            "phase": "soft_patch",
            "pct": round(dd * 100, 1),
            "duration": _dur(peak_i),
            "since": dates[peak_i].isoformat() if hasattr(dates[peak_i], "isoformat") else str(dates[peak_i]),
            "text": f"Right now we're about {_dur(peak_i)} into a soft patch — the book is "
                    f"{abs(round(dd * 100, 1))}% off its high. This is what riding momentum with a "
                    f"floor looks like in a down stretch; the edge is measured over full cycles.",
        }
    # at/near a new high → measure the upswing off the lowest point of the run
    trough, trough_i = last, len(eq) - 1
    for i in range(len(eq) - 1, -1, -1):
        if eq[i] <= trough:
            trough, trough_i = eq[i], i
    up = last / trough - 1.0 if trough else 0.0
    return {
        "phase": "upswing",
        "pct": round(up * 100, 1),
        "duration": _dur(trough_i),
        "since": dates[trough_i].isoformat() if hasattr(dates[trough_i], "isoformat") else str(dates[trough_i]),
        "text": f"Right now we're about {_dur(trough_i)} into an upswing — the book is up "
                f"{round(up * 100, 1)}% off its recent low.",
    }


async def apply_tier_serving(
    db, cached: dict, tier: str, data_cache: dict, buy_signals: List[dict],
) -> dict:
    """Return the tier overlay to merge into the dashboard payload:
      {buy_signals, tier, signal_source, exit_rule, tier_note, missed_opportunities?}.
    Preserver: passthrough t30v names + capitulation exposure note.
    Maximizer + rotating_bull: swap to the breakout book. Else: Preserver base.
    Maximizer always gets breakout-based missed-opps (real closed breakout winners).
    Caller only invokes this when tier_serving_enabled().
    """
    regime = (cached.get("regime_forecast") or {}).get("current_regime") or ""

    # "Signals" = NEW buy signals you don't already hold. Names already in the model
    # book live in the mirror-book / positions view, not the new-signal list — the
    # same definition the daily email and the grounded briefing use, so the portal,
    # the email, and the blurb all describe the identical set.
    try:
        from app.core.database import ModelPosition as _MP
        _held = set((await db.execute(
            select(_MP.symbol).where(
                _MP.portfolio_type == "live", _MP.status == "open")
        )).scalars().all())
    except Exception:
        _held = set()

    # Stamp the Preserver base list (used by Preserver, and by Maximizer when out of rotating).
    preserver_signals = []
    for s in buy_signals:
        if s.get("symbol") in _held:
            continue
        card = dict(s)
        card["source"] = "preserver"
        card["exit_rule"] = "trailing"
        preserver_signals.append(card)

    if tier == "maximizer":
        missed = await build_maximizer_missed(db)
        # Prefer the AI-generated daily briefing cached in the latest book snapshot (worker
        # writes it, anti-repetition); fall back to the templated strings below if absent.
        ai_brief = None
        try:
            from app.core.database import MaximizerBookSnapshot
            _bsnap = (await db.execute(
                select(MaximizerBookSnapshot).order_by(MaximizerBookSnapshot.snapshot_date.desc()).limit(1)
            )).scalars().first()
            if _bsnap and isinstance(_bsnap.positions_json, dict):
                ai_brief = _bsnap.positions_json.get("briefing")
        except Exception:
            ai_brief = None
        # ADDITIVE serving (Aug 2026): a Maximizer subscriber sees BOTH books, delineated —
        # the Preserver base signals (`buy_signals`) AND the breakout book (`breakout_book`) —
        # rather than a regime swap. The breakout book is always returned (held names counting
        # down + any fresh breakouts); outside rotating_bull it simply holds/ages with no new
        # entries. This matches the price story (base + breakout add-on) and keeps the add-on's
        # value visible in every regime.
        breakout = await build_maximizer_breakout_view(db, data_cache) or []
        held = sum(1 for c in breakout if c.get("status") == "holding")
        fresh = sum(1 for c in breakout if c.get("status") == "new")
        if regime == ROTATING:
            ctx = (
                f"Rotating-bull momentum is broad — your Maximizer breakout book is riding "
                f"{held} name{'s' if held != 1 else ''} into their hold windows"
                f"{f' and added {fresh} today' if fresh else ''}, shown alongside the Preserver "
                f"base signals. Each breakout sells on time at day 29, no trailing stop."
            )
            note = (
                "Rotating-bull: you're seeing both books — the Preserver base signals (30% "
                "trailing) and your Maximizer breakout book (same-day entries held 29 trading "
                "days; each card shows its day X/29 countdown). Breakouts sell on time, not on a stop."
            )
        elif held:
            ctx = (
                f"Out of rotating-bull — breakout hunting is paused, so no new breakout entries. "
                f"Your breakout book holds {held} name{'s' if held != 1 else ''} winding down to "
                f"their day-29 exits, shown alongside the Preserver base signals (30% trailing)."
            )
            note = (
                "Not a rotating-bull regime: breakout hunting is paused. Your breakout book winds "
                "down to its day-29 exits; new buys follow the Preserver base (30% trailing). Both "
                "books are shown."
            )
        else:
            ctx = (
                "Out of rotating-bull — breakout hunting is paused and the breakout book is empty. "
                "You're on the Preserver base signals (30% trailing) until momentum broadens."
            )
            note = (
                "Not a rotating-bull regime: breakout hunting is paused and your breakout book is "
                "empty. New buys follow the Preserver base (30% trailing) until momentum broadens."
            )
        return {
            "buy_signals": preserver_signals,
            "breakout_book": breakout,
            "tier": "maximizer",
            "signal_source": "both",
            "exit_rule": "trailing",
            "missed_opportunities": missed,
            "market_context": ai_brief or ctx,
            "tier_note": note,
        }
    note = None
    if regime in CAPITULATION:
        note = (
            "Capitulation regime: the Preserver overlay is defensive — raise cash toward "
            "~25% exposure and let the trailing stops do their job. New buys are paused "
            "until momentum turns."
        )
    out = {
        "buy_signals": preserver_signals,
        "tier": tier,
        "signal_source": "preserver",
        "exit_rule": "trailing",
        "tier_note": note,
    }
    if tier == "maximizer":
        # A Maximizer user outside rotating_bull still gets breakout-based missed-opps (the
        # breakout winners accumulate across rotating spells, worth surfacing any regime).
        out["missed_opportunities"] = await build_maximizer_missed(db)
    else:
        # Preserver users see the breakout winners as an UPSELL ("what Maximizer caught")
        # — a separate block, their own trailing-stop missed-opps stay intact.
        out["upsell_missed"] = await build_maximizer_missed(db)
    return out
