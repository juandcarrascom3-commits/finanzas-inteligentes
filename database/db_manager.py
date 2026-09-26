"""SQLite repository layer for demo and personal local finance data."""

import csv
import glob
import hashlib
import io
import json
import logging
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_DB_FILE = os.path.join(os.path.dirname(__file__), "finanzas.db")
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")
SEED_FILE = os.path.join(os.path.dirname(__file__), "seeds", "initial_seed.sql")
BACKUP_FILE_PREFIXES = ("finance-backup-", "finance-pre-restore-")
VALID_SOURCES = {"DEMO", "MANUAL", "CSV", "BUDGETBAKERS", "ETORO", "GOOGLE", "MARKET_DATA"}
VALID_INVESTMENT_OPERATION_TYPES = {
    "CONTRIBUTION", "WITHDRAWAL", "BUY", "SELL", "DIVIDEND", "INTEREST", "FEE",
    "TRANSFER_IN", "TRANSFER_OUT", "SPLIT", "ADJUSTMENT",
}
logger = logging.getLogger(__name__)


def resolve_db_path() -> str:
    configured = os.getenv("FINANCE_DB_PATH")
    if configured:
        if os.path.isabs(configured):
            return configured
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.abspath(os.path.join(project_root, configured))
    return DEFAULT_DB_FILE


