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
CLAUDE_MODEL = "claude-sonnet-4-6"


def _build_reply_system_prompt(char_limit: int, platform_name: str) -> str:
    """Build a reply-system prompt with the canonical voice + voice-filter ban list.

    Keeping this dynamic so the banned-vocabulary stays in sync with the
    post-filter (single source of truth in voice_filters.py).
    """
    from app.services.voice_filters import banned_summary_for_prompt
    return f"""You write {platform_name} replies as Erik, founder of RigaCap — for the investor tired of fighting their own worst instincts.
Someone you follow {('tweeted' if platform_name == 'Twitter' else 'posted')} about a stock our system traded. Write a brief, natural reply that adds a genuine idea to the thread.

VOICE: Erik, the founder. Plain-spoken and direct — a smart guy who's made these mistakes himself, typing a thought to a friend on his phone. NOT a financial columnist. Short sentences. Everyday words. Lean first-person where it's true ("I've done this," "I've held a loser too long," "I've stopped skipping the boring names"). You've spent years watching investors — yourself included — lose money not to bad picks but to bad behavior: holding a loser on a "thesis," selling a winner early, capitulating at the bottom. That lived experience IS your voice.

PLAIN, NOT POLISHED — if a phrase sounds like an essay, or uses a word you wouldn't say out loud to a friend, rewrite it plainer. Short sentences, everyday words.

VARY THE SHAPE — this matters as much as the words. Do NOT write to a fixed template. Replies must NOT all read as "[behavioral confession] → [$TICKER flagged DATE, +X% since] → [terse maxim]". That skeleton is ONE option; using it every time reads mechanical and robotic. Rotate the structure from reply to reply:
- Opener: sometimes a plain observation, sometimes a first-person confession, sometimes a question back to the poster. Do NOT always open "The urge to ___ is real."
- The result: sometimes cite it as quiet evidence, sometimes weave it mid-sentence, and OFTEN drop the ticker/return entirely and make a purely behavioral point. Do NOT always use the exact "$X flagged [date], +Y% since" construction.
- Closer: do NOT always end on a maxim ("that's the point", "that was X, not Y", "that's kind of the point"). Sometimes end on a question, an admission, or just stop.
Same voice, DIFFERENT shapes — study the range:
- A) "I've stopped skipping the boring names. When a sector headline hits, the unsexy one usually holds up better than the ticker everyone's chasing. $KO caught my eye mid-July, up ~5% since. Not exciting — kind of the point."
- B) "Dilution headlines are built to shake out the people who'd have been fine just holding. We stayed in $INTC through that offering. The real question was never the price. It's whether anything actually changed, or just the mood."
- C) "Everyone sees the gap-up, so everyone pays for it. The quiet weeks before it are where the edge actually lived — and it never feels like a signal at the time. Almost never does."
- TOO WORDY (never write like this): "The boring incumbent is often the real trade when a sector headline breaks... how often the unsexy name holds better when the high-multiple peer disappoints."
Note: A leads with a confession + a soft flex; B weaves the position in and ends on a question; C carries NO ticker or number at all. Pick whatever fits the thread — never default to the same one.

OPEN WITH DISCIPLINE — the rule that matters most:
- The FIRST sentence is a behavioral or process insight, never a result. Lead with the lesson (position sizing, sitting still, exiting on the rule not the story, staying invested through a scary dip, the boring name being the real trade) — or a lived-experience truth in first person ("I've watched a -8% turn into -22% while calling it a thesis hold; the loss that finally hits your account is the same number regardless of the story you told").
- A positive result MAY appear, but ONLY as secondary, understated evidence AFTER the insight — never the hook. Reorder so discipline leads and the number supports, e.g. open with WHY a name was holdable, then "(+X% since, but the sizing is the point)".
- NEVER open with "Our system flagged $X — up Y%". That is a flex leading; it's banned as an opener.
- If the only honest thing you'd say is a return, SKIP — output the single word SKIP and nothing else.

WHAT CONVERTS: the reader should think "huh, that's a healthier way to think about this" — not "cool, they made money." You are the calm, honest voice lowering the temperature in a noisy thread. Curiosity, never a pitch. Have a real, slightly contrarian opinion worth clicking over to read — but land it as someone who's made the mistake themselves, never as someone grading or lecturing the reader. Confident and lived-in, not judgy or teachy.

- Say "our system flagged this" / "we caught this move", never "we predicted".
- NEVER give financial advice. NEVER use hashtags.
- NEVER start with "Great post!" "Nice call!" "Interesting" "Just" or "Here's the thing".
- {banned_summary_for_prompt()}
- One concise idea. Don't ramble. Have an opinion; don't hedge.
- Em-dashes welcome. Sound like you typed it on your phone — real, not polished.

FORMAT: Under {char_limit} chars. Plain text only. No markdown. No emojis at start.
End on a COMPLETE sentence that lands a real point. NEVER use an ellipsis ('...' or '…') and NEVER trail off unfinished.
Include rigacap.com/track-record only if it fits naturally (rarely)."""


