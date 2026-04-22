---
name: Pickle build playbook — clean data requirements and safety
description: Step-by-step process for building, validating, and deploying pickle files. Includes ETF exclusions, guardrails, and data hygiene checks.
type: project
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
## Pickle Build Playbook

### Pre-Build Checklist
1. **Verify Alpaca API key is valid** (Pro tier for SIP data)
2. **Verify universe source** — `stock_universe.py` loads Alpaca `get_all_assets()` + MUST_INCLUDE list
3. **Set output to staging path** — NEVER write to `prices/all_data.pkl.gz` directly
4. **Use backend venv** with `numpy==1.26.3` (system numpy 2.x breaks pickle compat)

### What Gets Excluded (stock_universe.py EXCLUDED_PATTERNS)
All non-individual-equity instruments:
- **Leveraged/inverse ETFs**: TQQQ, SQQQ, SOXL, SOXS, FAS, FAZ, TSLL, NVDL, etc.
- **1x inverse ETFs**: PSQ, DOG, RWM, SH, etc.
- **Index ETFs**: SPY, QQQ, IWM, DIA, VTI, VOO (customers want stock picks)
- **Sector ETFs**: XLB, XLE, XLF, XLK, XLV, SOXX, SMH, KRE, XBI, GDX, etc.
- **International ETFs**: FXI, KWEB, EEM, EFA, INDA, etc.
- **Commodity ETFs**: GLD, IAU, SLV, USO, UNG, DBC, etc.
- **Bond/Treasury ETFs**: TLT, AGG, BND, LQD, HYG, JNK, etc.
- **Crypto ETFs**: IBIT, FBTC, GBTC, ETHE, BITX, etc.
- **Smart beta/thematic**: SCHD, ARKK, QUAL, MTUM, etc.
- **Volatility products**: UVXY, SVXY, VXX, VIXY
- **Problematic**: DWAC, PHUN

### What Gets Included
- **All individual US equities** from Alpaca asset list where `tradable=True`, `status=active`
- **MUST_INCLUDE list**: Dow 30, major stocks that might get filtered by price/volume (NIO, RIVN, PLTR, etc.)
- **Min requirements**: price > $5, avg volume > 100K
- **SPY stays in pickle** for regime detection (SPY > 200MA) but excluded from signal generation

### Indicators Computed Per Symbol
- `dwap` (200-day Daily Weighted Average Price)
- `ma_50`, `ma_200` (moving averages)
- `vol_avg` (20-day average volume)
- `high_52w` (52-week high)

### Build Command
```bash
source backend/venv/bin/activate
cd backend
caffeinate -i python3 ../scripts/build_10y_pickle.py
```

### Post-Build Validation (BEFORE promoting to production)
1. **Symbol count**: must be ≥ 3,000 (script guardrail aborts below this)
2. **Spot-check**: load pickle, verify major symbols present (AAPL, MSFT, GOOGL, NVDA)
3. **Date range**: first date should match START_DATE, last date should be recent
4. **No ETFs**: grep for SPY in signal universe (should only be in data_cache for regime, not in get_universe())
5. **Indicator columns**: each symbol should have `dwap`, `ma_50`, `ma_200`, `vol_avg`, `high_52w`
6. **File size**: 7y ≈ 120MB compressed, 10y ≈ 300MB+ compressed. If < 50MB, something is wrong.

### Promotion to Production
```bash
# Script uploads to STAGING key automatically
# Verify, then promote:
aws s3 cp s3://rigacap-prod-price-data-149218244179/prices/all_data_STAGING.pkl.gz \
  s3://rigacap-prod-price-data-149218244179/prices/all_data.pkl.gz \
  --profile rigacap --region us-east-1
```

### Emergency Restore
```bash
# Weekly backups exist in prices/backups/
aws s3 ls s3://rigacap-prod-price-data-149218244179/prices/backups/ --profile rigacap
aws s3 cp s3://rigacap-prod-price-data-149218244179/prices/backups/weekly_2026-W16.pkl.gz \
  s3://rigacap-prod-price-data-149218244179/prices/all_data.pkl.gz \
  --profile rigacap --region us-east-1
```

### Known Issues
- **10y pickle OOMs at 3008 MB Lambda** — needs 4096+ MB Worker Lambda
- **Pickle shrink on incremental fetch** is normal — `fetch_incremental` strips indicator columns for lazy recompute (~50% size reduction)
- **Corp-actions check** (Layer 2, deployed Apr 15) catches ticker reuse and silent splits nightly
- **Apr 22, 2026 incident**: build script auto-uploaded 3-symbol pickle to production. Fixed: guardrail + staging key.

Noted Apr 22, 2026.
