import urllib.error

import pytest

from database.db_manager import DatabaseManager
from backend.integrations.budgetbakers_adapter import BudgetBakersAdapter, BudgetBakersInitSyncError, BudgetBakersRateLimitError


def test_budgetbakers_adapter_pagination_and_normalization():
    adapter = BudgetBakersAdapter(token="token")
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        if path.endswith("/accounts"):
            return {"accounts": [{"id": "acc-1", "name": "Cash", "balance": {"value": 120, "currencyCode": "USD"}}]}, {"last_data_change_rev": "rev-1"}
        if path.endswith("/categories"):
            return {"categories": [{"id": "cat-1", "name": "Food"}]}, {}
        if params and params.get("offset") == 0:
            return {"records": [{"id": "r-1", "accountId": "acc-1", "amount": {"value": -10, "currencyCode": "USD"}, "category": {"name": "Food"}, "recordDate": "2026-09-20T10:00:00Z"}], "nextOffset": 1}, {}
        return {"records": [{"id": "r-2", "account": {"id": "acc-1"}, "amount": 20, "currencyCode": "USD", "categoryName": "Salary", "date": "2026-09-21"}]}, {}

    adapter._get = fake_get

    accounts = adapter.fetch_accounts()
    records = adapter.fetch_records()
    categories = adapter.fetch_categories()
    normalized_accounts = adapter.normalize_accounts(accounts["items"])
    normalized_records = adapter.normalize_records(records["items"], {"Food": "Alimentacion"})
    normalized_categories = adapter.normalize_categories(categories["items"])
    normalized_budgets = adapter.normalize_budgets([{"id": "b-1", "category": {"name": "Food"}, "amount": {"value": 400, "currencyCode": "USD"}}])
    normalized_orders = adapter.normalize_standing_orders([{"id": "so-1", "name": "Rent", "amount": -900, "frequency": "monthly", "nextDate": "2026-10-01"}])

    assert records["pages"] == 2
    assert accounts["meta"]["last_data_change_rev"] == "rev-1"
    assert normalized_accounts[0]["external_id"] == "acc-1"
    assert normalized_records[0]["category"] == "Alimentacion"
    assert normalized_records[0]["external_account_id"] == "acc-1"
    assert normalized_records[1]["external_id"] == "r-2"
    assert normalized_categories[0]["external_name"] == "Food"
    assert normalized_budgets[0]["external_id"] == "b-1"
    assert normalized_orders[0]["status"] == "confirmed"


def test_canonical_budgetbakers_import_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    db = DatabaseManager(str(tmp_path / "finance.local.db"))
    accounts = [{
        "name": "Wallet Cash",
        "account_type": "cash",
        "currency": "USD",
        "opening_balance": 100,
        "current_balance": 100,
        "source": "BUDGETBAKERS",
        "external_id": "wallet-acc-1",
    }]
    transactions = [{
        "amount": -15,
        "category": "General",
        "date": "2026-09-20",
        "description": "Lunch",
        "currency": "USD",
        "source": "BUDGETBAKERS",
        "external_id": "wallet-tx-1",
        "external_account_id": "wallet-acc-1",
    }]

    preview = db.preview_canonical_import(accounts, transactions, "BUDGETBAKERS")
    assert preview["new_accounts"] == 1
    assert preview["new_transaction_count"] == 1

    first = db.import_canonical_import(accounts, transactions, "BUDGETBAKERS")
    second = db.import_canonical_import(accounts, transactions, "BUDGETBAKERS")
    modified = db.import_canonical_import(accounts, [{**transactions[0], "amount": -20}], "BUDGETBAKERS")

    assert first["imported_count"] == 1
    assert second["imported_count"] == 0
    assert second["duplicate_count"] == 1
    assert modified["updated_count"] == 1
    assert len(db.get_accounts()) == 1
    assert len(db.get_transactions(source="BUDGETBAKERS")) == 1


def test_budgetbakers_adapter_specific_errors(monkeypatch):
    adapter = BudgetBakersAdapter(token="token")

    class Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    def raise_409(*args, **kwargs):
        raise urllib.error.HTTPError("url", 409, "sync", Headers(), None)

    monkeypatch.setattr("urllib.request.urlopen", raise_409)
    with pytest.raises(BudgetBakersInitSyncError):
        adapter._get("/v1/api/accounts")

    def raise_429(*args, **kwargs):
        raise urllib.error.HTTPError("url", 429, "rate", Headers({"Retry-After": "60"}), None)

    monkeypatch.setattr("urllib.request.urlopen", raise_429)
    with pytest.raises(BudgetBakersRateLimitError) as exc:
        adapter._get("/v1/api/accounts")
    assert exc.value.retry_after == "60"
