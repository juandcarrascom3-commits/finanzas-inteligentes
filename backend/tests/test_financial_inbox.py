from copy import deepcopy
from datetime import date

from backend.analytics.financial_inbox import compose_financial_inbox


AS_OF = date(2026, 9, 21)


def projection(**overrides):
    base = {
        "currency": "COP",
        "as_of": AS_OF.isoformat(),
        "horizon_days": 30,
        "horizon_end": "2026-10-21",
        "status": "READY",
        "projected_balance": 500000,
        "confidence": "HIGH",
        "confidence_reasons": ["fixture"],
    }
    return {**base, **overrides}


def safe(**overrides):
    return {"status": "READY", "currency": "COP", "safe_to_spend": 100000, "reserve_floor": 2000000, **overrides}


def inbox(**kwargs):
    payload = {
        "as_of": AS_OF,
        "currency": "COP",
        "horizon_days": 30,
        "projection": projection(),
        "safe_to_spend": safe(),
        "plan_vs_actual": [],
        "budget_burn": [],
        "data_confidence": {"level": "HIGH", "reasons": [], "inputs": {}},
        "financial_events": [],
    }
    payload.update(kwargs)
    return compose_financial_inbox(**payload)


def types(result):
    return [item["type"] for item in result["attention_items"]]


def test_projected_cash_shortfall_precedes_negative_safe_to_spend():
    result = inbox(projection=projection(projected_balance=-1), safe_to_spend=safe(safe_to_spend=-10))
    assert types(result) == ["PROJECTED_CASH_SHORTFALL"]
    assert result["attention_items"][0]["severity"] == "URGENT"


def test_negative_safe_to_spend_only_when_no_cash_shortfall():
    result = inbox(projection=projection(projected_balance=1), safe_to_spend=safe(safe_to_spend=-10))
    assert types(result) == ["SAFE_TO_SPEND_NEGATIVE"]
    assert result["attention_items"][0]["severity"] == "ATTENTION"


def test_budget_over_plan_precedes_pace_risk_for_same_category():
    result = inbox(
        plan_vs_actual=[{"category": "Food", "currency": "COP", "planned": 100, "actual": 150, "variance": 50, "variance_pct": 50, "status": "OVER_PLAN"}],
        budget_burn=[{"category": "Food", "currency": "COP", "budget": 100, "spent": 80, "projected_close": 160, "pace_status": "OVER_PACE", "budget_status": "WITHIN_BUDGET"}],
    )
    assert types(result) == ["BUDGET_OVER_PLAN"]
    assert result["attention_items"][0]["severity"] == "ATTENTION"


def test_budget_pace_risk_when_not_over_plan():
    result = inbox(
        plan_vs_actual=[{"category": "Food", "currency": "COP", "planned": 100, "actual": 80, "variance": -20, "variance_pct": -20, "status": "UNDER_PLAN"}],
        budget_burn=[{"category": "Food", "currency": "COP", "budget": 100, "spent": 80, "projected_close": 160, "pace_status": "OVER_PACE", "budget_status": "WITHIN_BUDGET"}],
    )
    assert types(result) == ["BUDGET_PACE_RISK"]
    assert result["attention_items"][0]["severity"] == "WATCH"


def test_data_limitation_consolidates_and_partial_cash_does_not_shortfall():
    result = inbox(
        projection=projection(status="PARTIAL", reason="NOT_ENOUGH_HISTORY", projected_balance=-999),
        data_confidence={"level": "LOW", "reasons": ["No hay transacciones", "No hay presupuestos"], "inputs": {}},
    )
    assert types(result) == ["DATA_LIMITATION"]
    assert result["status"] == "PARTIAL"
    assert len(result["attention_items"][0]["evidence"]) == 2


def test_future_events_go_to_timeline_without_attention_and_past_expected_not_overdue():
    events = [
        {"id": "future", "date": "2026-09-25", "amount": 100, "currency": "COP", "direction": "OUTFLOW", "certainty": "EXPECTED", "confidence": "HIGH", "source": "recurrence_pattern", "source_id": "r1", "event_type": "RECURRING", "label": "Rent"},
        {"id": "past", "date": "2026-09-01", "amount": 100, "currency": "COP", "direction": "OUTFLOW", "certainty": "EXPECTED", "confidence": "HIGH", "source": "recurrence_pattern", "source_id": "r2", "event_type": "RECURRING", "label": "Old"},
    ]
    result = inbox(financial_events=events)
    assert result["status"] == "EMPTY"
    assert result["attention_items"] == []
    assert [item["id"] for item in result["timeline"]] == ["timeline:event:future"]


def test_currency_isolation_and_missing_reserve_is_not_limitation():
    result = inbox(
        safe_to_spend=None,
        plan_vs_actual=[{"category": "Food", "currency": "USD", "planned": 100, "actual": 150, "variance": 50, "variance_pct": 50, "status": "OVER_PLAN"}],
        financial_events=[{"id": "usd", "date": "2026-09-25", "amount": 100, "currency": "USD", "direction": "OUTFLOW", "certainty": "EXPECTED", "confidence": "HIGH", "source": "recurrence_pattern", "source_id": "r1", "event_type": "RECURRING", "label": "USD"}],
    )
    assert result["status"] == "EMPTY"
    assert result["attention_items"] == []
    assert result["timeline"] == []


def test_determinism_and_no_mutation():
    events = [{"id": "future", "date": "2026-09-25", "amount": 100, "currency": "COP", "direction": "OUTFLOW", "certainty": "EXPECTED", "confidence": "HIGH", "source": "recurrence_pattern", "source_id": "r1", "event_type": "RECURRING", "label": "Rent"}]
    args = {
        "projection": projection(projected_balance=-1),
        "financial_events": events,
    }
    before = deepcopy(args)
    first = inbox(**args)
    second = inbox(**args)
    assert first == second
    assert args == before
