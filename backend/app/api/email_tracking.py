"""Email engagement tracking — public endpoints (no auth).

The endpoints here are hit by email clients (image fetch) and recipients
clicking through (redirect). Neither has access to our auth cookies/tokens,
so they're intentionally unauthenticated. Recipient identity comes from
the token in the URL, which we minted at send time and looked up on event.

Endpoints:
  GET /api/email/track/{token}.gif     -> 1x1 transparent GIF, logs 'opened'
  GET /api/email/click/{token}         -> redirects to ?u=<encoded-url>, logs 'clicked'

Both are best-effort: errors don't fail the response. We'd rather lose a
tracking event than break an email click for the user.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import Response, RedirectResponse
from sqlalchemy import select

from app.core.database import EmailEvent, async_session
from app.core.security import get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter()

# 43-byte 1x1 transparent GIF — smallest valid GIF that all email clients
# will fetch and discard without rendering anything visible.
_PIXEL_GIF = bytes.fromhex(
    "47494638396101000100800000ffffff00000021f90401000000002c00000000010001000002024401003b"
)


async def _log_event(token: str, event_type: str, request: Request, click_url: Optional[str] = None) -> None:
    """Best-effort write: look up the original 'sent' row to copy user_id
    and email_type forward, then append the engagement event. Never raises."""
    try:
        async with async_session() as db:
            # Find the original sent row to inherit user_id + email_type
            sent_q = await db.execute(
                select(EmailEvent)
                .where(EmailEvent.token == token, EmailEvent.event_type == 'sent')
                .limit(1)
            )
            sent_row = sent_q.scalar_one_or_none()
            ip = get_client_ip(request) if request else None
            ua = (request.headers.get("user-agent") or "")[:255] if request else None
            db.add(EmailEvent(
                token=token,
                email_address=sent_row.email_address if sent_row else None,
                email_type=sent_row.email_type if sent_row else None,
                user_id=sent_row.user_id if sent_row else None,
                event_type=event_type,
                click_url=click_url[:2000] if click_url else None,
                ip=ip[:64] if ip else None,
                user_agent=ua,
                created_at=datetime.utcnow(),
            ))
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to log email {event_type} for token {token[:8]}: {e}")


@router.get("/track/{token}.gif")
async def email_open_pixel(token: str, request: Request):
    """1x1 transparent GIF that logs 'opened' when fetched. Never fails —
    even if logging blows up, we still return the GIF so the email
    client renders cleanly."""
    await _log_event(token, "opened", request)
    return Response(
        content=_PIXEL_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, private",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/click/{token}")
async def email_click_redirect(
    token: str,
    request: Request,
    u: str = Query(..., description="URL-encoded target URL"),
):
    """Logs 'clicked' then 302-redirects to the target URL. If the URL
    looks bogus, redirect to rigacap.com root rather than 4xx (so the
    recipient still ends up somewhere usable)."""
    # Basic safety: only redirect to https:// or our own domain
    target = u.strip()
    if not (target.startswith("https://") or target.startswith("http://")):
        target = "https://rigacap.com/"
    await _log_event(token, "clicked", request, click_url=target)
    return RedirectResponse(url=target, status_code=302)
