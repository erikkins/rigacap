"""
Post Scheduler Service - Automated scheduling, admin notifications, and auto-publishing.

Handles the full lifecycle:
1. Auto-schedule draft posts across optimal posting windows
2. Send T-24h and T-1h admin approval notifications with cancel links
3. Auto-publish approved posts when scheduled_for <= now
4. Cancel mechanism via JWT-signed one-click email links
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError, ExpiredSignatureError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.database import SocialPost

logger = logging.getLogger(__name__)

# Admin email
ADMIN_EMAIL = "erik@rigacap.com"

# Optimal posting hours (ET) by day type
OPTIMAL_HOURS = {
    "weekday": [9, 12, 17],   # Morning, lunch, after-work
    "weekend": [10, 14],       # Mid-morning, afternoon
}

# Minimum minutes between posts per platform (prevents spam blocks)
PLATFORM_COOLDOWN_MINUTES = {
    "threads": 180,   # 3 hours — Threads aggressively blocks rapid posting
    "instagram": 120,  # 2 hours
    "twitter": 30,     # 30 min — Twitter is more lenient
    "tiktok": 240,     # 4 hours — conservative until we understand rate limits
}


class PostSchedulerService:
    """Schedule posts and send admin approval notifications."""

    def __init__(self):
        # Track which posts we've already emailed about to avoid spam
        self._failure_emailed: set[int] = set()

    async def schedule_post(
        self, post_id: int, publish_at: datetime, db: AsyncSession
    ) -> bool:
        """
        Set scheduled_for on a SocialPost. Status must be 'approved'.

        Returns True if successfully scheduled.
        """
        result = await db.execute(
            select(SocialPost).where(SocialPost.id == post_id)
        )
        post = result.scalar_one_or_none()

        if not post:
            logger.error(f"Post {post_id} not found")
            return False

        if post.status not in ("approved", "draft"):
            logger.error(f"Cannot schedule post {post_id} with status '{post.status}'")
            return False

        post.scheduled_for = publish_at
        post.status = "scheduled"
        await db.commit()

        logger.info(f"Post {post_id} scheduled for {publish_at.isoformat()}")
        return True

    async def auto_schedule_drafts(self, db: AsyncSession) -> int:
        """
        Called nightly after content generation.
        Takes all new draft posts (without scheduled_for), assigns scheduled_for times
        spread across the next 1-3 days at optimal posting hours.

        Returns count of posts scheduled.
        """
        result = await db.execute(
            select(SocialPost).where(
                and_(
                    SocialPost.status == "draft",
                    SocialPost.scheduled_for.is_(None),
                )
            ).order_by(SocialPost.created_at)
        )
        posts = result.scalars().all()

        if not posts:
            return 0

        now = datetime.utcnow()
        scheduled_count = 0

        for i, post in enumerate(posts):
            # Spread posts across 1-3 days
            day_offset = 1 + (i // 4)  # 4 posts per day max
            target_date = now + timedelta(days=day_offset)

            # Pick optimal hour based on weekday/weekend
            is_weekend = target_date.weekday() >= 5
            hours = OPTIMAL_HOURS["weekend" if is_weekend else "weekday"]
            hour = hours[i % len(hours)]

            publish_at = target_date.replace(hour=hour, minute=0, second=0, microsecond=0)

            post.scheduled_for = publish_at
            scheduled_count += 1

        await db.commit()

        logger.info(f"Auto-scheduled {scheduled_count} draft posts")

        # Send T-24h notification for posts scheduled within next 48h
        upcoming = [p for p in posts if p.scheduled_for and p.scheduled_for <= now + timedelta(hours=48)]
        if upcoming:
            await self._send_batch_notification(upcoming, hours_before=24)

        return scheduled_count

    async def check_and_publish(self, db: AsyncSession) -> int:
        """
        Called every 15 minutes by scheduler.
        Finds posts where status in ('approved','scheduled') AND scheduled_for <= now.
        Publishes them via SocialPostingService, respecting per-platform cooldowns
        to avoid spam blocks (especially Threads).

        Returns count of posts published.
        """
        now = datetime.utcnow()
        logger.info(f"[PUBLISH] check_and_publish running, now={now.isoformat()}")

        result = await db.execute(
            select(SocialPost).where(
                and_(
                    SocialPost.status.in_(["approved", "scheduled"]),
                    SocialPost.scheduled_for.isnot(None),
                    SocialPost.scheduled_for <= now,
                    SocialPost.post_type != "contextual_reply",
                )
            ).order_by(SocialPost.scheduled_for)
        )
        posts = result.scalars().all()
        logger.info(f"[PUBLISH] Found {len(posts)} post(s) ready to publish")

        if not posts:
            return 0

        # Query last posted_at per platform to enforce cooldowns
        last_posted: dict[str, datetime] = {}
        for platform in PLATFORM_COOLDOWN_MINUTES:
            last_result = await db.execute(
                select(SocialPost.posted_at).where(
                    and_(
                        SocialPost.platform == platform,
                        SocialPost.status == "posted",
                        SocialPost.posted_at.isnot(None),
                    )
                ).order_by(SocialPost.posted_at.desc()).limit(1)
            )
            last_ts = last_result.scalar_one_or_none()
            if last_ts:
                last_posted[platform] = last_ts

        from app.services.social_posting_service import social_posting_service

        MAX_PUBLISH_ATTEMPTS = 3

        published = 0
        skipped = 0
        for post in posts:
            # Check if post has exhausted retries
            attempts = getattr(post, 'publish_attempts', 0) or 0
            if attempts >= MAX_PUBLISH_ATTEMPTS:
                post.status = "publish_failed"
                logger.warning(
                    f"Post {post.id} ({post.platform}) failed after "
                    f"{attempts} attempts — marking as publish_failed"
                )
                skipped += 1
                continue

            # Check platform cooldown
            cooldown_min = PLATFORM_COOLDOWN_MINUTES.get(post.platform, 30)
            platform_last = last_posted.get(post.platform)
            if platform_last:
                elapsed = (now - platform_last).total_seconds() / 60
                if elapsed < cooldown_min:
                    remaining = int(cooldown_min - elapsed)
                    logger.info(
                        f"Skipping post {post.id} ({post.platform}) — "
                        f"cooldown {remaining}min remaining"
                    )
                    skipped += 1
                    continue

            # Mark as 'publishing' + increment attempts BEFORE the API call.
            # Prevents duplicate posts when two concurrent invocations (cron +
            # manual trigger) grab the same post. The second invocation sees
            # 'publishing' and skips it.
            post.publish_attempts = attempts + 1
            post.status = "publishing"
            await db.commit()

            try:
                pub_result = await social_posting_service.publish_post(post)
                if "error" not in pub_result:
                    published += 1
                    # Update last_posted so subsequent posts in this batch
                    # respect the cooldown within the same run
                    last_posted[post.platform] = now
                    logger.info(f"Auto-published post {post.id} to {post.platform}")
                else:
                    error_msg = pub_result['error']
                    logger.error(
                        f"Auto-publish failed for post {post.id} "
                        f"(attempt {post.publish_attempts}/{MAX_PUBLISH_ATTEMPTS}): {error_msg}"
                    )
                    if post.publish_attempts >= MAX_PUBLISH_ATTEMPTS:
                        post.status = "publish_failed"
                        logger.warning(f"Post {post.id} marked as publish_failed")
                    else:
                        post.status = "approved"  # Reset for retry
                    await self._send_publish_failure_email(post, str(error_msg))
            except Exception as e:
                logger.error(
                    f"Auto-publish error for post {post.id} "
                    f"(attempt {post.publish_attempts}/{MAX_PUBLISH_ATTEMPTS}): {e}"
                )
                if post.publish_attempts >= MAX_PUBLISH_ATTEMPTS:
                    post.status = "publish_failed"
                    logger.warning(f"Post {post.id} marked as publish_failed")
                else:
                    post.status = "approved"  # Reset for retry
                await self._send_publish_failure_email(post, str(e))

        await db.commit()

        if published or skipped:
            logger.info(
                f"Auto-publish: {published} published, {skipped} skipped (cooldown) "
                f"out of {len(posts)} due"
            )

        return published

    async def _send_publish_failure_email(self, post, error_msg: str):
        """Send admin email when a scheduled post fails to publish (once per post)."""
        if post.id in self._failure_emailed:
            return
        self._failure_emailed.add(post.id)
        try:
            from app.services.email_service import admin_email_service

            content_preview = (post.text_content or "")[:120]
            html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
<tr><td style="background:linear-gradient(135deg,#172554,#1e3a5f);padding:24px;text-align:center;">
    <h1 style="margin:0;color:#ef4444;font-size:20px;">Post Publish Failed</h1>
    <p style="margin:6px 0 0;color:#94a3b8;font-size:14px;">Post #{post.id} &middot; {post.platform}</p>
</td></tr>
<tr><td style="background:#fff;padding:24px;">
    <table width="100%" style="font-size:14px;color:#374151;">
        <tr><td style="padding:6px 0;font-weight:600;width:100px;">Platform</td><td>{post.platform}</td></tr>
        <tr><td style="padding:6px 0;font-weight:600;">Post ID</td><td>{post.id}</td></tr>
        <tr><td style="padding:6px 0;font-weight:600;">Type</td><td>{post.post_type or 'unknown'}</td></tr>
        <tr><td style="padding:6px 0;font-weight:600;">Content</td><td style="color:#6b7280;">{content_preview}{'...' if len(post.text_content or '') > 120 else ''}</td></tr>
    </table>
    <div style="margin:16px 0;padding:12px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;">
        <p style="margin:0;font-size:13px;font-weight:600;color:#dc2626;">Error</p>
        <p style="margin:4px 0 0;font-size:13px;color:#7f1d1d;word-break:break-all;">{error_msg[:300]}</p>
    </div>
    <p style="margin:16px 0 0;font-size:12px;color:#9ca3af;">
        The post status remains 'scheduled' and will be retried on the next 15-minute cycle.
        Check the Threads/Instagram app for account restrictions if this persists.
    </p>
</td></tr>
</table></body></html>"""

            await admin_email_service.send_email(
                to_email=ADMIN_EMAIL,
                subject=f"[RigaCap] Post #{post.id} failed to publish ({post.platform})",
                html_content=html,
            )
        except Exception as e:
            logger.error(f"Failed to send publish failure email for post {post.id}: {e}")

    async def send_notifications(self, db: AsyncSession) -> int:
        """
        Called every hour by scheduler.
        Sends T-24h and T-1h admin notifications for upcoming scheduled posts.

        Returns count of notifications sent.
        """
        now = datetime.utcnow()
        sent = 0

        # T-24h notifications: posts scheduled in 23-25 hours
        result_24h = await db.execute(
            select(SocialPost).where(
                and_(
                    SocialPost.status.in_(["approved", "scheduled"]),
                    SocialPost.scheduled_for.isnot(None),
                    SocialPost.scheduled_for > now + timedelta(hours=23),
                    SocialPost.scheduled_for <= now + timedelta(hours=25),
                    SocialPost.notification_24h_sent == False,
                )
            )
        )
        posts_24h = result_24h.scalars().all()

        for post in posts_24h:
            success = await self._send_notification(post, hours_before=24)
            if success:
                post.notification_24h_sent = True
                sent += 1

        # T-1h notifications: posts scheduled in 30min-90min
        result_1h = await db.execute(
            select(SocialPost).where(
                and_(
                    SocialPost.status.in_(["approved", "scheduled"]),
                    SocialPost.scheduled_for.isnot(None),
                    SocialPost.scheduled_for > now + timedelta(minutes=30),
                    SocialPost.scheduled_for <= now + timedelta(minutes=90),
                    SocialPost.notification_1h_sent == False,
                )
            )
        )
        posts_1h = result_1h.scalars().all()

        for post in posts_1h:
            success = await self._send_notification(post, hours_before=1)
            if success:
                post.notification_1h_sent = True
                sent += 1

        if sent:
            await db.commit()
            logger.info(f"Sent {sent} post notifications")

        return sent

    async def cancel_post(self, post_id: int, db: AsyncSession) -> bool:
        """Admin cancels a scheduled post. Resets to approved so it can be rescheduled."""
        result = await db.execute(
            select(SocialPost).where(SocialPost.id == post_id)
        )
        post = result.scalar_one_or_none()

        if not post:
            return False

        if post.status == "posted":
            return False

        post.status = "approved"
        post.scheduled_for = None
        post.notification_24h_sent = False
        post.notification_1h_sent = False
        await db.commit()

        logger.info(f"Post {post_id} unscheduled (reset to approved)")
        return True

    def generate_cancel_token(self, post_id: int, expires_hours: int = 48) -> str:
        """Generate a JWT token for one-click cancel from email."""
        payload = {
            "post_id": post_id,
            "action": "cancel",
            "exp": datetime.utcnow() + timedelta(hours=expires_hours),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    def generate_approve_token(self, post_id: int, expires_hours: int = 72) -> str:
        """Generate a JWT token for one-click approve+publish from email."""
        payload = {
            "post_id": post_id,
            "action": "approve_publish",
            "exp": datetime.utcnow() + timedelta(hours=expires_hours),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    def verify_approve_token(self, token: str) -> Optional[int]:
        """Verify an approve JWT token and return the post_id."""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            if payload.get("action") != "approve_publish":
                return None
            return payload.get("post_id")
        except ExpiredSignatureError:
            logger.warning("Approve token expired")
            return None
        except JWTError:
            logger.warning("Invalid approve token")
            return None

    def verify_cancel_token(self, token: str) -> Optional[int]:
        """
        Verify a cancel JWT token and return the post_id.
        Returns None if invalid or expired.
        """
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            if payload.get("action") != "cancel":
                return None
            return payload.get("post_id")
        except ExpiredSignatureError:
            logger.warning("Cancel token expired")
            return None
        except JWTError:
            logger.warning("Invalid cancel token")
            return None

    async def _send_notification(self, post: SocialPost, hours_before: int) -> bool:
        """Send email notification for a single post."""
        try:
            from app.services.email_service import admin_email_service

            cancel_token = self.generate_cancel_token(post.id)
            cancel_url = f"https://api.rigacap.com/api/admin/social/posts/{post.id}/cancel-email?token={cancel_token}"
            approve_token = self.generate_approve_token(post.id)
            publish_url = f"https://api.rigacap.com/api/admin/social/posts/{post.id}/approve-email?token={approve_token}"

            return await admin_email_service.send_post_approval_notification(
                to_email=ADMIN_EMAIL,
                post=post,
                hours_before=hours_before,
                cancel_url=cancel_url,
                publish_url=publish_url,
            )
        except Exception as e:
            logger.error(f"Failed to send notification for post {post.id}: {e}")
            return False

    async def _send_batch_notification(
        self, posts: list, hours_before: int
    ) -> int:
        """Send notification for a batch of posts."""
        sent = 0
        for post in posts:
            if await self._send_notification(post, hours_before):
                sent += 1
        return sent


# Singleton instance
post_scheduler_service = PostSchedulerService()
