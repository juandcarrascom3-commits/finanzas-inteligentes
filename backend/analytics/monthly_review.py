"""Monthly review and planning engine."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from backend.analytics.understand import (
    get_budget_risks,
    get_cashflow_forecast,
    get_financial_changes,
    get_recurring_transactions,
    summarize_transactions,
)


def _month_range(period: str) -> Tuple[date, date]:
    year, month = [int(part) for part in period.split("-")]
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _previous_period(period: str) -> str:
    year, month = [int(part) for part in period.split("-")]
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def get_confirmed_recurring(stored_rules: List[Dict[str, Any]], detected: List[Dict[str, Any]]) -> Dict[str, Any]:
    confirmed = [rule for rule in stored_rules if rule.get("status") == "confirmed"]
    rejected_keys = {(rule.get("merchant"), round(float(rule.get("typical_amount", 0) or 0), 2)) for rule in stored_rules if rule.get("status") == "rejected"}
    possible = [
        item for item in detected
        if (item.get("merchant"), round(float(item.get("typical_amount", 0) or 0), 2)) not in rejected_keys
    ]
    return {"confirmed": confirmed, "detected": possible}


def get_budget_variances(transactions: List[Dict[str, Any]], budgets: List[Dict[str, Any]], period: str) -> List[Dict[str, Any]]:
    start, end = _month_range(period)
    summary = summarize_transactions(transactions, start, end)
    variances = []
    for budget in budgets:
        if not budget.get("is_active", 1):
            continue
        limit = float(budget.get("monthly_limit", 0) or 0)
        spent = summary["by_category"].get(budget["category"], 0.0)
        variance = spent - limit
        variances.append({
            "category": budget["category"],
            "budget": round(limit, 2),
            "spent": round(spent, 2),
            "variance": round(variance, 2),
            "variance_pct": round((variance / limit) * 100, 2) if limit > 0 else 0.0,
            "status": "over" if variance > 0 else "under",
            "source": budget.get("source", "MANUAL"),
        })
    return sorted(variances, key=lambda item: abs(item["variance"]), reverse=True)


def get_upcoming_obligations(confirmed_recurring: List[Dict[str, Any]], horizon_days: int = 35, today: Optional[date] = None) -> List[Dict[str, Any]]:
    today = today or date.today()
    horizon = today + timedelta(days=horizon_days)
    upcoming = []
    for rule in confirmed_recurring:
        next_expected = rule.get("next_expected")
        if not next_expected:
            continue
        try:
            next_date = datetime.fromisoformat(next_expected).date()
        except Exception:
            continue
        if today <= next_date <= horizon:
            upcoming.append({
                "merchant": rule["merchant"],
                "amount": float(rule.get("typical_amount", 0) or 0),
                "category": rule.get("category", "General"),
                "date": next_date.isoformat(),
                "source": rule.get("source", "DETECTED"),
            })
    return sorted(upcoming, key=lambda item: item["date"])


def get_monthly_action_items(review: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions = []
    for variance in review["budget_variances"]:
        if variance["variance_pct"] > 10:
            actions.append({
                "type": "budget_overrun",
                "severity": "high" if variance["variance_pct"] > 25 else "medium",
                "reason": f"{variance['category']} está {variance['variance_pct']}% sobre presupuesto.",
                "reference": {"category": variance["category"], "variance": variance["variance"]},
                "action": "Revisar presupuesto o recortar gasto variable",
            })
    for item in review["recurring"]["detected"][:5]:
        if item.get("confidence") == "possible":
            actions.append({
                "type": "recurring_candidate",
                "severity": "low",
                "reason": f"Confirmar si {item['merchant']} es recurrente.",
                "reference": {"merchant": item["merchant"], "amount": item["typical_amount"]},
                "action": "Confirmar o rechazar recurrente",
            })
    if review["forecast"]["projected_balance"] < 0:
        actions.append({
            "type": "cashflow_negative",
            "severity": "high",
            "reason": "El saldo proyectado de corto plazo es negativo.",
            "reference": {"projected_balance": review["forecast"]["projected_balance"]},
            "action": "Revisar entradas previstas y gastos próximos",
        })
    return actions


def get_monthly_review(
    transactions: List[Dict[str, Any]],
    accounts: List[Dict[str, Any]],
    budgets: List[Dict[str, Any]],
    stored_recurring: List[Dict[str, Any]],
    reconciliation: Dict[str, Any],
    period: Optional[str] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    today = today or date.today()
    period = period or today.strftime("%Y-%m")
    start, end = _month_range(period)
    previous = _previous_period(period)
    previous_start, previous_end = _month_range(previous)
    summary = summarize_transactions(transactions, start, end)
    previous_summary = summarize_transactions(transactions, previous_start, previous_end)
    detected = get_recurring_transactions(transactions, today=today)
    recurring = get_confirmed_recurring(stored_recurring, detected)
    budget_variances = get_budget_variances(transactions, budgets, period)
    budget_burn = get_budget_risks(transactions, budgets, today=today)
    forecast = get_cashflow_forecast(accounts, transactions, recurring["confirmed"] or recurring["detected"], today=today)
    review = {
        "period": period,
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "facts": {
            "income": summary["income"],
            "expenses": summary["expenses"],
            "cashflow": summary["cashflow"],
            "savings_rate_pct": summary["savings_rate_pct"],
            "available_net_worth": round(sum(float(account.get("current_balance", 0) or 0) for account in accounts), 2),
            "previous_income": previous_summary["income"],
            "previous_expenses": previous_summary["expenses"],
            "previous_cashflow": previous_summary["cashflow"],
        },
        "comparison": get_financial_changes(transactions, "current_month", today=end),
        "budget_variances": budget_variances,
        "recurring": recurring,
        "upcoming_obligations": get_upcoming_obligations(recurring["confirmed"], today=today),
        "forecast": forecast,
        "budget_burn": budget_burn,
        "reconciliation": reconciliation,
    }
    review["action_items"] = get_monthly_action_items(review)
    return review
