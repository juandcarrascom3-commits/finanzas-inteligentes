"""S2A data-integrity hardening: properties A-L on the T0 temp database.

Complements (never rewrites) the existing regression contracts:
- test_destructive_audit.py   -> S2B mutation audit semantics
- test_ingestion_boundaries.py -> S2C payload bounds / pagination / hash binding

Covered here: wallet preview read-only-ness, import-plan atomicity,
idempotency and MANUAL preservation, atomic CSV batches, controlled unknown
valuation tickers, honest budget ids, controlled duplicate manual
transactions and manual price sanity. Every test cleans up the rows it
creates so no other suite sees leftovers.
"""

import json
import uuid

from fastapi.testclient import TestClient

import backend.app as app_module
from backend.app import app, db
from backend.integrations.budgetbakers_adapter import BudgetBakersAdapter

client = TestClient(app)
lenient_client = TestClient(app, raise_server_exceptions=False)


# --- helpers ----------------------------------------------------------------


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


def _rows(sql, params=()):
    conn = db.get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _wallet_adapter() -> BudgetBakersAdapter:
    """Real adapter with a scripted transport: deterministic Wallet fixture."""
    adapter = BudgetBakersAdapter(token="token")

    def fake_get(path, params=None):
        if path.endswith("/accounts"):
            return {"accounts": [{"id": "s2a-acc-1", "name": "S2A Wallet", "balance": {"value": 50, "currencyCode": "USD"}}]}, {"last_data_change_rev": "rev-s2a"}
        if path.endswith("/records"):
            return {"records": [{
                "id": "s2a-tx-1",
                "accountId": "s2a-acc-1",
                "amount": {"value": -10, "currencyCode": "USD"},
                "category": {"name": "Food"},
                "recordDate": "2026-09-20T10:00:00Z",
                "note": "S2A preview row",
            }]}, {}
        if path.endswith("/categories"):
            return {"categories": [{"id": "s2a-cat-1", "name": "Food"}]}, {}
        if path.endswith("/budgets"):
            return {"budgets": []}, {}
        if path.endswith("/standing-orders"):
            return {"standingOrders": []}, {}
        raise AssertionError(f"unexpected Wallet path: {path}")

    adapter._get = fake_get
    return adapter


def _db_snapshot():
    return {
        "source_mappings": _rows("SELECT * FROM source_mappings ORDER BY rowid"),
        "sync_state": _rows("SELECT * FROM source_sync_state ORDER BY rowid"),
        "event_ids": {event["id"] for event in db.get_action_events(limit=1000)},
        "accounts": _scalar("SELECT COUNT(*) FROM accounts"),
        "transactions": _scalar("SELECT COUNT(*) FROM transactions"),
        "budgets": _scalar("SELECT COUNT(*) FROM budgets"),
        "recurring_rules": _scalar("SELECT COUNT(*) FROM recurring_rules"),
        "asset_valuations": _scalar("SELECT COUNT(*) FROM asset_valuations"),
        "benchmark_prices": _scalar("SELECT COUNT(*) FROM benchmark_prices"),
        "fx_rates": _scalar("SELECT COUNT(*) FROM fx_rates"),
    }


# --- A. wallet preview = zero persistence -----------------------------------


def test_wallet_preview_performs_zero_persistence(monkeypatch):
    adapter = _wallet_adapter()
    monkeypatch.setattr(app_module, "get_budgetbakers_adapter", lambda: adapter)

    before = _db_snapshot()
    response = client.post("/api/budgetbakers/preview")
    assert response.status_code == 200
    body = response.json()

    # zero writes: no mappings, no sync state, no events, no financial rows
    assert _db_snapshot() == before

    # category discovery now travels in meta instead of being persisted
    assert body["meta"]["discovered_categories"] == [{"external_id": "s2a-cat-1", "external_name": "Food"}]
    assert isinstance(body["preview_hash"], str) and len(body["preview_hash"]) == 64

    # the confirm call persists the discovered mappings (feature preserved)
    imported = client.post("/api/budgetbakers/import", json={
        "accounts": body["accounts"],
        "transactions": body["transactions"],
        "meta": body["meta"],
    })
    assert imported.status_code == 200
    assert _scalar(
        "SELECT COUNT(*) FROM source_mappings WHERE source = 'BUDGETBAKERS' "
        "AND external_type = 'category' AND external_id = 's2a-cat-1'"
    ) == 1

    try:
        # a second preview after a real import still writes nothing
        after_import = _db_snapshot()
        again = client.post("/api/budgetbakers/preview")
        assert again.status_code == 200
        assert _db_snapshot() == after_import
    finally:
        _cleanup_sql(
            ("DELETE FROM source_mappings WHERE source = 'BUDGETBAKERS' AND external_id = ?", ("s2a-cat-1",)),
            ("DELETE FROM transactions WHERE external_id = ?", ("s2a-tx-1",)),
            ("DELETE FROM accounts WHERE external_id = ?", ("s2a-acc-1",)),
        )


