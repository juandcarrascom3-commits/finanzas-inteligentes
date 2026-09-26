"""S2C ingestion boundaries (§16 of the implementation packet).

Covers payload bounds, BudgetBakers pagination safety caps, typed import-plan
validation, and preview/confirm hash binding — all against the T0 isolated
temp DB (never the personal database).
"""

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

import backend.app as app_module
from backend.app import _ingest_preview_hash, app, db
from backend.integrations.budgetbakers_adapter import (
    MAX_FETCH_PAGES,
    BudgetBakersAdapter,
    BudgetBakersPaginationError,
)
from database.db_manager import (
    MAX_CANONICAL_ACCOUNTS,
    MAX_CANONICAL_TRANSACTIONS,
    MAX_CSV_CONTENT_CHARS,
    MAX_CSV_ROWS,
    MAX_IMPORT_PLAN_ITEMS,
    MAX_MAPPING_ITEMS,
)

client = TestClient(app)
lenient_client = TestClient(app, raise_server_exceptions=False)


# --- helpers ---------------------------------------------------------------

def _all_event_ids():
    return {event["id"] for event in db.get_action_events(limit=1000)}


def _new_events(before_ids):
    return [event for event in db.get_action_events(limit=1000) if event["id"] not in before_ids]


def _cleanup_sql(*statements):
    conn = db.get_connection()
    try:
        for statement, params in statements:
            conn.execute(statement, params)
        conn.commit()
    finally:
        conn.close()


def _scalar(sql, params=()):
    conn = db.get_connection()
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def _canonical_payload(uid):
    accounts = [{
        "name": f"S2C Cuenta {uid}",
        "account_type": "cash",
        "currency": "USD",
        "opening_balance": 0,
        "current_balance": 0,
        "source": "BUDGETBAKERS",
        "external_id": f"s2c-acc-{uid}",
    }]
    transactions = [{
        "amount": -15,
        "category": "General",
        "date": "2026-09-22",
        "description": "S2C canonical",
        "currency": "USD",
        "source": "BUDGETBAKERS",
        "external_id": f"s2c-tx-{uid}",
        "external_account_id": f"s2c-acc-{uid}",
    }]
    return accounts, transactions


def _cleanup_canonical(uid):
    _cleanup_sql(
        ("DELETE FROM transactions WHERE external_id = ?", (f"s2c-tx-{uid}",)),
        ("DELETE FROM accounts WHERE external_id = ?", (f"s2c-acc-{uid}",)),
    )


# --- T0 / §18: personal DB isolation proof ---------------------------------


def test_t0_temp_db_isolation_proof():
    expected = os.path.abspath(os.environ["FINANCE_DB_PATH"])
    assert os.path.abspath(db.db_path) == expected
    assert "finance-pytest-" in expected  # conftest mkdtemp prefix
    repo_root = os.path.abspath(os.path.join(os.path.dirname(app_module.__file__), ".."))
    personal = os.path.abspath(os.path.join(repo_root, "database", "finanzas.db"))
    assert os.path.abspath(db.db_path) != personal


# --- PAYLOAD LIMITS (§7 / §16.1-3) -----------------------------------------


def test_oversized_csv_content_rejected():
    response = client.post(
        "/api/import/transactions/preview",
        json={"content": "x" * (MAX_CSV_CONTENT_CHARS + 1)},
    )
    assert response.status_code == 422


def test_oversized_canonical_lists_rejected():
    too_many_tx = client.post(
        "/api/budgetbakers/import",
        json={"transactions": [{}] * (MAX_CANONICAL_TRANSACTIONS + 1)},
    )
    too_many_accounts = client.post(
        "/api/budgetbakers/import",
        json={"accounts": [{}] * (MAX_CANONICAL_ACCOUNTS + 1)},
    )
    assert too_many_tx.status_code == 422
    assert too_many_accounts.status_code == 422


def test_normal_csv_payload_accepted():
    content = "date,amount,category,description,currency,external_id\n2026-09-22,-25,Alimentacion,S2C CSV,USD,s2c-normal-1\n"
    response = client.post("/api/import/transactions/preview", json={"content": content})
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 0
    assert isinstance(body["preview_hash"], str) and len(body["preview_hash"]) == 64


def test_oversized_mapping_config_rejected():
    response = client.post(
        "/api/mapping-config/import",
        json={"config": {"etoro_instrument_mappings": [{}] * (MAX_MAPPING_ITEMS + 1)}},
    )
    assert response.status_code == 422