# Cached prompts (built lazily on first use to avoid import-order issues)
REPLY_SYSTEM_PROMPT = _build_reply_system_prompt(260, "Twitter")
THREADS_REPLY_SYSTEM_PROMPT = _build_reply_system_prompt(350, "Threads")

# ── Tier voice forks ─────────────────────────────────────────────────────────
# We serve two buyers. A thread's emotional register tells us which one is reading,
# so we fork the ANGLE of the reply (never the base voice, never naming a product).
# One reply per thread — the classifier picks ONE tier; dedup keeps it to one draft.
PRESERVER_VOICE_OVERLAY = """
THIS THREAD'S ANGLE — PROTECT (the reader is anxious: a loss, a scary dip, the urge to sell / panic / capitulate / "just get out"):
- Speak to the investor fighting the urge to bail. The edge here is behavioral: not giving back what you've made, exiting on a rule instead of a story, sitting still when it's uncomfortable.
- Lean into lived experience — holding through fear, or cutting on the rule not the story ("the loss that finally hits your account is the same number regardless of the story you told along the way").
- The "win" isn't a big number, it's not blowing up. Calm, protective, been-there. Do NOT cheerlead a rally in this thread."""

MAXIMIZER_VOICE_OVERLAY = """
THIS THREAD'S ANGLE — GROW IT, DON'T FUMBLE IT (the reader is chasing momentum, afraid of missing a runner, or watching a name go vertical). Speak to the investor who wants the big move but keeps sabotaging it — buying the top, selling the winner early, or letting a gain round-trip to nothing.

ROTATE THE THESIS — this is the fix for sounding repetitive. There are SEVERAL distinct maximizer ideas; pick the ONE that best fits this thread and, above all, DON'T reuse the same idea you used in a recent maximizer reply. Do NOT make every reply about "the entry is easy / the exit matters more" — that is ONE angle among these, not the default:
- LET WINNERS RUN: most people clip a green position early to "lock it in" and miss the 40% that was still coming. The money's in the ones you didn't sell too soon.
- THE GIVEBACK MATH: a +45% that round-trips to +6% is the real loss — the discipline is keeping the gain, not calling the top.
- IN BEFORE THE CROWD: the quiet weeks before the vertical candle were the actual entry. Chasing the gap-up means paying for what everyone can already see.
- PATIENCE THROUGH THE SHAKEOUT: the 8-10% mid-hold dip is exactly what flushes people out of what turns out to be the year's biggest winner.
- POSITION, DON'T PREDICT: you don't need to nail the top — you need a plan that still works when you're wrong about it.
- THE EXIT IS THE EDGE: you can ride a strong trend AND have a hard rule that gets you out before the giveback. (Use SPARINGLY — it's been overused; prefer another angle unless it's a clear fit.)

TONE: confident and a little contrarian — a take worth clicking over to read, not a hedge. But say it as someone who's MADE the mistake ("I've sold a runner at +12% and watched it triple"), never as someone grading the reader's. Lived-in and honest, not judgy or teachy. The reader should feel seen, not lectured."""

