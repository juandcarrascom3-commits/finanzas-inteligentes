"""Deterministic personal finance analysis services."""

import re
import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


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


def summarize_transactions(transactions: List[Dict[str, Any]], start: date, end: date) -> Dict[str, Any]:
    selected = [tx for tx in transactions if _in_range(tx, start, end)]
    income = sum(float(tx.get("amount", 0) or 0) for tx in selected if float(tx.get("amount", 0) or 0) > 0)
    expenses = sum(abs(float(tx.get("amount", 0) or 0)) for tx in selected if float(tx.get("amount", 0) or 0) < 0)
    by_category: Dict[str, float] = defaultdict(float)
    for tx in selected:
        amount = float(tx.get("amount", 0) or 0)
        if amount < 0:
            by_category[tx.get("category") or "General"] += abs(amount)
    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "cashflow": round(income - expenses, 2),
        "savings_rate_pct": round(((income - expenses) / income) * 100, 2) if income > 0 else 0.0,
        "by_category": dict(by_category),
        "transactions": selected,
    }


def get_financial_changes(transactions: List[Dict[str, Any]], period: str = "current_month", today: Optional[date] = None) -> Dict[str, Any]:
    start, end, previous_start, previous_end = _period_range(period, today)
    current = summarize_transactions(transactions, start, end)
    previous = summarize_transactions(transactions, previous_start, previous_end)
    category_delta = []
    all_categories = set(current["by_category"]) | set(previous["by_category"])
    for category in all_categories:
        now_value = current["by_category"].get(category, 0.0)
        before_value = previous["by_category"].get(category, 0.0)
        category_delta.append({"category": category, "delta": round(now_value - before_value, 2), "current": round(now_value, 2), "previous": round(before_value, 2)})
    category_delta.sort(key=lambda item: abs(item["delta"]), reverse=True)
    impactful = sorted(current["transactions"], key=lambda tx: abs(float(tx.get("amount", 0) or 0)), reverse=True)[:10]
    return {
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
    elapsed_pct = today.day / 31 * 100
    risks = []
    current = summarize_transactions(transactions, start, today)
    for budget in budgets:
        limit = float(budget.get("monthly_limit", 0) or 0)
        if limit <= 0:
            continue
        spent = current["by_category"].get(budget["category"], 0.0)
        pct = (spent / limit) * 100
        projected = spent / max(today.day, 1) * 31
        if pct >= 100:
            status = "probably_exceeded"
        elif pct > elapsed_pct + 15 or projected > limit:
            status = "at_risk"
        else:
            status = "on_track"
        risks.append({
            "category": budget["category"],
            "budget": round(limit, 2),
            "spent": round(spent, 2),
            "remaining": round(limit - spent, 2),
            "spent_pct": round(pct, 2),
            "month_elapsed_pct": round(elapsed_pct, 2),
            "projected_close": round(projected, 2),
            "status": status,
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
