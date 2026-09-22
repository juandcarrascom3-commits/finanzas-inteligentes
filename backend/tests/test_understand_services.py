from datetime import date

from backend.analytics.understand import (
    build_analysis_export,
    eligible_budget_spend,
    get_data_confidence,
    get_action_items,
    get_budget_risks,
    get_cashflow_forecast,
    get_financial_changes,
    get_plan_vs_actual,
    get_recurring_transactions,
)
from backend.analytics.monthly_review import get_monthly_review


def tx(id, amount, day, category="General", description="Store", account_id="acc", currency="USD", flow_type=None):
    row = {"id": id, "amount": amount, "date": day, "category": category, "description": description, "account_id": account_id, "currency": currency, "source": "MANUAL"}
    if flow_type:
        row["flow_type"] = flow_type
    return row


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
    assert any(item["merchant"].startswith("payroll") and item["confidence"] in {"MEDIUM", "HIGH"} for item in recurring)
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


def test_transfer_neutrality_for_cashflow_and_savings_rate():
    transactions = [
        tx("salary", 5_000_000, "2026-09-01", "Salario", currency="COP", flow_type="INCOME"),
        tx("food", -1_000_000, "2026-09-02", "Mercado", currency="COP", flow_type="EXPENSE"),
        tx("out", -2_000_000, "2026-09-03", "Transferencia", currency="COP", flow_type="TRANSFER"),
        tx("in", 2_000_000, "2026-09-03", "Transferencia", currency="COP", flow_type="TRANSFER"),
    ]
    result = get_financial_changes(transactions, "current_month", today=date(2026, 9, 20))
    cop = result["by_currency"]["COP"]
    assert cop["income"]["current"] == 5_000_000
    assert cop["expenses"]["current"] == 1_000_000
    assert cop["net_cash_flow"]["current"] == 4_000_000
    assert cop["savings_rate_semantics"]["current"]["value_pct"] == 80


def test_transfer_in_and_out_are_independently_neutral():
    base = [tx("food", -100, "2026-09-02", "Mercado", flow_type="EXPENSE")]
    out = get_financial_changes(base + [tx("out", -900, "2026-09-03", "Transferencia", flow_type="TRANSFER")], today=date(2026, 9, 20))
    inbound = get_financial_changes(base + [tx("in", 900, "2026-09-03", "Transferencia", flow_type="TRANSFER")], today=date(2026, 9, 20))
    assert out["by_currency"]["USD"]["expenses"]["current"] == 100
    assert inbound["by_currency"]["USD"]["expenses"]["current"] == 100
    assert inbound["by_currency"]["USD"]["income"]["current"] == 0


def test_zero_income_savings_rate_is_unevaluable_but_cashflow_remains():
    result = get_financial_changes([tx("expense", -500_000, "2026-09-02", "Mercado", currency="COP", flow_type="EXPENSE")], today=date(2026, 9, 20))
    cop = result["by_currency"]["COP"]
    assert cop["net_cash_flow"]["current"] == -500_000
    assert cop["savings_rate_semantics"]["current"]["value"] is None
    assert cop["savings_rate_semantics"]["current"]["evaluability"] == "UNEVALUABLE"
    assert cop["savings_rate_semantics"]["current"]["reason"] == "NO_INCOME"


def test_savings_rate_delta_pp_relative_and_previous_zero():
    transactions = [
        tx("i1", 1000, "2026-09-01", "Income", flow_type="INCOME"),
        tx("e1", -700, "2026-09-02", "Food", flow_type="EXPENSE"),
        tx("i0", 1000, "2026-08-01", "Income", flow_type="INCOME"),
        tx("e0", -800, "2026-08-02", "Food", flow_type="EXPENSE"),
    ]
    result = get_financial_changes(transactions, today=date(2026, 9, 20))
    sem = result["by_currency"]["USD"]["savings_rate_semantics"]
    assert sem["delta_pp"] == 10
    assert sem["relative_delta_pct"] == 50

    previous_zero = [
        tx("i1", 1000, "2026-09-01", "Income", flow_type="INCOME"),
        tx("e1", -700, "2026-09-02", "Food", flow_type="EXPENSE"),
        tx("i0", 1000, "2026-08-01", "Income", flow_type="INCOME"),
        tx("e0", -1000, "2026-08-02", "Food", flow_type="EXPENSE"),
    ]
    sem_zero = get_financial_changes(previous_zero, today=date(2026, 9, 20))["by_currency"]["USD"]["savings_rate_semantics"]
    assert sem_zero["delta_pp"] == 30
    assert sem_zero["relative_delta_pct"] is None