# Do NOT name a product/plan/tier in the OUTPUT — these overlays only set the angle.
_TIER_OVERLAY = {"preserver": PRESERVER_VOICE_OVERLAY, "maximizer": MAXIMIZER_VOICE_OVERLAY}

# Applied to EVERY reply — the guard against fabricating or overstating a result.
FACTUAL_ACCURACY_RULES = """
FACTUAL ACCURACY — non-negotiable, a wrong claim here is worse than no reply:
- Use ONLY the exact return figure in Trade data. Never change, round up, or inflate it.
- NEVER invent, approximate, or shift a date. Do not say "mid-May", "back in spring", "in April" unless that EXACT date is in Trade data. If you are not stating the exact given date, state NO date at all.
- If Trade data is a WALK-FORWARD TEST RESULT: you MUST frame it as walk-forward testing (e.g. "in our walk-forward testing, the system caught ..." / "tested over that period, it would have ..."). NEVER imply we personally held it or bought it live, and NEVER give it a specific entry date.
- If Trade data is a REAL TRACKED TRADE: you may say our system caught/held it.
- If you cannot make an honest point within these limits, output SKIP."""

# Register keywords. A thread leans MAXIMIZER when it's about chasing a runner / FOMO /
# breakouts; PRESERVER when it's about fear / loss / drawdown / the urge to capitulate.
# Preserver is the default for neutral/ambiguous threads — it's the brand-core calm voice.
_MAXIMIZER_CUES = (
    "breakout", "break out", "all-time high", "all time high", "52-week high", "52 week high",
    "new high", "parabolic", "squeeze", "momentum", "ripping", "running", "rally", "rallying",
    "moon", "moonshot", "10x", "multibagger", "how high", "how much higher", "chasing", "chase",
    "fomo", "missed the", "did i miss", "too late to buy", "get in", "buy the breakout",
    "leaders", "hypergrowth", "going vertical", "loading up", "adding here", "up big", "up huge",
)
_PRESERVER_CUES = (
    "should i sell", "sell everything", "crash", "correction", "drawdown", "underwater",
    "bag hold", "bagholder", "holding the bag", "panic", "capitulate", "capitulation",
    "bear market", "cut losses", "cut my losses", "stop loss", "protect", "preserve",
    "defensive", "hedge", "sleep at night", "scared", " fear", "thesis hold", "average down",
    "averaging down", "buy the dip", "volatile", "volatility", "risk off", "recession",
    "get out", "should i hold", "down " , "keeps dropping", "falling knife", "bleeding",
)

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


# Percentage/return figures (e.g. "+45%", "30.5 %", "-12%"). Used by the number-collision
# guardrail so we never echo a return the source post already states.
_PCT_RE = re.compile(r'[-+]?\d{1,3}(?:\.\d+)?\s*%')


def _percent_figures(text: str) -> List[float]:
    """All percentage figures in a string as absolute floats (e.g. '+45.0%' -> 45.0)."""
    out = []
    for m in _PCT_RE.findall(text or ""):
        try:
            out.append(abs(float(m.replace('%', '').replace(' ', ''))))
        except ValueError:
            continue
    return out


