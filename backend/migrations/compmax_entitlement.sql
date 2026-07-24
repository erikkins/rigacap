-- compmax — admin COMP entitlement for the Maximizer tier (grant Maximizer without paying).
-- Mirrors has_maxpp_addon: ADDITIVE, one new column on subscriptions, NOT NULL DEFAULT false
-- so existing rows backfill safely + SQLAlchemy SELECTs never break. Migration-FIRST: run this,
-- verify, THEN deploy the model column + serving code that references it (see CLAUDE.md).
--
-- Effective entitlement in code: is_maximizer = has_maxpp_addon (paid) OR compmax (admin comp).
-- Idempotent (IF NOT EXISTS) so re-running is safe.
--
-- RUN (off-hours, not near the 4 PM ET scan) via the worker run_migration handler:
--   aws lambda invoke --function-name rigacap-prod-worker --profile rigacap --region us-east-1 \
--     --cli-read-timeout 120 --payload fileb:///tmp/compmax.json /tmp/out.json
-- where /tmp/compmax.json =
--   {"run_migration": true,
--    "sql": "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS compmax BOOLEAN NOT NULL DEFAULT false"}
-- Verify: {"run_migration": true, "sql": "SELECT column_name FROM information_schema.columns WHERE table_name='subscriptions' AND column_name='compmax'"}
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS compmax BOOLEAN NOT NULL DEFAULT false;
