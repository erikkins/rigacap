"""Email tracking helpers: token minting, pixel injection, link wrapping.

EmailService imports these to instrument outgoing emails. The pattern:

    from app.services.email_tracking_service import prepare_tracked_email
    html, token = await prepare_tracked_email(
        html=raw_html,
        email_address="...",
        email_type="daily_digest",
        user_id=user.id,
    )
    # ... actually send html ...

After prepare_tracked_email() returns, a 'sent' row is in email_events,
the HTML has the tracking pixel embedded, and every <a href="..."> that
points at a public URL has been wrapped through /api/email/click/{token}.
"""
import logging
import re
import uuid
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import EmailEvent, async_session

logger = logging.getLogger(__name__)

# Default base URL — EmailService can pass a different one if needed.
# Tracking endpoints live under /api/email/track and /api/email/click.
_BASE_URL = "https://api.rigacap.com"

# Hrefs we should NOT rewrite:
#   - mailto:, tel:, javascript:, fragment anchors
#   - One-click unsubscribe links (RFC 8058 — must be the direct URL)
#   - Already-tracked links (idempotent if called twice)
_SKIP_HREF_PATTERNS = (
    "mailto:", "tel:", "javascript:", "#",
)
_SKIP_HREF_SUBSTRINGS = (
    "/unsubscribe", "list-unsubscribe", "/api/email/click/",
)


def make_email_token() -> str:
    """Mint a fresh tracking token (URL-safe, 32 hex chars)."""
    return uuid.uuid4().hex


async def record_sent(
    token: str,
    email_address: str,
    email_type: str,
    user_id=None,
    db: Optional[AsyncSession] = None,
) -> None:
    """Insert the 'sent' row that anchors the (token, email_address,
    email_type, user_id) tuple. Pixel-open and click events later look
    up this row to inherit identity."""
    own_session = db is None
    try:
        session = async_session() if own_session else db
        if own_session:
            async with session as s:
                s.add(EmailEvent(
                    token=token,
                    email_address=email_address[:255] if email_address else None,
                    email_type=email_type[:64] if email_type else None,
                    user_id=user_id,
                    event_type="sent",
                    created_at=datetime.utcnow(),
                ))
                await s.commit()
        else:
            db.add(EmailEvent(
                token=token,
                email_address=email_address[:255] if email_address else None,
                email_type=email_type[:64] if email_type else None,
                user_id=user_id,
                event_type="sent",
                created_at=datetime.utcnow(),
            ))
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to record email sent ({email_type} -> {email_address}): {e}")


def add_tracking_pixel(html: str, token: str, base_url: str = _BASE_URL) -> str:
    """Append a 1x1 transparent pixel to the end of the email HTML. Most
    clients (Gmail, Apple Mail, Outlook web) load images eagerly enough
    that this fires on view. Image-blocking clients (some Outlook
    configurations) result in a false-negative, which is fine for
    relative comparisons."""
    pixel = (
        f'<img src="{base_url}/api/email/track/{token}.gif" '
        f'width="1" height="1" alt="" style="display:block;border:0;outline:0;width:1px;height:1px;" />'
    )
    if "</body>" in html.lower():
        # Insert just before </body> so the pixel renders last
        return re.sub(r"</body>", pixel + "</body>", html, count=1, flags=re.IGNORECASE)
    return html + pixel


def wrap_links(html: str, token: str, base_url: str = _BASE_URL) -> str:
    """Rewrite every <a href="..."> in the HTML to redirect through
    /api/email/click/{token} so clicks get logged. Skips mailto:/tel:/
    javascript: links, anchor fragments, unsubscribe links (must stay
    direct per RFC 8058), and any link already going through the
    tracking endpoint."""
    def _maybe_wrap(match: re.Match) -> str:
        full = match.group(0)
        url = match.group(1)
        # Decoded check — href values may have HTML entities
        url_check = url.replace("&amp;", "&").strip()
        if not url_check:
            return full
        if any(url_check.lower().startswith(p) for p in _SKIP_HREF_PATTERNS):
            return full
        if any(s in url_check.lower() for s in _SKIP_HREF_SUBSTRINGS):
            return full
        wrapped = f"{base_url}/api/email/click/{token}?u={quote(url_check, safe='')}"
        return full.replace(url, wrapped, 1)
    # Match href="..." or href='...' — keep the surrounding quotes intact
    return re.sub(r'href=["\']([^"\']+)["\']', _maybe_wrap, html)


async def prepare_tracked_email(
    html: str,
    email_address: str,
    email_type: str,
    user_id=None,
    base_url: str = _BASE_URL,
    db: Optional[AsyncSession] = None,
) -> Tuple[str, str]:
    """One-shot instrumentation: mint token, record 'sent', inject pixel,
    wrap links. Returns (instrumented_html, token).

    Falls back to (original_html, token) if any step fails — tracking is
    observation, not load-bearing for the actual email send.
    """
    token = make_email_token()
    try:
        await record_sent(token, email_address, email_type, user_id=user_id, db=db)
    except Exception as e:
        logger.warning(f"prepare_tracked_email: record_sent failed, continuing without tracking: {e}")
        return html, token
    try:
        html_out = wrap_links(html, token, base_url=base_url)
        html_out = add_tracking_pixel(html_out, token, base_url=base_url)
        return html_out, token
    except Exception as e:
        logger.warning(f"prepare_tracked_email: instrumentation failed: {e}")
        return html, token
