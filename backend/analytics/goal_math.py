"""Pure goal, interest and calculator math."""

from decimal import Decimal, getcontext
from typing import Any, Dict, Optional

getcontext().prec = 34

MAX_GOAL_PERIODS = 1200
MAX_DEBT_PERIODS = 1200


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def _ratio(value: Decimal) -> float:
    return float(value)


def effective_rate(annual_effective_rate_pct: Any, periods_per_year: int = 12) -> Decimal:
    annual = _d(annual_effective_rate_pct) / Decimal("100")
    if annual <= Decimal("-1"):
        raise ValueError("annual_effective_rate_pct must be greater than -100")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    return (Decimal("1") + annual) ** (Decimal("1") / Decimal(periods_per_year)) - Decimal("1")


def rate_assumptions(annual_effective_rate_pct: Any, periods_per_year: int = 12, contribution_timing: Optional[str] = None) -> Dict[str, Any]:
    periodic = effective_rate(annual_effective_rate_pct, periods_per_year)
    assumptions = {
        "annual_effective_rate_pct": float(_d(annual_effective_rate_pct)),
        "periodic_rate": _ratio(periodic),
        "periods_per_year": periods_per_year,
    }
    if contribution_timing:
        assumptions["contribution_timing"] = contribution_timing
    return assumptions


def future_value(
    principal: Any,
    periodic_contribution: Any,
    annual_effective_rate_pct: Any,
    periods: int,
    contribution_timing: str = "END",
    currency: str = "USD",
    periods_per_year: int = 12,
) -> Dict[str, Any]:
    if periods < 0:
        raise ValueError("periods must be non-negative")
    timing = contribution_timing.upper()
    if timing not in {"END", "BEGIN"}:
        raise ValueError("contribution_timing must be END or BEGIN")
    p = _d(principal)
    pmt = _d(periodic_contribution)
    r = effective_rate(annual_effective_rate_pct, periods_per_year)
    n = Decimal(periods)
    if periods == 0:
        fv = p
    elif r == 0:
        fv = p + pmt * n
    else:
        growth = (Decimal("1") + r) ** n
        contribution_component = pmt * ((growth - Decimal("1")) / r)
        if timing == "BEGIN":
            contribution_component *= Decimal("1") + r
        fv = p * growth + contribution_component
    total_contributions = p + pmt * n
    return {
        "status": "OK",
        "currency": currency,
        "principal": _money(p),
        "periodic_contribution": _money(pmt),
        "periods": periods,
        "future_value": _money(fv),
        "total_contributions": _money(total_contributions),
        "growth": _money(fv - total_contributions),
        "contribution_timing": timing,
        "assumptions": rate_assumptions(annual_effective_rate_pct, periods_per_year, timing),
    }


def required_payment_for_target(
    target: Any,
    current_amount: Any,
    annual_effective_rate_pct: Any,
    periods: int,
    contribution_timing: str = "END",
    currency: str = "USD",
    periods_per_year: int = 12,
) -> Dict[str, Any]:
    target_d = _d(target)
    current = _d(current_amount)
    timing = contribution_timing.upper()
    if target_d <= current:
        return {"status": "COMPLETED", "reason": "TARGET_ALREADY_REACHED", "currency": currency, "target": _money(target_d), "current_amount": _money(current), "periods": periods, "required_contribution": 0.0, "assumptions": rate_assumptions(annual_effective_rate_pct, periods_per_year, timing)}
    if periods <= 0:
        return {"status": "UNEVALUABLE", "reason": "INVALID_PERIODS", "currency": currency, "target": _money(target_d), "current_amount": _money(current), "periods": periods, "required_contribution": None, "assumptions": rate_assumptions(annual_effective_rate_pct, periods_per_year, timing)}
    projected_current = _d(future_value(current, 0, annual_effective_rate_pct, periods, timing, currency, periods_per_year)["future_value"])
    if projected_current >= target_d:
        return {"status": "PROJECTED_GROWTH_SUFFICIENT", "reason": "PROJECTED_GROWTH_SUFFICIENT", "currency": currency, "target": _money(target_d), "current_amount": _money(current), "periods": periods, "required_contribution": 0.0, "assumptions": rate_assumptions(annual_effective_rate_pct, periods_per_year, timing)}
    r = effective_rate(annual_effective_rate_pct, periods_per_year)
    n = Decimal(periods)
    needed = target_d - projected_current
    if r == 0:
        required = (target_d - current) / n
    else:
        growth = (Decimal("1") + r) ** n
        factor = (growth - Decimal("1")) / r
        if timing == "BEGIN":
            factor *= Decimal("1") + r
        required = needed / factor
    if required < 0:
        required = Decimal("0")
    return {"status": "OK", "reason": None, "currency": currency, "target": _money(target_d), "current_amount": _money(current), "periods": periods, "required_contribution": _money(required), "assumptions": rate_assumptions(annual_effective_rate_pct, periods_per_year, timing)}


