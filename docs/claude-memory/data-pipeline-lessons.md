# Data Pipeline Lessons (Mar 6, 2026 Incident)

## What Happened
1. A daily scan ran at midnight UTC (not the intended 4 PM ET) with stale data
2. Alpaca bars hadn't settled yet, CSVs in S3 ended at Mar 4
3. Pickle was deleted while debugging, causing OOM cascade
4. Multiple failed attempts to re-scan (OOM at 3008 MB Worker Lambda)
5. Bad signals generated from stale data, bad portfolio buys made (BLBX at wrong price)
6. Eventually rebuilt pickle locally and re-ran scan

## Root Causes
- **No guard against running scan before data is settled.** The scan ran before Alpaca had settled Mar 5/6 bars.
- **Pickle deletion is catastrophic.** Without pickle, Lambda must load 7381 individual CSVs → guaranteed OOM at 3008 MB.
- **Daily scan doesn't export CSVs.** Only pickle + dashboard + snapshot. Charts stay stale unless CSVs are explicitly exported.
- **Freshness gate only checks SPY.** Other symbols can be stale without triggering alerts.

## Recovery Steps (for next time)
1. **Don't panic. Don't delete the pickle.**
2. If pickle is corrupted but CSVs exist: use `{"csv_export_from_scan": true}` to rebuild (loads pickle → exports CSVs)
3. If pickle is deleted:
   - **Build locally**: Download CSVs from S3, fetch missing days from yfinance in batches of 500, build pickle, upload to S3
   - This is the only reliable path at 3008 MB memory
4. After pickle is in S3: `{"daily_scan": true}` on Worker Lambda generates signals/dashboard/snapshot
5. CSVs must be updated separately — either via `{"csv_export_from_scan": true}` or local script
6. Fix any bad portfolio entries via `run_migration` SQL

## CSV Column Format
The scanner exports CSVs with these columns:
```
Date, date, open, high, low, close, volume, dwap, ma_50, ma_200, vol_avg, high_52w
```
All lowercase. yfinance returns `Open, High, Low, Close, Volume` (capitalized). When patching CSVs with yfinance data, MUST map to lowercase columns.

## Key Table Names (always forget these)
- `model_positions` — portfolio positions (NOT model_portfolio_positions)
- `model_portfolio_state` — cash, PnL, trade counts
- `model_portfolio_snapshots` — daily value snapshots
- `regime_forecast_snapshots` — daily regime data
  - Column: `probabilities_json` (NOT transition_probs)
  - Has: `spy_close`, `vix_close`
- `ensemble_signals` — daily signal records
  - Unique constraint: `(signal_date, symbol)`

## Emergency Playbook
```bash
# 1. Check if pickle exists
aws s3 ls s3://rigacap-prod-price-data-149218244179/prices/all_data.pkl.gz --profile rigacap

# 2. Run daily scan (pickle must exist in S3)
aws lambda invoke --function-name rigacap-prod-worker --profile rigacap --region us-east-1 --cli-read-timeout 900 --payload '{"daily_scan": true}' /tmp/scan-result.json

# 3. Export CSVs (loads pickle, writes all individual CSVs)
aws lambda invoke --function-name rigacap-prod-worker --profile rigacap --region us-east-1 --cli-read-timeout 900 --payload '{"csv_export_from_scan": true}' /tmp/csv-result.json

# 4. Delete bad signals
aws lambda invoke --function-name rigacap-prod-worker --profile rigacap --payload '{"run_migration": true, "sql": "DELETE FROM ensemble_signals WHERE signal_date = '\''2026-03-06'\''"}' /tmp/del.json

# 5. Delete bad portfolio entries
aws lambda invoke --function-name rigacap-prod-worker --profile rigacap --payload '{"run_migration": true, "sql": "DELETE FROM model_positions WHERE id = 79"}' /tmp/del.json

# 6. Fix portfolio state (cash, PnL, trade count)
aws lambda invoke --function-name rigacap-prod-worker --profile rigacap --payload '{"run_migration": true, "sql": "UPDATE model_portfolio_state SET current_cash = X, total_pnl = Y, total_trades = Z WHERE portfolio_type = '\''live'\''"}' /tmp/fix.json
```

## Preventive Measures Needed
- [x] Add scan time guard: `_wait_for_alpaca_settlement()` pre-flight polls SPY bars+volume before bulk fetch, falls back to yfinance if not settled after 5 min
- [ ] Add broader freshness validation beyond just SPY
- [ ] Add CSV export step to normal daily scan pipeline
- [ ] Request Lambda memory increase to 10240 MB (submitted to AWS)
- [ ] Consider pickle-to-/tmp offload to reduce memory pressure during scan
