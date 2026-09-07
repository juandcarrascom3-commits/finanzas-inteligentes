"""
Finanzas Inteligentes: FastAPI REST API Backend
Exposes endpoints for:
- Top KPIs (Net Worth USD/COP, Savings Rate, TWR/MWR, Sharpe, Beta, Drawdown)
- Asset Allocation (Treemap/Sunburst data hierarchy)
- Temporal Evolution (Portfolio Growth vs S&P 500 Benchmark)
- Panorama (Projections & Semaphoric Budget Checklist)
- Asset Grid (Holdings & Watchlist)
- Investment Theses & Human Safety Guardrail Enforcement
- BudgetBakers Decoupled Ingestion & 25-request/day rate-limited client
- Executive Diagnostic Reports & Geopolitical Risk radar
"""

import os
import uuid
import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database.db_manager import DatabaseManager
from backend.analytics.metrics import (
    calculate_net_worth,
    calculate_savings_rate,
    calculate_twr,
    calculate_mwr_irr,
    calculate_portfolio_risk_metrics,
    USD_COP_EXCHANGE_RATE
)
from backend.analytics.projections import calculate_budget_projections
from backend.services.budgetbakers_client import BudgetBakersClient, DailyQuotaExceededError
from backend.services.guardrail_service import GuardrailService, TradeGuardrailBlockedError

app = FastAPI(
    title="Finanzas Inteligentes API",
    description="Backend for Wealth Management, Risk Analytics & Ingestion",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager()
bb_client = BudgetBakersClient(db_path=db.db_path)

# --- Pydantic Request Models ---
class ThesisInput(BaseModel):
    id: Optional[str] = None
    ticker: str
    thesis_text: str
    valuation_grade: int = Field(ge=1, le=5)
    timing_context: str
    safety_margin: float = Field(ge=0.0)
    criteria_details: Dict[str, bool]

class PurchaseSimulationInput(BaseModel):
    ticker: str
    target_amount_usd: float = Field(gt=0.0)

class MappingUpdateInput(BaseModel):
    mapping_id: str
    local_category: str
    is_active: bool

# --- API Endpoints ---

@app.get("/api/health")
def health():
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}