# --- BUDGETBAKERS PAGINATION CAP (§8 / §16.4-6) ----------------------------


def test_normal_pagination_still_works():
    adapter = BudgetBakersAdapter(token="token")

    def fake_get(path, params=None):
        if params.get("offset") == 0:
            return {"records": [{"id": "r-1"}], "nextOffset": 1}, {}
        return {"records": [{"id": "r-2"}]}, {}

    adapter._get = fake_get
    result = adapter.fetch_records()
    assert result["pages"] == 2
    assert [item["id"] for item in result["items"]] == ["r-1", "r-2"]


def test_pagination_safety_cap_fails_clearly():
    adapter = BudgetBakersAdapter(token="token")
    calls = []

    def fake_get(path, params=None):
        calls.append(params["offset"])
        return {"records": [{"id": f"r-{params['offset']}"}], "nextOffset": params["offset"] + 200}, {}

    adapter._get = fake_get
    with pytest.raises(BudgetBakersPaginationError):
        adapter.fetch_records()
    assert len(calls) == MAX_FETCH_PAGES


def test_repeating_pages_cannot_loop_forever():
    adapter = BudgetBakersAdapter(token="token")
    calls = []

    def fake_get(path, params=None):
        calls.append(params["offset"])
        return {"records": [{"id": "same"}], "nextOffset": 1}, {}  # always repeats

    adapter._get = fake_get
    with pytest.raises(BudgetBakersPaginationError):
        adapter.fetch_records()
    assert len(calls) <= 3  # second page cannot advance -> fails fast


def test_pagination_failure_maps_to_controlled_http_error(monkeypatch):
    class BrokenAdapter:
        def is_configured(self):
            return True

        def fetch_accounts(self):
            raise BudgetBakersPaginationError("BudgetBakers superó el límite de 200 páginas.")

    monkeypatch.setattr(app_module, "get_budgetbakers_adapter", lambda: BrokenAdapter())
    response = client.post("/api/budgetbakers/preview")
    assert response.status_code == 502
    assert "límite" in response.json()["detail"]


# --- IMPORT-PLAN TYPING (§9 / §16.7-10) ------------------------------------


def test_valid_typed_plan_works():
    uid = uuid.uuid4().hex[:10]
    before = _all_event_ids()
    try:
        response = client.post(
            "/api/budgetbakers/import-plan",
            json={
                "budgets": [{"category": f"S2C Plan {uid}", "monthly_limit": 120, "currency": "USD", "external_id": f"s2c-plan-b-{uid}"}],
                "standing_orders": [
                    {
                        "merchant": f"S2C Rent {uid}",
                        "typical_amount": -900,
                        "category": "Vivienda",
                        "frequency": "monthly",
                        "external_id": f"s2c-plan-so-{uid}",
                        "next_expected": "2026-10-01",
                    }
                ],
            },
        )
        assert response.status_code == 200
        assert response.json() == {"imported_budgets": 1, "imported_standing_orders": 1}
        new_events = _new_events(before)
        assert [event["event_type"] for event in new_events] == ["IMPORT_PLAN_SUCCESS"]
    finally:
        _cleanup_sql(
            ("DELETE FROM budgets WHERE external_id = ?", (f"s2c-plan-b-{uid}",)),
            ("DELETE FROM recurring_rules WHERE external_id = ?", (f"s2c-plan-so-{uid}",)),
        )


def test_malformed_plan_rejected_before_mutation():
    response = client.post(
        "/api/budgetbakers/import-plan",
        json={"budgets": [{"category": "S2C Malformed", "monthly_limit": "not-a-number"}], "standing_orders": []},
    )
    assert response.status_code == 422
    assert _scalar("SELECT COUNT(*) FROM budgets WHERE category = ?", ("S2C Malformed",)) == 0

    non_list = client.post("/api/budgetbakers/import-plan", json={"budgets": "not-a-list", "standing_orders": []})
    assert non_list.status_code == 422


def test_oversized_plan_rejected():
    response = client.post(
        "/api/budgetbakers/import-plan",
        json={"budgets": [{"category": f"S2C Big {index}"} for index in range(MAX_IMPORT_PLAN_ITEMS + 1)], "standing_orders": []},
    )
    assert response.status_code == 422
    assert _scalar("SELECT COUNT(*) FROM budgets WHERE category LIKE 'S2C Big %'") == 0


