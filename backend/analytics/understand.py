"""Deterministic personal finance analysis services."""

import re
import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

BUDGET_PACE_TOLERANCE = 0.10


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _period_range(period: str, today: Optional[date] = None) -> Tuple[date, date, date, date]:
    today = today or date.today()
    if period == "previous_month":
        first_current = today.replace(day=1)
        end = first_current - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "last_30_days":
        end = today
        start = today - timedelta(days=29)
    else:
        start = today.replace(day=1)
        end = today
        previous_month = 12 if today.month == 1 else today.month - 1
        previous_year = today.year - 1 if today.month == 1 else today.year
        previous_last_day = calendar.monthrange(previous_year, previous_month)[1]
        previous_start = date(previous_year, previous_month, 1)
        previous_end = date(previous_year, previous_month, min(today.day, previous_last_day))
        return start, end, previous_start, previous_end
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    return start, end, previous_start, previous_end


def _in_range(tx: Dict[str, Any], start: date, end: date) -> bool:
    try:
        tx_date = _parse_date(tx["date"])
    except Exception:
        return False
    return start <= tx_date <= end


def _flow_type(tx: Dict[str, Any]) -> Optional[str]:
    value = tx.get("flow_type")
    return str(value).upper() if value else None


def _is_transfer(tx: Dict[str, Any]) -> bool:
    return _flow_type(tx) == "TRANSFER"


def _is_income(tx: Dict[str, Any]) -> bool:
    amount = float(tx.get("amount", 0) or 0)
    flow_type = _flow_type(tx)
    if flow_type:
        return flow_type == "INCOME" and amount > 0
    return amount > 0


def _is_expense(tx: Dict[str, Any]) -> bool:
    amount = float(tx.get("amount", 0) or 0)
    flow_type = _flow_type(tx)
    if flow_type:
        return flow_type == "EXPENSE" and amount < 0
    return amount < 0


def _savings_rate_state(income: float, cashflow: float) -> Dict[str, Any]:
    if income <= 0:
        return {"value": None, "value_pct": None, "evaluability": "UNEVALUABLE", "reason": "NO_INCOME"}
    value = cashflow / income
    return {"value": round(value, 6), "value_pct": round(value * 100, 2), "evaluability": "EVALUABLE", "reason": None}


def _savings_rate_change(current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    if current.get("evaluability") != "EVALUABLE" or previous.get("evaluability") != "EVALUABLE":
        return {"delta_pp": None, "relative_delta_pct": None}
    current_pct = float(current.get("value_pct") or 0)
    previous_pct = float(previous.get("value_pct") or 0)
    delta_pp = round(current_pct - previous_pct, 2)
    return {
        "delta_pp": delta_pp,
        "relative_delta_pct": round(delta_pp / abs(previous_pct) * 100, 2) if previous_pct != 0 else None,
    }


def summarize_transactions(transactions: List[Dict[str, Any]], start: date, end: date) -> Dict[str, Any]:
    selected = [tx for tx in transactions if _in_range(tx, start, end)]
    income = sum(float(tx.get("amount", 0) or 0) for tx in selected if _is_income(tx))
    expenses = sum(abs(float(tx.get("amount", 0) or 0)) for tx in selected if _is_expense(tx))
    by_category: Dict[str, float] = defaultdict(float)
    for tx in selected:
        amount = float(tx.get("amount", 0) or 0)
        if _is_expense(tx):
            by_category[tx.get("category") or "General"] += abs(amount)
    cashflow = income - expenses
    savings_rate = _savings_rate_state(income, cashflow)
    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "cashflow": round(cashflow, 2),
        "savings_rate_pct": round(((income - expenses) / income) * 100, 2) if income > 0 else 0.0,
        "savings_rate": savings_rate,
        "by_category": dict(by_category),
        "transactions": selected,
    }


def _tx_currency(tx: Dict[str, Any]) -> str:
    return str(tx.get("currency") or "UNKNOWN").upper()


def _delta_metric(current: float, previous: float) -> Dict[str, Any]:
    delta = round(current - previous, 2)
    return {
        "current": round(current, 2),
        "previous": round(previous, 2),
        "delta": delta,
        "delta_pct": round(delta / abs(previous) * 100, 2) if previous != 0 else None,
    }


def _summaries_by_currency(transactions: List[Dict[str, Any]], start: date, end: date) -> Dict[str, Dict[str, Any]]:
    currencies = sorted({_tx_currency(tx) for tx in transactions if _in_range(tx, start, end)})
    return {currency: summarize_transactions([tx for tx in transactions if _tx_currency(tx) == currency], start, end) for currency in currencies}


