-- Maximizer add-on entitlement (2-tier launch, Track B). ADDITIVE — one new column on
-- subscriptions, NOT NULL DEFAULT false so existing rows backfill safely + SQLAlchemy
-- SELECTs never break. Migration-FIRST: run this, verify, THEN deploy the model column +
-- webhook/checkout code that references it. Idempotent (IF NOT EXISTS).
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS has_maxpp_addon BOOLEAN NOT NULL DEFAULT false;