def test_s2b_malformed_plan_rejected_at_boundary():
    """Contract correction (S2 micro-closeout): a budget item without category
    identity is malformed client structure, so the typed layer rejects it with
    a controlled 422 BEFORE any mutation — no KeyError, no generic 500, no
    IMPORT_PLAN_FAILED event and zero rows written (S2A B). Genuine
    persistence failures keep the S2B IMPORT_PLAN_FAILED semantics proven in
    test_destructive_audit.py."""
    before = _all_event_ids()
    budgets_before = _scalar("SELECT COUNT(*) FROM budgets")

    missing = client.post("/api/budgetbakers/import-plan", json={"budgets": [{}], "standing_orders": []})
    blank = client.post("/api/budgetbakers/import-plan", json={"budgets": [{"category": "   "}], "standing_orders": []})
    explicit_null = client.post("/api/budgetbakers/import-plan", json={"budgets": [{"category": None}], "standing_orders": []})

    assert missing.status_code == 422
    assert blank.status_code == 422
    assert explicit_null.status_code == 422
    assert _new_events(before) == []
    assert _scalar("SELECT COUNT(*) FROM budgets") == budgets_before


# --- PREVIEW BINDING: BudgetBakers canonical (§10-11 / §16.11-15) ----------


def test_budgetbakers_preview_hash_deterministic():
    accounts, transactions = _canonical_payload("hash-det")
    first = _ingest_preview_hash({"accounts": accounts, "transactions": transactions})
    reordered = _ingest_preview_hash({"transactions": transactions, "accounts": accounts})
    assert first == reordered
    assert len(first) == 64
    mutated = _ingest_preview_hash({"accounts": accounts, "transactions": [{**transactions[0], "amount": -16}]})
    assert mutated != first


def test_unchanged_canonical_payload_imports_with_hash():
    uid = uuid.uuid4().hex[:10]
    accounts, transactions = _canonical_payload(uid)
    preview_hash = _ingest_preview_hash({"accounts": accounts, "transactions": transactions})
    try:
        response = client.post(
            "/api/budgetbakers/import",
            json={"accounts": accounts, "transactions": transactions, "meta": {"preview_hash": preview_hash}},
        )
        assert response.status_code == 200
        assert response.json()["imported_count"] == 1

        # Backward compatibility: requests without a hash keep working (§17).
        no_hash = client.post("/api/budgetbakers/import", json={"accounts": accounts, "transactions": transactions, "meta": {}})
        assert no_hash.status_code == 200
        assert no_hash.json()["duplicate_count"] >= 1
    finally:
        _cleanup_canonical(uid)


