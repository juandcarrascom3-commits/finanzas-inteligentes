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
from backend.integrations.budgetbakers_adapter import (
    BudgetBakersAdapter,
    BudgetBakersAuthError,
    BudgetBakersInitSyncError,
    BudgetBakersNetworkError,
    BudgetBakersRateLimitError,
)
from backend.analytics.understand import (
    get_action_items,
    get_budget_risks,
    get_cashflow_forecast,
    get_financial_changes,
    get_recurring_transactions,
)
from backend.analytics.monthly_review import get_monthly_review
from backend.analytics.wealth import (
    compare_benchmark,
    get_allocation,
    get_concentration,
    get_data_quality,
    get_performance,
    get_performance_attribution,
    get_portfolio_history,
    get_portfolio_summary,
    get_rebalancing_plan,
    get_total_return_breakdown,
    get_wealth_action_items,
)
from backend.analytics.investment_ledger import (
    derive_positions,
    get_effective_holdings,
    get_ledger_reconciliation,
    get_realized_pnl,
)
from backend.services.budgetbakers_client import BudgetBakersClient, DailyQuotaExceededError
from backend.services.guardrail_service import GuardrailService, TradeGuardrailBlockedError
from backend.services.market_data_service import apply_market_prices, get_market_data_status, sync_market_data