def eligible_budget_spend(transactions: List[Dict[str, Any]], category: str, currency: str, start: date, end: date) -> float:
    expected_currency = (currency or "").upper()
    total = 0.0
    for tx in transactions:
        if not _in_range(tx, start, end):
            continue
        if not tx.get("currency") or _tx_currency(tx) != expected_currency:
            continue
        if (tx.get("category") or "General") != category:
            continue
        if _is_transfer(tx) or not _is_expense(tx):
            continue
        total += abs(float(tx.get("amount", 0) or 0))
    return round(total, 2)


def get_plan_vs_actual(transactions: List[Dict[str, Any]], budgets: List[Dict[str, Any]], start: date, end: date) -> List[Dict[str, Any]]:
    rows = []
    for budget in budgets:
        if not budget.get("is_active", 1):
            continue
        planned = float(budget.get("monthly_limit", 0) or 0)
        currency = (budget.get("currency") or "USD").upper()
        actual = eligible_budget_spend(transactions, budget["category"], currency, start, end)
        variance = round(actual - planned, 2)
        if actual < planned:
            status = "UNDER_PLAN"
        elif actual == planned:
            status = "ON_PLAN"
        else:
            status = "OVER_PLAN"
        rows.append({
            "objective_type": "EXPENSE_CAP",
            "category": budget["category"],
            "currency": currency,
            "planned": round(planned, 2),
            "actual": round(actual, 2),
            "variance": variance,
            "variance_pct": round(variance / abs(planned) * 100, 2) if planned != 0 else None,
            "status": status,
            "source": budget.get("source", "MANUAL"),
        })
    return sorted(rows, key=lambda item: abs(item["variance"]), reverse=True)


def explain_financial_changes(what_changed: Dict[str, Any]) -> Dict[str, Any]:
    primary = what_changed.get("primary_currency")
    metrics = what_changed.get("metrics", {})
    contributors = what_changed.get("category_contributors", [])
    reasons = []
    cashflow = metrics.get("net_cash_flow", {})
    expenses = metrics.get("expenses", {})
    income = metrics.get("income", {})
    if cashflow.get("delta", 0) < 0:
        reasons.append("El cashflow empeoró frente al periodo comparable.")
    elif cashflow.get("delta", 0) > 0:
        reasons.append("El cashflow mejoró frente al periodo comparable.")
    else:
        reasons.append("El cashflow se mantuvo estable frente al periodo comparable.")
    if expenses.get("delta", 0) > 0:
        reasons.append("Los gastos aumentaron.")
    if income.get("delta", 0) < 0:
        reasons.append("Los ingresos bajaron.")
    if contributors:
        top = contributors[0]
        reasons.append(f"La categoría con mayor cambio fue {top['category']}.")
    return {
        "metric": "net_cash_flow",
        "currency": primary,
        "current": cashflow.get("current", 0),
        "previous": cashflow.get("previous", 0),
        "delta": cashflow.get("delta", 0),
        "contributors": contributors[:5],
        "data_quality": what_changed.get("data_confidence", {}),
        "reasons": reasons,
    }


