---
name: Real solution for intraday data anomalies (flash spikes, bad ticks)
description: Apr 30 2026 intraday WF validation surfaced FCEL/AMRN/NCTY trades with absurd "intraday gain" deltas (+3407% etc.) caused by momentary 1-minute spikes. Outlier filter is a band-aid; need a principled execution model.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**The bug surface:** Intraday trailing-stop validation (Apr 30 2026) showed three trades with absurd delta values driven by single-minute price spikes that no real trader could have executed against:
- FCEL 2021-01-11: +3407.21 pp
- FCEL 2021-02-08: +2860.90 pp
- AMRN 2018-10-03: +1885.72 pp

These are penny stocks during the meme-stock era — momentary 1-minute prints far above the day's average price. The simulator treats those prints as the running HWM, fires the stop at HWM × 0.88, and reports an exit price no one could actually have realized.

**Why this matters:** Production fires intraday stops too. If we trust intraday minute-bar data uncritically, production logic could trigger at impossible prices, then we'd have a real (vs simulated) trade execution that fails. Live broker would reject the order or fill at a much worse price. Slippage, gaps.

**Approaches to a real solution (research project, ~1-2 days):**

1. **Volume threshold** — discard bars with volume < N shares (e.g., < 100). Single-share bad prints carry no real liquidity.
2. **VWAP-based trigger price** — use the minute's VWAP rather than its LOW as the execution price. Closer to what an actual market order would fill at.
3. **Multi-minute confirmation** — require the stop trigger to hold for N consecutive minutes (e.g., 2-minute window) before firing. Filters single-minute flash spikes.
4. **Outlier rejection** — drop bars with H/L > 50% above/below surrounding bars' median. These are statistically suspicious.
5. **Sanity cap on HWM updates** — don't update HWM if a bar's HIGH is more than X% above the day's open (likely bad data, not a real high).
6. **Slippage model** — apply N% slippage to the trigger price (e.g., real fill = trigger × (1 - slippage_pct)). Better reflects real execution than a perfect fill at HWM × 0.88.

**Best path forward:** Combination of (3) + (6). Multi-minute confirmation filters the obvious spikes; slippage model accounts for real-world fill quality.

**For tonight's analysis:** apply outlier cap (±50 pp delta) as a band-aid so we can compute meaningful aggregate stats. Note in the report that the cap is a placeholder pending the real fix.

**Connected work:**
- Intraday WF validation result analysis (Apr 30 2026)
- Production intraday-stop logic (already deployed) — uses ALPACA quotes which are SIP-consolidated, so probably less prone to single-print anomalies than historical SIP minute bars. But still worth audit.
- Cache rule: real fix should be applied at SIMULATION time, not at cache write time. Raw cache stays raw — interpretation layer applies the model.

**Reference:** The 65 "intraday-worse" trades (IREN, ASTS, RIOT, etc.) are a SEPARATE issue — those are real intraday volatility cutting winners short, not data anomalies. Different problem (lockout-window question), different solution.
