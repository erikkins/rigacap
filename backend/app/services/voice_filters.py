"""Brand-voice filter for AI-generated user-facing text.

Single source of truth for terms banned by:
  - `MarketingNewsletterStrategyCLAUDE.md` §11 Forbidden Phrases
  - `feedback_no_tape.md` (no trader jargon)
  - `feedback_no_dwap_in_public.md` (proprietary indicator, never name in prose)

Wraps Claude calls in engagement_service / reply_scanner_service /
ai_content_service so the negative instruction is *enforced*, not just *asked
for*. Negative prompts are unreliable — Haiku 4.5 in particular leaks "tape"
and "AI-powered" despite explicit prohibition. Verification + retry is the
fix.

Usage:
    from app.services.voice_filters import contains_banned, generate_with_voice_filter

    # one-shot check
    found = contains_banned(draft_text)
    if found:
        # regenerate or fall back

    # convenience wrapper around an LLM call
    result = generate_with_voice_filter(call_fn, max_retries=2)
"""

from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Banned vocabulary
# ----------------------------------------------------------------------------

# Word-boundary single-token bans. Case-insensitive, exact-word matches only
# (won't false-positive on "tapestry", "lifestyle", etc.).
WORD_BANS: dict[str, str] = {
    # Trader jargon — feedback_no_tape.md
    "tape":         "trader-jargon (banned per voice doc)",
    "printing":     "trader-jargon",
    "ripping":      "trader-jargon",
    "lfg":          "fanboy / crypto-speak",
    "moon":         "crypto / meme-speak",
    # SaaS-startup vocabulary — strategy doc §11
    "autonomous":   "forbidden phrase",
    "guaranteed":   "forbidden phrase (also legal risk)",
    "unlock":       "SaaS-speak",
    # Proprietary — feedback_no_dwap_in_public.md
    "dwap":         "proprietary indicator, never name in public prose",
}

# Multi-word phrase bans (substring match, case-insensitive)
PHRASE_BANS: dict[str, str] = {
    "ai-powered":            "forbidden phrase",
    "ai powered":            "forbidden phrase",
    "hedge fund returns":    "forbidden phrase",
    "game-changing":         "forbidden phrase",
    "game changing":         "forbidden phrase",
    "crush the market":      "forbidden phrase",
    "join thousands":        "forbidden phrase",
    "diamond hands":         "crypto / meme-speak",
}


def contains_banned(text: str) -> List[Tuple[str, str]]:
    """Return [(term, reason), ...] for every banned word/phrase found in text.

    Empty list = clean. Case-insensitive throughout.
    """
    if not text:
        return []
    lc = text.lower()
    found: List[Tuple[str, str]] = []

    for word, reason in WORD_BANS.items():
        # word-boundary so "tape" matches but "tapestry" does not
        if re.search(rf"\b{re.escape(word)}\b", lc):
            found.append((word, reason))

    for phrase, reason in PHRASE_BANS.items():
        if phrase in lc:
            found.append((phrase, reason))

    return found


def is_clean(text: str) -> bool:
    """Convenience: True if text has no banned words/phrases."""
    return not contains_banned(text)


def banned_summary_for_prompt() -> str:
    """A human-readable list suitable for injecting into a Claude system prompt.

    Use this so the prompt and the post-filter stay in sync — single source.
    """
    words = ", ".join(f'"{w}"' for w in WORD_BANS)
    phrases = ", ".join(f'"{p}"' for p in PHRASE_BANS if " " in p or "-" in p)
    return (
        f"BANNED WORDS (never use, even if mirroring user's text): {words}. "
        f"BANNED PHRASES: {phrases}."
    )


def generate_with_voice_filter(
    call_fn: Callable[[Optional[str]], Optional[str]],
    max_retries: int = 2,
    label: str = "voice",
) -> Optional[str]:
    """Call `call_fn(extra_directive)` until the output is voice-clean or retries exhausted.

    `call_fn` should accept an optional extra directive string (None on first
    attempt; a stronger reminder on retries) and return the model's text or
    None on failure.

    Returns the clean text, or None if all attempts contained banned terms /
    failed.
    """
    extra: Optional[str] = None
    for attempt in range(max_retries + 1):
        text = call_fn(extra)
        if not text:
            return None
        found = contains_banned(text)
        if not found:
            return text
        terms = ", ".join(t for t, _ in found)
        logger.warning(f"[{label}] attempt {attempt + 1}: voice violation — banned terms: {terms}")
        if attempt < max_retries:
            extra = (
                f"YOUR PRIOR DRAFT CONTAINED BANNED WORDS/PHRASES ({terms}). "
                f"Regenerate WITHOUT using any of: {', '.join(WORD_BANS)}, "
                f"{', '.join(PHRASE_BANS)}. Find different words. Do not paraphrase by adding 'so-called' or quotes — just don't use them."
            )
    logger.warning(f"[{label}] all {max_retries + 1} attempts failed voice filter; returning None")
    return None
