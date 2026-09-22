"""Short-term deterministic cash projection analytics."""

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, getcontext
from statistics import median
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.analytics.goal_math import emergency_coverage
from backend.analytics.understand import _in_range, _is_expense, _is_transfer, _merchant_key, _parse_date, _tx_currency, get_recurring_transactions

getcontext().prec = 28

STRONG_HISTORY_WEEKS = 8
USABLE_HISTORY_WEEKS = 4
MAX_LOOKBACK_WEEKS = 12


def _d(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def normalize_financial_event(event: Dict[str, Any]) -> Dict[str, Any]:
    amount = abs(_d(event.get("amount", 0)))
    direction = str(event.get("direction") or "").upper()
    if direction not in {"INFLOW", "OUTFLOW"}:
        direction = "INFLOW" if _d(event.get("amount", 0)) >= 0 else "OUTFLOW"
    return {**event, "amount": _money(amount), "direction": direction, "currency": str(event.get("currency") or "USD").upper()}


def aggregate_financial_events(events: List[Dict[str, Any]], currency: str, as_of: date, horizon_end: date) -> Dict[str, Any]:
    totals = {key: Decimal("0") for key in ["committed_inflows", "expected_inflows", "committed_outflows", "expected_outflows"]}
    included = []
    for raw in events:
        event = normalize_financial_event(raw)
        event_date = _parse_date(event["date"])
        if event["currency"] != currency.upper() or not (as_of < event_date <= horizon_end):
            continue
        certainty = str(event.get("certainty") or "EXPECTED").upper()
        direction = event["direction"]
        amount = _d(event["amount"])
        if certainty == "COMMITTED" and direction == "INFLOW":
            totals["committed_inflows"] += amount
        elif certainty == "COMMITTED" and direction == "OUTFLOW":
            totals["committed_outflows"] += amount
        elif direction == "INFLOW":
            totals["expected_inflows"] += amount
        else:
            totals["expected_outflows"] += amount
        included.append(event)
    return {**{key: _money(value) for key, value in totals.items()}, "events": included}


def _recurring_membership_keys(transactions: List[Dict[str, Any]], source_ids: Optional[Set[str]] = None) -> Set[Tuple[str, str, str, str, str]]:
    if not source_ids:
        return set()
    patterns = get_recurring_transactions(transactions)
    return {
        (p["merchant_key"], p["currency"], p["direction"], p["category"], p.get("account_id") or "")
        for p in patterns
        if p.get("confidence") in {"MEDIUM", "HIGH"} and (source_ids is None or p.get("id") in source_ids)
    }


def _tx_pattern_key(tx: Dict[str, Any]) -> Optional[Tuple[str, str, str, str, str]]:
    if _is_transfer(tx) or not _is_expense(tx):
        return None
    return (_merchant_key(tx), _tx_currency(tx), "OUTFLOW", tx.get("category") or "General", tx.get("account_id") or "")


def calculate_variable_spend_baseline(
    transactions: List[Dict[str, Any]],
    currency: str,
    as_of: date,
    covered_week_starts: Optional[Set[date]] = None,
    recurring_event_source_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    recurring_keys = _recurring_membership_keys(transactions, recurring_event_source_ids)
    week_start = _monday(as_of)
    lookback_start = week_start - timedelta(days=7 * MAX_LOOKBACK_WEEKS)
    weekly: Dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    observed_weeks: Set[date] = set()
    for tx in transactions:
        try:
            tx_date = _parse_date(tx["date"])
        except Exception:
            continue
        if not (lookback_start <= tx_date < week_start):
            continue
        if not _is_expense(tx) or _is_transfer(tx) or _tx_currency(tx) != currency.upper():
            continue
        key = _tx_pattern_key(tx)
        if key and key in recurring_keys:
            continue
        start = _monday(tx_date)
        weekly[start] += abs(_d(tx.get("amount", 0)))
        observed_weeks.add(start)
    coverage_limited = covered_week_starts is None
    weeks_to_use = sorted(observed_weeks if coverage_limited else covered_week_starts)[-MAX_LOOKBACK_WEEKS:]
    totals = [_money(weekly.get(week, Decimal("0"))) for week in weeks_to_use]
    reasons = []
    if coverage_limited:
        reasons.append("LIMITED_TRANSACTION_COVERAGE")
    if len(totals) < USABLE_HISTORY_WEEKS:
        return {"status": "NOT_ENOUGH_HISTORY", "reason": "NOT_ENOUGH_HISTORY", "weeks": len(totals), "weekly_totals": totals, "median_weekly_spend": None, "weekly_mad": None, "daily_equivalent": None, "confidence": "LOW", "confidence_reasons": reasons + ["fewer than 4 usable weeks"]}
    med = float(median(totals))
    mad = float(median([abs(value - med) for value in totals]))
    if med == 0 and mad == 0:
        relative_mad = 0.0
    elif med == 0:
        relative_mad = None
    else:
        relative_mad = mad / med
    if len(totals) >= STRONG_HISTORY_WEEKS and relative_mad is not None and relative_mad <= 0.50 and not coverage_limited:
        confidence = "HIGH"
    elif relative_mad is not None and relative_mad <= 1.00:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    return {
        "status": "READY",
        "weeks": len(totals),
        "weekly_totals": totals,
        "median_weekly_spend": round(med, 2),
        "weekly_mad": round(mad, 2),
        "relative_mad": round(relative_mad, 4) if relative_mad is not None else None,
        "daily_equivalent": round(med / 7, 2),
        "confidence": confidence,
        "confidence_reasons": reasons + [f"{len(totals)} usable weeks"],
    }


def _confidence_min(levels: List[str]) -> str:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return min(levels, key=lambda level: order.get(level, 0))


def project_cash(
    currency: str,
    as_of: date,
    horizon_days: int,
    starting_balance: Optional[float],
    events: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    starting_balance_source: str = "MANUAL",
    balance_as_of: Optional[str] = None,
    balance_freshness: str = "UNKNOWN",
    covered_week_starts: Optional[Set[date]] = None,
) -> Dict[str, Any]:
    horizon_end = as_of + timedelta(days=horizon_days)
    if starting_balance is None:
        return {"currency": currency, "as_of": as_of.isoformat(), "horizon_days": horizon_days, "status": "UNEVALUABLE", "reason": "STARTING_BALANCE_REQUIRED", "projected_balance": None}
    event_totals = aggregate_financial_events(events, currency, as_of, horizon_end)
    start = _d(starting_balance)
    known_balance = start + _d(event_totals["committed_inflows"]) + _d(event_totals["expected_inflows"]) - _d(event_totals["committed_outflows"]) - _d(event_totals["expected_outflows"])
    recurring_event_source_ids = {event.get("source_id") for event in event_totals["events"] if event.get("source") == "recurrence_pattern" and event.get("source_id")}
    baseline = calculate_variable_spend_baseline(transactions, currency, as_of, covered_week_starts, recurring_event_source_ids or set())
    if baseline["status"] != "READY":
        return {
            "currency": currency,
            "as_of": as_of.isoformat(),
            "horizon_days": horizon_days,
            "horizon_end": horizon_end.isoformat(),
            "starting_liquid_balance": _money(start),
            "starting_balance_source": starting_balance_source,
            "balance_as_of": balance_as_of,
            "balance_freshness": balance_freshness,
            **{key: event_totals[key] for key in ["committed_inflows", "expected_inflows", "committed_outflows", "expected_outflows"]},
            "balance_after_known_events": _money(known_balance),
            "variable_spend_baseline": baseline,
            "estimated_variable_outflows": None,
            "projected_balance": None,
            "status": "PARTIAL",
            "reason": baseline["reason"],
            "confidence": "LOW",
            "confidence_reasons": baseline["confidence_reasons"],
            "assumptions": {"event_interval": "(as_of, horizon_end]", "no_fx": True},
        }
    variable = _d(baseline["daily_equivalent"]) * Decimal(horizon_days)
    projected = known_balance - variable
    caps = [baseline["confidence"]]
    reasons = list(baseline["confidence_reasons"])
    if starting_balance_source != "MANUAL" and balance_freshness != "FRESH":
        caps.append("MEDIUM")
        reasons.append("UNKNOWN_BALANCE_FRESHNESS")
    if any(event.get("confidence") == "MEDIUM" for event in event_totals["events"] if event.get("certainty") == "EXPECTED"):
        caps.append("MEDIUM")
        reasons.append("MEDIUM_EXPECTED_EVENT")
    return {
        "currency": currency,
        "as_of": as_of.isoformat(),
        "horizon_days": horizon_days,
        "horizon_end": horizon_end.isoformat(),
        "starting_liquid_balance": _money(start),
        "starting_balance_source": starting_balance_source,
        "balance_as_of": balance_as_of,
        "balance_freshness": balance_freshness,
        **{key: event_totals[key] for key in ["committed_inflows", "expected_inflows", "committed_outflows", "expected_outflows"]},
        "balance_after_known_events": _money(known_balance),
        "variable_spend_baseline": baseline,
        "estimated_variable_outflows": _money(variable),
        "projected_balance": _money(projected),
        "status": "READY",
        "reason": None,
        "confidence": _confidence_min(caps),
        "confidence_reasons": reasons,
        "assumptions": {"event_interval": "(as_of, horizon_end]", "no_fx": True},
    }


def calculate_safe_to_spend(projection: Dict[str, Any], reserve_floor: Optional[float]) -> Dict[str, Any]:
    if reserve_floor is None:
        return {"status": "UNEVALUABLE", "reason": "RESERVE_FLOOR_REQUIRED", "safe_to_spend": None}
    if projection.get("starting_liquid_balance") is None or projection.get("estimated_variable_outflows") is None:
        return {"status": "UNEVALUABLE", "reason": projection.get("reason") or "PROJECTION_REQUIRED", "safe_to_spend": None}
    safe = (
        _d(projection["starting_liquid_balance"])
        + _d(projection["committed_inflows"])
        - _d(projection["committed_outflows"])
        - _d(projection["expected_outflows"])
        - _d(projection["estimated_variable_outflows"])
        - _d(reserve_floor)
    )
    return {
        "status": "READY",
        "reason": None,
        "currency": projection["currency"],
        "safe_to_spend": _money(safe),
        "expected_inflow_upside": projection.get("expected_inflows", 0.0),
        "reserve_floor": reserve_floor,
        "projection_status": projection.get("status"),
    }


def calculate_runway(liquid_resources: float, essential_monthly_expenses: float, currency: str = "USD") -> Dict[str, Any]:
    return emergency_coverage(liquid_resources, essential_monthly_expenses, currency)
