"""
Personal Finance Projections & Budgeting Checklist Model
Calculates:
- 3, 6, and 12-month future cash flow projections (Income, Expenses, Net Savings)
- Liquid Runway (emergency reserve coverage in months)
- Semaphoric status (Green, Orange, Red) for budget categories
"""

from typing import List, Dict, Any

def calculate_budget_projections(
    monthly_income: float,
    monthly_expenses: float,
    current_cash_reserves: float,
    discretionary_spending: float = 0.0,
    expected_growth_rate: float = 0.02
) -> Dict[str, Any]:
    """
    Projects cumulative capital accumulation and cash flow dynamics over 3, 6, and 12 months.
    """
    monthly_net_savings = monthly_income - monthly_expenses
    runway_months = round(current_cash_reserves / monthly_expenses, 1) if monthly_expenses > 0 else 999.0

    projections = []
    accumulated_net = 0.0
    for month in range(1, 13):
        # Apply small inflation/growth factor
        month_income = monthly_income * ((1.0 + expected_growth_rate / 12) ** month)
        month_expenses = monthly_expenses * ((1.0 + 0.03 / 12) ** month) # 3% annual expense drift
        net = month_income - month_expenses
        accumulated_net += net
        projections.append({
            "month": month,
            "projected_income": round(month_income, 2),
            "projected_expenses": round(month_expenses, 2),
            "monthly_net": round(net, 2),
            "cumulative_savings": round(accumulated_net, 2),
            "total_liquidity": round(current_cash_reserves + accumulated_net, 2)
        })

    # Semaphoric Health Checklist
    checklist = []

    # Check 1: Savings Rate >= 30%
    savings_rate = ((monthly_income - monthly_expenses) / monthly_income * 100) if monthly_income > 0 else 0
    if savings_rate >= 30.0:
        s_status = "GREEN"
        s_msg = f"Excelente tasa de ahorro ({round(savings_rate, 1)}% >= 30%). Objetivo de acumulación óptimo."
    elif savings_rate >= 15.0:
        s_status = "ORANGE"
        s_msg = f"Tasa de ahorro moderada ({round(savings_rate, 1)}%). Recomendable optimizar gastos fijos."
    else:
        s_status = "RED"
        s_msg = f"Tasa de ahorro baja ({round(savings_rate, 1)}% < 15%). Capacidad de inversión comprometida."

    checklist.append({
        "id": "savings_rate",
        "title": "Tasa de Ahorro Mensual",
        "value": f"{round(savings_rate, 1)}%",
        "status": s_status,
        "message": s_msg
    })

    # Check 2: Emergency Runway (Months of Expenses)
    if runway_months >= 6.0:
        r_status = "GREEN"
        r_msg = f"Fondo de emergencia robusto ({runway_months} meses). Cobertura adecuada ante contingencias."
    elif runway_months >= 3.0:
        r_status = "ORANGE"
        r_msg = f"Fondo de emergencia en nivel intermedio ({runway_months} meses). Meta mínima recomendada: 6 meses."
    else:
        r_status = "RED"
        r_msg = f"Fondo de emergencia crítico ({runway_months} meses < 3 meses). Priorizar liquidez antes de activos de riesgo."

    checklist.append({
        "id": "emergency_runway",
        "title": "Colchón de Seguridad (Runway)",
        "value": f"{runway_months} meses",
        "status": r_status,
        "message": r_msg
    })

    # Check 3: Discretionary Spending Ratio
    disc_ratio = (discretionary_spending / monthly_expenses * 100) if monthly_expenses > 0 else 0
    if disc_ratio <= 25.0:
        d_status = "GREEN"
        d_msg = f"Gasto discrecional controlado ({round(disc_ratio, 1)}% del gasto total)."
    elif disc_ratio <= 40.0:
        d_status = "ORANGE"
        d_msg = f"Gasto discrecional elevado ({round(disc_ratio, 1)}%). Oportunidad de recorte táctico."
    else:
        d_status = "RED"
        d_msg = f"Gasto discrecional excesivo ({round(disc_ratio, 1)}% > 40%). Riesgo de fuga de capital."

    checklist.append({
        "id": "discretionary_ratio",
        "title": "Control de Gasto Discrecional",
        "value": f"{round(disc_ratio, 1)}%",
        "status": d_status,
        "message": d_msg
    })

    # Check 4: Cash Flow Balance
    if monthly_net_savings > 0:
        c_status = "GREEN"
        c_msg = f"Flujo de caja mensual positivo (+${round(monthly_net_savings, 2)} USD)."
    elif monthly_net_savings == 0:
        c_status = "ORANGE"
        c_msg = "Flujo de caja neutral. No se genera superávit operativo."
    else:
        c_status = "RED"
        c_msg = f"Déficit operativo mensual (-${round(abs(monthly_net_savings), 2)} USD). Alerta roja de consumo."

    checklist.append({
        "id": "cashflow_balance",
        "title": "Balance Operativo de Flujo de Caja",
        "value": f"${round(monthly_net_savings, 2)} USD",
        "status": c_status,
        "message": c_msg
    })

    return {
        "monthly_net_savings": round(monthly_net_savings, 2),
        "runway_months": runway_months,
        "projections_summary": {
            "3_months_net": round(sum(p["monthly_net"] for p in projections[:3]), 2),
            "6_months_net": round(sum(p["monthly_net"] for p in projections[:6]), 2),
            "12_months_net": round(sum(p["monthly_net"] for p in projections[:12]), 2)
        },
        "monthly_timeline": projections,
        "checklist": checklist
    }
