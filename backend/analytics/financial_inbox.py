"""Deterministic financial inbox composition from canonical analytics."""

import hashlib
from datetime import date
from typing import Any, Dict, List, Optional


SEVERITY_ORDER = {"URGENT": 0, "ATTENTION": 1, "WATCH": 2, "INFO": 3}
LIMITATION_STATUSES = {"PARTIAL", "PARTIAL_DATA", "STALE", "NOT_ENOUGH_HISTORY", "INSUFFICIENT_DATA"}


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _item(
    item_type: str,
    severity: str,
    title: str,
    summary: str,
    effective_date: str,
    source: str,
    source_id: Optional[str] = None,
    currency: Optional[str] = None,
    confidence: Optional[str] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
    actions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "id": f"{item_type}:{_stable_id(item_type, source, source_id or title, currency, effective_date)}",
        "type": item_type,
        "severity": severity,
        "title": title,
        "summary": summary,
        "effective_date": effective_date,
        "currency": currency,
        "source": source,
        "source_id": source_id,
        "confidence": confidence,
        "evidence": evidence or [],
        "actions": actions or [],
    }


def _same_cash_context(item: Dict[str, Any]) -> str:
    return f"{item.get('currency')}:{item.get('effective_date')}:{item.get('source_id') or 'cash'}"


def derive_attention_items(
    *,
    as_of: date,
    currency: str,
    projection: Dict[str, Any],
    safe_to_spend: Optional[Dict[str, Any]],
    plan_vs_actual: List[Dict[str, Any]],
    budget_burn: List[Dict[str, Any]],
    data_confidence: Dict[str, Any],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    as_of_iso = as_of.isoformat()
    projected_shortfall = False

    if projection.get("currency") == currency and projection.get("status") == "READY" and projection.get("projected_balance") is not None and projection["projected_balance"] < 0:
        projected_shortfall = True
        items.append(_item(
            "PROJECTED_CASH_SHORTFALL",
            "URGENT",
            "Caja proyectada negativa",
            "La proyección canónica de caja termina por debajo de cero.",
            projection.get("horizon_end") or as_of_iso,
            "cash_projection",
            f"{currency}:{projection.get('horizon_days')}",
            currency,
            projection.get("confidence"),
            [
                {"metric": "projected_balance", "value": projection.get("projected_balance")},
                {"metric": "horizon_days", "value": projection.get("horizon_days")},
                {"metric": "confidence_reasons", "value": projection.get("confidence_reasons", [])},
            ],
            ["VIEW_DETAILS", "OPEN_SCENARIO"],
        ))

    if (
        not projected_shortfall
        and safe_to_spend
        and safe_to_spend.get("currency") == currency
        and safe_to_spend.get("status") == "READY"
        and safe_to_spend.get("safe_to_spend") is not None
        and safe_to_spend["safe_to_spend"] < 0
    ):
        items.append(_item(
            "SAFE_TO_SPEND_NEGATIVE",
            "ATTENTION",
            "Safe-to-Spend negativo",
            "El cálculo conservador de dinero disponible para gastar está por debajo de cero.",
            projection.get("horizon_end") or as_of_iso,
            "safe_to_spend",
            f"{currency}:{projection.get('horizon_days')}",
            currency,
            projection.get("confidence"),
            [
                {"metric": "safe_to_spend", "value": safe_to_spend.get("safe_to_spend")},
                {"metric": "reserve_floor", "value": safe_to_spend.get("reserve_floor")},
            ],
            ["VIEW_DETAILS", "OPEN_SCENARIO"],
        ))

    over_plan_keys = set()
    for row in plan_vs_actual:
        if row.get("currency") != currency or row.get("status") != "OVER_PLAN":
            continue
        source_id = f"{row.get('category')}:{row.get('currency')}"
        over_plan_keys.add(source_id)
        items.append(_item(
            "BUDGET_OVER_PLAN",
            "ATTENTION",
            f"Presupuesto excedido: {row.get('category')}",
            "El resultado canónico de plan vs actual está por encima del presupuesto.",
            as_of_iso,
            "plan_vs_actual",
            source_id,
            currency,
            None,
            [{"metric": key, "value": row.get(key)} for key in ["planned", "actual", "variance", "variance_pct", "status"]],
            ["REVIEW_BUDGET"],
        ))

    for row in budget_burn:
        if row.get("currency") != currency or row.get("pace_status") != "OVER_PACE" or row.get("budget_status") == "EXCEEDED":
            continue
        source_id = f"{row.get('category')}:{row.get('currency')}"
        if source_id in over_plan_keys:
            continue
        items.append(_item(
            "BUDGET_PACE_RISK",
            "WATCH",
            f"Ritmo alto: {row.get('category')}",
            "El ritmo canónico de gasto va por encima del ritmo esperado.",
            as_of_iso,
            "budget_burn",
            source_id,
            currency,
            None,
            [{"metric": key, "value": row.get(key)} for key in ["budget", "spent", "projected_close", "pace_status", "budget_status"]],
            ["REVIEW_BUDGET"],
        ))

    limitation_candidates = []
    if projection.get("status") in LIMITATION_STATUSES or projection.get("reason") in LIMITATION_STATUSES:
        limitation_candidates.append(("cash_projection", projection.get("status"), projection.get("reason")))
    level = data_confidence.get("level")
    if level == "LOW":
        limitation_candidates.append(("data_confidence", level, "; ".join(data_confidence.get("reasons", []))))
    if limitation_candidates:
        source, status, reason = limitation_candidates[0]
        items.append(_item(
            "DATA_LIMITATION",
            "WATCH",
            "Datos incompletos para evaluar todo",
            str(reason or status or "Limitación de datos"),
            as_of_iso,
            source,
            source,
            currency,
            level,
            [{"metric": s, "status": st, "reason": rs} for s, st, rs in limitation_candidates],
            ["REVIEW_DATA"],
        ))

    return items


def deduplicate_attention_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    strongest_by_family: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if item["type"] in {"PROJECTED_CASH_SHORTFALL", "SAFE_TO_SPEND_NEGATIVE"}:
            family = f"cash:{_same_cash_context(item)}"
        elif item["type"] in {"BUDGET_OVER_PLAN", "BUDGET_PACE_RISK"}:
            family = f"budget:{item.get('source_id')}"
        elif item["type"] == "DATA_LIMITATION":
            family = f"data:{item.get('source_id')}"
        else:
            family = item["id"]
        current = strongest_by_family.get(family)
        if current is None or SEVERITY_ORDER[item["severity"]] < SEVERITY_ORDER[current["severity"]]:
            strongest_by_family[family] = item
    return list(strongest_by_family.values())


def sort_attention_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: (SEVERITY_ORDER.get(item["severity"], 99), item.get("effective_date") or "", item["id"]))


