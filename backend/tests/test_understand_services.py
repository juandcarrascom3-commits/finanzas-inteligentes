from datetime import date

from backend.analytics.understand import (
    build_analysis_export,
    get_data_confidence,
    get_action_items,
    get_budget_risks,
    get_cashflow_forecast,
    get_financial_changes,
    get_recurring_transactions,
)


def tx(id, amount, day, category="General", description="Store", account_id="acc", currency="USD"):
    return {"id": id, "amount": amount, "date": day, "category": category, "description": description, "account_id": account_id, "currency": currency, "source": "MANUAL"}


def test_what_changed_is_deterministic():
    transactions = [
        tx("1", 3000, "2026-09-01", "Ingresos", "Salary"),
        tx("2", -100, "2026-09-05", "Food", "Market"),
        tx("3", 2500, "2026-08-01", "Ingresos", "Salary"),
        tx("4", -40, "2026-08-05", "Food", "Market"),
    ]
    result = get_financial_changes(transactions, "current_month", today=date(2026, 9, 20))
    assert result["facts"]["income"] == 3000
    assert result["variation"]["expenses"] == 60
    assert result["metrics"]["income"]["current"] == 3000
    assert result["metrics"]["expenses"]["delta"] == 60
    assert result["category_changes"][0]["category"] == "Food"


def test_recurring_budget_forecast_and_actions():
    transactions = [
        tx("s1", 3000, "2026-07-01", "Ingresos", "Payroll"),
        tx("s2", 3000, "2026-08-01", "Ingresos", "Payroll"),
        tx("s3", 3000, "2026-09-01", "Ingresos", "Payroll"),
        tx("n1", -50, "2026-08-03", "Streaming", "Netflix"),
        tx("n2", -50, "2026-09-03", "Streaming", "Netflix"),
        tx("f1", -500, "2026-09-10", "Food", "Market"),
    ]
    recurring = get_recurring_transactions(transactions, today=date(2026, 9, 20))
    assert any(item["merchant"].startswith("payroll") and item["confidence"] == "probable" for item in recurring)
    budgets = get_budget_risks(transactions, [{"category": "Food", "monthly_limit": 400}], today=date(2026, 9, 20))
    assert budgets[0]["status"] == "probably_exceeded"
    forecast = get_cashflow_forecast([{"current_balance": 1000, "is_active": 1}], transactions, recurring, today=date(2026, 9, 20))
    assert "projected_balance" in forecast
    actions = get_action_items({"unmapped_accounts": [{"external_name": "Wallet Cash", "external_id": "a1"}], "unmapped_categories": []}, budgets, recurring, {"status": "CONNECTED"})
    assert any(item["type"] == "account_mapping" for item in actions)
    assert any(item["type"] == "budget_risk" for item in actions)


def test_what_changed_handles_empty_and_missing_previous():
    result = get_financial_changes([], "current_month", today=date(2026, 9, 20))
    assert result["facts"]["income"] == 0
    assert result["metrics"] == {}
    assert result["category_contributors"] == []

    current_only = [tx("1", -100, "2026-09-05", "Food")]
    current = get_financial_changes(current_only, "current_month", today=date(2026, 9, 20))
    assert current["metrics"]["expenses"]["current"] == 100
    assert current["metrics"]["expenses"]["previous"] == 0
    assert current["metrics"]["expenses"]["delta_pct"] is None


def test_what_changed_previous_zero_income_zero_and_expense_sign_semantics():
    transactions = [
        tx("1", 0, "2026-09-01", "Ignored"),
        tx("2", -25, "2026-09-05", "Food"),
        tx("3", 0, "2026-08-05", "Ignored"),
    ]
    result = get_financial_changes(transactions, "current_month", today=date(2026, 9, 20))
    assert result["facts"]["income"] == 0
    assert result["facts"]["savings_rate_pct"] == 0
    assert result["metrics"]["net_cash_flow"]["current"] == -25
    assert result["category_contributors"][0]["delta"] == 25


def test_what_changed_separates_mixed_currencies_and_missing_categories():
    transactions = [
        tx("1", 1000, "2026-09-01", "Ingresos"),
        tx("2", -100, "2026-09-05", "", currency="USD"),
        tx("3", -200000, "2026-09-05", "Mercado", currency="COP"),
        tx("4", -50, "2026-08-05", "", currency="USD"),
        tx("5", -150000, "2026-08-05", "Mercado", currency="COP"),
    ]
    result = get_financial_changes(transactions, "current_month", today=date(2026, 9, 20))
    assert result["mixed_currencies"] is True
    assert result["primary_currency"] is None
    assert result["metrics"] == {}
    assert result["by_currency"]["USD"]["expenses"]["delta"] == 50
    assert result["by_currency"]["COP"]["expenses"]["delta"] == 50000
    assert result["by_currency"]["USD"]["category_contributors"][0]["category"] == "General"


def test_data_confidence_levels():
    good_tx = [tx("1", 1000, "2026-09-01", "Ingresos"), tx("2", -100, "2026-09-02", "Food")]
    high = get_data_confidence(good_tx, [{"category": "Food", "monthly_limit": 500}], [{"merchant": "rent"}], {"unmapped_accounts": [], "unmapped_categories": []}, {"status": "CONNECTED"})
    medium = get_data_confidence(good_tx, [], [], {"unmapped_accounts": [{"external_id": "a1"}], "unmapped_categories": []}, {"status": "CONNECTED"})
    low = get_data_confidence([], [], [], {}, {"status": "CONNECTED"})
    assert high["level"] == "HIGH"
    assert medium["level"] == "MEDIUM"
    assert low["level"] == "LOW"


def test_analysis_export_has_expected_shape_and_no_secret_fields():
    changes = get_financial_changes([tx("1", 1000, "2026-09-01", "Ingresos")], today=date(2026, 9, 20))
    confidence = get_data_confidence([tx("1", 1000, "2026-09-01", "Ingresos")])
    exported = build_analysis_export("current_month", changes, [], [], {"period": "2026-09"}, {"available": True}, confidence)
    serialized = str(exported).lower()
    assert exported["what_changed"]["by_currency"]
    assert "api_key" not in serialized
    assert "token" not in serialized
    assert "secret" not in serialized
