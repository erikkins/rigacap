"""
Newsletter Generator Service

Generates the weekly "Market, Measured." newsletter draft using Claude.
Four sections, each with a specific job:

§01 The Week in Focus — market regime read in plain English (readers open for this)
§02 One Idea, Explained — rotating educational topic (readers stay for this)
§03 What the System is Not Doing — discipline differentiator (trust-builder)
§04 A Note From Erik — personal, informal (relationship-builder)

Rules:
- No specific tickers in free version (paid subscribers see them on dashboard)
- No predictions ("we think the market will...")
- No doom-and-gloom or hype
- Pitch stays in footer only, never in body
- Target ~850 words total, never over 1200
- Voice: Matt Levine meets a curious quant founder at dinner
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import boto3
import httpx

logger = logging.getLogger(__name__)

S3_BUCKET = "rigacap-prod-price-data-149218244179"
DRAFT_KEY_PREFIX = "newsletter/drafts/"
ISSUE_KEY_PREFIX = "newsletter/issues/"

EDUCATIONAL_TOPICS = [
    {
        "slug": "walk-forward",
        "title": "Why walk-forward validation matters — and why most backtests are lying to you.",
        "seed": "Explain walk-forward simulation vs naive backtesting. Why optimizing on all data is cheating. What you get instead: numbers you can trust, even if they're lower.",
    },
    {
        "slug": "trailing-stops",
        "title": "The exit strategy that lets winners run.",
        "seed": "Explain trailing stops vs fixed stop losses. Why a 12% trailing stop is the Goldilocks number. How it changes your relationship with volatile stocks.",
    },
    {
        "slug": "regime-detection",
        "title": "Most investors think bull or bear. Reality has seven moods.",
        "seed": "Explain our 7 market regimes — by their actual names: Strong Bull, Weak Bull, Rotating Bull, Range-Bound, Weak Bear, Panic / Crash, and Recovery. Each calls for different behavior. How regime detection prevents the biggest mistake retail investors make: applying Strong Bull tactics in a Weak Bear or a Panic / Crash. NEVER substitute generic names like 'Bull' or 'Bear' or 'Neutral' or 'Strong Bear' — those are not our regimes.",
    },
    {
        "slug": "position-sizing",
        "title": "Why 6 positions at 15% each beats 30 positions at 3%.",
        "seed": "Explain concentrated vs diversified position sizing. Why over-diversification kills returns. How our system sizes positions based on conviction, not comfort.",
    },
    {
        "slug": "momentum-ranking",
        "title": "The math behind 'buy what's going up.'",
        "seed": "Explain momentum as a factor. Why 10-day and 60-day momentum windows capture different things. How composite scoring filters noise from signal.",
    },
    {
        "slug": "drawdown-math",
        "title": "A 50% loss requires a 100% gain to recover. That's not symmetry — that's the trap.",
        "seed": "Explain drawdown math and why protecting capital matters more than maximizing returns. How our max drawdown of ~24% compares to buy-and-hold's ~34% in 2022.",
    },
    {
        "slug": "signal-vs-noise",
        "title": "Why the system was quiet this month — and why that's the feature, not the bug.",
        "seed": "Explain why 3-4 signals per month is optimal. What happens when systems over-trade. Why quiet months are the discipline working, not broken.",
    },
    {
        "slug": "ensemble-approach",
        "title": "One signal is a guess. Three signals agreeing is a system.",
        "seed": "Explain ensemble methodology — combining timing, momentum quality, and confirmation. Why no single indicator is trusted alone. How disagreement between signals keeps you out of bad trades.",
    },
]

SYSTEM_PROMPT = """You write sections of a weekly financial newsletter called "Market, Measured." by Erik Kins, founder of RigaCap.

VOICE: Thoughtful, specific, lightly self-aware. Like Matt Levine or Marc Rubinstein — a smart person explaining something they find genuinely interesting. You're a curious founder, not a financial media personality.