def build_timeline(attention_items: List[Dict[str, Any]], financial_events: List[Dict[str, Any]], currency: str, as_of: date) -> List[Dict[str, Any]]:
    now_items = [
        {
            "id": f"timeline:{item['id']}",
            "date": as_of.isoformat(),
            "temporal_relation": "NOW",
            "type": item["type"],
            "title": item["title"],
            "summary": item["summary"],
            "currency": item.get("currency"),
            "confidence": item.get("confidence"),
            "source": item["source"],
            "source_id": item.get("source_id"),
        }
        for item in attention_items
    ]
    future_items = []
    for event in financial_events:
        if event.get("currency") != currency:
            continue
        try:
            event_date = date.fromisoformat(str(event.get("date"))[:10])
        except ValueError:
            continue
        if event_date <= as_of:
            continue
        future_items.append({
            "id": f"timeline:event:{event.get('id')}",
            "date": event_date.isoformat(),
            "temporal_relation": "FUTURE",
            "type": event.get("event_type") or "FINANCIAL_EVENT",
            "title": event.get("label") or "Evento financiero",
            "summary": f"{event.get('direction')} · {event.get('certainty')}",
            "amount": event.get("amount"),
            "currency": event.get("currency"),
            "certainty": event.get("certainty"),
            "confidence": event.get("confidence"),
            "source": event.get("source"),
            "source_id": event.get("source_id"),
        })
    future_items.sort(key=lambda item: (item["date"], item["id"]))
    return now_items + future_items


def compose_financial_inbox(
    *,
    as_of: date,
    currency: str,
    horizon_days: int,
    projection: Dict[str, Any],
    safe_to_spend: Optional[Dict[str, Any]],
    plan_vs_actual: List[Dict[str, Any]],
    budget_burn: List[Dict[str, Any]],
    data_confidence: Dict[str, Any],
    financial_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    items = sort_attention_items(deduplicate_attention_items(derive_attention_items(
        as_of=as_of,
        currency=currency,
        projection=projection,
        safe_to_spend=safe_to_spend,
        plan_vs_actual=plan_vs_actual,
        budget_burn=budget_burn,
        data_confidence=data_confidence,
    )))
    timeline = build_timeline(items, financial_events, currency, as_of)
    summary = {
        "urgent_count": sum(1 for item in items if item["severity"] == "URGENT"),
        "attention_count": sum(1 for item in items if item["severity"] == "ATTENTION"),
        "watch_count": sum(1 for item in items if item["severity"] == "WATCH"),
    }
    status = "PARTIAL" if any(item["type"] == "DATA_LIMITATION" for item in items) else "READY" if items else "EMPTY"
    return {
        "as_of": as_of.isoformat(),
        "currency": currency,
        "horizon_days": horizon_days,
        "status": status,
        "attention_items": items,
        "summary": summary,
        "timeline": timeline,
        "assumptions": {"no_fx": True, "expected_events_are_not_overdue": True, "scenario_data_excluded": True},
    }