app = FastAPI(
    title="Finanzas Inteligentes API",
    description="Backend for Wealth Management, Risk Analytics & Ingestion",
    version="1.0.0"
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "FINANCE_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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

class AccountInput(BaseModel):
    id: Optional[str] = None
    name: str
    account_type: str = "cash"
    currency: str = "USD"
    opening_balance: float = 0.0
    current_balance: Optional[float] = None
    source: str = "MANUAL"
    is_active: bool = True

class AssetInput(BaseModel):
    ticker: str
    name: str
    asset_type: str = "Renta Variable"
    sector: str = "General"
    country: str = "Global"
    quantity: float = 0.0
    avg_price: float = 0.0
    current_price: float = 0.0
    currency: str = "USD"
    is_watchlist: bool = False
    logo_url: str = ""
    target_allocation_pct: float = 0.0
    source: str = "MANUAL"

class TransactionInput(BaseModel):
    id: Optional[str] = None
    account_id: Optional[str] = None
    amount: float
    category: str = "General"
    date: str
    description: str = ""
    currency: str = "USD"
    source: str = "MANUAL"
    external_id: Optional[str] = None

class CsvImportInput(BaseModel):
    content: str

class BackupPathInput(BaseModel):
    path: str

class ValuationInput(BaseModel):
    ticker: str
    valuation_date: str
    price: float = Field(gt=0)
    currency: str = "USD"
    source: str = "MANUAL"

class ValuationCsvInput(BaseModel):
    content: str
    source: str = "MANUAL"

class BenchmarkCsvInput(BaseModel):
    content: str
    benchmark_key: str
    label: Optional[str] = None
    source: str = "MANUAL"

class RebalanceQueryInput(BaseModel):
    contribution_usd: float = 0.0

class InvestmentOperationInput(BaseModel):
    id: Optional[str] = None
    occurred_at: str
    ticker: Optional[str] = None
    account_id: Optional[str] = None
    operation_type: str
    quantity: float = 0.0
    price: float = 0.0
    amount: float = 0.0
    fee: float = 0.0
    currency: str = "USD"
    source: str = "MANUAL"
    external_id: Optional[str] = None
    notes: str = ""
    metadata: Dict[str, Any] = {}

class InvestmentLedgerCsvInput(BaseModel):
    content: str
    source: str = "CSV"

class OpeningPositionInput(BaseModel):
    id: Optional[str] = None
    ticker: str
    account_id: Optional[str] = None
    opened_at: str
    quantity: float = Field(gt=0)
    unit_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"
    source: str = "MANUAL"
    notes: str = ""

class PositionAuthorityInput(BaseModel):
    ticker: str
    account_id: Optional[str] = None
    authority_state: str
    notes: str = ""

class SourceMappingInput(BaseModel):
    id: Optional[str] = None
    source: str
    external_type: str
    external_id: str
    external_name: str = ""
    local_id: Optional[str] = None
    local_type: Optional[str] = None
    is_active: bool = True

class CanonicalImportInput(BaseModel):
    accounts: List[Dict[str, Any]] = []
    transactions: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {}

class BudgetInput(BaseModel):
    id: Optional[str] = None
    category: str
    monthly_limit: float
    currency: str = "USD"
    source: str = "MANUAL"
    period: str = "MONTHLY"
    is_active: bool = True
    external_id: Optional[str] = None

class RecurringStatusInput(BaseModel):
    status: str

class MarketDataConfigInput(BaseModel):
    provider: str = "YFINANCE"
    benchmark_symbol: Optional[str] = "SPY"
    benchmark_label: Optional[str] = "SPY ETF"
    benchmark_provider: Optional[str] = "YFINANCE"
    quote_ttl_minutes: int = 720
    stale_after_days: int = 7
    history_lookback_days: int = 365
    fx_max_age_days: int = 5

class MarketDataSyncInput(BaseModel):
    include_watchlist: bool = False
    benchmark_symbol: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    mode: str = "FULL"

class SymbolMappingInput(BaseModel):
    internal_symbol: str
    provider: str = "YFINANCE"
    provider_symbol: str
    instrument_type: str = "EQUITY"
    expected_currency: Optional[str] = None
    status: str = "ACTIVE"
    notes: str = ""

class PriceAuthorityInput(BaseModel):
    ticker: str
    authority_mode: str = "AUTO"
    manual_price: Optional[float] = None
    manual_currency: Optional[str] = None
    notes: str = ""

class FxRateInput(BaseModel):
    base_currency: str
    quote_currency: str
    rate: float = Field(gt=0)
    rate_date: str
    provider: str = "MANUAL"
    source: str = "MANUAL"

class FxCsvInput(BaseModel):
    content: str
    source: str = "MANUAL"


def get_budgetbakers_adapter() -> BudgetBakersAdapter:
    return BudgetBakersAdapter()


def budgetbakers_error_response(exc: Exception):
    now = datetime.datetime.now().isoformat()
    if isinstance(exc, BudgetBakersAuthError):
        db.set_sync_state("BUDGETBAKERS", {"status": "AUTH_ERROR", "last_sync_at": now, "last_error": str(exc)})
        db.add_action_event("BUDGETBAKERS", "TOKEN_INVALID", str(exc), "ERROR")
        raise HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, BudgetBakersInitSyncError):
        db.set_sync_state("BUDGETBAKERS", {"status": "INIT_SYNC_IN_PROGRESS", "last_sync_at": now, "last_error": str(exc), "sync_in_progress": "true"})
        db.add_action_event("BUDGETBAKERS", "INIT_SYNC_IN_PROGRESS", str(exc), "WARNING")
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, BudgetBakersRateLimitError):
        db.set_sync_state("BUDGETBAKERS", {"status": "RATE_LIMITED", "last_sync_at": now, "last_error": str(exc)})
        db.add_action_event("BUDGETBAKERS", "RATE_LIMITED", str(exc), "WARNING", {"retry_after": exc.retry_after})
        headers = {"Retry-After": exc.retry_after} if exc.retry_after else None
        raise HTTPException(status_code=429, detail={"message": str(exc), "retry_after": exc.retry_after}, headers=headers)
    if isinstance(exc, BudgetBakersNetworkError):
        db.set_sync_state("BUDGETBAKERS", {"status": "NETWORK_ERROR", "last_sync_at": now, "last_error": str(exc)})
        raise HTTPException(status_code=502, detail=str(exc))
    raise exc

# --- API Endpoints ---

@app.get("/api/health")
def health():
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}

@app.get("/api/data-source")
def get_data_source():
    return db.get_data_source()

