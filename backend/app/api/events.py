"""Per-user usage event logging.

POST /api/events accepts a batch of events from the frontend. Authenticated
(must be logged in). The frontend's useEventLogger hook batches events and
flushes via sendBeacon on unload or every N events / N seconds.

Volume estimate at current scale (~100 active subs × 50 events/day) is
~5K events/day ≈ 1.8M rows/year ≈ ~360 MB. Trivial for RDS. If volume
grows, add a TTL job to delete events older than ~1 year — they're
behavioral telemetry, not authoritative records.
"""
import json
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import UserEvent, User, get_db
from app.core.security import get_current_user, get_admin_user, get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter()


# Max payload length we'll accept per event. Anything bigger gets truncated.
_MAX_PAYLOAD_LEN = 4 * 1024  # 4 KB JSON
_MAX_PATH_LEN = 250
_MAX_UA_LEN = 250


class EventIn(BaseModel):
    """One event from the client batch."""
    event_type: str = Field(..., min_length=1, max_length=64)
    payload: Optional[dict] = None
    path: Optional[str] = None
    session_id: Optional[str] = None
    # Client-side timestamp (ISO). Server timestamp is the authoritative one
    # but client_ts is useful for measuring client→server latency.
    client_ts: Optional[str] = None


class EventBatch(BaseModel):
    events: List[EventIn] = Field(..., max_length=50)


@router.post("/log")
async def log_events(
    batch: EventBatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a batch of usage events from the authenticated user. Always
    returns 200 (with count) — never fail the client on logging errors;
    we'd rather lose a batch than break the UX."""
    if not batch.events:
        return {"logged": 0}

    ip = get_client_ip(request)
    ua = (request.headers.get("user-agent") or "")[:_MAX_UA_LEN]
    now = datetime.utcnow()
    inserted = 0
    for ev in batch.events:
        try:
            payload_str = None
            if ev.payload is not None:
                payload_str = json.dumps(ev.payload, default=str)[:_MAX_PAYLOAD_LEN]
            row = UserEvent(
                user_id=user.id,
                session_id=(ev.session_id or "")[:64] or None,
                event_type=ev.event_type[:64],
                payload_json=payload_str,
                path=(ev.path or "")[:_MAX_PATH_LEN] or None,
                ip=ip[:64] if ip else None,
                user_agent=ua or None,
                created_at=now,
            )
            db.add(row)
            inserted += 1
        except Exception as e:
            logger.warning(f"Skipping bad event for user {user.id}: {e}")
    try:
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to commit event batch: {e}")
        return {"logged": 0, "error": "commit_failed"}
    return {"logged": inserted}


# ─── Admin: per-user activity feed ───────────────────────────────────────


@router.get("/admin/users/{user_id}/activity")
async def admin_user_activity(
    user_id: str,
    limit: int = 200,
    event_type: Optional[str] = None,
    _admin = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a user's recent activity feed (most recent first). Used by
    the admin UI for support and behavioral analysis."""
    from sqlalchemy import select, desc
    q = select(UserEvent).where(UserEvent.user_id == user_id)
    if event_type:
        q = q.where(UserEvent.event_type == event_type)
    q = q.order_by(desc(UserEvent.created_at)).limit(min(limit, 1000))
    rows = (await db.execute(q)).scalars().all()
    return {
        "user_id": user_id,
        "count": len(rows),
        "events": [
            {
                "id": r.id,
                "event_type": r.event_type,
                "payload": json.loads(r.payload_json) if r.payload_json else None,
                "path": r.path,
                "session_id": r.session_id,
                "created_at": r.created_at.isoformat(),
                "user_agent": r.user_agent,
            } for r in rows
        ],
    }


@router.get("/admin/summary")
async def admin_event_summary(
    hours: int = 24,
    _admin = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate event-type counts over the last N hours. Useful for a
    quick dashboard of what's getting used."""
    from sqlalchemy import select, func, desc
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    q = (
        select(UserEvent.event_type, func.count().label("n"))
        .where(UserEvent.created_at >= since)
        .group_by(UserEvent.event_type)
        .order_by(desc("n"))
    )
    rows = (await db.execute(q)).all()
    return {
        "hours": hours,
        "since": since.isoformat(),
        "by_event_type": [{"event_type": r[0], "count": r[1]} for r in rows],
    }
