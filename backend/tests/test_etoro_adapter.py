import json
import urllib.error

import pytest

from backend.integrations.etoro_adapter import EtoroAdapter, EtoroRateLimitError
from backend.app import _etoro_mapping_suggestions
from database.db_manager import DatabaseManager


def test_etoro_headers_and_connection(monkeypatch):
    adapter = EtoroAdapter(api_key="api", user_key="user", environment="demo")
    captured = {}

    class Response:
        headers = {"x-rate-limit-limit": "60"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"positions": [{"id": "p1", "instrumentId": "AAPL"}]}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        captured["url"] = request.full_url
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = adapter.test_connection()

    assert result["status"] == "CONNECTED"
    assert "/trading/info/demo/portfolio" in captured["url"]
    assert captured["headers"]["X-api-key"] == "api"
    assert captured["headers"]["X-user-key"] == "user"
    assert captured["headers"]["X-request-id"]


def test_etoro_pagination_and_normalization():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        if not params or "cursor" not in params:
            return {"orders": [{"id": "o1", "instrumentId": "AAPL", "type": "BUY", "quantity": 2, "price": 100, "currency": "USD", "date": "2026-09-01"}], "nextCursor": "next"}, {}
        return {"orders": [{"id": "o2", "instrumentId": "AAPL", "type": "SELL", "quantity": 1, "price": 120, "currency": "USD", "date": "2026-09-10"}]}, {}

    adapter._get = fake_get

    history = adapter.fetch_history()
    normalized = adapter.normalize_operations({"orders": history["items"]}, {"AAPL": "AAPL"})

    assert history["pages"] == 2
    assert calls[1][1]["cursor"] == "next"
    assert [row["operation_type"] for row in normalized["operations"]] == ["BUY", "SELL"]
    assert normalized["operations"][0]["amount"] == 200
    assert normalized["operations"][1]["external_id"] == "o2"


def test_etoro_multi_currency_income_fee_and_mapping():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    raw = {
        "orders": [
            {"id": "d1", "instrument": {"id": "VUSA.L", "name": "VUSA"}, "type": "DIVIDEND", "cashAmount": 9.5, "currency": "GBP", "date": "2026-09-11"},
            {"id": "f1", "instrumentId": "AAPL", "type": "FEE", "fee": 1.25, "currency": "USD", "date": "2026-09-12"},
        ]
    }

    normalized = adapter.normalize_operations(raw, {"VUSA.L": "VUSA", "AAPL": "AAPL"})

    assert normalized["rejected_rows"] == []
    assert normalized["operations"][0]["operation_type"] == "DIVIDEND"
    assert normalized["operations"][0]["ticker"] == "VUSA"
    assert normalized["operations"][0]["currency"] == "GBP"
    assert normalized["operations"][1]["operation_type"] == "FEE"
    assert normalized["operations"][1]["amount"] == 1.25


def test_etoro_rejects_unmapped_and_unsupported_instruments():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    raw = {
        "orders": [
            {"id": "missing", "instrumentId": "TSLA", "type": "BUY", "quantity": 1, "price": 200, "date": "2026-09-01"},
            {"id": "cfd", "instrumentId": "AAPL", "type": "BUY", "quantity": 1, "price": 100, "leverage": 5, "date": "2026-09-01"},
        ]
    }

    normalized = adapter.normalize_operations(raw, {"AAPL": "AAPL"})
    positions = adapter.normalize_positions({"positions": raw["orders"]}, {"AAPL": "AAPL"})

    assert len(normalized["operations"]) == 0
    assert len(normalized["rejected_rows"]) == 2
    assert positions["unmapped"][0]["external_instrument_id"] == "TSLA"
    assert positions["unsupported"][0]["external_instrument_id"] == "AAPL"


def test_etoro_investment_import_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    db = DatabaseManager(str(tmp_path / "finance.local.db"))
    db.save_source_mapping({
        "source": "ETORO",
        "external_type": "instrument",
        "external_id": "AAPL",
        "external_name": "Apple",
        "local_id": "AAPL",
        "local_type": "ticker",
    })
    operation = {
        "occurred_at": "2026-09-01",
        "ticker": "AAPL",
        "operation_type": "BUY",
        "quantity": 2,
        "price": 100,
        "amount": 200,
        "fee": 0,
        "currency": "USD",
        "source": "ETORO",
        "external_id": "etoro-o1",
    }

    preview = db.preview_investment_operations([operation], "ETORO")
    first = db.import_investment_operations([operation], "ETORO")
    second = db.import_investment_operations([{**operation, "price": 101, "amount": 202}], "ETORO")

    assert preview["new_count"] == 1
    assert first["imported_count"] == 1
    assert second["imported_count"] == 0
    assert second["updated_count"] == 1
    assert len(db.get_investment_transactions()) == 1
    assert db.get_investment_transactions()[0]["amount"] == 202


