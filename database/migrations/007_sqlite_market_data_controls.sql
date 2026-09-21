-- Market data controls: provider symbol mapping and price authority.

CREATE TABLE IF NOT EXISTS market_symbol_mappings (
    id TEXT PRIMARY KEY,
    internal_symbol TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    instrument_type TEXT NOT NULL DEFAULT 'EQUITY',
    expected_currency TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(internal_symbol, provider)
);

CREATE INDEX IF NOT EXISTS idx_market_symbol_mappings_lookup
ON market_symbol_mappings(internal_symbol, provider, status);

CREATE TABLE IF NOT EXISTS price_authority (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    authority_mode TEXT NOT NULL DEFAULT 'AUTO',
    manual_price REAL,
    manual_currency TEXT,
    manual_updated_at TEXT,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
