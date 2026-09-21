-- Investment ledger and realized performance foundation.

CREATE TABLE IF NOT EXISTS investment_transactions (
    id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    ticker TEXT,
    account_id TEXT,
    operation_type TEXT NOT NULL CHECK (
        operation_type IN (
            'CONTRIBUTION', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND',
            'INTEREST', 'FEE', 'TRANSFER_IN', 'TRANSFER_OUT', 'SPLIT', 'ADJUSTMENT'
        )
    ),
    quantity REAL NOT NULL DEFAULT 0,
    price REAL NOT NULL DEFAULT 0,
    amount REAL NOT NULL DEFAULT 0,
    fee REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT NOT NULL DEFAULT 'MANUAL',
    external_id TEXT,
    notes TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_investment_transactions_source_external
ON investment_transactions(source, external_id)
WHERE external_id IS NOT NULL AND external_id != '';

CREATE INDEX IF NOT EXISTS idx_investment_transactions_ticker_date
ON investment_transactions(ticker, occurred_at);

CREATE INDEX IF NOT EXISTS idx_investment_transactions_type_date
ON investment_transactions(operation_type, occurred_at);
