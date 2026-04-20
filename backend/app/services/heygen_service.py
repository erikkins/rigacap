"""
HeyGen Video Service - Generate AI avatar videos from trade results.

Uses HeyGen API v3 (Digital Twin) to create short-form video content featuring
Erik's AI avatar narrating trade results and market commentary.
Cycles through multiple avatar looks for variety.

API docs: https://developers.heygen.com/docs/quick-start
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

HEYGEN_BASE_URL = "https://api.heygen.com"

# Default voice (override via method params or env var)
DEFAULT_VOICE_ID = os.getenv("HEYGEN_DEFAULT_VOICE_ID", "")

# Multiple avatar look IDs to cycle through (comma-separated env var)
AVATAR_ROTATION = [
    a.strip() for a in os.getenv("HEYGEN_AVATAR_ROTATION", "").split(",") if a.strip()
]

# Fallback if rotation list is empty
DEFAULT_AVATAR_ID = os.getenv("HEYGEN_DEFAULT_AVATAR_ID", "")


class HeyGenService:
    """Generate AI avatar videos using HeyGen API v3 Digital Twin."""

    def __init__(self):
        self.api_key = os.getenv("HEYGEN_API_KEY", "")
        self.enabled = bool(self.api_key)
        self._avatar_index = 0
        if not self.enabled:
            logger.warning("HeyGen service disabled - HEYGEN_API_KEY not configured")

    def _next_avatar_id(self) -> str:
        """Cycle through avatar look IDs for variety."""
        if not AVATAR_ROTATION:
            return DEFAULT_AVATAR_ID
        avatar_id = AVATAR_ROTATION[self._avatar_index % len(AVATAR_ROTATION)]
        self._avatar_index += 1
        return avatar_id

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def list_avatars(self) -> Optional[list]:
        """List Digital Twin looks via v3 API."""
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{HEYGEN_BASE_URL}/v3/avatars/looks",
                    headers=self._headers(),
                    params={"avatar_type": "digital_twin", "ownership": "private"},
                )

            if resp.status_code != 200:
                logger.error(f"HeyGen list avatars error {resp.status_code}: {resp.text}")
                return None

            data = resp.json()
            avatars = data.get("data", [])
            logger.info(f"HeyGen: found {len(avatars)} digital twin looks")
            return avatars

        except Exception as e:
            logger.error(f"HeyGen list avatars failed: {e}")
            return None

    async def list_voices(self) -> Optional[list]:
        """List available voices via v3 API."""
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{HEYGEN_BASE_URL}/v3/voices",
                    headers=self._headers(),
                )

            if resp.status_code != 200:
                logger.error(f"HeyGen list voices error {resp.status_code}: {resp.text}")
                return None

            data = resp.json()
            voices = data.get("data", [])
            logger.info(f"HeyGen: found {len(voices)} voices")
            return voices

        except Exception as e:
            logger.error(f"HeyGen list voices failed: {e}")
            return None

    async def create_video(
        self,
        script: str,
        avatar_id: Optional[str] = None,
        voice_id: Optional[str] = None,
        aspect_ratio: str = "9:16",
        resolution: str = "1080p",
        background_color: str = "#172554",
        callback_url: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a Digital Twin video via v3 API.

        Args:
            script: Text for the avatar to speak (max 5000 chars).
            avatar_id: Digital Twin look ID. Cycles through rotation list if not provided.
            voice_id: Voice ID. Falls back to HEYGEN_DEFAULT_VOICE_ID.
            aspect_ratio: "9:16" (portrait/Reels/TikTok) or "16:9" (landscape).
            resolution: "4k", "1080p", or "720p".
            background_color: Hex color for background. Default is RigaCap navy.
            callback_url: Webhook URL for completion notification.

        Returns:
            video_id string if successfully queued, or None on failure.
        """
        if not self.enabled:
            logger.error("HeyGen service not enabled")
            return None

        avatar_id = avatar_id or self._next_avatar_id()
        voice_id = voice_id or DEFAULT_VOICE_ID

        if not avatar_id or not voice_id:
            logger.error("HeyGen: avatar_id and voice_id are required. "
                         "Set HEYGEN_AVATAR_ROTATION and HEYGEN_DEFAULT_VOICE_ID env vars.")
            return None

        payload = {
            "type": "avatar",
            "avatar_id": avatar_id,
            "script": script[:5000],
            "voice_id": voice_id,
            "title": f"RigaCap - {script[:40]}...",
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "background": {
                "type": "color",
                "value": background_color,
            },
        }

        if callback_url:
            payload["callback_url"] = callback_url

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{HEYGEN_BASE_URL}/v3/videos",
                    headers=self._headers(),
                    json=payload,
                )

            if resp.status_code != 200:
                logger.error(f"HeyGen create video error {resp.status_code}: {resp.text}")
                return None

            data = resp.json()
            video_id = data.get("data", {}).get("video_id")
            if video_id:
                logger.info(f"HeyGen v3: video queued, video_id={video_id}, avatar={avatar_id}")
            else:
                logger.error(f"HeyGen v3: no video_id in response: {data}")
            return video_id

        except Exception as e:
            logger.error(f"HeyGen create video failed: {e}")
            return None

    async def get_video_status(self, video_id: str) -> Optional[dict]:
        """
        Check the status of a video generation job via v3 API.

        Returns dict with status, video_url (when completed), or error (when failed).
        """
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{HEYGEN_BASE_URL}/v3/videos/{video_id}",
                    headers=self._headers(),
                )

            if resp.status_code != 200:
                logger.error(f"HeyGen video status error {resp.status_code}: {resp.text}")
                return None

            inner = resp.json().get("data", {})
            status = inner.get("status", "unknown")
            result = {"status": status, "video_id": video_id}

            if status == "completed":
                result["video_url"] = inner.get("video_url")
                result["duration"] = inner.get("duration")
                result["thumbnail_url"] = inner.get("thumbnail_url")
            elif status == "failed":
                result["error"] = inner.get("failure_message", "Unknown error")

            return result

        except Exception as e:
            logger.error(f"HeyGen video status check failed: {e}")
            return None

    async def generate_trade_video(
        self,
        trade_data: dict,
        aspect_ratio: str = "9:16",
        avatar_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Generate a video from trade result data.

        Takes the same trade_data dict used by ai_content_service and builds a
        narration script, then queues a HeyGen video with a rotating avatar.

        Returns dict with video_id and script, or None on failure.
        """
        script = self._build_trade_script(trade_data)
        if not script:
            return None

        video_id = await self.create_video(
            script=script,
            avatar_id=avatar_id,
            voice_id=voice_id,
            aspect_ratio=aspect_ratio,
        )

        if not video_id:
            return None

        return {
            "video_id": video_id,
            "script": script,
            "trade_data": trade_data,
            "aspect_ratio": aspect_ratio,
        }

    @staticmethod
    def _build_trade_script(trade_data: dict) -> Optional[str]:
        """Build a narration script from trade result data."""
        symbol = trade_data.get("symbol")
        pnl_pct = trade_data.get("pnl_pct")
        entry_price = trade_data.get("entry_price")
        exit_price = trade_data.get("exit_price")
        entry_date = str(trade_data.get("entry_date", ""))[:10]
        exit_date = str(trade_data.get("exit_date", ""))[:10]
        exit_reason = trade_data.get("exit_reason", "trailing_stop")

        if not symbol or pnl_pct is None:
            logger.error("Trade data missing required fields (symbol, pnl_pct)")
            return None

        if pnl_pct > 0:
            script = (
                f"Our system flagged {symbol} on {entry_date} at {entry_price:.2f} dollars. "
                f"We exited on {exit_date} at {exit_price:.2f} for a {pnl_pct:+.1f}% gain. "
            )
            if exit_reason == "trailing_stop":
                script += "The trailing stop locked in profits on the way up. "
            elif exit_reason == "market_regime":
                script += "Our market regime filter signaled caution, so we took profits early. "

            script += (
                "No luck involved. This is algorithmic momentum, walk-forward validated "
                "across five years of live market data. "
                "See our full track record at rigacap.com."
            )
        else:
            script = (
                f"Transparency matters. Our system entered {symbol} on {entry_date} "
                f"at {entry_price:.2f} and exited on {exit_date} at {exit_price:.2f} "
                f"for a {pnl_pct:+.1f}% loss. "
            )
            if exit_reason == "trailing_stop":
                script += "The trailing stop did its job, limiting the downside. "
            elif exit_reason == "market_regime":
                script += "Our regime detector caught the shift and cut the position. "

            script += (
                "Not every trade wins. But our system manages risk so one bad trade "
                "doesn't derail the portfolio. Check our verified track record at rigacap.com."
            )

        return script


heygen_service = HeyGenService()
