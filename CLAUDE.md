# CLAUDE.md - Stocker Trading System

> This file provides context for Claude Code CLI. It captures the full history and decisions from our development session.

## Project Overview

**Stocker** is a momentum-based stock trading system with a React dashboard and FastAPI backend, designed for deployment on AWS.

## Trading Strategy v2 (Momentum)

The current strategy uses momentum-based ranking with market regime filtering:

```
BUY SIGNAL (Momentum Ranking):
- 10-day momentum (short-term)
- 60-day momentum (long-term)
- Composite score: short_mom × 0.5 + long_mom × 0.3 - volatility × 0.2
- Quality filter: Price > MA20 and MA50 (uptrend)
- Breakout filter: Within 5% of 50-day high
- Volume > 500,000
- Price > $20

SELL RULES:
- Trailing Stop: 15% from high water mark
- Market Regime Exit: SPY < 200-day MA → close all positions

PORTFOLIO:
- Max 5 positions
- 18% of portfolio per position
- Weekly rebalancing (Fridays)
```

**Backtest Results (2021-2026, 5 years):**
- 263% total return (29% annualized)
- 1.15 Sharpe ratio
- -14.2% max drawdown
- 49% win rate

**Recent Performance (2021-2026, 5 years):**
- 95% total return (14% annualized)
- 1.19 Sharpe ratio
- -10.5% max drawdown
- 47% win rate

## Legacy Strategy (DWAP)

The original DWAP strategy is still available for backward compatibility:

```
BUY SIGNAL:
- Price > DWAP × 1.05 (5% above 200-day Daily Weighted Average Price)
- Volume > 500,000
- Price > $20

SELL RULES:
- Stop Loss: -8%
- Profit Target: +20%
```

## Key Strategy Improvements (v1 → v2)

| Aspect | v1 (DWAP) | v2 (Momentum) |
|--------|-----------|---------------|
| Entry | DWAP threshold | Momentum ranking |
| Positions | 15 @ 6.6% | 5 @ 18% |
| Stop Loss | Fixed 8% | 15% trailing |
| Profit Target | Fixed 20% | Let winners run |
| Market Filter | None | SPY > 200MA |
| Rebalancing | Daily | Weekly |
| Sharpe | 0.19 | 1.48 |

## Ensemble Strategy (Current Production)

The Ensemble strategy (strategy_id: 5, type: `ensemble`) combines DWAP timing + momentum quality + trailing stops + 7-regime market detection. This is the proprietary differentiator and centerpiece of all marketing.

```
ENTRY (3-factor ensemble):
1. TIMING: Price > DWAP × 1.05 (catches early breakouts)
2. QUALITY: Top momentum ranking (10d/60d composite)
3. CONFIRMATION: Near 50-day high, volume spike × 1.3

EXIT:
- Trailing Stop: 12% from high water mark
- Market Regime Filter: Adapts across 7 regimes

PORTFOLIO:
- Max 6 positions @ 15% each
- Biweekly rebalancing
```

**Walk-Forward Results (2021-2026, 5 years, no hindsight bias):**

| Year | Return | S&P 500 |
|------|--------|---------|
| 2021 | +4.6% | +21.0% |
| 2022 | +6.2% | -20.4% |
| 2023 | +0.3% | +23.4% |
| 2024 | +83.2% | +23.8% |
| 2025 | +17.8% | +18.3% |
| **5-Year Avg** | **+208%** | **+84%** |

- ~25% annualized return (avg across multiple start dates)
- 0.88 Sharpe ratio
- All years positive regardless of start date
- 10-Year: +680% ($10k → $78k), 22% annualized

## Architecture

```
Frontend (React + Vite + TailwindCSS)
    ↓
API Gateway / CloudFront
    ↓
Backend (FastAPI on Lambda)
    ↓
PostgreSQL (RDS) + Redis (ElastiCache)
    ↓
DualSourceProvider (market_data_provider.py)
    ├── Alpaca (primary for historical daily bars - faster, more reliable)
    ├── yfinance (primary for live quotes + index symbols + fallback)
    └── Auto-failover with health tracking
```

## Market Data Sources (Dual-Source Architecture)

After a 2-day stale data incident (Feb 26-27, 2026), the data pipeline uses dual sources with automatic failover:

| Use Case | Primary | Fallback | Reason |
|----------|---------|----------|--------|
| Daily scan (EOD bars) | Alpaca | yfinance | Alpaca faster/more reliable for bulk historical |
| Live intraday quotes | yfinance | Alpaca | Alpaca free = IEX only, yfinance = all exchanges |
| VIX / index data | yfinance | — | Alpaca doesn't serve index symbols (^VIX, ^GSPC) |
| Sector ETF bars | Alpaca | yfinance | Normal tickers, Alpaca-compatible |

