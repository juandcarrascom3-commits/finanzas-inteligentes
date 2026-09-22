"""Read-only scenario orchestration over canonical finance engines."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional

from backend.analytics.cash_projection import calculate_safe_to_spend, project_cash
from backend.analytics.goal_math import amortize_debt, future_value, required_payment_for_target, solve_periods_to_target

getcontext().prec = 28


def _d(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def _delta(scenario: Dict[str, Any], baseline: Dict[str, Any], keys: List[str]) -> Dict[str, float]:
    deltas: Dict[str, float] = {}
    for key in keys:
        if baseline.get(key) is None or scenario.get(key) is None:
            continue
        deltas[key] = _money(_d(scenario[key]) - _d(baseline[key]))
    return deltas


def _validate_currency(currency: str, expected: str) -> str:
    normalized = str(currency or expected).upper()
    if normalized != expected.upper():
        raise ValueError("CURRENCY_MISMATCH")
    return normalized


def evaluate_cash_scenario(context: Dict[str, Any], overrides: Dict[str, Any], engine_inputs: Dict[str, Any]) -> Dict[str, Any]:
    if "weekly_variable_spend_delta" in overrides and "variable_spend_percent_change" in overrides:
        raise ValueError("ONLY_ONE_VARIABLE_SPEND_OVERRIDE_ALLOWED")

    currency = str(context.get("currency") or "USD").upper()
    as_of = context["as_of"]
    horizon_days = int(context.get("horizon_days", 30))
    reserve_floor = context.get("reserve_floor")
    scenario_reserve = overrides.get("reserve_floor_override", reserve_floor)
    if scenario_reserve is not None and _d(scenario_reserve) < 0:
        raise ValueError("INVALID_RESERVE_FLOOR")

    base_events = deepcopy(engine_inputs.get("events", []))
    transactions = deepcopy(engine_inputs.get("transactions", []))
    common = {
        "currency": currency,
        "as_of": as_of,
        "horizon_days": horizon_days,
        "starting_balance": engine_inputs.get("starting_balance"),
        "transactions": transactions,
        "starting_balance_source": engine_inputs.get("starting_balance_source", "MANUAL"),
        "balance_as_of": engine_inputs.get("balance_as_of"),
        "balance_freshness": engine_inputs.get("balance_freshness", "UNKNOWN"),
    }

    baseline_projection = project_cash(events=deepcopy(base_events), **common)
    baseline_safe = calculate_safe_to_spend(baseline_projection, reserve_floor)

    simulated_events = []
    horizon_end = as_of + timedelta(days=horizon_days)
    for raw in overrides.get("simulated_events") or []:
        _validate_currency(raw.get("currency"), currency)
        event_date = date.fromisoformat(str(raw["date"])[:10])
        if not (as_of < event_date <= horizon_end):
            continue
        direction = str(raw.get("direction") or "").upper()
        if direction not in {"INFLOW", "OUTFLOW"}:
            raise ValueError("INVALID_SIMULATED_EVENT_DIRECTION")
        simulated_events.append({
            "id": f"scenario:{len(simulated_events) + 1}",
            "date": event_date.isoformat(),
            "amount": _money(abs(_d(raw.get("amount", 0)))),
            "currency": currency,
            "direction": direction,
            "label": raw.get("label") or "Simulated event",
            "certainty": "SIMULATED",
            "confidence": "SIMULATED",
            "source": "scenario",
        })

    scenario_projection = project_cash(events=deepcopy(base_events) + simulated_events, **common)
    variable_override = "weekly_variable_spend_delta" in overrides or "variable_spend_percent_change" in overrides
    if variable_override:
        baseline_variable = baseline_projection.get("variable_spend_baseline") or {}
        if baseline_variable.get("status") != "READY" or baseline_variable.get("median_weekly_spend") is None:
            scenario_projection = {**scenario_projection, "status": "UNEVALUABLE", "reason": "VARIABLE_BASELINE_REQUIRED", "projected_balance": None, "estimated_variable_outflows": None}
        else:
            weekly = _d(baseline_variable["median_weekly_spend"])
            if "weekly_variable_spend_delta" in overrides:
                weekly += _d(overrides.get("weekly_variable_spend_delta"))
            else:
                weekly *= Decimal("1") + _d(overrides.get("variable_spend_percent_change"))
            if weekly < 0:
                weekly = Decimal("0")
            daily = weekly / Decimal("7")
            variable_outflow = daily * Decimal(horizon_days)
            known = _d(scenario_projection.get("balance_after_known_events"))
            scenario_projection = {
                **scenario_projection,
                "variable_spend_baseline": {**baseline_variable, "scenario_median_weekly_spend": _money(weekly), "scenario_daily_equivalent": _money(daily)},
                "estimated_variable_outflows": _money(variable_outflow),
                "projected_balance": _money(known - variable_outflow),
                "status": "READY" if scenario_projection.get("starting_liquid_balance") is not None else scenario_projection.get("status"),
                "reason": None if scenario_projection.get("starting_liquid_balance") is not None else scenario_projection.get("reason"),
            }

    scenario_safe = calculate_safe_to_spend(scenario_projection, scenario_reserve)
    simulated_inflow_upside = sum((_d(event["amount"]) for event in simulated_events if event["direction"] == "INFLOW"), Decimal("0"))
    affected = []
    if simulated_events or variable_override:
        affected.extend(["projected_balance", "safe_to_spend"])
    if variable_override:
        affected.append("variable_weekly_spend")
    if scenario_reserve != reserve_floor:
        affected.append("reserve_floor")
    affected_metrics = list(dict.fromkeys(affected))

    baseline = {"projection": baseline_projection, "safe_to_spend": baseline_safe}
    scenario = {"projection": scenario_projection, "safe_to_spend": scenario_safe, "simulated_inflow_upside": _money(simulated_inflow_upside)}
    deltas = {
        "projected_balance": _delta(scenario_projection, baseline_projection, ["projected_balance"]).get("projected_balance"),
        "safe_to_spend": _delta(scenario_safe, baseline_safe, ["safe_to_spend"]).get("safe_to_spend"),
    }
    if variable_override:
        base_weekly = baseline_projection.get("variable_spend_baseline", {}).get("median_weekly_spend")
        scen_weekly = scenario_projection.get("variable_spend_baseline", {}).get("scenario_median_weekly_spend")
        if base_weekly is not None and scen_weekly is not None:
            deltas["variable_weekly_spend"] = _money(_d(scen_weekly) - _d(base_weekly))
    return {
        "scenario_type": "CASH",
        "baseline": baseline,
        "scenario": scenario,
        "deltas": {k: v for k, v in deltas.items() if v is not None},
        "affected_metrics": affected_metrics,
        "assumptions": {"currency": currency, "as_of": as_of.isoformat(), "horizon_days": horizon_days, "simulated_events": len(simulated_events), "no_fx": True},
        "status": "READY" if scenario_projection.get("status") == "READY" and scenario_safe.get("status") == "READY" else scenario_projection.get("status") or scenario_safe.get("status"),
    }


def evaluate_debt_scenario(context: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    extra = _d(overrides.get("extra_payment", 0))
    if extra < 0:
        raise ValueError("INVALID_EXTRA_PAYMENT")
    args = {
        "balance": context.get("balance", 0),
        "annual_effective_rate_pct": context.get("annual_effective_rate_pct", 0),
        "monthly_payment": context.get("monthly_payment", 0),
        "currency": str(context.get("currency") or "USD").upper(),
    }
    baseline = amortize_debt(extra_payment=0, **args)
    scenario = amortize_debt(extra_payment=extra, **args)
    return {
        "scenario_type": "DEBT",
        "baseline": baseline,
        "scenario": scenario,
        "deltas": _delta(scenario, baseline, ["periods", "total_interest", "total_paid"]),
        "affected_metrics": [key for key in ["payoff_periods", "total_interest", "total_paid"] if baseline.get("periods" if key == "payoff_periods" else key) is not None and scenario.get("periods" if key == "payoff_periods" else key) is not None],
        "assumptions": {"currency": args["currency"], "extra_payment": _money(extra), "delta_semantics": "scenario - baseline"},
        "status": scenario.get("payoff_status") or baseline.get("payoff_status"),
    }


def evaluate_goal_scenario(context: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"monthly_contribution_override", "target_amount_override", "periods_override"}
    if not any(key in overrides for key in allowed):
        raise ValueError("GOAL_OVERRIDE_REQUIRED")
    currency = str(context.get("currency") or "USD").upper()
    contribution = context.get("monthly_contribution", 0)
    target = context.get("target_amount", 0)
    periods = int(context.get("periods", 0))
    scenario_contribution = overrides.get("monthly_contribution_override", contribution)
    scenario_target = overrides.get("target_amount_override", target)
    scenario_periods = int(overrides.get("periods_override", periods))
    common = {
        "current_amount": context.get("current_amount", 0),
        "annual_effective_rate_pct": context.get("annual_effective_rate_pct", 0),
        "contribution_timing": context.get("contribution_timing", "END"),
        "currency": currency,
    }

    def run(target_amount: Any, monthly_contribution: Any, period_count: int) -> Dict[str, Any]:
        return {
            "future_value": future_value(common["current_amount"], monthly_contribution, common["annual_effective_rate_pct"], period_count, common["contribution_timing"], currency),
            "goal_eta": solve_periods_to_target(target_amount, common["current_amount"], monthly_contribution, common["annual_effective_rate_pct"], common["contribution_timing"], currency),
            "required_payment": required_payment_for_target(target_amount, common["current_amount"], common["annual_effective_rate_pct"], period_count, common["contribution_timing"], currency),
        }

    baseline = run(target, contribution, periods)
    scenario = run(scenario_target, scenario_contribution, scenario_periods)
    deltas: Dict[str, float] = {}
    fv_delta = _delta(scenario["future_value"], baseline["future_value"], ["future_value"])
    if "future_value" in fv_delta:
        deltas["future_value"] = fv_delta["future_value"]
    eta_delta = _delta(scenario["goal_eta"], baseline["goal_eta"], ["periods_required"])
    if "periods_required" in eta_delta:
        deltas["goal_eta_periods"] = eta_delta["periods_required"]
    payment_delta = _delta(scenario["required_payment"], baseline["required_payment"], ["required_contribution"])
    if "required_contribution" in payment_delta:
        deltas["required_payment"] = payment_delta["required_contribution"]
    affected = []
    if "monthly_contribution_override" in overrides or "periods_override" in overrides:
        affected.extend(["future_value", "goal_eta_periods"])
    if "target_amount_override" in overrides or "periods_override" in overrides:
        affected.append("required_payment")
    return {
        "scenario_type": "GOAL",
        "baseline": baseline,
        "scenario": scenario,
        "deltas": deltas,
        "affected_metrics": list(dict.fromkeys(affected)),
        "assumptions": {"currency": currency, "contribution_timing": common["contribution_timing"], "delta_semantics": "scenario - baseline"},
        "status": "READY",
    }


def evaluate_scenario(scenario_type: str, context: Dict[str, Any], overrides: Dict[str, Any], engine_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    kind = str(scenario_type or "").upper()
    baseline_before = deepcopy(context)
    if kind == "CASH":
        result = evaluate_cash_scenario(context, overrides, engine_inputs or {})
    elif kind == "DEBT":
        result = evaluate_debt_scenario(context, overrides)
    elif kind == "GOAL":
        result = evaluate_goal_scenario(context, overrides)
    else:
        raise ValueError("INVALID_SCENARIO_TYPE")
    if context != baseline_before:
        raise RuntimeError("BASELINE_MUTATED")
    return result
