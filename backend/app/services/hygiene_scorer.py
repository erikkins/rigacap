"""
Hygiene confidence scorer.

Classifies every flagged symbol-metadata anomaly into one of three tiers:

  AUTO       — confidence high enough to execute without human review.
                Acted on during the nightly hygiene run; surfaces in the
                admin queue only as a read-only audit row.
  RECOMMEND  — system has a strong opinion (delist / rename / migrate)
                but wants a one-click confirmation. Shows in the queue
                with a pre-filled action.
  EXCEPTION  — held by a user, or the system cannot decide. Requires
                human judgment.

The scorer is intentionally rule-driven first; AI verdict (Claude triage
of recent news) is layered on top when present, captured nightly as a
SymbolMetadataEvent so the admin queue never has to wait for an LLM call.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, and_, desc

from app.core.database import (
    async_session,
    SymbolMetadata,
    SymbolMetadataEvent,
    Position,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tiers / actions

TIER_AUTO = "AUTO"
TIER_RECOMMEND = "RECOMMEND"
TIER_EXCEPTION = "EXCEPTION"

ACTION_DELIST = "delist"
ACTION_RENAME = "rename"
ACTION_MIGRATE = "migrate"        # ticker reuse: drop history, adopt new asset_id
ACTION_RESTORE = "restore"        # false alarm — re-activate
ACTION_NEEDS_HUMAN = "needs_human"

# Days-missing thresholds
DAYS_AUTO = 14   # >= → AUTO-eligible (matches existing AUTO_QUARANTINE_DAYS)
DAYS_RECO = 7    # >= → at least RECOMMEND (worth surfacing)


@dataclass
class QueueItem:
    symbol: str
    category: str                     # "missing" | "reuse"
    tier: str                         # AUTO | RECOMMEND | EXCEPTION
    recommended_action: str           # delist / rename / migrate / restore / needs_human
    reasoning: str
    days_missing: Optional[int] = None
    in_open_position: bool = False
    status: Optional[str] = None
    last_bar_date: Optional[str] = None
    last_close: Optional[float] = None
    company_name: Optional[str] = None
    ai_verdict: Optional[str] = None
    ai_summary: Optional[str] = None
    # ticker-reuse only
    old_asset_id: Optional[str] = None
    new_asset_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Classification helpers

def _classify_missing_row(
    row: dict,
    ai_verdict: Optional[str],
    ai_summary: Optional[str],
) -> Tuple[str, str, str]:
    """
    Decide tier + recommended action + reasoning for one missing-in-Alpaca row.

    Inputs from `symbol_metadata_service.diagnose_missing()`:
        symbol, days_missing, in_open_position, status, suggested_action
    Plus optional AI verdict from a SymbolMetadataEvent('ai_triage') run.
    """
    sym = row["symbol"]
    days = row.get("days_missing") or 0
    held = row.get("in_open_position", False)

    # Rule 1: held positions never auto-act. Operator must close first.
    if held:
        return (
            TIER_EXCEPTION,
            ACTION_NEEDS_HUMAN,
            f"User holds open position in {sym} — close manually before delisting.",
        )

    # Rule 2: >= 14 days missing → AUTO-eligible.
    # The 14-day window is the same threshold the verify pass uses for
    # auto-quarantine; by this point Alpaca has had both an active-list
    # and inactive-list miss for two full trading weeks, which is
    # overdetermined for any transient glitch.
    if days >= DAYS_AUTO:
        if ai_verdict == "RENAME":
            return (
                TIER_RECOMMEND,
                ACTION_RENAME,
                f"Missing {days}d, AI suggests rename — supply new ticker.",
            )
        if ai_verdict == "KEEP":
            return (
                TIER_EXCEPTION,
                ACTION_NEEDS_HUMAN,
                f"Missing {days}d but AI says KEEP — review.",
            )
        # DELIST verdict, or no AI verdict at all: AUTO delist.
        why_ai = "AI=DELIST" if ai_verdict == "DELIST" else "no contrary AI verdict"
        return (
            TIER_AUTO,
            ACTION_DELIST,
            f"Missing {days}d, no user position, {why_ai}.",
        )

    # Rule 3: 7-13 days missing → RECOMMEND (likely delist, want one-click).
    if days >= DAYS_RECO:
        return (
            TIER_RECOMMEND,
            ACTION_DELIST,
            f"Missing {days}d, no user position{', AI=' + ai_verdict if ai_verdict else ''}.",
        )

    # Rule 4: < 7 days — recheck only; do not surface.
    # Returning EXCEPTION here would dump dozens of transient rows into the
    # admin queue; the caller drops these before rendering.
    return (
        TIER_EXCEPTION,
        ACTION_NEEDS_HUMAN,
        f"Missing only {days}d — auto-rechecking nightly.",
    )


def _classify_reuse_row(
    sym: str,
    old_asset_id: Optional[str],
    new_asset_id: Optional[str],
    in_open_position: bool,
) -> Tuple[str, str, str]:
    """
    Decide tier + action for an asset_id-drift (ticker reuse) row.

    Alpaca's asset_id is authoritative; a drift means the exchange has
    recycled the ticker to a different entity. Default action is
    MIGRATE: drop the old company's price history and start fresh on
    the new asset_id under the same ticker.
    """
    if in_open_position:
        return (
            TIER_EXCEPTION,
            ACTION_NEEDS_HUMAN,
            f"User holds {sym} — close position before migrating asset_id.",
        )
    return (
        TIER_AUTO,
        ACTION_MIGRATE,
        f"Alpaca asset_id changed ({old_asset_id[:8] if old_asset_id else '?'}… → "
        f"{new_asset_id[:8] if new_asset_id else '?'}…); no user position.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# AI verdict cache (persisted as SymbolMetadataEvent rows)

AI_TRIAGE_EVENT_TYPE = "ai_triage"
AI_TRIAGE_TTL_HOURS = 36  # re-run AI if older than this


async def _load_recent_ai_verdicts(symbols: List[str]) -> Dict[str, dict]:
    """
    Latest ai_triage event per symbol within TTL. Used to avoid re-calling
    Claude for symbols already triaged in this nightly window.

    Returns: {symbol: {"verdict": ..., "summary": ..., "detected_at": ...}}
    """
    if not symbols:
        return {}
    cutoff = datetime.utcnow() - timedelta(hours=AI_TRIAGE_TTL_HOURS)
    out: Dict[str, dict] = {}
    async with async_session() as db:
        result = await db.execute(
            select(SymbolMetadataEvent)
            .where(SymbolMetadataEvent.symbol.in_(symbols))
            .where(SymbolMetadataEvent.event_type == AI_TRIAGE_EVENT_TYPE)
            .where(SymbolMetadataEvent.detected_at >= cutoff)
            .order_by(SymbolMetadataEvent.symbol, desc(SymbolMetadataEvent.id))
        )
        for ev in result.scalars().all():
            if ev.symbol in out:
                continue
            try:
                details = json.loads(ev.details_json or "{}")
                out[ev.symbol] = {
                    "verdict": details.get("verdict"),
                    "summary": (details.get("summary") or "")[:600],
                    "detected_at": ev.detected_at.isoformat(),
                }
            except Exception:
                pass
    return out


async def _persist_ai_verdict(symbol: str, verdict: str, summary: str) -> None:
    async with async_session() as db:
        db.add(SymbolMetadataEvent(
            symbol=symbol,
            event_type=AI_TRIAGE_EVENT_TYPE,
            details_json=json.dumps({
                "verdict": verdict,
                "summary": (summary or "")[:600],
            }),
        ))
        await db.commit()


async def _run_ai_triage(
    symbols: List[str],
    concurrency: int = 6,
) -> Dict[str, dict]:
    """
    Run the news/AI triage path on a batch of symbols, concurrent-capped.
    Persists results so the admin queue endpoint can read without re-calling
    Claude.
    """
    if not symbols:
        return {}
    import asyncio

    # Defer the import — admin.py owns the Claude wiring. Importing at module
    # top would create a circular dependency.
    from app.api.admin import fetch_symbol_news_and_summarize

    sem = asyncio.Semaphore(concurrency)
    results: Dict[str, dict] = {}

    async def one(sym: str):
        async with sem:
            try:
                tri = await fetch_symbol_news_and_summarize(sym)
            except Exception as e:
                logger.warning(f"AI triage failed for {sym}: {e}")
                return
            verdict = (tri or {}).get("verdict") or "UNKNOWN"
            summary = (tri or {}).get("summary") or ""
            results[sym] = {"verdict": verdict, "summary": summary[:600]}
            try:
                await _persist_ai_verdict(sym, verdict, summary)
            except Exception as pe:
                logger.warning(f"persist AI verdict failed for {sym}: {pe}")

    await asyncio.gather(*(one(s) for s in symbols), return_exceptions=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points

async def score_missing(run_ai: bool = True) -> List[QueueItem]:
    """
    Build the missing-in-Alpaca queue: classify every active missing row,
    layer cached AI verdicts on, and (optionally) call Claude for any
    >=14d rows we don't already have a fresh verdict for.
    """
    from app.services.symbol_metadata_service import symbol_metadata_service
    from app.services.scanner import scanner_service

    rows = await symbol_metadata_service.diagnose_missing()
    if not rows:
        return []

    # Pre-load any AI verdicts we already have within TTL
    syms = [r["symbol"] for r in rows]
    ai_cache = await _load_recent_ai_verdicts(syms)

    # Decide which symbols need a fresh AI call: anything >= 14d, not held,
    # and not in the cache. We skip <14d rows because they're not AUTO-
    # eligible — AI doesn't change the tier verdict for those.
    need_ai = [
        r["symbol"] for r in rows
        if not r.get("in_open_position")
        and (r.get("days_missing") or 0) >= DAYS_AUTO
        and r["symbol"] not in ai_cache
    ]
    if run_ai and need_ai:
        logger.info(f"hygiene_scorer: running AI triage on {len(need_ai)} symbols")
        fresh = await _run_ai_triage(need_ai)
        ai_cache.update(fresh)

    out: List[QueueItem] = []
    for r in rows:
        sym = r["symbol"]
        ai = ai_cache.get(sym) or {}
        tier, action, reasoning = _classify_missing_row(
            r, ai.get("verdict"), ai.get("summary")
        )

        # Last-bar enrichment from in-memory pickle (only API Lambda has empty
        # cache; on Worker, this is populated).
        last_close = None
        last_bar_date = r.get("last_bar_date")
        try:
            df = scanner_service.data_cache.get(sym)
            if df is not None and len(df) > 0:
                last_close = float(df.iloc[-1].get("close", 0)) if hasattr(df.iloc[-1], 'get') else None
        except Exception:
            pass

        out.append(QueueItem(
            symbol=sym,
            category="missing",
            tier=tier,
            recommended_action=action,
            reasoning=reasoning,
            days_missing=r.get("days_missing"),
            in_open_position=bool(r.get("in_open_position")),
            status=r.get("status"),
            last_bar_date=last_bar_date,
            last_close=last_close,
            ai_verdict=ai.get("verdict"),
            ai_summary=ai.get("summary"),
        ))
    return out


async def score_reuse() -> List[QueueItem]:
    """
    Build the ticker-reuse queue: every symbol whose stored asset_id no
    longer matches Alpaca's current asset_id. Source of truth = the
    SymbolMetadata row's quarantine_reason='asset_id_changed' state plus
    the latest asset_id_changed event for the old/new UUIDs.
    """
    async with async_session() as db:
        result = await db.execute(
            select(SymbolMetadata).where(
                and_(
                    SymbolMetadata.status == "quarantined",
                    SymbolMetadata.quarantine_reason == "asset_id_changed",
                )
            )
        )
        metas = result.scalars().all()
        if not metas:
            return []

        syms = [m.symbol for m in metas]
        # Latest asset_id_changed event per symbol — gives us old/new UUIDs
        ev_res = await db.execute(
            select(SymbolMetadataEvent)
            .where(SymbolMetadataEvent.symbol.in_(syms))
            .where(SymbolMetadataEvent.event_type == "asset_id_changed")
            .order_by(SymbolMetadataEvent.symbol, desc(SymbolMetadataEvent.id))
        )
        latest_by_sym: Dict[str, dict] = {}
        for ev in ev_res.scalars().all():
            if ev.symbol in latest_by_sym:
                continue
            try:
                latest_by_sym[ev.symbol] = json.loads(ev.details_json or "{}")
            except Exception:
                latest_by_sym[ev.symbol] = {}

        # Held-position check
        held_res = await db.execute(
            select(Position.symbol)
            .where(Position.status == "open")
            .where(Position.symbol.in_(syms))
            .distinct()
        )
        held = {row[0] for row in held_res.all()}

    out: List[QueueItem] = []
    for m in metas:
        ev = latest_by_sym.get(m.symbol, {})
        old_id = ev.get("old_asset_id") or m.asset_id
        new_id = ev.get("new_asset_id")
        tier, action, reasoning = _classify_reuse_row(
            m.symbol, old_id, new_id, m.symbol in held
        )
        out.append(QueueItem(
            symbol=m.symbol,
            category="reuse",
            tier=tier,
            recommended_action=action,
            reasoning=reasoning,
            in_open_position=m.symbol in held,
            status=m.status,
            old_asset_id=old_id,
            new_asset_id=new_id,
        ))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Execution of AUTO tier — applies the recommended action and writes audit.

async def execute_auto_tier(items: List[QueueItem]) -> dict:
    """
    Apply recommended actions for every AUTO-tier item. Returns a summary:
      {"delisted": N, "migrated": M, "errors": K, "symbols": [...]}
    """
    from app.services.scanner import scanner_service

    summary = {"delisted": [], "migrated": [], "errors": []}
    auto_items = [it for it in items if it.tier == TIER_AUTO]
    if not auto_items:
        return summary

    async with async_session() as db:
        for it in auto_items:
            try:
                res = await db.execute(
                    select(SymbolMetadata).where(SymbolMetadata.symbol == it.symbol)
                )
                meta = res.scalar_one_or_none()
                if not meta:
                    summary["errors"].append({"symbol": it.symbol, "error": "no metadata row"})
                    continue

                if it.recommended_action == ACTION_DELIST:
                    meta.status = "delisted"
                    # Reason captures the AI verdict (or absence of one) so
                    # restorations later can read the audit trail.
                    if it.ai_verdict == "DELIST":
                        meta.quarantine_reason = "ai_auto_delist"
                    else:
                        meta.quarantine_reason = "auto_delist_14d_no_position"
                    meta.first_missing_at = None
                    db.add(SymbolMetadataEvent(
                        symbol=it.symbol,
                        event_type="auto_delist",
                        details_json=json.dumps({
                            "tier": it.tier,
                            "days_missing": it.days_missing,
                            "ai_verdict": it.ai_verdict,
                            "reasoning": it.reasoning,
                        }),
                    ))
                    summary["delisted"].append(it.symbol)

                elif it.recommended_action == ACTION_MIGRATE:
                    # Ticker reuse: adopt the new asset_id, reset status,
                    # drop any cached price history for this symbol so the
                    # next daily scan refetches fresh under the new entity.
                    if it.new_asset_id:
                        meta.asset_id = it.new_asset_id
                    meta.status = "active"
                    meta.quarantine_reason = None
                    meta.quarantined_at = None
                    meta.first_missing_at = None
                    db.add(SymbolMetadataEvent(
                        symbol=it.symbol,
                        event_type="ticker_reuse_migrated",
                        details_json=json.dumps({
                            "old_asset_id": it.old_asset_id,
                            "new_asset_id": it.new_asset_id,
                        }),
                    ))
                    # Drop pickle entry — old company's bars must not
                    # contaminate the new entity's indicator math.
                    try:
                        if scanner_service.data_cache and it.symbol in scanner_service.data_cache:
                            del scanner_service.data_cache[it.symbol]
                    except Exception:
                        pass
                    summary["migrated"].append(it.symbol)

                else:
                    summary["errors"].append({
                        "symbol": it.symbol,
                        "error": f"AUTO tier had unsupported action {it.recommended_action}",
                    })
            except Exception as e:
                summary["errors"].append({"symbol": it.symbol, "error": str(e)[:200]})

        await db.commit()

    return summary