**Key files:**
- `backend/app/services/market_data_provider.py` — AlpacaProvider, YfinanceProvider, DualSourceProvider
- `GET /api/market-data-status` — Public endpoint for frontend staleness banner
- Lambda handler `compare_data_sources` — A/B validation between sources

**Auto-retry:** If >10% of symbols fail during daily scan, automatically retries with yfinance fallback.

**Frontend banner:** Polls `/api/market-data-status` — shows blue "processing" during 4-4:45 PM ET, amber "stale" if data is late.

**Alpaca free tier constraints:**
- 200 req/min rate limit, batches of 100 symbols
- 15-minute delay (non-issue for EOD bars fetched after 4 PM)
- Cannot serve index symbols (^VIX, ^GSPC)

## Project Structure

```
stocker-app/
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main dashboard with charts, auth, trade flow
│   │   ├── main.jsx         # React entry point
│   │   └── index.css        # Tailwind styles
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── Dockerfile
├── backend/
│   ├── main.py              # FastAPI app with all endpoints
│   ├── services/
│   │   ├── scanner.py       # DWAP signal generation
│   │   ├── indicators.py    # Technical indicators
│   │   └── stocker_live.py  # Live scanning system
│   ├── requirements.txt
│   └── Dockerfile
├── infrastructure/
│   └── terraform/
│       └── main.tf          # AWS: S3, CloudFront, Lambda, API Gateway, RDS
├── docker-compose.yml       # Local development stack
└── .github/workflows/
    └── deploy.yml           # CI/CD pipeline
```

## Launch Readiness Audit (updated 2026-02-18)

### Done — Production Ready

| Area | Status | Details |
|------|--------|---------|
| **Core Product** | DONE | Dashboard, signals, positions, charts, simple/advanced modes, time-travel (admin) |
| **Auth** | DONE | Google OAuth, Apple Sign In, email/password, JWT tokens, password reset |
| **Payments** | DONE | Stripe Checkout, 7-day trial (CC required), cancel via Customer Portal, webhooks |
| **Email** | DONE | Welcome, daily digest (6 PM ET), sell alerts (intraday), double-signal alerts, password reset, post approval notifications, SPF/DKIM/DMARC configured, List-Unsubscribe (RFC 8058) |
| **Data Pipeline** | DONE | Daily scan (4 PM ET via EventBridge), yfinance, S3 caching, pre-computed dashboard JSON. **Freshness gate:** all email/communication jobs validate daily scan ran successfully today before sending; stale data → emails HELD + admin alert. Manual override: pass `target_emails` to bypass. |
| **Infrastructure** | DONE | Lambda + ECR, CloudFront CDN, Route53, ACM SSL, API Gateway, CI/CD (GitHub Actions) |
| **Legal** | DONE | Terms of Service, Privacy Policy (GDPR/CCPA), financial disclaimer, contact page |
| **Security** | DONE | CORS whitelist, JWT auth, bcrypt passwords, Turnstile bot protection, S3 private (no public signal access), admin-only routes, subscription gating |
| **Broker Disclaimer** | DONE | "Signals only — execute via your broker" in dashboard, tour, landing page, FAQ, welcome email |
| **OG / Social** | DONE | OpenGraph + Twitter Card meta tags, launch card PNGs |
| **Error Handling** | DONE | React ErrorBoundary wraps entire app |
| **GA4 Analytics** | DONE | Measurement ID `G-0QKQRXTFSX` configured in index.html |
| **Landing Page Copy** | DONE | "Credit card required" in 3 places (monthly, annual, CTA), hero spacing fixed |
| **"We Called It" Engine** | DONE | Full AI-powered social content pipeline (see below) |
| **Deep Intelligence Suite** | DONE | AI trade autopsies, ghost portfolios (3 parallel universes), regime shift forecast dashboard, "What If You Followed Us" calculator |

### "We Called It" Content Engine (added 2026-02-17)

AI-powered social media automation: real walk-forward trades → Claude API content → admin approval → auto-publish.