# --- C. standing orders idempotent by (source, external_id) -----------------


def test_standing_orders_idempotent_by_source_external_id():
    uid = uuid.uuid4().hex[:10]
    external_id = f"s2a-so-{uid}"
    body = {
        "budgets": [],
        "standing_orders": [{
            "merchant": f"S2A Rent {uid}",
            "typical_amount": -900,
            "category": "Vivienda",
            "frequency": "monthly",
            "external_id": external_id,
            "next_expected": "2026-10-01",
        }],
    }
    try:
        first = client.post("/api/budgetbakers/import-plan", json=body)
        second = client.post("/api/budgetbakers/import-plan", json=body)
        assert first.status_code == 200 and second.status_code == 200
        assert _scalar(
            "SELECT COUNT(*) FROM recurring_rules WHERE source = 'BUDGETBAKERS' AND external_id = ?",
            (external_id,),
        ) == 1
        assert _scalar(
            "SELECT COUNT(DISTINCT id) FROM recurring_rules WHERE source = 'BUDGETBAKERS' AND external_id = ?",
            (external_id,),
        ) == 1
    finally:
        _cleanup_sql(("DELETE FROM recurring_rules WHERE external_id = ?", (external_id,)))


# --- D. MANUAL budgets preserved --------------------------------------------


def test_manual_budgets_are_preserved_from_plan_import():
    uid = uuid.uuid4().hex[:10]
    manual_category = f"S2A Manual Budget {uid}"
    bb_category = f"S2A Wallet Budget {uid}"
    created = client.post(
        "/api/budgets",
        json={"category": manual_category, "monthly_limit": 100, "currency": "USD", "source": "MANUAL"},
    )
    assert created.status_code == 200
    original_id = created.json()["id"]
    try:
        # a Wallet plan never overwrites the user's MANUAL budget
        response = client.post("/api/budgetbakers/import-plan", json={
            "budgets": [{"category": manual_category, "monthly_limit": 999, "currency": "USD", "external_id": f"s2a-plan-{uid}"}],
            "standing_orders": [],
        })
        assert response.status_code == 200
        assert response.json() == {"imported_budgets": 0, "imported_standing_orders": 0}
        row = _rows("SELECT id, monthly_limit, source, external_id FROM budgets WHERE category = ?", (manual_category,))[0]
        assert row["id"] == original_id
        assert row["monthly_limit"] == 100
        assert row["source"] == "MANUAL"
        assert row["external_id"] is None

        # budgets already owned by BudgetBakers keep updating normally
        first = client.post("/api/budgetbakers/import-plan", json={
            "budgets": [{"category": bb_category, "monthly_limit": 100, "currency": "USD", "external_id": f"s2a-plan-b-{uid}"}],
            "standing_orders": [],
        })
        second = client.post("/api/budgetbakers/import-plan", json={
            "budgets": [{"category": bb_category, "monthly_limit": 999, "currency": "USD", "external_id": f"s2a-plan-b-{uid}"}],
            "standing_orders": [],
        })
        assert first.json() == {"imported_budgets": 1, "imported_standing_orders": 0}
        assert second.json() == {"imported_budgets": 1, "imported_standing_orders": 0}
        assert _rows("SELECT monthly_limit FROM budgets WHERE category = ?", (bb_category,))[0]["monthly_limit"] == 999
    finally:
        _cleanup_sql(
            ("DELETE FROM budgets WHERE category = ?", (manual_category,)),
            ("DELETE FROM budgets WHERE category = ?", (bb_category,)),
        )


# --- E. wallet import-plan atomic -------------------------------------------


