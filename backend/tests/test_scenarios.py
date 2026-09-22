from copy import deepcopy
from datetime import date

import pytest

from backend.analytics.scenarios import evaluate_cash_scenario, evaluate_debt_scenario, evaluate_goal_scenario, evaluate_scenario


AS_OF = date(2026, 9, 21)


def tx_rows(weekly_amount=500_000, weeks=4, currency="COP"):
    days = ["2026-08-24", "2026-08-31", "2026-09-07", "2026-09-14"]
    return [
        {"id": f"tx-{idx}", "date": day, "amount": -weekly_amount, "currency": currency, "description": "Market", "category": "Food"}
        for idx, day in enumerate(days[:weeks])
    ]


def cash_context():
    return {"currency": "COP", "as_of": AS_OF, "horizon_days": 28, "starting_balance": 5_000_000, "reserve_floor": 2_000_000}


def cash_engine(transactions=None, events=None):
    return {
        "starting_balance": 5_000_000,
        "starting_balance_source": "MANUAL",
        "balance_as_of": AS_OF.isoformat(),
        "balance_freshness": "MANUAL",
        "transactions": transactions if transactions is not None else tx_rows(),
        "events": events if events is not None else [],
    }


def test_cash_weekly_reduction_delta_percent_and_floor():
    reduced = evaluate_cash_scenario(cash_context(), {"weekly_variable_spend_delta": -100_000}, cash_engine())
    assert reduced["scenario"]["projection"]["variable_spend_baseline"]["scenario_median_weekly_spend"] == 400_000
    assert reduced["deltas"]["variable_weekly_spend"] == -100_000

    percent = evaluate_cash_scenario(cash_context(), {"variable_spend_percent_change": -0.2}, cash_engine())
    assert percent["scenario"]["projection"]["variable_spend_baseline"]["scenario_median_weekly_spend"] == 400_000

    floor = evaluate_cash_scenario(cash_context(), {"weekly_variable_spend_delta": -600_000}, cash_engine(tx_rows(100_000)))
    assert floor["scenario"]["projection"]["variable_spend_baseline"]["scenario_median_weekly_spend"] == 0


def test_cash_simulated_outflow_inflow_horizon_and_reserve_semantics():
    base = evaluate_cash_scenario(cash_context(), {}, cash_engine())
    purchase = evaluate_cash_scenario(cash_context(), {"simulated_events": [{"date": "2026-10-01", "amount": 1_000_000, "currency": "COP", "direction": "OUTFLOW"}]}, cash_engine())
    assert purchase["deltas"]["projected_balance"] == -1_000_000
    assert purchase["deltas"]["safe_to_spend"] == -1_000_000

    inflow = evaluate_cash_scenario(cash_context(), {"simulated_events": [{"date": "2026-10-01", "amount": 1_000_000, "currency": "COP", "direction": "INFLOW"}]}, cash_engine())
    assert inflow["deltas"]["projected_balance"] == 1_000_000
    assert inflow["deltas"]["safe_to_spend"] == 0
    assert inflow["scenario"]["simulated_inflow_upside"] == 1_000_000

    outside = evaluate_cash_scenario(cash_context(), {"simulated_events": [{"date": "2026-11-01", "amount": 1_000_000, "currency": "COP", "direction": "OUTFLOW"}]}, cash_engine())
    assert outside["scenario"] == base["scenario"]

    reserve = evaluate_cash_scenario(cash_context(), {"reserve_floor_override": 3_000_000}, cash_engine())
    assert reserve["deltas"]["safe_to_spend"] == -1_000_000


def test_cash_variable_baseline_required_currency_isolation_and_validation():
    short_history = evaluate_cash_scenario(cash_context(), {"weekly_variable_spend_delta": -100_000}, cash_engine(tx_rows(500_000, weeks=2)))
    assert short_history["status"] == "UNEVALUABLE"
    assert short_history["scenario"]["projection"]["reason"] == "VARIABLE_BASELINE_REQUIRED"

    with pytest.raises(ValueError, match="CURRENCY_MISMATCH"):
        evaluate_cash_scenario(cash_context(), {"simulated_events": [{"date": "2026-10-01", "amount": 1_000_000, "currency": "USD", "direction": "OUTFLOW"}]}, cash_engine())

    with pytest.raises(ValueError, match="ONLY_ONE_VARIABLE_SPEND_OVERRIDE_ALLOWED"):
        evaluate_cash_scenario(cash_context(), {"weekly_variable_spend_delta": -1, "variable_spend_percent_change": -0.1}, cash_engine())


def test_debt_extra_payment_and_non_amortizing_status_propagation():
    result = evaluate_debt_scenario({"balance": 12_000_000, "annual_effective_rate_pct": 24, "monthly_payment": 1_000_000, "currency": "COP"}, {"extra_payment": 300_000})
    assert result["scenario"]["periods"] <= result["baseline"]["periods"]
    assert result["scenario"]["total_interest"] <= result["baseline"]["total_interest"]
    assert result["deltas"]["periods"] == result["scenario"]["periods"] - result["baseline"]["periods"]

    non_amortizing = evaluate_debt_scenario({"balance": 12_000_000, "annual_effective_rate_pct": 24, "monthly_payment": 1, "currency": "COP"}, {"extra_payment": 0})
    assert non_amortizing["status"] == "NON_AMORTIZING"
    assert non_amortizing["deltas"] == {}


def test_goal_contribution_improves_eta_and_delta_semantics():
    result = evaluate_goal_scenario(
        {"current_amount": 3_000_000, "target_amount": 12_000_000, "annual_effective_rate_pct": 0, "periods": 24, "monthly_contribution": 500_000, "contribution_timing": "END", "currency": "COP"},
        {"monthly_contribution_override": 800_000},
    )
    assert result["scenario"]["goal_eta"]["periods_required"] <= result["baseline"]["goal_eta"]["periods_required"]
    assert result["deltas"]["goal_eta_periods"] == result["scenario"]["goal_eta"]["periods_required"] - result["baseline"]["goal_eta"]["periods_required"]


def test_baseline_immutability_no_persistence_and_determinism():
    context = cash_context()
    engine = cash_engine()
    before_context = deepcopy(context)
    before_engine = deepcopy(engine)
    overrides = {"simulated_events": [{"date": "2026-10-01", "amount": 1_000_000, "currency": "COP", "direction": "OUTFLOW"}]}
    one = evaluate_scenario("CASH", context, overrides, engine)
    two = evaluate_scenario("CASH", context, overrides, engine)
    assert context == before_context
    assert engine == before_engine
    assert one == two
