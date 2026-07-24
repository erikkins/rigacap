// RegimeTell — the "meat chip" done honestly: an EXPECTATION-SETTER, not a trade signal.
// Given the current 7-regime label (already served in dashboard.regime_forecast.current_regime),
// it tells subscribers what to EXPECT of their tier vs the index right now — so a normal
// short-term lag (like a rotating-bull July) reads as designed behavior, not a reason to bail.
// Deliberately NOT actionable ("stay invested" / "get out") — timing the strategy in/out is
// the exact panic behavior the product protects against. Sets expectations, then trust the system.
import React from 'react';

// tone: 'neutral' (track/lag the index — the edge is quiet), 'defensive' (lose less than index),
// 'engage' (participate as it confirms). Drives the accent color.
const REGIME = {
  strong_bull:  { name: 'Strong Bull',   tone: 'neutral',   expect: 'Broad rally. Fully invested and keeping pace — the strategy won’t chase a melt-up, so brief lags vs the index are normal.' },
  weak_bull:    { name: 'Weak Bull',      tone: 'neutral',   expect: 'Narrow, advancing market. Invested in the leaders; expect to roughly track the index, with the edge showing over the cycle.' },
  rotating_bull:{ name: 'Rotating Bull',  tone: 'neutral',   expect: 'Choppy sector rotation — the quiet regime for the edge. Expect to track or modestly lag the index short-term; it shows up over full cycles, not week to week.' },
  range_bound:  { name: 'Range Bound',    tone: 'neutral',   expect: 'Directionless market. Expect modest, index-like returns while the strategy holds quality and waits. Sideways stretches are normal.' },
  weak_bear:    { name: 'Weak Bear',      tone: 'defensive', expect: 'Market weakening — the strategy is de-risking. Expect it to give back less than the index from here. This is where preservation starts to matter.' },
  panic_crash:  { name: 'Panic / Crash',  tone: 'defensive', expect: 'Sharp selloff — defensive and raising cash. Expect to lose meaningfully less than the index; the point is not being fully exposed to the drop.' },
  recovery:     { name: 'Recovery',       tone: 'engage',    expect: 'Rebounding off lows — re-engaging as conditions confirm. Expect to participate as the recovery proves itself, not to call the exact bottom.' },
};

// Tier-specific nuance appended to the regime line.
const TIER_NUANCE = {
  maximizer: {
    neutral:   'As the aggressive tier, expect bigger swings both ways; the vol-target trims exposure automatically when volatility spikes.',
    defensive: 'The vol-target is cutting exposure automatically — aggressive tiers fall hardest without it; this is that brake working.',
    engage:    'Aggressive re-engagement can be sharp; the vol-target scales exposure back up as vol settles.',
  },
  preserver: {
    neutral:   'As the preservation tier, tracking the index here is by design — your edge is the downside protection that shows up in the next drawdown.',
    defensive: 'This is exactly what you’re paying for: the defensive overlay raises cash to cushion the drawdown.',
    engage:    'The overlay eases back to full exposure as the recovery confirms — gradually, not on a hunch.',
  },
};

const ACCENT = { neutral: 'border-ink-light', defensive: 'border-claret', engage: 'border-rule-dark' };

export default function RegimeTell({ regime, tier = 'core' }) {
  const r = REGIME[regime];
  if (!r) return null;
  const nuance = (TIER_NUANCE[tier] || {})[r.tone];
  return (
    <div className={`mt-2 p-3 rounded bg-paper-card border-l-2 ${ACCENT[r.tone]} border-y border-r border-rule`}>
      <div className="text-[11px] uppercase tracking-wide text-ink-light mb-1">
        What to expect from your strategy · {r.name}
      </div>
      <p className="text-sm text-ink leading-snug">{r.expect}</p>
      {nuance && <p className="text-xs text-ink-mute leading-snug mt-1.5">{nuance}</p>}
      <p className="text-[11px] text-ink-light italic mt-2">
        Built to beat the market over full cycles — not every month. Short-term lag vs the index is expected, not a problem.
      </p>
    </div>
  );
}