| Component | Status | Details |
|-----------|--------|---------|
| **AI Content Generation** | DONE | `ai_content_service.py`: Claude Sonnet 4.5 generates posts from real trade data. 3 post types: `trade_result`, `missed_opportunity`, `we_called_it`. Template fallback if API unavailable. Markdown stripping + char limit enforcement. |
| **Post Scheduler** | DONE | `post_scheduler_service.py`: Auto-schedules drafts across optimal windows (9/12/17 weekday, 10/14 weekend). Spreads posts 1-3 days out, max 4/day. |
| **Admin Approval Pipeline** | DONE | T-24h and T-1h email notifications with post preview + one-click JWT-signed cancel link. |
| **Auto-Publish** | DONE | Cron job every 15min publishes approved posts when `scheduled_for <= now` via Twitter API v2 + Instagram Graph API. |
| **Notification Checks** | DONE | Hourly cron sends T-24h/T-1h notifications for upcoming posts. |
| **Social Tab UI** | DONE | Schedule/cancel buttons, AI badge (sparkle icon), scheduled/cancelled status filters, scheduled_for datetime display. |
| **API Endpoints** | DONE | `POST /schedule`, `POST /cancel`, `GET /cancel-email?token=` (JWT one-click), `POST /regenerate-ai` |
| **Lambda Handlers** | DONE | `test_ai_content` (single post test), `generate_social_posts` (bulk from WF trades with clear_existing option) |
| **DB Columns** | DONE | `ai_generated`, `ai_model`, `ai_prompt_hash`, `news_context_json`, `notification_24h_sent`, `notification_1h_sent` |

### Gaps — Pre-Launch / First Month

| Item | Priority | Status | Notes |
|------|----------|--------|-------|
| **Cookie consent banner** | MEDIUM | DONE | GDPR consent banner for GA4 |
| **CloudWatch alarms** | MEDIUM | DONE | 8 alarms (Lambda errors/throttles/duration, API 5xx/4xx, RDS CPU/storage/connections) → SNS email |
| **Mobile responsive polish** | MEDIUM | DONE | Header, metric grids, tables, modals — tested on phone |
| **Custom 404 page** | LOW | DONE | Dark theme catch-all with back-to-home button |
| **Email deliverability** | HIGH | DONE | SPF + DKIM + DMARC DNS records, List-Unsubscribe + List-Unsubscribe-Post headers (RFC 8058) |
| **Email verification** | LOW | DEFERRED | Not critical — Stripe CC verification is stronger |

### Growth — Road to 5,000 Subscribers

| Item | Status | Notes |
|------|--------|-------|
| **"We Called It" social proof** | READY | AI posts auto-generated nightly from real trades, scheduled + published |
| **Public track record page** | DONE | /track-record with walk-forward data, linked from hero + welcome email + social posts |
| **Referral program** | DONE | "Give a month, get a month" — unique 8-char codes, Stripe coupon at checkout, referrer rewarded on trial→paid conversion, welcome email referral section, dashboard modal with copy link |
| **Onboarding email drip** | DONE | 5-step drip over 8 days: how signals work (D1), pro tips (D3), trial ending (D5), last day (D6), win-back w/ 20% off (D8). EventBridge 10 AM ET daily. |
| **Social proof / testimonials** | TODO | Landing page section with real user results |
| **Content / SEO strategy** | TODO | Blog posts, market commentary — organic discovery |
| **Churn prevention** | TODO | Cancel survey, win-back emails, usage alerts |
| **User performance dashboard** | DONE | "Your RigaCap Journey" card — personalized what-if from signup date vs SPY, shareable results |

### Key Metrics to Track (GA4 live)
- Landing page → trial signup conversion rate
- Trial → paid conversion rate (target: 3-5%)
- Monthly churn rate (target: <5%)
- CAC by channel (organic, social, paid)
- Revenue per signal-engagement (do users who act on more signals retain better?)
- Social post engagement (clicks, impressions) — AI vs template content performance
- Email-to-post time (nightly WF → published post, goal: 24-48h)

## Data Sources

**Primary: yfinance (Yahoo Finance)**
- Free, unlimited, no API key
- 20+ years historical daily OHLCV
- All US stocks, ETFs
- Split/dividend adjusted

```python
import yfinance as yf
df = yf.download("AAPL", period="2y")
```

**Stock Universe:**
- NASDAQ-100 (~100 stocks)
- S&P 500 additions (~50 stocks)
- Excludes: VXX, UVXY, TQQQ, SQQQ, FAS, FAZ, etc.

## Commands

### Local Development
```bash
# Docker (easiest)
docker-compose up

# Manual
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

### Lambda Container Deployment

**CRITICAL: AWS Lambda requires single-platform linux/amd64 images.**

Docker BuildKit creates multi-platform manifest lists with attestations that Lambda rejects with:
> "The image manifest, config or layer media type is not supported"

Always use `--provenance=false --sbom=false` when building Lambda container images:

```bash
# Build Lambda-compatible image
cd backend
docker buildx build --platform linux/amd64 --provenance=false --sbom=false -f Dockerfile.lambda -t rigacap-prod-api:latest --load .

