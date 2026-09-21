from datetime import date

from backend.analytics.understand import (
    get_action_items,
    get_budget_risks,
    get_cashflow_forecast,
    get_financial_changes,
    get_recurring_transactions,
)


def tx(id, amount, day, category="General", description="Store", account_id="acc"):
    return {"id": id, "amount": amount, "date": day, "category": category, "description": description, "account_id": account_id, "currency": "USD", "source": "MANUAL"}


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
