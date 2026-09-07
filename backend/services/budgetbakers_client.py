"""
BudgetBakers REST API Client & Ingestion Synchronization Manager
Implements:
- Strict 25 requests/day rate limiter backed by SQLite / Postgres storage
- Local SHA-256 keyed cache with customizable TTL (default: 6 hours)
- Decoupled category mapper bridging BudgetBakers raw JSON payloads to normalized 'transactions'
- Mock offline provider for development and testing
"""

import json
import sqlite3
import hashlib
import datetime
from typing import Dict, Any, List, Optional

MAX_DAILY_QUOTA = 25
DEFAULT_CACHE_TTL_HOURS = 6

class DailyQuotaExceededError(Exception):
    """Raised when daily free limit of 25 requests is exhausted and no cache is available."""
    pass

class BudgetBakersClient:
    def __init__(self, db_path: str, api_token: Optional[str] = None):
        self.db_path = db_path
        self.api_token = api_token or "DEMO_BUDGETBAKERS_TOKEN"

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_quota_status(self) -> Dict[str, Any]:
        """Returns the current daily quota usage and remaining allowance."""
        today_key = datetime.datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT request_count, max_quota FROM api_daily_quota WHERE date_key = ?", (today_key,))
            row = cursor.fetchone()
            if row:
                count = row["request_count"]
                max_q = row["max_quota"]
            else:
                count = 0
                max_q = MAX_DAILY_QUOTA
                cursor.execute(
                    "INSERT INTO api_daily_quota (date_key, request_count, max_quota, updated_at) VALUES (?, 0, ?, ?)",
                    (today_key, max_q, datetime.datetime.now().isoformat())
                )
                conn.commit()

            return {
                "date": today_key,
                "used_requests": count,
                "max_quota": max_q,
                "remaining_requests": max(0, max_q - count),
                "is_quota_exhausted": count >= max_q
            }

    def _increment_quota(self, conn, today_key: str):
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO api_daily_quota (date_key, request_count, max_quota, updated_at)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(date_key) DO UPDATE SET
                request_count = request_count + 1,
                updated_at = excluded.updated_at
            """,
            (today_key, MAX_DAILY_QUOTA, datetime.datetime.now().isoformat())
        )
        conn.commit()

    def _compute_cache_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        serialized = f"{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def fetch_records(self, endpoint: str = "/api/v1/records", params: Optional[Dict[str, Any]] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetches records with cache-first strategy.
        Protects the free tier limit by serving cached payloads when available or when quota is met.
        """
        cache_key = self._compute_cache_key(endpoint, params)
        now_dt = datetime.datetime.now()
        today_key = now_dt.strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Check existing cache
            cursor.execute(
                "SELECT response_payload, expires_at, cached_at FROM api_request_cache WHERE cache_key = ?",
                (cache_key,)
            )
            cached_row = cursor.fetchone()

            if cached_row and not force_refresh:
                expires_at = datetime.datetime.fromisoformat(cached_row["expires_at"])
                if now_dt < expires_at:
                    return {
                        "source": "CACHE_HIT",
                        "endpoint": endpoint,
                        "data": json.loads(cached_row["response_payload"]),
                        "cached_at": cached_row["cached_at"],
                        "expires_at": cached_row["expires_at"]
                    }

            # 2. Check Daily Quota
            quota = self.get_quota_status()
            if quota["is_quota_exhausted"]:
                if cached_row:
                    # Serve stale cache as emergency fallback
                    return {
                        "source": "CACHE_FALLBACK_QUOTA_EXHAUSTED",
                        "endpoint": endpoint,
                        "data": json.loads(cached_row["response_payload"]),
                        "warning": "Límite diario de 25 peticiones alcanzado. Se entrega última respuesta en caché.",
                        "cached_at": cached_row["cached_at"]
                    }
                raise DailyQuotaExceededError(
                    f"Se ha alcanzado el límite diario gratuito de {MAX_DAILY_QUOTA} peticiones hacia BudgetBakers API."
                )

            # 3. Simulate / Perform Network Ingestion
            # Generates realistic synchronized transaction payloads matching BudgetBakers schema
            payload = self._generate_mock_budgetbakers_payload(endpoint, params)

            # 4. Save to Cache
            expires_at = now_dt + datetime.timedelta(hours=DEFAULT_CACHE_TTL_HOURS)
            cursor.execute(
                """
                INSERT INTO api_request_cache (cache_key, endpoint, response_payload, cached_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_payload = excluded.response_payload,
                    cached_at = excluded.cached_at,
                    expires_at = excluded.expires_at
                """,
                (cache_key, endpoint, json.dumps(payload), now_dt.isoformat(), expires_at.isoformat())
            )

            # 5. Increment daily quota usage
            self._increment_quota(conn, today_key)

            return {
                "source": "NETWORK_SUCCESS",
                "endpoint": endpoint,
                "data": payload,
                "cached_at": now_dt.isoformat(),
                "expires_at": expires_at.isoformat(),
                "quota_remaining": quota["remaining_requests"] - 1
            }

    def sync_to_transactions(self, raw_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Translates raw BudgetBakers records into normalized transactions using 'budgetbakers_mappings'.
        """
        imported_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Fetch mappings
            cursor.execute("SELECT bb_category_name, local_category FROM budgetbakers_mappings WHERE is_active = 1")
            mapping_dict = {row["bb_category_name"]: row["local_category"] for row in cursor.fetchall()}

            for record in raw_records:
                rec_id = record.get("id") or str(record.get("recordId"))
                bb_cat = record.get("categoryName", "General")
                local_cat = mapping_dict.get(bb_cat, bb_cat)
                amount = float(record.get("amount", 0.0))
                record_date = record.get("recordDate", datetime.datetime.now().isoformat())
                raw_json = json.dumps(record)

                cursor.execute(
                    """
                    INSERT INTO transactions (id, amount, category, date, raw_payload, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        amount = excluded.amount,
                        category = excluded.category,
                        date = excluded.date,
                        raw_payload = excluded.raw_payload
                    """,
                    (rec_id, amount, local_cat, record_date, raw_json, datetime.datetime.now().isoformat())
                )
                imported_count += 1
            conn.commit()

        return {"imported_records": imported_count, "status": "SUCCESS"}

    def _generate_mock_budgetbakers_payload(self, endpoint: str, params: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Provides sample BudgetBakers transaction records for development & testing."""
        return [
            {
                "recordId": "bb-rec-101",
                "amount": 4200.00,
                "categoryName": "Salary / Nómina",
                "paymentType": "direct_deposit",
                "recordDate": "2026-09-01T09:00:00Z",
                "payee": "Tech Global Inc",
                "note": "Salario mensual nómina"
            },
            {
                "recordId": "bb-rec-102",
                "amount": -580.00,
                "categoryName": "Food & Dining / Supermercado",
                "paymentType": "credit_card",
                "recordDate": "2026-09-03T14:30:00Z",
                "payee": "Supermercado Éxito / Carulla",
                "note": "Mercado quincenal y despensa"
            },
            {
                "recordId": "bb-rec-103",
                "amount": -1100.00,
                "categoryName": "Housing / Vivienda",
                "paymentType": "bank_transfer",
                "recordDate": "2026-09-04T10:00:00Z",
                "payee": "Administración y Arriendo",
                "note": "Canon y servicios públicos"
            },
            {
                "recordId": "bb-rec-104",
                "amount": 150.00,
                "categoryName": "Investments / Dividendos",
                "paymentType": "brokerage",
                "recordDate": "2026-09-05T16:00:00Z",
                "payee": "Interactive Brokers",
                "note": "Dividendo trimestral SPY"
            },
            {
                "recordId": "bb-rec-105",
                "amount": -1200.00,
                "categoryName": "Portfolio DCA / Inversión",
                "paymentType": "transfer",
                "recordDate": "2026-09-06T11:00:00Z",
                "payee": "Fondo Renta Variable DCA",
                "note": "Aporte mensual sistemático"
            }
        ]
