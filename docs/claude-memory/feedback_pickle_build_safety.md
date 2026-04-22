---
name: Pickle build safety — NEVER auto-upload, always verify before replacing
description: Build script auto-uploaded a 3-symbol pickle to S3, replacing the 4000+ symbol production pickle. Added safety rules.
type: feedback
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
On Apr 22, 2026, the build_10y_pickle.py script ran with only 3 symbols fetched (SPY + 2 others) and auto-uploaded to S3, replacing the production pickle. Restored from weekly backup immediately.

**Why:** The script has `S3_KEY = "prices/all_data.pkl.gz"` hardcoded — it overwrites production on upload regardless of how many symbols were fetched.

**How to apply:**
1. NEVER auto-upload to the production S3 key. Build to a separate path first.
2. ALWAYS verify symbol count before any upload: minimum 4000 symbols or abort.
3. The guardrail check should be in the script itself, not relied on manually.
4. Build to `/tmp/all_data_NEW.pkl.gz` first, verify, then manually copy to production path.
5. When building a 10y pickle, output to `all_data_10y.pkl.gz` — a different key entirely.
