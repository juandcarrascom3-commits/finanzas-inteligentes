"""
Portfolio Analytics & Quantitative Financial Metrics
Computes:
- Net Worth in USD and COP
- Monthly Savings Rate (%)
- Time-Weighted Return (TWR)
- Money-Weighted Return (MWR / IRR)
- Portfolio Beta (relative to S&P 500)
- Sharpe Ratio
- Maximum Drawdown (MDD)
"""

from typing import List, Dict, Any, Tuple
import math

USD_COP_EXCHANGE_RATE = 4050.0  # Parity default, can be dynamically refreshed

def calculate_net_worth(assets: List[Dict[str, Any]], exchange_rate: float = USD_COP_EXCHANGE_RATE) -> Dict[str, float]:
    """
    Computes total net worth aggregated across all holdings in both USD and COP.
    """
    total_usd = 0.0
    for asset in assets:
        if asset.get("is_watchlist", False):
            continue
        qty = float(asset.get("quantity", 0))
        price = float(asset.get("current_price", 0))
        currency = asset.get("currency", "USD").upper()

        if currency == "USD":
            total_usd += qty * price
        elif currency == "COP":
            total_usd += (qty * price) / exchange_rate
        else:
            total_usd += qty * price

    total_cop = total_usd * exchange_rate
    return {
        "net_worth_usd": round(total_usd, 2),
        "net_worth_cop": round(total_cop, 2),
        "exchange_rate": exchange_rate
    }

def calculate_savings_rate(monthly_income: float, monthly_expenses: float) -> Dict[str, Any]:
    """
    Computes monthly savings rate and status.
    Formula: (Income - Expenses) / Income * 100
    """
    if monthly_income <= 0:
        return {"savings_rate_pct": 0.0, "net_savings": -monthly_expenses, "status": "CRITICAL"}

    net_savings = monthly_income - monthly_expenses
    rate = (net_savings / monthly_income) * 100.0

    if rate >= 30.0:
        status = "OPTIMAL"  # Green
    elif rate >= 15.0:
        status = "MODERATE" # Orange
    else:
        status = "DEFICIT"  # Red

    return {
        "savings_rate_pct": round(rate, 2),
        "net_savings": round(net_savings, 2),
        "monthly_income": round(monthly_income, 2),
        "monthly_expenses": round(monthly_expenses, 2),
        "status": status
    }

def calculate_twr(subperiod_returns: List[float]) -> float:
    """
    Time-Weighted Return (TWR) eliminates the distortion of external cash flows.
    TWR = Product(1 + R_k) - 1
    subperiod_returns: e.g. [0.03, -0.01, 0.05, 0.08] for +3%, -1%, +5%, +8%
    """
    if not subperiod_returns:
        return 0.0
    compound_factor = 1.0
    for r in subperiod_returns:
        compound_factor *= (1.0 + r)
    return round((compound_factor - 1.0) * 100.0, 2)

def calculate_mwr_irr(cash_flows: List[Tuple[float, float]], max_iter: int = 100, tol: float = 1e-6) -> float:
    """
    Money-Weighted Return (MWR / Internal Rate of Return).
    cash_flows: list of (time_in_years, cash_flow_amount)
    Example: [(0.0, -10000), (0.5, -2000), (1.0, 14000)]
    Uses Newton-Raphson method to solve NPV(r) = 0.
    Returns annualized percentage.
    """
    if not cash_flows or len(cash_flows) < 2:
        return 0.0

    r = 0.10  # Initial guess (10%)
    for _ in range(max_iter):
        npv = 0.0
        d_npv = 0.0
        for t, cf in cash_flows:
            denom = math.pow(1.0 + r, t) if (1.0 + r) > 0 else 1e-6
            npv += cf / denom
            if (1.0 + r) > 0:
                d_npv -= (t * cf) / math.pow(1.0 + r, t + 1)

        if abs(npv) < tol:
            break
        if abs(d_npv) < 1e-12:
            break

        step = npv / d_npv
        r -= step
        if r < -0.99:
            r = -0.99

    return round(r * 100.0, 2)

def calculate_portfolio_risk_metrics(
    portfolio_daily_returns: List[float],
    benchmark_daily_returns: List[float],
    risk_free_rate_annual: float = 0.045
) -> Dict[str, float]:
    """
    Calculates:
    - Beta relative to S&P 500 benchmark: Cov(Rp, Rb) / Var(Rb)
    - Sharpe Ratio: (Annualized Rp - Rf) / Annualized StDev(Rp)
    - Maximum Drawdown (MDD) from daily equity curve
    """
    n = len(portfolio_daily_returns)
    if n < 2 or len(benchmark_daily_returns) != n:
        return {"beta": 1.0, "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0}

    mean_p = sum(portfolio_daily_returns) / n
    mean_b = sum(benchmark_daily_returns) / n

    cov_pb = sum((p - mean_p) * (b - mean_b) for p, b in zip(portfolio_daily_returns, benchmark_daily_returns)) / (n - 1)
    var_b = sum((b - mean_b) ** 2 for b in benchmark_daily_returns) / (n - 1)
    var_p = sum((p - mean_p) ** 2 for p in portfolio_daily_returns) / (n - 1)

    std_p_daily = math.sqrt(var_p) if var_p > 0 else 1e-6
    std_p_annual = std_p_daily * math.sqrt(252)

    beta = cov_pb / var_b if var_b > 1e-9 else 1.0

    # Annualized portfolio return assuming 252 trading days
    annualized_return_p = ((1.0 + mean_p) ** 252) - 1.0
    sharpe = (annualized_return_p - risk_free_rate_annual) / std_p_annual if std_p_annual > 0 else 0.0

    # Max Drawdown calculation
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in portfolio_daily_returns:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak
        if dd < max_dd:
            max_dd = dd

    return {
        "beta": round(beta, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100.0, 2),
        "annualized_volatility_pct": round(std_p_annual * 100.0, 2)
    }
