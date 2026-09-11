#!/usr/bin/env bash
#
# set-snaptrade-prod-env.sh — safely add the SnapTrade PRODUCTION credentials to the api + worker
# Lambdas WITHOUT the --environment landmine (which replaces ALL env vars and would wipe
# DATABASE_URL / Stripe / JWT etc). It reads the current env, MERGES the new keys in, and writes
# the COMPLETE map back — with backups + before/after sanity checks so a partial write can't happen.
#
# Secrets NEVER appear on the command line or in this repo: they live only in a local creds file
# that you fill in (default: ~/.rigacap/snaptrade-prod.env), which the script sources.
#
# What it sets:
#   - SNAPTRADE_PROD_CLIENT_ID / SNAPTRADE_PROD_CONSUMER_KEY  -> BOTH api + worker   (from creds file)
#   - SNAPTRADE_CLIENT_ID / SNAPTRADE_CONSUMER_KEY (the TEST key) -> WORKER           (auto-copied
#       from the api Lambda's live env, so you don't re-enter them; needed for the reconcile sweep)
#   - SNAPTRADE_KMS_KEY_ID -> BOTH, only if you put it in the creds file (optional)
#
# Usage:
#   ./scripts/set-snaptrade-prod-env.sh            # uses ~/.rigacap/snaptrade-prod.env
#   ./scripts/set-snaptrade-prod-env.sh /path/to/creds.env
#
set -euo pipefail

PROFILE=rigacap
REGION=us-east-1
API=rigacap-prod-api
WORKER=rigacap-prod-worker
CREDS_FILE="${1:-$HOME/.rigacap/snaptrade-prod.env}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${TMPDIR:-/tmp}/snaptrade-env-backup-$STAMP"

# --- 1. Load prod creds from the local file (never from argv, never printed) -------------------
if [ ! -f "$CREDS_FILE" ]; then
  cat >&2 <<MSG
❌ Creds file not found: $CREDS_FILE

Create it with your brand-new SnapTrade PRODUCTION pair (values in place of the ...):

  mkdir -p "$(dirname "$CREDS_FILE")"
  cat > "$CREDS_FILE" <<'EOF'
SNAPTRADE_PROD_CLIENT_ID=...
SNAPTRADE_PROD_CONSUMER_KEY=...
# KMS at-rest encryption is already wired (alias/rigacap-snaptrade-secret) and set by default.
# Only add a line here if you ever rotate to a different key:
# SNAPTRADE_KMS_KEY_ID=...
EOF
  chmod 600 "$CREDS_FILE"

Then re-run this script.
MSG
  exit 1
fi

set -a; . "$CREDS_FILE"; set +a
: "${SNAPTRADE_PROD_CLIENT_ID:?SNAPTRADE_PROD_CLIENT_ID missing from $CREDS_FILE}"
: "${SNAPTRADE_PROD_CONSUMER_KEY:?SNAPTRADE_PROD_CONSUMER_KEY missing from $CREDS_FILE}"
# At-rest encryption for the per-user userSecret. Defaults to the KMS key created for this
# (alias/rigacap-snaptrade-secret); override in the creds file only if you rotate to a new key.
# Not a secret — it's a key identifier — so it's safe to default here.
SNAPTRADE_KMS_KEY_ID="${SNAPTRADE_KMS_KEY_ID:-147fae49-0adc-4cb0-b1b2-b91c0330f5ef}"
export SNAPTRADE_KMS_KEY_ID

mkdir -p "$BACKUP_DIR"
echo "🔧 SnapTrade prod-env merge (backups -> $BACKUP_DIR)"

# --- 2. Auto-pull the TEST creds from the api Lambda's live env (so we needn't re-enter them) ---
API_ENV_JSON="$(aws lambda get-function-configuration --function-name "$API" \
  --profile "$PROFILE" --region "$REGION" --query 'Environment.Variables' --output json)"
export TEST_CID="$(printf '%s' "$API_ENV_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("SNAPTRADE_CLIENT_ID",""))')"
export TEST_KEY="$(printf '%s' "$API_ENV_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("SNAPTRADE_CONSUMER_KEY",""))')"
if [ -z "$TEST_CID" ] || [ -z "$TEST_KEY" ]; then
  echo "⚠️  Could not read the existing TEST key off $API — worker will get PROD keys only." >&2
fi