def test_etoro_position_reconciliation():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    etoro_positions = adapter.normalize_positions(
        {"positions": [{"id": "p1", "instrumentId": "AAPL", "quantity": 2, "averagePrice": 100}]},
        {"AAPL": "AAPL"},
    )["positions"]

    result = adapter.reconcile_positions(etoro_positions, [{"ticker": "AAPL", "quantity": 1.5}])

    assert result["summary"]["issues"] == 1
    assert result["rows"][0]["reconciliation_status"] == "QUANTITY_MISMATCH"
    assert result["rows"][0]["ledger_quantity_diff"] == 0.5


def test_etoro_rate_limit_error(monkeypatch):
    adapter = EtoroAdapter(api_key="api", user_key="user")

    class Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    def raise_429(*args, **kwargs):
        raise urllib.error.HTTPError("url", 429, "rate", Headers({"Retry-After": "60"}), None)

    monkeypatch.setattr("urllib.request.urlopen", raise_429)

    with pytest.raises(EtoroRateLimitError) as exc:
        adapter._get("/trading/info/demo/portfolio")
    assert exc.value.retry_after == "60"


def test_etoro_duplicate_update_and_local_conflict_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    db = DatabaseManager(str(tmp_path / "finance.local.db"))
    original = {
        "occurred_at": "2026-09-01",
        "ticker": "AAPL",
        "operation_type": "BUY",
        "quantity": 1,
        "price": 100,
        "amount": 100,
        "currency": "USD",
        "source": "ETORO",
        "external_id": "same",
        "notes": "eToro buy read-only import",
        "metadata": {"source": "ETORO"},
    }
    db.import_investment_operations([original], "ETORO")

    unchanged = db.preview_investment_operations([original], "ETORO")
    updated = db.preview_investment_operations([{**original, "price": 101, "amount": 101}], "ETORO")

    assert unchanged["classifications"][0]["classification"] == "unchanged"
    assert updated["classifications"][0]["classification"] == "update_candidate"

    conflict_db = DatabaseManager(str(tmp_path / "conflict.db"))
    conflict_db.save_investment_transaction({**original, "notes": "manual edit", "metadata": {}})
    conflict = conflict_db.preview_investment_operations([{**original, "amount": 102}], "ETORO")
    assert conflict["classifications"][0]["classification"] == "local_conflict"
    with pytest.raises(ValueError):
        conflict_db.import_investment_operations([{**original, "amount": 102}], "ETORO")
    assert conflict_db.get_investment_transactions()[0]["amount"] == 100


def test_mapping_config_export_validate_import(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    source_db = DatabaseManager(str(tmp_path / "source.db"))
    source_db.save_source_mapping({"source": "ETORO", "external_type": "instrument", "external_id": "AAPL", "external_name": "Apple", "local_id": "AAPL", "local_type": "ticker"})
    source_db.save_symbol_mapping({"internal_symbol": "AAPL", "provider": "YFINANCE", "provider_symbol": "AAPL", "instrument_type": "EQUITY", "expected_currency": "USD"})
    source_db.save_price_authority({"ticker": "AAPL", "authority_mode": "AUTO"})

    config = source_db.export_mapping_config()
    assert source_db.validate_mapping_config(config)["valid"] is True

    target_db = DatabaseManager(str(tmp_path / "target.db"))
    result = target_db.import_mapping_config(config)

    assert result["imported"]["etoro_instrument_mappings"] == 1
    assert target_db.get_source_mapping_lookup("ETORO", "instrument")["AAPL"] == "AAPL"
    assert target_db.get_symbol_mappings(provider="YFINANCE", internal_symbol="AAPL")
    assert target_db.get_price_authority("AAPL")


def test_bulk_mapping_suggestions_are_not_confirmed():
    suggestions = _etoro_mapping_suggestions([
        {"external_instrument_id": "AAPL", "external_name": "AAPL", "symbol": "AAPL", "instrument_type": "EQUITY", "currency": "USD", "status": "MISSING_MAPPING"}
    ])

    assert suggestions[0]["suggested"]
    assert suggestions[0]["suggested"][0]["ticker"] == "AAPL"
    assert suggestions[0]["confirmed"] is False


def test_etoro_opening_position_required_coverage():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    positions = adapter.normalize_positions({"positions": [{"id": "p1", "instrumentId": "AAPL", "quantity": 5}]}, {"AAPL": "AAPL"})["positions"]
    reconciliation = adapter.reconcile_positions(positions, [])

    assert reconciliation["rows"][0]["reconciliation_status"] == "INSUFFICIENT_HISTORY"