def solve_periods_to_target(
    target: Any,
    current_amount: Any,
    periodic_contribution: Any,
    annual_effective_rate_pct: Any,
    contribution_timing: str = "END",
    currency: str = "USD",
    periods_per_year: int = 12,
    max_periods: int = MAX_GOAL_PERIODS,
) -> Dict[str, Any]:
    target_d = _d(target)
    current = _d(current_amount)
    if target_d <= current:
        return {"reached": True, "reason": "TARGET_ALREADY_REACHED", "currency": currency, "target": _money(target_d), "current_amount": _money(current), "periodic_contribution": _money(_d(periodic_contribution)), "periods_required": 0, "assumptions": rate_assumptions(annual_effective_rate_pct, periods_per_year, contribution_timing.upper())}
    for period in range(1, max_periods + 1):
        fv = _d(future_value(current, periodic_contribution, annual_effective_rate_pct, period, contribution_timing, currency, periods_per_year)["future_value"])
        if fv >= target_d:
            return {"reached": True, "reason": None, "currency": currency, "target": _money(target_d), "current_amount": _money(current), "periodic_contribution": _money(_d(periodic_contribution)), "periods_required": period, "projected_value": _money(fv), "assumptions": rate_assumptions(annual_effective_rate_pct, periods_per_year, contribution_timing.upper())}
    return {"reached": False, "reason": "TARGET_NOT_REACHABLE", "currency": currency, "target": _money(target_d), "current_amount": _money(current), "periodic_contribution": _money(_d(periodic_contribution)), "periods_required": None, "assumptions": rate_assumptions(annual_effective_rate_pct, periods_per_year, contribution_timing.upper())}


def emergency_coverage(liquid_resources: Any, essential_monthly_expenses: Any, currency: str = "USD") -> Dict[str, Any]:
    liquid = _d(liquid_resources)
    expenses = _d(essential_monthly_expenses)
    if expenses <= 0:
        return {"currency": currency, "liquid_resources": _money(liquid), "essential_monthly_expenses": _money(expenses), "coverage_months": None, "evaluability": "UNEVALUABLE", "reason": "NO_ESSENTIAL_EXPENSE_BASE"}
    return {"currency": currency, "liquid_resources": _money(liquid), "essential_monthly_expenses": _money(expenses), "coverage_months": _ratio(liquid / expenses), "evaluability": "EVALUABLE", "reason": None}


def _simulate_debt(balance: Decimal, annual_effective_rate_pct: Any, monthly_payment: Decimal, extra_payment: Decimal, currency: str, max_periods: int) -> Dict[str, Any]:
    if balance <= 0:
        return {"payoff_status": "PAID", "currency": currency, "periods": 0, "total_paid": 0.0, "total_interest": 0.0, "final_payment": 0.0, "monthly_payment": _money(monthly_payment), "extra_payment": _money(extra_payment), "assumptions": rate_assumptions(annual_effective_rate_pct)}
    r = effective_rate(annual_effective_rate_pct)
    scheduled = monthly_payment + extra_payment
    if scheduled <= 0 or (r > 0 and scheduled <= balance * r):
        return {"payoff_status": "NON_AMORTIZING", "currency": currency, "periods": None, "total_paid": None, "total_interest": None, "final_payment": None, "monthly_payment": _money(monthly_payment), "extra_payment": _money(extra_payment), "assumptions": rate_assumptions(annual_effective_rate_pct)}
    periods = 0
    total_paid = Decimal("0")
    total_interest = Decimal("0")
    final_payment = Decimal("0")
    current = balance
    while current > 0 and periods < max_periods:
        interest = current * r
        amount_due = current + interest
        payment = scheduled if scheduled < amount_due else amount_due
        current = amount_due - payment
        total_paid += payment
        total_interest += interest
        final_payment = payment
        periods += 1
    if current > Decimal("0.00000001"):
        return {"payoff_status": "MAX_PERIODS_REACHED", "currency": currency, "periods": periods, "total_paid": _money(total_paid), "total_interest": _money(total_interest), "final_payment": _money(final_payment), "monthly_payment": _money(monthly_payment), "extra_payment": _money(extra_payment), "assumptions": rate_assumptions(annual_effective_rate_pct)}
    return {"payoff_status": "PAID", "currency": currency, "periods": periods, "total_paid": _money(total_paid), "total_interest": _money(total_interest), "final_payment": _money(final_payment), "monthly_payment": _money(monthly_payment), "extra_payment": _money(extra_payment), "assumptions": rate_assumptions(annual_effective_rate_pct)}


def amortize_debt(
    balance: Any,
    annual_effective_rate_pct: Any,
    monthly_payment: Any,
    extra_payment: Any = 0,
    currency: str = "USD",
    max_periods: int = MAX_DEBT_PERIODS,
) -> Dict[str, Any]:
    bal = _d(balance)
    payment = _d(monthly_payment)
    extra = _d(extra_payment)
    scenario = _simulate_debt(bal, annual_effective_rate_pct, payment, extra, currency, max_periods)
    baseline = _simulate_debt(bal, annual_effective_rate_pct, payment, Decimal("0"), currency, max_periods)
    comparison = {"baseline": baseline}
    if scenario.get("payoff_status") == "PAID" and baseline.get("payoff_status") == "PAID":
        comparison["periods_saved"] = max(int(baseline["periods"]) - int(scenario["periods"]), 0)
        comparison["interest_saved"] = _money(_d(baseline["total_interest"]) - _d(scenario["total_interest"]))
    return {**scenario, "comparison": comparison}


def opportunity_cost(amount: Any, annual_effective_rate_pct: Any, periods: int, currency: str = "USD") -> Dict[str, Any]:
    fv = future_value(amount, 0, annual_effective_rate_pct, periods, "END", currency)
    original = _d(amount)
    future = _d(fv["future_value"])
    return {"currency": currency, "amount": _money(original), "periods": periods, "assumed_future_value": _money(future), "opportunity_cost": _money(future - original), "assumptions": fv["assumptions"], "note": "Assumed rate is not guaranteed."}
