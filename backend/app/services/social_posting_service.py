"""
Social media publishing service — posts to Twitter API v2, Instagram Graph API,
Threads API, and TikTok Content Posting API.

Uses httpx (already in requirements.txt) for all HTTP requests.
OAuth 1.0a signing for Twitter is done manually (no extra dependency).
"""

import hashlib
import hmac
import logging
import os
import re
import time
import urllib.parse
import uuid
from base64 import b64encode
from datetime import datetime
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SocialPostingService:
    """Publish posts to Twitter, Instagram, Threads, and TikTok."""

    # Twitter API v2 endpoints
    TWITTER_TWEET_URL = "https://api.twitter.com/2/tweets"
    TWITTER_MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"

    # Instagram Graph API
    INSTAGRAM_API_BASE = "https://graph.instagram.com/v24.0"

    # Threads API
    THREADS_API_BASE = "https://graph.threads.net/v1.0"

    # TikTok Content Posting API
    TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"

    # ── Twitter ──────────────────────────────────────────────────────

    def _oauth1_signature(
        self, method: str, url: str, params: dict, body_params: dict = None
    ) -> str:
        """Generate OAuth 1.0a Authorization header for Twitter."""
        consumer_key = settings.TWITTER_API_KEY
        consumer_secret = settings.TWITTER_API_SECRET
        token = settings.TWITTER_ACCESS_TOKEN
        token_secret = settings.TWITTER_ACCESS_TOKEN_SECRET

        oauth_params = {
            "oauth_consumer_key": consumer_key,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": token,
            "oauth_version": "1.0",
        }

        # Combine all params for signature base string
        all_params = {**oauth_params, **params}
        if body_params:
            all_params.update(body_params)

        sorted_params = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted(all_params.items())
        )

        base_string = (
            f"{method.upper()}&"
            f"{urllib.parse.quote(url, safe='')}&"
            f"{urllib.parse.quote(sorted_params, safe='')}"
        )

        signing_key = (
            f"{urllib.parse.quote(consumer_secret, safe='')}&"
            f"{urllib.parse.quote(token_secret, safe='')}"
        )

        signature = b64encode(
            hmac.new(
                signing_key.encode(), base_string.encode(), hashlib.sha1
            ).digest()
        ).decode()

        oauth_params["oauth_signature"] = signature

        auth_header = "OAuth " + ", ".join(
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        )
        return auth_header

    async def _upload_media_to_twitter(self, image_bytes: bytes) -> Optional[str]:
        """Upload an image to Twitter and return the media_id string."""
        auth_header = self._oauth1_signature(
            "POST", self.TWITTER_MEDIA_UPLOAD_URL, {}
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.TWITTER_MEDIA_UPLOAD_URL,
                headers={"Authorization": auth_header},
                files={"media": ("image.png", image_bytes, "image/png")},
            )

        if resp.status_code not in (200, 201):
            logger.error("Twitter media upload failed: %s %s", resp.status_code, resp.text)
            return None

        media_id = resp.json().get("media_id_string")
        logger.info("Twitter media uploaded: %s", media_id)
        return media_id

    async def post_to_twitter(
        self, text: str, image_url: Optional[str] = None,
        reply_to_tweet_id: Optional[str] = None,
    ) -> dict:
        """Post a tweet. Optionally attach an image (downloaded from image_url).

        Returns {"tweet_id": "...", "tweet_url": "..."} on success,
        or {"error": "..."} on failure.
        """
        if not settings.TWITTER_API_KEY:
            return {"error": "Twitter API credentials not configured"}

        media_id = None
        if image_url:
            async with httpx.AsyncClient(timeout=30) as client:
                img_resp = await client.get(image_url)
            if img_resp.status_code == 200:
                media_id = await self._upload_media_to_twitter(img_resp.content)

        payload = {"text": text}
        if media_id:
            payload["media"] = {"media_ids": [media_id]}
        if reply_to_tweet_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_tweet_id}

        # Twitter API v2 uses JSON body — OAuth 1.0a signature only covers URL params
        auth_header = self._oauth1_signature("POST", self.TWITTER_TWEET_URL, {})

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.TWITTER_TWEET_URL,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if resp.status_code not in (200, 201):
            logger.error("Twitter post failed: %s %s", resp.status_code, resp.text)
            return {"error": f"Twitter API error {resp.status_code}: {resp.text}"}

        data = resp.json().get("data", {})
        tweet_id = data.get("id", "")
        return {
            "tweet_id": tweet_id,
            "tweet_url": f"https://x.com/rigacap/status/{tweet_id}",
        }

    # ── Instagram ────────────────────────────────────────────────────

    async def post_to_instagram(
        self, caption: str, image_url: str
    ) -> dict:
        """Publish a photo to Instagram via the Graph API.

        image_url must be publicly accessible (use S3 presigned URL with long expiry).

        Returns {"media_id": "...", "permalink": "..."} on success,
        or {"error": "..."} on failure.
        """
        if not settings.INSTAGRAM_ACCESS_TOKEN or not settings.INSTAGRAM_BUSINESS_ACCOUNT_ID:
            return {"error": "Instagram API credentials not configured"}

        ig_user_id = settings.INSTAGRAM_BUSINESS_ACCOUNT_ID
        access_token = settings.INSTAGRAM_ACCESS_TOKEN

        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Create media container
            container_resp = await client.post(
                f"{self.INSTAGRAM_API_BASE}/{ig_user_id}/media",
                data={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": access_token,
                },
            )

            if container_resp.status_code != 200:
                logger.error("IG container creation failed: %s %s", container_resp.status_code, container_resp.text)
                return {"error": f"Instagram container error: {container_resp.text}"}

            container_id = container_resp.json().get("id")
            if not container_id:
                return {"error": "No container ID returned"}

            # Step 2: Poll until container is ready (up to 30s)
            for _ in range(6):
                status_resp = await client.get(
                    f"{self.INSTAGRAM_API_BASE}/{container_id}",
                    params={
                        "fields": "status_code",
                        "access_token": access_token,
                    },
                )
                status_code = status_resp.json().get("status_code")
                if status_code == "FINISHED":
                    break
                if status_code == "ERROR":
                    return {"error": "Instagram container processing failed"}
                await _async_sleep(5)

            # Step 3: Publish
            publish_resp = await client.post(
                f"{self.INSTAGRAM_API_BASE}/{ig_user_id}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": access_token,
                },
            )

            if publish_resp.status_code != 200:
                logger.error("IG publish failed: %s %s", publish_resp.status_code, publish_resp.text)
                return {"error": f"Instagram publish error: {publish_resp.text}"}

            media_id = publish_resp.json().get("id", "")

            # Get permalink
            permalink = ""
            try:
                perm_resp = await client.get(
                    f"{self.INSTAGRAM_API_BASE}/{media_id}",
                    params={
                        "fields": "permalink",
                        "access_token": access_token,
                    },
                )
                permalink = perm_resp.json().get("permalink", "")
            except Exception:
                pass

            return {"media_id": media_id, "permalink": permalink}

    # ── Threads ──────────────────────────────────────────────────────

    async def post_to_threads(
        self, text: str, image_url: Optional[str] = None,
        reply_to_id: Optional[str] = None,
    ) -> dict:
        """Post to Threads via the Threads API.

        Returns {"threads_id": "...", "permalink": "..."} on success,
        or {"error": "..."} on failure.
        """
        if not settings.THREADS_ACCESS_TOKEN or not settings.THREADS_USER_ID:
            return {"error": "Threads API credentials not configured"}

        user_id = settings.THREADS_USER_ID
        access_token = settings.THREADS_ACCESS_TOKEN

        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Create media container
            container_data = {
                "text": text,
                "access_token": access_token,
            }

            if image_url:
                container_data["media_type"] = "IMAGE"
                container_data["image_url"] = image_url
            else:
                container_data["media_type"] = "TEXT"

            if reply_to_id:
                container_data["reply_to_id"] = reply_to_id

            container_resp = await client.post(
                f"{self.THREADS_API_BASE}/{user_id}/threads",
                data=container_data,
            )

            if container_resp.status_code != 200:
                logger.error("Threads container failed: %s %s", container_resp.status_code, container_resp.text)
                return {"error": f"Threads container error: {container_resp.text}"}

            container_id = container_resp.json().get("id")
            if not container_id:
                return {"error": "No container ID returned from Threads"}

            # Step 2: Wait for container to be ready (up to 30s)
            for _ in range(6):
                status_resp = await client.get(
                    f"{self.THREADS_API_BASE}/{container_id}",
                    params={
                        "fields": "status",
                        "access_token": access_token,
                    },
                )
                if status_resp.status_code == 200:
                    status = status_resp.json().get("status")
                    if status == "FINISHED":
                        break
                    if status == "ERROR":
                        return {"error": "Threads container processing failed"}
                await _async_sleep(5)

            # Step 3: Publish
            publish_resp = await client.post(
                f"{self.THREADS_API_BASE}/{user_id}/threads_publish",
                data={
                    "creation_id": container_id,
                    "access_token": access_token,
                },
            )

            if publish_resp.status_code != 200:
                logger.error("Threads publish failed: %s %s", publish_resp.status_code, publish_resp.text)
                return {"error": f"Threads publish error: {publish_resp.text}"}

            threads_id = publish_resp.json().get("id", "")

            # Get permalink
            permalink = ""
            try:
                perm_resp = await client.get(
                    f"{self.THREADS_API_BASE}/{threads_id}",
                    params={
                        "fields": "permalink",
                        "access_token": access_token,
                    },
                )
                permalink = perm_resp.json().get("permalink", "")
            except Exception:
                pass

            return {"threads_id": threads_id, "permalink": permalink}

    async def lookup_threads_user_by_username(self, username: str) -> Optional[str]:
        """Look up a Threads user ID by username."""
        if not settings.THREADS_ACCESS_TOKEN:
            return None

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.THREADS_API_BASE}/{settings.THREADS_USER_ID}",
                    params={
                        "fields": "id,username",
                        "access_token": settings.THREADS_ACCESS_TOKEN,
                    },
                )
            if resp.status_code == 200:
                return resp.json().get("id")
        except Exception as e:
            logger.warning("Threads user lookup failed for %s: %s", username, e)

        return None

    # ── TikTok ───────────────────────────────────────────────────────

    async def post_to_tiktok(
        self, text: str, image_url: Optional[str] = None,
    ) -> dict:
        """Post to TikTok via the Content Posting API.

        For photo posts (image_url provided): creates a photo post.
        For text-only: TikTok requires a photo or video, so we return an error.

        Returns {"tiktok_id": "..."} on success, or {"error": "..."} on failure.
        """
        if not settings.TIKTOK_ACCESS_TOKEN:
            return {"error": "TikTok access token not configured"}

        access_token = settings.TIKTOK_ACCESS_TOKEN
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        if not image_url:
            return {"error": "TikTok posts require an image or video"}

        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Initialize photo upload
            init_resp = await client.post(
                f"{self.TIKTOK_API_BASE}/post/publish/inbox/video/init/",
                headers=headers,
                json={
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "video_url": image_url,
                    },
                    "post_info": {
                        "title": text[:150],
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "disable_comment": False,
                        "disable_duet": False,
                        "disable_stitch": False,
                    },
                    "post_mode": "DIRECT_POST",
                    "media_type": "PHOTO",
                },
            )

            if init_resp.status_code != 200:
                # Try the photo-specific endpoint
                init_resp = await client.post(
                    f"{self.TIKTOK_API_BASE}/post/publish/content/init/",
                    headers=headers,
                    json={
                        "post_info": {
                            "title": text[:150],
                            "description": text[:2200],
                            "privacy_level": "PUBLIC_TO_EVERYONE",
                            "disable_comment": False,
                        },
                        "source_info": {
                            "source": "PULL_FROM_URL",
                            "photo_cover_index": 0,
                            "photo_images": [image_url],
                        },
                        "post_mode": "DIRECT_POST",
                        "media_type": "PHOTO",
                    },
                )

            if init_resp.status_code != 200:
                logger.error("TikTok post init failed: %s %s", init_resp.status_code, init_resp.text[:500])
                return {"error": f"TikTok init error: {init_resp.text[:200]}"}

            result = init_resp.json()
            publish_id = result.get("data", {}).get("publish_id", "")

            if not publish_id:
                return {"error": f"No publish_id returned: {result}"}

            # Step 2: Check publish status (poll up to 30s)
            for _ in range(6):
                status_resp = await client.post(
                    f"{self.TIKTOK_API_BASE}/post/publish/status/fetch/",
                    headers=headers,
                    json={"publish_id": publish_id},
                )
                if status_resp.status_code == 200:
                    status_data = status_resp.json().get("data", {})
                    status = status_data.get("status")
                    if status == "PUBLISH_COMPLETE":
                        return {"tiktok_id": publish_id}
                    if status in ("FAILED", "PUBLISH_FAILED"):
                        fail_reason = status_data.get("fail_reason", "unknown")
                        return {"error": f"TikTok publish failed: {fail_reason}"}
                await _async_sleep(5)

            return {"tiktok_id": publish_id}

    # ── Instagram Comments ───────────────────────────────────────────

    async def post_instagram_comment(
        self, comment_id: str, message: str
    ) -> dict:
        """Reply to an Instagram comment.

        Returns {"comment_id": "...", "success": True} on success,
        or {"error": "..."} on failure.
        """
        if not settings.INSTAGRAM_ACCESS_TOKEN:
            return {"error": "Instagram API credentials not configured"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.INSTAGRAM_API_BASE}/{comment_id}/replies",
                data={
                    "message": message,
                    "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
                },
            )

        if resp.status_code != 200:
            logger.error("IG comment reply failed: %s %s", resp.status_code, resp.text)
            return {"error": f"Instagram comment reply error: {resp.text}"}

        reply_id = resp.json().get("id", "")
        return {"comment_id": reply_id, "success": True}

    # ── Twitter Follow ──────────────────────────────────────────────

    TWITTER_USERS_ME_URL = "https://api.twitter.com/2/users/me"
    TWITTER_USERS_BY_USERNAME_URL = "https://api.twitter.com/2/users/by/username"

    async def get_authenticated_user_id(self) -> Optional[str]:
        """Get the Twitter user ID for the authenticated account."""
        auth_header = self._oauth1_signature("GET", self.TWITTER_USERS_ME_URL, {})
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                self.TWITTER_USERS_ME_URL,
                headers={"Authorization": auth_header},
            )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("id")
        logger.error("Failed to get authenticated user: %s %s", resp.status_code, resp.text)
        return None

    async def lookup_twitter_user_id(self, username: str) -> Optional[str]:
        """Look up a Twitter user ID by username (without @)."""
        url = f"{self.TWITTER_USERS_BY_USERNAME_URL}/{username}"
        auth_header = self._oauth1_signature("GET", url, {})
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                headers={"Authorization": auth_header},
            )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("id")
        logger.warning("User lookup failed for @%s: %s %s", username, resp.status_code, resp.text)
        return None

    async def follow_twitter_user(self, target_user_id: str, my_user_id: str = None) -> dict:
        """Follow a Twitter user by their user ID.

        Returns {"following": True, "pending": False} on success,
        or {"error": "..."} on failure.
        """
        if not settings.TWITTER_API_KEY:
            return {"error": "Twitter API credentials not configured"}

        if not my_user_id:
            my_user_id = await self.get_authenticated_user_id()
            if not my_user_id:
                return {"error": "Could not determine authenticated user ID"}

        url = f"https://api.twitter.com/2/users/{my_user_id}/following"
        auth_header = self._oauth1_signature("POST", url, {})

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                },
                json={"target_user_id": target_user_id},
            )

        if resp.status_code in (200, 201):
            return resp.json().get("data", {})
        logger.error("Twitter follow failed: %s %s", resp.status_code, resp.text)
        return {"error": f"Twitter API error {resp.status_code}: {resp.text}"}

    async def batch_follow_twitter(self, usernames: list[str]) -> dict:
        """Follow a list of Twitter usernames. Returns results per username."""
        import asyncio

        my_user_id = await self.get_authenticated_user_id()
        if not my_user_id:
            return {"error": "Could not determine authenticated user ID"}

        results = {}
        for username in usernames:
            clean = username.lstrip("@").strip()
            if not clean:
                continue
            try:
                target_id = await self.lookup_twitter_user_id(clean)
                if not target_id:
                    results[clean] = {"error": "User not found"}
                    continue
                result = await self.follow_twitter_user(target_id, my_user_id)
                results[clean] = result
                logger.info("Followed @%s: %s", clean, result)
            except Exception as e:
                results[clean] = {"error": str(e)}
                logger.error("Error following @%s: %s", clean, e)
            # Rate limit: 5 requests per 15 min window for follows
            await asyncio.sleep(3)

        return {
            "my_user_id": my_user_id,
            "followed": sum(1 for r in results.values() if r.get("following")),
            "failed": sum(1 for r in results.values() if "error" in r),
            "results": results,
        }

    # ── Threads Token Refresh ────────────────────────────────────────

    async def refresh_threads_token(self) -> dict:
        """Refresh the Threads long-lived access token and update Lambda env var.

        Threads long-lived tokens expire after 60 days. This method exchanges
        the current token for a new one and persists it by updating the Lambda
        function's environment variables via boto3.

        Returns {"success": True, "expires_in": ...} or {"error": "..."}.
        """
        if not settings.THREADS_ACCESS_TOKEN:
            return {"error": "No Threads access token configured"}

        # Step 1: Exchange current token for a new long-lived token
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://graph.threads.net/refresh_access_token",
                    params={
                        "grant_type": "th_refresh_token",
                        "access_token": settings.THREADS_ACCESS_TOKEN,
                    },
                )

            if resp.status_code != 200:
                logger.error(
                    "Threads token refresh failed: %s %s",
                    resp.status_code, resp.text,
                )
                return {"error": f"Refresh API error {resp.status_code}: {resp.text}"}

            data = resp.json()
            new_token = data.get("access_token")
            expires_in = data.get("expires_in", 0)

            if not new_token:
                return {"error": "No access_token in refresh response"}

            logger.info(
                "Threads token refreshed, expires in %d days",
                expires_in // 86400,
            )
        except Exception as e:
            logger.error("Threads token refresh request failed: %s", e)
            return {"error": str(e)}

        # Step 2: Update in-memory setting for current execution
        settings.THREADS_ACCESS_TOKEN = new_token

        # Step 3: Persist to Lambda env var so it survives cold starts
        function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        if function_name:
            try:
                import boto3
                lambda_client = boto3.client("lambda", region_name="us-east-1")

                # Get current config
                config = lambda_client.get_function_configuration(
                    FunctionName=function_name
                )
                env_vars = config.get("Environment", {}).get("Variables", {})

                # Update token
                env_vars["THREADS_ACCESS_TOKEN"] = new_token

                lambda_client.update_function_configuration(
                    FunctionName=function_name,
                    Environment={"Variables": env_vars},
                )
                logger.info("Lambda env var THREADS_ACCESS_TOKEN updated")
            except Exception as e:
                logger.error("Failed to update Lambda env var: %s", e)
                return {
                    "success": True,
                    "warning": f"Token refreshed in memory but Lambda env update failed: {e}",
                    "expires_in": expires_in,
                }

        return {"success": True, "expires_in": expires_in}

    # ── UTM tracking ────────────────────────────────────────────────

    _UTM_PLATFORM_MAP = {
        "twitter": "twitter",
        "instagram": "instagram",
        "threads": "threads",
        "tiktok": "tiktok",
    }

    _RIGACAP_URL_RE = re.compile(
        r'(https?://(?:www\.)?rigacap\.com)(/[^\s)"\']*)?\b',
        re.IGNORECASE,
    )

    @staticmethod
    def _inject_utm(text: str, platform: str) -> str:
        """Append UTM params to any rigacap.com URL in text."""
        source = SocialPostingService._UTM_PLATFORM_MAP.get(platform, platform)
        utm = urllib.parse.urlencode({
            "utm_source": source,
            "utm_medium": "social",
            "utm_campaign": "post",
        })

        def _add_utm(m):
            base = m.group(1)
            path = m.group(2) or ""
            # Don't double-add if UTM already present
            if "utm_source" in path:
                return m.group(0)
            sep = "&" if "?" in path else "?"
            return f"{base}{path}{sep}{utm}"

        return SocialPostingService._RIGACAP_URL_RE.sub(_add_utm, text)

    # ── Unified publish ──────────────────────────────────────────────

    async def publish_post(self, post) -> dict:
        """Publish a SocialPost to its target platform.

        Updates post.status and post.posted_at in-place (caller must commit).
        Returns the platform-specific result dict.
        """
        text = post.text_content or ""
        if post.hashtags:
            text += f"\n\n{post.hashtags}"

        # Auto-inject UTM tracking params into rigacap.com URLs
        text = self._inject_utm(text, post.platform)

        image_url = None
        if post.image_s3_key:
            if post.image_s3_key.startswith("https://") or post.image_s3_key.startswith("http://"):
                # Already a full URL (e.g. launch cards on CloudFront) — use directly
                image_url = post.image_s3_key
            else:
                from app.services.chart_card_generator import chart_card_generator
                image_url = chart_card_generator.get_presigned_url(
                    post.image_s3_key, expires_in=3600
                )

        if post.platform == "twitter":
            reply_to = getattr(post, 'reply_to_tweet_id', None)
            result = await self.post_to_twitter(text, image_url, reply_to_tweet_id=reply_to)
        elif post.platform == "instagram":
            # Instagram comment replies use a different API path
            if getattr(post, 'post_type', None) == "instagram_comment_reply":
                comment_id = getattr(post, 'reply_to_instagram_comment_id', None)
                if not comment_id:
                    return {"error": "No comment ID for Instagram comment reply"}
                result = await self.post_instagram_comment(comment_id, text)
            else:
                if not image_url:
                    # Auto-generate a branded text card for posts without trade charts
                    from app.services.chart_card_generator import chart_card_generator
                    png_bytes = chart_card_generator.generate_text_card(
                        text=post.text_content or "",
                        headline=getattr(post, 'post_type', '').replace('_', ' ').title(),
                    )
                    date_str = datetime.utcnow().strftime("%Y%m%d")
                    s3_key = chart_card_generator.upload_to_s3(
                        png_bytes, post.id, "text", date_str
                    )
                    if s3_key:
                        post.image_s3_key = s3_key
                        image_url = chart_card_generator.get_presigned_url(
                            s3_key, expires_in=3600
                        )
                    if not image_url:
                        return {"error": "Instagram posts require an image — failed to generate text card"}
                result = await self.post_to_instagram(text, image_url)
        elif post.platform == "threads":
            reply_to = getattr(post, 'reply_to_thread_id', None)
            result = await self.post_to_threads(text, image_url, reply_to_id=reply_to)
        elif post.platform == "tiktok":
            if not image_url:
                from app.services.chart_card_generator import chart_card_generator
                png_bytes = chart_card_generator.generate_text_card(
                    text=post.text_content or "",
                    headline=getattr(post, 'post_type', '').replace('_', ' ').title(),
                )
                date_str = datetime.utcnow().strftime("%Y%m%d")
                s3_key = chart_card_generator.upload_to_s3(
                    png_bytes, post.id, "text", date_str
                )
                if s3_key:
                    post.image_s3_key = s3_key
                    image_url = chart_card_generator.get_presigned_url(
                        s3_key, expires_in=3600
                    )
                if not image_url:
                    return {"error": "TikTok posts require an image — failed to generate text card"}
            result = await self.post_to_tiktok(text, image_url)
        else:
            return {"error": f"Unknown platform: {post.platform}"}

        if "error" not in result:
            post.status = "posted"
            post.posted_at = datetime.utcnow()

        return result


async def _async_sleep(seconds: float):
    """Async sleep without importing asyncio at module level."""
    import asyncio
    await asyncio.sleep(seconds)


# Singleton
social_posting_service = SocialPostingService()