class ReplyScannerService:
    """Scan followed accounts' tweets, match to trades, generate reply drafts."""

    def __init__(self):
        self.enabled = bool(settings.ANTHROPIC_API_KEY) and bool(settings.TWITTER_API_KEY)
        self._user_id_cache: Dict[str, str] = {}
        self._recent_replies: List[str] = []

    async def _load_recent_replies(self, db, days: int = 8, limit: int = 30) -> List[str]:
        """Reply drafts from roughly the last 5 reply-days (an ~8-day window spans weekday
        gaps) — fed to the generator so it varies opening line + discipline angle for
        versatility, not just avoiding today's repeats. Anti-repetition."""
        try:
            from sqlalchemy import select, desc
            cutoff = datetime.utcnow() - timedelta(days=days)
            rows = (await db.execute(
                select(SocialPost.text_content)
                .where(
                    SocialPost.post_type == "contextual_reply",
                    SocialPost.created_at >= cutoff,
                )
                .order_by(desc(SocialPost.created_at)).limit(limit)
            )).scalars().all()
            return [r for r in rows if r]
        except Exception:
            return []

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

        # Anti-repetition: load our recent replies so the generator varies its opening
        # line + discipline angle instead of sounding like a template every scan.
        self._recent_replies = await self._load_recent_replies(db)

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

                    tier = self.classify_tier(tweet_text, trade)
                    reply_text = await self._generate_reply(
                        tweet_text, username, trade, symbol, tier=tier
                    )
                    if not reply_text:
                        continue
                    # Feed this reply into the avoid-set so the NEXT one in the same scan
                    # takes a different shape/angle. (Repeating a hot ticker across threads is
                    # fine + human — the point is each reply is its own take, not a clone.)
                    self._recent_replies.insert(0, reply_text)

                    detail = {
                        "platform": "twitter",
                        "username": username,
                        "tweet_id": tweet_id,
                        "symbol": symbol,
                        "tier": tier,
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

                tier = self.classify_tier(thread_text, best_trade)
                reply_text = await self._generate_reply(
                    thread_text, thread_username, best_trade, best_symbol,
                    platform="threads", tier=tier
                )
                if not reply_text:
                    continue
                self._recent_replies.insert(0, reply_text)

                detail = {
                    "platform": "threads",
                    "username": thread_username,
                    "tweet_id": thread_id,
                    "symbol": best_symbol,
                    "tier": tier,
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
                    self._recent_replies.insert(0, reply_text)

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
        # Expand referenced tweets + request note_tweet so RETWEETS (whose `text` the API truncates
        # at "…") and long-form tweets resolve to their FULL text. Without this we reply to — and
        # run the number-collision guardrail against — a truncated thread (a real hidden number
        # in the tail is invisible). See the $LRCX +45% retweet case.
        params = {
            "max_results": "10",
            "start_time": start_time,
            "tweet.fields": "created_at,text,author_id,note_tweet,referenced_tweets",
            "expansions": "referenced_tweets.id",
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
            tweets = data.get("data", [])
            included = {t["id"]: t for t in data.get("includes", {}).get("tweets", [])}
            return [{**tw, "text": self._full_tweet_text(tw, included)} for tw in tweets]

        except Exception as e:
            logger.error(f"Error fetching tweets for user {user_id}: {e}")
            return []

    @staticmethod
    def _full_tweet_text(tweet: dict, included: Dict[str, dict]) -> str:
        """Resolve a tweet's FULL text: prefer its long-form note; for a retweet use the original's
        full text (the RT `text` field is truncated with "…"); for a quote keep the commentary and
        append the quoted content for context."""
        note = (tweet.get("note_tweet") or {}).get("text")
        text = note or tweet.get("text", "") or ""
        for ref in (tweet.get("referenced_tweets") or []):
            if ref.get("type") in ("retweeted", "quoted"):
                orig = included.get(ref.get("id"))
                if not orig:
                    continue
                orig_text = (orig.get("note_tweet") or {}).get("text") or orig.get("text", "")
                if not orig_text:
                    continue
                if ref["type"] == "retweeted":
                    return orig_text          # the original IS the content
                return f"{text}\n\n{orig_text}".strip()   # quote: commentary + quoted body
        return text

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

        # Real tracked matches are framed as trades we actually caught/held.
        for m in matches.values():
            m["is_walkforward"] = False

        # Fallback: WALK-FORWARD simulation trades for unmatched symbols. These are NOT
        # positions we personally held — they get framed as walk-forward testing, and we
        # HARD-BLOCK any name the live/STR book contradicts (a real closed loss, or a
        # currently-underwater open position) so we never claim a win on a name we actually
        # lost money on (e.g. SNDK: sim +34% vs live -23%).
        unmatched = [s for s in symbols if s not in matches]
        wf_candidates = {}
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
                    if sym not in unmatched or sym in wf_candidates:
                        continue
                    # Only genuinely CLOSED-on-a-rule trades. A `rebalance_exit` on the
                    # sim's latest rebalance is an OPEN position marked-to-market at the
                    # window edge (not a completed win) — and those batches include losers
                    # sitting next to the flashy names. Cite only decisive rule exits.
                    reason = (trade.get("exit_reason") or "").lower()
                    closed_on_rule = reason in (
                        "trailing_stop", "market_regime", "profit_target",
                        "stop_loss", "stop", "target",
                    )
                    if trade.get("pnl_pct", 0) >= 5 and closed_on_rule:
                        trade["is_walkforward"] = True
                        trade["source"] = "walkforward"
                        wf_candidates[sym] = trade

        if wf_candidates:
            contradicted = await self._contradicted_symbols(set(wf_candidates), db)
            for sym, trade in wf_candidates.items():
                if sym in contradicted:
                    logger.info(
                        f"[reply-scanner] WF cite for {sym} BLOCKED — live/STR book "
                        f"contradicts (real loss or currently underwater)"
                    )
                    continue
                matches[sym] = trade

        return matches

    async def _contradicted_symbols(self, symbols: set, db) -> set:
        """Symbols whose walk-forward 'win' the LIVE/STR book would contradict.

        Blocks a WF cite when our real book shows that same name as either a CLOSED
        LOSS (pnl <= 0) or an OPEN position that's currently underwater (latest close
        below entry). Never claim a win on a name we actually lost on / are down on.
        Symbols with no real position at all are NOT contradicted (nothing to conflict).
        """
        from sqlalchemy import select
        from collections import defaultdict
        from app.core.database import ModelPosition

        bad: set = set()
        if not symbols:
            return bad

        rows = (await db.execute(
            select(ModelPosition).where(
                ModelPosition.symbol.in_(list(symbols)),
                ModelPosition.portfolio_type.in_(["live", "signal_track_record"]),
            )
        )).scalars().all()

        by_sym = defaultdict(list)
        for r in rows:
            by_sym[r.symbol].append(r)

        try:
            from app.services.model_portfolio_service import _fetch_latest_close_from_s3
        except Exception:
            _fetch_latest_close_from_s3 = None

        price_cache: Dict[str, Optional[float]] = {}

        def _close(sym: str) -> Optional[float]:
            if _fetch_latest_close_from_s3 is None:
                return None
            if sym not in price_cache:
                try:
                    c = _fetch_latest_close_from_s3(sym)
                    price_cache[sym] = float(c) if c is not None else None
                except Exception:
                    price_cache[sym] = None
            return price_cache[sym]

        for sym, poss in by_sym.items():
            for p in poss:
                if p.status == "closed":
                    if (p.pnl_pct or 0) <= 0:
                        bad.add(sym)
                        break
                else:  # open — block only if we can confirm it's underwater right now
                    cur = _close(sym)
                    if cur is not None and p.entry_price and cur < float(p.entry_price):
                        bad.add(sym)
                        break
        return bad

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

    @staticmethod
    def classify_tier(tweet_text: str, trade: Optional[dict] = None) -> str:
        """Pick which buyer is reading this thread by its emotional register.

        MAXIMIZER when it's about chasing a runner / FOMO / breakouts; PRESERVER when
        it's about fear / loss / drawdown / the urge to capitulate. Neutral/ambiguous →
        PRESERVER (the brand-core calm voice). Register drives it; a big winner only
        breaks a tie toward maximizer.
        """
        t = (tweet_text or "").lower()
        max_score = sum(1 for cue in _MAXIMIZER_CUES if cue in t)
        pre_score = sum(1 for cue in _PRESERVER_CUES if cue in t)
        if max_score > pre_score:
            return "maximizer"
        if pre_score > max_score:
            return "preserver"
        # Tie: lean maximizer only if the matched trade is a strong runner, else preserve.
        try:
            if float((trade or {}).get("pnl_pct", 0) or 0) >= 25.0:
                return "maximizer"
        except (TypeError, ValueError):
            pass
        return "preserver"

    async def _generate_reply(
        self, tweet_text: str, username: str, trade: dict, symbol: str,
        platform: str = "twitter", tier: str = "preserver",
    ) -> Optional[str]:
        """Generate a contextual reply using Claude API, forked to the thread's tier voice."""
        if not settings.ANTHROPIC_API_KEY:
            return None

        pnl_pct = trade.get("pnl_pct", 0)
        entry_date = str(trade.get("entry_date", ""))[:10]
        is_wf = bool(trade.get("is_walkforward"))

        # Optics guardrail: if the source post ALREADY states a return within a few points of ours,
        # do NOT echo a matching number — it reads as parroting their stat ("you just copied us"),
        # which is exactly what undermines the independent-evidence point. Force a purely behavioral
        # angle with no number (or SKIP). (Origin: the $LRCX +45% coincidence, Sep 2026 — our WF
        # 44.96% -> "+45.0%" happened to match a "+45%" in the Tickeron thread.)
        _our_ret = abs(pnl_pct or 0)
        number_collision = any(abs(r - _our_ret) <= 5.0 for r in _percent_figures(tweet_text))
        # Conservative fallback: if the post text STILL looks truncated (trailing "…" — the API's
        # cut-off marker we couldn't expand), a return could be hiding in the tail. Suppress our
        # number rather than risk parroting one we can't see.
        if not number_collision and tweet_text.rstrip().endswith(("…", "...")):
            number_collision = True
            logger.info(f"[reply-scanner] @{username}/{symbol}: source text looks truncated — suppressing number defensively")

        if is_wf:
            # Walk-forward test trade (NOT a position we personally held). No precise entry
            # date — WF entries land on rebalance boundaries, so a specific day would be a
            # misleading artifact. Frame as walk-forward testing, return only.
            trade_context = (
                f"WALK-FORWARD TEST RESULT (this is NOT a position we personally held — it is "
                f"what the system would have done in walk-forward testing): the system caught "
                f"${symbol} for {pnl_pct:+.1f}%. Do NOT state a specific entry/buy date for this "
                f"one. You MUST frame it as walk-forward testing, never as a live trade we held."
            )
        else:
            trade_context = (
                f"REAL TRACKED TRADE (our system actually caught this in the tracked book): "
                f"${symbol}, entered {entry_date}, {pnl_pct:+.1f}%."
            )

        platform_label = "tweeted" if platform == "twitter" else "posted on Threads"
        char_limit = 260 if platform == "twitter" else 350

        user_prompt = (
            f"@{username} {platform_label}:\n\"{tweet_text[:600]}\"\n\n"
            f"Trade data: {trade_context}\n\n"
            f"Write a reply to this post. The reply should feel like a natural addition "
            f"to the conversation, not a cold sales pitch. Reference the specific stock "
            f"and our trade result briefly. Max {char_limit} chars."
        )

        if number_collision:
            user_prompt += (
                "\n\nCRITICAL: The post above ALREADY states a return figure within a few points of ours. "
                "Do NOT put ANY percentage or return number in your reply — a matching figure reads as "
                "parroting their stat. Make a PURELY BEHAVIORAL point (discipline, the exit rule, the "
                "giveback, staying in before the crowd) with NO number at all. If you cannot make an honest "
                "point without the number, reply with the single word SKIP."
            )
            logger.info(
                f"[reply-scanner] @{username}/{symbol}: number-collision guardrail ON "
                f"(our {_our_ret:.1f}% ~ a figure in the post) — forcing no-number/behavioral angle"
            )

        system_prompt = (
            THREADS_REPLY_SYSTEM_PROMPT if platform == "threads"
            else REPLY_SYSTEM_PROMPT
        )
        # Fork the ANGLE to the thread's tier (never name a product in the output).
        system_prompt = system_prompt + "\n" + _TIER_OVERLAY.get(tier, PRESERVER_VOICE_OVERLAY)
        system_prompt = system_prompt + "\n" + FACTUAL_ACCURACY_RULES

        from app.services.voice_filters import contains_banned

        # Anti-repetition: feed our recent replies (last ~5 reply-days) so the model varies
        # its opening line + discipline angle for versatility, not a template every scan.
        avoid_block = ""
        if self._recent_replies:
            _joined = "\n".join(f"- {r.strip()}" for r in self._recent_replies[:25])
            avoid_block = (
                "\n\nYOUR RECENT REPLIES (last few days, and any already written THIS scan) — match NONE of "
                "these on (a) opening line, (b) SHAPE/skeleton (e.g. don't repeat 'confession → $TICKER "
                "flagged DATE +X% since → maxim' if they already used it), (c) closer type (maxim vs question "
                "vs fragment), or — MOST IMPORTANT — (d) THE UNDERLYING IDEA/THESIS. If a recent reply argued "
                "'the entry is easy, the exit rule matters more' (or any single angle), THIS one MUST make a "
                "DIFFERENT point — pick another idea from your angle menu. It is fine to reply about the same "
                "ticker more than once, but each reply must be its own distinct take, never the same argument "
                "reworded. If the recent ones cited a ticker+return, THIS one should probably carry no number "
                "at all. Give the reader a real person with range, not a template:\n" + _joined
            )

        # Regenerate up to 3x on banned vocab OR over-length. NEVER ship an ellipsis-
        # truncated reply — regenerate shorter, or skip.
        retry_note = None
        for attempt in range(3):
            directives = avoid_block
            if retry_note:
                directives += "\n\n" + retry_note
            try:
                full_system = system_prompt + directives
                text = await self._call_claude(user_prompt, system_prompt=full_system)
                if not text:
                    return None

                text = self._strip_markdown(text)

                # Model opted to skip (only a return-flex to offer) — no draft.
                if text.strip().rstrip(".").upper() == "SKIP" or len(text.strip()) < 15:
                    logger.info(f"[reply-scanner] @{username}/{symbol}: model SKIPPED (no discipline-led angle)")
                    return None

                # Deterministic backstop for the number-collision guardrail: if the post already
                # states a matching return, the reply must carry NO number. Regenerate if one slipped
                # through; after 3 tries the loop returns None (skip) rather than echo their stat.
                if number_collision and _percent_figures(text):
                    logger.warning(f"[reply-scanner] @{username}/{symbol} attempt {attempt + 1}: cited a number despite collision guardrail, regenerating")
                    retry_note = (
                        "YOUR PRIOR DRAFT STILL CONTAINED A PERCENTAGE/RETURN NUMBER. The source post already "
                        "states a matching figure — you MUST NOT cite ANY number. Rewrite as a purely behavioral "
                        "point with no percentage at all, or reply with the single word SKIP."
                    )
                    continue

                violations = contains_banned(text)
                if violations:
                    terms = ", ".join(t for t, _ in violations)
                    logger.warning(f"[reply-scanner] @{username}/{symbol} attempt {attempt + 1}: banned terms: {terms}")
                    retry_note = (
                        "YOUR PRIOR DRAFT CONTAINED BANNED WORDS. Regenerate without ANY trader jargon, "
                        "SaaS-speak, or proprietary indicator names ('tape','printing','ripping','AI-powered', "
                        "'unlock','autonomous','guaranteed','DWAP'). Do not paraphrase with 'so-called' or quotes."
                    )
                    continue

                # NEVER trail off. Reject ANY ellipsis (regardless of length) — the model
                # sometimes ends on "..." as a rhetorical trail-off, which reads unfinished.
                if "..." in text or "…" in text:
                    logger.warning(f"[reply-scanner] @{username}/{symbol} attempt {attempt + 1}: ellipsis / trailed off, regenerating")
                    retry_note = (
                        "YOUR PRIOR DRAFT USED AN ELLIPSIS or trailed off unfinished. NEVER use '...' or '…' "
                        "anywhere. Every sentence must be COMPLETE and land on a real point — no trailing off, "
                        "no implied 'you know what I mean' ending. Finish the thought."
                    )
                    continue

                # NEVER post an over-length (would-be-truncated) reply — regenerate shorter.
                if len(text) > char_limit:
                    logger.warning(f"[reply-scanner] @{username}/{symbol} attempt {attempt + 1}: {len(text)}>{char_limit} chars, regenerating shorter")
                    retry_note = (
                        f"Your draft was {len(text)} characters — HARD MAX {char_limit}. Rewrite it SHORTER, "
                        f"end on a COMPLETE sentence, and NEVER use an ellipsis or '...'. Cut a whole idea if needed."
                    )
                    continue

                return text

            except Exception as e:
                logger.error(f"Reply generation failed for @{username}/{symbol}: {e}")
                return None

        # 3 attempts still failed voice/length — skip rather than post a bad or truncated reply.
        logger.warning(f"[reply-scanner] @{username}/{symbol}: rejected all 3 attempts (voice/length)")
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
            # Prompt-cache the static reply system prompt across a bulk scan run.
            "system": [{"type": "text", "text": system_prompt or REPLY_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
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

        # Batch into ONE digest email (a card + one-click approve per draft) so a
        # 4x/day scan cadence doesn't spam N separate emails per run.
        items = []
        for detail in details:
            post = post_by_tweet.get(detail.get("tweet_id"))
            if not post:
                continue
            approve_token = post_scheduler_service.generate_approve_token(post.id)
            compose_url = f"https://api.rigacap.com/api/admin/social/posts/{post.id}/compose-email?token={approve_token}"
            items.append({"post": post, "approve_url": compose_url, "tier": detail.get("tier")})

        if not items:
            return 0
        try:
            ok = await admin_email_service.send_reply_approval_batch(
                to_email="erik@rigacap.com",
                items=items,
            )
            return len(items) if ok else 0
        except Exception as e:
            logger.error(f"Failed to send batch approval email: {e}")
            return 0

    async def resend_pending_approvals(self, db, limit: int = 25) -> int:
        """Re-send the batch approval email for all currently-pending reply drafts, with
        freshly-minted approve links on the correct api.rigacap.com host. Used to recover
        drafts whose original email carried a broken host (or an expired token)."""
        from app.services.email_service import admin_email_service
        from app.services.post_scheduler_service import post_scheduler_service
        from app.core.database import SocialPost
        from sqlalchemy import select, desc

        result = await db.execute(
            select(SocialPost).where(
                SocialPost.post_type == "contextual_reply",
                SocialPost.status == "draft",
            ).order_by(desc(SocialPost.created_at)).limit(limit)
        )
        posts = result.scalars().all()

        items = []
        for post in posts:
            approve_token = post_scheduler_service.generate_approve_token(post.id)
            compose_url = f"https://api.rigacap.com/api/admin/social/posts/{post.id}/compose-email?token={approve_token}"
            try:
                _trade = json.loads(post.source_trade_json) if post.source_trade_json else None
            except (ValueError, TypeError):
                _trade = None
            tier = self.classify_tier(post.source_tweet_text or "", _trade)
            items.append({"post": post, "approve_url": compose_url, "tier": tier})

        if not items:
            return 0
        try:
            ok = await admin_email_service.send_reply_approval_batch(
                to_email="erik@rigacap.com",
                items=items,
            )
            return len(items) if ok else 0
        except Exception as e:
            logger.error(f"Failed to resend batch approval email: {e}")
            return 0

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