ABSOLUTE RULES:
- Plain English only. NO jargon: no "tape," "bid," "offered," "risk-on," "price action," "positioning," "flows," "carry," "printing," "ripping," "names" (meaning stocks), or any trader-speak.
- No predictions. Never say "I think the market will..." The system responds to regime changes, it doesn't predict.
- No doom-and-gloom or hype. Both are easy clicks and both are antithetical to the brand.
- No specific ticker symbols EVER — no AAPL, NVDA, RIOT, SPY, nothing. Free readers who want tickers subscribe. Say "a name," "one position," "a tech stock" instead. The ONLY exception is "S&P 500" (the index name, not the ticker).
- No emojis. No hashtags.
- Never mention "our algorithm" or "AI-powered." You can say "the system" or "our approach."
- Sound human. Use fragments sometimes. Vary rhythm. Write like you typed it on a Sunday morning, not like you drafted it in a boardroom.
- Never start paragraphs with "Interesting" or "It's worth noting" or "Let me explain."
- Keep it tight. Each section should be 150-250 words. Total newsletter under 1000 words.
- CRITICAL: Every number you cite MUST come from the data provided. If the data says 0 stops, say 0. If it says 1, say 1. NEVER invent, round, or estimate numbers. If you don't have data for something, don't mention it. Getting a number wrong destroys trust instantly.

THE SEVEN REGIMES (these are the EXACT names — never substitute or invent others):
  1. Strong Bull       — broad rally, high participation
  2. Weak Bull         — advancing but narrow leadership
  3. Rotating Bull     — leadership rotating across sectors; index choppy
  4. Range-Bound       — no trend either way; chop
  5. Weak Bear         — drifting lower on weak breadth
  6. Panic / Crash     — disorderly selling; volatility spike
  7. Recovery          — turning up off a panic low; early signs of a base
NEVER use generic substitutes like "Bull," "Bear," "Strong Bear," "Neutral." Use the seven names above verbatim. If you must compress, "panic_crash" can be written "Panic Crash" but never just "Bear."

The newsletter has four sections. Each has a job:
§01 "The Week in Focus" — what the system is seeing right now, in plain English
§02 "One Idea, Explained" — teach one concept from quant methodology
§03 "What the System is Not Doing" — name 3 things we're sitting out, and why (THIS IS THE MOST IMPORTANT SECTION)
§04 "A Note From Erik" — 2-3 sentences, personal, invites reply

