from backend.analytics.wealth import compare_benchmark, get_portfolio_summary
from backend.integrations.market_data_provider import MarketPrice, MarketQuote
from backend.services.market_data_service import apply_market_prices, convert_currency, get_market_coverage, resolve_market_symbol, sync_market_data
from database.db_manager import DatabaseManager


class FakeProvider:
    name = "FAKE"

    def __init__(self, fail_symbols=None):
        self.fail_symbols = set(fail_symbols or [])
        self.history_calls = []
        self.quote_calls = []

    def get_quote(self, symbol):
        self.quote_calls.append(symbol)
        if symbol in self.fail_symbols:
            raise RuntimeError("provider failed")
        return MarketQuote(symbol=symbol, price=101, currency="USD", as_of="2026-01-03", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={"adjusted": True})

    def get_price_history(self, symbol, start, end):
        self.history_calls.append((symbol, start, end))
        if symbol in self.fail_symbols:
            raise RuntimeError("history failed")
        return [
            MarketPrice(symbol=symbol, price=100, currency="USD", price_date="2026-01-02", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={"adjusted": True}),
            MarketPrice(symbol=symbol, price=101, currency="USD", price_date="2026-01-03", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={"adjusted": True}),
        ]

    def get_fx_history(self, pair, start, end):
        return [
            MarketPrice(symbol=pair, price=4000, currency="COP", price_date="2026-01-02", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={}),
            MarketPrice(symbol=pair, price=4100, currency="COP", price_date="2026-01-03", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={}),
        ]

    def get_benchmark_history(self, symbol, start, end):
        return [
            MarketPrice(symbol=symbol, price=100, currency="USD", price_date="2026-01-01", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={"adjusted": True}),
            MarketPrice(symbol=symbol, price=102, currency="USD", price_date="2026-01-02", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={"adjusted": True}),
            MarketPrice(symbol=symbol, price=101, currency="USD", price_date="2026-01-03", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={"adjusted": True}),
            MarketPrice(symbol=symbol, price=104, currency="USD", price_date="2026-01-04", provider=self.name, retrieved_at="2026-01-03T12:00:00", metadata={"adjusted": True}),
        ]

    def get_etf_holdings(self, symbol):
        return {"symbol": symbol, "status": "UNAVAILABLE", "coverage": "PARTIAL_HOLDINGS", "holdings": []}


def make_db(tmp_path, monkeypatch):
    db_path = tmp_path / "market.db"
    monkeypatch.setenv("FINANCE_DB_PATH", str(db_path))
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    return DatabaseManager()


