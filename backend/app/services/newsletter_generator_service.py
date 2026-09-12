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
import re
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
        "seed": "Explain walk-forward simulation vs naive backtesting. Why optimizing on all data is cheating. The credibility test: when cleaner data made our own numbers smaller, we published the smaller numbers. What you get instead: figures you can trust, even when they're lower.",
    },
    {
        "slug": "behavioral-gap",
        "title": "The return your strategy earned isn't the return you collected.",
        "seed": "Explain the investor behavior gap: Morningstar measures it around 1.2 percentage points a year; in crash years it's far worse. Investors collect less than their strategies earn because they sell at bottoms and re-enter late. The punchline: the best strategy is not the one with the biggest number — it's the one whose path never hands you a reason to quit.",
    },
    {
        "slug": "drawdown-math",
        "title": "A 50% loss requires a 100% gain to recover. That's not symmetry — that's the trap.",
        "seed": "Explain drawdown math and why protecting capital matters more than maximizing returns. In our 21-year walk-forward Preserver's worst drawdown was 13.7%, while the index lost more than half its value twice in the same span. Describe all figures as walk-forward.",
    },
    {
        "slug": "wide-stops",
        "title": "Why our stops are wide — tight stops feel safe and bleed you dry.",
        "seed": "Explain trailing stops vs fixed stop losses, and why TIGHT trailing stops are a trap: every wiggle stops you out, you pay the whipsaw tax, and you miss the recovery. Wide trailing stops give winners room to breathe and only act on genuine trend breaks. Don't cite specific stop percentages — explain the principle.",
    },
    {
        "slug": "diversified-sizing",
        "title": "Concentration looks brave. Mostly it's just loud.",
        "seed": "Explain position sizing: why a book of roughly twenty volatility-sized positions beats a handful of big concentrated bets. Concentration amplifies both your best idea and your worst, and the worst is the one that ends the ride. Sizing by volatility means every position carries similar risk, not similar dollars.",
    },
    {
        "slug": "cash-position",
        "title": "Cash is a position. Sometimes it's the only correct one.",
        "seed": "Explain why the system moves entirely to cash when market conditions turn hostile, and stays out until conditions recover. The hardest part isn't the math — it's that sitting out feels like failing while markets bounce. Reference the 2008 result: our walk-forward ended that year roughly flat while the index fell about 37%, because it had gone to cash early. Describe as walk-forward.",
    },
    {
        "slug": "signal-vs-noise",
        "title": "Why the system was quiet this week — and why that's the feature, not the bug.",
        "seed": "Explain selectivity: the system only acts when its entry conditions all align, and most days they don't. What happens when systems over-trade. Why quiet stretches are the discipline working, not broken. Never cite a specific signals-per-month cadence.",
    },
    {
        "slug": "ensemble-approach",
        "title": "One signal is a guess. Three signals agreeing is a system.",
        "seed": "Explain ensemble methodology — combining timing, momentum quality, and confirmation. Why no single indicator is trusted alone. How disagreement between signals keeps you out of bad trades. Describe the structure only — never specific thresholds or formulas.",
    },
    {
        "slug": "momentum-explained",
        "title": "The math behind 'buy what's going up.'",
        "seed": "Explain momentum as a factor: it's one of the most persistent effects in markets, and also one of the most violent when it unwinds. How our approach looks for recent acceleration inside an established longer trend, penalized for volatility — structure only, no specific lookback windows or weights. Why raw, unmanaged momentum is almost impossible for a human to hold: in our 21-year walk-forward the raw factor drew down 57%.",
    },
    {
        "slug": "sharpe-over-decades",
        "title": "What a 'good' Sharpe ratio actually looks like over twenty years.",
        "seed": "Explain why Sharpe ratios above 1 live in short windows and overfit backtests, while long-horizon Sharpes compress: the S&P 500 scored 0.54 over the last 21 years, Warren Buffett's lifetime figure is about 0.79 ('Buffett's Alpha', Frazzini/Kabiller/Pedersen 2018) — the best ever measured over 30+ years. Our 21-year walk-forward figures are Preserver 0.87 and Maximizer 0.93 — above Buffett's, so state plainly that ours is walk-forward (with a pre-2016 survivorship caveat that flatters the early years) where Buffett's is real.",
    },
    {
        "slug": "the-premium",
        "title": "We trail the index most years. On purpose. Here's the deal.",
        "seed": "Explain the structural trade: a defensive momentum strategy behaves like insurance — it pays its premium in bull-run underperformance and collects in crashes. In our 21-year walk-forward Preserver beat the index in only about a quarter of rolling 3-year windows; its wins concentrate almost entirely in periods containing a crash. If you need to beat the market every year, this is the wrong product — and saying so up front is the point.",
    },
    {
        "slug": "the-exit-is-the-edge",
        "title": "Everyone obsesses over the entry. The exit is where the money is kept.",
        "seed": "Explain the Maximizer side: in momentum, picking a winner is the easy part — the hard part is not giving it back. The real edge is a pre-decided exit rule that fires whether or not you feel brave, so a big gain never round-trips to zero. 'Growth with a seatbelt.' Contrast with the human instinct to hold a winner 'just a little longer' and watch it reverse. Structure only, no specific hold windows or thresholds.",
    },
    {
        "slug": "two-settings",
        "title": "Protect and grow are two different jobs. So we stopped forcing one dial to do both.",
        "seed": "Explain why one engine now has two settings — Preserver (protect) and Maximizer (grow). A single dial tuned to protect gives the growth-seeker a compromise, and vice versa. Same discipline underneath (momentum, regime awareness, a hard exit); the reader picks the temperament. The point isn't which number is bigger — it's that neither setting asks you to be a hero at the worst possible moment. Numbers walk-forward only.",
    },
    {
        "slug": "riding-winners",
        "title": "Why we buy strength, not dips — and hold on a clock, not a feeling.",
        "seed": "Explain buying into strength near recent highs (never catching a falling knife) and holding on a predetermined schedule rather than on conviction or mood. Feelings are the enemy of a momentum book: they make you sell winners early and marry losers. A clock doesn't have feelings. Structure/principle only — no specific hold lengths or entry thresholds.",
    },
]

