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
- LEAD WITH DISCIPLINE, NOT RETURNS. RigaCap sells a risk-managed process, not hot stock picks. The strongest posts show the discipline working: a volatile name sized smaller so it couldn't sink the book, the system stepping back before a drop, a stop that capped a loss, staying invested through a scary dip that recovered, diversification cushioning a bad week. Big winners are fine occasionally — but they are NOT the main story. The repeatable process is.
- Never frame a single trade as proof the strategy "works." One trade is an anecdote; the process across many trades is the point. The brand is half-the-drawdown discipline, not lottery tickets.

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
                f"Write a post about a completed trade — but LEAD WITH THE DISCIPLINE, not the gain.\n"
                f"${symbol}: entered at ${entry_price:.2f} on {entry_date}, "
                f"exited at ${exit_price:.2f} on {exit_date} for {pnl_pct:+.1f}%.\n"
                f"Exit reason: {exit_reason}.\n"
                f"FRAME: the point isn't the {pnl_pct:+.1f}% — it's that the rules did exactly what they "
                f"were designed to do (let a winner run, or exit on the predetermined signal). The "
                f"repeatable process is the story; this number is just one instance of it."
            ),
            "discipline_win": (
                f"Write a post about the RISK DISCIPLINE working — not a big winner, the process itself.\n"
                f"${symbol} context: {news_context or 'recent system behavior'}.\n"
                f"Pick whichever angle the data supports: a volatile name sized smaller so it couldn't "
                f"sink the book; the system stepping back from new entries when losses clustered; staying "
                f"invested through a scary dip that recovered; diversification cushioning a rough week. "
                f"The lesson: boring, repeated discipline is what produces a drawdown you can actually live with."
            ),
            "missed_opportunity": (
                f"Write a restrained post about a signal subscribers acted on — NOT FOMO-baiting.\n"
                f"${symbol}: signal fired {entry_date} at ${entry_price:.2f}, "
                f"exited {exit_date} at ${exit_price:.2f} for {pnl_pct:+.1f}%.\n"
                f"FRAME: the value is a disciplined system surfacing this on schedule — not 'you should "
                f"have bought.' Emphasize process over the missed gain."
            ),
            "we_called_it": (
                f"Write a 'we called it' post connecting our trade result to news.\n"
                f"${symbol}: {pnl_pct:+.1f}% return. "
                f"Our system flagged this before the news broke.\n"
                f"News context: {news_context or 'No specific news provided.'}"
            ),
            "loss_review": (
                f"Write a post about a stopped-out trade where the system was wrong "
                f"and the trailing stop did its job.\n"
                f"${symbol}: entered at ${entry_price:.2f} on {entry_date}, "
                f"exited at ${exit_price:.2f} on {exit_date} for {pnl_pct:+.1f}%.\n"
                f"Exit reason: {exit_reason}.\n\n"
                "FRAME: The trailing stop is a feature of the system, not a failure. The system "
                "identifies opportunities and caps the cost when one doesn't work out. The job "
                "of the stop is exactly this — exit before a small loss becomes a large one.\n\n"
                "VOICE: Editorial, calm, restrained. Like writing the loss column in an annual "
                "report — honest, specific, no spin.\n\n"
                "DO:\n"
                "- Name the loss amount honestly (use the actual percentage).\n"
                "- Frame discipline as the product. The exit at the predetermined level IS the win.\n"
                "- Be specific about the mechanic: 'trailing stop fired at X% from peak.'\n"
                "- Treat the loss as data, not drama.\n\n"
                "DO NOT:\n"
                "- Apologize, spin, or oversell.\n"
                "- Say 'we still believe in this stock' / 'we'll get them next time' / "
                "'this is just temporary.'\n"
                "- Add false optimism. The trade didn't work. That's the whole post.\n"
                "- Use 'painful', 'tough', 'rough' — soft-pedaling words. State the loss "
                "and what the system did about it."
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

            # Hashtags are appended at POST time (text_content + "\n\n" + hashtags),
            # so the BODY must leave room for them under the platform char_limit —
            # otherwise body(≤limit) + hashtags exceeds it. (Jun 17 2026: an AI
            # "We Called It" body fit 500 but body+hashtags 400'd Threads' 500 cap.)
            hashtag_map = {
                "trade_result": f"#StockTrading #AlgoTrading #WalkForward #RigaCap ${symbol}",
                "missed_opportunity": f"#StockTrading #MissedTrade #AlgoTrading #RigaCap ${symbol}",
                "we_called_it": f"#WeCalledIt #AlgoTrading #TradingSignals #RigaCap ${symbol}",
                "loss_review": f"#TrailingStop #RiskManagement #SystematicTrading #RigaCap ${symbol}",
            }
            hashtags = hashtag_map.get(post_type, f"#RigaCap ${symbol}")
            effective_limit = max(80, char_limit - len(hashtags) - 2)  # 2 = "\n\n"

            # Too long → REGENERATE a coherent shorter post (don't just hard-truncate,
            # which clips the CTA). Re-prompt Claude up to 2x; truncate only as a last
            # resort so a stubborn overrun can never 400 the platform.
            attempts = 0
            while text and len(text) > effective_limit and attempts < 2:
                attempts += 1
                shorter_prompt = (
                    user_prompt
                    + f"\n\nYour previous draft was {len(text)} characters, but the body must "
                    f"fit in {effective_limit} characters (hashtags are appended separately). "
                    f"Rewrite it tighter — same message, keep the rigacap.com CTA, "
                    f"hard max {effective_limit} characters."
                )
                retry = await self._call_claude(shorter_prompt)
                if not retry:
                    break
                retry = self._strip_markdown(retry)
                retry = re.sub(r'^(Twitter|Instagram|Twitter/X|Threads|IG):\s*', '', retry, flags=re.IGNORECASE).strip()
                text = retry
            if len(text) > effective_limit:
                text = text[:effective_limit - 1].rsplit(" ", 1)[0] + "…"
                logger.warning("AI %s/%s post still >%d after %d regen attempt(s) — truncated", platform, post_type, effective_limit, attempts)

            post = SocialPost(
                post_type=post_type,
                platform=platform,
                status="draft",
                text_content=text,
                hashtags=hashtags,
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

    # Standalone "wow, I hadn't considered that" research nuggets — pure
    # curiosity hooks from the canon, NOT trade results. These are the weekly
    # original-content payload: an idea so interesting it stands on its own and
    # makes a visiting stranger want to follow. (Jun 24 2026)
    INSIGHT_SEEDS = [
        "The behavioral gap: across a full cycle, the average fund investor earns meaningfully LESS than the funds they own — not from picking wrong, but from not sitting still through the dips. The leak is behavior, not selection.",
        "An investor who panic-sells at a 25% drawdown and one who holds can end a long run with wildly different outcomes from the SAME strategy. The path you can actually stay on matters more than the path with the highest peak.",
        "Long-horizon Sharpe ratios live in a different universe from the ones people quote. Over 21 backtested years our strategy scored 0.73; the S&P scored 0.54 on the same window; Buffett's lifetime figure — the best ever measured over 30+ years — is 0.79. Sharpes above 1 almost always come from short, flattering windows.",
        "In 2008 the index fell about 38%. A strategy built around drawdown control can end a year like that roughly flat — not by predicting the crash, but by having a rule that steps aside when the market turns hostile. The discipline is the edge, not the forecast.",
        "Worst-case matters more than best-case, because worst-case is when people sell. A 19% worst drawdown across two decades vs. raw momentum's 57% isn't a smaller number for its own sake — it's the difference between a path you hold and one you abandon at the bottom.",
        "We rebuilt our research on cleaner, survivorship-free data and our own numbers came in WORSE than before — so we published the worse numbers. A backtest you can defend beats a flattering one you can't. Most services do the opposite.",
        "The biggest risk in a portfolio usually isn't in the portfolio — it's the person holding it. Most investors don't fail by picking the wrong thing; they fail by abandoning the right thing at the worst moment.",
    ]

    # Durable backtest LESSONS (not full posts — the raw truths the dynamic
    # generator pairs with a live market reading). NO coefficients/recipe.
    CANON_LESSONS = [
        "Across 21 backtested years the worst drawdown was about 19%; raw momentum's was 57%. Worst-case matters more than best-case — worst-case is when people actually sell.",
        "In 2008 the index fell ~38%; a drawdown-controlled approach can finish a year like that roughly flat (backtested) — not by predicting the crash, but by stepping aside when the market turns hostile.",
        "Over 21 backtested years the strategy's Sharpe was 0.73; the S&P scored 0.54 on the same window, and Buffett's lifetime figure — the best ever over 30+ years — is 0.79. Sharpes above 1 almost always come from short, flattering windows.",
        "The system goes to cash when the market falls below its long-term trend. Quiet, boring weeks are a feature — much of the edge is in what it does NOT do.",
        "The behavioral gap: across a full cycle the average investor earns less than the very funds they own — not from picking wrong, but from not sitting still through the dips.",
        "An investor who panic-sells at a 25% drawdown and one who holds can end a long run with wildly different outcomes from the SAME strategy. The path you can stay on beats the path with the highest peak.",
        "We rebuilt our research on cleaner, survivorship-free data, our own numbers came in worse, and we published the worse ones. A backtest you can defend beats a flattering one you can't.",
        "Built to be boring: wide trailing stops, ~20 positions, sized by volatility. The goal isn't the highest return — it's a path a real human can actually hold through.",
    ]

    async def generate_dynamic_insight(
        self, market_state: dict, platform: str = "twitter",
        lesson: str = "", lean: str = "state",
    ) -> Optional[SocialPost]:
        """Generate ONE rando grounded in TODAY's real market reading, paired with a
        durable backtest lesson — so it reads as 'here's what we're seeing this week,'
        not a reworded landing-page line. Uses ONLY facts passed in market_state (no
        fabrication); NEVER names a held/signaled ticker (those are subscriber-only)."""
        if not self.enabled:
            return None
        import re as _re
        ms = market_state or {}
        char_limit = 270 if platform == "twitter" else 600

        facts = []
        if ms.get("regime"):
            facts.append(f"Market regime today: {ms['regime']}" + (f" (outlook: {ms['outlook']})" if ms.get("outlook") else "") + ".")
        if ms.get("spy_change_pct") is not None:
            facts.append(f"S&P 500 today: {ms['spy_change_pct']:+.1f}%.")
        if ms.get("vix") is not None:
            facts.append(f"VIX sits at {ms['vix']:.1f}.")
        if ms.get("cross_asset"):
            facts.append("Cross-asset moves today: " + ", ".join(ms["cross_asset"]) + ".")
        if ms.get("signal_count") is not None:
            fresh = ms.get("fresh_count")
            facts.append(f"Our system surfaced {ms['signal_count']} buy signals today" + (f" ({fresh} brand-new since yesterday)" if fresh is not None else "") + ".")
        if ms.get("top_sectors"):
            facts.append(f"Those signals cluster in: {', '.join(ms['top_sectors'])}.")
        if ms.get("positions") is not None:
            posture = f"The live model book holds {ms['positions']} positions"
            if ms.get("cash_pct") is not None:
                posture += f", about {ms['cash_pct']}% in cash"
            facts.append(posture + ".")
        facts_block = "\n".join(f"- {f}" for f in facts) if facts else "- (limited data today)"

        lean_instr = (
            "State ONLY what is literally true in the data above, then the lesson it evokes. Make NO prediction."
            if lean != "soft_read" else
            "Lead with what's literally true today, then you MAY add ONE hedged note about what readings like this have HISTORICALLY tended to precede — never a forecast, never a number you weren't given."
        )

        prompt = (
            f"Write ONE {platform} post for Erik, founder of RigaCap. Connect something REAL "
            f"happening in the market RIGHT NOW to a durable lesson from our 21-year backtest — so "
            f"a smart stranger thinks 'huh, I hadn't considered that' and wants to know who wrote it.\n\n"
            f"TODAY'S REAL DATA (use ONLY the numbers and themes that appear here — invent NOTHING):\n{facts_block}\n\n"
            f"THE BACKTEST LESSON to pair it with (rephrase in Erik's voice, don't quote verbatim; "
            f"keep the word 'backtest'/'backtested' near any backtested number):\n{lesson}\n\n"
            f"HOW TO FRAME IT: {lean_instr}\n\n"
            f"HARD RULES:\n"
            f"- NEVER name a specific stock ticker or company — our signals are subscriber-only. "
            f"Sectors and themes ONLY (e.g. 'financials', 'defensives').\n"
            f"- Never reveal strategy parameters, weights, thresholds, or coefficients.\n"
            f"- Standalone: interesting even with zero context. Lead with the concrete current "
            f"observation, then the lesson. Calm, honest, first-person, a touch wry. No pitch, no "
            f"advice, no hype, no emojis.\n"
            f"- Hard max {char_limit - 30} characters. End with rigacap.com/track-record ONLY if it fits naturally."
        )
        try:
            text = await self._call_claude(prompt)
            if not text:
                return None
            text = self._strip_markdown(text)
            text = _re.sub(r'^(Twitter|Instagram|Twitter/X|Threads|IG):\s*', '', text, flags=_re.IGNORECASE).strip()
            hashtags = "#Investing #RiskManagement #MarketsToday #RigaCap"
            eff_limit = max(120, char_limit - len(hashtags) - 2)
            if len(text) > eff_limit:
                text = text[:eff_limit - 1].rsplit(" ", 1)[0] + "…"
            return SocialPost(
                post_type="research_insight", platform=platform, status="draft",
                text_content=text, hashtags=hashtags, ai_generated=True, ai_model=CLAUDE_MODEL,
            )
        except Exception as e:
            logger.error(f"Dynamic insight generation failed: {e}")
            return None

    async def generate_research_insight(self, platform: str = "twitter", seed_idx: Optional[int] = None) -> Optional[SocialPost]:
        """Generate ONE standalone research-insight post — a curiosity hook from
        the canon, not a trade result. Additive, never refuting: the reader should
        think 'wow, I hadn't considered that,' then click through."""
        if not self.enabled:
            return None
        import re as _re
        seeds = self.INSIGHT_SEEDS
        idx = (seed_idx if seed_idx is not None else 0) % len(seeds)
        seed = seeds[idx]
        char_limit = 270 if platform == "twitter" else 600
        prompt = (
            f"Write ONE {platform} post for Erik, founder of RigaCap. It must be a STANDALONE "
            f"insight a smart stranger finds genuinely surprising — they should think 'huh, I "
            f"hadn't considered that' and want to know who wrote it. NOT a pitch, NOT a trade "
            f"result, NOT advice. Calm, honest, first-person, a little wry. Lead with the idea. "
            f"No one is being corrected or refuted — there's no other person here.\n\n"
            f"The insight to convey (rephrase in Erik's voice, don't quote it verbatim):\n{seed}\n\n"
            f"Any number you use is BACKTESTED — say 'backtest'/'backtested' near it. Hard max "
            f"{char_limit - 30} characters (room for a link). End with rigacap.com/track-record "
            f"only if it fits naturally."
        )
        try:
            text = await self._call_claude(prompt)
            if not text:
                return None
            text = self._strip_markdown(text)
            text = _re.sub(r'^(Twitter|Instagram|Twitter/X|Threads|IG):\s*', '', text, flags=_re.IGNORECASE).strip()
            hashtags = "#Investing #RiskManagement #Behavioralfinance #RigaCap"
            eff_limit = max(120, char_limit - len(hashtags) - 2)
            if len(text) > eff_limit:
                text = text[:eff_limit - 1].rsplit(" ", 1)[0] + "…"
            return SocialPost(
                post_type="research_insight",
                platform=platform,
                status="draft",
                text_content=text,
                hashtags=hashtags,
                ai_generated=True,
                ai_model=CLAUDE_MODEL,
            )
        except Exception as e:
            logger.error(f"Research-insight generation failed: {e}")
            return None

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
