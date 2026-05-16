---
name: S3 list_objects_v2 — always filter subdirectory prefixes
description: list_objects_v2 with a prefix returns objects from ALL nested paths. Sort-then-pick logic must filter out subdirectory keys (e.g., "backups/") or it silently returns the wrong file.
type: feedback
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
When using `s3.list_objects_v2(Prefix='some/path/')` to find the "latest" object by sorted-key, **always filter out keys from subdirectories** of that prefix.

**Why:** `list_objects_v2` returns ALL objects under the prefix, including those in nested "directories" (S3 has no real directories; nested paths are just longer keys with `/` separators). And lowercase letters sort AFTER digits in ASCII — so `newsletter/drafts/backups/X.json` sorts AFTER `newsletter/drafts/2026-XX-YY.json` in descending order.

**The bug this caused (May 16 2026):** Admin newsletter editor stubbornly showed May 3 draft content for 12 days. Root cause: `get_latest_draft()` called `list_objects_v2(Prefix='newsletter/drafts/')`, then `sorted(keys, reverse=True)[0]`. A backup file at `newsletter/drafts/backups/2026-05-03.pre-regime-fix.json` was sorting above all the dated drafts because `b` > `2` in ASCII. Reload + hard refresh didn't help because the API itself was returning the wrong file.

**How to apply:**

Two patterns that work:

```python
# Option A — filter by key shape
keys = [
    o["Key"] for o in resp.get("Contents", [])
    if "/backups/" not in o["Key"]   # or any subdirectory pattern
]

# Option B — use Delimiter='/' to skip subdirectories entirely
resp = s3.list_objects_v2(Bucket=B, Prefix=P, Delimiter='/')
# Contents now only includes top-level keys under P
```

Prefer Option A when you might add subdirectories with various names in the future. Prefer Option B when you have a strict flat-list layout.

**Audit checklist for any new `list_objects_v2 + sorted` logic:**
- Does my prefix path have (or might it gain) subdirectories?
- Would a subdirectory key sort higher than a top-level key under any sort order I'm using?
- If yes, filter explicitly.

This bites every storage-as-database use of S3. Same pattern would break if anyone adds `newsletter/drafts/archive/`, `newsletter/drafts/_meta.json`, etc.
