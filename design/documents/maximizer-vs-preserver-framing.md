# Maximizer vs Preserver — Positioning Framing (DRAFT, internal)

*Status: strategy draft, Jul 2026. t30v (base) is LIVE; the Preserver (v1) and
Maximizer (v2) regime-routed tiers are RESEARCH-stage — all tier numbers are backtest,
validated cross-half + EXT holdout + daily-DD + walk-forward + independent-proxy crash
defense. Behavior-level only — never publish the mechanics (regime routing / shape /
vol-scaling logic). "Survivorship-free" stays out of customer copy (table stakes).*

## Naming (LOCKED Jul 7)
Customer-facing names: **Preserver** (base tier) · **Core** (the engine, under both tiers) ·
**Maximizer** (aggressive add-on). Internal-only, NEVER customer-facing: **`t30v`** (the Core
engine's research code) and **`Maximizer++`** (retired). Treat `t30v` like the recipe — internal
docs/code may use it; it must never appear in any public copy, graphic, or email. Trademark-check
"Maximizer" before public use (may need the "RigaCap Maximizer" lockup).

## The core idea: one engine, a 2-tier product (base + aggressive add-on)

Our earlier positioning work (the analyst dialogue) landed on a hard truth: the *same*
product grades **F for the "Market Maximizer" and A for the "Capital Preserver."**
Marketing's job was **filtration, not conversion.**

The regime research lets us ship the *right* product to each persona from **one engine**,
as **two tiers**:

| | **BASE — Preserver** (flagship) | **ADD-ON — Maximizer** |
|---|---|---|
| For | capital-preservers, $250k+, advisers | aggressive growth, risk-tolerant |
| Daily backtest — **last 2yr** | **31% / 1.75 / −13% DD** | **49% / 1.94 / −17% DD** |
| Daily backtest — 2021–26 (incl 2022) | 19% / 1.33 / −13% DD | 36% / 1.61 / −20% DD |
| Job | keep drawdown low, all-weather | max return, crash-defended |
| Risk owned | least — no factor-crash exposure | **momentum-crash tail** (tamed, not gone) |
| One-liner | "behavioral capital insurance" | "offense with a seatbelt" |

**BASE = Preserver:** the t30v momentum engine **+ regime-adaptive defense.** It runs the
proven Core strategy ~70% of the time (rotating-bull) and overlays defensive sleeves in
calm-bull and capitulation regimes — keeping upside while roughly *halving* the drawdown in
turbulence. On-brand: capital preservation.

**ADD-ON = Maximizer:** the same engine, but it routes the dominant regime to a
higher-return breakout engine wrapped in a momentum-crash volatility brake (below).

Under both sits **Core (t30v)** — the live, **20-year-track-record** engine (canonical
8.3% ann / 0.73 / 19% MaxDD, 2007–26). It's **not a separate product; it's the proof and
the foundation** both tiers run on. Over history and in turbulence **Preserver ≥ Core**
(Core only wins calm melt-ups) — so Preserver is the honest new default, and Core stays as
the proven record we *lead with* for credibility.

### Packaging & pricing (decided direction)
- **Base (Preserver):** the flagship subscription — **$129/mo standard, $1,099/yr.**
- **Maximizer:** a **paid add-on** (leaning; give it a distinct sub-brand name for a brand
  firewall), **~+$100–120/mo → aggressive tier ≈ $229–249/mo (~$2–2.5k/yr).** The paywall
  does double duty: it **monetizes** higher willingness-to-pay *and* **filters out
  risk-intolerant users** (the whole reason to gate it).
  - *Fee-drag check:* $249/mo ≈ 1.0–1.2% on $250k, 0.6% on $500k — at the ~1% psych ceiling.
  - *Go a fully SEPARATE product* instead of an add-on **only if** the aggressive audience is
    a different persona than the $250k+ preserver base (then it needs its own funnel).
  - ⚠️ **Price on the DURABLE ~+7pp/yr incremental over Preserver — NOT the 49% recent peak.**

### The Maximizer momentum-crash control (why the aggressive tier is investable)
The breakout engine earns ~30% but carries a **momentum-crash** tail (the 2021 factor
unwind: −32% — invisible to any market/VIX signal, because the index stayed healthy while
leadership crashed). We tame it *mechanically*, no curve-fitting: scale exposure down when
the **momentum factor's own realized volatility** spikes (it hit ~50% vs ~17–29% normal
into 2021 — a bright, independent warning light). Validated with an *independent* momentum
factor, not just self-reference. Effect: **halves the crash (−32% → ~−20 to −26%), lifts
Sharpe, costs ~4–6 pts of CAGR.** This is what makes Maximizer a defensible product
rather than a coin-flip. (Note: crash is *reduced*, not eliminated — momentum risk is
partly irreducible; that honesty is part of the tier's pitch.)

## Lead with the RECENT record, not the 20-year

Rule (Erik): *the future rhymes with the recent past* — so the **last ~2 years** is the
headline for the pitch. The 20-year, positive-every-window record is **research
credibility** (proof it's not curve-fit), not the sales number. Order the story:
**recent headline → risk behavior → then "and it holds up over 20 years."**

### The Maximizer — headline (backtest)
- **Last 2 years: ~37% annualized, Sharpe ~1.9, worst drawdown ~−15%.**
- 20-yr research: positive in every rolling window, disciplined risk.
- Pitch: *"When momentum is working, we're all the way in. The last two years show what
  that looks like."*

### The Preserver — headline (backtest)
- **Last 2 years: ~32% annualized, Sharpe ~1.8, worst drawdown ~−13%.**
- **Its signature is turbulence:** across 2021–26 (which *included* the 2022 bear) it cut
  the *daily* worst drawdown from ~−24% to ~−13% — **nearly in half** — while *raising*
  return (Sharpe 1.09 → 1.32). That's the whole product in one line.
- Pitch: *"You barely give up anything in the good years — and when the market breaks,
  you lose half as much. That gap is the product."*

## The honest catch (say it out loud — it's a feature)

The Preserver's edge **needs turbulence to pay off.** In a smooth, low-volatility
melt-up (like the last ~2 years in isolation), the Maximizer actually *edges it* on
return — you pay a small premium for protection you didn't end up needing. That honesty
IS the pitch: it's **insurance.** You don't resent your insurance in a year the house
didn't burn down. Frame the small calm-market give-up as the premium; frame 2022-style
drawdown-halving as the payout.

## Messaging principles
- **Filtration → self-selection.** Present the dial; let the persona pick their tier. Don't
  sell a Preserver a Maximizer or vice versa — mismatched customers churn.
- **Recent numbers first, 20-year for credibility.**
- **Honesty about the trade-off** is the differentiator, not a liability (capital-
  preservers trust the shop that tells them the cost; and Maximizer buyers must be told
  they own momentum-crash risk, tamed but not gone).
- **Never the recipe.** Behavior and outcomes only — no shape/regime/vol-scaling mechanics
  in public.
- Reusable brand language (canon): "behavioral capital insurance," "Anti-Capitulation
  Engine," "structurally buying a put option on the market; the premium is paid in
  bull-run underperformance."

## Open / to-do
- Productionize the allocator + vol-scaling before Preserver / Maximizer can be *sold*
  (currently research; t30v base is the only live tier).
- Decide packaging: three tiers/toggles of one subscription, or separate products?
- Pull final, locked backtest numbers (daily, walk-forward-faithful) for any public use.
- Legal/compliance review of any performance claims (backtest disclaimers).
- (Research follow-up) TOPD independent crash-proxy validated; if productionized, prefer it
  over self-vol (reusable across sleeves) and calibrate the vol target for the CAGR/crash
  trade the tier wants.