def test_market_sync_is_idempotent_and_incremental(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.add_or_update_asset({"ticker": "AAA", "name": "AAA", "quantity": 2, "avg_price": 90, "current_price": 0, "currency": "USD"})
    db.save_asset_valuation({"ticker": "AAA", "valuation_date": "2026-01-01", "price": 99, "currency": "USD", "source": "MARKET_DATA", "provider": "FAKE"})
    provider = FakeProvider()

    first = sync_market_data(db, provider=provider, benchmark_symbol="SPY", start="2026-01-01", end="2026-01-03")
    second = sync_market_data(db, provider=provider, benchmark_symbol="SPY", start="2026-01-01", end="2026-01-03")

    assert first["status"] == "CONNECTED"
    assert provider.history_calls[0] == ("AAA", "2026-01-02", "2026-01-03")
    assert second["assets"][0]["history_rows"] == 0
    assert len(db.get_asset_valuations(ticker="AAA", start="2026-01-01", end="2026-01-03")) == 3


def test_symbol_mapping_and_unresolved_symbol(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.save_symbol_mapping({"internal_symbol": "LOCAL", "provider": "FAKE", "provider_symbol": "LOCAL.BA", "instrument_type": "EQUITY", "expected_currency": "USD"})

    mapped = resolve_market_symbol(db, "LOCAL", "FAKE")
    unresolved = resolve_market_symbol(db, "BAD SYMBOL", "FAKE")

    assert mapped["provider_symbol"] == "LOCAL.BA"
    assert mapped["source"] == "MAPPING"
    assert unresolved["status"] == "UNRESOLVED"


def test_sync_uses_provider_symbol_mapping(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.add_or_update_asset({"ticker": "LOCAL", "name": "Local", "quantity": 1, "avg_price": 1, "current_price": 1, "currency": "USD"})
    db.save_symbol_mapping({"internal_symbol": "LOCAL", "provider": "FAKE", "provider_symbol": "LOCAL.BA"})
    provider = FakeProvider()

    result = sync_market_data(db, provider=provider, benchmark_symbol="", start="2026-01-01", end="2026-01-03", mode="QUICK")

    assert result["assets"][0]["provider_symbol"] == "LOCAL.BA"
    assert provider.quote_calls == ["LOCAL.BA"]
    assert provider.history_calls == []


def test_fx_conversion_and_missing_fx_are_explicit(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.save_fx_rate({"base_currency": "USD", "quote_currency": "COP", "rate": 4000, "rate_date": "2026-01-02", "provider": "FAKE"})

    converted = convert_currency(db, 8000, "COP", "USD", "2026-01-03")
    missing = convert_currency(db, 10, "EUR", "USD", "2026-01-03")

    assert converted["status"] == "AVAILABLE"
    assert converted["amount"] == 2
    assert missing["status"] == "INSUFFICIENT_FX_DATA"


def test_stale_price_and_manual_fallback(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.save_market_data_config({"stale_after_days": 1})
    db.add_or_update_asset({"ticker": "AAA", "name": "AAA", "quantity": 1, "avg_price": 5, "current_price": 12, "currency": "USD"})
    db.save_asset_valuation({"ticker": "AAA", "valuation_date": "2020-01-01", "price": 10, "currency": "USD", "source": "MARKET_DATA", "provider": "FAKE"})

    priced = apply_market_prices(db, [{"ticker": "AAA", "quantity": 1, "avg_price": 5, "current_price": 12, "currency": "USD", "is_watchlist": 0}])
    unavailable = apply_market_prices(db, [{"ticker": "BBB", "quantity": 1, "avg_price": 5, "current_price": 0, "currency": "USD", "is_watchlist": 0}])

    assert priced["holdings"][0]["price_status"] == "MANUAL"
    assert priced["holdings"][0]["current_price"] == 12
    assert unavailable["holdings"][0]["price_status"] == "UNAVAILABLE"


def test_price_authority_manual_overrides_market_price(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.add_or_update_asset({"ticker": "AAA", "name": "AAA", "quantity": 1, "avg_price": 5, "current_price": 12, "currency": "USD"})
    db.save_asset_valuation({"ticker": "AAA", "valuation_date": "2999-01-01", "price": 99, "currency": "USD", "source": "MARKET_DATA", "provider": "FAKE"})
    db.save_price_authority({"ticker": "AAA", "authority_mode": "MANUAL", "manual_price": 15, "manual_currency": "USD"})

    priced = apply_market_prices(db, [{"ticker": "AAA", "quantity": 1, "avg_price": 5, "current_price": 12, "currency": "USD", "is_watchlist": 0}])

    assert priced["holdings"][0]["current_price"] == 15
    assert priced["holdings"][0]["price_source"] == "MANUAL"
    assert priced["holdings"][0]["price_authority"] == "MANUAL"


def test_manual_price_does_not_rewrite_history(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.add_or_update_asset({"ticker": "AAA", "name": "AAA", "quantity": 1, "avg_price": 5, "current_price": 12, "currency": "USD"})
    before = db.get_asset_valuations(ticker="AAA")
    db.save_price_authority({"ticker": "AAA", "authority_mode": "MANUAL", "manual_price": 15, "manual_currency": "USD"})

    assert db.get_asset_valuations(ticker="AAA") == before


def test_provider_partial_failure_keeps_sync_running(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.add_or_update_asset({"ticker": "AAA", "name": "AAA", "quantity": 1, "avg_price": 1, "current_price": 1, "currency": "USD"})
    db.add_or_update_asset({"ticker": "BAD", "name": "BAD", "quantity": 1, "avg_price": 1, "current_price": 1, "currency": "USD"})

    result = sync_market_data(db, provider=FakeProvider(fail_symbols={"BAD"}), benchmark_symbol="SPY", start="2026-01-01", end="2026-01-03")

    assert result["status"] == "PARTIAL"
    assert any(row["ticker"] == "AAA" and row["status"] == "UPDATED" for row in result["assets"])
    assert any(row["ticker"] == "BAD" and row["status"] == "FAILED" for row in result["assets"])


def test_unresolved_symbol_does_not_call_provider(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.add_or_update_asset({"ticker": "BAD SYMBOL", "name": "Bad", "quantity": 1, "avg_price": 1, "current_price": 0, "currency": "USD"})
    provider = FakeProvider()

    result = sync_market_data(db, provider=provider, benchmark_symbol="", start="2026-01-01", end="2026-01-03")

    assert result["assets"][0]["status"] == "UNRESOLVED_SYMBOL"
    assert provider.quote_calls == []


def test_benchmark_alignment_calculates_beta():
    history = {
        "series": [
            {"date": "2026-01-01", "portfolio_value_usd": 100},
            {"date": "2026-01-02", "portfolio_value_usd": 104},
            {"date": "2026-01-03", "portfolio_value_usd": 102},
            {"date": "2026-01-04", "portfolio_value_usd": 108},
        ]
    }
    benchmark = [
        {"valuation_date": "2026-01-01", "price": 100},
        {"valuation_date": "2026-01-02", "price": 102},
        {"valuation_date": "2026-01-03", "price": 101},
        {"valuation_date": "2026-01-04", "price": 104},
    ]

    result = compare_benchmark(history, benchmark)

    assert result["status"] == "AVAILABLE"
    assert result["beta"]["status"] == "AVAILABLE"
    assert result["beta"]["value"] is not None
    assert result["coverage"]["aligned_observations"] == 4


def test_benchmark_insufficient_alignment_is_explicit():
    result = compare_benchmark(
        {"series": [{"date": "2026-01-01", "portfolio_value_usd": 100}, {"date": "2026-01-02", "portfolio_value_usd": 101}]},
        [{"valuation_date": "2026-02-01", "price": 100}, {"valuation_date": "2026-02-02", "price": 101}],
    )

    assert result["beta"]["status"] == "INSUFFICIENT_DATA"
    assert result["coverage"]["aligned_observations"] == 0


def test_multi_currency_portfolio_uses_historical_fx(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.save_fx_rate({"base_currency": "USD", "quote_currency": "COP", "rate": 4000, "rate_date": "2026-01-02", "provider": "FAKE"})
    assets = [
        {"ticker": "AAA", "quantity": 1, "avg_price": 80, "current_price": 100, "currency": "USD", "is_watchlist": 0},
        {"ticker": "COL", "quantity": 1, "avg_price": 2000, "current_price": 4000, "currency": "COP", "is_watchlist": 0},
    ]

    summary = get_portfolio_summary(assets, fx_rates=db.get_fx_rates(), fx_max_age_days=365)

    assert summary["total_value_usd"] == 101


def test_manual_fx_csv_and_coverage_summary(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.add_or_update_asset({"ticker": "COL", "name": "Col", "quantity": 1, "avg_price": 2000, "current_price": 4000, "currency": "COP"})
    imported = db.import_fx_rates_csv("date,base,quote,rate\n2026-01-02,USD,COP,4000\n")

    coverage = get_market_coverage(db, [{"ticker": "COL", "quantity": 1, "avg_price": 2000, "current_price": 4000, "currency": "COP", "is_watchlist": 0}])

    assert imported["imported_count"] == 1
    assert coverage["rows"][0]["fx_status"] in {"OK", "MISSING_FX"}
    assert coverage["summary"]["holdings_total"] == 1


def test_quick_sync_skips_asset_history_and_full_sync_fetches_it(tmp_path, monkeypatch):
    db = make_db(tmp_path, monkeypatch)
    db.add_or_update_asset({"ticker": "AAA", "name": "AAA", "quantity": 1, "avg_price": 1, "current_price": 1, "currency": "USD"})
    provider = FakeProvider()

    quick = sync_market_data(db, provider=provider, benchmark_symbol="", start="2026-01-01", end="2026-01-03", mode="QUICK")
    full = sync_market_data(db, provider=provider, benchmark_symbol="", start="2026-01-01", end="2026-01-03", mode="FULL")

    assert quick["assets"][0]["history_rows"] == 0
    assert full["assets"][0]["history_rows"] >= 0
    assert quick["mode"] == "QUICK"
