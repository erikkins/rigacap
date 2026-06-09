#!/usr/bin/env bash
#
# Launch an EC2 spot instance to run a 10-year walk-forward simulation.
#
# Usage:
#   ./scripts/ec2-spot-walkforward.sh              # Full run (build data + sim)
#   SKIP_BUILD=1 ./scripts/ec2-spot-walkforward.sh  # Reuse existing 10y pickle
#
# The instance self-terminates when done. Cost: ~$0.03-0.05 for a 1-hour run.
#
set -euo pipefail

PROFILE="rigacap"
REGION="us-east-1"
ROLE_NAME="rigacap-ec2-spot-role"
INSTANCE_PROFILE_NAME="rigacap-ec2-spot-profile"
INSTANCE_TYPE="${INSTANCE_TYPE:-r6i.large}"  # 16 GB, 2 vCPU
SPOT_MAX_PRICE="${SPOT_MAX_PRICE:-0.10}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== RigaCap 10-Year Walk-Forward (EC2 Spot) ==="
echo ""

# ─────────────────────────────────────────────────────────────
# Step 1: Read env vars from Worker Lambda
# ─────────────────────────────────────────────────────────────
echo "[1/5] Reading environment from rigacap-prod-worker Lambda..."

LAMBDA_CONFIG=$(aws lambda get-function-configuration \
  --function-name rigacap-prod-worker \
  --profile "$PROFILE" \
  --region "$REGION" \
  --query 'Environment.Variables' \
  --output json)

DATABASE_URL=$(echo "$LAMBDA_CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['DATABASE_URL'])")
ALPACA_API_KEY=$(echo "$LAMBDA_CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['ALPACA_API_KEY'])")
ALPACA_SECRET_KEY=$(echo "$LAMBDA_CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['ALPACA_SECRET_KEY'])")
PRICE_DATA_BUCKET=$(echo "$LAMBDA_CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin).get('PRICE_DATA_BUCKET', 'rigacap-prod-price-data-149218244179'))")

# Mask secrets in output
echo "  DATABASE_URL: ${DATABASE_URL:0:30}..."
echo "  ALPACA_API_KEY: ${ALPACA_API_KEY:0:8}..."
echo "  PRICE_DATA_BUCKET: $PRICE_DATA_BUCKET"

# ─────────────────────────────────────────────────────────────
# Step 2: Get latest ECR image URI
# ─────────────────────────────────────────────────────────────
echo ""
echo "[2/5] Getting latest ECR image..."

ACCOUNT_ID=$(aws sts get-caller-identity --profile "$PROFILE" --query 'Account' --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/rigacap-prod-api"

# Get the latest image tag (by push date)
LATEST_TAG=$(aws ecr describe-images \
  --repository-name rigacap-prod-api \
  --profile "$PROFILE" \
  --region "$REGION" \
  --query 'sort_by(imageDetails,& imagePushedAt)[-1].imageTags[0]' \
  --output text)

ECR_IMAGE="${ECR_REPO}:${LATEST_TAG}"
echo "  Image: $ECR_IMAGE"

# ─────────────────────────────────────────────────────────────
# Step 3: Create IAM role + instance profile (idempotent)
# ─────────────────────────────────────────────────────────────
echo ""
echo "[3/5] Ensuring IAM role exists..."

# Trust policy for EC2
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ec2.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}'

# Create role (ignore if exists)
if aws iam get-role --role-name "$ROLE_NAME" --profile "$PROFILE" &>/dev/null; then
  echo "  Role $ROLE_NAME already exists"
else
  echo "  Creating role $ROLE_NAME..."
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_POLICY" \
    --profile "$PROFILE" > /dev/null
fi

# Inline policy: S3 + ECR + EC2 self-terminate
INLINE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::${PRICE_DATA_BUCKET}",
        "arn:aws:s3:::${PRICE_DATA_BUCKET}/*"
      ]
    },
    {
      "Sid": "ECRPull",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SelfTerminate",
      "Effect": "Allow",
      "Action": "ec2:TerminateInstances",
      "Resource": "arn:aws:ec2:${REGION}:${ACCOUNT_ID}:instance/*",
      "Condition": {
        "StringEquals": {
          "ec2:ResourceTag/Name": "rigacap-10y-walkforward"
        }
      }
    }
  ]
}
EOF
)

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "rigacap-ec2-spot-policy" \
  --policy-document "$INLINE_POLICY" \
  --profile "$PROFILE"

