from datetime import datetime, timedelta

from backend.analytics.portfolio_xray import calculate_portfolio_exposure, normalize_fund_composition_snapshot
from backend.services.market_data_service import get_cached_fund_compositions, refresh_fund_compositions
from database.db_manager import DatabaseManager


def asset(ticker, value, asset_type="Equity", sector="Tech"):
    return {
        "ticker": ticker,
        "name": ticker,
        "asset_type": asset_type,
        "sector": sector,
        "country": "US",
        "currency": "USD",
        "quantity": 1,
        "current_price": value,
        "market_value_usd": value,
        "is_watchlist": 0,
    }


def fund(symbol, holdings=None, asset_classes=None, sectors=None, **extra):
    return normalize_fund_composition_snapshot(
        symbol,
        "FAKE",
        {
            "holdings": holdings or [],
            "asset_classes": asset_classes or [],
            "sectors": sectors or [],
            "source_as_of": "2026-01-31",
            **extra,
        },
        fetched_at="2026-02-01T00:00:00",
    )


def item(result, lens, label):
    return next(row for row in result["lenses"][lens]["items"] if row["label"] == label)


def test_direct_security_exposure_and_missing_valuation():
    result = calculate_portfolio_exposure([asset("AAPL", 10), asset("ZERO", 0)], {})
    aapl = item(result, "underlying_security", "AAPL")
    assert aapl["effective_weight"] == 1
    assert aapl["contributors"][0]["source_symbol"] == "AAPL"
    assert result["portfolio_value"] == 10


def test_full_and_partial_fund_no_renormalization_and_residual():
    assets = [asset("VOO", 20, "ETF", "Fund"), asset("CASH", 80, "Cash", "Cash")]
    snapshots = {"VOO": fund("VOO", holdings=[{"symbol": "AAPL", "label": "AAPL", "weight": 0.2}, {"symbol": "MSFT", "label": "MSFT", "weight": 0.2}])}
    result = calculate_portfolio_exposure(assets, snapshots)
    assert item(result, "underlying_security", "AAPL")["effective_weight"] == 0.04
    assert item(result, "underlying_security", "MSFT")["effective_weight"] == 0.04
    residual = item(result, "underlying_security", "UNKNOWN_RESIDUAL")
    assert residual["effective_weight"] == 0.12
    assert result["lenses"]["underlying_security"]["coverage_ratio"] == 0.88


def test_direct_indirect_multifund_aggregation_traceability_and_identity():
    assets = [asset("AAPL", 50), asset("VOO", 25, "ETF", "Fund"), asset("VGT", 25, "ETF", "Fund")]
    snapshots = {
        "VOO": fund("VOO", holdings=[{"symbol": "AAPL", "label": "Apple", "weight": 0.1}]),
        "VGT": fund("VGT", holdings=[{"symbol": "AAPL", "label": "Apple", "weight": 0.2}, {"symbol": "GOOGL", "label": "Alphabet A", "weight": 0.1}]),
    }
    result = calculate_portfolio_exposure(assets, snapshots)
    aapl = item(result, "underlying_security", "AAPL")
    assert aapl["effective_weight"] == 0.575
    assert {row["source_symbol"] for row in aapl["contributors"]} == {"AAPL", "VOO", "VGT"}
    assert result["intersections"][0]["id"] == aapl["id"]
    assert item(result, "underlying_security", "Alphabet A")["id"] != aapl["id"]


def test_wrapper_not_double_counted_and_source_conservation_with_opaque_denominator():
    assets = [asset("VOO", 20, "ETF", "Fund"), asset("OPA", 80, "ETF", "Fund")]
    snapshots = {"VOO": fund("VOO", holdings=[{"symbol": "AAPL", "label": "AAPL", "weight": 0.5}, {"symbol": "MSFT", "label": "MSFT", "weight": 0.5}])}
    result = calculate_portfolio_exposure(assets, snapshots)
    labels = [row["label"] for row in result["lenses"]["underlying_security"]["items"]]
    assert "VOO" not in labels
    assert item(result, "underlying_security", "AAPL")["effective_weight"] == 0.1
    assert result["lenses"]["underlying_security"]["opaque_weight"] == 0.8
    assert result["status"] == "PARTIAL"


def test_lens_specific_coverage_and_unknown_states_are_distinct():
    assets = [asset("ETF1", 50, "ETF", "Fund"), asset("UNK", 50, "Equity", "")]
    snapshots = {"ETF1": fund("ETF1", holdings=[{"symbol": "AAPL", "label": "AAPL", "weight": 0.4}], asset_classes=[{"label": "Equity", "weight": 1.0}], sectors=[])}
    result = calculate_portfolio_exposure(assets, snapshots)
    assert result["lenses"]["asset_class"]["coverage_ratio"] == 1
    assert result["lenses"]["sector"]["unclassified_weight"] == 1
    assert result["lenses"]["underlying_security"]["residual_weight"] == 0.3
    assert result["lenses"]["underlying_security"]["residual_weight"] != result["lenses"]["sector"]["unclassified_weight"]


def test_invalid_provider_weights_are_not_silently_repaired():
    bad = fund("BAD", holdings=[{"symbol": "A", "label": "A", "weight": 0.8}, {"symbol": "B", "label": "B", "weight": 0.5}])
    assert bad["status"] == "PARTIAL"
    result = calculate_portfolio_exposure([asset("BAD", 100, "ETF", "Fund")], {"BAD": bad})
    assert result["opaque_positions"][0]["reason"] == "INVALID_FUND_COMPOSITION"
    assert result["lenses"]["underlying_security"]["opaque_weight"] == 1


def test_provenance_and_deterministic_output():
    snapshots = {"VOO": fund("VOO", holdings=[{"symbol": "AAPL", "label": "AAPL", "weight": 1.0}])}
    first = calculate_portfolio_exposure([asset("VOO", 100, "ETF", "Fund")], snapshots)
    second = calculate_portfolio_exposure([asset("VOO", 100, "ETF", "Fund")], snapshots)
    assert first == second
    assert snapshots["VOO"]["fetched_at"] != snapshots["VOO"]["source_as_of"]
    assert first["provenance"]["fund_compositions"] == "market_data_cache"


class FakeFundProvider:
    name = "FAKE"

    def __init__(self):
        self.calls = []

    def get_etf_holdings(self, symbol):
        self.calls.append(symbol)
        return {"symbol": symbol, "status": "READY", "holdings": [{"symbol": "AAPL", "label": "AAPL", "weight": 0.5}], "asset_classes": [], "sectors": [], "source_as_of": "2026-01-31"}


def test_refresh_uses_provider_and_normal_read_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_DB_PATH", str(tmp_path / "xray.db"))
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    db = DatabaseManager()
    provider = FakeFundProvider()
    refreshed = refresh_fund_compositions(db, ["VOO"], provider=provider)
    assert refreshed["status"] == "CONNECTED"
    assert provider.calls == ["VOO"]
    provider.calls.clear()
    cached = get_cached_fund_compositions(db, ["VOO"], provider_name="FAKE")
    assert cached["VOO"]["holdings"][0]["symbol"] == "AAPL"
    assert provider.calls == []
