from database.db_manager import DatabaseManager
from backend.analytics.investment_ledger import (
    calculate_mwr,
    derive_positions,
    get_investment_cashflows,
    get_investment_income,
    get_ledger_reconciliation,
    get_realized_pnl,
    get_unrealized_pnl_from_lots,
    match_lots_fifo,
)


def op(id, day, typ, ticker=None, quantity=0, price=0, amount=0, fee=0, currency="USD"):
    return {
        "id": id,
        "occurred_at": day,
        "operation_type": typ,
        "ticker": ticker,
        "quantity": quantity,
        "price": price,
        "amount": amount,
        "fee": fee,
        "currency": currency,
        "source": "MANUAL",
        "external_id": id,
        "account_id": None,
        "notes": "",
        "metadata": {},
    }


def test_fifo_partial_sell_realized_pnl():
    operations = [
        op("b1", "2026-01-01", "BUY", "AAA", 10, 100, fee=0),
        op("b2", "2026-02-01", "BUY", "AAA", 10, 120, fee=0),
        op("s1", "2026-03-01", "SELL", "AAA", 15, 150, fee=0),
    ]
    matched = match_lots_fifo(operations)
    assert matched["issues"] == []
    assert matched["realized_trades"][0]["cost_basis"] == 1600
    assert matched["realized_trades"][0]["realized_pnl"] == 650
    positions = derive_positions(operations)["positions"]
    assert positions[0]["quantity"] == 5
    assert positions[0]["avg_cost"] == 120


def test_full_sell_multiple_lots_and_fee():
    operations = [
        op("b1", "2026-01-01", "BUY", "AAA", 5, 100, fee=5),
        op("b2", "2026-01-02", "BUY", "AAA", 5, 110, fee=5),
        op("s1", "2026-02-01", "SELL", "AAA", 10, 120, fee=10),
    ]
    pnl = get_realized_pnl(operations)
    assert pnl["total_realized_pnl"] == 130
    assert derive_positions(operations)["positions"] == []


def test_contribution_then_buy_is_not_double_counted_as_performance_cashflow():
    operations = [
        op("c1", "2026-01-01", "CONTRIBUTION", amount=1000),
        op("b1", "2026-01-02", "BUY", "AAA", 10, 100, amount=1000),
        op("w1", "2026-03-01", "WITHDRAWAL", amount=100),
        op("t1", "2026-03-02", "TRANSFER_IN", amount=500),
    ]
    cashflows = get_investment_cashflows(operations)
    assert cashflows["total_external_cashflow"] == 900
    assert len(cashflows["cashflows"]) == 2
    mwr = calculate_mwr(operations, final_value=1200, final_date="2026-04-01")
    assert mwr["status"] == "AVAILABLE"


def test_dividends_interest_and_fees_are_separate():
    operations = [
        op("d1", "2026-01-10", "DIVIDEND", "AAA", amount=25),
        op("i1", "2026-01-11", "INTEREST", amount=10),
        op("f1", "2026-01-12", "FEE", amount=3),
        op("b1", "2026-01-13", "BUY", "AAA", 1, 100, fee=2),
    ]
    income = get_investment_income(operations)
    assert income["dividends_total"] == 25
    assert income["interest_total"] == 10
    assert income["fees_total"] == 5


def test_reconciliation_match_mismatch_and_insufficient_history():
    assets = [
        {"ticker": "AAA", "quantity": 10, "avg_price": 100, "current_price": 120, "currency": "USD", "is_watchlist": 0},
        {"ticker": "BBB", "quantity": 2, "avg_price": 50, "current_price": 50, "currency": "USD", "is_watchlist": 0},
    ]
    operations = [op("b1", "2026-01-01", "BUY", "AAA", 10, 100)]
    rec = get_ledger_reconciliation(assets, operations)
    assert next(row for row in rec["rows"] if row["ticker"] == "AAA")["status"] == "MATCH"
    assert next(row for row in rec["rows"] if row["ticker"] == "BBB")["status"] == "INSUFFICIENT_HISTORY"


def test_insufficient_lots_and_fx_data_are_reported():
    operations = [op("s1", "2026-02-01", "SELL", "AAA", 2, 150)]
    assert match_lots_fifo(operations)["issues"][0]["type"] == "INSUFFICIENT_LOTS"

    assets = [{"ticker": "AAA", "quantity": 1, "avg_price": 100, "current_price": 120, "currency": "COP", "is_watchlist": 0}]
    lots = [op("b1", "2026-01-01", "BUY", "AAA", 1, 100, currency="USD")]
    unrealized = get_unrealized_pnl_from_lots(assets, lots)
    assert unrealized["issues"][0]["type"] == "INSUFFICIENT_FX_DATA"


def test_csv_import_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.db"
    monkeypatch.setenv("FINANCE_DB_PATH", str(db_path))
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    db = DatabaseManager()

    csv = "date,ticker,type,quantity,price,amount,fee,currency,external_id\n2026-01-01,AAA,BUY,10,100,1000,1,USD,trade-1\n"
    preview = db.preview_investment_transactions_csv(csv)
    first = db.import_investment_transactions_csv(csv)
    second = db.import_investment_transactions_csv(csv)
    assert preview["accepted_count"] == 1
    assert first["imported_count"] == 1
    assert second["imported_count"] == 0
    assert second["duplicate_count"] == 1
    assert len(db.get_investment_transactions()) == 1
