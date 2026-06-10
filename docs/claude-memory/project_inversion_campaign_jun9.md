---
name: inversion-campaign-jun9
description: "Jun 9 2026 — Inversion campaign (naive momentum + minimal defense) REFUTED: 17 variants, none got daily MDD under 40%. Naive's TRUE daily MDD is −52% (race JSON's −30% is monthly-sampling artifact). t30v's 17.9% through the same 2021-23 factor unwind = the gate conjunction is the moat. Behavioral sim: t30v beats panic-SPY in every scenario, does NOT beat panic-naive. t30v-side ablation launched."
metadata: 
  node_type: memory
  type: project
  originSessionId: 701a2e93-33c0-4e85-a7bc-2cb9d9956d94
---

# Inversion campaign (Jun 9 2026) — can naive momentum (28.8% CAGR) be defended cheaply? NO.

Follow-on to [[jun9-strategy-reckoning-and-launch]]. Erik's call: keep the 14% window-mean copy live for now (low traffic; 10% continuous "too far from North Star for me"), run the research. North Star 20/20/1.0/1.0 still locked.

**Harness:** `scripts/inversion_campaign.py` — daily-resolution sim on PITFWU parquet (veneer universe/split-adjusted/delistings), continuous 2017→2026 lens, real turnover, net@10/20bps. Pre-registered params (trail30=t30v, DD-tighten 15→8=May 22, 200MA=literature). Results: `scripts/inversion_results.json` (17 variants, checkpointed). Run under `backend/venv/bin/python` + `AWS_PROFILE=rigacap` (system python lacks aiohttp). Bars disk-cached at `~/.cache/pitfwu_close/`.

## The two headline discoveries
1. **Naive momentum's TRUE daily MDD is −52% to −55%, not the −30% in portfolio-race.json.** The race's naive curve is monthly-resolution (one point per rebalance) and missed the Jan-29-2021 intra-month blowoff peak and the 2.5-yr unwind trough (Oct 26 2023). Race JSON + the animation MUST be rebuilt at daily resolution — current published comparison is too KIND to naive. (Race CAGR validated: my A_base 29.9% vs race 28.8% ✓.)
2. **The 2021-23 momentum-factor unwind is the defining risk event and it's INDEX-INVISIBLE** — SPY was healthy through most of it, so SPY-200MA filters do nothing (B/C: MDD still ~54%). The factor crashed while the market rose.

## All 17 variants (CAGR gross / net@20bps / Sharpe / daily MDD)
- A naive base: 29.9 / 25.2 / 0.84 / **54.8** (yearly: 2020 +83, 2025 +52; 2021-23 unwind −52)
- B SPY200MA rebal: 25.2/21.6/0.78/53.7 · C SPY200MA daily: 21.3/17.5/0.71/54.4 — **index regime blind to factor unwind**
- **D trail30 only: 34.5 / 26.2 / 0.98 / 43.1 — best offense in the space** (Calmar 0.80)
- E trail30+ddtighten: 23.2/11.6/0.83/45.7 (29x turnover!) · J top10 full defense: 11.5/5.5/0.51/**58.6 — defended WORSE than naked** — **DD-tighten/whipsaw lesson: any defense that mechanically re-enters during a factor unwind compounds losses** (May 22 DD-tighten validated on DWAP-gated entries, does NOT transplant to forced monthly re-entry)
- F 200MA+t30: 30.1/23.8/0.93/43.1 · G all three: 23.2/13.6/0.86/40.9 (best MDD of all 17) · H DD-halve: 24.0/21.4/0.84/44.1 · I top10: 29.2/24.3/0.78/57.6
- Round 2 (gates/factor-trend, hypothesis formed on same window): K factor-own-200MA trend: 17.4/14.4/0.63/**60.3** (whipsaw at blowoff top) · L hi250-90% gate: 13.7/10.5/0.64/49.4 · M ma50 gate: 18.3/13.3/0.64/65.4 · N L+t30: 15.0/11.6/0.70/42.3 · O M+t30: 24.6/17.3/0.82/52.3 · P/Q combos: 19.5/54.2, 12.2/43.3

## Verdict
**The inversion thesis is REFUTED: nothing in the naive+overlay space gets MDD below ~40%.** t30v went through the same unwind at −17.9%. Its "terrible exchange rate" (gave up ~19pp CAGR for ~12pp DD) is partially vindicated: simple tools CANNOT buy that protection at any price tested. t30v's full conjunction (DWAP×1.05 + near-50d-high 3% + ensemble score + biweekly + inverse-vol) keeps you OUT of a factor unwind in a way no overlay replicates — soft single gates (ma50, hi250-90) lose the return WITHOUT gaining the protection.

## Behavioral sim (on weekly race data — daily would be harsher on naive)
Panic-sell at 20-25% own-DD, various re-entries: **t30v never trips (17.9% max). Panic-SPY realizes 0.1-9.3% → t30v's 9.9% beats behavioral SPY in EVERY scenario** (the honest animation story). Panic-naive still realizes 10-21% — behavior does NOT rescue us vs naive on this decade. Also: t30v's longest below-peak stretch = 37mo (worse than SPY 24mo, ≈naive 36mo) — defense is "shallow but LONG underwater"; don't oversell comfort.

## Open: t30v-side ablation (running at session end)
`pitfwu_wf_periods.py ablate` (mode added; wf() now takes dwap_th/near_hi; disable = −1000/+1000) → `scripts/ablation_results.json`, checkpointed per config. Configs: no_nearhigh, no_dwap, no_gates, no_volw, trail40 on t30v base (20×4.5 t30 volw1.0), continuous 2017-2026. Question: which control is the drawdown technology, what does each cost in CAGR — is there a t30v-minus-one-control at ~15-20% CAGR / ≤25% MDD? Base ref: 9.8%/17.9% (race).

## Next after ablation
- If a relaxed-t30v middle exists → per-window Tier-2 (held-out starts) before believing it (round-2/ablation variants are shaped by this window's data).
- Pre-2016 parquet extension (2008 GFC + 2009 momentum crash) is the decisive out-of-sample test — naive's 28.8% rode a crash-free decade; 2009 is where naive momentum historically died. Helps animation drama too.
- Rebuild portfolio-race.json with DAILY naive resolution before building the animation.
