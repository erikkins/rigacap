"""
Social Engagement Opportunities Service

Scans Twitter feeds from curated finance accounts, filters for
topics RigaCap has a strong take on, and generates Claude-drafted
comment suggestions for the founder to post manually.

Daily 9 AM ET delivery via admin email.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Curated finance accounts to monitor — pulled from RigaCap's actual
# Twitter following list + hand-picked additions for engagement value.
# Format: (twitter_handle, display_name, why_we_follow)
MONITORED_ACCOUNTS = [
    # Already following on Twitter
    ("MacroCharts", "Macro Charts", "macro + regime analysis"),
    ("sentimentrader", "SentimenTrader", "sentiment/fear analysis"),
    ("markminervini", "Mark Minervini", "SEPA momentum methodology"),
    ("unusual_whales", "Unusual Whales", "market data + flow"),
    ("GarethSoloway", "Gareth Soloway", "technical analysis + macro"),
    ("LindaRaschke", "Linda Raschke", "systematic trading legend"),
    ("Ritholtz", "Barry Ritholtz", "market commentary + macro"),
    ("morganhousel", "Morgan Housel", "investing psychology"),
    ("PeterLBrandt", "Peter Brandt", "technical analysis + risk mgmt"),
    ("mikeharrisNY", "Michael Harris", "quant analysis"),
    ("thetraderisk", "Trade Risk", "objective market research"),
    ("RedDogT3", "Scott Redler", "market strategy"),
    ("elerianm", "Mohamed El-Erian", "macro economics"),
    ("TrendSpider", "TrendSpider", "technical analysis platform"),
    # High-value additions to follow
    ("TraderLion", "TraderLion", "momentum/growth trading community"),
    ("IBDinvestors", "IBD Investors", "momentum/growth methodology"),
    ("WillieDelwiche", "Willie Delwiche", "market breadth + regimes"),
    ("AndrewThrasher", "Andrew Thrasher", "market breadth analysis"),
    ("RyanDetrick", "Ryan Detrick", "seasonality + market stats"),
    ("LizAnnSonders", "Liz Ann Sonders", "Schwab chief strategist"),
]

# Topics we have strong takes on — used for keyword filtering
TOPIC_KEYWORDS = [
    # Market regime
    "bull market", "bear market", "market regime", "regime change",
    "market crash", "correction", "recovery", "breadth",
    "rotating", "rotation", "sector rotation",
    # Momentum / signals
    "momentum", "breakout", "signal", "buy signal", "sell signal",
    "trailing stop", "stop loss", "risk management",
    # Strategy / backtesting
    "backtest", "walk forward", "walk-forward", "systematic",
    "algorithmic", "quant", "rules-based",
    # Market conditions
    "VIX", "volatility", "fear", "market fear",
    "SPY", "S&P 500", "200-day", "moving average",
    # General themes we can riff on
    "win rate", "drawdown", "max drawdown", "sharpe",
    "position sizing", "portfolio", "concentration",
    "let winners run", "cut losses",
]

# Minimum keyword matches to qualify a tweet as relevant
MIN_KEYWORD_MATCHES = 1

# Skip posts that are hostile to our category — replying would look
# like we're defending "slick signal services" or picking a fight.
NEGATIVE_KEYWORDS = [
    "scam", "slimy", "snake oil", "fraud", "con artist", "rip off",
    "ripoff", "garbage", "worthless", "waste of money", "don't trust",
    "never trust", "avoid", "stay away", "predatory", "deceived",
    "signaling services", "signal service scam", "prop firm",
    "sim prop", "fake signals", "pump and dump",
]


class EngagementService:

    def _get_twitter_headers(self) -> dict:
        """Build OAuth 1.0a headers for Twitter API v2."""
        import hashlib
        import hmac
        import time
        import urllib.parse
        import uuid
        from app.core.config import settings

        # For read-only endpoints, we can use Bearer token (app-only auth)
        # But user timeline requires user context. Use OAuth 1.0a.
        # Actually for reading OTHER users' tweets, app-only (Bearer) works.
        # Let's try Bearer first — simpler.
        return {
            "Authorization": f"Bearer {self._get_bearer_token()}",
        }

    def _get_bearer_token(self) -> str:
        """Get Twitter app-only Bearer token using API key + secret."""
        import base64
        import httpx
        from app.core.config import settings

        key = settings.TWITTER_API_KEY
        secret = settings.TWITTER_API_SECRET
        credentials = base64.b64encode(f"{key}:{secret}".encode()).decode()

        resp = httpx.post(
            "https://api.twitter.com/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials",
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
        logger.error(f"Bearer token fetch failed: {resp.status_code} {resp.text[:200]}")
        return ""

    def _resolve_user_id(self, handle: str, headers: dict) -> Optional[str]:
        """Resolve a Twitter handle to a user ID."""
        import httpx
        try:
            resp = httpx.get(
                f"https://api.twitter.com/2/users/by/username/{handle}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("id")
        except Exception as e:
            logger.warning(f"Failed to resolve @{handle}: {e}")
        return None

    def _get_user_tweets(self, user_id: str, headers: dict, since_hours: int = 24) -> List[dict]:
        """Get recent tweets from a specific user."""
        import httpx
        since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            resp = httpx.get(
                f"https://api.twitter.com/2/users/{user_id}/tweets",
                headers=headers,
                params={
                    "max_results": 10,
                    "start_time": since,
                    "tweet.fields": "created_at,public_metrics,text",
                    "exclude": "retweets,replies",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
            elif resp.status_code == 429:
                logger.warning("Twitter rate limit hit")
                return []
        except Exception as e:
            logger.warning(f"Failed to fetch tweets for user {user_id}: {e}")
        return []

    def _score_relevance(self, text: str) -> tuple:
        """Score a tweet's relevance to RigaCap's topics. Returns (score, matched_keywords).
        Returns -1 if the post is hostile to our category (negative filter)."""
        text_lower = text.lower()
        # Skip hostile posts — replying looks like we're defending the industry
        if any(neg in text_lower for neg in NEGATIVE_KEYWORDS):
            return -1, []
        matches = [kw for kw in TOPIC_KEYWORDS if kw.lower() in text_lower]
        return len(matches), matches

    def _generate_comment(self, tweet_text: str, author: str, matched_topics: List[str],
                          market_context: str = "") -> str:
        """Use Claude to draft a suggested comment, post-filtered for voice violations."""
        import httpx
        from app.core.config import settings
        from app.services.voice_filters import (
            banned_summary_for_prompt,
            generate_with_voice_filter,
        )

        if not settings.ANTHROPIC_API_KEY:
            return "(Claude API key not available — draft manually)"

        # Voice ban list is enforced via post-filter; this prompt-time mention
        # is a soft hint only. The hard enforcement happens after generation.
        banned_hint = banned_summary_for_prompt()

        base_system = (
            "You write short Twitter replies as Erik, founder of RigaCap — an equity signal "
            "service for the investor tired of fighting their own worst instincts. "
            "You're a real person, not a brand account. "
            "\n\n"
            "GOAL: induce curiosity, NOT pitch the product. The best reply is one where a "
            "reader thinks 'who is this person?' and clicks through to find out — not one "
            "that hands them the answer. The curiosity hook is CALM SPECIFICITY, not "
            "contrarian heat. The world has plenty of takes; Erik's voice brings the "
            "temperature down by referencing what a disciplined system actually does in "
            "conditions like these.\n\n"
            "VOICE: Considered, restrained, methodical. Editorial-financial-publication register "
            "(think FT, Economist, Stratechery). Earnest and direct — like a smart colleague at "
            "dinner, not a fintech CEO on stage. Reads as 'the calm specific voice in a noisy "
            "thread,' never as 'the smartest person in the replies.'\n\n"
            "EVERY REPLY MUST INCLUDE AT LEAST ONE OF:\n"
            "  (a) a concrete, specific number — years of track record, win/loss rates, "
            "trailing-stop width, days held in cash, percentage of trades that exited at the stop, "
            "real walk-forward stats — anything specific enough that it stops a scroll.\n"
            "  (b) an observation about the cost of reacting to noise — what a disciplined "
            "system would do here, or has done in similar conditions before. The 'would' tense "
            "is key: you're sharing what discipline looks like, not telling the author they're "
            "wrong. ('In rotating-bull regimes the system usually holds through this kind of "
            "one-day move.')\n"
            "  (c) an honest admission of a limitation, miss, or losing trade. Vulnerability beats "
            "polish on social. Saying 'we missed this one' or 'the system was wrong about X' is "
            "better than another 'great take' agreement.\n\n"
            "NEVER:\n"
            "  - Refute, debunk, or 'actually' the author.\n"
            "  - Position the reply as a correction or a teaching moment.\n"
            "  - Use 'you' pointed at the author. Address the *topic*, not the person.\n"
            "  - Lead with disagreement language ('not quite', 'but actually', 'the problem with that…').\n"
            "  - Use passive-aggressive softeners ('to be fair', 'to be honest').\n\n"
            "A reader should think 'huh, that's a different angle' — not 'ouch, Erik just called "
            "that guy out.'\n\n"
            "RULES: "
            f"- {banned_hint} "
            "- Say it like you'd say it to a friend who reads the FT but isn't a trader. "
            "- Never say 'our algorithm'. You can reference 'our system' ONLY if natural. "
            "- Most replies should NOT mention RigaCap at all — just share a smart, specific take. "
            "- NEVER pitch product features (signals/month, pricing, trial). The brand is the "
            "implicit reward for clicking through; do not give it away in the reply itself. "
            "- BANNED PATTERNS: 'great point', 'agreed, X matters', 'this is the discipline angle', "
            "'worth noting', 'this resonates', 'absolutely' — these are filler that adds nothing.\n"
            "- 1-2 sentences max. No hashtags. No emojis. "
            "- Em-dashes are welcome — they're editorial. "
            "- SOUND HUMAN: never start with 'Interesting' or 'Great point' or 'Just'. "
            "  Have a real opinion. Use fragments sometimes. Vary rhythm. "
            "  Write like you typed it on your phone, not like you drafted it.\n\n"
            "AVAILABLE SPECIFICS YOU CAN REFERENCE NATURALLY:\n"
            "  - 11-year walk-forward track record\n"
            "  - 21.5% annualized over both 5-year and 11-year windows\n"
            "  - 12% trailing stop discipline\n"
            "  - System stays in cash during regime exits — quiet weeks happen often by design\n"
            "  - 3-4 high-conviction signals per month\n"
            "  - Walk-forward validated, regime-aware, concentrated by design"
        )

        market_note = f"\n\nToday's market context for reference: {market_context}" if market_context else ""

        base_prompt = (
            f"Write a reply to this tweet by @{author}:\n\n"
            f'"{tweet_text}"\n\n'
            f"Relevant topics: {', '.join(matched_topics)}.{market_note}\n\n"
            f"Draft a 1-2 sentence reply that adds insight. Don't pitch anything."
        )

        def _call_claude(extra_directive: Optional[str]) -> Optional[str]:
            system = base_system + ("\n\n" + extra_directive if extra_directive else "")
            try:
                resp = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-6",
                        "max_tokens": 150,
                        "system": system,
                        "messages": [{"role": "user", "content": base_prompt}],
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    content = resp.json().get("content", [])
                    if content and content[0].get("type") == "text":
                        return content[0]["text"].strip().strip('"')
            except Exception as e:
                logger.warning(f"Claude comment generation failed: {e}")
            return None

        clean = generate_with_voice_filter(_call_claude, max_retries=2, label="engagement")
        if clean:
            return clean
        return "(Voice filter failed — manual draft needed; banned terms detected in all attempts)"

    async def scan_engagement_opportunities(
        self, max_opportunities: int = 5, since_hours: int = 24
    ) -> List[Dict]:
        """
        Scan monitored Twitter accounts for engagement-worthy posts.

        Returns a list of opportunities, each with:
        - author, handle, tweet_text, tweet_url
        - relevance_score, matched_topics
        - suggested_comment (Claude-drafted)
        """
        import asyncio

        headers = self._get_twitter_headers()
        if not headers.get("Authorization") or headers["Authorization"] == "Bearer ":
            return [{"error": "Failed to get Twitter Bearer token"}]

        # Resolve handles → user IDs (cache these eventually)
        all_tweets = []
        for handle, display_name, _ in MONITORED_ACCOUNTS:
            user_id = self._resolve_user_id(handle, headers)
            if not user_id:
                continue
            tweets = self._get_user_tweets(user_id, headers, since_hours)
            for t in tweets:
                score, keywords = self._score_relevance(t.get("text", ""))
                if score >= MIN_KEYWORD_MATCHES:
                    metrics = t.get("public_metrics", {})
                    all_tweets.append({
                        "author": display_name,
                        "handle": handle,
                        "tweet_id": t["id"],
                        "tweet_text": t["text"],
                        "tweet_url": f"https://twitter.com/{handle}/status/{t['id']}",
                        "created_at": t.get("created_at"),
                        "likes": metrics.get("like_count", 0),
                        "retweets": metrics.get("retweet_count", 0),
                        "replies": metrics.get("reply_count", 0),
                        "relevance_score": score,
                        "matched_topics": keywords,
                    })

        # Sort by relevance × engagement
        all_tweets.sort(
            key=lambda t: t["relevance_score"] * (1 + t["likes"] + t["retweets"] * 3),
            reverse=True,
        )

        # Take top N and generate comments
        opportunities = all_tweets[:max_opportunities]

        # Get today's market context for Claude (if available)
        market_context = ""
        try:
            import boto3
            import json
            s3 = boto3.client("s3", region_name="us-east-1")
            obj = s3.get_object(
                Bucket="rigacap-prod-price-data-149218244179",
                Key="signals/dashboard.json",
            )
            dash = json.loads(obj["Body"].read())
            market_context = dash.get("market_context", "")
        except Exception:
            pass

        for opp in opportunities:
            opp["suggested_comment"] = self._generate_comment(
                opp["tweet_text"],
                opp["handle"],
                opp["matched_topics"],
                market_context,
            )

        return opportunities


engagement_service = EngagementService()