def get_financial_changes(transactions: List[Dict[str, Any]], period: str = "current_month", today: Optional[date] = None) -> Dict[str, Any]:
    start, end, previous_start, previous_end = _period_range(period, today)
    current = summarize_transactions(transactions, start, end)
    previous = summarize_transactions(transactions, previous_start, previous_end)
    current_by_currency = _summaries_by_currency(transactions, start, end)
    previous_by_currency = _summaries_by_currency(transactions, previous_start, previous_end)
    all_currencies = sorted(set(current_by_currency) | set(previous_by_currency))
    by_currency = {}
    for currency in all_currencies:
        now = current_by_currency.get(currency, summarize_transactions([], start, end))
        before = previous_by_currency.get(currency, summarize_transactions([], previous_start, previous_end))
        category_contributors = []
        for category in set(now["by_category"]) | set(before["by_category"]):
            now_value = now["by_category"].get(category, 0.0)
            before_value = before["by_category"].get(category, 0.0)
            category_contributors.append({
                "category": category or "General",
                "currency": currency,
                "current": round(now_value, 2),
                "previous": round(before_value, 2),
                "delta": round(now_value - before_value, 2),
            })
        category_contributors.sort(key=lambda item: abs(item["delta"]), reverse=True)
        by_currency[currency] = {
            "currency": currency,
            "income": _delta_metric(now["income"], before["income"]),
            "expenses": _delta_metric(now["expenses"], before["expenses"]),
            "net_cash_flow": _delta_metric(now["cashflow"], before["cashflow"]),
            "savings_rate": _delta_metric(now["savings_rate_pct"], before["savings_rate_pct"]),
            "savings_rate_semantics": {
                "current": now["savings_rate"],
                "previous": before["savings_rate"],
                **_savings_rate_change(now["savings_rate"], before["savings_rate"]),
            },
            "category_contributors": category_contributors[:8],
        }
    primary_currency = all_currencies[0] if len(all_currencies) == 1 else None
    category_delta = []
    all_categories = set(current["by_category"]) | set(previous["by_category"])
    for category in all_categories:
        now_value = current["by_category"].get(category, 0.0)
        before_value = previous["by_category"].get(category, 0.0)
        category_delta.append({"category": category, "delta": round(now_value - before_value, 2), "current": round(now_value, 2), "previous": round(before_value, 2)})
    category_delta.sort(key=lambda item: abs(item["delta"]), reverse=True)
    impactful = sorted(current["transactions"], key=lambda tx: abs(float(tx.get("amount", 0) or 0)), reverse=True)[:10]
    result = {
        "period": period,
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "previous_range": {"from": previous_start.isoformat(), "to": previous_end.isoformat()},
        "facts": {
            "income": current["income"],
            "expenses": current["expenses"],
            "cashflow": current["cashflow"],
            "savings_rate_pct": current["savings_rate_pct"],
        },
        "variation": {
            "income": round(current["income"] - previous["income"], 2),
            "expenses": round(current["expenses"] - previous["expenses"], 2),
            "cashflow": round(current["cashflow"] - previous["cashflow"], 2),
            "savings_rate_pct": round(current["savings_rate_pct"] - previous["savings_rate_pct"], 2),
        },
        "category_changes": category_delta[:8],
        "largest_transactions": impactful,
        "interpretation": [
            "Gastos subieron frente al periodo anterior." if current["expenses"] > previous["expenses"] else "Gastos bajaron o se mantuvieron frente al periodo anterior.",
            "Cashflow positivo." if current["cashflow"] >= 0 else "Cashflow negativo.",
        ],
        "by_currency": by_currency,
        "primary_currency": primary_currency,
        "metrics": by_currency.get(primary_currency, {}) if primary_currency else {},
        "category_contributors": by_currency.get(primary_currency, {}).get("category_contributors", []) if primary_currency else [],
        "mixed_currencies": len(all_currencies) > 1,
    }
    result["explain"] = explain_financial_changes(result)
    return result