from app.services.perf_numbers import PERF as _PERF


def _canonical_numbers_block() -> str:
    """Canonical performance lines from the SSOT (perf_numbers.PERF) so newsletter copy can't
    drift from the site. NEVER hardcode these figures — change them in perf_numbers."""
    p, m, b = _PERF["preserver"], _PERF["maximizer"], _PERF["benchmarks"]
    s = _PERF["supporting"]
    dd = lambda x: f"{abs(x):g}"
    return (
        f"- 21-year walk-forward (2007-2026): RigaCap Preserver {p['yr21']['cagr']:g}% a year, "
        f"worst drawdown {dd(p['yr21']['maxdd'])}%; RigaCap Maximizer {m['yr21']['cagr']:g}% a year, "
        f"worst drawdown {dd(m['yr21']['maxdd'])}%\n"
        f"- The index (S&P 500) returned {b['spy_21yr']['cagr']:g}% a year and lost more than half its "
        f"value twice in that span; raw momentum returned {b['raw_mom_21yr']['cagr']:g}% and drew down "
        f"{dd(b['raw_mom_21yr']['maxdd'])}%\n"
        f"- 2008: both settings ended the year roughly flat (about +{s['yr2008']['preserver']:g}%) while the index fell about 37%\n"
        f"- A typical 2-year stretch (rolling, walk-forward): Preserver about +{p['typical_24mo']:g}%, "
        f"Maximizer about +{m['typical_24mo']:g}%\n"
        f"- Sharpe over 21 walk-forward years: Preserver {p['yr21']['sharpe']:g}, Maximizer {m['yr21']['sharpe']:g} "
        f"(S&P 0.54; Buffett's lifetime is 0.79 — note our pre-2016 data carries a survivorship caveat that flatters the early years)"
    )


_CANON = _canonical_numbers_block()

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
- AGGREGATE DATA ONLY — this is the #1 source of fabrication, so read carefully. The ONLY facts you have are: the regime, the S&P 500 move, the VIX, the structured counts (fresh signals / monitoring / watchlist / open positions / stops / profit exits), and the MARKET COLOR briefing (broad index/sector/commodity moves). You do NOT know any individual stock's move, any specific day's trade, how any named position behaved, or a sub-count like "4 of the 8 are clean." NEVER invent a per-security or per-day anecdote — e.g. "a tech stock jumped 20% Wednesday," "a position sold Thursday afternoon," "a ride-hailing name," "four clean entries." Speak from the aggregate and from the SYSTEM'S PRINCIPLES, never from fabricated trade detail.
- NEVER INVENT NEWS. You may reference a current event ONLY if it appears verbatim in a "RECENT HEADLINES" block provided in the prompt. If no headlines are provided, do NOT reference any specific dated event, vote, Fed meeting, earnings, or "this week X happened" — you have no way to know it occurred, and fabricating one (e.g. "the Senate stopgap cleared Thursday and the system re-evaluated within the hour") invents both the event and a causal claim. When you do cite a provided headline, never claim the system "reacted within the hour" or imply causation you can't observe — just note the backdrop.

THE SEVEN REGIMES (these are the EXACT names — never substitute or invent others):
  1. Strong Bull       — broad rally, high participation
  2. Weak Bull         — advancing but narrow leadership
  3. Rotating Bull     — leadership rotating across sectors; index choppy
  4. Range-Bound       — no trend either way; chop
  5. Weak Bear         — drifting lower on weak breadth
  6. Panic / Crash     — disorderly selling; volatility spike
  7. Recovery          — turning up off a panic low; early signs of a base
