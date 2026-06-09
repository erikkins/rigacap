#!/bin/bash
# Local 10y+ walk-forward run (Oct 2015 → today) on the FIXED 11y pickle.
# Option B config: smoothed AI with warmup + reduced trials.
#   --smoothing 0.7  — blend 70% prior + 30% new optimizer suggestion (damps
#                      walk-forward overfit thrash)
#   --warmup 13      — first 13 periods use fixed params; AI kicks in once
#                      indicators have stabilized
#   --n-trials 30    — smaller TPE search per period; faster, less Bayesian
#                      depth, but with smoothing the lookback context smooths
#                      out single-period noise anyway
# nohup + caffeinate so it survives terminal close and laptop sleep.
set -e

cd /Users/erikkins/CODE/stocker-app
source backend/venv/bin/activate

nohup caffeinate -i python3 scripts/local_wf_runner.py \
    --pickle backend/data/all_data_11y.pkl.gz \
    --start 2015-10-15 \
    --end 2026-04-27 \
    --strategy-id 5 \
    --max-symbols 200 \
    --n-trials 30 \
    --smoothing 0.7 \
    --warmup 13 \
    > /tmp/wf_11y_run.log 2>&1 &

WF_PID=$!
echo "Launched WF runner — PID $WF_PID"
echo "Log: /tmp/wf_11y_run.log"
echo "Tail with: tail -f /tmp/wf_11y_run.log"