# Create instance profile (ignore if exists)
if aws iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" --profile "$PROFILE" &>/dev/null; then
  echo "  Instance profile already exists"
else
  echo "  Creating instance profile..."
  aws iam create-instance-profile \
    --instance-profile-name "$INSTANCE_PROFILE_NAME" \
    --profile "$PROFILE" > /dev/null

  aws iam add-role-to-instance-profile \
    --instance-profile-name "$INSTANCE_PROFILE_NAME" \
    --role-name "$ROLE_NAME" \
    --profile "$PROFILE"

  echo "  Waiting 10s for IAM propagation..."
  sleep 10
fi

# ─────────────────────────────────────────────────────────────
# Step 4: Launch spot instance
# ─────────────────────────────────────────────────────────────
echo ""
echo "[4/5] Launching spot instance ($INSTANCE_TYPE, max \$${SPOT_MAX_PRICE}/hr)..."

# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text \
  --profile "$PROFILE" \
  --region "$REGION")

echo "  AMI: $AMI_ID"

# Get default VPC + subnet
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --profile "$PROFILE" \
  --region "$REGION")

# Security group: outbound only (no inbound needed)
SG_NAME="rigacap-ec2-spot-sg"
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --profile "$PROFILE" \
  --region "$REGION" 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  echo "  Creating security group (outbound-only)..."
  SG_ID=$(aws ec2 create-security-group \
    --group-name "$SG_NAME" \
    --description "RigaCap EC2 spot - outbound only" \
    --vpc-id "$VPC_ID" \
    --profile "$PROFILE" \
    --region "$REGION" \
    --query 'GroupId' \
    --output text)
fi
echo "  Security group: $SG_ID"

# Upload runner script to S3 (avoids 16KB user data limit)
echo "  Uploading runner script to S3..."
aws s3 cp "$SCRIPT_DIR/ec2_wf_runner.py" \
  "s3://${PRICE_DATA_BUCKET}/scripts/ec2_wf_runner.py" \
  --profile "$PROFILE" --region "$REGION"

# Build user data: use a JSON env file to avoid shell escaping issues with secrets
USER_DATA_FILE=$(mktemp)
trap "rm -f $USER_DATA_FILE" EXIT

# Write env vars to a JSON file that gets base64-encoded into user data.
# This avoids embedding secrets directly in the shell script.
ENV_JSON=$(python3 -c "
import json, sys
env = {
    'DATABASE_URL': sys.argv[1],
    'ALPACA_API_KEY': sys.argv[2],
    'ALPACA_SECRET_KEY': sys.argv[3],
    'PRICE_DATA_BUCKET': sys.argv[4],
    'DATA_SOURCE_PRIMARY': 'alpaca',
    'LAMBDA_ROLE': 'worker',
    'AWS_DEFAULT_REGION': sys.argv[5],
    'SKIP_BUILD': sys.argv[6],
    'WF_START_DATE': sys.argv[7],
    'WF_END_DATE': sys.argv[8],
    'WF_MAX_SYMBOLS': sys.argv[9],
    'WF_CARRY_POSITIONS': sys.argv[10],
    'WF_ENABLE_AI': sys.argv[11],
}
print(json.dumps(env))
" "$DATABASE_URL" "$ALPACA_API_KEY" "$ALPACA_SECRET_KEY" "$PRICE_DATA_BUCKET" \
  "$REGION" "$SKIP_BUILD" \
  "${WF_START_DATE:-2016-02-01}" "${WF_END_DATE:-2026-02-01}" \
  "${WF_MAX_SYMBOLS:-500}" "${WF_CARRY_POSITIONS:-true}" "${WF_ENABLE_AI:-false}")

ENV_B64=$(echo "$ENV_JSON" | base64)

# User data script — only references base64-encoded blobs, no raw secrets
cat > "$USER_DATA_FILE" << 'USERDATA_LITERAL'
#!/bin/bash
# Write the actual worker script to disk and run it via nohup
# (cloud-init has a 10-min timeout that kills long-running user-data scripts)
cat > /opt/run-walkforward.sh << 'WORKER_SCRIPT'
#!/bin/bash
set -euo pipefail
exec > /var/log/walkforward.log 2>&1

self_terminate() {
  echo ""
  echo "=== Self-terminating instance ==="
  echo "Time: $(date -u)"
  rm -f /tmp/docker.env
  # Upload log to S3 before terminating
  local BUCKET=$(echo '__ENV_B64__' | base64 -d | jq -r '.PRICE_DATA_BUCKET' 2>/dev/null || echo "")
  if [ -n "$BUCKET" ] && [ -f /var/log/walkforward.log ]; then
    aws s3 cp /var/log/walkforward.log "s3://${BUCKET}/logs/ec2-walkforward-$(date -u +%Y%m%d-%H%M%S).log" || true
  fi
  local TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60") || true
  local INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id) || true
  aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "__REGION_LITERAL__" || true
}
trap self_terminate EXIT

