"""
Database Manager & Repository Layer
Supports local SQLite database with full parity to Supabase PostgreSQL schemas.
Handles schema initialization, migrations, seeding, and transactional queries.
"""

import os
import sqlite3
import json
from typing import List, Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(__file__), "finanzas.db")
MIGRATION_FILE = os.path.join(os.path.dirname(__file__), "migrations", "001_sqlite_local.sql")
SEED_FILE = os.path.join(os.path.dirname(__file__), "seeds", "initial_seed.sql")

class DatabaseManager:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._initialize_database()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_database(self):
        """Runs the SQLite migration and seeds initial records if newly created."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Run migration
            if os.path.exists(MIGRATION_FILE):
                with open(MIGRATION_FILE, "r", encoding="utf-8") as f:
                    cursor.executescript(f.read())

            # Seed if assets table is empty
            cursor.execute("SELECT COUNT(*) as count FROM assets")
            count = cursor.fetchone()["count"]
            if count == 0 and os.path.exists(SEED_FILE):
                with open(SEED_FILE, "r", encoding="utf-8") as f:
                    cursor.executescript(f.read())
            conn.commit()

    # --- Assets ---
    def get_assets(self, include_watchlist: bool = True) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if include_watchlist:
                cursor.execute("SELECT * FROM assets ORDER BY asset_type, ticker")
            else:
                cursor.execute("SELECT * FROM assets WHERE is_watchlist = 0 ORDER BY asset_type, ticker")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def add_or_update_asset(self, asset: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO assets (ticker, name, asset_type, sector, country, quantity, avg_price, current_price, currency, is_watchlist, logo_url, target_allocation_pct, updated_at)
                VALUES (:ticker, :name, :asset_type, :sector, :country, :quantity, :avg_price, :current_price, :currency, :is_watchlist, :logo_url, :target_allocation_pct, datetime('now'))
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name,
                    asset_type = excluded.asset_type,
                    sector = excluded.sector,
                    country = excluded.country,
                    quantity = excluded.quantity,
                    avg_price = excluded.avg_price,
                    current_price = excluded.current_price,
                    currency = excluded.currency,
                    is_watchlist = excluded.is_watchlist,
                    logo_url = excluded.logo_url,
                    target_allocation_pct = excluded.target_allocation_pct,
                    updated_at = datetime('now')
                """,
                asset
            )
            conn.commit()

    # --- Investment Theses (Filtro Humano) ---
    def get_investment_theses(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT it.*, a.name as asset_name, a.current_price, a.asset_type, a.sector
                FROM investment_theses it
                JOIN assets a ON it.ticker = a.ticker
                ORDER BY it.updated_at DESC
            """)
            rows = cursor.fetchall()
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
            cursor = conn.cursor()
            criteria_str = json.dumps(thesis.get("criteria_details", {}))
            cursor.execute(
                """
                INSERT INTO investment_theses (id, ticker, thesis_text, valuation_grade, timing_context, safety_margin, checklist_passed, criteria_details, updated_at)
                VALUES (:id, :ticker, :thesis_text, :valuation_grade, :timing_context, :safety_margin, :checklist_passed, :criteria_details, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    ticker = excluded.ticker,
                    thesis_text = excluded.thesis_text,
                    valuation_grade = excluded.valuation_grade,
                    timing_context = excluded.timing_context,
                    safety_margin = excluded.safety_margin,
                    checklist_passed = excluded.checklist_passed,
                    criteria_details = excluded.criteria_details,
                    updated_at = datetime('now')
                """,
                {
                    "id": thesis.get("id"),
                    "ticker": thesis.get("ticker"),
                    "thesis_text": thesis.get("thesis_text"),
                    "valuation_grade": thesis.get("valuation_grade"),
                    "timing_context": thesis.get("timing_context"),
                    "safety_margin": thesis.get("safety_margin"),
                    "checklist_passed": 1 if thesis.get("checklist_passed") else 0,
                    "criteria_details": criteria_str
                }
            )
            conn.commit()

    # --- Geopolitical Risk ---
    def get_geopolitical_risk(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM geopolitical_risk ORDER BY active_risk_score DESC")
            return [dict(row) for row in cursor.fetchall()]

    # --- Transactions ---
    def get_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transactions ORDER BY date DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # --- BudgetBakers Mappings ---
    def get_budgetbakers_mappings(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM budgetbakers_mappings ORDER BY flow_type, local_category")
            return [dict(row) for row in cursor.fetchall()]

    def update_budgetbakers_mapping(self, mapping_id: str, local_category: str, is_active: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE budgetbakers_mappings SET local_category = ?, is_active = ? WHERE id = ?",
                (local_category, 1 if is_active else 0, mapping_id)
            )
            conn.commit()
