-- Market data automation foundation.
-- Keeps provider data local, idempotent, and separate from manual fallback.

ALTER TABLE asset_valuations ADD COLUMN provider TEXT;
ALTER TABLE asset_valuations ADD COLUMN retrieved_at TEXT;
ALTER TABLE asset_valuations ADD COLUMN metadata TEXT DEFAULT '{}';

ALTER TABLE benchmark_prices ADD COLUMN provider TEXT;
ALTER TABLE benchmark_prices ADD COLUMN retrieved_at TEXT;
ALTER TABLE benchmark_prices ADD COLUMN metadata TEXT DEFAULT '{}';

CREATE TABLE IF NOT EXISTS fx_rates (
    id TEXT PRIMARY KEY,
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    rate REAL NOT NULL,
    rate_date TEXT NOT NULL,
    provider TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'MARKET_DATA',
    retrieved_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(base_currency, quote_currency, rate_date, provider)
);

CREATE INDEX IF NOT EXISTS idx_fx_rates_pair_date
ON fx_rates(base_currency, quote_currency, rate_date DESC);

CREATE TABLE IF NOT EXISTS market_data_cache (
    cache_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    provider TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_data_config (
    id TEXT PRIMARY KEY DEFAULT 'default',
    provider TEXT NOT NULL DEFAULT 'YFINANCE',
    benchmark_symbol TEXT,
    benchmark_label TEXT,
    benchmark_provider TEXT,
    quote_ttl_minutes INTEGER NOT NULL DEFAULT 720,
    stale_after_days INTEGER NOT NULL DEFAULT 7,
    history_lookback_days INTEGER NOT NULL DEFAULT 365,
    fx_max_age_days INTEGER NOT NULL DEFAULT 5,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO market_data_config (
    id, provider, benchmark_symbol, benchmark_label, benchmark_provider
) VALUES (
    'default', 'YFINANCE', 'SPY', 'SPY ETF', 'YFINANCE'
);