The pitch for RigaCap goes in the footer ONLY. Never in the body sections."""


class NewsletterGeneratorService:

    def __init__(self):
        self._s3 = None

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = boto3.client("s3", region_name="us-east-1")
        return self._s3

    def _get_topic_for_week(self, date: datetime) -> dict:
        week_num = date.isocalendar()[1]
        idx = week_num % len(EDUCATIONAL_TOPICS)
        return EDUCATIONAL_TOPICS[idx]

    def _call_claude(self, prompt: str, max_tokens: int = 1500) -> str:
        from app.core.config import settings
        if not settings.ANTHROPIC_API_KEY:
            return "(Claude API key not available)"

        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": max_tokens,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if resp.status_code == 200:
            content = resp.json().get("content", [])
            if content and content[0].get("type") == "text":
                return content[0]["text"].strip()
        logger.warning(f"Claude newsletter call failed: {resp.status_code} {resp.text[:300]}")
        return "(Generation failed)"

    def _clean_body(self, text: str) -> str:
        """Strip section headers/titles that Claude sometimes includes."""
        import re
        lines = text.strip().split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if re.match(r'^#{1,4}\s', stripped):
                continue
            if re.match(r'^§\s*\d', stripped):
                continue
            if re.match(r'^\*\*§', stripped):
                continue
            if re.match(r'^(The Week in Focus|One Idea|What the System|A Note From|What the system)', stripped, re.IGNORECASE):
                continue
            if re.match(r'^\*\*(The Week|One Idea|What the System|A Note|What the system)', stripped):
                continue
            if re.match(r'^---+$', stripped):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    def _load_dashboard_data(self) -> dict:
        try:
            obj = self.s3.get_object(Bucket=S3_BUCKET, Key="signals/dashboard.json")
            return json.loads(obj["Body"].read())
        except Exception as e:
            logger.warning(f"Failed to load dashboard data: {e}")
            return {}

    def generate_draft(self, target_date: Optional[datetime] = None, force: bool = False) -> dict:
        if target_date is None:
            # Newsletter publishes on Sunday. Find the upcoming Sunday — including
            # today if today IS Sunday — so the filename matches the publish date.
            # This prevents the Apr 25/26 incident where a Saturday-generated draft
            # got dated for Saturday and a separate Sunday draft was created later.
            now = datetime.now(timezone.utc)
            days_until_sunday = (6 - now.weekday()) % 7  # Mon=0, Sun=6
            target_date = now + timedelta(days=days_until_sunday)

        date_str = target_date.strftime("%Y-%m-%d")

        # Safety: never overwrite a locked draft. Primary guardrail against the
        # Apr 25/26 incident — once you lock an editorial commit, no regen can
        # silently overwrite it. Pass force=True only if you explicitly want
        # to overwrite (e.g., emergency content correction).
        existing = self.get_draft(date_str)
        if existing and existing.get("status") == "locked" and not force:
            raise ValueError(
                f"Draft for {date_str} is already locked — refusing to regenerate. "
                f"Pass force=True only if you explicitly want to overwrite a locked draft."
            )

        dashboard = self._load_dashboard_data()
        market_stats = dashboard.get("market_stats", {})
        regime = market_stats.get("regime_name", "Unknown")
        spy_price = market_stats.get("spy_price")
        spy_change = market_stats.get("spy_change_pct")
        vix = market_stats.get("vix_level")
        market_context = dashboard.get("market_context", "")
        buy_signals = dashboard.get("buy_signals", [])
        # Snapshot — today's fresh-flagged count. Useful for monitoring/total
        # context but NOT the right "this week" number (the newsletter is a
        # WEEKLY recap, not a today snapshot).
        fresh_today = len([s for s in buy_signals if s.get("is_fresh")])
        monitoring_count = len([s for s in buy_signals if not s.get("is_fresh")])
        watchlist = dashboard.get("watchlist", [])

        # Real "fresh this week" — union of distinct symbols across the past
        # 7 days, sourced from ensemble_signals AND model_positions entries
        # (model_positions catches names the model_portfolio acted on even if
        # the STR row insertion lagged — May 13 2026 audit revealed STR writes
        # can trail model_positions by a day in some flows).
        fresh_count = fresh_today  # safe default if DB query fails
        try:
            import asyncio
            from app.core.database import async_session
            from sqlalchemy import text as sa_text

            async def _fetch_week_fresh():
                nonlocal fresh_count
                async with async_session() as db:
                    rows = await db.execute(sa_text("""
                        SELECT DISTINCT symbol FROM (
                            SELECT symbol FROM ensemble_signals
                            WHERE ensemble_entry_date >= CURRENT_DATE - INTERVAL '7 days'
                            UNION
                            SELECT symbol FROM model_positions
                            WHERE entry_date >= CURRENT_DATE - INTERVAL '7 days'
                            AND portfolio_type = 'live'
                        ) AS week_fresh
                    """))
                    fresh_count = len(rows.fetchall())

            loop2 = asyncio.get_event_loop()
            if loop2.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_fetch_week_fresh())).result(timeout=10)
            else:
                loop2.run_until_complete(_fetch_week_fresh())
        except Exception as e:
            logger.warning(f"Could not load 7-day fresh count, falling back to today snapshot: {e}")

        # Pull real position data from DB (dashboard.json doesn't include portfolio)
        open_count = 0
        stops_count = 0
        profit_exits_count = 0
        try:
            import asyncio
            from app.core.database import async_session
            from sqlalchemy import text as sa_text

            async def _fetch_portfolio():
                nonlocal open_count, stops_count, profit_exits_count
                async with async_session() as db:
                    row = await db.execute(sa_text(
                        "SELECT COUNT(*) FROM model_positions WHERE status = 'open' AND portfolio_type = 'live'"
                    ))
                    open_count = row.scalar() or 0
                    rows = await db.execute(sa_text(
                        "SELECT exit_reason, pnl_pct FROM model_positions "
                        "WHERE status = 'closed' AND portfolio_type = 'live' "
                        "AND exit_date >= CURRENT_DATE - INTERVAL '7 days'"
                    ))
                    for r in rows.fetchall():
                        reason = (r[0] or "").lower()
                        pnl = r[1] or 0
                        if reason in ("trailing_stop", "stop_loss", "regime_exit"):
                            stops_count += 1
                        elif pnl > 0:
                            profit_exits_count += 1

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_fetch_portfolio())).result(timeout=10)
            else:
                loop.run_until_complete(_fetch_portfolio())
        except Exception as e:
            logger.warning(f"Could not load portfolio data for newsletter: {e}")
            # Fall back to dashboard data
            positions = dashboard.get("positions", [])
            open_count = len(positions)
            recent_sells = dashboard.get("recent_sells", [])
            stops_count = len([s for s in recent_sells if s.get("exit_reason", "").lower() in ("trailing_stop", "stop_loss", "regime_exit")])
            profit_exits_count = len([s for s in recent_sells if s.get("exit_reason", "").lower() not in ("trailing_stop", "stop_loss", "regime_exit") and s.get("pnl_pct", 0) > 0])

        # Load previous week's newsletter for continuity
        prev_week_context = ""
        try:
            prev_date = target_date - timedelta(days=7)
            prev_draft = self.get_draft(prev_date.strftime("%Y-%m-%d"))
            if prev_draft and prev_draft.get("sections"):
                prev_regime = prev_draft.get("regime", "")
                prev_s1 = prev_draft["sections"][0].get("body", "")[:500]
                prev_week_context = f"\n\nLAST WEEK'S CONTEXT (for continuity — reference if something changed dramatically, ignore if stable):"
                prev_week_context += f"\nLast week's regime: {prev_regime}."
                if prev_regime != regime:
                    prev_week_context += f" THIS WEEK: regime shifted to {regime}. Note the change — readers will remember what you said last week."
                else:
                    prev_week_context += f" Same regime this week. No need to dwell on it."
                prev_week_context += f"\nLast week's §01 opening (for voice continuity, don't repeat): {prev_s1[:300]}..."
        except Exception:
            pass

        # Build market summary for Claude — ONLY verifiable facts
        market_summary = f"Regime: {regime}."
        if spy_price is not None:
            direction = "up" if (spy_change or 0) >= 0 else "down"
            market_summary += f" S&P 500 closed {direction} {abs(spy_change or 0):.1f}% at ${spy_price:,.0f}."
        if vix is not None:
            market_summary += f" VIX at {vix:.0f}."
        market_summary += f"\nFresh signals this week: {fresh_count}. Monitoring: {monitoring_count}. Watchlist: {len(watchlist)}."
        market_summary += f"\nOpen positions: {open_count}."
        market_summary += f"\nStops triggered this week: {stops_count}."
        if profit_exits_count:
            market_summary += f"\nProfit exits this week: {profit_exits_count}."
        if market_context:
            market_summary += f"\n\nAI market briefing from the system: {market_context}"

        # §01 — The Week in Focus
        s1_prompt = f"""Write §01 "The Week in Focus" for this week's newsletter.

