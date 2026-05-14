---
name: main.py housekeeping — extract Lambda event handlers into modules
description: backend/main.py is 9,228 lines and 90+ event-based handler branches. Refactor target: extract by domain (diagnostics, scheduled jobs, newsletter, WF, data storage) so the main handler dispatches instead of switching.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
`backend/main.py` is at **9,228 lines / 90+ event handler branches** as of May 13 2026. Every new Lambda event (cron, diagnostic, admin-invoke) lands in the same monolithic handler() function — diff churn is high, navigation is painful, and the file is a magnet for unrelated work.

## What's in there (rough groupings)

The Lambda `handler()` function in main.py is a sequence of `if event.get("<event_name>"): ...` branches. They cluster naturally by domain:

| Cluster | Sample events | Approx scope |
|---------|---------------|--------------|
| **Diagnostics / admin-invoke** | `pickle_validate`, `parquet_alignment_heal`, `parquet_divergence_inspect`, `parquet_diagnose`, `parquet_query`, `signal_month_analysis`, `data_quality_diagnostic`, `signal_diagnostic`, `test_parquet_roundtrip`, `wf_query` | Read-only Lambda-invoke endpoints. Grows steadily as new "let me check X" handlers get added. |
| **Scheduled scan / pipeline** | `daily_scan`, `intraday_monitor`, `csv_export_from_scan`, `pickle_rebuild_from_scan`, `pickle_rebuild`, `nightly_data_hygiene`, `ticker_health_check`, `engagement_opportunities`, `pipeline_health` | EventBridge cron destinations. Long-running, often chain to other events. |
| **Newsletter** | `generate_newsletter`, `market_measured`, `newsletter_draft_saturday` | Sat-gen + Sun-publish flow. Two recent bug fixes here (May 13). |
| **Walk-forward** | `walk_forward_job`, `nightly_wf_job`, `wf_query`, `save_wf_from_scan`, `save_wf_from_s3`, `backtest_request`, `ai_optimization_job` | Chunked self-chaining runner + diagnostics. The nightly chunking fix landed May 12. |
| **Email / lifecycle** | `daily_emails`, `double_signals`, `weekly_regime_report`, `onboarding_drip`, `new_user_check`, `monthly_recap`, `winback`, `password_reset`, `verify_email` | Subscriber lifecycle + admin notifications. |
| **Social / content** | `generate_social_posts`, `publish_posts`, `post_notifications`, `test_ai_content` | "We Called It" pipeline + Twitter/IG/Threads publish. |
| **Token refresh / housekeeping** | `meta_token_refresh`, `ig_token_refresh`, `warmer` | OAuth maintenance + Lambda warmer. |
| **Strategy / portfolio mgmt** | `strategy_analysis`, `model_portfolio`, `debug_user_portfolio_simulate`, `wf_fail` | Model-portfolio + WF-job state transitions. |

## Refactor target

Move each cluster into `backend/app/lambda_events/<domain>.py`, where each module exports a `try_handle(event, context) -> Optional[dict]` function. The Lambda `handler()` in main.py then becomes:

```python
from app.lambda_events import diagnostics, scheduled, newsletter, walk_forward, emails, social, tokens, strategy
HANDLERS = [diagnostics, scheduled, newsletter, walk_forward, emails, social, tokens, strategy]
def handler(event, context):
    for h in HANDLERS:
        result = h.try_handle(event, context)
        if result is not None:
            return result
    # fall through to FastAPI/Mangum for HTTP requests
    return _mangum_handler(event, context)
```

Each module owns its event-name predicate(s) and the implementation. main.py shrinks to ~500-1000 lines (FastAPI setup + Mangum wiring + dispatch list).

## Why not do it now

- **Touches every active codepath at once.** Concurrent feature work (parquet migration, newsletter fixes) would conflict heavily during the refactor window.
- **Test coverage on Lambda event branches is thin.** Each branch is essentially integration-tested via prod invocation; moving them around without contract tests risks silent regressions.
- **No active pain.** The size is annoying but not blocking. Branches are usually self-contained (most are <100 lines), so the navigation problem is grep-soluble.

## When to do it

Trigger conditions:
1. **A merge conflict in main.py blocks shipping.** Two branches both touching the giant `handler()` function fight on every PR.
2. **A new contributor or AI-pair-programmer struggles to find the right branch.** That's the practical signal that 90 branches has crossed a usability threshold.
3. **Quarterly housekeeping window** — pair with one parquet-migration cutover quiet period.

## How to apply (when the time comes)

1. **Start with the diagnostics cluster** — they're read-only, easiest to test, and their growth rate is the highest (so the relief is biggest there).
2. **One module per PR.** Don't bundle. Each module-extraction should ship in isolation with a verification invoke of every event it owns.
3. **Preserve event names verbatim.** EventBridge crons + manual invocation tooling reference these strings; renaming them is out of scope.
4. **Keep main.py's `_run_async` helper, `_lambda_data_loaded` flag, and singleton-loading dance** intact and importable from `app.lambda_events.common` — those are shared across event handlers.

## Connected

- `feedback_lambda_payload_truthy.md` — the truthy-payload rule applies to every dispatched handler.
- `project_admin_run_sql_handler.md` — proposed `run_sql` handler should land in the new `diagnostics` module, not main.py.
