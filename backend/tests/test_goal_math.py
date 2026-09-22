import pytest

from backend.analytics.goal_math import (
    amortize_debt,
    effective_rate,
    emergency_coverage,
    future_value,
    opportunity_cost,
    required_payment_for_target,
    solve_periods_to_target,
)


def approx(value, expected, tolerance=0.02):
    assert value == pytest.approx(expected, abs=tolerance)


@pytest.mark.parametrize(
    "rate,expected",
    [
        (0, 0),
        (12, 0.009488792934582974),
        (10, 0.007974140428903741),
    ],
)
def test_effective_rate_vectors(rate, expected):
    assert float(effective_rate(rate)) == pytest.approx(expected)


def test_effective_rate_rejects_invalid_rate():
    with pytest.raises(ValueError):
        effective_rate(-100)


def test_future_value_vectors():
    assert future_value(1_000_000, 100_000, 0, 12, "END")["future_value"] == 2_200_000
    approx(future_value(1_000_000, 100_000, 12, 12, "END")["future_value"], 2_384_649.79)
    approx(future_value(1_000_000, 100_000, 12, 12, "BEGIN")["future_value"], 2_396_649.79)
    assert future_value(1_000_000, 100_000, 12, 0, "END")["future_value"] == 1_000_000
    assert future_value(0, 100_000, 0, 12, "END")["future_value"] == 1_200_000
    assert future_value(1_000_000, 100_000, 0, 12, "BEGIN")["future_value"] == future_value(1_000_000, 100_000, 0, 12, "END")["future_value"]
    approx(future_value(1_000_000, 0, -12, 12, "END")["future_value"], 880_000)
    assert future_value(1_000_000, 100_000, 12, 12, "BEGIN")["future_value"] >= future_value(1_000_000, 100_000, 12, 12, "END")["future_value"]


def test_savings_goal_vectors():
    assert required_payment_for_target(12_000_000, 3_000_000, 0, 9)["required_contribution"] == 1_000_000
    completed = required_payment_for_target(10_000_000, 12_000_000, 12, 24)
    assert completed["required_contribution"] == 0
    assert completed["status"] == "COMPLETED"
    approx(required_payment_for_target(10_000_000, 2_000_000, 12, 24, "END")["required_contribution"], 279_412.13)
    sufficient = required_payment_for_target(1_100_000, 1_000_000, 12, 12)
    assert sufficient["required_contribution"] == 0
    assert sufficient["status"] == "PROJECTED_GROWTH_SUFFICIENT"


def test_goal_eta_vectors():
    assert solve_periods_to_target(5_000_000, 2_000_000, 500_000, 0)["periods_required"] == 6
    assert solve_periods_to_target(5_000_000, 5_000_000, 500_000, 0)["periods_required"] == 0
    unreachable = solve_periods_to_target(5_000_000, 2_000_000, 0, 0)
    assert unreachable["reached"] is False
    assert unreachable["reason"] == "TARGET_NOT_REACHABLE"
    assert solve_periods_to_target(10_000_000, 2_000_000, 300_000, 12)["periods_required"] == 23


def test_emergency_coverage_vectors():
    assert emergency_coverage(12_000_000, 3_000_000)["coverage_months"] == 4
    assert emergency_coverage(0, 3_000_000)["coverage_months"] == 0
    unevaluable = emergency_coverage(1_000_000, 0)
    assert unevaluable["evaluability"] == "UNEVALUABLE"
    assert unevaluable["reason"] == "NO_ESSENTIAL_EXPENSE_BASE"


def test_debt_vectors_and_extra_payment_invariant():
    zero = amortize_debt(0, 12, 1_000_000)
    assert zero["payoff_status"] == "PAID"
    assert zero["periods"] == 0
    assert zero["total_interest"] == 0

    no_interest = amortize_debt(12_000_000, 0, 1_000_000)
    assert no_interest["periods"] == 12
    assert no_interest["total_interest"] == 0

    twelve = amortize_debt(12_000_000, 12, 1_062_744.81)
    assert twelve["periods"] == 12
    approx(twelve["total_interest"], 752_937.70, 0.20)

    non = amortize_debt(12_000_000, 12, 10)
    assert non["payoff_status"] == "NON_AMORTIZING"

    extra = amortize_debt(12_000_000, 12, 1_000_000, 250_000)
    base = extra["comparison"]["baseline"]
    assert extra["periods"] <= base["periods"]
    assert extra["total_interest"] <= base["total_interest"]


def test_opportunity_cost_vectors():
    result = opportunity_cost(1_000_000, 12, 12)
    approx(result["assumed_future_value"], 1_120_000)
    approx(result["opportunity_cost"], 120_000)
    assert opportunity_cost(1_000_000, 0, 12)["opportunity_cost"] == 0