echo "=== Walk-Forward Runner Starting ==="
echo "Time: $(date -u)"

# Install Docker + jq
dnf install -y docker jq
systemctl start docker

# Decode env vars from base64 JSON blob
ENV_JSON=$(echo '__ENV_B64__' | base64 -d)
REGION=$(echo "$ENV_JSON" | jq -r '.AWS_DEFAULT_REGION')
ECR_IMAGE='__ECR_IMAGE__'
ACCOUNT_ID='__ACCOUNT_ID__'

# ECR login
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Pull image
echo "Pulling $ECR_IMAGE ..."
docker pull "$ECR_IMAGE"

# Download runner script from S3
BUCKET=$(echo "$ENV_JSON" | jq -r '.PRICE_DATA_BUCKET')
aws s3 cp "s3://${BUCKET}/scripts/ec2_wf_runner.py" /tmp/ec2_wf_runner.py

# Write Docker env file from JSON
echo "$ENV_JSON" | jq -r 'to_entries[] | "\(.key)=\(.value)"' > /tmp/docker.env

# Run simulation inside the production container
# --network host lets the container reach EC2 IMDS for AWS credentials (S3 access)
echo "Starting walk-forward simulation..."
docker run --rm \
  --network host \
  --entrypoint python3 \
  -v /tmp/ec2_wf_runner.py:/tmp/ec2_wf_runner.py:ro \
  --env-file /tmp/docker.env \
  "$ECR_IMAGE" \
  /tmp/ec2_wf_runner.py 2>&1

echo ""
echo "=== Simulation finished successfully ==="
echo "Time: $(date -u)"
WORKER_SCRIPT

chmod +x /opt/run-walkforward.sh

# Launch worker in background (survives cloud-init timeout)
nohup /opt/run-walkforward.sh &
echo "Worker PID: $!"
echo "Log: /var/log/walkforward.log"
USERDATA_LITERAL

# Substitute placeholders into user data (safe — base64 is [A-Za-z0-9+/=\n])
python3 -c "
import sys
with open(sys.argv[1]) as f:
    content = f.read()
content = content.replace('__ENV_B64__', sys.argv[2])
content = content.replace('__ECR_IMAGE__', sys.argv[3])
content = content.replace('__ACCOUNT_ID__', sys.argv[4])
content = content.replace('__REGION_LITERAL__', sys.argv[5])
with open(sys.argv[1], 'w') as f:
    f.write(content)
" "$USER_DATA_FILE" "$ENV_B64" "$ECR_IMAGE" "$ACCOUNT_ID" "$REGION"

# Get all subnet IDs (excluding us-east-1e which doesn't support r-type)
ALL_SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=default-for-az,Values=true" \
  --query 'Subnets[?AvailabilityZone!=`us-east-1e`].SubnetId' \
  --output json \
  --profile "$PROFILE" \
  --region "$REGION")

