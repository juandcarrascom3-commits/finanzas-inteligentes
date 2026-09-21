import json
import urllib.error

import pytest

from backend.integrations.etoro_adapter import EtoroAdapter, EtoroNetworkError, EtoroRateLimitError
import backend.app as app_module
from backend.app import _etoro_dry_run, _etoro_mapping_suggestions
from database.db_manager import DatabaseManager


class FakeBody:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def close(self):
        return None


def test_etoro_headers_and_connection(monkeypatch):
    adapter = EtoroAdapter(api_key=" api\n", user_key="'user' ", base_url=" https://public-api.etoro.com/api/v1/ ", environment=" demo ")
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
    assert captured["url"] == "https://public-api.etoro.com/api/v1/trading/info/demo/portfolio"
    assert captured["headers"]["X-api-key"] == "api"
    assert captured["headers"]["X-user-key"] == "user"
    assert captured["headers"]["X-request-id"]
    assert captured["headers"]["User-agent"] == "FinancePersonal/1.0"
    assert "Authorization" not in captured["headers"]


def test_etoro_portfolio_and_pnl_are_distinct_read_only_resources():
    adapter = EtoroAdapter(api_key="api", user_key="user", environment="demo")
    calls = []

    def fake_get(path, params=None):
        calls.append(path)
        return {"positions": []}, {}

    adapter._get = fake_get
    adapter.fetch_portfolio()
    adapter.fetch_pnl()

    assert calls == ["/trading/info/demo/portfolio", "/trading/info/demo/pnl"]


def test_etoro_routes_are_explicit_for_demo_and_real():
    demo = EtoroAdapter(api_key="api", user_key="user", environment="demo")
    real = EtoroAdapter(api_key="api", user_key="user", environment="real")

    assert demo._portfolio_path() == "/trading/info/demo/portfolio"
    assert demo._pnl_path() == "/trading/info/demo/pnl"
    assert real._portfolio_path() == "/trading/info/portfolio"
    assert real._pnl_path() == "/trading/info/real/pnl"
    assert "/real/portfolio" not in real._portfolio_path()
    assert demo._history_path() == "/trading/info/trade/demo/history"
    assert real._history_path() == "/trading/info/trade/history"


def test_etoro_request_id_is_unique_per_request(monkeypatch):
    adapter = EtoroAdapter(api_key="api", user_key="user")
    request_ids = []

    class Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        request_ids.append(dict(request.header_items())["X-request-id"])
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    adapter.fetch_portfolio()
    adapter.fetch_pnl()

    assert len(request_ids) == 2
    assert request_ids[0] != request_ids[1]


def history_row(**overrides):
    row = {
        "positionId": "p1",
        "parentPositionId": None,
        "orderId": 0,
        "instrumentId": "i1",
        "socialTradeId": None,
        "openTimestamp": "2026-01-01T10:00:00Z",
        "closeTimestamp": "2026-01-10T10:00:00Z",
        "openRate": 10,
        "closeRate": 20,
        "units": 1,
        "investment": 10,
        "initialInvestment": 10,
        "fees": -1.2,
        "netProfit": 8.8,
        "isBuy": True,
        "leverage": 1,
    }
    row.update(overrides)
    return row


def test_etoro_history_fetch_starts_at_page_one_and_does_not_stop_on_partial_page():
    adapter = EtoroAdapter(api_key="api", user_key="user", environment="demo")
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        page = params["page"]
        if page == 1:
            return {"history": [history_row(positionId="p1")]}, {}
        if page == 2:
            return {"history": [history_row(positionId="p2", orderId=0)]}, {}
        return {"history": []}, {}

    adapter._get = fake_get
    result = adapter.fetch_history(min_date="2026-01-01", page_size=50, max_pages=5)

    assert [params["page"] for _, params in calls] == [1, 2, 3]
    assert 0 not in [params["page"] for _, params in calls]
    assert all(path == "/trading/info/trade/demo/history" for path, _ in calls)
    assert calls[0][1]["minDate"] == "2026-01-01"
    assert result["history_status"] == "READY"
    assert result["rows_downloaded"] == 2
    assert result["stop_reason"] == "EMPTY_PAGE"


