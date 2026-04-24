"""
Reply Scanner Service — Scan tweets from followed accounts, match symbols
to walk-forward trades, and generate contextual reply drafts via Claude API.

Generated replies are saved as SocialPost drafts with post_type='contextual_reply'
for admin review before publishing.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.database import SocialPost, WalkForwardSimulation
from app.services.social_posting_service import social_posting_service

logger = logging.getLogger(__name__)

# Claude API (same endpoint/model as ai_content_service)
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

REPLY_SYSTEM_PROMPT = """You write Twitter replies as Erik, founder of RigaCap — a disciplined momentum strategy for self-directed investors.
Someone you follow tweeted about a stock that our system traded. Write a brief, natural reply that adds value.

VOICE: You are Erik, the founder. Earnest, direct, like a colleague — not a brand account.
- Say "our system flagged this" or "we caught this move", never "we predicted"
- NEVER give financial advice
- NEVER use hashtags in replies
- NEVER start with "Great post!" "Nice call!" "Interesting" "Just" or "Here's the thing"
- NEVER use jargon: no "tape," "printing," "ripping," "LFG"
- One concise point. Don't ramble.
- Sound like you typed this on your phone. Not polished, not drafted. Real.
- Have an opinion. Don't hedge.

FORMAT: Under 260 chars. Plain text only. No markdown. No emojis at start.
Include rigacap.com/track-record only if space allows naturally."""

THREADS_REPLY_SYSTEM_PROMPT = """You write Threads replies as Erik, founder of RigaCap — a disciplined momentum strategy for self-directed investors.
Someone posted about a stock that our system traded. Write a brief, natural reply that adds value.

VOICE: You are Erik, the founder. Earnest, direct, like a colleague — not a brand account.
- Say "our system flagged this" or "we caught this move", never "we predicted"
- NEVER give financial advice
- NEVER use hashtags in replies
- NEVER start with "Great post!" "Nice call!" "Interesting" "Just" or "Here's the thing"
- NEVER use jargon: no "tape," "printing," "ripping," "LFG"
- One concise point. Don't ramble.
- Sound like you typed this on your phone. Not polished, not drafted. Real.
- Have an opinion. Don't hedge.