@app.get("/api/dashboard")
def get_dashboard_summary(exchange_rate: float = Query(USD_COP_EXCHANGE_RATE, ge=1000.0)):
    """Computes Top KPI Row, Allocation Treemap Hierarchy, and Benchmark curve."""
    assets = db.get_assets(include_watchlist=False)
    
    # 1. Top KPI: Net Worth
    net_worth_data = calculate_net_worth(assets, exchange_rate=exchange_rate)
    
    # 2. Top KPI: Monthly Savings Rate from persisted transactions
    tx_summary = db.get_transaction_summary()
    monthly_income = tx_summary["income"]
    monthly_expenses = tx_summary["expenses"]
    savings_data = calculate_savings_rate(monthly_income, monthly_expenses)

    # 3. Returns/risk require historical valuations; expose insufficient data explicitly.
    valuations = db.get_asset_valuations()
    wealth_history = get_portfolio_history(assets, valuations, db.get_transactions(limit=5000), exchange_rate=exchange_rate)
    wealth_performance = get_performance(wealth_history)
    twr = wealth_performance["twr"].get("value_pct")
    mwr = wealth_performance["mwr"].get("value_pct")
    risk_metrics = {
        "beta": None,
        "sharpe_ratio": wealth_performance["risk"]["sharpe"].get("value"),
        "max_drawdown_pct": wealth_performance["risk"]["max_drawdown"].get("value_pct"),
        "annualized_volatility_pct": wealth_performance["risk"]["volatility"].get("value_pct"),
        "status": {
            "twr": wealth_performance["twr"]["status"],
            "mwr": wealth_performance["mwr"]["status"],
            "beta": wealth_performance["risk"]["beta"]["status"],
        }
    }

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

    evolution_chart = []

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
        "daily_api_quota": bb_client.get_quota_status(),
        "data_source": db.get_data_source(),
        "cashflow": tx_summary
    }

@app.get("/api/panorama")
def get_panorama():
    """Generates future cash flow forecasts and semaphoric budgeting checklist."""
    summary = db.get_transaction_summary()
    income = summary["income"]
    expenses = summary["expenses"]
    cash_reserves = sum(float(a.get("current_balance", 0) or 0) for a in db.get_accounts())
    discretionary = 0.0

    projections = calculate_budget_projections(
        monthly_income=income,
        monthly_expenses=expenses,
        current_cash_reserves=cash_reserves,
        discretionary_spending=discretionary
    )
    return projections

@app.get("/api/accounts")
def get_accounts():
    return db.get_accounts()

@app.post("/api/accounts")
def save_account(account: AccountInput):
    return db.save_account(account.model_dump())

@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str):
    db.delete_account(account_id)
    return {"status": "SUCCESS"}

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

@app.post("/api/assets")
def save_asset(asset: AssetInput):
    return db.add_or_update_asset(asset.model_dump())

@app.delete("/api/assets/{ticker}")
def delete_asset(ticker: str):
    db.delete_asset(ticker)
    return {"status": "SUCCESS"}

@app.get("/api/transactions")
def get_transactions(
    limit: int = Query(100, ge=1, le=1000),
    account_id: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None
):
    return db.get_transactions(limit=limit, account_id=account_id, category=category, source=source)

@app.post("/api/transactions")
def save_transaction(tx: TransactionInput):
    return db.save_transaction(tx.model_dump())

@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(transaction_id: str):
    db.delete_transaction(transaction_id)
    return {"status": "SUCCESS"}

@app.get("/api/categories")
def get_categories():
    return db.get_categories()

@app.get("/api/valuations")
def get_asset_valuations(ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None):
    return db.get_asset_valuations(ticker=ticker, start=start, end=end)

@app.post("/api/valuations")
def save_asset_valuation(valuation: ValuationInput):
    return db.save_asset_valuation(valuation.model_dump())

@app.post("/api/valuations/import")
def import_asset_valuations_csv(payload: ValuationCsvInput):
    return db.import_asset_valuations_csv(payload.content, source=payload.source)

@app.get("/api/benchmarks")
def get_benchmark_prices(benchmark_key: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None):
    return db.get_benchmark_prices(benchmark_key=benchmark_key, start=start, end=end)