def test_etoro_history_fetch_stops_on_no_new_identities_and_keeps_identity_conflicts():
    adapter = EtoroAdapter(api_key="api", user_key="user")

    def fake_get_conflict(path, params=None):
        if params["page"] == 1:
            return {"history": [history_row(positionId="same", closeRate=20), history_row(positionId="same", closeRate=21)]}, {}
        return {"history": []}, {}

    adapter._get = fake_get_conflict
    conflict = adapter.fetch_history(page_size=100, max_pages=2)
    assert conflict["rows_downloaded"] == 2
    assert conflict["identity_conflicts"] == 1
    assert any(row.get("_etoro_identity_conflict") for row in conflict["items"])

    def fake_get_duplicate(path, params=None):
        if params["page"] in {1, 2}:
            return {"history": [history_row(positionId="dup", orderId=0)]}, {}
        return {"history": []}, {}

    adapter._get = fake_get_duplicate
    duplicate = adapter.fetch_history(page_size=100, max_pages=5)
    assert duplicate["rows_downloaded"] == 1
    assert duplicate["duplicate_rows"] == 1
    assert duplicate["stop_reason"] == "NO_NEW_IDENTITIES"


def test_etoro_history_fetch_respects_max_page_guardrail():
    adapter = EtoroAdapter(api_key="api", user_key="user")

    def fake_get(path, params=None):
        return {"history": [history_row(positionId=f"p{params['page']}")]}, {}

    adapter._get = fake_get
    result = adapter.fetch_history(page_size=1, max_pages=3)

    assert result["pages"] == 3
    assert result["rows_downloaded"] == 3
    assert result["stop_reason"] == "MAX_PAGES"


def test_etoro_history_fetch_always_sends_required_min_date():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    calls = []

    def fake_get(path, params=None):
        calls.append(params)
        return {"history": []}, {}

    adapter._get = fake_get
    adapter.fetch_history(max_pages=1)

    assert calls[0]["minDate"] == "2000-01-01"


def test_etoro_instrument_metadata_uses_instrument_id():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        return {"instruments": [{"instrumentID": 123, "symbol": "AAPL"}]}, {}

    adapter._get = fake_get
    adapter.fetch_instrument_metadata("123")

    assert calls == [("/market-data/search", {"instrumentId": "123", "pageSize": 1})]


def test_etoro_metadata_batch_fetches_each_instrument_once():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    calls = []

    def fake_get(path, params=None):
        calls.append(params["instrumentId"])
        return {"instruments": [{"instrumentID": params["instrumentId"], "symbol": f"T{params['instrumentId']}"}]}, {}

    adapter._get = fake_get
    metadata = adapter.fetch_metadata_for_instruments(["2", "1", "2"])

    assert calls == ["1", "2"]
    assert metadata["1"]["symbol"] == "T1"


def test_etoro_history_normalization_preserves_signed_fees_and_reconciles_netprofit():
    adapter = EtoroAdapter(api_key="api", user_key="user", environment="demo")
    normalized = adapter.normalize_history_rows(
        [history_row()],
        {"i1": {"symbol": "AAPL"}},
        {"i1": "AAPL"},
    )

    assert normalized["summary"]["compatible"] == 1
    assert normalized["summary"]["operations"] == 2
    buy, sell = normalized["operations"]
    assert buy["external_id"] == "ETORO:DEMO:history:p1:OPEN"
    assert sell["external_id"] == "ETORO:DEMO:history:p1:CLOSE"
    assert buy["external_id"] != sell["external_id"]
    assert buy["fee"] == 0
    assert sell["fee"] == 1.2
    assert buy["metadata"]["fees_raw"] == -1.2
    assert sell["metadata"]["fees_raw"] == -1.2
    assert normalized["net_profit_reconciliation"][0]["status"] == "MATCH"

    missing_reference = adapter.normalize_history_rows([history_row(positionId="p2", netProfit=None)], {"i1": {"symbol": "AAPL"}}, {"i1": "AAPL"})
    assert missing_reference["net_profit_reconciliation"][0]["status"] == "NOT_COMPARABLE"

    mismatch_reference = adapter.normalize_history_rows([history_row(positionId="p3", netProfit=99)], {"i1": {"symbol": "AAPL"}}, {"i1": "AAPL"})
    assert mismatch_reference["net_profit_reconciliation"][0]["status"] == "MISMATCH"


