-- Preserver shadow tables (Phase 2). ADDITIVE — creates two NEW tables; touches nothing
-- existing. Run OFF-HOURS via the worker `{"run_migration": true}` path, verify columns,
-- THEN deploy the SQLAlchemy models + daily-scan hook in a second commit (migration-first).
-- Idempotent (IF NOT EXISTS) so re-running is safe.

-- 1) Daily routed BUY candidates for the Preserver tier (mirrors ensemble_signals + source/regime)
CREATE TABLE IF NOT EXISTS preserver_signals (
    id              SERIAL PRIMARY KEY,
    signal_date     DATE        NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    price           DOUBLE PRECISION,
    source          VARCHAR(20) NOT NULL,          -- t30v | pullback_ma | oversold_bounce
    regime          VARCHAR(20),                   -- 7-regime label that day
    dollar_volume   DOUBLE PRECISION,              -- selection key (20d avg $-vol)
    hold_days       INTEGER,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_preserver_signal_date_symbol UNIQUE (signal_date, symbol)
);
CREATE INDEX IF NOT EXISTS ix_preserver_signals_date   ON preserver_signals (signal_date);
CREATE INDEX IF NOT EXISTS ix_preserver_signals_symbol ON preserver_signals (symbol);
CREATE INDEX IF NOT EXISTS ix_preserver_signals_status ON preserver_signals (status);

-- 2) Daily snapshot of the shadow held book + equity (to track live equity vs research range)
CREATE TABLE IF NOT EXISTS preserver_book_snapshots (
    id              SERIAL PRIMARY KEY,
    snapshot_date   DATE        NOT NULL,
    regime          VARCHAR(20),
    active_source   VARCHAR(20),                   -- which book drove entries today
    equity          DOUBLE PRECISION,              -- mark-to-market book value
    positions_json  JSONB,                         -- [{symbol, source, shares, entry_price, exit_date}]
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_preserver_snapshot_date UNIQUE (snapshot_date)
);
CREATE INDEX IF NOT EXISTS ix_preserver_snapshots_date ON preserver_book_snapshots (snapshot_date);
