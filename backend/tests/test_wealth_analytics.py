from database.db_manager import DatabaseManager
from backend.analytics.wealth import (
    compare_benchmark,
    get_allocation,
    get_concentration,
    get_data_quality,
    get_performance,
    get_performance_attribution,
    get_portfolio_history,
    get_rebalancing_plan,
)


def assets_fixture():
    return [
        {"ticker": "AAA", "name": "Alpha", "asset_type": "Equity", "sector": "Tech", "country": "US", "quantity": 10, "avg_price": 90, "current_price": 120, "currency": "USD", "is_watchlist": 0, "target_allocation_pct": 50},
        {"ticker": "BBB", "name": "Beta", "asset_type": "Bond", "sector": "Fixed Income", "country": "US", "quantity": 20, "avg_price": 50, "current_price": 55, "currency": "USD", "is_watchlist": 0, "target_allocation_pct": 30},
        {"ticker": "CCC", "name": "Cash", "asset_type": "Cash", "sector": "Cash", "country": "CO", "quantity": 100, "avg_price": 1, "current_price": 1, "currency": "USD", "is_watchlist": 0, "target_allocation_pct": 20},
    ]


def valuations_fixture():
    return [
        {"ticker": "AAA", "valuation_date": "2026-01-01", "price": 100, "currency": "USD", "source": "MANUAL"},
        {"ticker": "BBB", "valuation_date": "2026-01-01", "price": 50, "currency": "USD", "source": "MANUAL"},
        {"ticker": "CCC", "valuation_date": "2026-01-01", "price": 1, "currency": "USD", "source": "MANUAL"},
        {"ticker": "AAA", "valuation_date": "2026-02-01", "price": 110, "currency": "USD", "source": "MANUAL"},
        {"ticker": "BBB", "valuation_date": "2026-02-01", "price": 48, "currency": "USD", "source": "MANUAL"},
        {"ticker": "CCC", "valuation_date": "2026-02-01", "price": 1, "currency": "USD", "source": "MANUAL"},
        {"ticker": "AAA", "valuation_date": "2026-03-01", "price": 120, "currency": "USD", "source": "MANUAL"},
        {"ticker": "BBB", "valuation_date": "2026-03-01", "price": 55, "currency": "USD", "source": "MANUAL"},
        {"ticker": "CCC", "valuation_date": "2026-03-01", "price": 1, "currency": "USD", "source": "MANUAL"},
        {"ticker": "AAA", "valuation_date": "2026-04-01", "price": 118, "currency": "USD", "source": "MANUAL"},
        {"ticker": "BBB", "valuation_date": "2026-04-01", "price": 57, "currency": "USD", "source": "MANUAL"},
        {"ticker": "CCC", "valuation_date": "2026-04-01", "price": 1, "currency": "USD", "source": "MANUAL"},
    ]


def test_portfolio_history_performance_and_risk():
    tx = [{"date": "2026-02-01", "amount": 100, "raw_payload": {"investment_flow_type": "CONTRIBUTION"}}]
    history = get_portfolio_history(assets_fixture(), valuations_fixture(), tx)
    assert history["status"] == "AVAILABLE"
    assert len(history["series"]) == 4
    assert history["data_quality"]["coverage_pct"] == 100

    performance = get_performance(history, tx)
    assert performance["twr"]["status"] == "AVAILABLE"
    assert performance["mwr"]["status"] == "AVAILABLE"
    assert performance["cumulative_return"]["value_pct"] is not None
    assert performance["realized_pnl"]["status"] == "INSUFFICIENT_DATA"
    assert performance["risk"]["max_drawdown"]["status"] == "AVAILABLE"
    assert performance["risk"]["beta"]["status"] == "INSUFFICIENT_DATA"


def test_insufficient_data_is_explicit():
    history = get_portfolio_history(assets_fixture(), valuations_fixture()[:3], [])
    performance = get_performance(history)
    assert history["status"] == "INSUFFICIENT_DATA"
    assert performance["twr"]["status"] == "INSUFFICIENT_DATA"
    assert performance["twr"]["value_pct"] is None


def test_allocation_concentration_quality_and_rebalancing():
    allocation = get_allocation(assets_fixture())
    assert allocation["dimensions"]["asset_type"][0]["allocation_pct"] > 0

    concentration = get_concentration(allocation, {"single_asset_pct": 40})
    assert concentration["top3_pct"] == 100
    assert concentration["alerts"]

    quality = get_data_quality(assets_fixture(), valuations_fixture())
    assert quality["history_coverage_pct"] == 100

    rebalancing = get_rebalancing_plan(assets_fixture(), contribution_usd=300)
    assert rebalancing["status"] == "AVAILABLE"
    assert any(row["trade_usd"] < 0 for row in rebalancing["traditional"])
    assert sum(row["contribution_usd"] for row in rebalancing["new_contribution"]) == 300


def test_concentration_handles_empty_dimension_rows():
    allocation = {
        "total_value_usd": 0,
        "dimensions": {
            "sector": [],
            "country": [],
            "currency": [],
        },
        "holdings": [],
    }

    concentration = get_concentration(allocation)

    assert concentration["top_asset"] is None
    assert concentration["top3_pct"] == 0
    assert concentration["top5_pct"] == 0
    assert concentration["alerts"] == []


def test_attribution_and_benchmark_foundation():
    attribution = get_performance_attribution(assets_fixture(), valuations_fixture(), start="2026-01-01", end="2026-03-01")
    assert attribution["status"] == "AVAILABLE"
    assert attribution["top_winners"][0]["ticker"] == "AAA"

    history = get_portfolio_history(assets_fixture(), valuations_fixture())
    benchmark = compare_benchmark(history, [
        {"benchmark_key": "SPY", "valuation_date": "2026-01-01", "price": 100},
        {"benchmark_key": "SPY", "valuation_date": "2026-04-01", "price": 110},
    ])
    assert benchmark["status"] == "AVAILABLE"
    assert benchmark["excess_return_pct"] is not None


def test_valuation_and_benchmark_csv_import_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "wealth.db"
    monkeypatch.setenv("FINANCE_DB_PATH", str(db_path))
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    db = DatabaseManager()
    db.add_or_update_asset({"ticker": "AAA", "name": "Alpha", "quantity": 1, "avg_price": 90, "current_price": 100, "currency": "USD"})

    csv = "ticker,date,price,currency\nAAA,2026-01-01,100,USD\nAAA,2026-01-01,100,USD\n"
    first = db.import_asset_valuations_csv(csv)
    second = db.import_asset_valuations_csv(csv)
    assert first["accepted_count"] == 2
    assert second["imported_count"] == 2
    assert len(db.get_asset_valuations("AAA", "2026-01-01", "2026-01-01")) == 1

    bcsv = "date,price,currency\n2026-01-01,100,USD\n2026-01-01,100,USD\n"
    db.import_benchmark_prices_csv(bcsv, "SPY")
    db.import_benchmark_prices_csv(bcsv, "SPY")
    assert len(db.get_benchmark_prices("SPY")) == 1