Market data:
{market_summary}{prev_week_context}

Write 2-3 paragraphs explaining what the system is seeing in plain English. Translate the regime and data into something a smart non-trader would understand. Don't just list numbers — interpret them. What does this regime mean for how the system is behaving?

You may reference: number of fresh signals, watchlist count, open positions, stops triggered, profit exits — but ONLY the exact numbers from the data above. Do NOT make up any numbers. If the data says 1 stop was triggered, say 1. If it says 0, say 0.

CRITICAL: Do NOT use any specific ticker symbols anywhere (no AAPL, NVDA, RIOT, etc.). This newsletter goes to free readers. Refer to stocks generically: "a name," "one position," "a tech stock." Subscribers who want tickers get them in the daily digest.

IMPORTANT: Output ONLY the body paragraphs. Do NOT include any section header, title, number, or label like "§01" or "The Week in Focus" — those are added separately.

150-250 words."""

        s1_text = self._clean_body(self._call_claude(s1_prompt))

        # §02 — One Idea, Explained
        topic = self._get_topic_for_week(target_date)
        s2_prompt = f"""Write §02 "One Idea, Explained" about this topic:

Title: {topic['title']}
Concept to explain: {topic['seed']}

Write 2-3 paragraphs explaining this concept to a smart person who isn't a quant. Use a concrete example or thought experiment. Make it genuinely educational — this is the section that makes readers smarter, which is why they stay subscribed.