def _quote_sql_literal(value: str) -> str:
    """Escape repository-controlled metadata for interpolation into an executescript."""
    return "'" + value.replace("'", "''") + "'"


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
        with closing(self.get_connection()) as conn:
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
            statements: List[str] = []
            if version == "001":
                statements.extend(self._legacy_baseline_statements(cursor))
            statements.append(sql)
            self._apply_migration_atomically(cursor, version, filename, checksum, statements)

    def _apply_migration_atomically(
        self,
        cursor: sqlite3.Cursor,
        version: str,
        filename: str,
        checksum: str,
        statements: List[str],
    ):
        """Apply migration SQL and its schema_migrations record as one SQLite transaction.

        `executescript` commits any pending transaction first, then runs this script
        verbatim, so the explicit BEGIN IMMEDIATE/COMMIT pair below is what makes the
        migration and its record all-or-nothing. Any failure leaves the transaction open
        and is rolled back here, so a half-applied schema can never be recorded.
        """
        if not version or not all(ch in "0123456789" for ch in version):
            raise RuntimeError(f"Migration {filename} has an unsupported version; refusing to apply it.")
        if len(checksum) != 64 or any(ch not in "0123456789abcdef" for ch in checksum):
            raise RuntimeError(f"Migration {filename} has an unsupported checksum; refusing to apply it.")
        if not filename.startswith(f"{version}_") or not all(ch.isalnum() or ch in "._-" for ch in filename):
            raise RuntimeError(f"Migration {filename} has an unsupported name; refusing to apply it.")

        sql_statements = [
            statement.strip().rstrip(";").rstrip() + ";"
            for statement in statements
            if statement.strip()
        ]
        script = "\n".join(
            ["BEGIN IMMEDIATE;"]
            + sql_statements
            + [
                "INSERT INTO schema_migrations (version, filename, checksum) VALUES ("
                f"{_quote_sql_literal(version)}, {_quote_sql_literal(filename)}, {_quote_sql_literal(checksum)});",
                "COMMIT;",
            ]
        )
        connection = cursor.connection
        try:
            connection.executescript(script)
        except BaseException:
            connection.rollback()
            raise

    def _legacy_baseline_statements(self, cursor: sqlite3.Cursor) -> List[str]:
        """Return the ALTER statements migration 001 needs on a legacy database.

        They are collected instead of executed so they join the migration transaction:
        a legacy baseline can never end up half-applied.
        """
        statements: List[str] = []
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
                    statements.append(f"ALTER TABLE transactions ADD COLUMN {name} {ddl}")

        if "assets" in tables and "source" not in columns("assets"):
            statements.append("ALTER TABLE assets ADD COLUMN source TEXT NOT NULL DEFAULT 'DEMO'")
        return statements

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
            cursor = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            deleted = cursor.rowcount > 0
            self._insert_action_event(
                conn,
                "MANUAL",
                "ACCOUNT_DELETE",
                "Cuenta eliminada." if deleted else "Cuenta no encontrada; sin cambios.",
                "INFO",
                {"entity_id": account_id, "deleted": deleted},
            )
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
        clean_ticker = ticker.upper()
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM assets WHERE ticker = ?", (clean_ticker,))
            deleted = cursor.rowcount > 0
            self._insert_action_event(
                conn,
                "MANUAL",
                "ASSET_DELETE",
                "Activo eliminado." if deleted else "Activo no encontrado; sin cambios.",
                "INFO",
                {"entity_id": clean_ticker, "deleted": deleted},
            )
            conn.commit()

    def save_asset_valuation(self, valuation: Dict[str, Any]) -> Dict[str, Any]:
        retrieved_at = valuation.get("retrieved_at") or datetime.now().isoformat()
        metadata = valuation.get("metadata") or {}
        payload = {
            "id": valuation.get("id") or str(uuid.uuid4()),
            "ticker": valuation["ticker"].strip().upper(),
            "price": float(valuation.get("price", 0) or 0),
            "currency": valuation.get("currency", "USD").upper(),
            "valuation_date": str(valuation["valuation_date"])[:10],
            "source": self._clean_source(valuation.get("source", "MANUAL")),
            "provider": (valuation.get("provider") or "").strip().upper() or None,
            "retrieved_at": retrieved_at,
            "metadata": json.dumps(metadata if isinstance(metadata, dict) else self._safe_json(metadata), ensure_ascii=False),
        }
        with self.get_connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM asset_valuations
                WHERE ticker = ? AND valuation_date = ? AND source = ?
                """,
                (payload["ticker"], payload["valuation_date"], payload["source"]),
            ).fetchone()
            if existing:
                payload["id"] = existing["id"]
            conn.execute(
                """
                INSERT INTO asset_valuations (id, ticker, price, currency, valuation_date, source, provider, retrieved_at, metadata)
                VALUES (:id, :ticker, :price, :currency, :valuation_date, :source, :provider, :retrieved_at, :metadata)
                ON CONFLICT(ticker, valuation_date, source) DO UPDATE SET
                    price = excluded.price, currency = excluded.currency,
                    provider = excluded.provider, retrieved_at = excluded.retrieved_at, metadata = excluded.metadata
                """,
                payload,
            )
            conn.commit()
        return payload

    def get_asset_valuations(self, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if ticker:
            clauses.append("ticker = ?")
            params.append(ticker.upper())
        if start:
            clauses.append("valuation_date >= ?")
            params.append(start[:10])
        if end:
            clauses.append("valuation_date <= ?")
            params.append(end[:10])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM asset_valuations {where} ORDER BY valuation_date, ticker, source",
                params,
            ).fetchall()
            return [self._decode_market_row(dict(row)) for row in rows]

    def get_latest_asset_valuations(self, source: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        clauses, params = [], []
        if source:
            clauses.append("source = ?")
            params.append(self._clean_source(source))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT av.*
                FROM asset_valuations av
                JOIN (
                    SELECT ticker, MAX(valuation_date) AS valuation_date
                    FROM asset_valuations {where}
                    GROUP BY ticker
                ) latest
                ON latest.ticker = av.ticker AND latest.valuation_date = av.valuation_date
                ORDER BY av.ticker, av.source
                """,
                params,
            ).fetchall()
            latest: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                item = self._decode_market_row(dict(row))
                ticker = item["ticker"].upper()
                if ticker not in latest or item.get("source") == "MARKET_DATA":
                    latest[ticker] = item
            return latest

    def import_asset_valuations_csv(self, content: str, source: str = "MANUAL") -> Dict[str, Any]:
        rows = self._parse_csv_rows(content)
        accepted, rejected = [], []
        for index, row in enumerate(rows, start=2):
            try:
                payload = {
                    "ticker": row.get("ticker") or row.get("symbol"),
                    "valuation_date": row.get("valuation_date") or row.get("date") or row.get("fecha"),
                    "price": float(row.get("price") or row.get("precio") or ""),
                    "currency": row.get("currency") or row.get("moneda") or "USD",
                    "source": row.get("source") or source,
                }
                if not payload["ticker"] or not payload["valuation_date"]:
                    raise ValueError("ticker and valuation_date are required")
                datetime.fromisoformat(str(payload["valuation_date"]).replace("Z", "+00:00"))
                if payload["price"] <= 0:
                    raise ValueError("price must be positive")
                accepted.append(payload)
            except Exception as exc:
                rejected.append({"row_number": index, "row": row, "error": str(exc)})
        for payload in accepted:
            self.save_asset_valuation(payload)
        return {
            "accepted_rows": accepted,
            "rejected_rows": rejected,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "imported_count": len(accepted),
        }

    def save_benchmark_price(self, price: Dict[str, Any]) -> Dict[str, Any]:
        key = (price.get("benchmark_key") or price.get("ticker") or "BENCHMARK").strip().upper()
        retrieved_at = price.get("retrieved_at") or datetime.now().isoformat()
        metadata = price.get("metadata") or {}
        payload = {
            "id": price.get("id") or str(uuid.uuid4()),
            "benchmark_key": key,
            "label": price.get("label") or key,
            "price": float(price.get("price", 0) or 0),
            "currency": price.get("currency", "USD").upper(),
            "valuation_date": str(price["valuation_date"])[:10],
            "source": self._clean_source(price.get("source", "MANUAL")),
            "provider": (price.get("provider") or "").strip().upper() or None,
            "retrieved_at": retrieved_at,
            "metadata": json.dumps(metadata if isinstance(metadata, dict) else self._safe_json(metadata), ensure_ascii=False),
        }
        with self.get_connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM benchmark_prices
                WHERE benchmark_key = ? AND valuation_date = ? AND source = ?
                """,
                (payload["benchmark_key"], payload["valuation_date"], payload["source"]),
            ).fetchone()
            if existing:
                payload["id"] = existing["id"]
            conn.execute(
                """
                INSERT INTO benchmark_prices (id, benchmark_key, label, price, currency, valuation_date, source, provider, retrieved_at, metadata, updated_at)
                VALUES (:id, :benchmark_key, :label, :price, :currency, :valuation_date, :source, :provider, :retrieved_at, :metadata, datetime('now'))
                ON CONFLICT(benchmark_key, valuation_date, source) DO UPDATE SET
                    label = excluded.label, price = excluded.price, currency = excluded.currency,
                    provider = excluded.provider, retrieved_at = excluded.retrieved_at, metadata = excluded.metadata,
                    updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return payload

    def get_benchmark_prices(self, benchmark_key: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if benchmark_key:
            clauses.append("benchmark_key = ?")
            params.append(benchmark_key.upper())
        if start:
            clauses.append("valuation_date >= ?")
            params.append(start[:10])
        if end:
            clauses.append("valuation_date <= ?")
            params.append(end[:10])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM benchmark_prices {where} ORDER BY benchmark_key, valuation_date",
                params,
            ).fetchall()
            return [self._decode_market_row(dict(row)) for row in rows]

    def get_market_data_config(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM market_data_config WHERE id = 'default'").fetchone()
            if row:
                return dict(row)
            return {
                "id": "default",
                "provider": "YFINANCE",
                "benchmark_symbol": "SPY",
                "benchmark_label": "SPY ETF",
                "benchmark_provider": "YFINANCE",
                "quote_ttl_minutes": 720,
                "stale_after_days": 7,
                "history_lookback_days": 365,
            "fx_max_age_days": 5,
        }

    def get_symbol_mappings(self, provider: Optional[str] = None, internal_symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if provider:
            clauses.append("provider = ?")
            params.append(provider.upper())
        if internal_symbol:
            clauses.append("internal_symbol = ?")
            params.append(internal_symbol.upper())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(f"SELECT * FROM market_symbol_mappings {where} ORDER BY internal_symbol, provider", params).fetchall()
            return [dict(row) for row in rows]

    def save_symbol_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": mapping.get("id") or str(uuid.uuid4()),
            "internal_symbol": mapping["internal_symbol"].strip().upper(),
            "provider": (mapping.get("provider") or "YFINANCE").strip().upper(),
            "provider_symbol": mapping["provider_symbol"].strip().upper(),
            "instrument_type": (mapping.get("instrument_type") or "EQUITY").strip().upper(),
            "expected_currency": (mapping.get("expected_currency") or "").strip().upper() or None,
            "status": (mapping.get("status") or "ACTIVE").strip().upper(),
            "notes": mapping.get("notes") or "",
        }
        with self.get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM market_symbol_mappings WHERE internal_symbol = ? AND provider = ?",
                (payload["internal_symbol"], payload["provider"]),
            ).fetchone()
            if existing:
                payload["id"] = existing["id"]
            conn.execute(
                """
                INSERT INTO market_symbol_mappings (
                    id, internal_symbol, provider, provider_symbol, instrument_type,
                    expected_currency, status, notes, updated_at
                )
                VALUES (
                    :id, :internal_symbol, :provider, :provider_symbol, :instrument_type,
                    :expected_currency, :status, :notes, datetime('now')
                )
                ON CONFLICT(internal_symbol, provider) DO UPDATE SET
                    provider_symbol = excluded.provider_symbol,
                    instrument_type = excluded.instrument_type,
                    expected_currency = excluded.expected_currency,
                    status = excluded.status,
                    notes = excluded.notes,
                    updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return self.get_symbol_mappings(provider=payload["provider"], internal_symbol=payload["internal_symbol"])[0]

    def get_price_authority(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if ticker:
            clauses.append("ticker = ?")
            params.append(ticker.upper())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(f"SELECT * FROM price_authority {where} ORDER BY ticker", params).fetchall()
            return [dict(row) for row in rows]

    def save_price_authority(self, authority: Dict[str, Any]) -> Dict[str, Any]:
        mode = (authority.get("authority_mode") or authority.get("mode") or "AUTO").upper()
        if mode not in {"AUTO", "MANUAL"}:
            raise ValueError("authority_mode must be AUTO or MANUAL.")
        manual_price = authority.get("manual_price")
        payload = {
            "id": authority.get("id") or str(uuid.uuid4()),
            "ticker": authority["ticker"].strip().upper(),
            "authority_mode": mode,
            "manual_price": float(manual_price) if manual_price not in {None, ""} else None,
            "manual_currency": (authority.get("manual_currency") or authority.get("currency") or "").strip().upper() or None,
            "manual_updated_at": authority.get("manual_updated_at") or (datetime.now().isoformat() if manual_price not in {None, ""} else None),
            "notes": authority.get("notes") or "",
        }
        with self.get_connection() as conn:
            existing = conn.execute("SELECT id FROM price_authority WHERE ticker = ?", (payload["ticker"],)).fetchone()
            if existing:
                payload["id"] = existing["id"]
            conn.execute(
                """
                INSERT INTO price_authority (
                    id, ticker, authority_mode, manual_price, manual_currency,
                    manual_updated_at, notes, updated_at
                )
                VALUES (
                    :id, :ticker, :authority_mode, :manual_price, :manual_currency,
                    :manual_updated_at, :notes, datetime('now')
                )
                ON CONFLICT(ticker) DO UPDATE SET
                    authority_mode = excluded.authority_mode,
                    manual_price = excluded.manual_price,
                    manual_currency = excluded.manual_currency,
                    manual_updated_at = excluded.manual_updated_at,
                    notes = excluded.notes,
                    updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return self.get_price_authority(payload["ticker"])[0]

    def save_market_data_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_market_data_config()
        payload = {**current, **config, "id": "default"}
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO market_data_config (
                    id, provider, benchmark_symbol, benchmark_label, benchmark_provider,
                    quote_ttl_minutes, stale_after_days, history_lookback_days, fx_max_age_days, updated_at
                )
                VALUES (
                    :id, :provider, :benchmark_symbol, :benchmark_label, :benchmark_provider,
                    :quote_ttl_minutes, :stale_after_days, :history_lookback_days, :fx_max_age_days, datetime('now')
                )
                ON CONFLICT(id) DO UPDATE SET
                    provider = excluded.provider,
                    benchmark_symbol = excluded.benchmark_symbol,
                    benchmark_label = excluded.benchmark_label,
                    benchmark_provider = excluded.benchmark_provider,
                    quote_ttl_minutes = excluded.quote_ttl_minutes,
                    stale_after_days = excluded.stale_after_days,
                    history_lookback_days = excluded.history_lookback_days,
                    fx_max_age_days = excluded.fx_max_age_days,
                    updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return self.get_market_data_config()

    def get_market_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM market_data_cache WHERE cache_key = ?", (cache_key,)).fetchone()
            if not row:
                return None
            item = dict(row)
            if datetime.fromisoformat(item["expires_at"]) < datetime.now():
                return None
            item["payload"] = self._safe_json(item.get("payload"))
            return item

    def set_market_cache(self, cache_key: str, payload: Dict[str, Any], provider: str, expires_at: str) -> Dict[str, Any]:
        row = {
            "cache_key": cache_key,
            "payload": json.dumps(payload or {}, ensure_ascii=False),
            "provider": provider.upper(),
            "expires_at": expires_at,
        }
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO market_data_cache (cache_key, payload, provider, expires_at, updated_at)
                VALUES (:cache_key, :payload, :provider, :expires_at, datetime('now'))
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload, provider = excluded.provider,
                    expires_at = excluded.expires_at, updated_at = datetime('now')
                """,
                row,
            )
            conn.commit()
        return row

    def save_fx_rate(self, rate: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": rate.get("id") or str(uuid.uuid4()),
            "base_currency": rate["base_currency"].upper(),
            "quote_currency": rate["quote_currency"].upper(),
            "rate": float(rate.get("rate", 0) or 0),
            "rate_date": str(rate["rate_date"])[:10],
            "provider": (rate.get("provider") or "MANUAL").upper(),
            "source": self._clean_source(rate.get("source", "MARKET_DATA")),
            "retrieved_at": rate.get("retrieved_at") or datetime.now().isoformat(),
            "metadata": json.dumps(rate.get("metadata") or {}, ensure_ascii=False),
        }
        if payload["rate"] <= 0:
            raise ValueError("FX rate must be positive.")
        with self.get_connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM fx_rates
                WHERE base_currency = ? AND quote_currency = ? AND rate_date = ? AND provider = ?
                """,
                (payload["base_currency"], payload["quote_currency"], payload["rate_date"], payload["provider"]),
            ).fetchone()
            if existing:
                payload["id"] = existing["id"]
            conn.execute(
                """
                INSERT INTO fx_rates (
                    id, base_currency, quote_currency, rate, rate_date, provider, source, retrieved_at, metadata, updated_at
                )
                VALUES (
                    :id, :base_currency, :quote_currency, :rate, :rate_date, :provider, :source, :retrieved_at, :metadata, datetime('now')
                )
                ON CONFLICT(base_currency, quote_currency, rate_date, provider) DO UPDATE SET
                    rate = excluded.rate, source = excluded.source, retrieved_at = excluded.retrieved_at,
                    metadata = excluded.metadata, updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return self._decode_market_row(payload)

    def get_fx_rates(self, base_currency: Optional[str] = None, quote_currency: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if base_currency:
            clauses.append("base_currency = ?")
            params.append(base_currency.upper())
        if quote_currency:
            clauses.append("quote_currency = ?")
            params.append(quote_currency.upper())
        if start:
            clauses.append("rate_date >= ?")
            params.append(start[:10])
        if end:
            clauses.append("rate_date <= ?")
            params.append(end[:10])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(f"SELECT * FROM fx_rates {where} ORDER BY rate_date, base_currency, quote_currency", params).fetchall()
            return [self._decode_market_row(dict(row)) for row in rows]

    def get_fx_rate_on_or_before(self, base_currency: str, quote_currency: str, target_date: str, max_age_days: int = 5) -> Optional[Dict[str, Any]]:
        base = base_currency.upper()
        quote = quote_currency.upper()
        if base == quote:
            return {"base_currency": base, "quote_currency": quote, "rate": 1.0, "rate_date": target_date[:10], "provider": "IDENTITY", "source": "SYSTEM"}
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM fx_rates
                WHERE base_currency = ? AND quote_currency = ? AND rate_date <= ?
                ORDER BY rate_date DESC
                LIMIT 1
                """,
                (base, quote, target_date[:10]),
            ).fetchone()
            if not row:
                return None
            item = self._decode_market_row(dict(row))
            age = (datetime.fromisoformat(target_date[:10]).date() - datetime.fromisoformat(item["rate_date"]).date()).days
            if age > max_age_days:
                return None
            return item

    def import_fx_rates_csv(self, content: str, source: str = "MANUAL") -> Dict[str, Any]:
        rows = self._parse_csv_rows(content)
        accepted, rejected = [], []
        for index, row in enumerate(rows, start=2):
            try:
                payload = {
                    "base_currency": row.get("base") or row.get("base_currency"),
                    "quote_currency": row.get("quote") or row.get("quote_currency"),
                    "rate": float(row.get("rate") or ""),
                    "rate_date": row.get("date") or row.get("rate_date"),
                    "provider": row.get("provider") or source,
                    "source": source,
                }
                if not payload["base_currency"] or not payload["quote_currency"] or not payload["rate_date"]:
                    raise ValueError("base, quote and date are required")
                datetime.fromisoformat(str(payload["rate_date"]).replace("Z", "+00:00"))
                if payload["rate"] <= 0:
                    raise ValueError("rate must be positive")
                accepted.append(payload)
            except Exception as exc:
                rejected.append({"row_number": index, "row": row, "error": str(exc)})
        for payload in accepted:
            self.save_fx_rate(payload)
        return {
            "accepted_rows": accepted,
            "rejected_rows": rejected,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "imported_count": len(accepted),
        }

    def import_benchmark_prices_csv(self, content: str, benchmark_key: str, label: Optional[str] = None, source: str = "MANUAL") -> Dict[str, Any]:
        rows = self._parse_csv_rows(content)
        accepted, rejected = [], []
        for index, row in enumerate(rows, start=2):
            try:
                payload = {
                    "benchmark_key": benchmark_key,
                    "label": row.get("label") or label or benchmark_key,
                    "valuation_date": row.get("valuation_date") or row.get("date") or row.get("fecha"),
                    "price": float(row.get("price") or row.get("precio") or ""),
                    "currency": row.get("currency") or row.get("moneda") or "USD",
                    "source": row.get("source") or source,
                }
                if not payload["valuation_date"]:
                    raise ValueError("valuation_date is required")
                datetime.fromisoformat(str(payload["valuation_date"]).replace("Z", "+00:00"))
                if payload["price"] <= 0:
                    raise ValueError("price must be positive")
                accepted.append(payload)
            except Exception as exc:
                rejected.append({"row_number": index, "row": row, "error": str(exc)})
        for payload in accepted:
            self.save_benchmark_price(payload)
        return {
            "accepted_rows": accepted,
            "rejected_rows": rejected,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "imported_count": len(accepted),
        }

    def get_investment_transactions(
        self,
        ticker: Optional[str] = None,
        operation_type: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if ticker:
            clauses.append("ticker = ?")
            params.append(ticker.upper())
        if operation_type:
            clauses.append("operation_type = ?")
            params.append(self._clean_investment_operation_type(operation_type))
        if start:
            clauses.append("occurred_at >= ?")
            params.append(start[:10])
        if end:
            clauses.append("occurred_at <= ?")
            params.append(end[:10])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM investment_transactions {where} ORDER BY occurred_at, created_at, id",
                params,
            ).fetchall()
            return [self._decode_investment_transaction(dict(row)) for row in rows]

    def save_investment_transaction(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._normalize_investment_transaction(operation)
        with self.get_connection() as conn:
            if payload.get("external_id"):
                existing = conn.execute(
                    "SELECT id FROM investment_transactions WHERE source = ? AND external_id = ?",
                    (payload["source"], payload["external_id"]),
                ).fetchone()
                if existing:
                    payload["id"] = existing["id"]
            conn.execute(
                """
                INSERT INTO investment_transactions (
                    id, occurred_at, ticker, account_id, operation_type, quantity, price,
                    amount, fee, currency, source, external_id, notes, metadata, updated_at
                )
                VALUES (
                    :id, :occurred_at, :ticker, :account_id, :operation_type, :quantity, :price,
                    :amount, :fee, :currency, :source, :external_id, :notes, :metadata, datetime('now')
                )
                ON CONFLICT(id) DO UPDATE SET
                    occurred_at = excluded.occurred_at, ticker = excluded.ticker, account_id = excluded.account_id,
                    operation_type = excluded.operation_type, quantity = excluded.quantity, price = excluded.price,
                    amount = excluded.amount, fee = excluded.fee, currency = excluded.currency, source = excluded.source,
                    external_id = excluded.external_id, notes = excluded.notes, metadata = excluded.metadata,
                    updated_at = datetime('now')
                """,
                payload,
            )
            conn.commit()
        return self._decode_investment_transaction(payload)

    def delete_investment_transaction(self, operation_id: str):
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM investment_transactions WHERE id = ?", (operation_id,))
            deleted = cursor.rowcount > 0
            self._insert_action_event(
                conn,
                "MANUAL",
                "INVESTMENT_OPERATION_DELETE",
                "Operación de inversión eliminada." if deleted else "Operación de inversión no encontrada; sin cambios.",
                "INFO",
                {"entity_id": operation_id, "deleted": deleted},
            )
            conn.commit()

    def preview_investment_transactions_csv(self, content: str, source: str = "CSV") -> Dict[str, Any]:
        rows = self._parse_csv_rows(content)
        accepted, rejected, duplicate_count = [], [], 0
        with self.get_connection() as conn:
            for index, row in enumerate(rows, start=2):
                try:
                    payload = self._normalize_investment_transaction({
                        "occurred_at": row.get("occurred_at") or row.get("date") or row.get("fecha"),
                        "ticker": row.get("ticker") or row.get("symbol"),
                        "account_id": row.get("account_id") or None,
                        "operation_type": row.get("operation_type") or row.get("type") or row.get("tipo"),
                        "quantity": row.get("quantity") or row.get("cantidad") or 0,
                        "price": row.get("price") or row.get("precio") or 0,
                        "amount": row.get("amount") or row.get("importe") or 0,
                        "fee": row.get("fee") or row.get("commission") or row.get("comision") or 0,
                        "currency": row.get("currency") or row.get("moneda") or "USD",
                        "source": row.get("source") or source,
                        "external_id": row.get("external_id") or row.get("id") or None,
                        "notes": row.get("notes") or row.get("descripcion") or "",
                        "metadata": row,
                    })
                    if self._investment_transaction_exists(conn, payload):
                        duplicate_count += 1
                    accepted.append(payload)
                except Exception as exc:
                    rejected.append({"row_number": index, "row": row, "error": str(exc)})
        return {
            "accepted_rows": accepted,
            "rejected_rows": rejected,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "duplicate_count": duplicate_count,
            "new_count": max(len(accepted) - duplicate_count, 0),
        }

    def import_investment_transactions_csv(self, content: str, source: str = "CSV") -> Dict[str, Any]:
        preview = self.preview_investment_transactions_csv(content, source=source)
        imported, duplicates = 0, 0
        with self.get_connection() as conn:
            for row in preview["accepted_rows"]:
                if self._investment_transaction_exists(conn, row):
                    duplicates += 1
                    continue
                conn.execute(
                    """
                    INSERT INTO investment_transactions (
                        id, occurred_at, ticker, account_id, operation_type, quantity, price,
                        amount, fee, currency, source, external_id, notes, metadata, updated_at
                    )
                    VALUES (
                        :id, :occurred_at, :ticker, :account_id, :operation_type, :quantity, :price,
                        :amount, :fee, :currency, :source, :external_id, :notes, :metadata, datetime('now')
                    )
                    """,
                    row,
                )
                imported += 1
            conn.commit()
        return {**preview, "imported_count": imported, "duplicate_count": max(preview["duplicate_count"], duplicates)}

    def preview_investment_operations(self, operations: List[Dict[str, Any]], source: str = "ETORO") -> Dict[str, Any]:
        accepted, rejected, duplicate_count, update_count, conflict_count = [], [], 0, 0, 0
        classifications = []
        clean_source = self._clean_source(source)
        with self.get_connection() as conn:
            for index, operation in enumerate(operations, start=1):
                try:
                    payload = self._normalize_investment_transaction({**operation, "source": operation.get("source") or clean_source})
                    existing = self._get_investment_transaction_by_external_id(conn, payload["source"], payload.get("external_id"))
                    classification = "ready_to_import"
                    differences: Dict[str, Any] = {}
                    if existing:
                        duplicate_count += 1
                        classification, differences = self._classify_investment_update(existing, payload)
                        if classification == "update_candidate":
                            update_count += 1
                        elif classification == "local_conflict":
                            conflict_count += 1
                    accepted.append(payload)
                    classifications.append({
                        "external_id": payload.get("external_id"),
                        "ticker": payload.get("ticker"),
                        "operation_type": payload.get("operation_type"),
                        "classification": classification,
                        "differences": differences,
                    })
                except Exception as exc:
                    rejected.append({"row_number": index, "row": operation, "error": str(exc)})
        return {
            "accepted_rows": accepted,
            "rejected_rows": rejected,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "duplicate_count": duplicate_count,
            "update_count": update_count,
            "local_conflict_count": conflict_count,
            "new_count": max(len(accepted) - duplicate_count, 0),
            "classifications": classifications,
        }

    def import_investment_operations(self, operations: List[Dict[str, Any]], source: str = "ETORO") -> Dict[str, Any]:
        preview = self.preview_investment_operations(operations, source=source)
        if preview.get("local_conflict_count", 0) > 0:
            raise ValueError("Local conflicts detected. Resolve conflicts before importing.")
        imported, duplicates, updated = 0, 0, 0
        with self.get_connection() as conn:
            try:
                for row, classification in zip(preview["accepted_rows"], preview["classifications"]):
                    if classification["classification"] == "unchanged":
                        duplicates += 1
                        continue
                    existing = None
                    if row.get("external_id"):
                        existing = conn.execute(
                            "SELECT id FROM investment_transactions WHERE source = ? AND external_id = ?",
                            (row["source"], row["external_id"]),
                        ).fetchone()
                    if existing:
                        row["id"] = existing["id"]
                        updated += 1
                    conn.execute(
                        """
                        INSERT INTO investment_transactions (
                            id, occurred_at, ticker, account_id, operation_type, quantity, price,
                            amount, fee, currency, source, external_id, notes, metadata, updated_at
                        )
                        VALUES (
                            :id, :occurred_at, :ticker, :account_id, :operation_type, :quantity, :price,
                            :amount, :fee, :currency, :source, :external_id, :notes, :metadata, datetime('now')
                        )
                        ON CONFLICT(id) DO UPDATE SET
                            occurred_at = excluded.occurred_at, ticker = excluded.ticker, account_id = excluded.account_id,
                            operation_type = excluded.operation_type, quantity = excluded.quantity, price = excluded.price,
                            amount = excluded.amount, fee = excluded.fee, currency = excluded.currency, source = excluded.source,
                            external_id = excluded.external_id, notes = excluded.notes, metadata = excluded.metadata,
                            updated_at = datetime('now')
                        """,
                        row,
                    )
                    if not existing:
                        imported += 1
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {**preview, "imported_count": imported, "updated_count": updated, "duplicate_count": max(preview["duplicate_count"], duplicates)}

    def export_mapping_config(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "exported_at": datetime.now().isoformat(),
            "etoro_instrument_mappings": self.get_source_mappings("ETORO", "instrument"),
            "market_symbol_mappings": self.get_symbol_mappings(),
            "price_authority": self.get_price_authority(),
        }

    def validate_mapping_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        required = {"etoro_instrument_mappings", "market_symbol_mappings", "price_authority"}
        missing = sorted(required - set(payload.keys()))
        errors = [f"Missing {key}" for key in missing]
        counts = {key: len(payload.get(key) or []) for key in required if isinstance(payload.get(key) or [], list)}
        return {"valid": not errors, "errors": errors, "counts": counts}

    def import_mapping_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        validation = self.validate_mapping_config(payload)
        if not validation["valid"]:
            errors = validation["errors"]
            self._try_add_action_event(
                "MANUAL",
                "MAPPING_CONFIG_IMPORT_FAILED",
                "La importación de mappings fue rechazada; no se aplicó ningún cambio.",
                "WARNING",
                {"errors": errors},
            )
            raise ValueError("; ".join(errors))
        imported = {"etoro_instrument_mappings": 0, "market_symbol_mappings": 0, "price_authority": 0}
        with self.get_connection() as conn:
            try:
                for mapping in payload.get("etoro_instrument_mappings", []):
                    clean = {
                        "id": mapping.get("id") or str(uuid.uuid4()),
                        "source": "ETORO",
                        "external_type": "instrument",
                        "external_id": str(mapping["external_id"]),
                        "external_name": mapping.get("external_name", ""),
                        "local_id": mapping.get("local_id"),
                        "local_type": mapping.get("local_type") or "ticker",
                        "is_active": 1 if mapping.get("is_active", True) else 0,
                    }
                    conn.execute(
                        """
                        INSERT INTO source_mappings (id, source, external_type, external_id, external_name, local_id, local_type, is_active, updated_at)
                        VALUES (:id, :source, :external_type, :external_id, :external_name, :local_id, :local_type, :is_active, datetime('now'))
                        ON CONFLICT(source, external_type, external_id) DO UPDATE SET
                            external_name = excluded.external_name, local_id = excluded.local_id,
                            local_type = excluded.local_type, is_active = excluded.is_active, updated_at = datetime('now')
                        """,
                        clean,
                    )
                    imported["etoro_instrument_mappings"] += 1
                for mapping in payload.get("market_symbol_mappings", []):
                    clean = {
                        "id": mapping.get("id") or str(uuid.uuid4()),
                        "internal_symbol": mapping["internal_symbol"].strip().upper(),
                        "provider": (mapping.get("provider") or "YFINANCE").strip().upper(),
                        "provider_symbol": mapping["provider_symbol"].strip().upper(),
                        "instrument_type": (mapping.get("instrument_type") or "EQUITY").strip().upper(),
                        "expected_currency": (mapping.get("expected_currency") or "").strip().upper() or None,
                        "status": (mapping.get("status") or "ACTIVE").strip().upper(),
                        "notes": mapping.get("notes") or "",
                    }
                    conn.execute(
                        """
                        INSERT INTO market_symbol_mappings (id, internal_symbol, provider, provider_symbol, instrument_type, expected_currency, status, notes, updated_at)
                        VALUES (:id, :internal_symbol, :provider, :provider_symbol, :instrument_type, :expected_currency, :status, :notes, datetime('now'))
                        ON CONFLICT(internal_symbol, provider) DO UPDATE SET
                            provider_symbol = excluded.provider_symbol, instrument_type = excluded.instrument_type,
                            expected_currency = excluded.expected_currency, status = excluded.status,
                            notes = excluded.notes, updated_at = datetime('now')
                        """,
                        clean,
                    )
                    imported["market_symbol_mappings"] += 1
                for authority in payload.get("price_authority", []):
                    clean = {
                        "id": authority.get("id") or str(uuid.uuid4()),
                        "ticker": authority["ticker"].strip().upper(),
                        "authority_mode": (authority.get("authority_mode") or "AUTO").upper(),
                        "manual_price": authority.get("manual_price"),
                        "manual_currency": authority.get("manual_currency"),
                        "manual_updated_at": authority.get("manual_updated_at"),
                        "notes": authority.get("notes") or "",
                    }
                    conn.execute(
                        """
                        INSERT INTO price_authority (id, ticker, authority_mode, manual_price, manual_currency, manual_updated_at, notes, updated_at)
                        VALUES (:id, :ticker, :authority_mode, :manual_price, :manual_currency, :manual_updated_at, :notes, datetime('now'))
                        ON CONFLICT(ticker) DO UPDATE SET
                            authority_mode = excluded.authority_mode, manual_price = excluded.manual_price,
                            manual_currency = excluded.manual_currency, manual_updated_at = excluded.manual_updated_at,
                            notes = excluded.notes, updated_at = datetime('now')
                        """,
                        clean,
                    )
                    imported["price_authority"] += 1
                self._insert_action_event(
                    conn,
                    "MANUAL",
                    "MAPPING_CONFIG_IMPORT_SUCCESS",
                    "Configuración de mappings importada.",
                    "INFO",
                    {"imported": imported},
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                self._try_add_action_event(
                    "MANUAL",
                    "MAPPING_CONFIG_IMPORT_FAILED",
                    "La importación de mappings falló; no se aplicó ningún cambio.",
                    "ERROR",
                    {"error_type": type(exc).__name__},
                )
                raise
        return {"status": "IMPORTED", "imported": imported}

    def get_opening_positions(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if ticker:
            clauses.append("ticker = ?")
            params.append(ticker.upper())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM opening_positions {where} ORDER BY opened_at, ticker, account_id",
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def save_opening_position(self, position: Dict[str, Any]) -> Dict[str, Any]:
        quantity = float(position.get("quantity", 0) or 0)
        unit_cost = float(position.get("unit_cost", 0) or 0)
        total_cost = float(position.get("total_cost", 0) or 0)
        if quantity <= 0:
            raise ValueError("Opening position quantity must be positive.")
        if total_cost <= 0 and unit_cost > 0:
            total_cost = quantity * unit_cost
        if unit_cost <= 0 and total_cost > 0:
            unit_cost = total_cost / quantity
        payload = {
            "id": position.get("id") or str(uuid.uuid4()),
            "ticker": position["ticker"].strip().upper(),
            "account_id": position.get("account_id") or None,
            "opened_at": str(position.get("opened_at") or position.get("date"))[:10],
            "quantity": quantity,
            "unit_cost": unit_cost,
            "total_cost": total_cost,
            "currency": position.get("currency", "USD").upper(),
            "source": self._clean_source(position.get("source", "MANUAL")),
            "notes": position.get("notes") or "",
        }
        with self.get_connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM opening_positions
                WHERE ticker = ? AND COALESCE(account_id, '') = COALESCE(?, '') AND opened_at = ? AND source = ?
                """,
                (payload["ticker"], payload["account_id"], payload["opened_at"], payload["source"]),
            ).fetchone()
            if existing:
                payload["id"] = existing["id"]
                conn.execute(
                    """
                    UPDATE opening_positions
                    SET quantity = :quantity, unit_cost = :unit_cost, total_cost = :total_cost,
                        currency = :currency, notes = :notes, updated_at = datetime('now')
                    WHERE id = :id
                    """,
                    payload,
                )
            else:
                conn.execute(
                    """
                    INSERT INTO opening_positions (id, ticker, account_id, opened_at, quantity, unit_cost, total_cost, currency, source, notes, updated_at)
                    VALUES (:id, :ticker, :account_id, :opened_at, :quantity, :unit_cost, :total_cost, :currency, :source, :notes, datetime('now'))
                    """,
                    payload,
                )
            conn.commit()
        self.add_reconciliation_audit_event(payload["ticker"], payload["account_id"], "OPENING_POSITION_SAVED", payload)
        return payload

    def get_position_authority(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM position_authority ORDER BY ticker, account_id").fetchall()]

    def set_position_authority(self, ticker: str, state: str, account_id: Optional[str] = None, notes: str = "") -> Dict[str, Any]:
        clean_state = state.strip().upper()
        if clean_state not in {"MANUAL", "LEDGER_PENDING", "LEDGER_AUTHORITATIVE", "RECONCILIATION_REQUIRED"}:
            raise ValueError(f"Unsupported authority state: {state}")
        payload = {
            "id": str(uuid.uuid4()),
            "ticker": ticker.strip().upper(),
            "account_id": account_id or None,
            "authority_state": clean_state,
            "adopted_at": datetime.now().isoformat() if clean_state == "LEDGER_AUTHORITATIVE" else None,
            "reverted_at": datetime.now().isoformat() if clean_state == "MANUAL" else None,
            "notes": notes,
        }
        with self.get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM position_authority WHERE ticker = ? AND COALESCE(account_id, '') = COALESCE(?, '')",
                (payload["ticker"], payload["account_id"]),
            ).fetchone()
            if existing:
                payload["id"] = existing["id"]
                conn.execute(
                    """
                    UPDATE position_authority
                    SET authority_state = :authority_state,
                        adopted_at = COALESCE(:adopted_at, adopted_at),
                        reverted_at = COALESCE(:reverted_at, reverted_at),
                        notes = :notes,
                        updated_at = datetime('now')
                    WHERE id = :id
                    """,
                    payload,
                )
            else:
                conn.execute(
                    """
                    INSERT INTO position_authority (id, ticker, account_id, authority_state, adopted_at, reverted_at, notes, updated_at)
                    VALUES (:id, :ticker, :account_id, :authority_state, :adopted_at, :reverted_at, :notes, datetime('now'))
                    """,
                    payload,
                )
            conn.commit()
        self.add_reconciliation_audit_event(payload["ticker"], payload["account_id"], f"AUTHORITY_{clean_state}", payload)
        return payload

    def add_reconciliation_audit_event(self, ticker: str, account_id: Optional[str], event_type: str, payload: Dict[str, Any]):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO reconciliation_audit_events (id, ticker, account_id, event_type, payload) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), ticker.upper(), account_id, event_type, json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()

    def get_reconciliation_audit_events(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if ticker:
            clauses.append("ticker = ?")
            params.append(ticker.upper())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM reconciliation_audit_events {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["payload"] = self._safe_json(item.get("payload"))
                result.append(item)
            return result

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
                SELECT t.*, a.name as account_name, c.flow_type as flow_type
                FROM transactions t
                LEFT JOIN accounts a ON t.account_id = a.id
                LEFT JOIN categories c ON t.category = c.name
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
            cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
            deleted = cursor.rowcount > 0
            self._insert_action_event(
                conn,
                "MANUAL",
                "TRANSACTION_DELETE",
                "Transacción eliminada." if deleted else "Transacción no encontrada; sin cambios.",
                "INFO",
                {"entity_id": tx_id, "deleted": deleted},
            )
            conn.commit()

    def get_transaction_summary(self) -> Dict[str, float]:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN COALESCE(c.flow_type, CASE WHEN t.amount > 0 THEN 'INCOME' ELSE 'EXPENSE' END) = 'INCOME' AND t.amount > 0 THEN t.amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN COALESCE(c.flow_type, CASE WHEN t.amount < 0 THEN 'EXPENSE' ELSE 'INCOME' END) = 'EXPENSE' AND t.amount < 0 THEN ABS(t.amount) ELSE 0 END), 0) as expenses
                FROM transactions t
                LEFT JOIN categories c ON t.category = c.name
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
            cursor = conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
            deleted = cursor.rowcount > 0
            self._insert_action_event(
                conn,
                "MANUAL",
                "BUDGET_DELETE",
                "Presupuesto eliminado." if deleted else "Presupuesto no encontrado; sin cambios.",
                "INFO",
                {"entity_id": budget_id, "deleted": deleted},
            )
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

    def import_budgetbakers_plan(self, budgets: List[Dict[str, Any]], standing_orders: List[Dict[str, Any]]) -> Dict[str, int]:
        """Apply a BudgetBakers import plan and record exactly one audit event for it.

        The endpoint delegates here so the whole plan is one user-visible operation:
        each row keeps its existing per-row commit behavior, and the single event is
        written after the outcome is known and can never mask a failed import.
        """
        imported_budgets = 0
        imported_orders = 0
        try:
            for budget in budgets:
                self.save_budget({**budget, "source": "BUDGETBAKERS"})
                imported_budgets += 1
            for order in standing_orders:
                self.upsert_recurring_rule({**order, "source": "BUDGETBAKERS", "status": "confirmed"})
                imported_orders += 1
        except Exception as exc:
            self._try_add_action_event(
                "BUDGETBAKERS",
                "IMPORT_PLAN_FAILED",
                "La importación del plan de BudgetBakers falló.",
                "ERROR",
                {
                    "imported_budgets": imported_budgets,
                    "imported_standing_orders": imported_orders,
                    "error_type": type(exc).__name__,
                },
            )
            raise
        self._try_add_action_event(
            "BUDGETBAKERS",
            "IMPORT_PLAN_SUCCESS",
            "Plan de BudgetBakers importado.",
            "INFO",
            {"imported_budgets": imported_budgets, "imported_standing_orders": imported_orders},
        )
        return {"imported_budgets": imported_budgets, "imported_standing_orders": imported_orders}

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

    def _insert_action_event(
        self,
        conn: sqlite3.Connection,
        source: str,
        event_type: str,
        message: str,
        severity: str = "INFO",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write one action_events row on an existing connection; the caller owns the commit.

        Writing on the caller's connection lets a mutation and its audit record share
        a single transaction, so either both persist or neither does.
        """
        conn.execute(
            "INSERT INTO action_events (id, source, event_type, severity, message, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), self._clean_source(source), event_type, severity, message, json.dumps(payload or {}, ensure_ascii=False)),
        )

    def add_action_event(self, source: str, event_type: str, message: str, severity: str = "INFO", payload: Optional[Dict[str, Any]] = None):
        with self.get_connection() as conn:
            self._insert_action_event(conn, source, event_type, message, severity, payload)
            conn.commit()

    def _try_add_action_event(
        self,
        source: str,
        event_type: str,
        message: str,
        severity: str = "INFO",
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Best-effort audit write for mutations that cannot share one transaction.

        Restore replaces the database file and the import-plan loop commits row by
        row, so their events are written after the outcome is known. This helper never
        raises: recording the outcome must not mask, reverse or alter the operation
        being audited. Failures are logged instead.
        """
        if not os.path.isfile(self.db_path):
            logger.warning("Skipped action event %s/%s: no local database to record it in", source, event_type)
            return False
        try:
            with closing(self.get_connection()) as conn:
                self._insert_action_event(conn, source, event_type, message, severity, payload)
                conn.commit()
            return True
        except Exception:
            logger.exception("Could not record action event %s/%s", source, event_type)
            return False

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

    def _backup_directory(self) -> str:
        """Canonical directory where FINANCE writes its own backups."""
        return os.path.realpath(
            os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "backups")
        )

    def _resolve_backup_path(self, backup_path: str) -> str:
        """Resolve a caller-supplied backup path, failing closed outside the backup directory.

        Only files directly inside <dirname(db_path)>/backups/ whose names match the
        FINANCE-generated patterns (`finance-backup-*.db`, `finance-pre-restore-*.db`)
        are accepted. Resolution uses real paths, so traversal, foreign, sibling,
        UNC and symlinked locations outside the directory are rejected.
        """
        if not isinstance(backup_path, str) or not backup_path.strip():
            raise ValueError("Backup path is not allowed.")

        backup_dir = self._backup_directory()
        resolved = os.path.realpath(os.path.abspath(backup_path))

        if os.path.normcase(os.path.dirname(resolved)) != os.path.normcase(backup_dir):
            raise ValueError("Backup path must be inside the FINANCE backup directory.")

        filename = os.path.basename(resolved)
        if not filename.endswith(".db"):
            raise ValueError("Backup file name must use the .db FINANCE backup pattern.")
        if not filename.startswith(BACKUP_FILE_PREFIXES):
            raise ValueError("Backup file name does not match a FINANCE-generated backup.")
        if not os.path.isfile(resolved):
            raise ValueError("Backup file does not exist.")
        return resolved

    def _copy_sqlite(self, source_path: str, destination_path: str) -> None:
        """Copy a SQLite database with the SQLite backup API and deterministic closes.

        Both connections are always closed, so the result is a transactionally
        consistent snapshot instead of a mid-write byte copy of a live file, and
        Windows never keeps a stray handle on a generated backup.
        """
        if not os.path.isfile(source_path):
            raise ValueError("Source database file does not exist.")
        if os.path.abspath(source_path) == os.path.abspath(destination_path):
            raise ValueError("Source and destination database must be different files.")
        with closing(sqlite3.connect(source_path)) as source_conn:
            with closing(sqlite3.connect(destination_path)) as destination_conn:
                source_conn.backup(destination_conn)
                destination_conn.commit()

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
            "fx_rates",
            "market_data_cache",
            "market_data_config",
            "market_symbol_mappings",
            "price_authority",
            "investment_transactions",
            "opening_positions",
            "position_authority",
            "reconciliation_audit_events",
            "schema_migrations",
        ]
        with closing(self.get_connection()) as conn:
            data = {
                table: [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]
                for table in tables
                if table in self._table_names(conn.cursor())
            }
        backup_dir = os.path.join(os.path.dirname(self.db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        db_copy = os.path.join(backup_dir, f"finance-backup-{stamp}.db")
        self._copy_sqlite(self.db_path, db_copy)
        logger.info("Created local backup at %s", db_copy)
        return {
            "generated_at": datetime.now().isoformat(),
            "db_backup_path": db_copy,
            "schema": self.get_schema_info(),
            "data": data,
        }

    def _validate_database_file(self, path: str) -> Dict[str, Any]:
        """Validate integrity, required tables and migration records of a database file."""
        try:
            with closing(sqlite3.connect(path)) as conn:
                conn.row_factory = sqlite3.Row
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
                    "tables": sorted(tables),
                    "latest_version": migrations[-1]["version"] if migrations else None,
                    "migrations": migrations,
                }
        except sqlite3.DatabaseError as exc:
            raise ValueError("Backup file is not a valid SQLite database.") from exc

    def validate_backup(self, backup_path: str) -> Dict[str, Any]:
        resolved = self._resolve_backup_path(backup_path)
        info = self._validate_database_file(resolved)
        return {"valid": True, "path": backup_path, **info}

    def _assert_migrations_compatible(self, path: str) -> None:
        """Fail unless every migration recorded in `path` exists unchanged in this build."""
        with closing(sqlite3.connect(path)) as conn:
            conn.row_factory = sqlite3.Row
            applied = [
                (row["filename"], row["checksum"])
                for row in conn.execute("SELECT filename, checksum FROM schema_migrations ORDER BY version")
            ]
        known: Dict[str, str] = {}
        for file_path in glob.glob(os.path.join(MIGRATIONS_DIR, "*_sqlite_*.sql")):
            with open(file_path, "r", encoding="utf-8") as f:
                known[os.path.basename(file_path)] = hashlib.sha256(f.read().encode("utf-8")).hexdigest()
        for filename, checksum in applied:
            if filename not in known:
                raise ValueError("Restored database applies a migration unknown to this build.")
            if known[filename] != checksum:
                raise ValueError("Restored database migration checksums do not match this build.")

    def _verify_restored_database(self) -> None:
        """Post-restore gate: schema/integrity invariants plus migration compatibility."""
        self._validate_database_file(self.db_path)
        self._assert_migrations_compatible(self.db_path)

    def _recover_previous_database(self, had_live_database: bool, pre_restore_path: str) -> bool:
        """Return the live database to its pre-restore state after a failed restore."""
        try:
            if had_live_database:
                self._copy_sqlite(pre_restore_path, self.db_path)
                self._validate_database_file(self.db_path)
            elif os.path.exists(self.db_path):
                os.remove(self.db_path)
            return True
        except Exception:
            logger.exception("Could not recover the live database after a failed restore")
            return False

    def restore_backup(self, backup_path: str) -> Dict[str, Any]:
        resolved = self._resolve_backup_path(backup_path)
        validation = self.validate_backup(resolved)
        backup_dir = os.path.join(os.path.dirname(self.db_path), "backups")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        pre_restore_path = os.path.join(backup_dir, f"finance-pre-restore-{stamp}.db")
        had_live_database = os.path.exists(self.db_path)

        try:
            os.makedirs(backup_dir, exist_ok=True)
            if had_live_database:
                self._copy_sqlite(self.db_path, pre_restore_path)
        except Exception as exc:
            raise ValueError("Could not create the pre-restore backup; restore was cancelled.") from exc

        try:
            self._copy_sqlite(resolved, self.db_path)
            self._verify_restored_database()
        except Exception as exc:
            recovered = self._recover_previous_database(had_live_database, pre_restore_path)
            self._try_add_action_event(
                "MANUAL",
                "BACKUP_RESTORE_FAILED",
                "La restauración falló; la base de datos anterior quedó intacta."
                if recovered
                else "La restauración falló y la base de datos no pudo recuperarse.",
                "ERROR",
                {
                    "backup_file": os.path.basename(resolved),
                    "recovered": recovered,
                    "error_type": type(exc).__name__,
                },
            )
            if recovered:
                raise ValueError("Restore failed; the previous database was left unchanged.") from exc
            raise ValueError("Restore failed and the live database could not be recovered.") from exc

        schema = self.get_schema_info()
        self._try_add_action_event(
            "MANUAL",
            "BACKUP_RESTORE_SUCCESS",
            "Base de datos local restaurada desde backup.",
            "INFO",
            {"backup_file": os.path.basename(resolved), "schema_version": schema["latest_version"]},
        )
        logger.warning("Restored local database from %s", backup_path)
        return {
            "status": "RESTORED",
            "restored_from": backup_path,
            "pre_restore_backup_path": pre_restore_path if os.path.exists(pre_restore_path) else None,
            "validation": validation,
            "schema": schema,
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

    def _decode_market_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        if "metadata" in row:
            row["metadata"] = self._safe_json(row.get("metadata"))
        return row

    def _transaction_fingerprint(self, tx: Dict[str, Any]) -> str:
        raw = f"{tx.get('date')}|{tx.get('amount')}|{tx.get('category')}|{tx.get('description')}|{tx.get('account_id')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _clean_source(self, source: str) -> str:
        value = (source or "MANUAL").upper()
        return value if value in VALID_SOURCES else "MANUAL"

    def _clean_investment_operation_type(self, operation_type: str) -> str:
        value = (operation_type or "").strip().upper()
        if value not in VALID_INVESTMENT_OPERATION_TYPES:
            raise ValueError(f"Unsupported investment operation type: {operation_type}")
        return value

    def _normalize_investment_transaction(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        metadata = operation.get("metadata", {})
        if isinstance(metadata, str):
            try:
                json.loads(metadata)
                metadata_json = metadata
            except Exception:
                metadata_json = json.dumps({"raw": metadata}, ensure_ascii=False)
        else:
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        occurred_at = operation.get("occurred_at") or operation.get("date")
        if not occurred_at:
            raise ValueError("occurred_at/date is required")
        payload = {
            "id": operation.get("id") or str(uuid.uuid4()),
            "occurred_at": str(occurred_at)[:19],
            "ticker": (operation.get("ticker") or "").strip().upper() or None,
            "account_id": operation.get("account_id") or None,
            "operation_type": self._clean_investment_operation_type(operation.get("operation_type") or operation.get("type")),
            "quantity": float(operation.get("quantity", 0) or 0),
            "price": float(operation.get("price", 0) or 0),
            "amount": float(operation.get("amount", 0) or 0),
            "fee": float(operation.get("fee", 0) or 0),
            "currency": (operation.get("currency") or "USD").upper(),
            "source": self._clean_source(operation.get("source", "MANUAL")),
            "external_id": operation.get("external_id") or None,
            "notes": operation.get("notes") or "",
            "metadata": metadata_json,
        }
        self._validate_investment_transaction(payload)
        if not payload["external_id"]:
            payload["external_id"] = self._investment_transaction_fingerprint(payload)
        return payload

    def _validate_investment_transaction(self, payload: Dict[str, Any]):
        datetime.fromisoformat(str(payload["occurred_at"]).replace("Z", "+00:00"))
        op = payload["operation_type"]
        if payload["quantity"] < 0:
            raise ValueError("quantity cannot be negative")
        if payload["price"] < 0 or payload["fee"] < 0:
            raise ValueError("price and fee cannot be negative")
        if op in {"BUY", "SELL"}:
            if not payload.get("ticker"):
                raise ValueError("ticker is required for BUY/SELL")
            if payload["quantity"] <= 0:
                raise ValueError("quantity must be positive for BUY/SELL")
            if payload["price"] <= 0 and payload["amount"] <= 0:
                raise ValueError("price or amount is required for BUY/SELL")
        if op in {"DIVIDEND", "INTEREST"} and payload["amount"] == 0:
            raise ValueError("amount is required for income operations")
        if op in {"CONTRIBUTION", "WITHDRAWAL", "FEE"} and payload["amount"] == 0:
            raise ValueError("amount is required for cashflow/fee operations")

    def _decode_investment_transaction(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row["metadata"] = self._safe_json(row.get("metadata"))
        return row

    def _investment_transaction_exists(self, conn: sqlite3.Connection, row: Dict[str, Any]) -> bool:
        if row.get("external_id"):
            found = conn.execute(
                "SELECT 1 FROM investment_transactions WHERE source = ? AND external_id = ? LIMIT 1",
                (row.get("source", "CSV"), row["external_id"]),
            ).fetchone()
            if found:
                return True
        return False

    def _get_investment_transaction_by_external_id(self, conn: sqlite3.Connection, source: str, external_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not external_id:
            return None
        row = conn.execute(
            "SELECT * FROM investment_transactions WHERE source = ? AND external_id = ? LIMIT 1",
            (source, external_id),
        ).fetchone()
        return self._decode_investment_transaction(dict(row)) if row else None

    def _classify_investment_update(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        fields = ["occurred_at", "ticker", "account_id", "operation_type", "quantity", "price", "amount", "fee", "currency"]
        differences = {}
        for field in fields:
            old_value = existing.get(field)
            new_value = incoming.get(field)
            if isinstance(old_value, float) or isinstance(new_value, float):
                if round(float(old_value or 0), 8) != round(float(new_value or 0), 8):
                    differences[field] = {"local": old_value, "incoming": new_value}
            elif old_value != new_value:
                differences[field] = {"local": old_value, "incoming": new_value}
        if not differences:
            return "unchanged", {}
        metadata = existing.get("metadata") or {}
        notes = existing.get("notes") or ""
        if existing.get("source") == "ETORO" and "manual" not in notes.lower():
            return "update_candidate", differences
        return "local_conflict", differences

    def _investment_transaction_fingerprint(self, operation: Dict[str, Any]) -> str:
        raw = "|".join(str(operation.get(key, "")) for key in ["occurred_at", "ticker", "operation_type", "quantity", "price", "amount", "fee", "currency", "account_id"])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