# Or use the deploy script which handles this automatically:
./scripts/deploy-container.sh
```

**Note:** The Lambda init phase has a 10-second timeout. Database connections are initialized lazily on first request to avoid this timeout.

**CRITICAL: NEVER use `aws lambda update-function-configuration --environment`** to force cold starts or change a single env var. This flag **REPLACES ALL environment variables**, wiping DATABASE_URL, Stripe keys, JWT secrets, etc. — causing a full production outage. To force a cold start, use `aws lambda update-function-code` with the current image URI instead.

### Invoking Lambda Directly (IMPORTANT)

**API Gateway has a 29-second timeout.** For long-running operations (walk-forward simulations, backtests, AI optimization), you MUST invoke Lambda directly:

```bash
# Create payload file
cat > /tmp/payload.json << 'EOF'
{
  "walk_forward_job": {
    "start_date": "2024-02-06",
    "end_date": "2026-02-06",
    "frequency": "biweekly",
    "min_score_diff": 10.0,
    "enable_ai": false,
    "max_symbols": 100
  }
}
EOF

# Invoke Lambda directly (bypasses API Gateway timeout)
aws lambda invoke \
  --function-name rigacap-prod-api \
  --region us-east-1 \
  --invocation-type RequestResponse \
  --payload fileb:///tmp/payload.json \
  --cli-read-timeout 600 \
  /tmp/result.json

# Check results
cat /tmp/result.json | python3 -m json.tool
```

**DO NOT:**
- Call API Gateway endpoints for long operations (will timeout at 29s)
- Try to run simulations locally (no database/data available)

**Lambda payload types:**
- `walk_forward_job`: Walk-forward simulation
- `backtest_job`: Single backtest run
- `ai_optimization_job`: AI parameter optimization

### Deployment

**CRITICAL: Database migration safety.** NEVER deploy new SQLAlchemy model columns and the DB migration in the same commit. SQLAlchemy auto-includes all model columns in SELECT queries — if the column doesn't exist in the DB, ALL queries break (including auth), causing full outage. Use the **migration-first pattern:**
1. Deploy migration SQL only (via `run_migration` Lambda event or admin endpoint)
2. Run migration, verify columns exist
3. THEN deploy the SQLAlchemy model changes in a second commit

**NEVER deploy breaking schema changes during business hours.** Schedule for off-hours or use the pattern above.

**Emergency migration:** Invoke `{"run_migration": true}` on the worker Lambda — it runs ALTER TABLE directly without needing auth.

**CI/CD handles deployment automatically** — pushing to `main` triggers GitHub Actions which builds and deploys the Lambda container. Do NOT run `scripts/deploy-container.sh` manually unless CI/CD is broken.

**Terraform** (infrastructure changes only — not needed for code deploys):

**IMPORTANT:** Always use `AWS_PROFILE=rigacap` for terraform commands. The default AWS profile points to a different account (774558858301). The rigacap account is 149218244179.

```bash
cd infrastructure/terraform
terraform init
AWS_PROFILE=rigacap terraform apply -var="lambda_image_tag=latest"
```

## Original Context

This project is a rebuild of a legacy Azure SQL stock prediction tool. The original system had:
- 48 database tables
- 45 technical indicators
- 46 trading rules in 127 stored procedures
- Daily Weighted Average Price (DWAP) as primary indicator

We ported the best-performing rules to Python, backtested extensively, and built a modern React + FastAPI stack.

## Session History Summary

1. Analyzed legacy model.xml (1.4MB) with full database schema
2. Extracted 46 trading rules from stored procedures
3. Implemented indicators in Python (indicators.py)
4. Built backtesting engine (backtester.py)
5. Ran comprehensive optimization (35+ combinations)
6. Identified winning strategy: DWAP 5% / Stop 8% / Target 20%
7. Built React dashboard with charts and auth
8. Created AWS infrastructure (Terraform)
9. Set up CI/CD (GitHub Actions)
10. **Upgraded to Momentum Strategy v2** (Sharpe 1.48)
    - Momentum-based ranking (10/60 day)
    - Trailing stops (15%)
    - Weekly rebalancing
    - Market regime filter (SPY > 200MA)

## PDF Documents

Two professional PDF documents are maintained and regenerated as features evolve:

**Investor Report** (`design/documents/rigacap-investor-report.html` → `.pdf`)
- Navy+gold brand styling, cover page with SVG spire logo
- Executive summary, walk-forward performance, ensemble approach, 7-regime intelligence
- AI/ML section (Optuna, adaptive scoring), "We Called It" content engine
- Platform architecture, subscriber experience, growth roadmap

**Technical Architecture** (`design/documents/rigacap-technical-architecture.html` → `.pdf`)
- Full tech audit: AWS infra, database schema (17 tables), 85 API endpoints
- Backend services (20+), frontend components, security architecture
- CI/CD pipeline, monitoring, performance characteristics, dependencies

**To regenerate PDFs:**
```bash
# Edit the HTML source files, then convert:
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header \
  --print-to-pdf="design/documents/rigacap-investor-report.pdf" \
  design/documents/rigacap-investor-report.html