def test_import_plan_failure_rolls_back_every_row():
    uid = uuid.uuid4().hex[:10]
    valid_category = f"S2A Atomic Budget {uid}"
    before = {event["id"] for event in db.get_action_events(limit=1000)}

    # first budget is valid, second lacks category -> KeyError after row one
    response = lenient_client.post("/api/budgetbakers/import-plan", json={
        "budgets": [{"category": valid_category, "monthly_limit": 10, "currency": "USD"}, {}],
        "standing_orders": [],
    })
    assert response.status_code == 500
    assert _scalar("SELECT COUNT(*) FROM budgets WHERE category = ?", (valid_category,)) == 0

    new_events = [e for e in db.get_action_events(limit=1000) if e["id"] not in before]
    assert [event["event_type"] for event in new_events] == ["IMPORT_PLAN_FAILED"]
    payload = json.loads(new_events[0]["payload"] or "{}")
    assert payload["error_type"] == "KeyError"
    assert payload["imported_budgets"] == 0
    assert payload["imported_standing_orders"] == 0
    assert payload["rolled_back"] is True


# --- F + I. valuations CSV atomic, unknown ticker controlled ----------------


def test_valuation_csv_is_atomic_and_unknown_ticker_is_controlled():
    uid = uuid.uuid4().hex[:8].upper()
    ticker = f"S2A{uid}"
    created = client.post("/api/assets", json={"ticker": ticker, "name": "S2A Valuation Asset"})
    assert created.status_code == 200
    # saving an asset also records its opening valuation: remember the baseline
    baseline = _scalar("SELECT COUNT(*) FROM asset_valuations WHERE ticker = ?", (ticker,))
    try:
        content = (
            "date,price,ticker\n"
            f"2020-01-15,101.5,{ticker}\n"
            "2020-01-16,102.5,S2AUNKNOWN\n"
        )
        response = client.post("/api/valuations/import", json={"content": content})
        assert response.status_code == 400
        assert "S2AUNKNOWN" in response.json()["detail"]
        # atomic: the valid first row must not have survived the failed batch
        assert _scalar("SELECT COUNT(*) FROM asset_valuations WHERE ticker = ?", (ticker,)) == baseline

        # the single-row endpoint is controlled too (400, not 500, no row)
        single = client.post("/api/valuations", json={
            "ticker": "S2AUNKNOWN",
            "valuation_date": "2020-01-15",
            "price": 101.5,
        })
        assert single.status_code == 400
        assert _scalar("SELECT COUNT(*) FROM asset_valuations WHERE ticker = ?", ("S2AUNKNOWN",)) == 0

        # the happy path is unchanged
        ok = client.post("/api/valuations/import", json={
            "content": f"date,price,ticker\n2020-01-15,101.5,{ticker}\n"
        })
        assert ok.status_code == 200
        assert ok.json()["imported_count"] == 1
        assert _scalar("SELECT COUNT(*) FROM asset_valuations WHERE ticker = ?", (ticker,)) == baseline + 1
    finally:
        _cleanup_sql(
            ("DELETE FROM asset_valuations WHERE ticker = ?", (ticker,)),
            ("DELETE FROM assets WHERE ticker = ?", (ticker,)),
        )


# --- G + H. benchmark / FX CSV atomic ---------------------------------------


def test_benchmark_csv_batch_is_atomic(monkeypatch):
    benchmark_key = f"S2AB{uuid.uuid4().hex[:8].upper()}"
    original = db.save_benchmark_price
    calls = {"count": 0}

    def flaky(price, conn=None):
        calls["count"] += 1
        if calls["count"] >= 2:
            raise RuntimeError("simulated benchmark write failure")
        return original(price, conn=conn)

    monkeypatch.setattr(db, "save_benchmark_price", flaky)
    response = client.post("/api/benchmarks/import", json={
        "content": "date,price\n2026-09-22,100\n2026-09-23,101\n",
        "benchmark_key": benchmark_key,
    })
    assert response.status_code == 400
    assert calls["count"] == 2  # second row really did fail mid-batch
    assert _scalar("SELECT COUNT(*) FROM benchmark_prices WHERE benchmark_key = ?", (benchmark_key,)) == 0


def test_fx_csv_batch_is_atomic(monkeypatch):
    base = f"S2A{uuid.uuid4().hex[:6].upper()}"
    original = db.save_fx_rate
    calls = {"count": 0}

    def flaky(rate, conn=None):
        calls["count"] += 1
        if calls["count"] >= 2:
            raise RuntimeError("simulated fx write failure")
        return original(rate, conn=conn)

    monkeypatch.setattr(db, "save_fx_rate", flaky)
    response = client.post("/api/market-data/fx/import", json={
        "content": f"base,quote,rate,date\n{base},USD,1.5,2026-09-22\n{base},USD,1.6,2026-09-23\n",
    })
    assert response.status_code == 400
    assert calls["count"] == 2
    assert _scalar("SELECT COUNT(*) FROM fx_rates WHERE base_currency = ?", (base,)) == 0


