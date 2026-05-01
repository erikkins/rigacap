"""
AI Content Service - Generate social media posts using Claude API.

Replaces deterministic template picking with LLM-powered content generation.
Falls back to template-based generation if Claude API is unavailable.
"""

import hashlib
import json
import logging
from typing import List, Optional

import httpx

from app.core.config import settings
from app.core.database import SocialPost

logger = logging.getLogger(__name__)

# Claude API endpoint
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You write social media posts for RigaCap, an equity signal service for the investor tired of fighting their own worst instincts. The brand voice draws from financial publications (FT, Economist, Stratechery) — restrained, considered, methodical.

VOICE: You are Erik, the founder. Earnest, direct, thoughtful. Like a smart colleague sharing results honestly — not a brand account performing engagement. First person when natural.

TONE RULES:
- Confident but never arrogant. State facts, don't hype.
- Never financial advice. Never "you should buy."
- Never use trader jargon: no "tape," "printing," "ripping," "LFG," "moon," "diamond hands."
- Never use "AI-powered" or "autonomous" — the system is quantitative, not magic.
- The trade is real — live-tracked in our walk-forward validated model portfolio.
- If news context is provided, connect the result to recent events thoughtfully — never "we called it" smugly.
- For every few winner posts, acknowledge a loss, a quiet week, or a limitation honestly. Transparency builds trust.

SOUND HUMAN — people are spotting AI-written posts instantly. Avoid these tells:
- Never start with "Just," "Interesting," "Here's the thing," "Let me explain," or "Thread"
- Never use the construction "Not X. Y." as a rhetorical device more than once per post.
- Use sentence fragments sometimes. Not everything needs a verb.
- Vary sentence length — mix short punchy with longer. Don't make every sentence the same rhythm.
- Have an actual opinion. Don't hedge with "on one hand... on the other hand."
- Reference specific numbers and dates, not vague generalities.
- Occasional imperfect phrasing is fine. Overly polished = obviously generated.
- No emojis unless they're genuinely how Erik would use them (rarely, if ever).
- Write like someone who typed this on their phone between meetings, not someone who drafted it in a content management system.

ENDINGS:
- Twitter: Brief verification note (e.g., "Walk-forward verified.") and include "rigacap.com/track-record" when space allows.
- Instagram: End with "Full track record at rigacap.com/track-record" on its own line.