def test_etoro_history_classification_rejects_leverage_short_copy_and_partial_data():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    normalized = adapter.normalize_history_rows(
        [
            history_row(positionId="lev", leverage=2),
            history_row(positionId="short", isBuy=False),
            history_row(positionId="copy", socialTradeId="social-1"),
            history_row(positionId="partial", closeTimestamp=None),
        ],
        {"i1": {"symbol": "AAPL"}},
        {"i1": "AAPL"},
    )

    assert normalized["summary"]["compatible"] == 0
    assert normalized["summary"]["unsupported"] == 2
    assert normalized["summary"]["partial"] == 2
    assert {row["classification"] for row in normalized["unsupported_rows"]} == {"UNSUPPORTED"}
    assert {row["classification"] for row in normalized["partial_rows"]} == {"PARTIAL_DATA"}


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


def test_etoro_snapshot_merges_portfolio_and_pnl_by_position_id_with_fx_and_signed_fees():
    adapter = EtoroAdapter(api_key="api", user_key="user", environment="demo")
    portfolio = {
        "clientPortfolio": {
            "positions": [
                {
                    "positionID": "p1",
                    "CID": "cid-demo",
                    "orderID": "o1",
                    "instrumentID": "i1",
                    "units": 2,
                    "openRate": 10,
                    "openConversionRate": 1.2,
                    "amount": 24,
                    "totalFees": -0.5,
                    "totalExternalFees": -0.1,
                    "totalExternalTaxes": -0.2,
                    "leverage": 1,
                    "isBuy": True,
                },
                {
                    "positionID": "p2",
                    "CID": "cid-demo",
                    "instrumentID": "i1",
                    "units": 3,
                    "openRate": 11,
                    "openConversionRate": 1.2,
                    "totalFees": -0.3,
                },
            ]
        }
    }
    pnl = {
        "clientPortfolio": {
            "unrealizedPnL": 15.0,
            "positions": [
                {
                    "positionID": "p1",
                    "closeRate": {"value": 12},
                    "closeConversionRate": {"value": 1.3},
                    "unrealizedPnL": {"pnL": 7.2},
                    "exposureInAccountCurrency": 31.2,
                    "marginInAccountCurrency": 24.0,
                    "timestamp": "2026-09-21T00:00:00Z",
                },
                {
                    "positionID": "p2",
                    "closeRate": 12,
                    "closeConversionRate": 1.3,
                    "unrealizedPnL": {"pnL": 7.8},
                    "exposureInAccountCurrency": 46.8,
                    "marginInAccountCurrency": 39.0,
                },
            ],
        }
    }

    snapshot = adapter.build_snapshot(portfolio, pnl, {"i1": {"symbol": "AAA", "name": "Alpha", "assetClass": "EQUITY", "exchange": "NASDAQ", "isin": "US000"}})

    assert snapshot["snapshot_status"] == "READY"
    assert snapshot["history_status"] == "NOT_AVAILABLE"
    assert len(snapshot["direct_positions"]) == 2
    assert {row["positionID"] for row in snapshot["direct_positions"]} == {"p1", "p2"}
    first = snapshot["direct_positions"][0]
    assert first["instrumentID"] == "i1"
    assert first["ticker"] == "AAA"
    assert first["open_value_account"] == 24
    assert first["current_value_account"] == 31.2
    assert first["unrealized_pnl"] == 7.2
    assert first["totalFees"] == -0.5
    assert first["fees_cost_abs"] == 0.5
    assert first["exposure_reconciliation"]["status"] == "MATCH"
    assert snapshot["account_pnl_reconciliation"]["status"] == "MATCH"


def test_etoro_snapshot_marks_missing_pnl_as_partial_data():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    snapshot = adapter.build_snapshot(
        {"positions": [{"positionID": "p1", "instrumentID": "i1", "units": 1, "openRate": 10, "openConversionRate": 1}]},
        {"positions": []},
        {},
    )

    assert snapshot["snapshot_status"] == "PARTIAL_DATA"
    assert snapshot["positions"][0]["status"] == "PARTIAL_DATA"
    assert snapshot["warnings"][0]["type"] == "MISSING_PNL"


