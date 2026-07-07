---
name: project-sell-alert-parity-bug-jul7
description: SELL-alert parity bug — dashboard 12% vs model/email 30% trailing stop; + rollup-email TODO (deferred by Erik Jul 7)
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# SELL-alert parity bug + rollup TODO (found Jul 7 2026, DEFERRED — Erik: "save that and finish this migration")

## What Erik saw
Held 4 (GLW/UMC/MRVL/WULF) in erik@rigacap.com. Daily scan ran → got **ONE email (WULF)** but the **dashboard showed SELL ribbons + SELL buttons on ALL 4** → he manually sold all 4 (recorded exits ~4:31pm ET, all reason=stop_loss).

## Root cause — two code paths use DIFFERENT trailing stops
- **Dashboard** `scanner_service.generate_sell_signals` (backend/app/api/signals.py:1815-1818) passes hardcoded **`settings.TRAILING_STOP_PCT = 12.0`** (config.py:92). Comment: "regime adjustments disabled (validated: fixed beats adaptive)". → at 12% ALL 4 were past the stop → 4 SELL ribbons.
- **Email EOD alert pass** (backend/main.py:1938 "User-position EOD alert pass") + **model live exits** use **`_get_regime_trailing_stop(data)`** (model_portfolio_service.py:132; reads `dashboard_data['regime_adjustments']['effective']['trailing_stop_pct']`, else fallback `TRAILING_STOP_PCT=12`). Today resolved to **~30%** (regime-adjusted, rotating_bull). → only WULF (−30.2% off high) breached → 1 email.

## Verified math (off-high drawdown vs 30% trail)
WULF hwm28.98 exit20.24 = **−30.2%** ✅ breached 30% (stop 20.29). GLW hwm255.69 exit185.38 −27.5% ❌. MRVL hwm310.58 exit230.70 −25.7% ❌. UMC hwm28.01 exit23.83 −14.9% ❌. All 4 in active universe (in data_cache) so Bug-B "universe skip" was NOT it.

## Verdict
**Email was CORRECT** (WULF = only genuine 30%-trail model exit). **Dashboard is STALE** — a MISSED spot in the t30v 12%→30% display-parity sweep (see [[project-preserver-2tier-phase2]] follow-up #2 "t30v DISPLAY PARITY SWEEP"; [[feedback_wf_prod_parity]]: any UI exit param MUST be the live t30v value). Affects **ALL subscribers** — dashboard tells everyone to exit at 12% while the model holds to 30% → premature exits. Erik was pushed into 3 exits (GLW/MRVL/UMC) the model would still HOLD; only WULF was real.

## TWO fixes (both DEFERRED Jul 7 to finish the Preserver migration; Erik still wants rollup)
1. **PRIMARY money bug:** signals.py:1818 → use `_get_regime_trailing_stop(data)` (or 30) so dashboard ribbons == email == model. All-subscriber prod change.
2. **SECONDARY (Erik's original ask, he reaffirmed "single rollup email is the better option"):** the EOD alert pass (main.py:1938) sends **one `send_sell_alert` per symbol** (email_service.send_sell_alert is single-symbol only). Build a **consolidated rollup** email listing all positions that exited that day. Latent today (only 1 breached), but the day ≥2 breach 30% it'll spray N emails.

Both ride a normal deploy. Get Erik's explicit nod that dashboard should align to 30% (he's ~confirmed) before flipping what every subscriber sees.
