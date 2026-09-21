-- Ledger reconciliation and per-position source of truth.

CREATE TABLE IF NOT EXISTS opening_positions (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    account_id TEXT,
    opened_at TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_cost REAL NOT NULL DEFAULT 0,
    total_cost REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT NOT NULL DEFAULT 'MANUAL',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, account_id, opened_at, source)
);

CREATE INDEX IF NOT EXISTS idx_opening_positions_ticker_account
ON opening_positions(ticker, account_id);

CREATE TABLE IF NOT EXISTS position_authority (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    account_id TEXT,
    authority_state TEXT NOT NULL DEFAULT 'MANUAL' CHECK (
        authority_state IN ('MANUAL', 'LEDGER_PENDING', 'LEDGER_AUTHORITATIVE', 'RECONCILIATION_REQUIRED')
    ),
    adopted_at TEXT,
    reverted_at TEXT,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, account_id)
);

CREATE INDEX IF NOT EXISTS idx_position_authority_state
ON position_authority(authority_state);

CREATE TABLE IF NOT EXISTS reconciliation_audit_events (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    account_id TEXT,
    event_type TEXT NOT NULL,
    payload TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_audit_ticker
ON reconciliation_audit_events(ticker, created_at DESC);
