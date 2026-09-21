"""SQLite repository layer for demo and personal local finance data."""

import csv
import glob
import hashlib
import io
import json
import logging
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_DB_FILE = os.path.join(os.path.dirname(__file__), "finanzas.db")
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")
SEED_FILE = os.path.join(os.path.dirname(__file__), "seeds", "initial_seed.sql")
VALID_SOURCES = {"DEMO", "MANUAL", "CSV", "BUDGETBAKERS", "ETORO", "GOOGLE", "MARKET_DATA"}
logger = logging.getLogger(__name__)


def resolve_db_path() -> str:
    configured = os.getenv("FINANCE_DB_PATH")
    if configured:
        if os.path.isabs(configured):
            return configured
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.abspath(os.path.join(project_root, configured))
    return DEFAULT_DB_FILE


class DatabaseManager:
    def __init__(self, db_path: str = ""):
        self.db_path = db_path or resolve_db_path()
        self.seed_demo = os.getenv("FINANCE_SEED_DEMO", "1").lower() in {"1", "true", "yes"}
        self._initialize_database()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize_database(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            logger.info("Initializing Finance database at %s", self.db_path)
            self._run_migrations(cursor)
            self._ensure_schema(cursor)
            self._seed_defaults(cursor)
            cursor.execute("SELECT COUNT(*) as count FROM assets")
            count = cursor.fetchone()["count"]
            if self.seed_demo and count == 0 and os.path.exists(SEED_FILE):
                with open(SEED_FILE, "r", encoding="utf-8") as f:
                    cursor.executescript(f.read())
                cursor.execute("UPDATE assets SET source = 'DEMO' WHERE source IS NULL OR source = ''")
            conn.commit()

    def _run_migrations(self, cursor: sqlite3.Cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*_sqlite_*.sql")))
        for path in migration_files:
            filename = os.path.basename(path)
            version = filename.split("_", 1)[0]
            with open(path, "r", encoding="utf-8") as f:
                sql = f.read()
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            row = cursor.execute("SELECT checksum FROM schema_migrations WHERE version = ?", (version,)).fetchone()
            if row:
                if row["checksum"] != checksum:
                    raise RuntimeError(f"Migration {filename} was modified after being applied.")
                continue
            logger.info("Applying database migration %s", filename)
            if version == "001":
                self._prepare_legacy_schema_for_baseline(cursor)
            cursor.executescript(sql)
            cursor.execute(
                "INSERT INTO schema_migrations (version, filename, checksum) VALUES (?, ?, ?)",
                (version, filename, checksum),
            )

    def _prepare_legacy_schema_for_baseline(self, cursor: sqlite3.Cursor):
        tables = self._table_names(cursor)

        def columns(table: str) -> set[str]:
            cursor.execute(f"PRAGMA table_info({table})")
            return {row["name"] for row in cursor.fetchall()}

        if "transactions" in tables:
            tx_cols = columns("transactions")
            for name, ddl in {
                "source": "TEXT NOT NULL DEFAULT 'DEMO'",
                "external_id": "TEXT",
            }.items():
                if name not in tx_cols:
                    cursor.execute(f"ALTER TABLE transactions ADD COLUMN {name} {ddl}")

        if "assets" in tables and "source" not in columns("assets"):
            cursor.execute("ALTER TABLE assets ADD COLUMN source TEXT NOT NULL DEFAULT 'DEMO'")

    def _ensure_schema(self, cursor: sqlite3.Cursor):
        def columns(table: str) -> set[str]:
            cursor.execute(f"PRAGMA table_info({table})")
            return {row["name"] for row in cursor.fetchall()}

        tx_cols = columns("transactions")
        for name, ddl in {
            "account_id": "TEXT",
            "description": "TEXT DEFAULT ''",
            "currency": "TEXT NOT NULL DEFAULT 'USD'",
            "source": "TEXT NOT NULL DEFAULT 'DEMO'",
            "external_id": "TEXT",
            "updated_at": "TEXT",
        }.items():
            if name not in tx_cols:
                cursor.execute(f"ALTER TABLE transactions ADD COLUMN {name} {ddl}")

        if "source" not in columns("assets"):
            cursor.execute("ALTER TABLE assets ADD COLUMN source TEXT NOT NULL DEFAULT 'DEMO'")

        account_cols = columns("accounts")
        for name, ddl in {
            "external_id": "TEXT",
            "last_synced_at": "TEXT",
        }.items():
            if name not in account_cols:
                cursor.execute(f"ALTER TABLE accounts ADD COLUMN {name} {ddl}")

        budget_cols = columns("budgets") if "budgets" in self._table_names(cursor) else set()
        for name, ddl in {
            "period": "TEXT NOT NULL DEFAULT 'MONTHLY'",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
            "external_id": "TEXT",
        }.items():
            if budget_cols and name not in budget_cols:
                cursor.execute(f"ALTER TABLE budgets ADD COLUMN {name} {ddl}")

        cursor.executescript(
            """
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
            CREATE TABLE IF NOT EXISTS asset_valuations (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL REFERENCES assets(ticker) ON DELETE CASCADE,
                price REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                valuation_date TEXT NOT NULL,
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
            CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_external ON transactions(source, external_id);
            CREATE INDEX IF NOT EXISTS idx_accounts_source_external ON accounts(source, external_id);
            CREATE INDEX IF NOT EXISTS idx_asset_valuations_ticker_date ON asset_valuations(ticker, valuation_date DESC);
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
            """
        )

    def _table_names(self, cursor: sqlite3.Cursor) -> set[str]:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row["name"] for row in cursor.fetchall()}

    def _seed_defaults(self, cursor: sqlite3.Cursor):
        defaults = [
            ("cat-income", "Ingresos", "INCOME"),
            ("cat-housing", "Vivienda", "EXPENSE"),
            ("cat-food", "Alimentacion", "EXPENSE"),
            ("cat-transport", "Transporte", "EXPENSE"),
            ("cat-investment", "Inversion", "TRANSFER"),
            ("cat-general", "General", "EXPENSE"),
        ]
        for cat_id, name, flow_type in defaults:
            cursor.execute(
                "INSERT INTO categories (id, name, flow_type, source) VALUES (?, ?, ?, 'MANUAL') ON CONFLICT(name) DO NOTHING",
                (cat_id, name, flow_type),
            )

    def get_data_source(self) -> Dict[str, Any]:
        return {
            "db_path": self.db_path,
            "mode": "DEMO" if self.seed_demo else "REAL",
            "profile": "DEMO" if self.seed_demo else "PERSONAL",
            "seed_demo": self.seed_demo,
            "schema": self.get_schema_info(),
        }

    def get_schema_info(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT version, filename, checksum, applied_at FROM schema_migrations ORDER BY version"
            ).fetchall()
        migrations = [dict(row) for row in rows]
        return {
            "latest_version": migrations[-1]["version"] if migrations else None,
            "migrations": migrations,
        }

    def get_accounts(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()]

    def save_account(self, account: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": account.get("id") or str(uuid.uuid4()),
            "name": account["name"].strip(),
            "account_type": account.get("account_type", "cash"),
            "currency": account.get("currency", "USD").upper(),
            "opening_balance": float(account.get("opening_balance", 0) or 0),
            "current_balance": float(account.get("current_balance", account.get("opening_balance", 0)) or 0),
            "source": self._clean_source(account.get("source", "MANUAL")),
            "external_id": account.get("external_id") or None,
            "last_synced_at": account.get("last_synced_at"),
            "is_active": 1 if account.get("is_active", True) else 0,
        }
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO accounts (id, name, account_type, currency, opening_balance, current_balance, source, external_id, last_synced_at, is_active, updated_at)
                VALUES (:id, :name, :account_type, :currency, :opening_balance, :current_balance, :source, :external_id, :last_synced_at, :is_active, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, account_type = excluded.account_type, currency = excluded.currency,
                    opening_balance = excluded.opening_balance, current_balance = excluded.current_balance,
                    source = excluded.source, external_id = excluded.external_id, last_synced_at = excluded.last_synced_at,
                    is_active = excluded.is_active, updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return payload

    def delete_account(self, account_id: str):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()

    def get_assets(self, include_watchlist: bool = True) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            sql = "SELECT * FROM assets ORDER BY asset_type, ticker" if include_watchlist else "SELECT * FROM assets WHERE is_watchlist = 0 ORDER BY asset_type, ticker"
            return [dict(row) for row in conn.execute(sql).fetchall()]

    def add_or_update_asset(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "ticker": asset["ticker"].strip().upper(),
            "name": asset["name"].strip(),
            "asset_type": asset.get("asset_type", "Renta Variable"),
            "sector": asset.get("sector", "General"),
            "country": asset.get("country", "Global"),
            "quantity": float(asset.get("quantity", 0) or 0),
            "avg_price": float(asset.get("avg_price", 0) or 0),
            "current_price": float(asset.get("current_price", 0) or 0),
            "currency": asset.get("currency", "USD").upper(),
            "is_watchlist": 1 if asset.get("is_watchlist", False) else 0,
            "logo_url": asset.get("logo_url", ""),
            "target_allocation_pct": float(asset.get("target_allocation_pct", 0) or 0),
            "source": self._clean_source(asset.get("source", "MANUAL")),
        }
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO assets (ticker, name, asset_type, sector, country, quantity, avg_price, current_price, currency, is_watchlist, logo_url, target_allocation_pct, source, updated_at)
                VALUES (:ticker, :name, :asset_type, :sector, :country, :quantity, :avg_price, :current_price, :currency, :is_watchlist, :logo_url, :target_allocation_pct, :source, datetime('now'))
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name, asset_type = excluded.asset_type, sector = excluded.sector,
                    country = excluded.country, quantity = excluded.quantity, avg_price = excluded.avg_price,
                    current_price = excluded.current_price, currency = excluded.currency, is_watchlist = excluded.is_watchlist,
                    logo_url = excluded.logo_url, target_allocation_pct = excluded.target_allocation_pct,
                    source = excluded.source, updated_at = datetime('now')
                """,
                payload,
            )
            conn.execute(
                "INSERT INTO asset_valuations (id, ticker, price, currency, valuation_date, source) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), payload["ticker"], payload["current_price"], payload["currency"], datetime.now().date().isoformat(), payload["source"]),
            )
            conn.commit()
        return payload

    def delete_asset(self, ticker: str):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM assets WHERE ticker = ?", (ticker.upper(),))
            conn.commit()

    def get_investment_theses(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT it.*, a.name as asset_name, a.current_price, a.asset_type, a.sector
                FROM investment_theses it JOIN assets a ON it.ticker = a.ticker
                ORDER BY it.updated_at DESC
                """
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if isinstance(item.get("criteria_details"), str):
                try:
                    item["criteria_details"] = json.loads(item["criteria_details"])
                except Exception:
                    item["criteria_details"] = {}
            result.append(item)
        return result

    def save_investment_thesis(self, thesis: Dict[str, Any]):
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO investment_theses (id, ticker, thesis_text, valuation_grade, timing_context, safety_margin, checklist_passed, criteria_details, updated_at)
                VALUES (:id, :ticker, :thesis_text, :valuation_grade, :timing_context, :safety_margin, :checklist_passed, :criteria_details, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    ticker = excluded.ticker, thesis_text = excluded.thesis_text, valuation_grade = excluded.valuation_grade,
                    timing_context = excluded.timing_context, safety_margin = excluded.safety_margin,
                    checklist_passed = excluded.checklist_passed, criteria_details = excluded.criteria_details, updated_at = datetime('now')
                """,
                {
                    "id": thesis.get("id"),
                    "ticker": thesis.get("ticker"),
                    "thesis_text": thesis.get("thesis_text"),
                    "valuation_grade": thesis.get("valuation_grade"),
                    "timing_context": thesis.get("timing_context"),
                    "safety_margin": thesis.get("safety_margin"),
                    "checklist_passed": 1 if thesis.get("checklist_passed") else 0,
                    "criteria_details": json.dumps(thesis.get("criteria_details", {})),
                },
            )
            conn.commit()

    def get_transactions(self, limit: int = 100, account_id: Optional[str] = None, category: Optional[str] = None, source: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if account_id:
            clauses.append("t.account_id = ?")
            params.append(account_id)
        if category:
            clauses.append("t.category = ?")
            params.append(category)
        if source:
            clauses.append("t.source = ?")
            params.append(source.upper())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT t.*, a.name as account_name
                FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id
                {where}
                ORDER BY t.date DESC, t.created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def save_transaction(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._normalize_transaction(tx)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO transactions (id, account_id, amount, category, date, description, currency, source, external_id, raw_payload, updated_at)
                VALUES (:id, :account_id, :amount, :category, :date, :description, :currency, :source, :external_id, :raw_payload, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    account_id = excluded.account_id, amount = excluded.amount, category = excluded.category, date = excluded.date,
                    description = excluded.description, currency = excluded.currency, source = excluded.source,
                    external_id = excluded.external_id, raw_payload = excluded.raw_payload, updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return payload

    def delete_transaction(self, tx_id: str):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
            conn.commit()

    def get_transaction_summary(self) -> Dict[str, float]:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) as expenses
                FROM transactions
                """
            ).fetchone()
        income = float(row["income"] or 0)
        expenses = float(row["expenses"] or 0)
        return {"income": income, "expenses": expenses, "cashflow": income - expenses}

    def get_categories(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM categories ORDER BY flow_type, name").fetchall()]

    def get_budgets(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM budgets ORDER BY category").fetchall()]

    def save_budget(self, budget: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": budget.get("id") or str(uuid.uuid4()),
            "category": budget["category"],
            "monthly_limit": float(budget.get("monthly_limit", 0) or 0),
            "currency": budget.get("currency", "USD").upper(),
            "source": self._clean_source(budget.get("source", "MANUAL")),
            "period": budget.get("period", "MONTHLY"),
            "is_active": 1 if budget.get("is_active", True) else 0,
            "external_id": budget.get("external_id"),
        }
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO budgets (id, category, monthly_limit, currency, source, period, is_active, external_id, updated_at)
                VALUES (:id, :category, :monthly_limit, :currency, :source, :period, :is_active, :external_id, datetime('now'))
                ON CONFLICT(category) DO UPDATE SET
                    monthly_limit = excluded.monthly_limit, currency = excluded.currency,
                    source = excluded.source, period = excluded.period, is_active = excluded.is_active,
                    external_id = excluded.external_id, updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return payload

    def delete_budget(self, budget_id: str):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
            conn.commit()

    def get_recurring_rules(self, include_rejected: bool = False) -> List[Dict[str, Any]]:
        where = "" if include_rejected else "WHERE status != 'rejected'"
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute(f"SELECT * FROM recurring_rules {where} ORDER BY next_expected, merchant").fetchall()]

    def upsert_recurring_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": rule.get("id") or str(uuid.uuid4()),
            "merchant": rule["merchant"],
            "category": rule.get("category", "General"),
            "account_id": rule.get("account_id"),
            "typical_amount": float(rule.get("typical_amount", 0) or 0),
            "frequency": rule.get("frequency", "monthly"),
            "status": rule.get("status", "detected"),
            "source": rule.get("source", "DETECTED"),
            "external_id": rule.get("external_id"),
            "next_expected": rule.get("next_expected"),
            "last_seen": rule.get("last_seen"),
            "raw_payload": json.dumps(rule.get("raw_payload", rule), ensure_ascii=False),
        }
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO recurring_rules (id, merchant, category, account_id, typical_amount, frequency, status, source, external_id, next_expected, last_seen, raw_payload, updated_at)
                VALUES (:id, :merchant, :category, :account_id, :typical_amount, :frequency, :status, :source, :external_id, :next_expected, :last_seen, :raw_payload, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    merchant = excluded.merchant, category = excluded.category, account_id = excluded.account_id,
                    typical_amount = excluded.typical_amount, frequency = excluded.frequency, status = excluded.status,
                    source = excluded.source, external_id = excluded.external_id, next_expected = excluded.next_expected,
                    last_seen = excluded.last_seen, raw_payload = excluded.raw_payload, updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return payload

    def update_recurring_status(self, rule_id: str, status: str) -> Dict[str, Any]:
        if status not in {"detected", "confirmed", "rejected", "ignored"}:
            raise ValueError("Invalid recurring status")
        with self.get_connection() as conn:
            conn.execute("UPDATE recurring_rules SET status = ?, updated_at = datetime('now') WHERE id = ?", (status, rule_id))
            row = conn.execute("SELECT * FROM recurring_rules WHERE id = ?", (rule_id,)).fetchone()
            conn.commit()
        if not row:
            raise ValueError("Recurring rule not found")
        return dict(row)

    def sync_detected_recurring_rules(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        existing = {(row["merchant"], round(float(row["typical_amount"] or 0), 2)): row for row in self.get_recurring_rules(include_rejected=True)}
        saved = []
        for candidate in candidates:
            key = (candidate["merchant"], round(float(candidate.get("typical_amount", 0) or 0), 2))
            current = existing.get(key)
            if current and current["status"] in {"confirmed", "rejected", "ignored"}:
                saved.append(current)
                continue
            payload = {**candidate, "id": current["id"] if current else None, "status": current["status"] if current else "detected", "source": "DETECTED"}
            saved.append(self.upsert_recurring_rule(payload))
        return saved

    def save_monthly_review_snapshot(self, period: str, summary: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": str(uuid.uuid4()),
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "source": "SYSTEM",
            "summary_payload": json.dumps(summary, ensure_ascii=False),
        }
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO monthly_review_snapshots (id, period, generated_at, source, summary_payload)
                VALUES (:id, :period, :generated_at, :source, :summary_payload)
                ON CONFLICT(period) DO UPDATE SET
                    generated_at = excluded.generated_at, source = excluded.source,
                    summary_payload = excluded.summary_payload
                """,
                payload,
            )
            conn.commit()
        return payload

    def get_monthly_review_snapshots(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM monthly_review_snapshots ORDER BY period DESC").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["summary_payload"] = self._safe_json(item.get("summary_payload"))
            result.append(item)
        return result

    def get_geopolitical_risk(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM geopolitical_risk ORDER BY active_risk_score DESC").fetchall()]

    def get_budgetbakers_mappings(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM budgetbakers_mappings ORDER BY flow_type, local_category").fetchall()]

    def update_budgetbakers_mapping(self, mapping_id: str, local_category: str, is_active: bool):
        with self.get_connection() as conn:
            conn.execute("UPDATE budgetbakers_mappings SET local_category = ?, is_active = ? WHERE id = ?", (local_category, 1 if is_active else 0, mapping_id))
            conn.commit()

    def preview_transactions_csv(self, content: str) -> Dict[str, Any]:
        accepted, rejected = self._validate_csv_rows(self._parse_csv_rows(content))
        return {"accepted_rows": accepted, "rejected_rows": rejected, "accepted_count": len(accepted), "rejected_count": len(rejected)}

    def import_transactions_csv(self, content: str) -> Dict[str, Any]:
        preview = self.preview_transactions_csv(content)
        imported = 0
        duplicates = 0
        with self.get_connection() as conn:
            for row in preview["accepted_rows"]:
                if self._transaction_exists(conn, row):
                    duplicates += 1
                    continue
                payload = self._normalize_transaction(row, source="CSV")
                conn.execute(
                    """
                    INSERT INTO transactions (id, account_id, amount, category, date, description, currency, source, external_id, raw_payload, updated_at)
                    VALUES (:id, :account_id, :amount, :category, :date, :description, :currency, :source, :external_id, :raw_payload, datetime('now'))
                    """,
                    payload,
                )
                imported += 1
            conn.commit()
        return {**preview, "imported_count": imported, "duplicate_count": duplicates}

    def get_sync_state(self, source: str) -> Dict[str, Any]:
        clean_source = self._clean_source(source)
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM source_sync_state WHERE source = ?", (clean_source,)).fetchone()
        return dict(row) if row else {"source": clean_source, "status": "NOT_CONFIGURED"}

    def set_sync_state(self, source: str, state: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "source": self._clean_source(source),
            "status": state.get("status", "UNKNOWN"),
            "last_sync_at": state.get("last_sync_at"),
            "last_success_at": state.get("last_success_at"),
            "last_error": state.get("last_error"),
            "last_data_change_at": state.get("last_data_change_at"),
            "last_data_change_rev": state.get("last_data_change_rev"),
            "sync_in_progress": state.get("sync_in_progress"),
        }
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO source_sync_state (source, status, last_sync_at, last_success_at, last_error, last_data_change_at, last_data_change_rev, sync_in_progress, updated_at)
                VALUES (:source, :status, :last_sync_at, :last_success_at, :last_error, :last_data_change_at, :last_data_change_rev, :sync_in_progress, datetime('now'))
                ON CONFLICT(source) DO UPDATE SET
                    status = excluded.status, last_sync_at = excluded.last_sync_at, last_success_at = excluded.last_success_at,
                    last_error = excluded.last_error, last_data_change_at = excluded.last_data_change_at,
                    last_data_change_rev = excluded.last_data_change_rev, sync_in_progress = excluded.sync_in_progress,
                    updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return self.get_sync_state(payload["source"])

    def get_source_mappings(self, source: str, external_type: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = ["source = ?"]
        params: List[Any] = [self._clean_source(source)]
        if external_type:
            clauses.append("external_type = ?")
            params.append(external_type)
        with self.get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM source_mappings WHERE {' AND '.join(clauses)} ORDER BY external_type, external_name",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_source_mapping_lookup(self, source: str, external_type: str) -> Dict[str, str]:
        return {
            item["external_id"]: item["local_id"]
            for item in self.get_source_mappings(source, external_type)
            if item.get("is_active") and item.get("local_id")
        }

    def save_source_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": mapping.get("id") or str(uuid.uuid4()),
            "source": self._clean_source(mapping.get("source", "MANUAL")),
            "external_type": mapping["external_type"],
            "external_id": str(mapping["external_id"]),
            "external_name": mapping.get("external_name", ""),
            "local_id": mapping.get("local_id"),
            "local_type": mapping.get("local_type"),
            "is_active": 1 if mapping.get("is_active", True) else 0,
        }
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO source_mappings (id, source, external_type, external_id, external_name, local_id, local_type, is_active, updated_at)
                VALUES (:id, :source, :external_type, :external_id, :external_name, :local_id, :local_type, :is_active, datetime('now'))
                ON CONFLICT(source, external_type, external_id) DO UPDATE SET
                    external_name = excluded.external_name, local_id = excluded.local_id,
                    local_type = excluded.local_type, is_active = excluded.is_active, updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return payload

    def add_action_event(self, source: str, event_type: str, message: str, severity: str = "INFO", payload: Optional[Dict[str, Any]] = None):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO action_events (id, source, event_type, severity, message, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), self._clean_source(source), event_type, severity, message, json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()

    def get_action_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM action_events ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()]

    def get_reconciliation_summary(self, source: str = "BUDGETBAKERS") -> Dict[str, Any]:
        clean_source = self._clean_source(source)
        mappings = self.get_source_mappings(clean_source)
        mapped_accounts = {m["external_id"] for m in mappings if m["external_type"] == "account" and m.get("local_id") and m.get("is_active")}
        mapped_categories = {m["external_name"] or m["external_id"] for m in mappings if m["external_type"] == "category" and m.get("local_id") and m.get("is_active")}
        with self.get_connection() as conn:
            source_accounts = [dict(row) for row in conn.execute("SELECT * FROM accounts WHERE source = ? ORDER BY name", (clean_source,)).fetchall()]
            tx_rows = [dict(row) for row in conn.execute("SELECT * FROM transactions WHERE source = ? ORDER BY date DESC", (clean_source,)).fetchall()]
        category_counts: Dict[str, int] = {}
        no_category = 0
        for tx in tx_rows:
            raw = self._safe_json(tx.get("raw_payload"))
            external_category = raw.get("external_category") or tx.get("category") or ""
            if not external_category:
                no_category += 1
                continue
            category_counts[external_category] = category_counts.get(external_category, 0) + 1
        unmapped_categories = [
            {"external_name": name, "count": count}
            for name, count in sorted(category_counts.items(), key=lambda item: item[1], reverse=True)
            if name not in mapped_categories
        ]
        unmapped_accounts = [
            {"external_id": account.get("external_id"), "external_name": account.get("name"), "local_id": account.get("id")}
            for account in source_accounts
            if account.get("external_id") not in mapped_accounts
        ]
        return {
            "source": clean_source,
            "unmapped_accounts": unmapped_accounts,
            "unmapped_categories": unmapped_categories[:20],
            "no_category_count": no_category,
            "transaction_count": len(tx_rows),
        }

    def preview_canonical_import(self, accounts: List[Dict[str, Any]], transactions: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
        clean_source = self._clean_source(source)
        accepted, rejected = [], []
        duplicate_count = 0
        existing_account_ids = set()
        new_account_count = 0
        unmapped_accounts = set()
        unknown_currencies = set()
        updated_count = 0
        dates = []

        with self.get_connection() as conn:
            for account in accounts:
                external_id = account.get("external_id")
                if not external_id:
                    continue
                existing = conn.execute(
                    "SELECT id FROM accounts WHERE source = ? AND external_id = ? LIMIT 1",
                    (clean_source, external_id),
                ).fetchone()
                if existing:
                    existing_account_ids.add(external_id)
                else:
                    new_account_count += 1

            known_account_ids = {
                row["external_id"]
                for row in conn.execute(
                    "SELECT external_id FROM accounts WHERE source = ? AND external_id IS NOT NULL AND external_id != ''",
                    (clean_source,),
                ).fetchall()
            }
            known_account_ids.update(a.get("external_id") for a in accounts if a.get("external_id"))

            for index, tx in enumerate(transactions, start=1):
                try:
                    normalized = dict(tx)
                    normalized["source"] = clean_source
                    normalized["amount"] = float(normalized.get("amount", 0) or 0)
                    if not normalized.get("date"):
                        raise ValueError("date is required")
                    datetime.fromisoformat(str(normalized["date"]).replace("Z", "+00:00"))
                    if not normalized.get("currency"):
                        unknown_currencies.add("EMPTY")
                    if normalized.get("external_account_id") and normalized.get("external_account_id") not in known_account_ids:
                        unmapped_accounts.add(str(normalized.get("external_account_id")))
                    existing = self._get_existing_transaction(conn, normalized)
                    if existing and self._transaction_changed(existing, normalized):
                        updated_count += 1
                    elif existing:
                        duplicate_count += 1
                    accepted.append(normalized)
                    dates.append(normalized["date"][:10])
                except Exception as exc:
                    rejected.append({"row_number": index, "row": tx, "error": str(exc)})

        return {
            "source": clean_source,
            "accounts_detected": len(accounts),
            "new_accounts": new_account_count,
            "existing_accounts": len(existing_account_ids),
            "records_found": len(transactions),
            "accepted_rows": accepted,
            "rejected_rows": rejected,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "duplicate_count": duplicate_count,
            "updated_count": updated_count,
            "new_transaction_count": max(len(accepted) - duplicate_count - updated_count, 0),
            "unmapped_accounts": sorted(unmapped_accounts),
            "unknown_currencies": sorted(unknown_currencies),
            "date_range": {"from": min(dates) if dates else None, "to": max(dates) if dates else None},
        }

    def import_canonical_import(self, accounts: List[Dict[str, Any]], transactions: List[Dict[str, Any]], source: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        clean_source = self._clean_source(source)
        preview = self.preview_canonical_import(accounts, transactions, clean_source)
        account_id_by_external: Dict[str, str] = {}
        account_imported = 0
        imported = 0
        updated = 0
        duplicates = 0
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            for account in accounts:
                external_id = account.get("external_id")
                if not external_id:
                    continue
                existing = conn.execute(
                    "SELECT id FROM accounts WHERE source = ? AND external_id = ? LIMIT 1",
                    (clean_source, external_id),
                ).fetchone()
                payload = dict(account)
                payload["source"] = clean_source
                payload["last_synced_at"] = now
                if existing:
                    payload["id"] = existing["id"]
                account_payload = {
                    "id": payload.get("id") or str(uuid.uuid4()),
                    "name": payload["name"].strip(),
                    "account_type": payload.get("account_type", "cash"),
                    "currency": payload.get("currency", "USD").upper(),
                    "opening_balance": float(payload.get("opening_balance", 0) or 0),
                    "current_balance": float(payload.get("current_balance", payload.get("opening_balance", 0)) or 0),
                    "source": clean_source,
                    "external_id": external_id,
                    "last_synced_at": now,
                    "is_active": 1 if payload.get("is_active", True) else 0,
                }
                conn.execute(
                    """
                    INSERT INTO accounts (id, name, account_type, currency, opening_balance, current_balance, source, external_id, last_synced_at, is_active, updated_at)
                    VALUES (:id, :name, :account_type, :currency, :opening_balance, :current_balance, :source, :external_id, :last_synced_at, :is_active, datetime('now'))
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name, account_type = excluded.account_type, currency = excluded.currency,
                        opening_balance = excluded.opening_balance, current_balance = excluded.current_balance,
                        source = excluded.source, external_id = excluded.external_id, last_synced_at = excluded.last_synced_at,
                        is_active = excluded.is_active, updated_at = datetime('now')
                    """,
                    account_payload,
                )
                account_id_by_external[str(external_id)] = account_payload["id"]
                if not existing:
                    account_imported += 1

            for tx in preview["accepted_rows"]:
                existing_tx = self._get_existing_transaction(conn, tx)
                if existing_tx and self._transaction_changed(existing_tx, tx):
                    payload = dict(tx)
                    payload["source"] = clean_source
                    if not payload.get("account_id") and payload.get("external_account_id"):
                        payload["account_id"] = account_id_by_external.get(str(payload["external_account_id"]))
                    normalized_payload = self._normalize_transaction(payload, source=clean_source)
                    normalized_payload["id"] = existing_tx["id"]
                    conn.execute(
                        """
                        UPDATE transactions
                        SET account_id = :account_id, amount = :amount, category = :category, date = :date,
                            description = :description, currency = :currency, raw_payload = :raw_payload,
                            updated_at = datetime('now')
                        WHERE id = :id
                        """,
                        normalized_payload,
                    )
                    updated += 1
                    continue
                if existing_tx:
                    duplicates += 1
                    continue
                payload = dict(tx)
                payload["source"] = clean_source
                if not payload.get("account_id") and payload.get("external_account_id"):
                    payload["account_id"] = account_id_by_external.get(str(payload["external_account_id"]))
                conn.execute(
                    """
                    INSERT INTO transactions (id, account_id, amount, category, date, description, currency, source, external_id, raw_payload, updated_at)
                    VALUES (:id, :account_id, :amount, :category, :date, :description, :currency, :source, :external_id, :raw_payload, datetime('now'))
                    """,
                    self._normalize_transaction(payload, source=clean_source),
                )
                imported += 1
            conn.commit()

        sync_meta = meta or {}
        self.set_sync_state(clean_source, {
            "status": "CONNECTED",
            "last_sync_at": now,
            "last_success_at": now,
            "last_error": None,
            "last_data_change_at": sync_meta.get("last_data_change_at"),
            "last_data_change_rev": sync_meta.get("last_data_change_rev"),
            "sync_in_progress": sync_meta.get("sync_in_progress"),
        })
        if preview["unmapped_accounts"]:
            self.add_action_event(clean_source, "UNMAPPED_ACCOUNT", "Hay cuentas externas sin mapping local.", "WARNING", {"accounts": preview["unmapped_accounts"]})

        return {
            **preview,
            "account_imported_count": account_imported,
            "imported_count": imported,
            "updated_count": updated,
            "duplicate_count": duplicates,
        }

    def export_backup(self) -> Dict[str, Any]:
        tables = [
            "accounts",
            "assets",
            "transactions",
            "categories",
            "asset_valuations",
            "budgets",
            "recurring_rules",
            "source_mappings",
            "source_sync_state",
            "monthly_review_snapshots",
            "schema_migrations",
        ]
        with self.get_connection() as conn:
            data = {
                table: [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]
                for table in tables
                if table in self._table_names(conn.cursor())
            }
        backup_dir = os.path.join(os.path.dirname(self.db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        db_copy = os.path.join(backup_dir, f"finance-backup-{stamp}.db")
        shutil.copy2(self.db_path, db_copy)
        logger.info("Created local backup at %s", db_copy)
        return {
            "generated_at": datetime.now().isoformat(),
            "db_backup_path": db_copy,
            "schema": self.get_schema_info(),
            "data": data,
        }

    def validate_backup(self, backup_path: str) -> Dict[str, Any]:
        if not backup_path or not os.path.exists(backup_path):
            raise ValueError("Backup file does not exist.")
        if not os.path.isfile(backup_path):
            raise ValueError("Backup path must point to a file.")

        conn = sqlite3.connect(backup_path)
        conn.row_factory = sqlite3.Row
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError(f"Backup integrity check failed: {integrity}")
            tables = {
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            required = {"accounts", "assets", "transactions", "categories", "schema_migrations"}
            missing = sorted(required - tables)
            if missing:
                raise ValueError(f"Backup is missing required tables: {', '.join(missing)}")
            migrations = [
                dict(row)
                for row in conn.execute(
                    "SELECT version, filename, applied_at FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]
            return {
                "valid": True,
                "path": backup_path,
                "tables": sorted(tables),
                "latest_version": migrations[-1]["version"] if migrations else None,
                "migrations": migrations,
            }
        finally:
            conn.close()

    def restore_backup(self, backup_path: str) -> Dict[str, Any]:
        validation = self.validate_backup(backup_path)
        backup_dir = os.path.join(os.path.dirname(self.db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        pre_restore_path = os.path.join(backup_dir, f"finance-pre-restore-{stamp}.db")
        if os.path.exists(self.db_path):
            shutil.copy2(self.db_path, pre_restore_path)
        shutil.copy2(backup_path, self.db_path)
        logger.warning("Restored local database from %s", backup_path)
        return {
            "status": "RESTORED",
            "restored_from": backup_path,
            "pre_restore_backup_path": pre_restore_path if os.path.exists(pre_restore_path) else None,
            "validation": validation,
            "schema": self.get_schema_info(),
        }

    def _parse_csv_rows(self, content: str) -> List[Dict[str, Any]]:
        if not content.strip():
            return []
        reader = csv.DictReader(io.StringIO(content.strip()))
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]

    def _validate_csv_rows(self, rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        accepted, rejected = [], []
        for index, row in enumerate(rows, start=2):
            try:
                normalized = {
                    "date": row.get("date") or row.get("fecha"),
                    "amount": float(row.get("amount") or row.get("monto") or ""),
                    "category": row.get("category") or row.get("categoria") or "General",
                    "description": row.get("description") or row.get("descripcion") or row.get("payee") or "",
                    "currency": (row.get("currency") or row.get("moneda") or "USD").upper(),
                    "source": "CSV",
                    "external_id": row.get("external_id") or row.get("id") or "",
                    "account_id": row.get("account_id") or "",
                    "raw_payload": row,
                }
                if not normalized["date"]:
                    raise ValueError("date is required")
                datetime.fromisoformat(normalized["date"].replace("Z", "+00:00"))
                accepted.append(normalized)
            except Exception as exc:
                rejected.append({"row_number": index, "row": row, "error": str(exc)})
        return accepted, rejected

    def _transaction_exists(self, conn: sqlite3.Connection, row: Dict[str, Any]) -> bool:
        if row.get("external_id"):
            found = conn.execute("SELECT 1 FROM transactions WHERE source = ? AND external_id = ? LIMIT 1", (row.get("source", "CSV"), row["external_id"])).fetchone()
            if found:
                return True
        fingerprint = self._transaction_fingerprint(row)
        found = conn.execute("SELECT 1 FROM transactions WHERE external_id = ? LIMIT 1", (fingerprint,)).fetchone()
        row["external_id"] = row.get("external_id") or fingerprint
        return bool(found)

    def _transaction_exists_readonly(self, conn: sqlite3.Connection, row: Dict[str, Any]) -> bool:
        if row.get("external_id"):
            found = conn.execute(
                "SELECT 1 FROM transactions WHERE source = ? AND external_id = ? LIMIT 1",
                (row.get("source", "CSV"), row["external_id"]),
            ).fetchone()
            if found:
                return True
        fingerprint = self._transaction_fingerprint(row)
        found = conn.execute("SELECT 1 FROM transactions WHERE external_id = ? LIMIT 1", (fingerprint,)).fetchone()
        return bool(found)

    def _get_existing_transaction(self, conn: sqlite3.Connection, row: Dict[str, Any]) -> Optional[sqlite3.Row]:
        if row.get("external_id"):
            found = conn.execute(
                "SELECT * FROM transactions WHERE source = ? AND external_id = ? LIMIT 1",
                (row.get("source", "CSV"), row["external_id"]),
            ).fetchone()
            if found:
                return found
        fingerprint = self._transaction_fingerprint(row)
        return conn.execute("SELECT * FROM transactions WHERE external_id = ? LIMIT 1", (fingerprint,)).fetchone()

    def _transaction_changed(self, existing: sqlite3.Row, row: Dict[str, Any]) -> bool:
        return any([
            round(float(existing["amount"] or 0), 2) != round(float(row.get("amount", 0) or 0), 2),
            str(existing["date"])[:10] != str(row.get("date", ""))[:10],
            (existing["category"] or "") != (row.get("category") or "General"),
            (existing["description"] or "") != (row.get("description") or ""),
            (existing["currency"] or "").upper() != (row.get("currency") or "USD").upper(),
        ])

    def _normalize_transaction(self, tx: Dict[str, Any], source: Optional[str] = None) -> Dict[str, Any]:
        tx_source = self._clean_source(source or tx.get("source", "MANUAL"))
        return {
            "id": tx.get("id") or str(uuid.uuid4()),
            "account_id": tx.get("account_id") or None,
            "amount": float(tx.get("amount", 0) or 0),
            "category": tx.get("category") or "General",
            "date": tx.get("date") or datetime.now().date().isoformat(),
            "description": tx.get("description", ""),
            "currency": tx.get("currency", "USD").upper(),
            "source": tx_source,
            "external_id": tx.get("external_id") or self._transaction_fingerprint(tx),
            "raw_payload": json.dumps(tx.get("raw_payload", tx), ensure_ascii=False),
        }

    def _safe_json(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            return json.loads(value)
        except Exception:
            return {}

    def _transaction_fingerprint(self, tx: Dict[str, Any]) -> str:
        raw = f"{tx.get('date')}|{tx.get('amount')}|{tx.get('category')}|{tx.get('description')}|{tx.get('account_id')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _clean_source(self, source: str) -> str:
        value = (source or "MANUAL").upper()
        return value if value in VALID_SOURCES else "MANUAL"