# Build fleet overrides: try r6i.large, r5.large, r7i.large across all AZs
OVERRIDES=$(python3 -c "
import json, sys
subnets = json.loads(sys.argv[1])
types = ['r6i.large', 'r5.large', 'r7i.large', 'm5.xlarge']
overrides = []
for subnet in subnets:
    for itype in types:
        overrides.append({'InstanceType': itype, 'SubnetId': subnet})
print(json.dumps(overrides))
" "$ALL_SUBNETS")

# Launch via EC2 Fleet (tries all AZ + instance type combos automatically)
FLEET_ID=$(aws ec2 create-fleet \
  --type instant \
  --target-capacity-specification "TotalTargetCapacity=1,DefaultTargetCapacityType=spot" \
  --spot-options "AllocationStrategy=capacity-optimized,MaxTotalPrice=$SPOT_MAX_PRICE" \
  --launch-template-configs "[{
    \"LaunchTemplateSpecification\": {\"Version\": \"\\\$Default\"},
    \"Overrides\": $OVERRIDES
  }]" \
  --profile "$PROFILE" \
  --region "$REGION" \
  --query 'FleetId' \
  --output text 2>/dev/null || echo "")

# Fleet API requires a launch template — fall back to run-instances with retries
INSTANCE_ID=""
for try_type in r6i.large r5.large r7i.large m5.xlarge; do
  for try_az in b c d f a; do
    TRY_SUBNET=$(aws ec2 describe-subnets \
      --filters "Name=vpc-id,Values=$VPC_ID" "Name=default-for-az,Values=true" "Name=availability-zone,Values=${REGION}${try_az}" \
      --query 'Subnets[0].SubnetId' \
      --output text \
      --profile "$PROFILE" \
      --region "$REGION" 2>/dev/null)
    [ -z "$TRY_SUBNET" ] || [ "$TRY_SUBNET" = "None" ] && continue

    echo "  Trying $try_type in ${REGION}${try_az}..."
    INSTANCE_ID=$(aws ec2 run-instances \
      --image-id "$AMI_ID" \
      --instance-type "$try_type" \
      --subnet-id "$TRY_SUBNET" \
      --security-group-ids "$SG_ID" \
      --iam-instance-profile "Name=$INSTANCE_PROFILE_NAME" \
      --instance-market-options '{"MarketType":"spot","SpotOptions":{"MaxPrice":"'"$SPOT_MAX_PRICE"'","SpotInstanceType":"one-time"}}' \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=rigacap-10y-walkforward}]" \
      --user-data "file://$USER_DATA_FILE" \
      --metadata-options "HttpTokens=required,HttpPutResponseHopLimit=2,HttpEndpoint=enabled" \
      --query 'Instances[0].InstanceId' \
      --output text \
      --profile "$PROFILE" \
      --region "$REGION" 2>/dev/null) && break 2
    INSTANCE_ID=""
  done
done

if [ -z "$INSTANCE_ID" ]; then
  echo "ERROR: No spot capacity available across all instance types and AZs."
  echo "Try again later or increase SPOT_MAX_PRICE (current: \$${SPOT_MAX_PRICE}/hr)"
  exit 1
fi

echo "  Instance ID: $INSTANCE_ID"

# ─────────────────────────────────────────────────────────────
# Step 5: Monitoring instructions
# ─────────────────────────────────────────────────────────────
echo ""
echo "[5/5] Instance launched! Monitor with:"
echo ""
echo "  # Check instance status"
echo "  aws ec2 describe-instances --instance-ids $INSTANCE_ID --profile $PROFILE --query 'Reservations[0].Instances[0].State.Name' --output text"
echo ""
echo "  # View console output (boot logs only — limited)"
echo "  aws ec2 get-console-output --instance-id $INSTANCE_ID --profile $PROFILE --latest --query 'Output' --output text"
echo ""
echo "  # View full log (uploaded to S3 on completion/failure)"
echo "  aws s3 ls s3://${PRICE_DATA_BUCKET}/logs/ --profile $PROFILE | tail -5"
echo "  aws s3 cp s3://${PRICE_DATA_BUCKET}/logs/<latest>.log - --profile $PROFILE"
echo ""
echo "Expected timeline:"
echo "  ~2 min   — Instance boot + Docker install"
echo "  ~3 min   — ECR image pull"
echo "  ~15 min  — Data fetch (Alpaca, ~7000 symbols x 10y)"
echo "  ~30 min  — Walk-forward sim (260 biweekly periods)"
echo "  ~50 min  — Total. Instance self-terminates when done."
echo ""
echo "Estimated cost: \$0.03-0.05 (r6i.large spot ~\$0.03/hr)"
echo ""
echo "Results will appear in the walk_forward_simulations table."
echo "View in admin: Strategies > Walk-Forward History (2016-2026 range)"
