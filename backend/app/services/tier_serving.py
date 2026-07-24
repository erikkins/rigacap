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

# Regimes where the Preserver overlay raises cash (exposure -> ~25%). Mirrors
# preserver_service CAP / maximizer_blend_certify CAPIT.
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}
ROTATING = "rotating_bull"
BREAKOUT_HOLD = 29  # trading days (maximizer_sleeves.BREAKOUT["hold"])


def tier_serving_enabled() -> bool:
    """Global kill-switch. Off => callers serve the legacy Core payload unchanged."""
    return os.getenv("TIER_SERVING", "").lower() in ("1", "true", "yes")


def resolve_tier(subscription, is_admin: bool = False, preview_tier: Optional[str] = None) -> str:
    """'preserver' | 'maximizer'. Entitlement = paid add-on OR admin comp. Admins may
    force a view with ?preview_tier= for dark-launch verification."""
    if preview_tier in ("preserver", "maximizer"):
        return preview_tier
    if subscription is not None and (
        getattr(subscription, "has_maxpp_addon", False) or getattr(subscription, "compmax", False)
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
    """The breakout BOOK as buy_signal-shaped cards: HELD positions (day X/29 countdown)
    first, then today's fresh breakout buys. Reads the shadow tables only."""
    from app.core.database import MaximizerBookSnapshot, MaximizerSignal

    # Latest book snapshot -> held breakout positions.
    snap = (await db.execute(
        select(MaximizerBookSnapshot).order_by(MaximizerBookSnapshot.snapshot_date.desc()).limit(1)
    )).scalars().first()

    held: List[dict] = []
    held_syms = set()
    if snap and isinstance(snap.positions_json, dict):
        held_syms = {p.get("symbol") for p in snap.positions_json.get("positions", []) if p.get("symbol")}
        await _load_prices(list(held_syms), data_cache)
        for p in snap.positions_json.get("positions", []):
            sym = p.get("symbol")
            if not sym:
                continue
            entry = float(p.get("entry") or 0) or 0.0
            days_held = int(p.get("days_held") or 0)
            hold = int(p.get("hold") or BREAKOUT_HOLD)
            days_left = max(0, hold - days_held)
            cur = _current_price(sym, data_cache, entry)
            pnl_pct = ((cur / entry - 1) * 100) if entry else 0.0
            held.append({
                "symbol": sym,
                "price": round(cur, 2),
                "entry_price": round(entry, 2),
                "source": "breakout",
                "exit_rule": "hold",
                "hold_days": hold,
                "days_held": days_held,
                "days_left": days_left,
                "exit_date_approx": _approx_exit_date(days_left),
                "pnl_pct": round(pnl_pct, 1),
                "status": "holding",
                "is_fresh": False,
                "in_user_position": False,
                # display-compat defaults for the buy-card renderer
                "ensemble_score": 0,
                "signal_strength_label": "Holding",
            })
        held.sort(key=lambda c: c["days_left"])  # nearest to exit first

    # Today's fresh breakout buys (latest signal_date, source=breakout, active) that aren't
    # already held.
    latest = (await db.execute(
        select(MaximizerSignal.signal_date)
        .where(MaximizerSignal.source == "breakout")
        .order_by(MaximizerSignal.signal_date.desc()).limit(1)
    )).scalar_one_or_none()
    fresh: List[dict] = []
    if latest is not None:
        rows = (await db.execute(
            select(MaximizerSignal).where(
                MaximizerSignal.signal_date == latest,
                MaximizerSignal.source == "breakout",
                MaximizerSignal.status == "active",
            )
        )).scalars().all()
        for r in rows:
            if r.symbol in held_syms:
                continue
            hold = int(r.hold_days or BREAKOUT_HOLD)
            fresh.append({
                "symbol": r.symbol,
                "price": round(float(r.price or 0), 2),
                "source": "breakout",
                "exit_rule": "hold",
                "hold_days": hold,
                "days_held": 0,
                "days_left": hold,
                "exit_date_approx": _approx_exit_date(hold),
                "dollar_volume": float(r.dollar_volume or 0),
                "status": "new",
                "is_fresh": True,          # act today — breakout signal is a same-day cross
                "in_user_position": False,
                "ensemble_score": 0,
                "signal_strength_label": "New breakout",
            })
        fresh.sort(key=lambda c: -c.get("dollar_volume", 0))

    return fresh + held  # new buys first, then the held book


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

    if tier == "maximizer":
        missed = await build_maximizer_missed(db)
        if regime == ROTATING:
            breakout = await build_maximizer_breakout_view(db, data_cache)
            # Faithful only if the shadow book has data; otherwise fall back to the Preserver
            # base rather than showing an empty screen.
            if breakout:
                return {
                    "buy_signals": breakout,
                    "tier": "maximizer",
                    "signal_source": "breakout",
                    "exit_rule": "hold",
                    "missed_opportunities": missed,
                    "tier_note": (
                        "Rotating-bull regime: your Maximizer book is hunting breakouts. Each "
                        "name is a same-day entry held ~29 trading days, then sold on time (no "
                        "trailing stop). Held names show their day X/29 countdown."
                    ),
                }

    # Preserver base (also Maximizer in every non-rotating regime — Option B). Stamp each
    # card source='preserver' so an entry scopes the trade to the trailing-stop rule.
    preserver_signals = []
    for s in buy_signals:
        card = dict(s)
        card["source"] = "preserver"
        card["exit_rule"] = "trailing"
        preserver_signals.append(card)
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