@app.get("/api/dashboard")
def get_dashboard_summary(exchange_rate: float = Query(USD_COP_EXCHANGE_RATE, ge=1000.0)):
    """Computes Top KPI Row, Allocation Treemap Hierarchy, and Benchmark curve."""
    assets = db.get_assets(include_watchlist=False)
    
    # 1. Top KPI: Net Worth
    net_worth_data = calculate_net_worth(assets, exchange_rate=exchange_rate)
    
    # 2. Top KPI: Monthly Savings Rate
    # Derive from transactions or standard monthly run-rate
    monthly_income = 6200.00
    monthly_expenses = 4040.00
    savings_data = calculate_savings_rate(monthly_income, monthly_expenses)

    # 3. Top KPI: Returns (TWR & MWR)
    subperiods = [0.038, 0.045, -0.018, 0.052, 0.021, 0.041] # Past 6 months
    twr = calculate_twr(subperiods)
    cash_flows = [(0.0, -120000.0), (0.25, -5000.0), (0.5, -5000.0), (1.0, 148520.0)]
    mwr = calculate_mwr_irr(cash_flows)

    # 4. Top KPI: Risk Metrics
    p_returns = [0.006, -0.003, 0.012, 0.004, -0.008, 0.009, -0.002, 0.007, 0.005, -0.004, 0.011, 0.003] * 5
    b_returns = [0.005, -0.004, 0.009, 0.003, -0.007, 0.007, -0.003, 0.006, 0.004, -0.003, 0.008, 0.002] * 5
    risk_metrics = calculate_portfolio_risk_metrics(p_returns, b_returns)

    # 5. Central Visual: Asset Allocation Hierarchy (Sunburst / Treemap data)
    allocation_by_type: Dict[str, Dict[str, Any]] = {}
    total_val = net_worth_data["net_worth_usd"]

    for a in assets:
        t = a["asset_type"]
        s = a["sector"]
        val_usd = float(a["quantity"]) * float(a["current_price"])
        if a["currency"] == "COP":
            val_usd = val_usd / exchange_rate

        if t not in allocation_by_type:
            allocation_by_type[t] = {"name": t, "value": 0.0, "children": {}}

        allocation_by_type[t]["value"] += val_usd
        if s not in allocation_by_type[t]["children"]:
            allocation_by_type[t]["children"][s] = {"name": s, "value": 0.0, "items": []}

        allocation_by_type[t]["children"][s]["value"] += val_usd
        allocation_by_type[t]["children"][s]["items"].append({
            "ticker": a["ticker"],
            "name": a["name"],
            "country": a["country"],
            "value_usd": round(val_usd, 2),
            "allocation_pct": round((val_usd / total_val * 100), 2) if total_val > 0 else 0
        })

    treemap_data = []
    for t_name, t_data in allocation_by_type.items():
        children_list = []
        for s_name, s_data in t_data["children"].items():
            children_list.append({
                "name": s_name,
                "value": round(s_data["value"], 2),
                "items": s_data["items"]
            })
        treemap_data.append({
            "name": t_name,
            "value": round(t_data["value"], 2),
            "percentage": round((t_data["value"] / total_val * 100), 1) if total_val > 0 else 0,
            "children": children_list
        })

    # 6. Central Visual: Temporal Evolution (12 Months Portfolio vs S&P 500)
    history_dates = [
        "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
        "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"
    ]
    p_cum = [100.0, 103.2, 106.5, 104.8, 109.4, 112.8, 111.2, 116.5, 120.4, 118.9, 122.5, 126.8]
    spy_cum = [100.0, 102.1, 104.2, 103.1, 106.8, 108.9, 107.5, 111.4, 113.8, 112.6, 115.2, 117.9]
    evolution_chart = [
        {
            "date": d,
            "portfolio_growth": p_cum[i],
            "benchmark_growth": spy_cum[i],
            "alpha_spread": round(p_cum[i] - spy_cum[i], 2),
            "portfolio_usd": round(120000.0 * (p_cum[i] / 100.0), 2)
        }
        for i, d in enumerate(history_dates)
    ]

    return {
        "kpis": {
            "net_worth": net_worth_data,
            "savings_rate": savings_data,
            "twr_pct": twr,
            "mwr_pct": mwr,
            "risk_metrics": risk_metrics
        },
        "allocation_treemap": treemap_data,
        "temporal_evolution": evolution_chart,
        "geopolitical_risk": db.get_geopolitical_risk(),
        "daily_api_quota": bb_client.get_quota_status()
    }

@app.get("/api/panorama")
def get_panorama():
    """Generates future cash flow forecasts and semaphoric budgeting checklist."""
    income = 6200.0
    expenses = 4040.0
    cash_reserves = 21250.0  # Combined USD cash + COP cash in USD
    discretionary = 950.0

    projections = calculate_budget_projections(
        monthly_income=income,
        monthly_expenses=expenses,
        current_cash_reserves=cash_reserves,
        discretionary_spending=discretionary
    )
    return projections

@app.get("/api/assets")
def get_assets_list():
    """Returns holdings and watchlist data grid items with P&L return calculations."""
    assets = db.get_assets(include_watchlist=True)
    results = []
    for a in assets:
        item = dict(a)
        qty = float(item["quantity"])
        avg_p = float(item["avg_price"])
        curr_p = float(item["current_price"])
        
        if qty > 0 and avg_p > 0:
            unrealized_pnl_pct = ((curr_p - avg_p) / avg_p) * 100.0
            unrealized_pnl_usd = (curr_p - avg_p) * qty
        else:
            unrealized_pnl_pct = 0.0
            unrealized_pnl_usd = 0.0

        item["unrealized_pnl_pct"] = round(unrealized_pnl_pct, 2)
        item["unrealized_pnl_usd"] = round(unrealized_pnl_usd, 2)
        item["market_value_usd"] = round(qty * curr_p, 2) if item["currency"] == "USD" else round((qty * curr_p) / USD_COP_EXCHANGE_RATE, 2)
        results.append(item)
    return results

@app.get("/api/theses")
def get_theses():
    """Returns investment theses with qualitative Investing Pro criteria."""
    return db.get_investment_theses()

