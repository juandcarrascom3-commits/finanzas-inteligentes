-- Operational hardening indexes for daily local use.
-- 001_sqlite_local.sql is the SQLite baseline; new schema changes must be
-- appended in numbered migration files like this one.

CREATE INDEX IF NOT EXISTS idx_transactions_date_source ON transactions(date DESC, source);
CREATE INDEX IF NOT EXISTS idx_budgets_active_category ON budgets(is_active, category);
CREATE INDEX IF NOT EXISTS idx_budgets_source_external ON budgets(source, external_id);
CREATE INDEX IF NOT EXISTS idx_recurring_status_next ON recurring_rules(status, next_expected);
CREATE INDEX IF NOT EXISTS idx_source_mappings_lookup ON source_mappings(source, external_type, external_id);
CREATE INDEX IF NOT EXISTS idx_monthly_review_period ON monthly_review_snapshots(period);
