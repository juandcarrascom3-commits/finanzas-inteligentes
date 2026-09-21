-- Wealth intelligence foundation.
-- Adds idempotent valuation imports and manual benchmark series.

DELETE FROM asset_valuations
WHERE rowid NOT IN (
    SELECT MAX(rowid)
    FROM asset_valuations
    GROUP BY ticker, valuation_date, source
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_valuations_identity
ON asset_valuations(ticker, valuation_date, source);

CREATE TABLE IF NOT EXISTS benchmark_prices (
    id TEXT PRIMARY KEY,
    benchmark_key TEXT NOT NULL,
    label TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    valuation_date TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'MANUAL',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(benchmark_key, valuation_date, source)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_prices_key_date
ON benchmark_prices(benchmark_key, valuation_date DESC);