def test_stale_canonical_payload_rejected_without_events():
    uid = uuid.uuid4().hex[:10]
    accounts, transactions = _canonical_payload(uid)
    preview_hash = _ingest_preview_hash({"accounts": accounts, "transactions": transactions})
    before = _all_event_ids()
    try:
        response = client.post(
            "/api/budgetbakers/import",
            json={
                "accounts": accounts,
                "transactions": [{**transactions[0], "amount": -999}],
                "meta": {"preview_hash": preview_hash},
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "STALE_PREVIEW"
        assert _new_events(before) == []
        assert _scalar("SELECT COUNT(*) FROM transactions WHERE external_id = ?", (f"s2c-tx-{uid}",)) == 0
    finally:
        _cleanup_canonical(uid)


def test_canonical_idempotent_retry_with_hash_stays_safe():
    uid = uuid.uuid4().hex[:10]
    accounts, transactions = _canonical_payload(uid)
    preview_hash = _ingest_preview_hash({"accounts": accounts, "transactions": transactions})
    body = {"accounts": accounts, "transactions": transactions, "meta": {"preview_hash": preview_hash}}
    try:
        first = client.post("/api/budgetbakers/import", json=body)
        second = client.post("/api/budgetbakers/import", json=body)
        assert first.status_code == 200 and first.json()["imported_count"] == 1
        assert second.status_code == 200 and second.json()["duplicate_count"] >= 1
        assert _scalar("SELECT COUNT(*) FROM transactions WHERE external_id = ?", (f"s2c-tx-{uid}",)) == 1
    finally:
        _cleanup_canonical(uid)


# --- CSV CONFIRM BINDING (§12 / §16.16-18) ---------------------------------


def _transactions_csv(uid):
    return (
        "date,amount,category,description,currency,external_id\n"
        f"2026-09-22,-42,S2C Binding,S2C CSV binding,USD,{uid}\n"
    )


def test_transactions_csv_preview_hash_deterministic():
    content = _transactions_csv("s2c-csv-det")
    first = client.post("/api/import/transactions/preview", json={"content": content})
    second = client.post("/api/import/transactions/preview", json={"content": content})
    different = client.post("/api/import/transactions/preview", json={"content": _transactions_csv("s2c-csv-det-2")})
    assert first.status_code == second.status_code == 200
    assert first.json()["preview_hash"] == second.json()["preview_hash"]
    assert different.json()["preview_hash"] != first.json()["preview_hash"]


def test_transactions_csv_stale_confirm_rejected_and_valid_confirm_works():
    uid = f"s2c-csv-{uuid.uuid4().hex[:10]}"
    content = _transactions_csv(uid)
    preview = client.post("/api/import/transactions/preview", json={"content": content})
    preview_hash = preview.json()["preview_hash"]
    try:
        stale = client.post(
            "/api/import/transactions",
            json={"content": content, "preview_hash": "0" * 64},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "STALE_PREVIEW"
        assert _scalar("SELECT COUNT(*) FROM transactions WHERE external_id = ?", (uid,)) == 0

        valid = client.post("/api/import/transactions", json={"content": content, "preview_hash": preview_hash})
        assert valid.status_code == 200
        assert valid.json()["imported_count"] == 1

        retry = client.post("/api/import/transactions", json={"content": content, "preview_hash": preview_hash})
        assert retry.status_code == 200
        assert retry.json()["duplicate_count"] >= 1
        assert _scalar("SELECT COUNT(*) FROM transactions WHERE external_id = ?", (uid,)) == 1
    finally:
        _cleanup_sql(("DELETE FROM transactions WHERE external_id = ?", (uid,)))


def test_investment_csv_binding_equivalent():
    uid = f"s2c-inv-{uuid.uuid4().hex[:10]}"
    content = (
        "date,ticker,type,quantity,price,amount,fee,currency,external_id\n"
        f"2026-09-22,S2CI,BUY,1,10,10,0.1,USD,{uid}\n"
    )
    first = client.post("/api/investment-ledger/preview", json={"content": content})
    second = client.post("/api/investment-ledger/preview", json={"content": content})
    assert first.status_code == 200
    # id-stripping keeps server-generated uuids out of the fingerprint
    assert first.json()["preview_hash"] == second.json()["preview_hash"]
    preview_hash = first.json()["preview_hash"]
    try:
        stale = client.post("/api/investment-ledger/import", json={"content": content, "preview_hash": "f" * 64})
        assert stale.status_code == 409
        assert _scalar("SELECT COUNT(*) FROM investment_transactions WHERE external_id = ?", (uid,)) == 0

        valid = client.post("/api/investment-ledger/import", json={"content": content, "preview_hash": preview_hash})
        assert valid.status_code == 200
        assert valid.json()["imported_count"] == 1

        retry = client.post("/api/investment-ledger/import", json={"content": content, "preview_hash": preview_hash})
        assert retry.status_code == 200
        assert retry.json()["duplicate_count"] >= 1
    finally:
        _cleanup_sql(("DELETE FROM investment_transactions WHERE external_id = ?", (uid,)))


# --- DIRECT CSV: valuation / benchmark / FX (§13 / §16.19-21) ---------------


def test_valuation_csv_bounds_validation_and_idempotency():
    oversized = client.post(
        "/api/valuations/import",
        json={"content": "x" * (MAX_CSV_CONTENT_CHARS + 1)},
    )
    assert oversized.status_code == 422

    row_cap_content = "date,price,ticker\n" + "".join("2026-09-22,101.5,S2CV\n" for _ in range(MAX_CSV_ROWS + 1))
    row_cap = client.post("/api/valuations/import", json={"content": row_cap_content})
    assert row_cap.status_code == 400
    assert "filas" in row_cap.json()["detail"]

    # asset_valuations.ticker has a FK to assets: unknown tickers must fail as a
    # controlled 4xx (previously an uncontrolled 500).
    unknown_ticker = client.post(
        "/api/valuations/import",
        json={"content": "date,price,ticker\n2026-09-22,101.5,S2CNOASSET\n"},
    )
    assert unknown_ticker.status_code == 400

    assert client.post("/api/assets", json={
        "ticker": "S2CV",
        "name": "S2C Valuation Asset",
        "asset_type": "Renta Variable",
        "sector": "Testing",
        "country": "Global",
        "quantity": 0,
        "avg_price": 0,
        "current_price": 0,
        "currency": "USD",
    }).status_code == 200

    content = "date,price,ticker\n2026-09-22,101.5,S2CV\n2026-09-23,-1,S2CV\n"
    try:
        first = client.post("/api/valuations/import", json={"content": content})
        assert first.status_code == 200
        assert first.json()["accepted_count"] == 1
        assert first.json()["rejected_count"] == 1  # non-positive price

        client.post("/api/valuations/import", json={"content": content})
        listed = client.get("/api/valuations", params={"ticker": "S2CV", "start": "2026-09-22", "end": "2026-09-22"})
        assert listed.status_code == 200
        assert len(listed.json()) == 1  # upsert idempotency (§14)
        rejected_day = client.get("/api/valuations", params={"ticker": "S2CV", "start": "2026-09-23", "end": "2026-09-23"})
        assert rejected_day.json() == []  # invalid price never persisted
    finally:
        _cleanup_sql(
            ("DELETE FROM asset_valuations WHERE ticker = ?", ("S2CV",)),
            ("DELETE FROM assets WHERE ticker = ?", ("S2CV",)),
        )


def test_benchmark_csv_validation_and_idempotency():
    oversized = client.post(
        "/api/benchmarks/import",
        json={"content": "y" * (MAX_CSV_CONTENT_CHARS + 1), "benchmark_key": "S2CB"},
    )
    assert oversized.status_code == 422

    content = "date,price\n2026-09-22,100\n2026-09-23,-5\n"
    try:
        first = client.post("/api/benchmarks/import", json={"content": content, "benchmark_key": "S2CB"})
        assert first.status_code == 200
        assert first.json()["accepted_count"] == 1
        assert first.json()["rejected_count"] == 1

        client.post("/api/benchmarks/import", json={"content": content, "benchmark_key": "S2CB"})
        listed = client.get("/api/benchmarks", params={"benchmark_key": "S2CB"})
        assert listed.status_code == 200
        assert len(listed.json()) == 1
    finally:
        _cleanup_sql(("DELETE FROM benchmark_prices WHERE benchmark_key = ?", ("S2CB",)))


def test_fx_csv_bounds_and_validation():
    oversized = client.post(
        "/api/market-data/fx/import",
        json={"content": "z" * (MAX_CSV_CONTENT_CHARS + 1)},
    )
    assert oversized.status_code == 422

    content = "base,quote,rate,date\nS2CF,USD,1.5,2026-09-22\nS2CF,USD,-1,2026-09-23\n"
    try:
        response = client.post("/api/market-data/fx/import", json={"content": content})
        assert response.status_code == 200
        assert response.json()["accepted_count"] == 1
        assert response.json()["rejected_count"] == 1  # non-positive rate
    finally:
        _cleanup_sql(("DELETE FROM fx_rates WHERE base_currency = ?", ("S2CF",)))


# --- REGRESSIONS (§16.22-25) -----------------------------------------------


def test_etoro_preview_hash_behavior_unchanged():
    assert callable(app_module._etoro_preview_hash)
    base_row = {"external_id": "e2e-1", "price": 100, "quantity": 1, "amount": 100}
    changed_row = {**base_row, "price": 101}
    first = app_module._etoro_preview_hash({"accepted_rows": [base_row]})
    again = app_module._etoro_preview_hash({"accepted_rows": [base_row]})
    changed = app_module._etoro_preview_hash({"accepted_rows": [changed_row]})
    assert first == again
    assert len(first) == 64
    assert changed != first

    # confirm gate still demands explicit confirmation before touching the provider
    gated = client.post("/api/etoro/import", json={"confirm_import": False, "operations": []})
    assert gated.status_code == 400
    assert gated.json()["detail"] == "CONFIRMATION_REQUIRED"


def test_s2a_integrity_helpers_unchanged():
    assert hasattr(db, "_apply_migration_atomically")
    assert hasattr(db, "_verify_restored_database")
    assert hasattr(db, "_copy_sqlite")
    db._verify_restored_database()  # read-only: integrity + migration compatibility
