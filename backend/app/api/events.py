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
    """Return a user's recent activity feed (most recent first), merging
    BOTH user_events (signal clicks, logins, etc.) AND email_events
    (sent/opened/clicked). Email events get the event_type prefix
    'email_' so they're trivially filterable and the frontend's
    color-coding picks them up. Used by the admin UI for support and
    behavioral analysis."""
    from sqlalchemy import select, desc
    from app.core.database import EmailEvent

    # Pull both sources, normalize to the same shape, merge + sort.
    cap = min(limit, 1000)

    user_q = select(UserEvent).where(UserEvent.user_id == user_id)
    if event_type and not event_type.startswith("email_"):
        user_q = user_q.where(UserEvent.event_type == event_type)
    user_q = user_q.order_by(desc(UserEvent.created_at)).limit(cap)
    user_rows = (await db.execute(user_q)).scalars().all()

    email_q = select(EmailEvent).where(EmailEvent.user_id == user_id)
    if event_type and event_type.startswith("email_"):
        # Map 'email_opened' filter -> EmailEvent.event_type == 'opened'
        email_q = email_q.where(EmailEvent.event_type == event_type[len("email_"):])
    email_q = email_q.order_by(desc(EmailEvent.created_at)).limit(cap)
    email_rows = (await db.execute(email_q)).scalars().all()

    items = []
    for r in user_rows:
        items.append({
            "id": f"u{r.id}",
            "source": "user",
            "event_type": r.event_type,
            "payload": json.loads(r.payload_json) if r.payload_json else None,
            "path": r.path,
            "session_id": r.session_id,
            "created_at": r.created_at,
            "user_agent": r.user_agent,
        })
    for r in email_rows:
        # Build a compact payload from the email row's structured columns
        payload = {"email_type": r.email_type}
        if r.click_url:
            payload["url"] = r.click_url
        items.append({
            "id": f"e{r.id}",
            "source": "email",
            "event_type": f"email_{r.event_type}",
            "payload": payload,
            "path": None,
            "session_id": None,
            "created_at": r.created_at,
            "user_agent": r.user_agent,
        })

    items.sort(key=lambda x: x["created_at"], reverse=True)
    items = items[:cap]
    # ISO-stringify timestamps for JSON
    for it in items:
        it["created_at"] = it["created_at"].isoformat()

    return {"user_id": user_id, "count": len(items), "events": items}


@router.get("/admin/email-engagement")
async def admin_email_engagement(
    days: int = 30,
    _admin = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate email engagement by type: sent / opened / clicked counts +
    open-rate and click-rate over the last N days.

    Caveats: Apple Mail Privacy Protection pre-fetches images, inflating
    'opened' for iOS recipients. Open rate here is best read as a
    relative signal (this campaign vs that one)."""
    from sqlalchemy import select, func
    from datetime import timedelta
    from app.core.database import EmailEvent
    since = datetime.utcnow() - timedelta(days=days)
    q = (
        select(EmailEvent.email_type, EmailEvent.event_type, func.count().label("n"))
        .where(EmailEvent.created_at >= since)
        .group_by(EmailEvent.email_type, EmailEvent.event_type)
    )
    rows = (await db.execute(q)).all()
    # Pivot to per-email_type buckets
    by_type: dict = {}
    for et, evt, n in rows:
        key = et or "(uncategorized)"
        bucket = by_type.setdefault(key, {"sent": 0, "opened": 0, "clicked": 0})
        if evt in bucket:
            bucket[evt] = n
    summary = []
    for et, b in by_type.items():
        open_rate = (b["opened"] / b["sent"]) if b["sent"] else None
        click_rate = (b["clicked"] / b["sent"]) if b["sent"] else None
        summary.append({
            "email_type": et,
            "sent": b["sent"],
            "opened": b["opened"],
            "clicked": b["clicked"],
            "open_rate": round(open_rate, 3) if open_rate is not None else None,
            "click_rate": round(click_rate, 3) if click_rate is not None else None,
        })
    summary.sort(key=lambda x: x["sent"], reverse=True)
    return {"days": days, "since": since.isoformat(), "by_email_type": summary}


@router.get("/admin/users/{user_id}/email-activity")
async def admin_user_email_activity(
    user_id: str,
    limit: int = 100,
    _admin = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-user email engagement feed: every send / open / click for this
    recipient, most recent first. Useful for support ('did they actually
    open the trial-end reminder?')."""
    from sqlalchemy import select, desc
    from app.core.database import EmailEvent
    q = (
        select(EmailEvent)
        .where(EmailEvent.user_id == user_id)
        .order_by(desc(EmailEvent.created_at))
        .limit(min(limit, 500))
    )
    rows = (await db.execute(q)).scalars().all()
    return {
        "user_id": user_id,
        "count": len(rows),
        "events": [
            {
                "id": r.id,
                "token": r.token,
                "email_type": r.email_type,
                "event_type": r.event_type,
                "click_url": r.click_url,
                "created_at": r.created_at.isoformat(),
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
