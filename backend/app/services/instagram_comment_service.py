"""
Instagram Comment Reply Service — monitors comments on our own Instagram posts
and generates Claude-powered reply drafts for admin approval.

Generated replies are saved as SocialPost drafts with post_type='instagram_comment_reply'.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.database import SocialPost

logger = logging.getLogger(__name__)

# Claude API (same endpoint/model as other services)
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-6"

COMMENT_REPLY_SYSTEM_PROMPT = """You reply to Instagram comments as Erik, founder of RigaCap.
A follower commented on one of your posts. Write a brief, warm reply.

VOICE: You are Erik. Friendly, genuine, direct — like responding to someone at a dinner party, not managing a brand account.
- Thank them or add value. Be real.
- NEVER give financial advice
- Keep it under 200 characters
- Don't be salesy — they already follow you
- Match their energy: if they're excited, be excited. If they ask a question, answer briefly.

FORMAT: Under 200 chars. Plain text only. No markdown. No emojis at start."""

INSTAGRAM_API_BASE = "https://graph.instagram.com/v24.0"


class InstagramCommentService:
    """Monitor Instagram comments and generate Claude-powered replies."""

    def __init__(self):
        self.enabled = (
            bool(settings.ANTHROPIC_API_KEY)
            and bool(settings.INSTAGRAM_ACCESS_TOKEN)
            and bool(settings.INSTAGRAM_BUSINESS_ACCOUNT_ID)
        )

    async def scan_and_reply(
        self, db, since_hours: int = 4
    ) -> dict:
        """
        Scan recent Instagram posts for new comments and generate reply drafts.

        Args:
            db: AsyncSession
            since_hours: How far back to look for new comments

        Returns:
            Summary dict with counts and details
        """
        if not self.enabled:
            return {"error": "Instagram comment service disabled — missing API keys"}

        results = {
            "posts_checked": 0,
            "comments_found": 0,
            "replies_created": 0,
            "skipped_dedup": 0,
            "skipped_short": 0,
            "details": [],
        }

        # Fetch our recent Instagram posts (last 7 days)
        our_posts = await self._fetch_our_recent_posts()
        if not our_posts:
            return {**results, "info": "No recent Instagram posts found"}

        since_time = datetime.utcnow() - timedelta(hours=since_hours)

        for media in our_posts:
            results["posts_checked"] += 1
            media_id = media.get("id", "")
            caption = media.get("caption", "")
            comments_count = media.get("comments_count", 0)

            if comments_count == 0:
                continue

            # Fetch comments for this post
            comments = await self._fetch_comments(media_id)

            for comment in comments:
                comment_id = comment.get("id", "")
                comment_text = comment.get("text", "")
                comment_username = comment.get("username", "")
                comment_timestamp = comment.get("timestamp", "")

                # Filter by time
                if comment_timestamp:
                    try:
                        ct = datetime.fromisoformat(
                            comment_timestamp.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                        if ct < since_time:
                            continue
                    except (ValueError, TypeError):
                        pass

                results["comments_found"] += 1

                # Skip very short comments (emojis only, etc.)
                clean = re.sub(r'[^\w\s]', '', comment_text).strip()
                if len(clean) < 10:
                    results["skipped_short"] += 1
                    continue

                # Dedup check
                if await self._check_dedup(comment_id, db):
                    results["skipped_dedup"] += 1
                    continue

                # Generate reply
                reply_text = await self._generate_comment_reply(
                    comment_text, comment_username, caption
                )
                if not reply_text:
                    continue

                # Save as draft
                post = SocialPost(
                    post_type="instagram_comment_reply",
                    platform="instagram",
                    status="draft",
                    text_content=reply_text,
                    reply_to_instagram_comment_id=comment_id,
                    reply_to_instagram_media_id=media_id,
                    reply_to_username=comment_username,
                    source_tweet_text=comment_text,  # Reuse field for original comment
                    ai_generated=True,
                    ai_model=CLAUDE_MODEL,
                )
                db.add(post)

                detail = {
                    "username": comment_username,
                    "comment_id": comment_id,
                    "comment_text": comment_text[:100],
                    "reply_text": reply_text,
                    "reply_chars": len(reply_text),
                }
                results["details"].append(detail)
                results["replies_created"] += 1

        if results["replies_created"] > 0:
            await db.commit()

            # Send approval emails
            results["emails_sent"] = await self._send_approval_emails(
                db, results["details"]
            )

        return results

    async def _fetch_our_recent_posts(self) -> List[dict]:
        """Fetch our recent Instagram posts (last 7 days)."""
        ig_user_id = settings.INSTAGRAM_BUSINESS_ACCOUNT_ID
        access_token = settings.INSTAGRAM_ACCESS_TOKEN

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{INSTAGRAM_API_BASE}/{ig_user_id}/media",
                    params={
                        "fields": "id,caption,timestamp,comments_count",
                        "limit": "20",
                        "access_token": access_token,
                    },
                )

            if resp.status_code != 200:
                logger.warning(
                    f"Failed to fetch IG media: {resp.status_code} {resp.text}"
                )
                return []

            data = resp.json()
            posts = data.get("data", [])

            # Filter to last 7 days
            cutoff = datetime.utcnow() - timedelta(days=7)
            recent = []
            for p in posts:
                ts = p.get("timestamp", "")
                if ts:
                    try:
                        post_time = datetime.fromisoformat(
                            ts.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                        if post_time >= cutoff:
                            recent.append(p)
                    except (ValueError, TypeError):
                        recent.append(p)
                else:
                    recent.append(p)

            return recent

        except Exception as e:
            logger.error(f"Error fetching IG media: {e}")
            return []

    async def _fetch_comments(self, media_id: str) -> List[dict]:
        """Fetch comments for a specific Instagram post."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{INSTAGRAM_API_BASE}/{media_id}/comments",
                    params={
                        "fields": "id,text,username,timestamp",
                        "limit": "50",
                        "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
                    },
                )

            if resp.status_code != 200:
                logger.warning(
                    f"Failed to fetch comments for {media_id}: {resp.status_code}"
                )
                return []

            return resp.json().get("data", [])

        except Exception as e:
            logger.error(f"Error fetching comments for {media_id}: {e}")
            return []

    async def _check_dedup(self, comment_id: str, db) -> bool:
        """Return True if we already have a reply draft for this comment."""
        from sqlalchemy import select

        result = await db.execute(
            select(SocialPost.id)
            .where(SocialPost.reply_to_instagram_comment_id == comment_id)
            .limit(1)
        )
        return result.scalars().first() is not None

    async def _generate_comment_reply(
        self,
        comment_text: str,
        username: str,
        our_post_caption: str,
    ) -> Optional[str]:
        """Generate a reply to an Instagram comment using Claude API."""
        if not settings.ANTHROPIC_API_KEY:
            return None

        user_prompt = (
            f"Our Instagram post caption:\n\"{our_post_caption[:200]}\"\n\n"
            f"@{username} commented:\n\"{comment_text[:200]}\"\n\n"
            f"Write a brief reply to this comment. Be warm, genuine, and on-brand. "
            f"Under 200 characters. Plain text only."
        )

        try:
            headers = {
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }

            payload = {
                "model": CLAUDE_MODEL,
                "max_tokens": 128,
                "system": COMMENT_REPLY_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    CLAUDE_API_URL, headers=headers, json=payload
                )

            if resp.status_code != 200:
                logger.error(f"Claude API error {resp.status_code}: {resp.text}")
                return None

            data = resp.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                text = content[0]["text"].strip()
                # Strip markdown
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                text = re.sub(r'(?<!\w)\*([^*]+?)\*(?!\w)', r'\1', text)
                # Enforce limit
                if len(text) > 200:
                    text = text[:197].rsplit(" ", 1)[0] + "..."
                return text

            return None

        except Exception as e:
            logger.error(f"Comment reply generation failed for @{username}: {e}")
            return None

    async def _send_approval_emails(self, db, details: list) -> int:
        """Send approval emails for new comment reply drafts."""
        from app.services.email_service import admin_email_service
        from app.services.post_scheduler_service import post_scheduler_service
        from sqlalchemy import select, desc

        result = await db.execute(
            select(SocialPost)
            .where(
                SocialPost.post_type == "instagram_comment_reply",
                SocialPost.status == "draft",
            )
            .order_by(desc(SocialPost.created_at))
            .limit(len(details))
        )
        posts = result.scalars().all()
        post_by_comment = {
            p.reply_to_instagram_comment_id: p for p in posts
        }

        sent = 0
        for detail in details:
            post = post_by_comment.get(detail.get("comment_id"))
            if not post:
                continue
            try:
                approve_token = post_scheduler_service.generate_approve_token(
                    post.id
                )
                approve_url = (
                    f"{settings.FRONTEND_URL}/api/admin/social/posts/"
                    f"{post.id}/approve-email?token={approve_token}"
                )

                success = await admin_email_service.send_reply_approval_email(
                    to_email="erik@rigacap.com",
                    post=post,
                    approve_url=approve_url,
                )
                if success:
                    sent += 1
            except Exception as e:
                logger.error(
                    f"Failed to send approval email for post {post.id}: {e}"
                )

        return sent


# Singleton
instagram_comment_service = InstagramCommentService()