def test_budget_spend_excludes_transfers_mismatched_currency_and_missing_currency():
    rows = [
        tx("expense", -700_000, "2026-09-02", "Mercado", currency="COP", flow_type="EXPENSE"),
        tx("transfer", -400_000, "2026-09-02", "Mercado", currency="COP", flow_type="TRANSFER"),
        tx("usd", -250, "2026-09-02", "Mercado", currency="USD", flow_type="EXPENSE"),
        {"id": "missing", "amount": -100_000, "date": "2026-09-02", "category": "Mercado", "flow_type": "EXPENSE"},
    ]
    assert eligible_budget_spend(rows, "Mercado", "COP", date(2026, 9, 1), date(2026, 9, 30)) == 700_000


def test_plan_vs_actual_expense_cap_statuses_and_identity():
    rows = [tx("expense", -1_200_000, "2026-09-02", "Mercado", currency="COP", flow_type="EXPENSE")]
    over = get_plan_vs_actual(rows, [{"category": "Mercado", "monthly_limit": 1_000_000, "currency": "COP"}], date(2026, 9, 1), date(2026, 9, 30))[0]
    assert over["variance"] == 200_000
    assert over["variance_pct"] == 20
    assert over["status"] == "OVER_PLAN"

    exact = get_plan_vs_actual([tx("expense", -1_000_000, "2026-09-02", "Mercado", currency="COP", flow_type="EXPENSE")], [{"category": "Mercado", "monthly_limit": 1_000_000, "currency": "COP"}], date(2026, 9, 1), date(2026, 9, 30))[0]
    assert exact["variance"] == 0
    assert exact["variance_pct"] == 0
    assert exact["status"] == "ON_PLAN"


def test_budget_burn_uses_actual_calendar_days_and_independent_statuses():
    rows = [tx("expense", -700_000, "2026-09-02", "Mercado", currency="COP", flow_type="EXPENSE")]
    burn = get_budget_risks(rows, [{"category": "Mercado", "monthly_limit": 1_000_000, "currency": "COP"}], today=date(2026, 9, 15))[0]
    assert burn["days_in_period"] == 30
    assert burn["burn_ratio"] == 0.7
    assert burn["time_ratio"] == 0.5
    assert burn["burn_pressure"] == 1.4
    assert burn["pace_projection"] == 1_400_000
    assert burn["pace_status"] == "OVER_PACE"
    assert burn["budget_status"] == "WITHIN_BUDGET"


def test_budget_burn_february_and_exceeded_budget():
    feb = get_budget_risks([tx("expense", -500_000, "2026-02-02", "Mercado", currency="COP", flow_type="EXPENSE")], [{"category": "Mercado", "monthly_limit": 1_000_000, "currency": "COP"}], today=date(2026, 2, 14))[0]
    assert feb["days_in_period"] == 28
    assert feb["time_ratio"] == 0.5
    assert feb["burn_pressure"] == 1.0
    assert feb["pace_projection"] == 1_000_000
    assert feb["pace_status"] == "ON_PACE"

    leap = get_budget_risks([tx("expense", -500_000, "2028-02-02", "Mercado", currency="COP", flow_type="EXPENSE")], [{"category": "Mercado", "monthly_limit": 1_000_000, "currency": "COP"}], today=date(2028, 2, 14))[0]
    assert leap["days_in_period"] == 29

    exceeded = get_budget_risks([tx("expense", -1_100_000, "2026-09-02", "Mercado", currency="COP", flow_type="EXPENSE")], [{"category": "Mercado", "monthly_limit": 1_000_000, "currency": "COP"}], today=date(2026, 9, 15))[0]
    assert exceeded["budget_status"] == "EXCEEDED"


def test_monthly_review_composes_wave1_domain_outputs():
    review = get_monthly_review(
        transactions=[tx("expense", -700_000, "2026-09-02", "Mercado", currency="COP", flow_type="EXPENSE")],
        accounts=[],
        budgets=[{"category": "Mercado", "monthly_limit": 1_000_000, "currency": "COP"}],
        stored_recurring=[],
        reconciliation={"unmapped_accounts": [], "unmapped_categories": []},
        period="2026-09",
        today=date(2026, 9, 15),
    )
    assert review["what_changed"]["by_currency"]["COP"]["expenses"]["current"] == 700_000
    assert review["plan_vs_actual"][0]["status"] == "UNDER_PLAN"
    assert review["budget_burn"][0]["pace_status"] == "OVER_PACE"
    assert "data_confidence" in review
