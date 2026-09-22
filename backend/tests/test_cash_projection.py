from datetime import date, timedelta

from backend.analytics.cash_projection import (
    aggregate_financial_events,
    calculate_runway,
    calculate_safe_to_spend,
    calculate_variable_spend_baseline,
    project_cash,
)
from backend.analytics.understand import get_recurring_transactions


def event(id, day, amount, currency="COP", direction="OUTFLOW", certainty="EXPECTED", confidence="HIGH"):
    return {"id": id, "date": day, "amount": amount, "currency": currency, "direction": direction, "certainty": certainty, "confidence": confidence, "label": id}


def tx(id, amount, day, description="Store", currency="COP", flow_type="EXPENSE"):
    return {"id": id, "amount": amount, "date": day, "description": description, "category": "General", "account_id": "acc", "currency": currency, "flow_type": flow_type}


def test_projection_known_events_and_projected_balance():
    events = [
        event("ci", "2026-09-25", 2_000_000, direction="INFLOW", certainty="COMMITTED"),
        event("ei", "2026-09-26", 1_000_000, direction="INFLOW"),
        event("co", "2026-09-27", 1_000_000, certainty="COMMITTED"),
        event("eo", "2026-09-28", 500_000),
    ]
    result = project_cash("COP", date(2026, 9, 21), 30, 5_000_000, events, [], covered_week_starts={date(2026, 9, 1), date(2026, 9, 8), date(2026, 8, 25), date(2026, 8, 18)})
    # No historical spend means covered zero weeks are valid.
    assert result["balance_after_known_events"] == 6_500_000
    assert result["estimated_variable_outflows"] == 0
    assert result["projected_balance"] == 6_500_000

    variable_rows = [tx(str(i), -1_000_000, day) for i, day in enumerate(["2026-08-18", "2026-08-25", "2026-09-01", "2026-09-08"])]
    variable = project_cash("COP", date(2026, 9, 21), 7, 5_000_000, events, variable_rows, covered_week_starts={date(2026, 8, 17), date(2026, 8, 24), date(2026, 8, 31), date(2026, 9, 7)})
    assert variable["estimated_variable_outflows"] == 999_999.98


def test_safe_to_spend_excludes_expected_inflows_and_preserves_negative():
    projection = {
        "currency": "COP",
        "starting_liquid_balance": 5_000_000,
        "committed_inflows": 2_000_000,
        "expected_inflows": 1_000_000,
        "committed_outflows": 1_000_000,
        "expected_outflows": 500_000,
        "estimated_variable_outflows": 1_000_000,
        "status": "READY",
    }
    result = calculate_safe_to_spend(projection, 2_000_000)
    assert result["safe_to_spend"] == 2_500_000
    assert result["expected_inflow_upside"] == 1_000_000
    assert calculate_safe_to_spend(projection, 6_000_000)["safe_to_spend"] == -1_500_000
    assert calculate_safe_to_spend(projection, None)["reason"] == "RESERVE_FLOOR_REQUIRED"


def test_currency_isolation_and_window_excludes_same_day():
    totals = aggregate_financial_events(
        [event("same", "2026-09-21", 100), event("usd", "2026-09-22", 999, currency="USD"), event("cop", "2026-09-22", 200)],
        "COP",
        date(2026, 9, 21),
        date(2026, 10, 21),
    )
    assert totals["expected_outflows"] == 200


def test_missing_starting_balance_and_partial_history():
    no_balance = project_cash("COP", date(2026, 9, 21), 30, None, [], [])
    assert no_balance["status"] == "UNEVALUABLE"
    assert no_balance["reason"] == "STARTING_BALANCE_REQUIRED"

    partial = project_cash("COP", date(2026, 9, 21), 30, 5_000_000, [], [tx("v1", -100, "2026-09-08")])
    assert partial["status"] == "PARTIAL"
    assert partial["reason"] == "NOT_ENOUGH_HISTORY"
    assert partial["projected_balance"] is None
    assert partial["balance_after_known_events"] == 5_000_000


