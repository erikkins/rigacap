"""SnapTrade connection lifecycle — the cost-control layer.

SnapTrade bills per connected user per day (~$1/user/day), so a user who stops being a
paying subscriber must be DEREGISTERED from SnapTrade or we pay for them in perpetuity.

`deregister()` does the two-sided cleanup:
  1. SnapTrade side — st.delete_user() removes the user + all connections (stops billing).
  2. Our side — we DON'T delete the snaptrade_users row (we keep history). We soft-status it
     to 'deregistered', stamp when/why, null the now-dead user_secret, and log a UserEvent.

Billing is stopped FIRST; the row is only soft-statused once the SnapTrade call succeeds, so a
transient API failure leaves the row 'active' and the daily reconcile sweep retries it. Safe to
call repeatedly (a row that isn't 'active' is a no-op; deleteUser swallows 404).

Callers: billing.handle_subscription_deleted (churn), the reconcile sweep (main.py), and the
user-initiated disconnect path.
"""
from __future__ import annotations

import json
import logging
import uuid as _uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _as_uuid(user_id):
    return _uuid.UUID(str(user_id)) if not isinstance(user_id, _uuid.UUID) else user_id


async def deregister(db: AsyncSession, user_id, reason: str, *, apply: bool = True) -> dict:
    """Deregister one user from SnapTrade and soft-status their row. Returns a small result
    dict for logging/reconcile output. Never raises — callers (Stripe webhook, sweep) stay safe.

    apply=False = dry run: report what WOULD happen without calling SnapTrade or mutating.
    """
    from app.core.database import SnaptradeUser, UserEvent
    from app.services import snaptrade_service as st

    uid = _as_uuid(user_id)
    row = (await db.execute(select(SnaptradeUser).where(SnaptradeUser.user_id == uid))).scalars().first()
    if not row or row.status != "active":
        return {"user_id": str(uid), "action": "noop", "reason": reason}
    if not apply:
        return {"user_id": str(uid), "action": "would_deregister", "reason": reason}

    # Stop billing FIRST. Only soft-status the row once SnapTrade confirms — a failed call
    # leaves the row 'active' so the next daily sweep retries it.
    # SAFETY: if SnapTrade isn't configured on THIS Lambda (e.g. keys missing on the worker), we
    # must NOT soft-status — doing so would mark the row deregistered while billing keeps running.
    # Leave it 'active' and bail so a properly-configured run cleans it up.
    if not st.is_configured():
        logger.warning(f"snaptrade deregister: not configured on this runtime — skipping {uid} "
                       f"(row left 'active' to avoid a false deregister while billing continues)")
        return {"user_id": str(uid), "action": "skipped_not_configured", "reason": reason}
    try:
        await st.delete_user(str(uid))
    except Exception as e:
        logger.warning(f"snaptrade deregister: deleteUser failed for {uid} ({reason}): {e}")
        return {"user_id": str(uid), "action": "error", "reason": reason, "error": str(e)}

    row.status = "deregistered"
    row.deregistered_at = datetime.utcnow()
    row.deregistered_reason = reason
    row.user_secret = None   # dead credential — the SnapTrade user it pointed to no longer exists
    db.add(UserEvent(user_id=uid, event_type="snaptrade_deregistered",
                     payload_json=json.dumps({"reason": reason})))
    await db.commit()
    logger.info(f"snaptrade deregistered {uid} (reason={reason})")
    return {"user_id": str(uid), "action": "deregistered", "reason": reason}
