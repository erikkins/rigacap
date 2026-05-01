"""
Trade Autopsy Service — AI-powered post-mortem analysis for closed trades.

Uses Claude API to generate forensic analysis of what went right/wrong
on each model portfolio trade.
"""

import json
import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.core.database import ModelPosition

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a quantitative trading analyst writing post-mortems for an ensemble momentum/DWAP trading system.

The system uses:
- DWAP (Daily Weighted Average Price) timing: entry when price > DWAP x 1.05
- Momentum ranking: 10-day/60-day composite score
- 7-regime market detection (strong_bull, weak_bull, rotating_bull, range_bound, weak_bear, panic_crash, recovery)
- 12% trailing stop from high water mark
- Biweekly rebalancing with force-close at period boundaries

Analyze the trade data provided and return a JSON object with these fields:
- verdict: one of "good_entry", "bad_entry", "good_exit", "bad_exit", "unlucky" (where system rules were correct but market moved against)
- entry_analysis: 1-2 sentences on entry timing quality
- exit_analysis: 1-2 sentences on exit execution quality
- regime_impact: 1 sentence on how market regime affected this trade
- lesson_learned: 1 actionable insight for improving the system
- score: integer 1-10 (10 = perfect trade execution)

Return ONLY valid JSON, no markdown, no code fences."""


class TradeAutopsyService:
    """Generate AI-powered trade post-mortems."""

    def __init__(self):
        self.enabled = bool(settings.ANTHROPIC_API_KEY)
        if not self.enabled:
            logger.warning("Trade autopsy service disabled - ANTHROPIC_API_KEY not configured")

    async def generate_autopsy(self, db: AsyncSession, position_id: int) -> dict:
        """Generate an AI autopsy for a single closed trade."""
        result = await db.execute(
            select(ModelPosition).where(ModelPosition.id == position_id)
        )
        pos = result.scalar_one_or_none()
        if not pos:
            return {"error": "Position not found"}
        if pos.status != "closed":
            return {"error": "Position is still open"}

        if not self.enabled:
            return {"error": "AI service not configured"}

        # Parse signal data
        sig = {}
        if pos.signal_data_json:
            try:
                sig = json.loads(pos.signal_data_json)
            except (json.JSONDecodeError, TypeError):
                pass

        # Build context for Claude
        days_held = 0
        if pos.entry_date and pos.exit_date:
            days_held = (pos.exit_date - pos.entry_date).days

        max_gain_pct = None
        if pos.highest_price and pos.entry_price:
            max_gain_pct = round(((pos.highest_price / pos.entry_price) - 1) * 100, 2)

        trade_context = {
            "symbol": pos.symbol,
            "portfolio_type": pos.portfolio_type,
            "entry_date": pos.entry_date.strftime("%Y-%m-%d") if pos.entry_date else "",
            "exit_date": pos.exit_date.strftime("%Y-%m-%d") if pos.exit_date else "",
            "entry_price": pos.entry_price,
            "exit_price": pos.exit_price,
            "pnl_pct": pos.pnl_pct,
            "pnl_dollars": pos.pnl_dollars,
            "exit_reason": pos.exit_reason,
            "days_held": days_held,
            "highest_price": pos.highest_price,
            "max_gain_pct": max_gain_pct,
            "ensemble_score": sig.get("ensemble_score"),
            "momentum_rank": sig.get("momentum_rank"),
            "pct_above_dwap": sig.get("pct_above_dwap"),
            "sector": sig.get("sector"),
            "short_momentum": sig.get("short_momentum"),
            "long_momentum": sig.get("long_momentum"),
            "volatility": sig.get("volatility"),
        }

        user_prompt = (
            f"Analyze this closed trade and return a JSON post-mortem:\n\n"
            f"{json.dumps(trade_context, indent=2)}"
        )

        try:
            text = await self._call_claude(user_prompt)
            if not text:
                return {"error": "AI returned empty response"}

            # Strip code fences if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            autopsy = json.loads(text)

            # Store in DB
            pos.autopsy_json = json.dumps(autopsy)
            await db.commit()

            return autopsy

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse autopsy JSON for {pos.symbol}: {e}")
            return {"error": f"Failed to parse AI response: {e}"}
        except Exception as e:
            logger.error(f"Autopsy generation failed for {pos.symbol}: {e}")
            return {"error": str(e)}

    async def get_autopsy(self, db: AsyncSession, position_id: int) -> Optional[dict]:
        """Return parsed autopsy for a position, or None."""
        result = await db.execute(
            select(ModelPosition).where(ModelPosition.id == position_id)
        )
        pos = result.scalar_one_or_none()
        if not pos or not pos.autopsy_json:
            return None
        try:
            return json.loads(pos.autopsy_json)
        except (json.JSONDecodeError, TypeError):
            return None

    async def bulk_generate(
        self, db: AsyncSession, portfolio_type: Optional[str] = None, limit: int = 20
    ) -> dict:
        """Generate autopsies for all closed trades that don't have one yet."""
        query = select(ModelPosition).where(
            ModelPosition.status == "closed",
            ModelPosition.autopsy_json.is_(None),
        )
        if portfolio_type:
            query = query.where(ModelPosition.portfolio_type == portfolio_type)
        query = query.order_by(ModelPosition.exit_date.desc()).limit(limit)

        result = await db.execute(query)
        positions = list(result.scalars().all())

        generated = 0
        errors = 0
        for pos in positions:
            autopsy = await self.generate_autopsy(db, pos.id)
            if "error" in autopsy:
                errors += 1
                logger.warning(f"Autopsy error for {pos.symbol} (id={pos.id}): {autopsy['error']}")
            else:
                generated += 1

        return {
            "generated": generated,
            "errors": errors,
            "total_candidates": len(positions),
        }

    async def _call_claude(self, user_prompt: str) -> Optional[str]:
        """Make a Claude API call."""
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
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


# Singleton
trade_autopsy_service = TradeAutopsyService()