def test_etoro_snapshot_keeps_direct_and_mirror_positions_separate():
    adapter = EtoroAdapter(api_key="api", user_key="user")
    portfolio = {
        "clientPortfolio": {
            "unrealizedPnL": 9,
            "positions": [{"positionID": "direct-1", "instrumentID": "i1", "units": 1, "openRate": 10, "openConversionRate": 1}],
            "mirrors": [{
                "mirrorID": "m1",
                "parentCID": "parent",
                "parentUsername": "copy",
                "initialInvestment": 100,
                "availableAmount": 5,
                "closedPositionsNetProfit": 2,
                "depositSummary": {"amount": 100},
                "withdrawalSummary": {"amount": 0},
                "positions": [{"positionID": "mirror-1", "instrumentID": "i2", "units": 1, "openRate": 20, "openConversionRate": 1}],
            }],
        }
    }
    pnl = {
        "clientPortfolio": {
            "unrealizedPnL": 9,
            "positions": [{"positionID": "direct-1", "closeRate": 14, "closeConversionRate": 1, "unrealizedPnL": {"pnL": 4}, "exposureInAccountCurrency": 14, "marginInAccountCurrency": 10}],
            "mirrors": [{"mirrorID": "m1", "positions": [{"positionID": "mirror-1", "closeRate": 25, "closeConversionRate": 1, "unrealizedPnL": {"pnL": 5}, "exposureInAccountCurrency": 25, "marginInAccountCurrency": 20}]}],
        }
    }

    snapshot = adapter.build_snapshot(portfolio, pnl, {})

    assert snapshot["direct_summary"]["positions"] == 1
    assert snapshot["mirror_summary"]["mirrors"] == 1
    assert snapshot["mirror_summary"]["internal_positions"] == 1
    assert snapshot["direct_positions"][0]["provenance"] == "ETORO_DIRECT"
    assert snapshot["mirrors"][0]["positions"][0]["provenance"] == "ETORO_MIRROR"
    assert snapshot["account_pnl_reconciliation"]["direct_pnl"] == 4
    assert snapshot["account_pnl_reconciliation"]["mirror_pnl"] == 5
    assert snapshot["account_pnl_reconciliation"]["status"] == "MATCH"


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


def test_etoro_404_route_not_found_is_network_not_auth(monkeypatch):
    adapter = EtoroAdapter(api_key="api", user_key="user")

    class Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    def raise_404(*args, **kwargs):
        body = json.dumps({"title": "RouteNotFound", "status": 404}).encode("utf-8")
        raise urllib.error.HTTPError("url", 404, "not found", Headers({"Content-Type": "application/json"}), fp=FakeBody(body))

    monkeypatch.setattr("urllib.request.urlopen", raise_404)

    with pytest.raises(EtoroNetworkError) as exc:
        adapter._get("/bad-route")
    assert exc.value.diagnostic["status_code"] == 404


def test_etoro_401_remains_auth_error(monkeypatch):
    adapter = EtoroAdapter(api_key="api", user_key="user")

    class Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    def raise_401(*args, **kwargs):
        body = json.dumps({"title": "Unauthorized", "status": 401}).encode("utf-8")
        raise urllib.error.HTTPError("url", 401, "unauthorized", Headers({"Content-Type": "application/json"}), fp=FakeBody(body))

    monkeypatch.setattr("urllib.request.urlopen", raise_401)

    with pytest.raises(Exception) as exc:
        adapter._get("/trading/info/demo/portfolio")
    assert exc.value.__class__.__name__ == "EtoroAuthError"


def test_etoro_cloudflare_1010_is_not_reported_as_auth_error(monkeypatch):
    adapter = EtoroAdapter(api_key="api", user_key="user")

    class Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    def raise_403_cloudflare(*args, **kwargs):
        body = json.dumps({
            "title": "Error 1010: Access denied",
            "status": 403,
            "error_name": "browser_signature_banned",
            "cloudflare_error": True,
        }).encode("utf-8")
        raise urllib.error.HTTPError("url", 403, "forbidden", Headers({"Content-Type": "application/json"}), fp=FakeBody(body))

    monkeypatch.setattr("urllib.request.urlopen", raise_403_cloudflare)

    with pytest.raises(EtoroNetworkError) as exc:
        adapter._get("/trading/info/demo/portfolio")
    assert exc.value.diagnostic["status_code"] == 403
    assert "browser_signature_banned" in exc.value.diagnostic["response_body"]


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