# --- J. save_budget returns the actual persisted id --------------------------


def test_save_budget_returns_actual_persisted_id():
    category = f"S2A Budget J {uuid.uuid4().hex[:8]}"
    first = client.post("/api/budgets", json={"category": category, "monthly_limit": 10, "currency": "USD"})
    second = client.post("/api/budgets", json={"category": category, "monthly_limit": 20, "currency": "USD"})
    try:
        assert first.status_code == 200 and second.status_code == 200
        first_id, second_id = first.json()["id"], second.json()["id"]
        assert second_id == first_id
        # the reported id must be the row that actually exists (upsert on category)
        assert _scalar("SELECT id FROM budgets WHERE category = ?", (category,)) == first_id
    finally:
        _cleanup_sql(("DELETE FROM budgets WHERE category = ?", (category,)))


# --- K. duplicate manual transaction controlled ------------------------------


def test_duplicate_manual_transaction_is_controlled():
    uid = uuid.uuid4().hex[:10]
    description = f"S2A manual {uid}"
    payload = {
        "amount": -12.34,
        "category": "General",
        "date": "2026-09-22",
        "description": description,
        "currency": "USD",
    }
    try:
        first = client.post("/api/transactions", json=payload)
        second = client.post("/api/transactions", json=payload)
        assert first.status_code == 200 and second.status_code == 200
        # identical manual save returns the persisted row instead of a twin
        assert second.json()["id"] == first.json()["id"]
        assert _scalar("SELECT COUNT(*) FROM transactions WHERE description = ?", (description,)) == 1

        # a genuinely different manual transaction still inserts
        other = client.post("/api/transactions", json={**payload, "amount": -99.99})
        assert other.status_code == 200
        assert other.json()["id"] != first.json()["id"]
        assert _scalar("SELECT COUNT(*) FROM transactions WHERE description = ?", (description,)) == 2

        # an explicit id keeps the edit/upsert path
        edited = client.post("/api/transactions", json={**payload, "id": first.json()["id"], "amount": -55})
        assert edited.status_code == 200
        assert edited.json()["id"] == first.json()["id"]
        assert _scalar(
            "SELECT COUNT(*) FROM transactions WHERE description = ?", (description,)
        ) == 2
        assert _scalar(
            "SELECT amount FROM transactions WHERE id = ?", (first.json()["id"],)
        ) == -55
    finally:
        _cleanup_sql(("DELETE FROM transactions WHERE description = ?", (description,)))


# --- L. MANUAL manual_price finite and > 0 -----------------------------------


def test_manual_price_authority_requires_finite_positive_price():
    ticker = f"S2A{uuid.uuid4().hex[:6].upper()}"

    def save(body, raw=None):
        if raw is not None:
            return client.post(
                "/api/market-data/price-authority",
                content=raw,
                headers={"Content-Type": "application/json"},
            )
        return client.post("/api/market-data/price-authority", json=body)

    try:
        # rejected before anything reaches the database
        assert save({"ticker": ticker, "authority_mode": "MANUAL", "manual_price": -5}).status_code == 422
        assert save({"ticker": ticker, "authority_mode": "MANUAL", "manual_price": 0}).status_code == 422
        assert save({"ticker": ticker, "authority_mode": "MANUAL"}).status_code == 422
        for bad in (float("nan"), float("inf"), float("-inf")):
            raw = json.dumps({"ticker": ticker, "authority_mode": "MANUAL", "manual_price": bad})
            assert save(None, raw=raw).status_code == 422
        assert _scalar("SELECT COUNT(*) FROM price_authority WHERE ticker = ?", (ticker,)) == 0

        # valid shapes still work
        assert save({"ticker": ticker, "authority_mode": "AUTO"}).status_code == 200
        ok = save({"ticker": ticker, "authority_mode": "MANUAL", "manual_price": 12.5})
        assert ok.status_code == 200
        stored = _scalar("SELECT manual_price FROM price_authority WHERE ticker = ?", (ticker,))
        assert stored == 12.5
    finally:
        _cleanup_sql(("DELETE FROM price_authority WHERE ticker = ?", (ticker,)))
