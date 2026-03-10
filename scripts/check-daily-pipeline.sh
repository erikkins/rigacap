#!/bin/bash
# Quick check that the daily pipeline fired and all chained jobs completed.
# Run ~30 min after the 4:20 PM EDT cron (i.e., around 4:50 PM EDT).
#
# Usage: ./scripts/check-daily-pipeline.sh

set -euo pipefail
PROFILE="rigacap"
REGION="us-east-1"
BUCKET="rigacap-prod-price-data-149218244179"

echo "=== Daily Pipeline Health Check ==="
echo "Current time: $(TZ=America/New_York date '+%I:%M %p EDT')"
echo ""

# 1. Dashboard freshness
echo "--- Dashboard JSON ---"
DASH_MODIFIED=$(aws s3api head-object --bucket $BUCKET --key signals/dashboard.json --profile $PROFILE --region $REGION --query 'LastModified' --output text 2>/dev/null || echo "NOT FOUND")
echo "Last modified: $DASH_MODIFIED"

# 2. SPY CSV freshness
echo ""
echo "--- SPY CSV ---"
SPY_MODIFIED=$(aws s3api head-object --bucket $BUCKET --key prices/SPY.csv --profile $PROFILE --region $REGION --query 'LastModified' --output text 2>/dev/null || echo "NOT FOUND")
echo "Last modified: $SPY_MODIFIED"

# 3. Recent worker logs — look for key pipeline events
echo ""
echo "--- Worker Logs (last 30 min) ---"
THIRTY_MIN_AGO=$(python3 -c "import datetime; print(int((datetime.datetime.utcnow() - datetime.timedelta(minutes=30)).timestamp()*1000))")
NOW=$(python3 -c "import datetime; print(int(datetime.datetime.utcnow().timestamp()*1000))")

for PATTERN in "daily_scan" "Chained CSV" "csv_export_from_scan" "daily_wf_cache" "Daily scan result" "CSV export"; do
    HITS=$(aws logs filter-log-events \
        --log-group-name /aws/lambda/rigacap-prod-worker \
        --profile $PROFILE --region $REGION \
        --start-time "$THIRTY_MIN_AGO" --end-time "$NOW" \
        --filter-pattern "$PATTERN" \
        --query 'events[*].message' --output text 2>/dev/null | head -3)
    if [ -n "$HITS" ]; then
        echo "  ✅ Found: $PATTERN"
    else
        echo "  ❌ Missing: $PATTERN"
    fi
done

# 4. Worker errors in last 30 min
echo ""
echo "--- Worker Errors (last 30 min) ---"
ERRORS=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda --metric-name Errors \
    --dimensions Name=FunctionName,Value=rigacap-prod-worker \
    --start-time "$(python3 -c "from datetime import datetime, timedelta; print((datetime.utcnow() - timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ'))")" \
    --end-time "$(python3 -c "from datetime import datetime; print(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))")" \
    --period 1800 --statistics Sum \
    --profile $PROFILE --region $REGION \
    --output json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
total = sum(p['Sum'] for p in data.get('Datapoints', []))
print(int(total))
")
if [ "$ERRORS" = "0" ]; then
    echo "  ✅ No errors"
else
    echo "  ❌ $ERRORS error(s)"
fi

echo ""
echo "=== Done ==="
