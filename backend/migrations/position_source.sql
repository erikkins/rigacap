-- positions.source — scope each trade to the STRATEGY that opened it, so the exit rule
-- follows the trade (not the user's current tier). A 'preserver' trade rides the 30%
-- trailing stop; a 'breakout' (Maximizer) trade rides the 29-trading-day time-stop.
-- Upgrading or downgrading tier must NEVER re-manage an already-open trade. A single
-- Maximizer user holds a MIX: breakout names (rotating_bull) + preserver names (every
-- other regime, since Maximizer == Preserver outside rotating_bull).
--
-- ADDITIVE: one new column, NOT NULL DEFAULT 'preserver' so existing rows backfill safely
-- (all historical entries were Core/Preserver = trailing-stop) + SQLAlchemy SELECTs never
-- break. 'preserver' (not internal 't30v') is the customer-facing label. Migration-FIRST:
-- run this, verify, THEN deploy the model column + entry/guidance code. Idempotent.
--
-- RUN (off-hours) via the worker run_migration handler with custom sql:
--   {"run_migration": true,
--    "sql": "ALTER TABLE positions ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'preserver'"}
ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'preserver';