def test_robust_weekly_baseline_partial_week_coverage_and_unknown_coverage():
    rows = []
    for idx, (monday, amount) in enumerate([
        ("2026-08-17", 500_000),
        ("2026-08-24", 550_000),
        ("2026-08-31", 600_000),
        ("2026-09-07", 580_000),
        ("2026-09-14", 2_000_000),
    ]):
        rows.append(tx(str(idx), -amount, monday))
    rows.append(tx("partial", -100_000, "2026-09-22"))
    baseline = calculate_variable_spend_baseline(rows, "COP", date(2026, 9, 24), covered_week_starts={date.fromisoformat(d) for d in ["2026-08-17", "2026-08-24", "2026-08-31", "2026-09-07", "2026-09-14"]})
    assert baseline["median_weekly_spend"] == 580_000

    covered_zero = calculate_variable_spend_baseline([tx("a", -500_000, "2026-08-17"), tx("b", -550_000, "2026-08-31"), tx("c", -600_000, "2026-09-07")], "COP", date(2026, 9, 15), covered_week_starts={date(2026, 8, 17), date(2026, 8, 24), date(2026, 8, 31), date(2026, 9, 7)})
    assert 0.0 in covered_zero["weekly_totals"]

    unknown = calculate_variable_spend_baseline(rows[:4], "COP", date(2026, 9, 15))
    assert "LIMITED_TRANSACTION_COVERAGE" in unknown["confidence_reasons"]
    assert unknown["confidence"] in {"LOW", "MEDIUM"}


def test_double_count_protection_and_low_pattern_stays_variable():
    rows = []
    for idx, day in enumerate(["2026-08-18", "2026-08-25", "2026-09-01", "2026-09-08"]):
        rows.append(tx(f"n{idx}", -50_000, day, description="Netflix"))
        rows.append(tx(f"v{idx}", -100_000, day, description="Groceries"))
    netflix_id = next(p["id"] for p in get_recurring_transactions(rows) if p["merchant"].startswith("netflix"))
    baseline = calculate_variable_spend_baseline(rows, "COP", date(2026, 9, 15), covered_week_starts={date(2026, 8, 17), date(2026, 8, 24), date(2026, 8, 31), date(2026, 9, 7)}, recurring_event_source_ids={netflix_id})
    assert baseline["median_weekly_spend"] == 100_000

    low_rows = [tx("l1", -40_000, "2026-08-18", description="Gym"), tx("l2", -40_000, "2026-08-25", description="Gym")]
    low = calculate_variable_spend_baseline(low_rows, "COP", date(2026, 9, 15), covered_week_starts={date(2026, 8, 17), date(2026, 8, 24), date(2026, 8, 31), date(2026, 9, 7)})
    assert low["median_weekly_spend"] == 20_000


def test_runway_and_confidence_caps():
    assert calculate_runway(12_000_000, 3_000_000, "COP")["coverage_months"] == 4
    invalid = calculate_runway(12_000_000, 0, "COP")
    assert invalid["evaluability"] == "UNEVALUABLE"
    assert invalid["reason"] == "NO_ESSENTIAL_EXPENSE_BASE"

    covered = {date(2026, 7, 6) + timedelta(days=7 * i) for i in range(8)}
    rows = [tx(str(i), -100_000, week.isoformat()) for i, week in enumerate(covered)]
    auto = project_cash("COP", date(2026, 9, 7), 7, 1_000_000, [], rows, starting_balance_source="ACCOUNTS", balance_freshness="UNKNOWN", covered_week_starts=covered)
    assert auto["status"] == "READY"
    assert auto["confidence"] == "MEDIUM"

    manual = project_cash("COP", date(2026, 9, 7), 7, 1_000_000, [], rows, starting_balance_source="MANUAL", balance_freshness="UNKNOWN", covered_week_starts=covered)
    assert manual["confidence"] == "HIGH"

    medium_event = project_cash("COP", date(2026, 9, 7), 7, 1_000_000, [event("m", "2026-09-08", 10_000, confidence="MEDIUM")], rows, starting_balance_source="MANUAL", balance_freshness="MANUAL", covered_week_starts=covered)
    assert medium_event["confidence"] == "MEDIUM"
