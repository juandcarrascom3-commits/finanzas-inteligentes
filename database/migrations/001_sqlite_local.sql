-- ====================================================================
-- FINANZAS INTELIGENTES: SQLITE LOCAL SCHEMA MIGRATION
-- Migration: 001_sqlite_local.sql
-- ====================================================================

-- 1. Table: transactions
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    date TEXT NOT NULL, -- ISO-8601 string
    raw_payload TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);

-- 2. Table: assets
CREATE TABLE IF NOT EXISTS assets (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL, -- 'Renta Variable', 'Efectivo', 'Alternativos'
    sector TEXT NOT NULL,     -- 'Tecnología', 'Consumo', 'Financiero', 'Cripto', 'Energía'
    country TEXT NOT NULL,    -- 'EE.UU.', 'Colombia', 'Global'
    quantity REAL NOT NULL DEFAULT 0,
    avg_price REAL NOT NULL DEFAULT 0,
    current_price REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    is_watchlist INTEGER DEFAULT 0, -- 0 = false, 1 = true
    logo_url TEXT,
    target_allocation_pct REAL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_sector ON assets(sector);

-- 3. Table: investment_theses
CREATE TABLE IF NOT EXISTS investment_theses (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL REFERENCES assets(ticker) ON DELETE CASCADE,
    thesis_text TEXT NOT NULL,
    valuation_grade INTEGER CHECK (valuation_grade BETWEEN 1 AND 5),
    timing_context TEXT,
    safety_margin REAL NOT NULL DEFAULT 0.00,
    checklist_passed INTEGER NOT NULL DEFAULT 0,
    criteria_details TEXT DEFAULT '{"knows_business_model":false,"debt_ebitda_healthy":false,"margin_safety_above_20":false,"timing_not_overbought":false,"emotional_bias_checked":false}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_investment_theses_ticker ON investment_theses(ticker);

-- 4. Table: geopolitical_risk
CREATE TABLE IF NOT EXISTS geopolitical_risk (
    region TEXT PRIMARY KEY,
    active_risk_score REAL NOT NULL,
    anomaly_alert INTEGER NOT NULL DEFAULT 0,
    headline TEXT,
    last_assessed TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 5. Table: budgetbakers_mappings
CREATE TABLE IF NOT EXISTS budgetbakers_mappings (
    id TEXT PRIMARY KEY,
    bb_category_name TEXT NOT NULL UNIQUE,
    local_category TEXT NOT NULL,
    flow_type TEXT NOT NULL, -- 'INCOME', 'EXPENSE', 'TRANSFER'
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 6. Table: api_request_cache & api_daily_quota
CREATE TABLE IF NOT EXISTS api_request_cache (
    cache_key TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    response_payload TEXT NOT NULL,
    cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_daily_quota (
    date_key TEXT PRIMARY KEY, -- 'YYYY-MM-DD'
    request_count INTEGER NOT NULL DEFAULT 0,
    max_quota INTEGER NOT NULL DEFAULT 25,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
