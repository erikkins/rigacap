"""
Push notification service using Expo Push API.

Sends notifications to mobile app users via Expo's push notification service.
Tokens are registered when users log in on the mobile app.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import PushToken

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class PushNotificationService:
    """Send push notifications via Expo Push API."""

    async def register_token(
        self,
        db: AsyncSession,
        user_id: str,
        token: str,
        platform: str,
        device_id: Optional[str] = None,
    ) -> PushToken:
        """Register or reactivate an Expo push token for a user."""
        stmt = pg_insert(PushToken).values(
            user_id=user_id,
            token=token,
            platform=platform,
            device_id=device_id,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ).on_conflict_do_update(
            index_elements=["token"],
            set_={
                "user_id": user_id,
                "platform": platform,
                "device_id": device_id,
                "is_active": True,
                "updated_at": datetime.utcnow(),
            },
        )
        await db.execute(stmt)
        await db.commit()

        result = await db.execute(
            select(PushToken).where(PushToken.token == token)
        )
        return result.scalar_one()

    async def unregister_token(self, db: AsyncSession, token: str) -> bool:
        """Deactivate a push token."""
        result = await db.execute(
            update(PushToken)
            .where(PushToken.token == token)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        await db.commit()
        return result.rowcount > 0

    async def get_active_tokens(self, db: AsyncSession, user_id: str) -> list[PushToken]:
        """Get all active push tokens for a user."""
        result = await db.execute(
            select(PushToken).where(
                PushToken.user_id == user_id,
                PushToken.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def has_active_tokens(self, db: AsyncSession, user_id: str) -> bool:
        """Check if a user has any active push tokens."""
        tokens = await self.get_active_tokens(db, user_id)
        return len(tokens) > 0

    async def _send_push(
        self, tokens: list[str], title: str, body: str, data: Optional[dict] = None
    ) -> list[dict]:
        """Send push notifications via Expo Push API.

        Returns list of ticket responses from Expo.
        """
        if not tokens:
            return []

        messages = [
            {
                "to": token,
                "sound": "default",
                "title": title,
                "body": body,
                **({"data": data} if data else {}),
            }
            for token in tokens
        ]

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    EXPO_PUSH_URL,
                    json=messages,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                tickets = result.get("data", [])

                # Log any errors
                for i, ticket in enumerate(tickets):
                    if ticket.get("status") == "error":
                        logger.warning(
                            f"Push failed for token {tokens[i][:20]}...: "
                            f"{ticket.get('message')}"
                        )

                return tickets
        except Exception as e:
            logger.error(f"Expo push API error: {e}")
            return []

    async def send_to_user(
        self,
        db: AsyncSession,
        user_id: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> int:
        """Send push notification to all active devices for a user.

        Returns number of notifications sent successfully.
        """
        tokens = await self.get_active_tokens(db, user_id)
        if not tokens:
            return 0

        token_strings = [t.token for t in tokens]
        tickets = await self._send_push(token_strings, title, body, data)

        # Deactivate tokens that Expo reports as invalid
        for i, ticket in enumerate(tickets):
            details = ticket.get("details", {})
            if details.get("error") == "DeviceNotRegistered":
                await self.unregister_token(db, token_strings[i])
                logger.info(f"Deactivated unregistered token: {token_strings[i][:20]}...")

        return sum(1 for t in tickets if t.get("status") == "ok")

    async def send_daily_summary_push(
        self, db: AsyncSession, user_id: str, signal_count: int, fresh_count: int
    ) -> int:
        """Send daily signal summary push notification."""
        if signal_count == 0:
            title = "Market Update"
            body = "No ensemble buy signals today. Check the dashboard for market regime details."
        elif fresh_count > 0:
            title = f"{signal_count} Buy Signal{'s' if signal_count != 1 else ''} Today"
            body = f"{fresh_count} fresh signal{'s' if fresh_count != 1 else ''}! Tap to view details."
        else:
            title = f"{signal_count} Buy Signal{'s' if signal_count != 1 else ''} Today"
            body = "Tap to view today's ensemble signals."

        return await self.send_to_user(
            db, user_id, title, body,
            data={"screen": "dashboard", "type": "daily_summary"},
        )

    async def send_sell_alert_push(
        self,
        db: AsyncSession,
        user_id: str,
        symbol: str,
        action: str,
        reason: str,
    ) -> int:
        """Send sell/warning alert push notification."""
        if action == "sell":
            title = f"SELL ALERT: {symbol}"
        else:
            title = f"WARNING: {symbol}"

        return await self.send_to_user(
            db, user_id, title, reason,
            data={"screen": "signal_detail", "symbol": symbol, "type": "sell_alert"},
        )

    async def send_to_admin_email(
        self,
        to_email: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> int:
        """Push an admin alert to one admin's devices (the admin mobile app
        registers under that account, so this reuses the existing push path).

        Self-contained: opens its own DB session so non-DB callers like the
        email service can fire-and-forget. Best-effort — never raises. Only
        sends if the address is on the ADMIN_EMAILS allowlist, so a stray call
        can never push to a normal subscriber.
        """
        import os
        from sqlalchemy import func
        from app.core.database import async_session, User

        try:
            email = (to_email or "").strip().lower()
            admin_emails = set(
                e.strip().lower()
                for e in os.environ.get("ADMIN_EMAILS", "erik@rigacap.com").split(",")
                if e.strip()
            )
            if not email or email not in admin_emails:
                return 0

            async with async_session() as db:
                result = await db.execute(
                    select(User).where(func.lower(User.email) == email)
                )
                user = result.scalar_one_or_none()
                if user is None:
                    return 0
                # Push bodies must be short — trim long alert text.
                snippet = body if len(body) <= 178 else body[:175] + "..."
                return await self.send_to_user(db, str(user.id), title, snippet, data)
        except Exception as e:
            logger.warning(f"send_to_admin_email failed for {to_email}: {e}")
            return 0


# Singleton
push_notification_service = PushNotificationService()
