-- ====================================================================
-- FINANZAS INTELIGENTES: SUPABASE POSTGRESQL SCHEMA MIGRATION
-- Migration: 001_supabase_postgresql.sql
-- ====================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Table: transactions
-- Stores raw BudgetBakers payloads and normalized transaction records
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    amount NUMERIC(15, 2) NOT NULL,
    category VARCHAR(100) NOT NULL,
    date TIMESTAMP WITH TIME ZONE NOT NULL,
    raw_payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);

-- 3. Table: assets
-- Normalized portfolio and watchlist assets
CREATE TABLE IF NOT EXISTS assets (
    ticker VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    asset_type VARCHAR(50) NOT NULL, -- 'Renta Variable', 'Efectivo', 'Alternativos'
    sector VARCHAR(50) NOT NULL,     -- 'Tecnología', 'Consumo', 'Financiero', 'Cripto', 'Energía'
    country VARCHAR(50) NOT NULL,    -- 'EE.UU.', 'Colombia', 'Global'
    quantity NUMERIC(18, 6) NOT NULL DEFAULT 0,
    avg_price NUMERIC(15, 4) NOT NULL DEFAULT 0,
    current_price NUMERIC(15, 4) NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    is_watchlist BOOLEAN DEFAULT FALSE,
    logo_url TEXT,
    target_allocation_pct NUMERIC(5, 2) DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_sector ON assets(sector);

-- 4. Table: investment_theses
-- Human Filter (Filtro Humano) based on Investing Pro qualitative valuation
CREATE TABLE IF NOT EXISTS investment_theses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker VARCHAR(20) NOT NULL REFERENCES assets(ticker) ON DELETE CASCADE,
    thesis_text TEXT NOT NULL,
    valuation_grade INTEGER CHECK (valuation_grade BETWEEN 1 AND 5),
    timing_context TEXT,
    safety_margin NUMERIC(5, 2) NOT NULL DEFAULT 0.00, -- e.g. 25.50 (%)
    checklist_passed BOOLEAN NOT NULL DEFAULT FALSE,
    criteria_details JSONB DEFAULT '{
        "knows_business_model": false,
        "debt_ebitda_healthy": false,
        "margin_safety_above_20": false,
        "timing_not_overbought": false,
        "emotional_bias_checked": false
    }'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_investment_theses_ticker ON investment_theses(ticker);

-- 5. Table: geopolitical_risk
-- Regional risk scores and macro alerts
CREATE TABLE IF NOT EXISTS geopolitical_risk (
    region VARCHAR(50) PRIMARY KEY, -- 'Norteamérica', 'Latinoamérica', 'Europa', 'Asia-Pacífico'
    active_risk_score NUMERIC(5, 2) NOT NULL, -- 0 to 100
    anomaly_alert BOOLEAN NOT NULL DEFAULT FALSE,
    headline TEXT,
    last_assessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Table: budgetbakers_mappings
-- Decoupled mapping between BudgetBakers raw JSON categories and local categories
CREATE TABLE IF NOT EXISTS budgetbakers_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bb_category_name VARCHAR(100) NOT NULL UNIQUE,
    local_category VARCHAR(100) NOT NULL,
    flow_type VARCHAR(20) NOT NULL, -- 'INCOME', 'EXPENSE', 'TRANSFER'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Table: api_request_cache & api_daily_quota
-- Enforce a hard cap of 25 API requests daily and local caching strategies
CREATE TABLE IF NOT EXISTS api_request_cache (
    cache_key VARCHAR(150) PRIMARY KEY,
    endpoint VARCHAR(255) NOT NULL,
    response_payload JSONB NOT NULL,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS api_daily_quota (
    date_key VARCHAR(10) PRIMARY KEY, -- 'YYYY-MM-DD'
    request_count INTEGER NOT NULL DEFAULT 0,
    max_quota INTEGER NOT NULL DEFAULT 25,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