def get_data_confidence(
    transactions: List[Dict[str, Any]],
    budgets: Optional[List[Dict[str, Any]]] = None,
    recurring: Optional[List[Dict[str, Any]]] = None,
    reconciliation: Optional[Dict[str, Any]] = None,
    sync_state: Optional[Dict[str, Any]] = None,
    wealth_quality: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    budgets = budgets or []
    recurring = recurring or []
    reconciliation = reconciliation or {}
    sync_state = sync_state or {}
    reasons = []
    critical_missing = False
    medium_issue = False
    if not transactions:
        critical_missing = True
        reasons.append("No hay transacciones persistidas para evaluar cashflow.")
    if any(not tx.get("date") or tx.get("amount") is None or not tx.get("currency") for tx in transactions):
        critical_missing = True
        reasons.append("Hay transacciones sin fecha, monto o moneda.")
    unmapped_accounts = reconciliation.get("unmapped_accounts") or []
    unmapped_categories = reconciliation.get("unmapped_categories") or []
    if unmapped_accounts or unmapped_categories:
        medium_issue = True
        reasons.append("Existen mappings pendientes de cuentas o categorías.")
    if not budgets:
        medium_issue = True
        reasons.append("No hay presupuestos configurados para comparar desviaciones.")
    if not recurring:
        medium_issue = True
        reasons.append("No hay recurrentes confirmados/detectados suficientes.")
    if sync_state.get("status") in {"AUTH_ERROR", "NETWORK_ERROR", "RATE_LIMITED", "PARTIAL"}:
        medium_issue = True
        reasons.append(f"Fuente externa relevante en estado {sync_state.get('status')}.")
    if wealth_quality and wealth_quality.get("issues"):
        medium_issue = True
        reasons.append("Wealth tiene observaciones de calidad de datos.")
    level = "LOW" if critical_missing else "MEDIUM" if medium_issue else "HIGH"
    if not reasons:
        reasons.append("Inputs críticos presentes y sin brechas relevantes detectadas.")
    return {
        "level": level,
        "reasons": reasons,
        "inputs": {
            "transactions": len(transactions),
            "budgets": len(budgets),
            "recurring": len(recurring),
            "unmapped_accounts": len(unmapped_accounts),
            "unmapped_categories": len(unmapped_categories),
            "sync_status": sync_state.get("status"),
        },
        "provenance": sorted({str(tx.get("source") or "UNKNOWN") for tx in transactions}),
    }


def build_analysis_export(
    period: str,
    what_changed: Dict[str, Any],
    recurring: List[Dict[str, Any]],
    budget_burn: List[Dict[str, Any]],
    monthly_review: Optional[Dict[str, Any]],
    wealth_summary: Optional[Dict[str, Any]],
    data_confidence: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sources": data_confidence.get("provenance", []),
        "cash_flow": what_changed.get("metrics", {}),
        "what_changed": {
            "range": what_changed.get("range"),
            "previous_range": what_changed.get("previous_range"),
            "primary_currency": what_changed.get("primary_currency"),
            "mixed_currencies": what_changed.get("mixed_currencies"),
            "by_currency": what_changed.get("by_currency", {}),
            "category_contributors": what_changed.get("category_contributors", []),
            "explain": what_changed.get("explain", {}),
        },
        "recurring": recurring,
        "budgets": budget_burn,
        "monthly_review": monthly_review,
        "wealth_summary": wealth_summary,
        "data_confidence": data_confidence,
    }


def _merchant_key(tx: Dict[str, Any]) -> str:
    text = f"{tx.get('description') or ''} {tx.get('category') or ''}".lower()
    text = re.sub(r"[^a-z0-9áéíóúñ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:80] or "sin descripcion"


def get_recurring_transactions(transactions: List[Dict[str, Any]], today: Optional[date] = None) -> List[Dict[str, Any]]:
    today = today or date.today()
    groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for tx in transactions:
        try:
            amount = float(tx.get("amount", 0) or 0)
            tx_date = _parse_date(tx["date"])
        except Exception:
            continue
        rounded_amount = round(amount / 5) * 5
        groups[(_merchant_key(tx), rounded_amount, tx.get("category") or "General", tx.get("account_id") or "")].append({**tx, "_date": tx_date})

    candidates = []
    for (merchant, rounded_amount, category, account_id), rows in groups.items():
        rows.sort(key=lambda tx: tx["_date"])
        if len(rows) < 2:
            continue
        gaps = [(rows[i]["_date"] - rows[i - 1]["_date"]).days for i in range(1, len(rows))]
        avg_gap = mean(gaps) if gaps else 0
        if 25 <= avg_gap <= 35:
            frequency = "monthly"
        elif 6 <= avg_gap <= 8:
            frequency = "weekly"
        elif 13 <= avg_gap <= 16:
            frequency = "biweekly"
        else:
            continue
        confidence = "probable" if len(rows) >= 3 else "possible"
        last_seen = rows[-1]["_date"]
        next_date = last_seen + timedelta(days=round(avg_gap)) if avg_gap else None
        amounts = [float(tx.get("amount", 0) or 0) for tx in rows]
        candidates.append({
            "merchant": merchant,
            "category": category,
            "account_id": account_id,
            "typical_amount": round(mean(amounts), 2),
            "frequency": frequency,
            "confidence": confidence,
            "occurrences": len(rows),
            "last_seen": last_seen.isoformat(),
            "next_expected": next_date.isoformat() if next_date and next_date >= today - timedelta(days=7) else None,
        })
    return sorted(candidates, key=lambda item: (item["confidence"] != "probable", item["next_expected"] or "9999"))


def get_budget_risks(transactions: List[Dict[str, Any]], budgets: List[Dict[str, Any]], today: Optional[date] = None) -> List[Dict[str, Any]]:
    today = today or date.today()
    start = today.replace(day=1)
    days_in_period = calendar.monthrange(today.year, today.month)[1]
    elapsed_days = today.day
    elapsed_pct = elapsed_days / days_in_period * 100
    risks = []
    for budget in budgets:
        if not budget.get("is_active", 1):
            continue
        limit = float(budget.get("monthly_limit", 0) or 0)
        if limit <= 0:
            continue
        currency = (budget.get("currency") or "USD").upper()
        spent = eligible_budget_spend(transactions, budget["category"], currency, start, today)
        pct = (spent / limit) * 100
        burn_ratio = spent / limit
        time_ratio = elapsed_days / days_in_period
        burn_pressure = burn_ratio / time_ratio if time_ratio > 0 else None
        projected = spent / max(elapsed_days, 1) * days_in_period
        budget_status = "WITHIN_BUDGET" if spent <= limit else "EXCEEDED"
        if burn_pressure is None:
            pace_status = "UNEVALUABLE"
        elif burn_pressure < 1 - BUDGET_PACE_TOLERANCE:
            pace_status = "UNDER_PACE"
        elif burn_pressure <= 1 + BUDGET_PACE_TOLERANCE:
            pace_status = "ON_PACE"
        else:
            pace_status = "OVER_PACE"
        if pct >= 100:
            status = "probably_exceeded"
        elif pace_status == "OVER_PACE" or projected > limit:
            status = "at_risk"
        else:
            status = "on_track"
        risks.append({
            "category": budget["category"],
            "currency": currency,
            "budget": round(limit, 2),
            "spent": round(spent, 2),
            "remaining": round(limit - spent, 2),
            "spent_pct": round(pct, 2),
            "month_elapsed_pct": round(elapsed_pct, 2),
            "projected_close": round(projected, 2),
            "status": status,
            "burn_ratio": round(burn_ratio, 4),
            "time_ratio": round(time_ratio, 4),
            "burn_pressure": round(burn_pressure, 4) if burn_pressure is not None else None,
            "pace_projection": round(projected, 2),
            "budget_status": budget_status,
            "pace_status": pace_status,
            "days_in_period": days_in_period,
            "elapsed_days": elapsed_days,
        })
    return risks


def get_cashflow_forecast(accounts: List[Dict[str, Any]], transactions: List[Dict[str, Any]], recurring: List[Dict[str, Any]], today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    horizon = today + timedelta(days=30)
    starting_balance = sum(float(account.get("current_balance", 0) or 0) for account in accounts if account.get("is_active", 1))
    recurring_in = 0.0
    recurring_out = 0.0
    for item in recurring:
        next_expected = item.get("next_expected")
        if not next_expected:
            continue
        try:
            next_date = _parse_date(next_expected)
        except Exception:
            continue
        if today <= next_date <= horizon:
            amount = float(item.get("typical_amount", 0) or 0)
            if amount >= 0:
                recurring_in += amount
            else:
                recurring_out += abs(amount)
    recent_start = today - timedelta(days=30)
    variable_expenses = [
        abs(float(tx.get("amount", 0) or 0))
        for tx in transactions
        if _in_range(tx, recent_start, today) and float(tx.get("amount", 0) or 0) < 0
    ]
    variable_avg = sum(variable_expenses) * 0.75
    projected_balance = starting_balance + recurring_in - recurring_out - variable_avg
    return {
        "range": {"from": today.isoformat(), "to": horizon.isoformat()},
        "starting_balance": round(starting_balance, 2),
        "expected_inflows": round(recurring_in, 2),
        "expected_outflows": round(recurring_out + variable_avg, 2),
        "projected_balance": round(projected_balance, 2),
        "uncertainty": "medium" if len(transactions) < 20 else "low",
        "components": {
            "recurring_inflows": round(recurring_in, 2),
            "recurring_outflows": round(recurring_out, 2),
            "variable_expense_estimate": round(variable_avg, 2),
        },
    }


def get_action_items(reconciliation: Dict[str, Any], budget_risks: List[Dict[str, Any]], recurring: List[Dict[str, Any]], sync_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    if sync_state.get("status") in {"AUTH_ERROR", "RATE_LIMITED", "INIT_SYNC_IN_PROGRESS", "NETWORK_ERROR"}:
        items.append({"type": "wallet_sync", "severity": "high", "title": "Wallet necesita atención", "why": sync_state.get("last_error") or sync_state.get("status"), "action": "Revisar conexión Wallet"})
    for account in reconciliation.get("unmapped_accounts", [])[:5]:
        items.append({"type": "account_mapping", "severity": "medium", "title": "Cuenta Wallet sin mapping", "why": account.get("external_name") or account.get("external_id"), "action": "Asignar cuenta Finance"})
    for category in reconciliation.get("unmapped_categories", [])[:5]:
        items.append({"type": "category_mapping", "severity": "medium", "title": "Categoria sin mapping", "why": f"{category['external_name']} aparece {category['count']} veces", "action": "Asignar categoria Finance"})
    for risk in budget_risks:
        if risk["status"] != "on_track":
            items.append({"type": "budget_risk", "severity": "medium", "title": "Presupuesto en riesgo", "why": f"{risk['category']} va en {risk['spent_pct']}%", "action": "Revisar gasto"})
    for item in recurring[:3]:
        if item["confidence"] == "possible":
            items.append({"type": "recurring_review", "severity": "low", "title": "Posible recurrente", "why": item["merchant"], "action": "Confirmar si es recurrente"})
    return items[:12]
