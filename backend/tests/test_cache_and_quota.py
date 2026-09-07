"""
Unit Tests for BudgetBakers API Client, Rate Limiting & Local Caching Strategies
Verifies:
- Cache-first response hits
- Strict enforcement of the 25 requests daily limit
- Stale cache serving upon quota exhaustion
"""

import os
import sqlite3
import pytest
from backend.services.budgetbakers_client import BudgetBakersClient, DailyQuotaExceededError, MAX_DAILY_QUOTA

@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_finanzas.db")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE api_daily_quota (
            date_key TEXT PRIMARY KEY,
            request_count INTEGER NOT NULL DEFAULT 0,
            max_quota INTEGER NOT NULL DEFAULT 25,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE api_request_cache (
            cache_key TEXT PRIMARY KEY,
            endpoint TEXT NOT NULL,
            response_payload TEXT NOT NULL,
            cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE budgetbakers_mappings (
            id TEXT PRIMARY KEY,
            bb_category_name TEXT NOT NULL UNIQUE,
            local_category TEXT NOT NULL,
            flow_type TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE transactions (
            id TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            raw_payload TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    return db_file

def test_initial_quota_and_caching(temp_db):
    client = BudgetBakersClient(db_path=temp_db)
    status = client.get_quota_status()
    assert status["max_quota"] == 25
    assert status["used_requests"] == 0
    assert status["remaining_requests"] == 25
    assert status["is_quota_exhausted"] is False

    # 1. First fetch (network / mock ingestion)
    resp1 = client.fetch_records(endpoint="/api/v1/records")
    assert resp1["source"] == "NETWORK_SUCCESS"
    assert len(resp1["data"]) > 0

    # Verify quota decremented
    status_after = client.get_quota_status()
    assert status_after["used_requests"] == 1
    assert status_after["remaining_requests"] == 24

    # 2. Second fetch of same endpoint within TTL (Must hit CACHE without consuming quota!)
    resp2 = client.fetch_records(endpoint="/api/v1/records")
    assert resp2["source"] == "CACHE_HIT"
    # Quota should NOT have increased
    assert client.get_quota_status()["used_requests"] == 1

def test_daily_quota_exhaustion_protection(temp_db):
    client = BudgetBakersClient(db_path=temp_db)
    
    # Simulate first fetch to populate cache
    client.fetch_records(endpoint="/api/v1/records")

    # Artificially set quota usage to 25 (maxed out)
    status = client.get_quota_status()
    today_key = status["date"]
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE api_daily_quota SET request_count = 25 WHERE date_key = ?", (today_key,))
    conn.commit()
    conn.close()

    assert client.get_quota_status()["is_quota_exhausted"] is True

    # 1. Force refresh when quota is exhausted but cache exists: should serve cached fallback with warning!
    fallback_resp = client.fetch_records(endpoint="/api/v1/records", force_refresh=True)
    assert fallback_resp["source"] == "CACHE_FALLBACK_QUOTA_EXHAUSTED"
    assert "Límite diario de 25 peticiones alcanzado" in fallback_resp["warning"]

    # 2. Query an uncached endpoint when quota is exhausted: should raise DailyQuotaExceededError!
    with pytest.raises(DailyQuotaExceededError):
        client.fetch_records(endpoint="/api/v1/uncached_endpoint_xyz")

def test_sync_to_transactions(temp_db):
    client = BudgetBakersClient(db_path=temp_db)
    
    # Add mapping
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO budgetbakers_mappings VALUES ('1', 'Salary / Nómina', 'Ingresos Laborales', 'INCOME', 1, '2026-09-01')")
    conn.commit()
    conn.close()

    raw_data = [
        {"recordId": "rec-1", "amount": 3000.0, "categoryName": "Salary / Nómina", "recordDate": "2026-09-01T10:00:00Z"}
    ]
    res = client.sync_to_transactions(raw_data)
    assert res["status"] == "SUCCESS"
    assert res["imported_records"] == 1

    # Verify transaction in db
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM transactions WHERE id = 'rec-1'").fetchone()
    assert row["amount"] == 3000.0
    assert row["category"] == "Ingresos Laborales"
    conn.close()
