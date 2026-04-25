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
from datetime import datetime, timezone
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
        "seed": "Explain the 7 market regimes. Why 'Strong Bull' and 'Weak Bull' require different behavior. How regime detection prevents the biggest mistake retail investors make: applying bull market tactics in a bear.",
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
- No specific ticker symbols. Free readers who want picks can subscribe.
- No emojis. No hashtags.
- Never mention "our algorithm" or "AI-powered." You can say "the system" or "our approach."
- Sound human. Use fragments sometimes. Vary rhythm. Write like you typed it on a Sunday morning, not like you drafted it in a boardroom.
- Never start paragraphs with "Interesting" or "It's worth noting" or "Let me explain."
- Keep it tight. Each section should be 150-250 words. Total newsletter under 1000 words.

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
                "model": "claude-sonnet-4-5-20250929",
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

    def _load_dashboard_data(self) -> dict:
        try:
            obj = self.s3.get_object(Bucket=S3_BUCKET, Key="signals/dashboard.json")
            return json.loads(obj["Body"].read())
        except Exception as e:
            logger.warning(f"Failed to load dashboard data: {e}")
            return {}

    def generate_draft(self, target_date: Optional[datetime] = None) -> dict:
        if target_date is None:
            target_date = datetime.now(timezone.utc)

        dashboard = self._load_dashboard_data()
        market_stats = dashboard.get("market_stats", {})
        regime = market_stats.get("regime_name", "Unknown")
        spy_price = market_stats.get("spy_price")
        spy_change = market_stats.get("spy_change_pct")
        vix = market_stats.get("vix_level")
        market_context = dashboard.get("market_context", "")
        buy_signals = dashboard.get("buy_signals", [])
        fresh_count = len([s for s in buy_signals if s.get("is_fresh")])
        monitoring_count = len([s for s in buy_signals if not s.get("is_fresh")])
        watchlist = dashboard.get("watchlist", [])

        # Build market summary for Claude
        market_summary = f"Regime: {regime}."
        if spy_price is not None:
            direction = "up" if (spy_change or 0) >= 0 else "down"
            market_summary += f" S&P 500 closed {direction} {abs(spy_change or 0):.1f}% at ${spy_price:,.0f}."
        if vix is not None:
            market_summary += f" VIX at {vix:.0f}."
        market_summary += f" Fresh signals this week: {fresh_count}. Monitoring: {monitoring_count}. Watchlist: {len(watchlist)}."
        if market_context:
            market_summary += f"\n\nAI market briefing from the system: {market_context}"

        # §01 — The Week in Focus
        s1_prompt = f"""Write §01 "The Week in Focus" for this week's newsletter.

Market data:
{market_summary}

Write 2-3 paragraphs explaining what the system is seeing in plain English. Translate the regime and data into something a smart non-trader would understand. Don't just list numbers — interpret them. What does this regime mean for how the system is behaving?

If there were fresh signals, mention that the system found opportunities (don't name tickers). If there were none, explain why quiet weeks happen and why that's the system working as designed.

150-250 words."""

        s1_text = self._call_claude(s1_prompt)

        # §02 — One Idea, Explained
        topic = self._get_topic_for_week(target_date)
        s2_prompt = f"""Write §02 "One Idea, Explained" about this topic:

Title: {topic['title']}
Concept to explain: {topic['seed']}

Current market context (weave in if natural, don't force it):
{market_summary}

Write 2-3 paragraphs explaining this concept to a smart person who isn't a quant. Use a concrete example or thought experiment. Make it genuinely educational — this is the section that makes readers smarter, which is why they stay subscribed.

200-300 words."""

        s2_text = self._call_claude(s2_prompt)

        # §03 — What the System is Not Doing
        s3_prompt = f"""Write §03 "What the System is Not Doing" for this week.

THIS IS THE MOST IMPORTANT SECTION. It builds trust by naming things we're explicitly sitting out.

Market context:
{market_summary}

Based on the current regime and market conditions, name 3 specific things the system is NOT doing right now, and explain why for each. Format each as a bold lead-in followed by 1-2 sentences of explanation.

Examples of what "not doing" means:
- Not chasing a specific sector rally that's overextended
- Not shorting anything (long-only by design)
- Not touching small caps (volume/price filters)
- Not adding positions in a weakening regime
- Not panic-selling existing positions despite headlines
- Not following the crowd into a popular trade

End with one italic sentence: "If you're looking for a system that does all of those things, this isn't it. What you're getting instead is a system that tries to do one thing very well and is transparent about what it won't do."

150-200 words for the three items."""

        s3_text = self._call_claude(s3_prompt)

        # Parse §03 into items (Claude returns them as bold lead-ins)
        s3_items = []
        current_item = ""
        for line in s3_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("**") or line.startswith("- **") or line.startswith("—"):
                if current_item:
                    s3_items.append(current_item.strip())
                current_item = line.lstrip("-—").strip()
            elif line.startswith("*If you") or line.startswith("If you"):
                if current_item:
                    s3_items.append(current_item.strip())
                    current_item = ""
            else:
                current_item += " " + line
        if current_item:
            s3_items.append(current_item.strip())

        # Clean markdown bold to HTML
        s3_items = [
            item.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            for item in s3_items[:3]
        ]

        # §04 — A Note From Erik
        s4_prompt = f"""Write §04 "A Note From Erik" — the founder signoff.

2-3 sentences only. Personal, informal, not pitch-y. Invite replies. Something tied to the current moment — maybe the regime, the season, a reflection on building in public. Don't be cheesy. Don't be motivational. Just be a real person writing to people who read your newsletter.

End with "See you next Sunday." on its own line.

50 words max."""

        s4_text = self._call_claude(s4_prompt, max_tokens=200)

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
            keys = sorted(
                [o["Key"] for o in resp.get("Contents", [])],
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

    def lock_draft(self, date_str: str) -> dict:
        draft = self.get_draft(date_str)
        if not draft:
            raise ValueError(f"No draft found for {date_str}")

        draft["status"] = "locked"
        draft["locked_at"] = datetime.now(timezone.utc).isoformat()

        self.s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{DRAFT_KEY_PREFIX}{date_str}.json",
            Body=json.dumps(draft).encode(),
            ContentType="application/json",
        )
        logger.warning(f"Newsletter draft locked for {date_str}")
        return draft


newsletter_generator = NewsletterGeneratorService()