"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header \
  --print-to-pdf="design/documents/rigacap-technical-architecture.pdf" \
  design/documents/rigacap-technical-architecture.html
```

## Generating PNG Images from Canvas HTML

Social launch cards (`design/brand/social-launch-cards.html`) render to `<canvas>` elements via JavaScript. The source HTML contains shared helper functions (`drawLogo`, `fillNavyGradient`, `drawGoldLine`, etc.) that all cards depend on.

**To regenerate a single card (e.g., card3):**

1. Extract ALL the JS from the source HTML (helpers are shared)
2. Create a wrapper HTML with all 5 canvases but only the target visible:
```python
# Extract JS and build isolated page
python3 -c "
import re
with open('design/brand/social-launch-cards.html') as f:
    html = f.read()
js = re.search(r'<script>(.*?)</script>', html, re.DOTALL).group(1)
page = '''<!DOCTYPE html>
<html><head><meta charset=\"UTF-8\"></head>
<body style=\"margin:0;padding:0;overflow:hidden;background:#172554;\">
<canvas id=\"card1\" width=\"1080\" height=\"1350\" style=\"display:none;\"></canvas>
<canvas id=\"card2\" width=\"1080\" height=\"1350\" style=\"display:none;\"></canvas>
<canvas id=\"card3\" width=\"1080\" height=\"1350\" style=\"display:block;\"></canvas>
<canvas id=\"card4\" width=\"1080\" height=\"1350\" style=\"display:none;\"></canvas>
<canvas id=\"card5\" width=\"1080\" height=\"1350\" style=\"display:none;\"></canvas>
<script>''' + js + '</script></body></html>'
with open('/tmp/card3-only.html', 'w') as f:
    f.write(page)
"
```
3. Screenshot with headless Chrome at exact canvas dimensions:
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu \
  --screenshot="/tmp/card3.png" \
  --window-size=1080,1350 \
  "file:///tmp/card3-only.html"
```
4. Copy to `frontend/public/launch-cards/launch-N.png`

**Important:** Do NOT create standalone JS — the cards share helper functions (`drawLogo`, `fillNavyGradient`, `drawGoldLine`, color constants like `NAVY = '#172554'`). Always extract the full `<script>` block and include all canvas elements (hidden ones fail silently).

## Lambda Architecture (API + Worker Split)

Two Lambda functions from the same Docker image, separated by `LAMBDA_ROLE` env var:

- **API Lambda** (`rigacap-prod-api`): `LAMBDA_ROLE=api`, 1024 MB, 30s timeout. Handles HTTP requests only. Skips pickle loading entirely — dashboard reads S3 JSON cache, positions from DB. Fast cold starts (~2-3s).
- **Worker Lambda** (`rigacap-prod-worker`): `LAMBDA_ROLE=worker`, 4096 MB, 900s timeout. Handles all EventBridge jobs (daily scan, emails, WF simulations, social publishing, pickle rebuild). Loads full 2+ GB pickle on cold start.

Both Lambdas share the same IAM role. Self-invocations (chained jobs) use `WORKER_FUNCTION_NAME` env var.

**Manual invoke always targets worker:**
```bash
aws lambda invoke --function-name rigacap-prod-worker --profile rigacap ...
```

## Security Review Cadence

Run a security audit every 2-3 weeks. Verify:

- All signal/dashboard/portfolio endpoints require auth (`require_valid_subscription` or `get_current_user`)
- S3 price-data bucket is private (block all public access)
- No signal data served via CDN or public S3 — all signal data flows through authenticated Lambda
- CORS whitelist in API Gateway and FastAPI middleware matches only `rigacap.com` + localhost dev
- Any new endpoints added since last review have proper auth guards
- No secrets in frontend bundle or git history

## Code Style

- Python: Black formatter, type hints preferred
- JavaScript: ESLint + Prettier, functional components, hooks
- Use Tailwind CSS for styling (no separate CSS files)
- Keep components in single files when under 500 lines
