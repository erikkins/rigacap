#!/usr/bin/env bash
# ============================================================================
# t30v chart / track-record data regeneration  (STAGED — do not run until the
# nightly email has fired; run SINGLY, never alongside another WF job)
# ============================================================================
#
# WHY: the track-record equity chart fetches /api/public/track-record, which
# serves a CACHED WalkForwardSimulation's equity_curve_json — currently the OLD
# 5-year run. This regenerates it as the honest 9-year t30v curve. The same run
# validates the strategy and confirms the headline numbers (triple duty).
#
# DB-POOL SAFETY: prod pool is pool_size=1 / overflow=2 / timeout=3s. Run this
# as a SINGLE job (no parallel WF). The past exhaustion was parallelism, not a
# single sequential run. Do NOT fire while the nightly email is in flight.
#
# ----------------------------------------------------------------------------
# PREREQUISITE (cutover item #2) — MUST be deployed first, or the curve is WRONG
# ----------------------------------------------------------------------------
#   vol_weight must be plumbed through so the WF actually applies inverse-vol:
#     _run_walk_forward_job (main.py:402)      -> read job_config["vol_weight"]
#     run_walk_forward_simulation (wf_service) -> accept vol_weight, set on backtester
#     backtester.configure / override          -> self.vol_weight = vol_weight
#   The backtester ALREADY has _vol_mult + med_vol (from research); this is just
#   plumbing the param through. WITHOUT it, payload below = equal-weight (NOT t30v).
#
#   Also verify /api/public/track-record serves THIS sim (latest vs a 'public'
#   flag) — if it filters to a specific cached row, mark this run accordingly.
# ----------------------------------------------------------------------------

set -euo pipefail

cat > /tmp/t30v_wf_payload.json << 'EOF'
{
  "walk_forward_job": {
    "strategy_id": 6,
    "start_date": "2017-01-03",
    "end_date": "2026-05-29",
    "frequency": "biweekly",
    "enable_ai": false,
    "max_symbols": 100,
    "max_positions": 20,
    "position_size_pct": 4.5,
    "trailing_stop_pct": 30.0,
    "vol_weight": 1.0,
    "dwap_threshold_pct": 5.0,
    "near_50d_high_pct": 3.0,
    "carry_positions": true,
    "purpose": "t30v_chart_regen_9yr"
  }
}
EOF

echo "Payload staged at /tmp/t30v_wf_payload.json"
echo "Run (SINGLE job, after email clears):"
echo ""
echo "  aws lambda invoke --function-name rigacap-prod-worker --region us-east-1 \\"
echo "    --invocation-type RequestResponse --profile rigacap \\"
echo "    --payload fileb:///tmp/t30v_wf_payload.json --cli-read-timeout 600 \\"
echo "    /tmp/t30v_wf_result.json && python3 -m json.tool /tmp/t30v_wf_result.json"
echo ""
echo "POST-RUN: GET /api/public/track-record should now return ~14% / 0.92 /"
echo "17% over 2017-2026; the chart on /track-record renders the 9-year curve."