@app.post("/api/theses")
def save_thesis(input_data: ThesisInput):
    """Evaluates the 5-point Human Safety Filter and saves or updates the investment thesis."""
    is_passed, message = GuardrailService.evaluate_checklist(
        valuation_grade=input_data.valuation_grade,
        safety_margin_pct=input_data.safety_margin,
        timing_context=input_data.timing_context,
        criteria=input_data.criteria_details
    )

    thesis_id = input_data.id or str(uuid.uuid4())
    thesis_dict = {
        "id": thesis_id,
        "ticker": input_data.ticker.upper(),
        "thesis_text": input_data.thesis_text,
        "valuation_grade": input_data.valuation_grade,
        "timing_context": input_data.timing_context,
        "safety_margin": input_data.safety_margin,
        "checklist_passed": is_passed,
        "criteria_details": input_data.criteria_details
    }
    db.save_investment_thesis(thesis_dict)
    return {
        "thesis": thesis_dict,
        "checklist_passed": is_passed,
        "evaluation_message": message
    }

@app.post("/api/simulate-purchase")
def simulate_purchase(sim: PurchaseSimulationInput):
    """
    STRICT GUARDRAIL: Blocks purchase simulation if thesis has not passed human safety checklist.
    """
    theses = db.get_investment_theses()
    matching_thesis = next((t for t in theses if t["ticker"] == sim.ticker.upper()), None)

    if not matching_thesis:
        raise HTTPException(
            status_code=400,
            detail=f"No existe tesis de inversión registrada para {sim.ticker}. Registre y valide el Filtro Humano primero."
        )

    assets = db.get_assets(include_watchlist=True)
    asset = next((a for a in assets if a["ticker"] == sim.ticker.upper()), None)
    current_price = float(asset["current_price"]) if asset else 100.0

    try:
        result = GuardrailService.simulate_purchase(
            ticker=sim.ticker.upper(),
            target_amount_usd=sim.target_amount_usd,
            current_price=current_price,
            thesis=matching_thesis
        )
        return result
    except TradeGuardrailBlockedError as e:
        raise HTTPException(
            status_code=403,
            detail=str(e)
        )

# --- BudgetBakers Ingestion & Cache Guard ---

@app.get("/api/budgetbakers/quota")
def get_bb_quota():
    return bb_client.get_quota_status()

@app.get("/api/budgetbakers/mappings")
def get_bb_mappings():
    return db.get_budgetbakers_mappings()

@app.post("/api/budgetbakers/sync")
def trigger_bb_sync(force_refresh: bool = False):
    """
    Synchronizes records from BudgetBakers API with cache and 25-request rate-limit protection.
    """
    try:
        fetch_result = bb_client.fetch_records(force_refresh=force_refresh)
        sync_result = bb_client.sync_to_transactions(fetch_result["data"])
        quota = bb_client.get_quota_status()
        return {
            "fetch_source": fetch_result.get("source"),
            "warning": fetch_result.get("warning"),
            "sync_details": sync_result,
            "daily_quota": quota
        }
    except DailyQuotaExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))

@app.post("/api/budgetbakers/mappings")
def update_mapping(data: MappingUpdateInput):
    db.update_budgetbakers_mapping(data.mapping_id, data.local_category, data.is_active)
    return {"status": "SUCCESS"}

# --- Executive Diagnostic Report ---

@app.get("/api/reports")
def get_executive_report(period: str = Query("mensual", pattern="^(diario|semanal|mensual)$")):
    """
    Generates strategic diagnosis based on user sketches (JERARQUIA & INFORME).
    """
    theses = db.get_investment_theses()
    approved_theses = [t["ticker"] for t in theses if t["checklist_passed"]]
    pending_theses = [t["ticker"] for t in theses if not t["checklist_passed"]]
    
    geopolitical = db.get_geopolitical_risk()
    anomalies = [g for g in geopolitical if g["anomaly_alert"]]

    return {
        "report_period": period.upper(),
        "generated_at": datetime.datetime.now().isoformat(),
        "dca_objectives": {
            "status": "CUMPLIDO",
            "monthly_target_usd": 1200.0,
            "executed_usd": 1200.0,
            "next_rebalance_date": "2026-10-01"
        },
        "thesis_guardrail_summary": {
            "total_theses": len(theses),
            "approved_tickers": approved_theses,
            "blocked_tickers": pending_theses
        },
        "geopolitical_alerts": anomalies,
        "strategic_recommendations": [
            "Mantener aportes sistemáticos (DCA) en ETFs de renta variable diversificada (SPY).",
            "Monitorear anomalía geopolítica en Europa y Asia-Pacífico antes de incrementar exposición.",
            "Completar el Filtro Humano para AAPL y AMZN antes de autorizar nuevas compras.",
            "Rebalancear liquidez en COP aprovechando la estabilidad relativa cambiaria."
        ]
    }
