---
name: Parquet migration — fix the real difference, never silence the alarm
description: When pickle/parquet diverge, investigate the underlying cause and align parquet with the target behavior. Never reclassify "structural" to "explainable" just to make the health-email warning green.
type: feedback
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
When the parquet-vs-pickle diff harness reports a divergence, the response is to UNDERSTAND the cause and align parquet with the way we want it to work post-cutover — not to broaden the "explainable" category, hide the type, or otherwise quiet the alarm.

**Why:** Once parquet becomes primary and pickle is demoted/decommissioned, every quirk we left unaddressed becomes "gee I wish we had done X differently." There's no second chance to reconcile — by then, parquet IS the authoritative store and any drift we silenced becomes part of production behavior.

The diff harness is the only window we have to compare what production currently does (pickle) to what we'll soon depend on (parquet) on real data. Silencing it forfeits that visibility.

**How to apply:**

1. **First question on any divergence:** "If parquet were already primary, which side is correct?" Not "is the diff harness mis-categorizing this?"
2. **If parquet is correct** → fix the pickle export OR accept that pickle will be retired and the discrepancy is one-way drift OK to ignore. But document the answer.
3. **If pickle is correct** → fix the parquet writer/reader before crossover. Do not cut over.
4. **If both representations are equally valid but different** → pick one as the canonical form, port the OTHER to match, then update the diff harness. The point of canonicalizing is the cutover, not the alarm.
5. **Never** add a divergence_type to the "explainable" allow-list without first answering "what would parquet-primary look like for this case, and have we made that the actual behavior?"

The Stage 3b cutover gate (7 consecutive clean days) loses meaning the moment we start widening the definition of "clean."