@app.post("/api/benchmarks/import")
def import_benchmark_prices_csv(payload: BenchmarkCsvInput):
    return db.import_benchmark_prices_csv(payload.content, payload.benchmark_key, label=payload.label, source=payload.source)

@app.get("/api/market-data/status")
def market_data_status():
    return get_market_data_status(db, db.get_assets(include_watchlist=False))

@app.get("/api/market-data/config")
def market_data_config():
    return db.get_market_data_config()

@app.post("/api/market-data/config")
def save_market_data_config(payload: MarketDataConfigInput):
    return db.save_market_data_config(payload.model_dump())

@app.get("/api/market-data/symbol-mappings")
def get_symbol_mappings(provider: Optional[str] = None, internal_symbol: Optional[str] = None):
    return db.get_symbol_mappings(provider=provider, internal_symbol=internal_symbol)

@app.post("/api/market-data/symbol-mappings")
def save_symbol_mapping(payload: SymbolMappingInput):
    return db.save_symbol_mapping(payload.model_dump())

@app.get("/api/market-data/price-authority")
def get_price_authority(ticker: Optional[str] = None):
    return db.get_price_authority(ticker)

@app.post("/api/market-data/price-authority")
def save_price_authority(payload: PriceAuthorityInput):
    try:
        return db.save_price_authority(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/market-data/fx")
def get_fx_rates(base_currency: Optional[str] = None, quote_currency: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None):
    return db.get_fx_rates(base_currency=base_currency, quote_currency=quote_currency, start=start, end=end)

@app.post("/api/market-data/fx")
def save_fx_rate(payload: FxRateInput):
    return db.save_fx_rate(payload.model_dump())

@app.post("/api/market-data/fx/import")
def import_fx_rates(payload: FxCsvInput):
    return db.import_fx_rates_csv(payload.content, source=payload.source)

@app.post("/api/market-data/sync")
def run_market_data_sync(payload: MarketDataSyncInput = MarketDataSyncInput()):
    try:
        return sync_market_data(
            db,
            include_watchlist=payload.include_watchlist,
            benchmark_symbol=payload.benchmark_symbol,
            start=payload.start,
            end=payload.end,
            mode=payload.mode,
        )
    except Exception as exc:
        now = datetime.datetime.now().isoformat()
        db.set_sync_state("MARKET_DATA", {"status": "FAILED", "last_sync_at": now, "last_error": str(exc)})
        raise HTTPException(status_code=502, detail=str(exc))

@app.get("/api/investment-ledger")
def get_investment_ledger(ticker: Optional[str] = None, operation_type: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None):
    return db.get_investment_transactions(ticker=ticker, operation_type=operation_type, start=start, end=end)

@app.post("/api/investment-ledger")
def save_investment_operation(payload: InvestmentOperationInput):
    try:
        return db.save_investment_transaction(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.delete("/api/investment-ledger/{operation_id}")
def delete_investment_operation(operation_id: str):
    db.delete_investment_transaction(operation_id)
    return {"status": "SUCCESS"}

@app.post("/api/investment-ledger/preview")
def preview_investment_ledger_csv(payload: InvestmentLedgerCsvInput):
    return db.preview_investment_transactions_csv(payload.content, source=payload.source)

@app.post("/api/investment-ledger/import")
def import_investment_ledger_csv(payload: InvestmentLedgerCsvInput):
    return db.import_investment_transactions_csv(payload.content, source=payload.source)

@app.get("/api/investment-ledger/reconciliation")
def investment_ledger_reconciliation():
    return get_ledger_reconciliation(
        db.get_assets(include_watchlist=False),
        db.get_investment_transactions(),
        db.get_opening_positions(),
        db.get_position_authority(),
    )

@app.get("/api/investment-ledger/realized-pnl")
def investment_ledger_realized_pnl(ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None):
    return get_realized_pnl(db.get_investment_transactions(), ticker=ticker, start=start, end=end, opening_positions=db.get_opening_positions())

@app.get("/api/opening-positions")
def get_opening_positions(ticker: Optional[str] = None):
    return db.get_opening_positions(ticker)

@app.post("/api/opening-positions")
def save_opening_position(payload: OpeningPositionInput):
    try:
        return db.save_opening_position(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/position-authority")
def get_position_authority():
    return db.get_position_authority()

@app.post("/api/position-authority")
def set_position_authority(payload: PositionAuthorityInput):
    assets = db.get_assets(include_watchlist=False)
    operations = db.get_investment_transactions()
    openings = db.get_opening_positions()
    current_authority = db.get_position_authority()
    reconciliation = get_ledger_reconciliation(assets, operations, openings, current_authority)
    row = next((item for item in reconciliation["rows"] if item["ticker"] == payload.ticker.upper()), None)
    if payload.authority_state.upper() == "LEDGER_AUTHORITATIVE":
        if not row or row["status"] != "MATCH":
            raise HTTPException(status_code=400, detail="Ledger adoption requires MATCH reconciliation.")
        lot_state = derive_positions(operations, openings)
        if lot_state["issues"]:
            raise HTTPException(status_code=400, detail={"message": "Ledger adoption blocked by lot issues.", "issues": lot_state["issues"]})
    try:
        return db.set_position_authority(payload.ticker, payload.authority_state, payload.account_id, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/effective-holdings")
def effective_holdings():
    return get_effective_holdings(
        db.get_assets(include_watchlist=False),
        db.get_investment_transactions(),
        db.get_opening_positions(),
        db.get_position_authority(),
    )

@app.get("/api/wealth")
def get_wealth(contribution_usd: float = Query(0.0, ge=0.0), benchmark_key: Optional[str] = None):
    assets = db.get_assets(include_watchlist=False)
    valuations = db.get_asset_valuations()
    fx_rates = db.get_fx_rates()
    market_config = db.get_market_data_config()
    fx_max_age_days = int(market_config.get("fx_max_age_days") or 5)
    transactions = db.get_transactions(limit=5000)
    ledger_operations = db.get_investment_transactions()
    openings = db.get_opening_positions()
    authority = db.get_position_authority()
    effective = get_effective_holdings(assets, ledger_operations, openings, authority)
    priced = apply_market_prices(db, effective["holdings"])
    effective_assets = priced["holdings"]
    benchmark_symbol = benchmark_key or market_config.get("benchmark_symbol")
    market_status = get_market_data_status(db, effective_assets)
    market_quality_issues = list(priced["issues"])
    for row in market_status["coverage"]["rows"]:
        if row["status"] == "UNRESOLVED_SYMBOL":
            market_quality_issues.append({"type": "symbol_mapping_required", "ticker": row["ticker"], "message": f"{row['ticker']} no tiene símbolo de provider resuelto.", "action": "Configurar provider symbol en Market Data."})
        elif row["status"] == "MISSING_FX":
            market_quality_issues.append({"type": "missing_fx", "ticker": row["ticker"], "message": f"{row['ticker']} requiere FX para valoración USD.", "action": "Registrar FX manual o sincronizar Market Data."})
        elif row["status"] == "MISSING_HISTORY":
            market_quality_issues.append({"type": "missing_historical_coverage", "ticker": row["ticker"], "message": f"{row['ticker']} no tiene histórico de mercado.", "action": "Ejecutar Full history refresh."})
    if market_status["coverage"]["summary"]["benchmark_status"] != "OK":
        market_quality_issues.append({"type": "benchmark_insufficient_coverage", "ticker": "BENCHMARK", "message": "Benchmark sin histórico suficiente.", "action": "Configurar benchmark y ejecutar actualización."})
    history = get_portfolio_history(effective_assets, valuations, transactions, fx_rates=fx_rates, fx_max_age_days=fx_max_age_days)
    performance = get_performance(history, transactions, ledger_operations=ledger_operations)
    allocation = get_allocation(effective_assets, fx_rates=fx_rates, fx_max_age_days=fx_max_age_days)
    concentration = get_concentration(allocation)
    data_quality = get_data_quality(effective_assets, valuations, fx_rates=fx_rates, fx_max_age_days=fx_max_age_days, market_issues=market_quality_issues, benchmark_key=benchmark_symbol)
    rebalancing = get_rebalancing_plan(effective_assets, contribution_usd=contribution_usd, fx_rates=fx_rates, fx_max_age_days=fx_max_age_days)
    if effective["status"] == "PARTIAL_DATA":
        rebalancing["status"] = "PARTIAL_DATA"
        rebalancing["reason"] = "Some positions have unresolved ledger/holding reconciliation."
    attribution = get_performance_attribution(effective_assets, valuations, fx_rates=fx_rates, fx_max_age_days=fx_max_age_days)
    benchmark = compare_benchmark(history, db.get_benchmark_prices(benchmark_key=benchmark_symbol) if benchmark_symbol else [])
    ledger_positions = derive_positions(ledger_operations, openings)
    ledger_reconciliation = effective["reconciliation"]
    return {
        "summary": get_portfolio_summary(effective_assets, fx_rates=fx_rates, fx_max_age_days=fx_max_age_days),
        "history": history,
        "performance": performance,
        "allocation": allocation,
        "concentration": concentration,
        "data_quality": data_quality,
        "attribution": attribution,
        "rebalancing": rebalancing,
        "benchmark": benchmark,
        "ledger": {
            "operations": ledger_operations,
            "positions": ledger_positions["positions"],
            "open_lots": ledger_positions["open_lots"],
            "realized_trades": ledger_positions["realized_trades"],
            "issues": ledger_positions["issues"],
            "reconciliation": ledger_reconciliation,
            "effective_holdings": effective,
            "authority": authority,
            "opening_positions": openings,
            "total_return_breakdown": get_total_return_breakdown(effective_assets, ledger_operations, openings),
        },
        "market_data": {
            **market_status,
            "config": market_config,
            "pricing_status": priced["status"],
            "issues": market_quality_issues,
        },
        "action_items": get_wealth_action_items(data_quality, concentration, rebalancing, ledger_reconciliation, ledger_positions["issues"]),
    }

@app.get("/api/budgets")
def get_budgets():
    return db.get_budgets()

@app.post("/api/budgets")
def save_budget(budget: BudgetInput):
    return db.save_budget(budget.model_dump())

@app.delete("/api/budgets/{budget_id}")
def delete_budget(budget_id: str):
    db.delete_budget(budget_id)
    return {"status": "SUCCESS"}

@app.get("/api/recurring")
def get_recurring():
    detected = get_recurring_transactions(db.get_transactions(limit=5000))
    stored = db.sync_detected_recurring_rules(detected)
    return stored

@app.patch("/api/recurring/{rule_id}")
def update_recurring(rule_id: str, payload: RecurringStatusInput):
    try:
        return db.update_recurring_status(rule_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/import/transactions/preview")
def preview_transactions_csv(payload: CsvImportInput):
    return db.preview_transactions_csv(payload.content)

@app.post("/api/import/transactions")
def import_transactions_csv(payload: CsvImportInput):
    return db.import_transactions_csv(payload.content)

@app.get("/api/backup")
def export_backup():
    return db.export_backup()

@app.post("/api/backup/validate")
def validate_backup(payload: BackupPathInput):
    try:
        return db.validate_backup(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/backup/restore")
def restore_backup(payload: BackupPathInput):
    try:
        return db.restore_backup(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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

@app.get("/api/budgetbakers/status")
def get_budgetbakers_status():
    adapter = get_budgetbakers_adapter()
    state = db.get_sync_state("BUDGETBAKERS")
    configured = adapter.is_configured()
    if not configured:
        return {
            "source": "BUDGETBAKERS",
            "configured": False,
            "status": "NOT_CONFIGURED",
            "message": "Configure BUDGETBAKERS_API_TOKEN en .env para conectar Wallet.",
            "sync_state": state,
        }
    return {
        "source": "BUDGETBAKERS",
        "configured": True,
        "status": state.get("status") if state.get("status") != "NOT_CONFIGURED" else "CONFIGURED",
        "last_success_at": state.get("last_success_at"),
        "last_error": state.get("last_error"),
        "last_data_change_at": state.get("last_data_change_at"),
        "sync_in_progress": state.get("sync_in_progress"),
        "sync_state": state,
    }

@app.post("/api/budgetbakers/test")
def test_budgetbakers_connection():
    try:
        result = get_budgetbakers_adapter().test_connection()
        if result.get("status") == "CONNECTED":
            db.set_sync_state("BUDGETBAKERS", {
                "status": "CONNECTED",
                "last_sync_at": datetime.datetime.now().isoformat(),
                "last_error": None,
                "last_data_change_at": result.get("last_data_change_at"),
                "sync_in_progress": result.get("sync_in_progress"),
            })
        return result
    except Exception as exc:
        return budgetbakers_error_response(exc)

def _budgetbakers_category_mappings() -> Dict[str, str]:
    legacy = {
        item["bb_category_name"]: item["local_category"]
        for item in db.get_budgetbakers_mappings()
        if item.get("is_active")
    }
    generic = {
        item["external_name"] or item["external_id"]: item["local_id"]
        for item in db.get_source_mappings("BUDGETBAKERS", "category")
        if item.get("is_active") and item.get("local_id")
    }
    return {**legacy, **generic}

@app.post("/api/budgetbakers/preview")
def preview_budgetbakers_import():
    try:
        adapter = get_budgetbakers_adapter()
        if not adapter.is_configured():
            raise BudgetBakersAuthError("BUDGETBAKERS_API_TOKEN no está configurado.")
        accounts_result = adapter.fetch_accounts()
        records_result = adapter.fetch_records()
        categories_result = adapter.fetch_categories()
        try:
            budgets_result = adapter.fetch_budgets()
        except BudgetBakersNetworkError:
            budgets_result = {"items": [], "pages": 0, "meta": {}, "warning": "Wallet budgets no disponible en esta API/cuenta."}
        try:
            standing_orders_result = adapter.fetch_standing_orders()
        except BudgetBakersNetworkError:
            standing_orders_result = {"items": [], "pages": 0, "meta": {}, "warning": "Wallet standing orders no disponible en esta API/cuenta."}
        normalized_accounts = adapter.normalize_accounts(accounts_result["items"])
        account_mappings = db.get_source_mapping_lookup("BUDGETBAKERS", "account")
        normalized_records = adapter.normalize_records(records_result["items"], category_mappings=_budgetbakers_category_mappings(), account_mappings=account_mappings)
        normalized_categories = adapter.normalize_categories(categories_result["items"])
        normalized_budgets = adapter.normalize_budgets(budgets_result["items"])
        normalized_standing_orders = adapter.normalize_standing_orders(standing_orders_result["items"])
        for category in normalized_categories:
            db.save_source_mapping({
                "source": "BUDGETBAKERS",
                "external_type": "category",
                "external_id": category["external_id"],
                "external_name": category["external_name"],
                "local_id": _budgetbakers_category_mappings().get(category["external_name"]),
                "local_type": "category",
                "is_active": True,
            })
        meta = {
            **accounts_result.get("meta", {}),
            **records_result.get("meta", {}),
            **categories_result.get("meta", {}),
            **budgets_result.get("meta", {}),
            **standing_orders_result.get("meta", {}),
        }
        db.set_sync_state("BUDGETBAKERS", {
            "status": "PREVIEW_READY",
            "last_sync_at": datetime.datetime.now().isoformat(),
            "last_error": None,
            "last_data_change_at": meta.get("last_data_change_at"),
            "last_data_change_rev": meta.get("last_data_change_rev"),
            "sync_in_progress": meta.get("sync_in_progress"),
        })
        preview = db.preview_canonical_import(normalized_accounts, normalized_records, "BUDGETBAKERS")
        return {
            **preview,
            "accounts": normalized_accounts,
            "transactions": normalized_records,
            "categories": normalized_categories,
            "budgets": normalized_budgets,
            "standing_orders": normalized_standing_orders,
            "meta": meta,
            "optional_warnings": [item.get("warning") for item in (budgets_result, standing_orders_result) if item.get("warning")],
            "pages": {
                "accounts": accounts_result.get("pages", 0),
                "records": records_result.get("pages", 0),
                "categories": categories_result.get("pages", 0),
                "budgets": budgets_result.get("pages", 0),
                "standing_orders": standing_orders_result.get("pages", 0),
            },
        }
    except Exception as exc:
        return budgetbakers_error_response(exc)

@app.post("/api/budgetbakers/import")
def import_budgetbakers_preview(payload: CanonicalImportInput):
    try:
        return db.import_canonical_import(payload.accounts, payload.transactions, "BUDGETBAKERS", payload.meta)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/source-mappings")
def get_source_mappings(source: str = Query("BUDGETBAKERS"), external_type: Optional[str] = None):
    return db.get_source_mappings(source, external_type)

@app.post("/api/source-mappings")
def save_source_mapping(mapping: SourceMappingInput):
    return db.save_source_mapping(mapping.model_dump())

@app.post("/api/budgetbakers/import-plan")
def import_budgetbakers_plan(payload: Dict[str, Any]):
    imported_budgets = 0
    imported_orders = 0
    for budget in payload.get("budgets", []):
        db.save_budget({**budget, "source": "BUDGETBAKERS"})
        imported_budgets += 1
    for order in payload.get("standing_orders", []):
        db.upsert_recurring_rule({**order, "source": "BUDGETBAKERS", "status": "confirmed"})
        imported_orders += 1
    return {"imported_budgets": imported_budgets, "imported_standing_orders": imported_orders}

@app.get("/api/reconciliation")
def get_reconciliation(source: str = Query("BUDGETBAKERS")):
    return db.get_reconciliation_summary(source)

@app.get("/api/understand")
def get_understand(period: str = Query("current_month", pattern="^(current_month|previous_month|last_30_days)$")):
    transactions = db.get_transactions(limit=5000)
    accounts = db.get_accounts()
    budgets = db.get_budgets()
    reconciliation = db.get_reconciliation_summary("BUDGETBAKERS")
    recurring = get_recurring_transactions(transactions)
    budget_risks = get_budget_risks(transactions, budgets)
    sync_state = db.get_sync_state("BUDGETBAKERS")
    return {
        "what_changed": get_financial_changes(transactions, period),
        "recurring": recurring,
        "budget_burn": budget_risks,
        "cashflow_forecast": get_cashflow_forecast(accounts, transactions, recurring),
        "action_items": get_action_items(reconciliation, budget_risks, recurring, sync_state),
        "reconciliation": reconciliation,
        "action_events": db.get_action_events(limit=20),
    }

@app.get("/api/monthly-review")
def monthly_review(period: Optional[str] = None):
    return get_monthly_review(
        transactions=db.get_transactions(limit=5000),
        accounts=db.get_accounts(),
        budgets=db.get_budgets(),
        stored_recurring=db.get_recurring_rules(include_rejected=True),
        reconciliation=db.get_reconciliation_summary("BUDGETBAKERS"),
        period=period,
    )

@app.post("/api/monthly-review/snapshot")
def save_monthly_review_snapshot(period: Optional[str] = None):
    review = monthly_review(period)
    return db.save_monthly_review_snapshot(review["period"], review)

@app.get("/api/monthly-review/snapshots")
def get_monthly_review_snapshots():
    return db.get_monthly_review_snapshots()

@app.get("/api/budgetbakers/mappings")
def get_bb_mappings():
    return db.get_budgetbakers_mappings()

@app.post("/api/budgetbakers/sync")
def trigger_bb_sync(force_refresh: bool = False):
    """
    Legacy mock sync is disabled. Use /api/budgetbakers/preview and /api/budgetbakers/import.
    """
    raise HTTPException(status_code=410, detail="La sincronización demo fue desactivada. Use preview/import real de BudgetBakers.")

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