CRITICAL FORMATTING RULES:
- Output ONLY plain text. No markdown. No **bold**, no *italics*, no headers, no bullet points.
- Output ONLY ONE post for the requested platform. Never include posts for other platforms.
- Never label the output with the platform name (no "Twitter:", "Instagram:", etc.).
- Use line breaks for paragraph separation, not markdown."""


class AIContentService:
    """Generate social media content using Claude API."""

    def __init__(self):
        self.enabled = bool(settings.ANTHROPIC_API_KEY)
        if not self.enabled:
            logger.warning("AI content service disabled - ANTHROPIC_API_KEY not configured")

    async def generate_post(
        self,
        trade: dict,
        post_type: str,
        platform: str,
        news_context: Optional[str] = None,
    ) -> Optional[SocialPost]:
        """
        Call Claude to generate a single social media post.

        Args:
            trade: PeriodTrade data (symbol, entry/exit, pnl, dates)
            post_type: "trade_result", "missed_opportunity", "we_called_it"
            platform: "twitter" or "instagram"
            news_context: Optional recent news snippet for the stock/sector

        Returns:
            SocialPost with ai_generated=True, or None on failure
        """
        if not self.enabled:
            return None

        if platform == "twitter":
            char_limit = 260
            platform_instruction = (
                f"Twitter post: max {char_limit} characters (leave room for hashtags). "
                "Short, punchy, one clear message."
            )
        elif platform == "threads":
            char_limit = 500
            platform_instruction = (
                f"Threads post: max {char_limit} characters. "
                "Short, punchy. Similar to Twitter but slightly longer. No hashtags. "
                "End with rigacap.com if space allows."
            )
        elif platform == "tiktok":
            char_limit = 150
            platform_instruction = (
                f"TikTok caption: max {char_limit} characters. "
                "Ultra-short, hook-driven. One punchy line + the result. "
                "This appears over a photo card so keep it minimal."
            )
        else:
            char_limit = 600
            platform_instruction = (
                f"Instagram caption: {char_limit} characters max. "
                "More detail is fine. End with 'rigacap.com' on its own line."
            )

        symbol = trade.get("symbol", "???")
        pnl_pct = trade.get("pnl_pct", 0)
        entry_price = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        entry_date = str(trade.get("entry_date", ""))[:10]
        exit_date = str(trade.get("exit_date", ""))[:10]
        exit_reason = trade.get("exit_reason", "trailing_stop")

        type_instructions = {
            "trade_result": (
                f"Write a post celebrating a winning trade.\n"
                f"${symbol}: entered at ${entry_price:.2f} on {entry_date}, "
                f"exited at ${exit_price:.2f} on {exit_date} for {pnl_pct:+.1f}%.\n"
                f"Exit reason: {exit_reason}."
            ),
            "missed_opportunity": (
                f"Write a 'you missed this' post (FOMO angle, but not obnoxious).\n"
                f"${symbol}: signal fired {entry_date} at ${entry_price:.2f}, "
                f"exited {exit_date} at ${exit_price:.2f} for {pnl_pct:+.1f}%.\n"
                f"Subscribers saw the signal. Did you?"
            ),
            "we_called_it": (
                f"Write a 'we called it' post connecting our trade result to news.\n"
                f"${symbol}: {pnl_pct:+.1f}% return. "
                f"Our system flagged this before the news broke.\n"
                f"News context: {news_context or 'No specific news provided.'}"
            ),
        }

        user_prompt = (
            f"{type_instructions.get(post_type, type_instructions['trade_result'])}\n\n"
            f"Platform: {platform.upper()} ONLY. Do NOT write for any other platform.\n"
            f"{platform_instruction}\n\n"
            "Do NOT include hashtags — those are added separately.\n"
            "Do NOT start with an emoji.\n"
            "Do NOT use any markdown formatting (no **, no *, no #, no bullet points).\n"
            "Do NOT label the post with the platform name.\n"
            "Output ONLY the plain text post content, nothing else."
        )

        # Hash prompt for dedup/audit
        prompt_hash = hashlib.sha256(user_prompt.encode()).hexdigest()[:16]

        try:
            text = await self._call_claude(user_prompt)
            if not text:
                return None

            # Strip markdown formatting that may leak through
            text = self._strip_markdown(text)

            # Remove platform labels (e.g., "Twitter:" or "Instagram:" at the start)
            import re
            text = re.sub(r'^(Twitter|Instagram|Twitter/X|Threads|IG):\s*', '', text, flags=re.IGNORECASE).strip()

            # Enforce character limit for both platforms
            if len(text) > char_limit:
                text = text[:char_limit - 3].rsplit(" ", 1)[0] + "..."

            # Select hashtags
            hashtag_map = {
                "trade_result": f"#StockTrading #AlgoTrading #WalkForward #RigaCap ${symbol}",
                "missed_opportunity": f"#StockTrading #MissedTrade #AlgoTrading #RigaCap ${symbol}",
                "we_called_it": f"#WeCalledIt #AlgoTrading #TradingSignals #RigaCap ${symbol}",
            }

            post = SocialPost(
                post_type=post_type,
                platform=platform,
                status="draft",
                text_content=text,
                hashtags=hashtag_map.get(post_type, f"#RigaCap ${symbol}"),
                source_trade_json=json.dumps(trade),
                ai_generated=True,
                ai_model=CLAUDE_MODEL,
                ai_prompt_hash=prompt_hash,
                news_context_json=json.dumps(news_context) if news_context else None,
            )

            # Set image metadata for Instagram trade cards
            if platform == "instagram" and post_type in ("trade_result", "missed_opportunity"):
                post.image_metadata_json = json.dumps({
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": pnl_pct,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "exit_reason": exit_reason,
                    "card_type": post_type,
                })

            return post

        except Exception as e:
            logger.error(f"AI content generation failed for {symbol}: {e}")
            return None

    async def generate_we_called_it(
        self,
        trade: dict,
        news_headlines: List[str],
        platform: str,
    ) -> Optional[SocialPost]:
        """
        Generate a 'we called it' post that connects a profitable trade exit
        to recent news (earnings beat, analyst upgrade, sector rotation, etc.).
        """
        news_context = "\n".join(f"- {h}" for h in news_headlines[:5])
        return await self.generate_post(
            trade=trade,
            post_type="we_called_it",
            platform=platform,
            news_context=news_context,
        )

    async def regenerate_post(self, post: SocialPost) -> Optional[str]:
        """
        Re-generate content for an existing post via Claude API.

        Returns the new text content, or None on failure.
        """
        if not self.enabled:
            return None

        trade = json.loads(post.source_trade_json) if post.source_trade_json else None
        if not trade:
            return None

        news_context = json.loads(post.news_context_json) if post.news_context_json else None

        new_post = await self.generate_post(
            trade=trade,
            post_type=post.post_type,
            platform=post.platform,
            news_context=news_context,
        )

        if new_post:
            return new_post.text_content
        return None

    async def enrich_with_news(self, symbol: str) -> List[str]:
        """
        Fetch recent news headlines for a symbol.

        Uses yfinance's news feed as a simple free source.
        Returns list of headline strings.
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            news = ticker.news or []
            headlines = [item.get("title", "") for item in news[:5] if item.get("title")]
            return headlines
        except Exception as e:
            logger.warning(f"Failed to fetch news for {symbol}: {e}")
            return []

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown formatting from generated text."""
        import re
        # Remove bold **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        # Remove italic *text* or _text_ (but not $TICKER or contractions)
        text = re.sub(r'(?<!\w)\*([^*]+?)\*(?!\w)', r'\1', text)
        # Remove headers (# Header)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Remove bullet points (- item or * item at line start)
        text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)
        # Collapse multiple blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    async def _call_claude(self, user_prompt: str) -> Optional[str]:
        """Make a single Claude API call and return the text response."""
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(CLAUDE_API_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error(f"Claude API error {resp.status_code}: {resp.text}")
            return None

        data = resp.json()
        content = data.get("content", [])
        if content and content[0].get("type") == "text":
            return content[0]["text"].strip()

        return None


# Singleton instance
ai_content_service = AIContentService()