CRITICAL: This section is purely educational. Do NOT reference any specific trades, positions, stops, tickers, or events from this week. Do NOT make up specific numbers about what the system did or didn't do. Teach the concept abstractly with hypothetical examples only.

IMPORTANT: Output ONLY the body paragraphs. Do NOT include any section header, title, number, or label — those are added separately.

200-300 words."""

        s2_text = self._clean_body(self._call_claude(s2_prompt))

        # §03 — What the System is Not Doing
        s3_prompt = f"""Write §03 "What the System is Not Doing" for this week.

THIS IS THE MOST IMPORTANT SECTION. It builds trust by naming things we're explicitly sitting out.

Market context:
{market_summary}

Based on the current regime and market conditions, write EXACTLY 3 items — things the system is NOT doing right now, and why.

Format: Each item starts with **Bold lead-in.** followed by 1-2 sentences. Example:
**Not chasing the AI rally.** The momentum scores have diverged from price in ways that historically precede pullbacks. We might miss more upside. That's fine.

Choose from ideas like:
- Not chasing a specific hot sector
- Not shorting anything (long-only by design)
- Not touching small caps (volume/price filters)
- Not adding positions in a weakening regime
- Not panic-selling existing positions despite headlines
- Not following the crowd into a popular trade

CRITICAL RULES:
- Output EXACTLY 3 items, each starting with **bold text.**
- Do NOT include any preamble, section header, title, or intro text like "Right now, the system is:" — just the 3 items.
- Do NOT include the closing italic sentence about "if you're looking for a system" — that's added separately.
- Do NOT number them.
- Do NOT use any specific ticker symbols (no AAPL, NVDA, FCX, etc.). Refer to stocks generically ("a name," "one position," "a tech stock").
- Do NOT invent or fabricate any events, exits, or trades. Only reference the counts from the data above.

150-200 words total."""

        s3_text = self._call_claude(s3_prompt)

        # Parse §03 into exactly 3 items
        import re
        s3_items = []
        # Split on bold markers — each item starts with **
        parts = re.split(r'\n(?=\*\*)', s3_text.strip())
        for part in parts:
            part = part.strip()
            if not part or not part.startswith('**'):
                continue
            # Convert markdown bold to HTML
            part = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', part, count=1)
            part = part.replace('\n', ' ').strip()
            s3_items.append(part)
        s3_items = s3_items[:3]

        # §04 — A Note From Erik
        s4_prompt = f"""Write §04 "A Note From Erik" — the founder signoff.

2-3 sentences only. Personal, informal, not pitch-y. Invite replies. Something tied to the current moment — maybe the regime, the season, a reflection on building in public. Don't be cheesy. Don't be motivational. Just be a real person writing to people who read your newsletter.

End with "See you next Sunday." on its own line.

IMPORTANT: Output ONLY the personal note text. Do NOT include any section header, title, number, or label. Do NOT start with "A Note From Erik" or similar — just the note itself.