NEVER use generic substitutes like "Bull," "Bear," "Strong Bear," "Neutral." Use the seven names above verbatim. If you must compress, "panic_crash" can be written "Panic Crash" but never just "Bear."

POSITIONING (Aug 2026): RigaCap is ONE engine with TWO settings, and the newsletter must speak to both temperaments — never Preserver-only.
- PRESERVER (protect): shallow drawdowns, sleep-at-night; built so you never get a reason to sell at the bottom.
- MAXIMIZER (grow): the same engine pushed for offense — hunts breakouts and rides winners, but the edge is the EXIT, not the entry: every name sells on a hard rule so a big gain never round-trips to zero. "Growth with a seatbelt."
The connective tissue is DISCIPLINE, not defense — the reader chooses how hard to push. Write with range and energy: confident about the upside (Maximizer), honest about the tradeoffs, never doom or hype, never predicting. If a section only ever talks about protecting/trailing/sitting-out, it has drifted Preserver-only — pull in the growth side.

PERFORMANCE NUMBERS — these are the ONLY ones you may cite; always describe them as WALK-FORWARD, NEVER "backtest":
""" + _CANON + """
- The LIVE record began June 11, 2026 — it is days old, and we say so plainly
PRODUCT: one engine, two settings — Preserver (preserve) and Maximizer (push). Never cite any other performance figure, including from older marketing, and NEVER the internal "Core"/t30v numbers.

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

    # Cardinal brand rule (feedback_no_tape_brand_voice): the market is never "the tape". The system
    # prompt forbids it, but the model can still slip — so we FINAL-CHECK every section and, if "tape"
    # appears, discard and regenerate (Erik: "run a final check … discard and regen"). Only if it
    # survives every retry do we scrub as a last resort, so "tape" can never ship.
    _BANNED_RE = re.compile(r'\btape\b', re.IGNORECASE)

    def _call_claude(self, prompt: str, max_tokens: int = 1500) -> str:
        from app.core.config import settings
        if not settings.ANTHROPIC_API_KEY:
            return "(Claude API key not available)"

        last = "(Generation failed)"
        for attempt in range(3):
            # On a retry, tell the model exactly what it did wrong so the regen actually differs.
            user_prompt = prompt if attempt == 0 else (
                prompt + "\n\nIMPORTANT: your previous attempt used the banned word \"tape\". Do NOT "
                "use \"tape\" anywhere — say \"the market\", \"the market's move\", or \"conditions\" "
                "instead. Regenerate the section cleanly."
            )
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-opus-4-8",  # weekly + quality-critical → most capable model
                    "max_tokens": max_tokens,
                    # Prompt-cache the static newsletter system prompt — an issue
                    # generates several sections back-to-back within the cache window.
                    "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                    "messages": [{"role": "user", "content": user_prompt}],
                },
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning(f"Claude newsletter call failed: {resp.status_code} {resp.text[:300]}")
                return "(Generation failed)"
            content = resp.json().get("content", [])
            if not (content and content[0].get("type") == "text"):
                return "(Generation failed)"
            text = content[0]["text"].strip()
            if not self._BANNED_RE.search(text):
                return text
            logger.warning(f"newsletter: banned word 'tape' in output (attempt {attempt + 1}/3) — discarding + regenerating")
            last = text

        # Regen exhausted — never ship "tape". Scrub to a neutral word and alert.
        logger.error("newsletter: 'tape' persisted after 3 regens — scrubbing to 'market' as last resort")
        return self._BANNED_RE.sub(lambda m: 'Market' if m.group(0)[0].isupper() else 'market', last)

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

    def _weekly_market_pack(self) -> str:
        """Real WEEKLY facts for the recap — so §01 summarizes the WEEK, not a single EOD snapshot,
        and never invents a regime-duration count. Every figure is computed from real data; anything
        unavailable is OMITTED (never fabricated). Returns a text block (or '' if nothing computable):
          - the current regime's UNBROKEN run (consecutive trading days / ~weeks) from market_context_history
          - week-over-week (~5 trading day) moves for SPY / Nasdaq-100 / Small Caps / Gold / Treasuries
            from real closes in scanner_service.data_cache
          - the week's biggest single-day S&P move
        """
        lines = []
        # --- regime run: consecutive trading days in the current regime (real, from history) ---
        try:
            import asyncio
            from app.core.database import async_session
            from sqlalchemy import text as sa_text
            run = {}

            async def _fetch_run():
                async with async_session() as db:
                    rows = await db.execute(sa_text(
                        "SELECT date, regime FROM market_context_history ORDER BY date DESC LIMIT 200"
                    ))
                    recs = rows.fetchall()
                    if not recs:
                        return
                    cur = recs[0][1]
                    n, first = 0, recs[0][0]
                    for d, rg in recs:
                        if rg == cur:
                            n += 1
                            first = d
                        else:
                            break
                    run.update(regime=cur, days=n, since=first)

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_fetch_run())).result(timeout=10)
            else:
                loop.run_until_complete(_fetch_run())
            if run.get("days"):
                wks = max(1, round(run["days"] / 5))
                lines.append(
                    f"REGIME RUN (real): the current regime ({run['regime']}) has held UNBROKEN for "
                    f"{run['days']} consecutive trading days (~{wks} weeks), since {run['since']}. "
                    f"State the regime's duration ONLY from this figure — NEVER invent a 'Nth week' count."
                )
        except Exception as e:
            logger.warning(f"weekly regime-run compute failed (omitting): {e}")

        # --- week-over-week asset moves from real closes (omit any symbol without clean history) ---
        try:
            import pandas as pd
            from app.services.scanner import scanner_service
            dc = getattr(scanner_service, "data_cache", {}) or {}
            assets = [("SPY", "S&P 500"), ("QQQ", "Nasdaq-100"), ("IWM", "Small Caps"),
                      ("GLD", "Gold"), ("TLT", "20-Year Treasuries")]
            moves, spy_notable = [], None
            for sym, name in assets:
                df = dc.get(sym)
                if df is None or "close" not in getattr(df, "columns", []) or len(df) < 6:
                    continue
                c = df["close"].astype(float)
                wk = (c.iloc[-1] / c.iloc[-6] - 1) * 100
                moves.append(f"{name} {'+' if wk >= 0 else ''}{wk:.1f}%")
                if sym == "SPY":
                    d5 = c.pct_change().tail(5) * 100
                    if len(d5):
                        idx = d5.abs().idxmax()
                        val = float(d5.loc[idx])
                        try:
                            dayname = pd.Timestamp(idx).strftime("%A")
                        except Exception:
                            dayname = None
                        spy_notable = f"{'+' if val >= 0 else ''}{val:.1f}%" + (f" ({dayname})" if dayname else "")
            if moves:
                lines.append(
                    "WEEKLY MARKET MOVES (real, ~5 trading days / week-over-week — cite THESE for the "
                    "week's action, NOT any single-day figure from the daily briefing): "
                    + ", ".join(moves) + "."
                )
            if spy_notable:
                lines.append(f"Biggest single S&P 500 day this week: {spy_notable}.")
        except Exception as e:
            logger.warning(f"weekly asset moves compute failed (omitting): {e}")

        return "\n".join(lines)

    LEAD_STORY_KEY = "newsletter/next_lead_story.json"

    def get_pending_lead_story(self) -> Optional[str]:
        """Optional operator-set focus for the next issue (set via the
        set_newsletter_lead_story Lambda event). Consumed on use."""
        try:
            obj = self.s3.get_object(Bucket=S3_BUCKET, Key=self.LEAD_STORY_KEY)
            return json.loads(obj["Body"].read()).get("concept") or None
        except Exception:
            return None

    def set_lead_story(self, concept: str) -> None:
        self.s3.put_object(Bucket=S3_BUCKET, Key=self.LEAD_STORY_KEY,
                           Body=json.dumps({"concept": concept}).encode())

    def _consume_lead_story(self, date_str: str) -> None:
        try:
            obj = self.s3.get_object(Bucket=S3_BUCKET, Key=self.LEAD_STORY_KEY)
            self.s3.put_object(Bucket=S3_BUCKET,
                               Key=f"newsletter/used_lead_stories/{date_str}.json",
                               Body=obj["Body"].read())
            self.s3.delete_object(Bucket=S3_BUCKET, Key=self.LEAD_STORY_KEY)
        except Exception:
            pass

    # --- Durable topic queue (the backlog Erik drives from the editor) ------------------------
    # newsletter/topic_queue.json = ordered list of {id, title, concept, body_preserved?, added_at}.
    # A one-liner/concept → §02 is regenerated from it; body_preserved → reused verbatim.
    TOPIC_QUEUE_KEY = "newsletter/topic_queue.json"

    def list_queue(self) -> list:
        try:
            q = json.loads(self.s3.get_object(Bucket=S3_BUCKET, Key=self.TOPIC_QUEUE_KEY)["Body"].read())
            return q if isinstance(q, list) else []
        except Exception:
            return []

    def _save_queue(self, q: list) -> None:
        self.s3.put_object(Bucket=S3_BUCKET, Key=self.TOPIC_QUEUE_KEY,
                           Body=json.dumps(q).encode(), ContentType="application/json")

    def add_topic(self, title: str, concept: str, body_preserved: Optional[str] = None) -> dict:
        import uuid
        item = {"id": uuid.uuid4().hex[:12], "title": (title or "").strip() or "Untitled topic",
                "concept": (concept or "").strip(), "added_at": datetime.now(timezone.utc).date().isoformat()}
        if body_preserved:
            item["body_preserved"] = body_preserved
        q = self.list_queue(); q.append(item); self._save_queue(q)
        return item

    def remove_topic(self, topic_id: str) -> list:
        q = [x for x in self.list_queue() if x.get("id") != topic_id]
        self._save_queue(q); return q

    def reorder_queue(self, ordered_ids: list) -> list:
        by = {x["id"]: x for x in self.list_queue()}
        new = [by[i] for i in ordered_ids if i in by] + [x for x in by.values() if x["id"] not in set(ordered_ids)]
        self._save_queue(new); return new

    def _pop_topic(self, topic_id: str) -> Optional[dict]:
        q = self.list_queue(); item = next((x for x in q if x.get("id") == topic_id), None)
        if item:
            self._save_queue([x for x in q if x.get("id") != topic_id])
        return item

    def generate_draft(self, target_date: Optional[datetime] = None, force: bool = False,
                       lead_story: Optional[str] = None, topic_id: Optional[str] = None) -> dict:
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
        max_time_stops = 0   # Maximizer breakout positions that reached their 29-day time-stop this week
        week_wins = []  # real closed WINNERS this week: (pnl_pct, days_held) — no tickers
        try:
            import asyncio
            from app.core.database import async_session
            from sqlalchemy import text as sa_text

            async def _fetch_portfolio():
                nonlocal open_count, stops_count, profit_exits_count, max_time_stops, week_wins
                async with async_session() as db:
                    row = await db.execute(sa_text(
                        "SELECT COUNT(*) FROM model_positions WHERE status = 'open' AND portfolio_type = 'live'"
                    ))
                    open_count = row.scalar() or 0
                    rows = await db.execute(sa_text(
                        "SELECT exit_reason, pnl_pct, entry_date, exit_date FROM model_positions "
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
                        if pnl and pnl > 0:
                            days = None
                            try:
                                if r[2] and r[3]:
                                    days = (r[3] - r[2]).days
                            except Exception:
                                days = None
                            week_wins.append((round(float(pnl), 1), days))
                    week_wins.sort(key=lambda w: w[0], reverse=True)

                    # Maximizer runs a SEPARATE breakout book whose exits are time-stops (sold on
                    # reaching their 29-day hold), NOT trailing/loss stops — so they live in
                    # tier_fills (reason='hold_exit'), not model_positions. Count this week's so the
                    # newsletter can say "0 Preserver stops, but N Maximizer positions timed out"
                    # instead of implying nothing exited anywhere. Aggregate count only — no tickers.
                    try:
                        mrow = await db.execute(sa_text(
                            "SELECT COUNT(*) FROM tier_fills "
                            "WHERE tier = 'maximizer' AND side = 'sell' AND reason = 'hold_exit' "
                            "AND fill_date >= CURRENT_DATE - INTERVAL '7 days'"
                        ))
                        max_time_stops = mrow.scalar() or 0
                    except Exception as _e:
                        logger.warning(f"Could not load Maximizer time-stop count: {_e}")

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

        # Real closed-win block — TRUE figures the sections may cite (no fabrication).
        wins_block = ""
        if week_wins:
            def _fmt_win(w):
                pnl, days = w
                return f"+{pnl:.1f}%" + (f" ({days} days)" if days else "")
            wins_block = (
                "\nREAL CLOSED WINS THIS WEEK (exact, true figures from the core model book — you MAY "
                "cite ONE generically, e.g. 'one position the system exited this week locked in +X%', "
                "NEVER a ticker, NEVER a rounded/invented number): "
                + "; ".join(_fmt_win(w) for w in week_wins[:3]) + "\n"
            )

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
        market_summary += f"\nPreserver stops triggered this week: {stops_count} (trailing/loss/regime exits in the core Preserver book)."
        if profit_exits_count:
            market_summary += f"\nProfit exits this week: {profit_exits_count}."
        # Maximizer time-stops are a DIFFERENT thing from Preserver stops: a breakout position
        # is sold when it reaches its 29-day hold, whether up or down — a scheduled exit, not a
        # loss-cut. Report it as its own fact so the newsletter never conflates the two (and never
        # implies "nothing exited" when the Preserver stop count is 0 but the Maximizer book turned over).
        market_summary += (
            f"\nMaximizer time-stops this week: {max_time_stops} "
            f"(breakout positions that reached their 29-day hold and were sold on schedule — "
            f"this is a SCHEDULED exit on the clock, NOT a loss-cutting stop; describe it that way, "
            f"and NEVER call it a 'stop-loss' or imply the position was cut for going against us)."
        )
        # Real WEEKLY facts (regime-run length + week-over-week asset moves + biggest S&P day) so
        # §01 recaps the WEEK and never invents a regime-duration. Prefer these over the daily briefing.
        weekly_pack = self._weekly_market_pack()
        if weekly_pack:
            market_summary += f"\n\n{weekly_pack}"
        if market_context:
            # LATEST DAILY briefing — BACKDROP/TEXTURE ONLY. Its % moves are a single-day snapshot,
            # NOT the week: never present its day-specific figures as "this week." Weekly figures come
            # from the WEEKLY MARKET MOVES block above. COUNTS come only from the structured data above.
            market_summary += f"\n\nLATEST DAILY BRIEFING (backdrop/texture only — do NOT cite its single-day % moves as the week; use WEEKLY MARKET MOVES for weekly figures; never take a signal/position/stop COUNT from here): {market_context}"

        # Lead story: a PICKED queue topic wins (consumed/removed on slot), else the explicit
        # param, else the legacy S3 slot. A picked topic may carry verbatim text (body_preserved).
        picked = self._pop_topic(topic_id) if topic_id else None
        if picked:
            lead_story = picked.get("concept") or picked.get("title")
        else:
            lead_story = lead_story or self.get_pending_lead_story()
        lead_note = ""
        if lead_story:
            lead_note = (
                f"\n\nTHIS ISSUE HAS A LEAD STORY (set by Erik): {lead_story}\n"
                "Weave its theme into this section where it is natural to do so — "
                "the week's data is still the spine, but the lead story is the angle."
            )

        # §01 — The Week in Focus
        s1_prompt = f"""Write §01 "The Week in Focus" for this week's newsletter.

Market data:
{market_summary}{prev_week_context}{lead_note}

Write 2-3 paragraphs explaining what the system is seeing in plain English. Translate the regime and data into something a smart non-trader would understand. Don't just list numbers — interpret them. What does this regime mean for how the system is behaving?

THIS IS A WEEKLY RECAP — describe what happened over the WEEK, not just the latest day:
- Use the WEEKLY MARKET MOVES block (week-over-week % for the S&P, Nasdaq, small caps, gold, treasuries) and the "biggest single S&P day" for the week's action. Do NOT present a single-day figure from the daily briefing as if it were the week.
- REGIME DURATION: if you note how long the regime has run, state it ONLY using the REGIME RUN figure provided (e.g. "~16 weeks"). NEVER invent a count like "second week running" — a wrong duration is an instant credibility hit. If no REGIME RUN figure is given, don't state a duration at all.

You may reference: number of fresh signals, watchlist count, open positions, Preserver stops triggered, Maximizer time-stops, profit exits — but ONLY the exact numbers from the "Market data" block above, and the S&P move + VIX. Do NOT make up any numbers. If the data says 1 stop, say 1; if 0, say 0. TWO DIFFERENT EXIT TYPES: "Preserver stops" are trailing/loss/regime exits in the core book; "Maximizer time-stops" are breakout positions sold on reaching their 29-day hold (a scheduled exit on the clock, not a loss-cut). Keep them distinct — if Preserver stops are 0 but Maximizer time-stops are >0, say so plainly (nothing was stopped out for losing, but the breakout book turned over on schedule); never let "0 stops" imply the whole engine was idle.

HARD NUMBER DISCIPLINE (this is where trust is won or lost):
- COUNTS are authoritative ONLY from the structured data (fresh signals, watchlist, open positions, stops). NEVER take a count from the MARKET COLOR briefing, and NEVER invent a prior-week comparison ("up from 9 to 14") — you are not given last week's counts.
- WEEKLY FIGURES come from the WEEKLY MARKET MOVES block (real week-over-week %) — cite those for "this week." The LATEST DAILY BRIEFING is a single-day snapshot: use it only for narrative backdrop, and NEVER present its day-specific % (e.g. "gold up 2%") as the week's move. Do NOT invent any figure that isn't in these blocks, and never describe an individual holding by a specific industry ("a ride-hailing name") — the counts are all we know about the book's composition.
- WHICH BOOK: the position/signal counts describe the CORE model book. Maximizer runs a SEPARATE breakout book with its own holdings — do NOT imply the core counts ("20 positions", "these 8 signals") are Maximizer's. When you contrast the two settings, keep Maximizer's behavior conceptual (hunts breakouts, holds on a clock, sells on a hard exit) unless given its own numbers.

CRITICAL: Do NOT use any specific ticker symbols anywhere (no AAPL, NVDA, RIOT, etc.). This newsletter goes to free readers. Refer to stocks generically: "a name," "one position," "a tech stock." Subscribers who want tickers get them in the daily digest.

IMPORTANT: Output ONLY the body paragraphs. Do NOT include any section header, title, number, or label like "§01" or "The Week in Focus" — those are added separately.

150-250 words."""

        s1_text = self._clean_body(self._call_claude(s1_prompt))

        # §02 — One Idea, Explained
        if lead_story:
            topic = {"slug": "lead-story",
                     "title": (picked.get("title") if picked else None) or "This week's lead story.",
                     "seed": lead_story + "\n\n(Also propose nothing about topics outside this lead story — this section IS the lead story this week.)"}
        else:
            topic = self._get_topic_for_week(target_date)
        s2_prompt = f"""Write §02 "One Idea, Explained" about this topic:

Title: {topic['title']}
Concept to explain: {topic['seed']}

Write 2-3 paragraphs explaining this concept to a smart person who isn't a quant. Use a concrete example or thought experiment. Make it genuinely educational — this is the section that makes readers smarter, which is why they stay subscribed.

CRITICAL: This section is purely educational. Do NOT reference any specific trades, positions, stops, tickers, or events from this week. Do NOT make up specific numbers about what the system did or didn't do. Teach the concept abstractly with hypothetical examples only.

IMPORTANT: Output ONLY the body paragraphs. Do NOT include any section header, title, number, or label — those are added separately.

200-300 words."""

        # Verbatim reuse when the picked topic carries preserved text; else regenerate from concept.
        if picked and picked.get("body_preserved"):
            s2_text = self._clean_body(picked["body_preserved"])
        else:
            s2_text = self._clean_body(self._call_claude(s2_prompt))

        # §03 — What the System is Not Doing
        s3_prompt = f"""Write §03 "What the System is Not Doing" for this week.

THIS IS THE MOST IMPORTANT SECTION. It builds trust by naming things we're explicitly sitting out.

Market context:
{market_summary}

Based on the current regime and market conditions, write EXACTLY 3 items — things the system is NOT doing right now, and why.

TIER BALANCE (required): we run TWO settings — Preserver (protect) and Maximizer (grow, a breakout book). AT LEAST ONE of the 3 items MUST be about the Maximizer/breakout side, so the section never reads Preserver-only. A good mix is 2 Preserver-side + 1 Maximizer-side. Keep Maximizer behavior CONCEPTUAL (it hunts breakouts, holds on a 29-day clock, sells on a hard time-stop, throttles exposure with a volatility target) — do NOT attach the core book's position/signal counts to it. EXCEPTION — the ONE Maximizer number you MAY cite is "Maximizer time-stops this week" from the Market context block: if it is >0, you may ground the Maximizer item in it (e.g. "a few breakout positions reached their 29-day exit and were sold on the clock"), framed as a scheduled exit that keeps a winner from round-tripping — never as a loss-cut, never with tickers.

Format: Wrap the ENTIRE first sentence of each item in **...** (the whole sentence bold, not just a lead-in phrase), then 1-2 more sentences unbolded. Example:
**The system isn't chasing the extended tech names this week.** The momentum scores have diverged from price in ways that historically precede pullbacks. We might miss more upside. That's fine.

Choose from ideas like —
Preserver side: not chasing a hot sector; not shorting (long-only by design); not touching small caps (volume/price filters); not adding into a weakening regime; not panic-selling despite headlines; not following the crowd into a popular trade.
Maximizer side: not forcing breakout entries when the regime isn't rewarding them; not white-knuckling a breakout past its 29-day time-stop hoping for more; not doubling down when volatility spikes (the vol-target trims exposure instead); not chasing a breakout that's already extended far past its trigger.

CRITICAL RULES:
- Output EXACTLY 3 items, each starting with **bold text.**
- AT LEAST ONE of the 3 items must be about the Maximizer/breakout side (see TIER BALANCE above). Never all-Preserver.
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
        # Rotated themes so the note doesn't drift back to "system doing less,
        # not more" every week. Pick by ISO week so the cycle is predictable
        # and recoverable across months. Prior-week's §04 is also passed in as
        # an anti-pattern to actively avoid.
        from datetime import date as _date
        s4_themes = [
            {
                "name": "the_craft",
                "guidance": "Reflect on a small craft / engineering decision in building the system — e.g., a metric you chose to optimize for, a tradeoff you made, an assumption you discarded. Concrete, not abstract.",
            },
            {
                "name": "founder_life",
                "guidance": "Something about building this solo. A small moment from the week — a piece of feedback, a bug hunt, a long Saturday at the keyboard. Human, specific, not motivational.",
            },
            {
                "name": "market_moment",
                "guidance": "React to something specific that happened in the market this week — a regime shift, an unusual signal pattern, a stock that moved against the system. Show the system reasoning, don't editorialize the news.",
            },
            {
                "name": "week_in_world",
                "guidance": "Tie to a notable current event from this week's headlines if any is genuinely relevant to investing mindset. If nothing fits, default to a craft or founder-life note. Never force a stretched analogy.",
            },
            {
                "name": "community",
                "guidance": "Reference reader feedback, a recurring question, or pose one back to the audience. Invites replies more directly. (Don't fabricate specific quotes — speak to the pattern of questions, not invented exchanges.)",
            },
            {
                "name": "philosophy",
                "guidance": "A lens on discipline, patience, or process — but anchored to a SPECIFIC example from this week's data or your day. Not abstract platitudes; not 'doing less, not more' (overused).",
            },
        ]
        week_idx = target_date.isocalendar()[1] % len(s4_themes)
        theme = s4_themes[week_idx]

        # Pull last week's §04 text to instruct Claude not to repeat its theme
        prev_s4_text = ""
        try:
            prev_date2 = target_date - timedelta(days=7)
            prev_draft2 = self.get_draft(prev_date2.strftime("%Y-%m-%d"))
            if prev_draft2 and prev_draft2.get("sections"):
                # Sections list is ordered; §04 is last
                for sec in prev_draft2["sections"]:
                    if sec.get("num") == "04":
                        prev_s4_text = (sec.get("body") or "")[:400]
                        break
        except Exception:
            pass

        # Pull top headlines via Google News RSS — same source the dashboard
        # AI briefing uses. Best-effort; an empty list is fine.
        headlines_lines = []
        try:
            import httpx as _httpx
            import xml.etree.ElementTree as _ET
            resp = _httpx.get(
                "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
                timeout=3, follow_redirects=True,
            )
            if resp.status_code == 200:
                root = _ET.fromstring(resp.text)
                for item in root.findall(".//item")[:5]:
                    title = item.findtext("title", "")
                    if title:
                        headlines_lines.append(title)
        except Exception:
            pass
        headlines_block = ""
        if headlines_lines:
            headlines_block = "\nThis week's top US headlines (use only if naturally relevant):\n" + "\n".join(f"- {h}" for h in headlines_lines) + "\n"

        prev_s4_block = ""
        if prev_s4_text:
            prev_s4_block = (
                f'\nTHE TRAP — last week\'s §04 fell into a recurring pattern that we are TRYING TO BREAK OUT OF:\n'
                f'"""{prev_s4_text}"""\n'
                f'Your job is NOT to echo this. Write something that has nothing in common with it.\n'
            )

        s4_prompt = f"""Write §04 "A Note From Erik" — the founder signoff.

THIS WEEK'S THEME (mandatory — stay on this theme, do not drift):
{theme['name'].upper()}: {theme['guidance']}
{prev_s4_block}{headlines_block}{wins_block}
HARD RULES:
- 2-3 sentences. 50 words max.
- NO INVENTED TRADES. Your ONLY real trade facts are in a "REAL CLOSED WINS THIS WEEK" block if one is present above. You MAY cite ONE of those wins generically (no ticker, exact %, e.g. "one position the system exited this week locked in +18%") — it's a true figure and a great concrete note. If NO wins block is present, do NOT reference any specific trade, stock move, day, or named position ("a tech stock jumped 20% Wednesday," "a stock we sold tore higher") — stay on craft, a principle, or the week's regime in the aggregate. Never fabricate or round a number.
- Personal, informal, not pitch-y. Invite replies. Don't be cheesy or motivational.
- BANNED themes (these have been overused — DO NOT touch them this week):
  * "waiting / not acting / sitting on hands / watching the data"
  * "doing less, not more"
  * "discipline looks boring from the outside"
  * "second-guessing yourself"
  * The market being "exhausting" or making you "tired"
- BANNED words/phrases this week: "waiting", "not acting", "doing less", "sitting", "exhausting", "exhausted", "second-guessing", "spinning wheels", "discipline looks boring"
- Write ONLY about this week's assigned theme. If you can't think of something theme-specific, write about a concrete object/decision/moment (not an abstract feeling).

End with "See you next Sunday." on its own line.

IMPORTANT: Output ONLY the personal note text. Do NOT include any section header, title, number, or label. Do NOT start with "A Note From Erik" or similar — just the note itself."""

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

        if lead_story:
            self._consume_lead_story(date_str)

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

        # Lock = frozen/ready-to-send, NOT public (Jun 13 2026). Locking used
        # to also write to issues/ — the public archive — so a Saturday lock
        # went live before Sunday's send + before final review. Public publish
        # now happens at send time via publish_issue() (Sunday email cron).
        logger.warning(f"Newsletter draft locked for {date_str} (not yet public)")
        return draft

    def publish_issue(self, date_str: str) -> dict:
        """Publish a (locked) draft to the public web archive. Called by the
        Sunday email-send cron AFTER the email goes out, so the public page and
        the email appear together, never before review/send."""
        draft = self.get_draft(date_str)
        if not draft:
            raise ValueError(f"No draft to publish for {date_str}")
        self.s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{ISSUE_KEY_PREFIX}{date_str}.json",
            Body=json.dumps(draft).encode(),
            ContentType="application/json",
        )
        logger.warning(f"Newsletter issue published to public archive: {date_str}")
        return draft


newsletter_generator = NewsletterGeneratorService()
