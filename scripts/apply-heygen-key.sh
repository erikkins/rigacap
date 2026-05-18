#!/usr/bin/env bash
#
# Apply HEYGEN_API_KEY to the production worker Lambda via Terraform.
#
# Usage:
#   ./scripts/apply-heygen-key.sh
#
# The script:
#   1. Auto-discovers the current Lambda image tag (so we don't pin stale).
#   2. Auto-discovers existing META_IG_APP_ID / META_IG_APP_SECRET values
#      from the live Lambda env, so terraform doesn't drop them.
#   3. Prompts you to paste the HeyGen API key (hidden input — won't echo).
#   4. Runs `terraform apply -target=aws_lambda_function.worker` with all
#      the right -var flags.
#
# The HeyGen key never gets saved to disk. It lives only in the running
# terraform invocation. Re-run this script anytime to update.
#

set -euo pipefail

# --- Resolve repo root (script is at scripts/apply-heygen-key.sh) ---
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$REPO_ROOT/infrastructure/terraform"
WORKER_FN="rigacap-prod-worker"

echo "→ Discovering current Lambda image tag..."
IMAGE_URI=$(AWS_PROFILE=rigacap aws lambda get-function \
  --function-name "$WORKER_FN" --region us-east-1 \
  --query 'Code.ImageUri' --output text)
LAMBDA_IMAGE_TAG="${IMAGE_URI##*:}"
echo "  → $LAMBDA_IMAGE_TAG"

echo "→ Reading existing META_IG values from Lambda env (preserves drift)..."
META_IG_APP_ID=$(AWS_PROFILE=rigacap aws lambda get-function-configuration \
  --function-name "$WORKER_FN" --region us-east-1 \
  --query 'Environment.Variables.META_IG_APP_ID' --output text)
META_IG_APP_SECRET=$(AWS_PROFILE=rigacap aws lambda get-function-configuration \
  --function-name "$WORKER_FN" --region us-east-1 \
  --query 'Environment.Variables.META_IG_APP_SECRET' --output text)

if [ -z "$META_IG_APP_ID" ] || [ "$META_IG_APP_ID" = "None" ]; then
  echo "  ⚠ META_IG_APP_ID is empty in Lambda env. If you applied terraform without"
  echo "    preserving it earlier, IG/Threads token refresh will break. Aborting"
  echo "    so you can manually set it via the AWS console first."
  exit 1
fi
echo "  → META_IG_APP_ID preserved: ${META_IG_APP_ID:0:6}…"
echo "  → META_IG_APP_SECRET preserved: ${META_IG_APP_SECRET:0:6}…"

echo "→ Checking if HeyGen API key is already set on the Lambda..."
EXISTING_KEY=$(AWS_PROFILE=rigacap aws lambda get-function-configuration \
  --function-name "$WORKER_FN" --region us-east-1 \
  --query 'Environment.Variables.HEYGEN_API_KEY' --output text)
if [ -n "$EXISTING_KEY" ] && [ "$EXISTING_KEY" != "None" ]; then
  echo "  → Key already set (${EXISTING_KEY:0:10}…). Reusing existing value, no input needed."
  HEYGEN_KEY="$EXISTING_KEY"
else
  echo
  echo "→ Paste your HeyGen API key (hidden — won't echo). Press ENTER when done:"
  read -s HEYGEN_KEY
  echo
  if [ -z "$HEYGEN_KEY" ]; then
    echo "  ✗ Empty key. Aborting."
    exit 1
  fi
  echo "  → Key captured (${#HEYGEN_KEY} chars)."
fi
echo

echo "→ Running terraform apply..."
cd "$TF_DIR"
AWS_PROFILE=rigacap terraform apply \
  -var="lambda_image_tag=$LAMBDA_IMAGE_TAG" \
  -var="meta_ig_app_id=$META_IG_APP_ID" \
  -var="meta_ig_app_secret=$META_IG_APP_SECRET" \
  -var="heygen_api_key=$HEYGEN_KEY" \
  -target=aws_lambda_function.worker

echo
echo "→ Verifying HEYGEN_API_KEY is now set on the Lambda..."
LIVE_KEY_PREFIX=$(AWS_PROFILE=rigacap aws lambda get-function-configuration \
  --function-name "$WORKER_FN" --region us-east-1 \
  --query 'Environment.Variables.HEYGEN_API_KEY' --output text | head -c 8)
if [ -n "$LIVE_KEY_PREFIX" ] && [ "$LIVE_KEY_PREFIX" != "None" ]; then
  echo "  ✓ HEYGEN_API_KEY set: ${LIVE_KEY_PREFIX}…"
  echo
  echo "Next: test fire a video"
  echo '  aws lambda invoke --function-name rigacap-prod-worker --profile rigacap --region us-east-1 \'
  echo '    --invocation-type RequestResponse --cli-read-timeout 90 \'
  echo "    --payload '"'"'{\"heygen_video\":{\"action\":\"create\",\"script\":\"Quick test of Avatar V engine.\",\"aspect_ratio\":\"9:16\"}}'"'"' \\"
  echo "    /tmp/heygen_out.json && cat /tmp/heygen_out.json"
else
  echo "  ✗ HEYGEN_API_KEY still empty after apply. Investigate."
  exit 1
fi
