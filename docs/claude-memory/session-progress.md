---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — Core-purge: Landing/TrackRecord+chart/ForAdvisers/Methodology/Social ALL done. NEXT: EMAIL templates (Core-heavy!).

## ✅ CANONICAL NUMBERS (one basis, all public): 21yr: **Preserver 8.6%/0.88/−13%** · **Maximizer 14.5%/0.95/−20%** vs S&P 9.8%(price)/−55%, raw-mom 13.2%/−57%. $100k→Pres $500k, Max $1.39M, SPY $535k(price-only). Recent 2yr (tier_vintages_daily.py AUTHORITATIVE): **Preserver 31.3%/1.75/2.43/−12.9%** · **Maximizer 48.9%/1.94/2.83/−17.3%** = landing dial 31/49 (CORRECT). Preserver adviser: down-mo −0.9%/up-mo +1.6%/corr 0.51/5-of-6-worst-months-in-cash. Rolling-win-vs-S&P: Pres 37/23/16% (1/3/5y), Max 54/51/48%. Recovery Pres 2.0yr vs SPY 5.4.

## ✅ DONE (all uncommitted, dev :5173): Landing (LandingPageV2), TrackRecord (TrackRecordPageV2 + **TierRaceChart.jsx** — Preserve/Both/Maximize hide-not-dim, 3 era-bands+dashed defensive+flags, thin lines, SPY price-only $535k [grid stat also fixed 763→535], animation StrictMode-fixed), ForAdvisers (Preserver-led sleeve, hero subhead reworked off survivorship-jargon, recent 2yr rows added back), Methodology (premium para reframed 2-tier, tildes gone). Data /public/track-record-curves.json (curves+defensive+events+annual).

## ✅ SOCIAL ENGINE (backend/app/services/ai_content_service.py): SYSTEM_PROMPT rewritten (2-tier product + CANONICAL NUMBERS guardrail + walk-forward-not-backtest + tighter voice); INSIGHT_SEEDS + CANON_LESSONS → tier numbers; inline "backtest" instrs → walk-forward. **MODEL claude-sonnet-4-6 is CORRECT** (Erik confirms = last prod Sonnet; DB shows 88 working gens — my "invalid" hypothesis was WRONG, reverted). "Not vibing" = genuine voice, prompt rework targets it. Can't test locally (API key Lambda-only). social_content_service.py template fallback = clean.

## 🔜 NEXT (Erik asked, offered): **EMAIL templates (email_service.py) — Core-HEAVY**: welcome/trial-drip/"what you bought" emails cite 8.3%/19%/0.5%-in-2008/"Backtested Return 8.3%" + "backtest" everywhere (lines ~1542-1953). Daily digest (generate_daily_summary_html:256) = mostly signal-list, lighter. Daily scan's SOCIAL uses ai_content_service (this voice); email digest = separate templates. Same purge needed.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; no tildes on numbers; claret+paper; tables "RigaCap Preserver/Maximizer". GATE: no tier CHARGES until Maximizer signals live. Commit only when asked (merge research→main). vite :5173 alive.
