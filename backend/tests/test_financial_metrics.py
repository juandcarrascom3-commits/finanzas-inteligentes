"""
Unit Tests for Financial Metrics & Quantitative Analytics Engine
Tests:
- Net Worth calculation in USD & COP
- Monthly Savings Rate classification (OPTIMAL, MODERATE, DEFICIT)
- Time-Weighted Return (TWR)
- Money-Weighted Return (MWR / IRR)
- Risk Metrics: Beta, Sharpe Ratio, Maximum Drawdown
"""

import pytest
import math
from backend.analytics.metrics import (
    calculate_net_worth,
    calculate_savings_rate,
    calculate_twr,
    calculate_mwr_irr,
    calculate_portfolio_risk_metrics
)

def test_calculate_net_worth():
    assets = [
        {"ticker": "AAPL", "quantity": 10, "current_price": 200.0, "currency": "USD", "is_watchlist": False},
        {"ticker": "BCOLOMBIA", "quantity": 100, "current_price": 4000.0, "currency": "COP", "is_watchlist": False},
        {"ticker": "AMZN", "quantity": 50, "current_price": 180.0, "currency": "USD", "is_watchlist": True} # Watchlist should be excluded
    ]
    # Exchange rate: 4000 COP per USD
    # AAPL: 10 * 200 = 2000 USD
    # BCOLOMBIA: 100 * 4000 COP = 400,000 COP = 100 USD
    # Total USD = 2100 USD
    # Total COP = 2100 * 4000 = 8,400,000 COP
    result = calculate_net_worth(assets, exchange_rate=4000.0)
    assert result["net_worth_usd"] == 2100.0
    assert result["net_worth_cop"] == 8400000.0

def test_calculate_savings_rate():
    # 1. Optimal savings (>30%)
    res1 = calculate_savings_rate(monthly_income=5000.0, monthly_expenses=3000.0)
    assert res1["savings_rate_pct"] == 40.0
    assert res1["status"] == "OPTIMAL"

    # 2. Moderate savings (15% - 30%)
    res2 = calculate_savings_rate(monthly_income=4000.0, monthly_expenses=3200.0)
    assert res2["savings_rate_pct"] == 20.0
    assert res2["status"] == "MODERATE"

    # 3. Deficit (<15%)
    res3 = calculate_savings_rate(monthly_income=3000.0, monthly_expenses=2800.0)
    assert res3["savings_rate_pct"] == 6.67
    assert res3["status"] == "DEFICIT"

def test_calculate_twr():
    # 4 quarters: +5%, +10%, -4%, +8%
    subperiods = [0.05, 0.10, -0.04, 0.08]
    # (1.05 * 1.10 * 0.96 * 1.08) - 1 = 1.197504 - 1 = +19.75%
    twr = calculate_twr(subperiods)
    assert abs(twr - 19.75) < 0.05

def test_calculate_mwr_irr():
    # Initial investment of $10,000, 1 year later worth $11,500 (15% return)
    cash_flows = [(0.0, -10000.0), (1.0, 11500.0)]
    irr = calculate_mwr_irr(cash_flows)
    assert abs(irr - 15.0) < 0.1

def test_portfolio_risk_metrics():
    # Simulated 20-day returns
    p_returns = [0.01, -0.005, 0.02, 0.015, -0.01, 0.005, -0.02, 0.018, 0.002, -0.004] * 2
    b_returns = [0.008, -0.004, 0.015, 0.01, -0.008, 0.004, -0.015, 0.012, 0.001, -0.003] * 2

    metrics = calculate_portfolio_risk_metrics(p_returns, b_returns, risk_free_rate_annual=0.045)
    assert "beta" in metrics
    assert "sharpe_ratio" in metrics
    assert "max_drawdown_pct" in metrics
    assert metrics["beta"] > 0
    assert metrics["max_drawdown_pct"] <= 0.0 # Drawdowns are negative or zero
