-- Maximizer shadow tables. ADDITIVE — creates two NEW tables; touches nothing existing.
-- Parallel to preserver_shadow_tables.sql. Run via the worker `{"run_migration": true}` path,
-- verify, THEN deploy the models + daily-scan hook. Idempotent (IF NOT EXISTS).

-- 1) Daily routed BUY candidates for the Maximizer tier (source can also be 'breakout')
CREATE TABLE IF NOT EXISTS maximizer_signals (
    id              SERIAL PRIMARY KEY,
    signal_date     DATE        NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    price           DOUBLE PRECISION,
    source          VARCHAR(20) NOT NULL,          -- t30v | pullback_ma | oversold_bounce | breakout
    regime          VARCHAR(20),                   -- 7-regime label that day
    dollar_volume   DOUBLE PRECISION,              -- selection key (20d avg $-vol)
    hold_days       INTEGER,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_maximizer_signal_date_symbol UNIQUE (signal_date, symbol)
);
CREATE INDEX IF NOT EXISTS ix_maximizer_signals_date   ON maximizer_signals (signal_date);
CREATE INDEX IF NOT EXISTS ix_maximizer_signals_symbol ON maximizer_signals (symbol);
CREATE INDEX IF NOT EXISTS ix_maximizer_signals_status ON maximizer_signals (status);

-- 2) Daily snapshot of the shadow held book (carries cash + positions + vol-brake eq_hist)
CREATE TABLE IF NOT EXISTS maximizer_book_snapshots (
    id              SERIAL PRIMARY KEY,
    snapshot_date   DATE        NOT NULL,
    regime          VARCHAR(20),
    active_source   VARCHAR(20),                   -- which book drove entries today
    equity          DOUBLE PRECISION,              -- mark-to-market book value
    positions_json  JSONB,                         -- {cash, positions:[...], eq_hist:[...]}
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_maximizer_snapshot_date UNIQUE (snapshot_date)
);
CREATE INDEX IF NOT EXISTS ix_maximizer_snapshots_date ON maximizer_book_snapshots (snapshot_date);