50 words max."""

        s4_text = self._clean_body(self._call_claude(s4_prompt, max_tokens=200))

        # Build the draft
        date_str = target_date.strftime("%Y-%m-%d")
        draft = {
            "date": date_str,
            "date_display": target_date.strftime("%B %d, %Y"),
            "status": "draft",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "regime": regime,
            "spy_price": spy_price,
            "spy_change": spy_change,
            "vix_level": vix,
            "fresh_count": fresh_count,
            "watchlist_count": len(watchlist),
            "word_count": len((s1_text + s2_text + s3_text + s4_text).split()),
            "sections": [
                {
                    "num": "01",
                    "label": "The Week in Focus",
                    "title": "What the system sees.",
                    "body": s1_text,
                },
                {
                    "num": "02",
                    "label": "One Idea, Explained",
                    "title": topic["title"],
                    "body": s2_text,
                },
                {
                    "num": "03",
                    "label": "What the System is Not Doing",
                    "title": "What the system is <em>not</em> doing.",
                    "items": s3_items,
                },
                {
                    "num": "04",
                    "label": "A Note From Erik",
                    "title": None,
                    "body": s4_text,
                },
            ],
        }

        # Don't overwrite a draft that was manually edited or locked
        existing = self.get_draft(date_str)
        if existing and existing.get("edited_at"):
            logger.warning(f"Skipping overwrite — draft for {date_str} was manually edited")
            return existing
        if existing and existing.get("status") == "locked":
            logger.warning(f"Skipping overwrite — draft for {date_str} is locked")
            return existing

        # Save draft to S3
        self.s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{DRAFT_KEY_PREFIX}{date_str}.json",
            Body=json.dumps(draft).encode(),
            ContentType="application/json",
        )

        logger.warning(f"Newsletter draft generated for {date_str}: {draft['word_count']} words")
        return draft

    def get_draft(self, date_str: str) -> Optional[dict]:
        try:
            obj = self.s3.get_object(
                Bucket=S3_BUCKET,
                Key=f"{DRAFT_KEY_PREFIX}{date_str}.json",
            )
            return json.loads(obj["Body"].read())
        except Exception:
            return None

    def get_latest_draft(self) -> Optional[dict]:
        try:
            resp = self.s3.list_objects_v2(
                Bucket=S3_BUCKET, Prefix=DRAFT_KEY_PREFIX
            )
            # Filter out the backups/ subdirectory — those files have keys
            # like 'newsletter/drafts/backups/2026-05-03.pre-regime-fix.json'
            # which sort AFTER the top-level dated drafts in descending order
            # (because 'b' > digit chars), so without this filter
            # get_latest_draft() returned the BACKUP of an old issue instead
            # of the latest live draft. Surfaced May 16 2026 when the admin
            # editor stubbornly showed the May 3 draft even though May 17
            # was the freshest.
            keys = sorted(
                [
                    o["Key"] for o in resp.get("Contents", [])
                    if "/backups/" not in o["Key"]
                ],
                reverse=True,
            )
            if keys:
                obj = self.s3.get_object(Bucket=S3_BUCKET, Key=keys[0])
                return json.loads(obj["Body"].read())
        except Exception:
            pass
        return None

    def update_draft(self, date_str: str, sections: List[dict]) -> dict:
        draft = self.get_draft(date_str)
        if not draft:
            raise ValueError(f"No draft found for {date_str}")
        if draft.get("status") == "locked":
            raise ValueError("Draft is locked and cannot be edited")

        draft["sections"] = sections
        draft["edited_at"] = datetime.now(timezone.utc).isoformat()
        total_text = " ".join(
            s.get("body", "") + " ".join(s.get("items", []))
            for s in sections
        )
        draft["word_count"] = len(total_text.split())

        self.s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{DRAFT_KEY_PREFIX}{date_str}.json",
            Body=json.dumps(draft).encode(),
            ContentType="application/json",
        )
        return draft

    def unlock_draft(self, date_str: str) -> dict:
        draft = self.get_draft(date_str)
        if not draft:
            raise ValueError(f"No draft found for {date_str}")
        draft["status"] = "draft"
        draft.pop("locked_at", None)
        self.s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{DRAFT_KEY_PREFIX}{date_str}.json",
            Body=json.dumps(draft).encode(),
            ContentType="application/json",
        )
        return draft

    def lock_draft(self, date_str: str) -> dict:
        draft = self.get_draft(date_str)
        if not draft:
            raise ValueError(f"No draft found for {date_str}")

        draft["status"] = "locked"
        draft["locked_at"] = datetime.now(timezone.utc).isoformat()

        draft_json = json.dumps(draft).encode()

        # Save locked draft
        self.s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{DRAFT_KEY_PREFIX}{date_str}.json",
            Body=draft_json,
            ContentType="application/json",
        )

        # Also publish to issues/ for the public web archive
        self.s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{ISSUE_KEY_PREFIX}{date_str}.json",
            Body=draft_json,
            ContentType="application/json",
        )

        logger.warning(f"Newsletter draft locked for {date_str}")
        return draft


newsletter_generator = NewsletterGeneratorService()