# --- 3. Merge helper. $1=function, $2=set-of-keys ('prod' | 'prod+test') --------------------
apply_env() {
  local FN="$1" MODE="$2"
  local cur; cur="$(aws lambda get-function-configuration --function-name "$FN" \
    --profile "$PROFILE" --region "$REGION" --query 'Environment.Variables' --output json)"

  local n_before; n_before="$(printf '%s' "$cur" | python3 -c 'import sys,json;print(len(json.load(sys.stdin) or {}))')"
  if [ "$n_before" -lt 5 ]; then
    echo "❌ ABORT $FN: only $n_before existing env vars — refusing to risk a partial overwrite." >&2
    exit 1
  fi
  printf '%s' "$cur" > "$BACKUP_DIR/$FN.before.json"

  # Merge in python: read current from stdin + new values from THIS process's env (not argv),
  # emit {"Variables": {...}} for `aws --environment file://`.
  printf '%s' "$cur" | MODE="$MODE" python3 -c '
import sys, os, json
cur = json.load(sys.stdin) or {}
add = {
  "SNAPTRADE_PROD_CLIENT_ID":   os.environ["SNAPTRADE_PROD_CLIENT_ID"],
  "SNAPTRADE_PROD_CONSUMER_KEY":os.environ["SNAPTRADE_PROD_CONSUMER_KEY"],
}
if os.environ.get("SNAPTRADE_KMS_KEY_ID"):
  add["SNAPTRADE_KMS_KEY_ID"] = os.environ["SNAPTRADE_KMS_KEY_ID"]
if os.environ["MODE"] == "prod+test":
  if os.environ.get("TEST_CID"): add["SNAPTRADE_CLIENT_ID"]   = os.environ["TEST_CID"]
  if os.environ.get("TEST_KEY"): add["SNAPTRADE_CONSUMER_KEY"] = os.environ["TEST_KEY"]
merged = dict(cur); merged.update(add)
# canary: never drop a load-bearing var
for k in ("DATABASE_URL",):
  assert k in merged, f"{k} vanished from merge — aborting"
json.dump({"Variables": merged}, open(os.environ["OUT"], "w"))
print(f"{len(cur)} -> {len(merged)} vars; adding: {sorted(add)}")
' 2>&1 | sed "s/^/   [$FN] /"

  aws lambda update-function-configuration --function-name "$FN" \
    --profile "$PROFILE" --region "$REGION" \
    --environment "file://$BACKUP_DIR/$FN.merged.json" >/dev/null

  aws lambda wait function-updated --function-name "$FN" --profile "$PROFILE" --region "$REGION"

  # --- verify: nothing lost, new keys present ---
  local after; after="$(aws lambda get-function-configuration --function-name "$FN" \
    --profile "$PROFILE" --region "$REGION" --query 'Environment.Variables' --output json)"
  printf '%s' "$after" | BEFORE="$BACKUP_DIR/$FN.before.json" MODE="$MODE" python3 -c '
import sys, json, os
a = json.load(sys.stdin) or {}
b = json.load(open(os.environ["BEFORE"]))
lost = [k for k in b if k not in a]
assert not lost, f"LOST vars: {lost}"
need = ["SNAPTRADE_PROD_CLIENT_ID","SNAPTRADE_PROD_CONSUMER_KEY"]
if os.environ["MODE"]=="prod+test": need += ["SNAPTRADE_CLIENT_ID","SNAPTRADE_CONSUMER_KEY"]
miss = [k for k in need if not a.get(k)]
assert not miss, f"MISSING after write: {miss}"
print(f"OK — {len(a)} vars, 0 lost, keys present")
' 2>&1 | sed "s/^/   [$FN] /"
}

# hand OUT path to the merge step (python writes the merged file there)
export OUT_API="$BACKUP_DIR/$API.merged.json"
export OUT_WORKER="$BACKUP_DIR/$WORKER.merged.json"

echo "→ api Lambda (prod keys):"
OUT="$OUT_API" apply_env "$API" "prod"
echo "→ worker Lambda (prod keys + copied test keys):"
OUT="$OUT_WORKER" apply_env "$WORKER" "prod+test"

echo "✅ Done. Backups of the prior env are in $BACKUP_DIR (delete once you're happy)."
echo "   Rollback if ever needed: aws lambda update-function-configuration --function-name <fn> \\"
echo "     --profile $PROFILE --region $REGION --environment \"file://<fn>.before.json\"  (wrap under {\"Variables\":...})"