def test_etoro_dry_run_does_not_mutate_database_and_reports_opening_suggestion(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    test_db = DatabaseManager(str(tmp_path / "finance.local.db"))
    monkeypatch.setattr(app_module, "db", test_db)
    operation = {
        "occurred_at": "2026-01-01",
        "ticker": "AAPL",
        "operation_type": "BUY",
        "quantity": 1,
        "price": 100,
        "amount": 100,
        "fee": 0,
        "currency": "USD",
        "source": "ETORO",
        "external_id": "ETORO:DEMO:history:p1:OPEN",
        "metadata": {"netProfit": 0},
    }
    positions = [{
        "ticker": "AAPL",
        "external_instrument_id": "i1",
        "external_name": "Apple",
        "quantity": 2,
        "status": "READY",
    }]

    result = _etoro_dry_run([operation], positions, [{"positionId": "p1", "status": "NOT_COMPARABLE"}])

    assert result["status"] == "DRY_RUN_ONLY"
    assert result["db_unchanged"] is True
    assert result["db_before"] == result["db_after"]
    assert result["db_before"]["investment_transactions"] == 0
    assert result["db_before"]["sha256"]
    assert test_db.get_investment_transactions() == []
    assert result["new_operations"] == 1
    assert result["coverage_summary"]["OPENING_POSITION_REQUIRED"] == 1
    assert result["opening_position_suggestions"][0]["opened_at"] is None
    assert result["opening_position_suggestions"][0]["requires_user_cost_basis"] is True
    assert result["net_profit_reconciliation"][0]["status"] == "NOT_COMPARABLE"


def etoro_import_operations():
    return [
        {
            "occurred_at": "2026-01-01T10:00:00",
            "ticker": "AAPL",
            "operation_type": "BUY",
            "quantity": 1,
            "price": 100,
            "amount": 100,
            "fee": 0,
            "currency": "USD",
            "source": "ETORO",
            "external_id": "ETORO:DEMO:history:p-safe:OPEN",
            "metadata": {"provenance": "ETORO_HISTORY_DIRECT", "fees_raw": -1.5, "netProfit": 18.5},
        },
        {
            "occurred_at": "2026-02-01T10:00:00",
            "ticker": "AAPL",
            "operation_type": "SELL",
            "quantity": 1,
            "price": 120,
            "amount": 120,
            "fee": 1.5,
            "currency": "USD",
            "source": "ETORO",
            "external_id": "ETORO:DEMO:history:p-safe:CLOSE",
            "metadata": {"provenance": "ETORO_HISTORY_DIRECT", "fees_raw": -1.5, "netProfit": 18.5},
        },
    ]


def build_safe_etoro_preview(operations):
    operation_preview = app_module.db.preview_investment_operations(operations, "ETORO")
    positions = []
    dry_run = app_module._etoro_dry_run(operation_preview["accepted_rows"], positions, [{"positionId": "p-safe", "status": "MATCH"}])
    preview = {
        **operation_preview,
        "source": "ETORO",
        "environment": "demo",
        "trade_history_status": "READY",
        "history_status": "READY",
        "positions": positions,
        "operations": operation_preview["accepted_rows"],
        "operation_classifications": operation_preview["classifications"],
        "rejected_rows": [],
        "rejected_count": 0,
        "positions_found": 0,
        "operations_found": len(operations),
        "history_summary": {"rows_downloaded": len(operations) // 2, "compatible": len(operations) // 2, "partial": 0, "unsupported": 0, "identity_conflicts": 0},
        "ready_to_import_count": operation_preview["new_count"],
        "update_candidate_count": operation_preview.get("update_count", 0),
        "local_conflict_count": operation_preview.get("local_conflict_count", 0),
        "unsupported_count": 0,
        "unmapped_count": 0,
        "unsupported_instruments": [],
        "unmapped_instruments": [],
        "unknown_currencies": [],
        "missing_fx": [],
        "period": {"from": "2026-01-01", "to": "2026-02-01", "status": "READY"},
        "reconciliation": {"rows": [], "issues": [], "summary": {"positions": 0, "issues": 0}},
        "mapping_suggestions": [],
        "dry_run": dry_run,
        "net_profit_reconciliation": [{"positionId": "p-safe", "status": "MATCH", "finance_realized_pnl": 18.5, "etoro_netProfit": 18.5, "difference": 0}],
        "data_quality": {"missing_mapping": 0, "unsupported_instrument": 0, "partial_history": 0, "identity_conflict": 0, "missing_fx": 0, "duplicate": operation_preview["duplicate_count"], "local_conflict": operation_preview.get("local_conflict_count", 0), "position_mismatch": 0},
        "optional_warnings": [],
        "meta": {"environment": "demo"},
    }
    preview_hash = app_module._etoro_preview_hash(preview)
    gates = app_module._etoro_import_gates(preview)
    preview["preview_hash"] = preview_hash
    preview["preview_valid"] = True
    preview["import_gates"] = gates
    preview["import_enabled"] = gates["status"] == "PASS"
    preview["meta"] = {**preview["meta"], "preview_hash": preview_hash}
    return preview


def test_etoro_safe_import_is_atomic_idempotent_and_backed_up(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    test_db = DatabaseManager(str(tmp_path / "finance.local.db"))
    monkeypatch.setattr(app_module, "db", test_db)
    operations = etoro_import_operations()
    monkeypatch.setattr(app_module, "_build_etoro_preview", lambda: build_safe_etoro_preview(operations))

    preview = build_safe_etoro_preview(operations)
    assert preview["import_enabled"] is True
    first = app_module.import_etoro_preview(app_module.EtoroImportInput(preview_hash=preview["preview_hash"], confirm_import=True))

    assert first["imported_count"] == 2
    assert first["post_import"]["status"] == "MATCH"
    assert first["backup"]["created"] is True
    assert first["backup"]["validation"]["valid"] is True
    assert len(test_db.get_investment_transactions()) == 2
    assert test_db.get_opening_positions() == []
    assert first["ready_to_import_count"] == 0

    second_preview = build_safe_etoro_preview(operations)
    assert second_preview["new_count"] == 0
    second = app_module.import_etoro_preview(app_module.EtoroImportInput(preview_hash=second_preview["preview_hash"], confirm_import=True))
    assert second["imported_count"] == 0
    assert len(test_db.get_investment_transactions()) == 2


def test_etoro_safe_import_rejects_stale_preview_when_mapping_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    test_db = DatabaseManager(str(tmp_path / "finance.local.db"))
    monkeypatch.setattr(app_module, "db", test_db)
    operations = etoro_import_operations()
    monkeypatch.setattr(app_module, "_build_etoro_preview", lambda: build_safe_etoro_preview(operations))

    preview = build_safe_etoro_preview(operations)
    test_db.save_source_mapping({"source": "ETORO", "external_type": "instrument", "external_id": "i1", "external_name": "Apple", "local_id": "AAPL", "local_type": "ticker"})

    with pytest.raises(Exception) as exc:
        app_module.import_etoro_preview(app_module.EtoroImportInput(preview_hash=preview["preview_hash"], confirm_import=True))
    assert getattr(exc.value, "status_code", None) == 409
    assert exc.value.detail["code"] == "STALE_PREVIEW"
    assert test_db.get_investment_transactions() == []


def test_etoro_safe_import_blocks_conflicts_and_real_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    test_db = DatabaseManager(str(tmp_path / "finance.local.db"))
    monkeypatch.setattr(app_module, "db", test_db)
    preview = build_safe_etoro_preview(etoro_import_operations())
    preview["local_conflict_count"] = 1
    assert app_module._etoro_import_gates(preview)["status"] == "BLOCKED"

    real_preview = build_safe_etoro_preview(etoro_import_operations())
    real_preview["environment"] = "real"
    assert "REAL_IMPORT_REQUIRES_EXPLICIT_USER_CONFIRMATION" in app_module._etoro_import_gates(real_preview)["failures"]


def test_etoro_batch_import_rolls_back_on_mid_batch_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    test_db = DatabaseManager(str(tmp_path / "finance.local.db"))
    operations = etoro_import_operations()
    original_get_connection = test_db.get_connection

    class FailingConnection:
        def __init__(self):
            self.conn = original_get_connection()
            self.inserts = 0

        def __enter__(self):
            self.conn.__enter__()
            return self

        def __exit__(self, *args):
            return self.conn.__exit__(*args)

        def execute(self, sql, params=()):
            if "INSERT INTO investment_transactions" in sql:
                self.inserts += 1
                if self.inserts == 2:
                    raise RuntimeError("simulated mid-batch failure")
            return self.conn.execute(sql, params)

        def commit(self):
            return self.conn.commit()

        def rollback(self):
            return self.conn.rollback()

    monkeypatch.setattr(test_db, "get_connection", lambda: FailingConnection())

    with pytest.raises(Exception):
        test_db.import_investment_operations(operations, "ETORO")

    monkeypatch.setattr(test_db, "get_connection", original_get_connection)
    assert test_db.get_investment_transactions() == []