FORMAT: Under 350 chars. Plain text only. No markdown. No emojis at start.
Include rigacap.com/track-record if space allows naturally."""

# Twitter API v2 endpoint for user tweets
TWITTER_USER_TWEETS_URL = "https://api.twitter.com/2/users/{user_id}/tweets"

# Threads API
THREADS_API_BASE = "https://graph.threads.net/v1.0"

# Accounts to monitor — username -> {name, category}
# Sourced from docs/social-target-list.md (X handles only)
FOLLOWED_ACCOUNTS: Dict[str, dict] = {
    "unusual_whales": {"name": "Unusual Whales", "category": "fintwit"},
    "PeterLBrandt": {"name": "Peter Brandt", "category": "fintwit"},
    "MacroCharts": {"name": "MacroCharts", "category": "fintwit"},
    "sentimentrader": {"name": "SentimenTrader", "category": "fintwit"},
    "thetraderisk": {"name": "Evan Medeiros", "category": "fintwit"},
    "QuantConnect": {"name": "QuantConnect", "category": "fintwit"},
    "mikeharrisNY": {"name": "Mike Harris", "category": "fintwit"},
    "AlpacaHQ": {"name": "Alpaca", "category": "fintech"},
    "TradingView": {"name": "TradingView", "category": "fintech"},
    "TrendSpider": {"name": "TrendSpider", "category": "fintech"},
    "LuxAlgo": {"name": "LuxAlgo", "category": "fintech"},
    "TradeZella": {"name": "TradeZella", "category": "fintech"},
    "Stocktwits": {"name": "Stocktwits", "category": "fintech"},
    "elelaborateholder": {"name": "Mohamed El-Erian", "category": "media"},
    "morganhousel": {"name": "Morgan Housel", "category": "media"},
    "ritholtz": {"name": "Barry Ritholtz", "category": "media"},
    "KateRooney": {"name": "Kate Rooney", "category": "media"},
    "markminervini": {"name": "Mark Minervini", "category": "educator"},
    "LindaRaschke": {"name": "Linda Raschke", "category": "educator"},
    "UmarAshraf": {"name": "Umar Ashraf", "category": "educator"},
    "RedDogT3": {"name": "Scott Redler", "category": "educator"},
    "garethsoloway": {"name": "Gareth Soloway", "category": "educator"},
    "Tickeron": {"name": "Tickeron", "category": "partner"},
    "Quantpedia": {"name": "Quantpedia", "category": "partner"},
    "QuantStart": {"name": "QuantStart", "category": "partner"},
    "TradersPost": {"name": "TradersPost", "category": "partner"},
}

# Company name -> ticker mappings for extraction
# Company names that are unambiguous — won't match common English words.
# Excluded: apple, snap, block, target, arm, unity, elastic, meta, uber, discord, visa
# Those require a cashtag ($AAPL) to match.
COMPANY_TO_TICKER: Dict[str, str] = {
    "nvidia": "NVDA", "microsoft": "MSFT", "amazon": "AMZN",
    "google": "GOOGL", "alphabet": "GOOGL", "facebook": "META",
    "tesla": "TSLA", "netflix": "NFLX", "broadcom": "AVGO",
    "qualcomm": "QCOM", "micron": "MU", "salesforce": "CRM",
    "adobe": "ADBE", "palantir": "PLTR", "snowflake": "SNOW", "crowdstrike": "CRWD",
    "palo alto networks": "PANW", "datadog": "DDOG", "servicenow": "NOW", "shopify": "SHOP",
    "coinbase": "COIN", "robinhood": "HOOD", "sofi": "SOFI", "paypal": "PYPL",
    "lyft": "LYFT", "airbnb": "ABNB", "doordash": "DASH", "roku": "ROKU",
    "spotify": "SPOT", "snapchat": "SNAP", "pinterest": "PINS",
    "costco": "COST", "walmart": "WMT", "home depot": "HD",
    "nike": "NKE", "starbucks": "SBUX", "mcdonalds": "MCD", "coca-cola": "KO",
    "pepsi": "PEP", "pepsico": "PEP", "procter & gamble": "PG", "johnson & johnson": "JNJ",
    "jpmorgan": "JPM", "goldman sachs": "GS", "morgan stanley": "MS",
    "bank of america": "BAC", "wells fargo": "WFC", "citigroup": "C",
    "mastercard": "MA", "american express": "AXP",
    "unitedhealth": "UNH", "pfizer": "PFE", "eli lilly": "LLY", "abbvie": "ABBV",
    "novo nordisk": "NVO", "merck": "MRK", "moderna": "MRNA",
    "exxon": "XOM", "chevron": "CVX", "conocophillips": "COP",
    "boeing": "BA", "lockheed martin": "LMT", "raytheon": "RTX",
    "disney": "DIS", "comcast": "CMCSA", "paramount": "PARA",
    "super micro": "SMCI", "supermicro": "SMCI",
    "arista networks": "ANET", "fortinet": "FTNT", "zscaler": "ZS",
    "mongodb": "MDB", "confluent": "CFLT",
    "trade desk": "TTD", "roblox": "RBLX",
    "rivian": "RIVN", "lucid motors": "LCID", "nio": "NIO",
}

# Words that look like tickers but aren't
FALSE_POSITIVE_TICKERS = {
    "AI", "CEO", "CFO", "CTO", "COO", "IPO", "ETF", "GDP", "CPI", "PPI",
    "PCE", "FED", "SEC", "FBI", "CIA", "DOJ", "FDA", "EPA", "CDC", "WHO",
    "IMF", "NATO", "NYSE", "FOMC", "OPEC", "API", "SDK", "GPU", "CPU",
    "RAM", "SSD", "HDD", "USB", "URL", "PDF", "CSV", "SQL", "AWS", "GCP",
    "IT", "HR", "PR", "QA", "PM", "VP", "MD", "PhD", "MBA", "CPA",
    "USA", "UK", "EU", "US", "UN", "UAE", "GDP", "ROI", "P&L", "EPS",
    "PE", "PS", "PB", "DD", "TA", "FA", "DCA", "ATH", "ATL", "YTD",
    "QoQ", "MoM", "YoY", "EOD", "AH", "PM", "AM", "EST", "PST", "UTC",
    "LOL", "IMO", "FWIW", "TBH", "NGL", "LMAO", "YOLO", "FUD", "HODL",
    "ALL", "ARE", "FOR", "HAS", "HIS", "HOW", "ITS", "MAY", "NEW",
    "NOW", "OLD", "OUR", "OUT", "OWN", "SAY", "SHE", "TOO", "TWO",
    "WAR", "WAY", "DAY", "BIG", "RUN", "TOP", "LOW", "HIGH", "CALL",
    "PUT", "LONG", "BUY", "SELL", "HOLD", "CASH", "BOND", "BEAR", "BULL",
    "OPEN", "NEXT", "JUST", "BEST", "GOOD", "REAL", "FREE", "TRUE", "FAST",
    "SAFE", "RISK", "PUMP", "DUMP", "MOON", "DEEP", "EDGE",
}

# Financial context words — nearby presence increases ticker confidence
_FINANCIAL_CONTEXT_WORDS = {
    "stock", "share", "shares", "price", "earnings", "revenue", "buy", "sell",
    "bullish", "bearish", "long", "short", "calls", "puts", "options",
    "breakout", "rally", "dip", "drop", "surge", "crash", "pump", "dump",
    "target", "upgrade", "downgrade", "analyst", "quarter", "q1", "q2", "q3", "q4",
    "eps", "pe", "market", "trading", "chart", "technical", "momentum",
    "resistance", "support", "volume", "squeeze", "gap", "highs", "lows",
}


def extract_symbols(text: str) -> List[str]:
    """
    Extract stock ticker symbols from tweet text using 3-tier extraction:
    1. Cashtags ($NVDA) — highest confidence
    2. Bare uppercase tickers (3+ chars) near financial context words
    3. Company name mentions (word-boundary match, not substring)

    Returns deduplicated list of valid-looking symbols.
    """
    symbols = set()

    # Strip @mentions and URLs before analysis (prevents username/URL false positives)
    clean_text = re.sub(r'@\w+', '', text)
    clean_text = re.sub(r'https?://\S+', '', clean_text)

    # Tier 1: Cashtags ($NVDA, $AAPL) — always trusted
    cashtags = re.findall(r'\$([A-Z]{1,5})\b', text)
    for tag in cashtags:
        if tag not in FALSE_POSITIVE_TICKERS:
            symbols.add(tag)

    # Tier 2: Bare uppercase tickers (3-5 chars) near financial context
    clean_lower = clean_text.lower()
    has_financial_context = any(w in clean_lower for w in _FINANCIAL_CONTEXT_WORDS)
    if has_financial_context:
        bare_tickers = re.findall(r'\b([A-Z]{3,5})\b', clean_text)
        for ticker in bare_tickers:
            if ticker not in FALSE_POSITIVE_TICKERS:
                symbols.add(ticker)

    # Tier 3: Company name mentions (word-boundary match)
    for name, ticker in COMPANY_TO_TICKER.items():
        if re.search(r'\b' + re.escape(name) + r'\b', clean_lower):
            symbols.add(ticker)

    return list(symbols)


class ReplyScannerService:
    """Scan followed accounts' tweets, match to trades, generate reply drafts."""

    def __init__(self):
        self.enabled = bool(settings.ANTHROPIC_API_KEY) and bool(settings.TWITTER_API_KEY)
        self._user_id_cache: Dict[str, str] = {}

    async def scan_and_generate(
        self,
        db,
        since_hours: int = 4,
        dry_run: bool = False,
        accounts: Optional[List[str]] = None,
        platforms: Optional[List[str]] = None,
    ) -> dict:
        """
        Main entry point. Scan tweets/threads, extract symbols, match trades, generate replies.

        Args:
            db: AsyncSession
            since_hours: How far back to look for posts
            dry_run: If True, generate reply text but don't save to DB
            accounts: Optional list of usernames to scan (defaults to all)
            platforms: Platforms to scan (default: ["twitter", "threads"])

        Returns:
            Summary dict with counts and details
        """
        if not self.enabled:
            return {"error": "Reply scanner disabled — missing API keys"}

        if platforms is None:
            platforms = ["twitter"]
            if settings.THREADS_ACCESS_TOKEN:
                platforms.append("threads")

        target_accounts = accounts or list(FOLLOWED_ACCOUNTS.keys())
        results = {
            "scanned_accounts": 0,
            "tweets_found": 0,
            "symbols_extracted": 0,
            "trades_matched": 0,
            "replies_created": 0,
            "skipped_dedup": 0,
            "details": [],
        }

        # ── Twitter scanning ──
        if "twitter" in platforms:
            # Resolve user IDs
            user_ids = await self._resolve_user_ids(target_accounts)

            for username, user_id in user_ids.items():
                results["scanned_accounts"] += 1

                tweets = await self._fetch_recent_tweets(user_id, since_hours)
                if not tweets:
                    continue

                for tweet in tweets:
                    results["tweets_found"] += 1
                    tweet_id = tweet.get("id", "")
                    tweet_text = tweet.get("text", "")

                    symbols = extract_symbols(tweet_text)
                    if not symbols:
                        continue

                    results["symbols_extracted"] += len(symbols)

                    trade_matches = await self._match_trade_history(symbols, db)
                    if not trade_matches:
                        continue

                    best_symbol = max(trade_matches, key=lambda s: trade_matches[s].get("pnl_pct", 0))
                    best_trade = trade_matches[best_symbol]
                    results["trades_matched"] += 1

                    symbol = best_symbol
                    trade = best_trade

                    if await self._check_deduplication(tweet_id, username, symbol, db):
                        results["skipped_dedup"] += 1
                        continue

                    reply_text = await self._generate_reply(
                        tweet_text, username, trade, symbol
                    )
                    if not reply_text:
                        continue

                    detail = {
                        "platform": "twitter",
                        "username": username,
                        "tweet_id": tweet_id,
                        "symbol": symbol,
                        "trade_return": f"{trade.get('pnl_pct', 0):+.1f}%",
                        "reply_text": reply_text,
                        "reply_chars": len(reply_text),
                    }

                    if not dry_run:
                        post = SocialPost(
                            post_type="contextual_reply",
                            platform="twitter",
                            status="draft",
                            text_content=reply_text,
                            source_trade_json=json.dumps(trade),
                            reply_to_tweet_id=tweet_id,
                            reply_to_username=username,
                            source_tweet_text=tweet_text,
                            ai_generated=True,
                            ai_model=CLAUDE_MODEL,
                        )
                        db.add(post)
                        detail["post_saved"] = True

                    results["details"].append(detail)
                    results["replies_created"] += 1

        # ── Threads scanning (mentions + keyword search) ──
        if "threads" in platforms and settings.THREADS_ACCESS_TOKEN:
            threads_mentions = await self._fetch_threads_mentions(since_hours)
            for mention in threads_mentions:
                results["tweets_found"] += 1
                thread_id = mention.get("id", "")
                thread_text = mention.get("text", "")
                thread_username = mention.get("username", "unknown")

                symbols = extract_symbols(thread_text)
                if not symbols:
                    continue

                results["symbols_extracted"] += len(symbols)

                trade_matches = await self._match_trade_history(symbols, db)
                if not trade_matches:
                    continue

                best_symbol = max(trade_matches, key=lambda s: trade_matches[s].get("pnl_pct", 0))
                best_trade = trade_matches[best_symbol]
                results["trades_matched"] += 1

                # Dedup: check if we already replied to this thread
                if await self._check_deduplication(thread_id, thread_username, best_symbol, db):
                    results["skipped_dedup"] += 1
                    continue

                reply_text = await self._generate_reply(
                    thread_text, thread_username, best_trade, best_symbol,
                    platform="threads"
                )
                if not reply_text:
                    continue

                detail = {
                    "platform": "threads",
                    "username": thread_username,
                    "tweet_id": thread_id,
                    "symbol": best_symbol,
                    "trade_return": f"{best_trade.get('pnl_pct', 0):+.1f}%",
                    "reply_text": reply_text,
                    "reply_chars": len(reply_text),
                }

                if not dry_run:
                    post = SocialPost(
                        post_type="contextual_reply",
                        platform="threads",
                        status="draft",
                        text_content=reply_text,
                        source_trade_json=json.dumps(best_trade),
                        reply_to_thread_id=thread_id,
                        reply_to_username=thread_username,
                        source_tweet_text=thread_text,
                        ai_generated=True,
                        ai_model=CLAUDE_MODEL,
                    )
                    db.add(post)
                    detail["post_saved"] = True

                results["details"].append(detail)
                results["replies_created"] += 1

            # ── Threads keyword search ──
            search_symbols = await self._get_searchable_symbols(db)
            results["keyword_symbols_searched"] = len(search_symbols)

            for symbol in search_symbols:
                keyword_posts = await self._fetch_threads_keyword_posts(
                    f"${symbol}", since_hours
                )

                for post in keyword_posts:
                    results["tweets_found"] += 1
                    thread_id = post.get("id", "")
                    thread_text = post.get("text", "")
                    thread_username = post.get("username", "unknown")

                    # Skip our own posts
                    if thread_username.lower() == "rigacap":
                        continue

                    results["symbols_extracted"] += 1

                    # Get trade data for this symbol
                    trade_matches = await self._match_trade_history([symbol], db)
                    if not trade_matches or symbol not in trade_matches:
                        continue

                    trade = trade_matches[symbol]
                    results["trades_matched"] += 1

                    if await self._check_deduplication(
                        thread_id, thread_username, symbol, db
                    ):
                        results["skipped_dedup"] += 1
                        continue

                    reply_text = await self._generate_reply(
                        thread_text, thread_username, trade, symbol,
                        platform="threads"
                    )
                    if not reply_text:
                        continue

                    detail = {
                        "platform": "threads",
                        "source": "keyword_search",
                        "username": thread_username,
                        "tweet_id": thread_id,
                        "symbol": symbol,
                        "trade_return": f"{trade.get('pnl_pct', 0):+.1f}%",
                        "reply_text": reply_text,
                        "reply_chars": len(reply_text),
                    }

                    if not dry_run:
                        new_post = SocialPost(
                            post_type="contextual_reply",
                            platform="threads",
                            status="draft",
                            text_content=reply_text,
                            source_trade_json=json.dumps(trade),
                            reply_to_thread_id=thread_id,
                            reply_to_username=thread_username,
                            source_tweet_text=thread_text,
                            ai_generated=True,
                            ai_model=CLAUDE_MODEL,
                        )
                        db.add(new_post)
                        detail["post_saved"] = True

                    results["details"].append(detail)
                    results["replies_created"] += 1

        if not dry_run and results["replies_created"] > 0:
            await db.commit()

            # Send one-click approval emails for each reply draft
            results["emails_sent"] = await self._send_approval_emails(db, results["details"])

        return results

    async def _resolve_user_ids(self, usernames: List[str]) -> Dict[str, str]:
        """Resolve Twitter usernames to user IDs, with caching."""
        resolved = {}
        for username in usernames:
            if username in self._user_id_cache:
                resolved[username] = self._user_id_cache[username]
                continue

            user_id = await social_posting_service.lookup_twitter_user_id(username)
            if user_id:
                self._user_id_cache[username] = user_id
                resolved[username] = user_id
            else:
                logger.warning(f"Could not resolve @{username}")

        return resolved

    async def _fetch_recent_tweets(
        self, user_id: str, since_hours: int
    ) -> List[dict]:
        """Fetch recent tweets from a user via Twitter API v2."""
        since_time = datetime.utcnow() - timedelta(hours=since_hours)
        start_time = since_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        url = TWITTER_USER_TWEETS_URL.format(user_id=user_id)
        params = {
            "max_results": "10",
            "start_time": start_time,
            "tweet.fields": "created_at,text,author_id",
        }

        # Build query string for OAuth signature
        auth_header = social_posting_service._oauth1_signature("GET", url, params)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": auth_header},
                )

            if resp.status_code != 200:
                logger.warning(
                    f"Failed to fetch tweets for user {user_id}: {resp.status_code} {resp.text}"
                )
                return []

            data = resp.json()
            return data.get("data", [])

        except Exception as e:
            logger.error(f"Error fetching tweets for user {user_id}: {e}")
            return []

    async def _fetch_threads_mentions(
        self, since_hours: int
    ) -> List[dict]:
        """Fetch recent Threads mentions of our account."""
        if not settings.THREADS_ACCESS_TOKEN or not settings.THREADS_USER_ID:
            return []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{THREADS_API_BASE}/{settings.THREADS_USER_ID}/replies",
                    params={
                        "fields": "id,text,username,timestamp",
                        "access_token": settings.THREADS_ACCESS_TOKEN,
                    },
                )

            if resp.status_code != 200:
                logger.warning(
                    f"Failed to fetch Threads mentions: {resp.status_code} {resp.text}"
                )
                return []

            data = resp.json()
            mentions = data.get("data", [])

            # Filter to recent mentions
            since_time = datetime.utcnow() - timedelta(hours=since_hours)
            recent = []
            for m in mentions:
                ts = m.get("timestamp", "")
                if ts:
                    try:
                        post_time = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                        if post_time >= since_time:
                            recent.append(m)
                    except (ValueError, TypeError):
                        continue

            return recent

        except Exception as e:
            logger.error(f"Error fetching Threads mentions: {e}")
            return []

    async def _fetch_threads_keyword_posts(
        self, query: str, since_hours: int
    ) -> List[dict]:
        """Search Threads for public posts matching a keyword query.

        Rate limit: 500 queries per 7 days (~71/day).
        """
        if not settings.THREADS_ACCESS_TOKEN or not settings.THREADS_USER_ID:
            return []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{THREADS_API_BASE}/{settings.THREADS_USER_ID}/threads_search",
                    params={
                        "q": query,
                        "fields": "id,text,username,timestamp",
                        "limit": "10",
                        "access_token": settings.THREADS_ACCESS_TOKEN,
                    },
                )

            if resp.status_code != 200:
                logger.warning(
                    f"Threads keyword search failed for '{query}': "
                    f"{resp.status_code} {resp.text}"
                )
                return []

            data = resp.json()
            posts = data.get("data", [])

            # Filter to recent posts
            since_time = datetime.utcnow() - timedelta(hours=since_hours)
            recent = []
            for p in posts:
                ts = p.get("timestamp", "")
                if ts:
                    try:
                        post_time = datetime.fromisoformat(
                            ts.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                        if post_time >= since_time:
                            recent.append(p)
                    except (ValueError, TypeError):
                        continue

            logger.info(
                f"Threads keyword '{query}': {len(posts)} results, "
                f"{len(recent)} recent"
            )
            return recent

        except Exception as e:
            logger.error(f"Error in Threads keyword search for '{query}': {e}")
            return []

    async def _get_searchable_symbols(self, db) -> List[str]:
        """Get symbols worth searching for — active positions + recent winners.

        Returns up to 15 symbols to stay within Threads rate limits
        (500 queries / 7 days ≈ 17 per scan at 4 scans/day).
        """
        from sqlalchemy import select

        symbols = []

        # 1. Active model portfolio positions (highest priority — we're in the trade)
        try:
            from app.core.database import ModelPosition
            result = await db.execute(
                select(ModelPosition.symbol).where(
                    ModelPosition.status == "active"
                )
            )
            active = [row[0] for row in result.all()]
            symbols.extend(active)
        except Exception:
            pass

        # 2. Recent closed winners (last 30 days, pnl >= 8%)
        try:
            from app.core.database import ModelPosition
            cutoff = datetime.utcnow() - timedelta(days=30)
            result = await db.execute(
                select(ModelPosition.symbol)
                .where(
                    ModelPosition.status == "closed",
                    ModelPosition.exit_date >= cutoff,
                    ModelPosition.pnl_pct >= 8,
                )
                .order_by(ModelPosition.pnl_pct.desc())
                .limit(10)
            )
            winners = [row[0] for row in result.all()]
            symbols.extend(s for s in winners if s not in symbols)
        except Exception:
            pass

        return symbols[:15]

    async def _match_trade_history(
        self, symbols: List[str], db
    ) -> Dict[str, dict]:
        """
        Match extracted symbols against trade history.
        Primary: real model portfolio exits (last 90 days, pnl >= 5%).
        Fallback: walk-forward simulation trades for unmatched symbols.
        Returns dict of symbol -> trade data for symbols with positive returns.
        """
        from sqlalchemy import select

        matches = {}

        # Primary: model portfolio closed positions (real tracked trades)
        try:
            from app.core.database import ModelPosition
            cutoff = datetime.utcnow() - timedelta(days=90)
            result = await db.execute(
                select(ModelPosition).where(
                    ModelPosition.status == "closed",
                    ModelPosition.exit_date >= cutoff,
                    ModelPosition.pnl_pct >= 5,
                ).order_by(ModelPosition.exit_date.desc())
            )
            for pos in result.scalars().all():
                if pos.symbol in symbols and pos.symbol not in matches:
                    matches[pos.symbol] = {
                        "symbol": pos.symbol,
                        "entry_date": pos.entry_date.isoformat() if pos.entry_date else "",
                        "exit_date": pos.exit_date.isoformat() if pos.exit_date else "",
                        "entry_price": pos.entry_price,
                        "exit_price": pos.exit_price,
                        "pnl_pct": pos.pnl_pct,
                        "exit_reason": pos.exit_reason,
                        "source": "model_portfolio",
                    }
        except Exception:
            pass  # Model tables may not exist yet

        # Fallback: WF simulation trades for unmatched symbols
        unmatched = [s for s in symbols if s not in matches]
        if unmatched:
            result = await db.execute(
                select(WalkForwardSimulation)
                .where(WalkForwardSimulation.trades_json.isnot(None))
                .where(WalkForwardSimulation.status == "completed")
                .order_by(WalkForwardSimulation.simulation_date.desc())
                .limit(10)
            )
            sims = result.scalars().all()

            for sim in sims:
                try:
                    trades = json.loads(sim.trades_json) if isinstance(sim.trades_json, str) else []
                except (json.JSONDecodeError, TypeError):
                    continue

                for trade in trades:
                    sym = trade.get("symbol", "")
                    if sym not in unmatched:
                        continue
                    if sym in matches:
                        continue

                    pnl = trade.get("pnl_pct", 0)
                    if pnl >= 5:
                        matches[sym] = trade

        return matches

    async def _check_deduplication(
        self, post_id: str, username: str, symbol: str, db
    ) -> bool:
        """
        Return True if this reply should be skipped (duplicate).
        Skip if: same post_id already replied to, or same account+symbol within 7 days.
        """
        from sqlalchemy import select, and_, or_

        # Check same tweet_id or thread_id
        result = await db.execute(
            select(SocialPost.id)
            .where(
                or_(
                    SocialPost.reply_to_tweet_id == post_id,
                    SocialPost.reply_to_thread_id == post_id,
                )
            )
            .limit(1)
        )
        if result.scalars().first() is not None:
            return True

        # Check same account+symbol within 7 days
        cutoff = datetime.utcnow() - timedelta(days=7)
        result = await db.execute(
            select(SocialPost.id)
            .where(
                and_(
                    SocialPost.reply_to_username == username,
                    SocialPost.post_type == "contextual_reply",
                    SocialPost.created_at >= cutoff,
                    SocialPost.source_trade_json.contains(f'"{symbol}"'),
                )
            )
            .limit(1)
        )
        if result.scalars().first() is not None:
            return True

        return False

    async def _generate_reply(
        self, tweet_text: str, username: str, trade: dict, symbol: str,
        platform: str = "twitter",
    ) -> Optional[str]:
        """Generate a contextual reply using Claude API."""
        if not settings.ANTHROPIC_API_KEY:
            return None

        pnl_pct = trade.get("pnl_pct", 0)
        entry_date = str(trade.get("entry_date", ""))[:10]

        trade_context = (
            f"Our ensemble system caught ${symbol}: entered {entry_date}, "
            f"returned {pnl_pct:+.1f}%."
        )

        platform_label = "tweeted" if platform == "twitter" else "posted on Threads"
        char_limit = 260 if platform == "twitter" else 350

        user_prompt = (
            f"@{username} {platform_label}:\n\"{tweet_text[:300]}\"\n\n"
            f"Trade data: {trade_context}\n\n"
            f"Write a reply to this post. The reply should feel like a natural addition "
            f"to the conversation, not a cold sales pitch. Reference the specific stock "
            f"and our trade result briefly. Max {char_limit} chars."
        )

        system_prompt = (
            THREADS_REPLY_SYSTEM_PROMPT if platform == "threads"
            else REPLY_SYSTEM_PROMPT
        )

        try:
            text = await self._call_claude(user_prompt, system_prompt=system_prompt)
            if not text:
                return None

            # Strip markdown
            text = self._strip_markdown(text)

            # Enforce char limit
            if len(text) > char_limit:
                text = text[:char_limit - 3].rsplit(" ", 1)[0] + "..."

            return text

        except Exception as e:
            logger.error(f"Reply generation failed for @{username}/{symbol}: {e}")
            return None

    async def _find_we_called_it_url(self, symbol: str, db) -> Optional[str]:
        """Find an existing posted 'we_called_it' post for this symbol."""
        from sqlalchemy import select, and_

        result = await db.execute(
            select(SocialPost)
            .where(
                and_(
                    SocialPost.post_type == "we_called_it",
                    SocialPost.status == "posted",
                    SocialPost.source_trade_json.contains(f'"{symbol}"'),
                )
            )
            .order_by(SocialPost.posted_at.desc())
            .limit(1)
        )
        post = result.scalars().first()
        if post and post.posted_at:
            return f"https://rigacap.com/track-record"
        return None

    async def _call_claude(self, user_prompt: str, system_prompt: str = None) -> Optional[str]:
        """Make a Claude API call for reply generation."""
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 256,
            "system": system_prompt or REPLY_SYSTEM_PROMPT,
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

    async def _send_approval_emails(self, db, details: list) -> int:
        """Send one-click approval emails for each created reply draft."""
        from app.services.email_service import admin_email_service
        from app.services.post_scheduler_service import post_scheduler_service
        from app.core.database import SocialPost
        from sqlalchemy import select, desc

        # Fetch the most recent contextual_reply drafts
        result = await db.execute(
            select(SocialPost).where(
                SocialPost.post_type == "contextual_reply",
                SocialPost.status == "draft",
            ).order_by(desc(SocialPost.created_at)).limit(len(details))
        )
        posts = result.scalars().all()
        post_by_tweet = {p.reply_to_tweet_id: p for p in posts}

        sent = 0
        for detail in details:
            post = post_by_tweet.get(detail.get("tweet_id"))
            if not post:
                continue
            try:
                approve_token = post_scheduler_service.generate_approve_token(post.id)
                approve_url = f"{settings.FRONTEND_URL}/api/admin/social/posts/{post.id}/approve-email?token={approve_token}"

                success = await admin_email_service.send_reply_approval_email(
                    to_email="erik@rigacap.com",
                    post=post,
                    approve_url=approve_url,
                )
                if success:
                    sent += 1
            except Exception as e:
                logger.error(f"Failed to send approval email for post {post.id}: {e}")

        return sent

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown formatting from generated text."""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'(?<!\w)\*([^*]+?)\*(?!\w)', r'\1', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


# Singleton
reply_scanner_service = ReplyScannerService()
