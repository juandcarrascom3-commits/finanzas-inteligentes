-- ====================================================================
-- FINANZAS INTELIGENTES: SQLITE LOCAL SCHEMA MIGRATION
-- Migration: 001_sqlite_local.sql
-- ====================================================================

-- 1. Table: transactions
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    account_id TEXT,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    date TEXT NOT NULL, -- ISO-8601 string
    description TEXT DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT NOT NULL DEFAULT 'DEMO',
    external_id TEXT,
    raw_payload TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_source_external_unique
ON transactions(source, external_id)
WHERE external_id IS NOT NULL AND external_id != '';
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'cash',
    currency TEXT NOT NULL DEFAULT 'USD',
    opening_balance REAL NOT NULL DEFAULT 0,
    current_balance REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'MANUAL',
    external_id TEXT,
    last_synced_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    flow_type TEXT NOT NULL DEFAULT 'EXPENSE',
    source TEXT NOT NULL DEFAULT 'MANUAL',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS budgets (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL UNIQUE,
    monthly_limit REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT NOT NULL DEFAULT 'MANUAL',
    period TEXT NOT NULL DEFAULT 'MONTHLY',
    is_active INTEGER NOT NULL DEFAULT 1,
    external_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recurring_rules (
    id TEXT PRIMARY KEY,
    merchant TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    account_id TEXT,
    typical_amount REAL NOT NULL DEFAULT 0,
    frequency TEXT NOT NULL DEFAULT 'monthly',
    status TEXT NOT NULL DEFAULT 'detected',
    source TEXT NOT NULL DEFAULT 'DETECTED',
    external_id TEXT,
    next_expected TEXT,
    last_seen TEXT,
    raw_payload TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monthly_review_snapshots (
    id TEXT PRIMARY KEY,
    period TEXT NOT NULL UNIQUE,
    generated_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'SYSTEM',
    summary_payload TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

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
    source TEXT NOT NULL DEFAULT 'DEMO',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_sector ON assets(sector);

CREATE TABLE IF NOT EXISTS asset_valuations (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL REFERENCES assets(ticker) ON DELETE CASCADE,
    price REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    valuation_date TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'MANUAL',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS source_sync_state (
    source TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'NOT_CONFIGURED',
    last_sync_at TEXT,
    last_success_at TEXT,
    last_error TEXT,
    last_data_change_at TEXT,
    last_data_change_rev TEXT,
    sync_in_progress TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_mappings (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    external_name TEXT,
    local_id TEXT,
    local_type TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_type, external_id)
);

CREATE TABLE IF NOT EXISTS action_events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO',
    message TEXT NOT NULL,
    payload TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
