"""Deterministic portfolio analytics for local wealth intelligence."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from math import sqrt
from typing import Any, Dict, List, Optional, Tuple

from backend.analytics.metrics import calculate_mwr_irr, calculate_twr
from backend.analytics.investment_ledger import (
    calculate_mwr as calculate_ledger_mwr,
    get_investment_cashflows,
    get_investment_income,
    get_ledger_reconciliation,
    get_realized_pnl,
    get_unrealized_pnl_from_lots,
)


KNOWN_CURRENCIES = {"USD", "COP"}


def _as_date(value: str) -> date:
    return datetime.fromisoformat(str(value)[:10]).date()


def _fx_rate_for_date(fx_rates: List[Dict[str, Any]], from_currency: str, to_currency: str, day: Optional[date], max_age_days: int = 5) -> Optional[float]:
    source = (from_currency or "USD").upper()
    target = (to_currency or "USD").upper()
    if source == target:
        return 1.0
    if day is None:
        day = date.today()
    candidates = []
    inverse = []
    for row in fx_rates or []:
        row_day = _as_date(row["rate_date"])
        if row_day > day:
            continue
        age = (day - row_day).days
        if age > max_age_days:
            continue
        base = row["base_currency"].upper()
        quote = row["quote_currency"].upper()
        if base == source and quote == target:
            candidates.append((row_day, float(row["rate"])))
        elif base == target and quote == source and float(row["rate"]) > 0:
            inverse.append((row_day, 1 / float(row["rate"])))
    if candidates:
        return sorted(candidates, key=lambda item: item[0])[-1][1]
    if inverse:
        return sorted(inverse, key=lambda item: item[0])[-1][1]
    return None


def _value_usd(quantity: float, price: float, currency: str, exchange_rate: float, valuation_date: Optional[date] = None, fx_rates: Optional[List[Dict[str, Any]]] = None, fx_max_age_days: int = 5) -> float:
    value = quantity * price
    currency = currency.upper()
    if currency == "USD":
        return value
    rate = _fx_rate_for_date(fx_rates or [], currency, "USD", valuation_date, fx_max_age_days)
    if rate is not None:
        return value * rate
    return value / exchange_rate if currency == "COP" else value


def _active_assets(assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [a for a in assets if not a.get("is_watchlist") and float(a.get("quantity") or 0) > 0]


def _latest_prices_by_date(valuations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in valuations:
        grouped[row["ticker"].upper()].append(row)
    for ticker in grouped:
        grouped[ticker].sort(key=lambda item: item["valuation_date"])
    return grouped


def _latest_price_on_or_before(rows: List[Dict[str, Any]], day: date) -> Optional[Dict[str, Any]]:
    latest = None
    for row in rows:
        if _as_date(row["valuation_date"]) <= day:
            latest = row
        else:
            break
    return latest


def get_portfolio_summary(assets: List[Dict[str, Any]], exchange_rate: float = 4050.0, fx_rates: Optional[List[Dict[str, Any]]] = None, fx_max_age_days: int = 5) -> Dict[str, Any]:
    holdings = _active_assets(assets)
    rows = []
    total = 0.0
    unrealized = 0.0
    for asset in holdings:
        qty = float(asset.get("quantity") or 0)
        price = float(asset.get("current_price") or 0)
        avg = float(asset.get("avg_price") or 0)
        currency = (asset.get("currency") or "USD").upper()
        value = _value_usd(qty, price, currency, exchange_rate, date.today(), fx_rates, fx_max_age_days) if price > 0 else 0.0
        cost = _value_usd(qty, avg, currency, exchange_rate, date.today(), fx_rates, fx_max_age_days) if avg > 0 else 0.0
        pnl = value - cost if cost > 0 else None
        total += value
        if pnl is not None:
            unrealized += pnl
        rows.append({**asset, "market_value_usd": round(value, 2), "cost_basis_usd": round(cost, 2), "unrealized_pnl_usd": round(pnl, 2) if pnl is not None else None})
    return {
        "total_value_usd": round(total, 2),
        "unrealized_pnl_usd": round(unrealized, 2),
        "unrealized_pnl_status": "AVAILABLE" if any(r["unrealized_pnl_usd"] is not None for r in rows) else "INSUFFICIENT_DATA",
        "holdings": rows,
    }


def get_portfolio_history(
    assets: List[Dict[str, Any]],
    valuations: List[Dict[str, Any]],
    transactions: Optional[List[Dict[str, Any]]] = None,
    exchange_rate: float = 4050.0,
    fx_rates: Optional[List[Dict[str, Any]]] = None,
    fx_max_age_days: int = 5,
) -> Dict[str, Any]:
    holdings = _active_assets(assets)
    by_ticker = _latest_prices_by_date(valuations)
    dates = sorted({_as_date(v["valuation_date"]) for v in valuations})
    series = []
    missing_dates = 0

    for day in dates:
        value = 0.0
        covered_value = 0.0
        covered_assets = 0
        asset_values = {}
        for asset in holdings:
            ticker = asset["ticker"].upper()
            price_row = _latest_price_on_or_before(by_ticker.get(ticker, []), day)
            if not price_row:
                continue
            qty = float(asset.get("quantity") or 0)
            price = float(price_row.get("price") or 0)
            currency = (price_row.get("currency") or asset.get("currency") or "USD").upper()
            asset_value = _value_usd(qty, price, currency, exchange_rate, day, fx_rates, fx_max_age_days)
            value += asset_value
            covered_value += asset_value
            covered_assets += 1
            asset_values[ticker] = round(asset_value, 2)
        if covered_assets < len(holdings):
            missing_dates += 1
        series.append({
            "date": day.isoformat(),
            "portfolio_value_usd": round(value, 2),
            "external_cash_flow_usd": _external_flow_on_day(transactions or [], day),
            "coverage_pct": round((covered_assets / len(holdings)) * 100, 2) if holdings else 100.0,
            "asset_values": asset_values,
        })

    return {
        "status": "AVAILABLE" if len(series) >= 2 else "INSUFFICIENT_DATA",
        "policy": "Uses the latest known price on or before each valuation date; missing prices are not invented.",
        "series": series,
        "data_quality": {
            "valuation_dates": len(series),
            "missing_valuation_dates": missing_dates,
            "coverage_pct": round(sum(p["coverage_pct"] for p in series) / len(series), 2) if series else 0.0,
        },
    }


def _external_flow_on_day(transactions: List[Dict[str, Any]], day: date) -> float:
    total = 0.0
    for tx in transactions:
        if str(tx.get("date", ""))[:10] != day.isoformat():
            continue
        raw = tx.get("raw_payload") or {}
        if isinstance(raw, str):
            raw = {}
        flow_type = str(raw.get("investment_flow_type") or raw.get("flow_type") or "").upper()
        if flow_type in {"CONTRIBUTION", "DEPOSIT", "WITHDRAWAL"}:
            total += float(tx.get("amount") or 0)
    return round(total, 2)


def get_performance(history: Dict[str, Any], transactions: Optional[List[Dict[str, Any]]] = None, ledger_operations: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    series = history.get("series", [])
    if len(series) < 2:
        return _insufficient_performance("Need at least two portfolio valuation dates.")
    values = [float(p["portfolio_value_usd"]) for p in series]
    if values[0] <= 0:
        return _insufficient_performance("Initial portfolio value must be positive.")

    returns = []
    for prev, cur in zip(series, series[1:]):
        start = float(prev["portfolio_value_usd"])
        end = float(cur["portfolio_value_usd"])
        flow = float(cur.get("external_cash_flow_usd") or 0)
        if start <= 0:
            continue
        returns.append((end - start - flow) / start)

    cumulative = (values[-1] - values[0] - sum(float(p.get("external_cash_flow_usd") or 0) for p in series[1:])) / values[0]
    mwr = calculate_ledger_mwr(ledger_operations, values[-1], series[-1]["date"]) if ledger_operations is not None else _money_weighted_return(series)
    risk = _risk_from_returns(returns)
    realized = get_realized_pnl(ledger_operations or [])
    income = get_investment_income(ledger_operations or [])
    return {
        "twr": {"status": "AVAILABLE", "value_pct": calculate_twr(returns), "reason": None},
        "mwr": mwr,
        "cumulative_return": {"status": "AVAILABLE", "value_pct": round(cumulative * 100, 2), "reason": None},
        "period_return": {"status": "AVAILABLE", "value_pct": round(returns[-1] * 100, 2) if returns else 0.0, "reason": None},
        "realized_pnl": {
            "status": realized["status"] if realized["trades"] else "INSUFFICIENT_DATA",
            "value_usd": realized["total_realized_pnl"] if realized["trades"] else None,
            "reason": None if realized["trades"] else "No closed FIFO lots/sells available.",
            "details": realized,
        },
        "income": income,
        "cashflows": get_investment_cashflows(ledger_operations or []),
        "risk": risk,
    }


def _insufficient_performance(reason: str) -> Dict[str, Any]:
    metric = {"status": "INSUFFICIENT_DATA", "value_pct": None, "reason": reason}
    return {
        "twr": metric,
        "mwr": metric,
        "cumulative_return": metric,
        "period_return": metric,
        "realized_pnl": {"status": "INSUFFICIENT_DATA", "value_usd": None, "reason": "No lot/sale model exists yet."},
        "risk": {
            "volatility": metric,
            "max_drawdown": metric,
            "sharpe": metric,
            "beta": {"status": "INSUFFICIENT_DATA", "value": None, "reason": "No benchmark series selected."},
        },
    }


def _money_weighted_return(series: List[Dict[str, Any]]) -> Dict[str, Any]:
    dated_flows = [(p["date"], float(p.get("external_cash_flow_usd") or 0)) for p in series if float(p.get("external_cash_flow_usd") or 0) != 0]
    if not dated_flows:
        return {"status": "INSUFFICIENT_DATA", "value_pct": None, "reason": "No explicit investment cash flows available."}
    start = _as_date(series[0]["date"])
    flows: List[Tuple[float, float]] = [(0.0, -float(series[0]["portfolio_value_usd"]))]
    for flow_date, amount in dated_flows:
        flows.append(((_as_date(flow_date) - start).days / 365.25, -amount))
    flows.append(((_as_date(series[-1]["date"]) - start).days / 365.25, float(series[-1]["portfolio_value_usd"])))
    return {"status": "AVAILABLE", "value_pct": calculate_mwr_irr(flows), "reason": None}


def _risk_from_returns(returns: List[float]) -> Dict[str, Any]:
    if len(returns) < 3:
        metric = {"status": "INSUFFICIENT_DATA", "value_pct": None, "reason": "Need at least three return observations."}
        return {
            "volatility": metric,
            "max_drawdown": metric,
            "sharpe": metric,
            "beta": {"status": "INSUFFICIENT_DATA", "value": None, "reason": "No benchmark series selected."},
        }
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    daily_vol = sqrt(variance)
    annual_vol = daily_vol * sqrt(252)
    annual_return = ((1 + mean) ** 252) - 1
    sharpe = (annual_return - 0.04) / annual_vol if annual_vol > 0 else None
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for item in returns:
        equity *= 1 + item
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity - peak) / peak)
    return {
        "volatility": {"status": "AVAILABLE", "value_pct": round(annual_vol * 100, 2), "reason": None},
        "max_drawdown": {"status": "AVAILABLE", "value_pct": round(max_dd * 100, 2), "reason": None},
        "sharpe": {"status": "AVAILABLE", "value": round(sharpe, 2) if sharpe is not None else None, "reason": None},
        "beta": {"status": "INSUFFICIENT_DATA", "value": None, "reason": "No benchmark series selected."},
    }


def get_allocation(assets: List[Dict[str, Any]], exchange_rate: float = 4050.0, fx_rates: Optional[List[Dict[str, Any]]] = None, fx_max_age_days: int = 5) -> Dict[str, Any]:
    summary = get_portfolio_summary(assets, exchange_rate, fx_rates, fx_max_age_days)
    total = summary["total_value_usd"]
    dimensions = {key: defaultdict(float) for key in ["asset_type", "sector", "country", "currency", "ticker"]}
    holdings = []
    for asset in summary["holdings"]:
        value = float(asset["market_value_usd"])
        pct = (value / total * 100) if total else 0.0
        row = {"ticker": asset["ticker"], "value_usd": round(value, 2), "allocation_pct": round(pct, 2)}
        holdings.append(row)
        for key in ["asset_type", "sector", "country", "currency"]:
            dimensions[key][asset.get(key) or "Unknown"] += value
        dimensions["ticker"][asset["ticker"]] += value
    return {
        "total_value_usd": total,
        "dimensions": {
            key: _dimension_rows(values, total)
            for key, values in dimensions.items()
        },
        "holdings": sorted(holdings, key=lambda item: item["value_usd"], reverse=True),
    }


def _dimension_rows(values: Dict[str, float], total: float) -> List[Dict[str, Any]]:
    return [
        {"name": name or "Unknown", "value_usd": round(value, 2), "allocation_pct": round((value / total * 100) if total else 0.0, 2)}
        for name, value in sorted(values.items(), key=lambda item: item[1], reverse=True)
    ]


def get_concentration(allocation: Dict[str, Any], thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    limits = {"single_asset_pct": 25.0, "top3_pct": 60.0, "sector_pct": 45.0, "country_pct": 70.0, "currency_pct": 80.0}
    limits.update(thresholds or {})
    holdings = allocation["holdings"]
    top1 = holdings[0] if holdings else None
    top3_pct = round(sum(item["allocation_pct"] for item in holdings[:3]), 2)
    top5_pct = round(sum(item["allocation_pct"] for item in holdings[:5]), 2)
    alerts = []
    if top1 and top1["allocation_pct"] > limits["single_asset_pct"]:
        alerts.append({"type": "single_asset", "severity": "medium", "message": f"{top1['ticker']} representa {top1['allocation_pct']}% de la cartera.", "action": "Revisar target allocation."})
    if top3_pct > limits["top3_pct"]:
        alerts.append({"type": "top3", "severity": "medium", "message": f"Top 3 representa {top3_pct}% de la cartera.", "action": "Revisar concentración."})
    for dimension, limit_key in [("sector", "sector_pct"), ("country", "country_pct"), ("currency", "currency_pct")]:
        top = allocation["dimensions"].get(dimension, [None])[0]
        if top and top["allocation_pct"] > limits[limit_key]:
            alerts.append({"type": dimension, "severity": "medium", "message": f"{top['name']} representa {top['allocation_pct']}% de la cartera.", "action": "Revisar exposición."})
    return {"top_asset": top1, "top3_pct": top3_pct, "top5_pct": top5_pct, "alerts": alerts}


def get_data_quality(assets: List[Dict[str, Any]], valuations: List[Dict[str, Any]], exchange_rate: float = 4050.0, fx_rates: Optional[List[Dict[str, Any]]] = None, fx_max_age_days: int = 5, market_issues: Optional[List[Dict[str, Any]]] = None, benchmark_key: Optional[str] = None) -> Dict[str, Any]:
    holdings = _active_assets(assets)
    tickers_with_history = {v["ticker"].upper() for v in valuations}
    summary = get_portfolio_summary(assets, exchange_rate, fx_rates, fx_max_age_days)
    total = summary["total_value_usd"]
    covered_value = 0.0
    issues = []
    for asset in summary["holdings"]:
        ticker = asset["ticker"].upper()
        value = float(asset["market_value_usd"])
        has_price = float(asset.get("current_price") or 0) > 0
        has_cost = float(asset.get("avg_price") or 0) > 0
        has_history = ticker in tickers_with_history
        if has_history:
            covered_value += value
        if not has_price:
            issues.append({"type": "missing_price", "ticker": ticker, "message": f"{ticker} no tiene precio actual.", "action": "Registrar precio manual o importar valoración."})
        if not has_cost:
            issues.append({"type": "missing_cost", "ticker": ticker, "message": f"{ticker} no tiene coste medio.", "action": "Completar costo promedio."})
        if not has_history:
            issues.append({"type": "missing_history", "ticker": ticker, "message": f"{ticker} no tiene histórico de valoración.", "action": "Importar histórico CSV o actualizar market data."})
        if (asset.get("currency") or "").upper() not in KNOWN_CURRENCIES:
            issues.append({"type": "unknown_currency", "ticker": ticker, "message": f"{ticker} usa moneda no reconocida.", "action": "Normalizar moneda."})
        if (asset.get("currency") or "USD").upper() != "USD" and _fx_rate_for_date(fx_rates or [], (asset.get("currency") or "USD").upper(), "USD", date.today(), fx_max_age_days) is None:
            issues.append({"type": "missing_fx", "ticker": ticker, "message": f"{ticker} requiere FX histórico/reciente para valorar en USD.", "action": "Actualizar FX de mercado o importar tasa manual."})
        if asset.get("price_status") in {"STALE", "UNAVAILABLE"}:
            issues.append({"type": f"{str(asset.get('price_status')).lower()}_price", "ticker": ticker, "message": f"{ticker} tiene precio {asset.get('price_status')}.", "action": "Actualizar market data o registrar precio manual."})
        for key in ["asset_type", "sector", "country"]:
            if not asset.get(key):
                issues.append({"type": "missing_metadata", "ticker": ticker, "message": f"{ticker} no tiene {key}.", "action": "Completar metadata."})
        if float(asset.get("target_allocation_pct") or 0) <= 0:
            issues.append({"type": "missing_target", "ticker": ticker, "message": f"{ticker} no tiene target allocation.", "action": "Definir target allocation."})
    for issue in market_issues or []:
        issues.append(issue)
    if benchmark_key is None:
        issues.append({"type": "missing_benchmark", "ticker": "BENCHMARK", "message": "No hay benchmark seleccionado para comparación.", "action": "Configurar o sincronizar benchmark."})
    return {
        "history_coverage_pct": round((covered_value / total * 100) if total else 0.0, 2),
        "assets_with_history": len(tickers_with_history & {a["ticker"].upper() for a in holdings}),
        "total_assets": len(holdings),
        "issues": issues,
    }


def get_performance_attribution(assets: List[Dict[str, Any]], valuations: List[Dict[str, Any]], start: Optional[str] = None, end: Optional[str] = None, exchange_rate: float = 4050.0, fx_rates: Optional[List[Dict[str, Any]]] = None, fx_max_age_days: int = 5) -> Dict[str, Any]:
    holdings = _active_assets(assets)
    by_ticker = _latest_prices_by_date(valuations)
    dates = sorted({_as_date(v["valuation_date"]) for v in valuations})
    if len(dates) < 2:
        return {"status": "INSUFFICIENT_DATA", "reason": "Need at least two valuation dates.", "contributors": []}
    start_day = _as_date(start) if start else dates[0]
    end_day = _as_date(end) if end else dates[-1]
    contributors = []
    initial_total = final_total = 0.0
    for asset in holdings:
        rows = by_ticker.get(asset["ticker"].upper(), [])
        start_price = _latest_price_on_or_before(rows, start_day)
        end_price = _latest_price_on_or_before(rows, end_day)
        if not start_price or not end_price:
            continue
        qty = float(asset.get("quantity") or 0)
        start_value = _value_usd(qty, float(start_price["price"]), start_price.get("currency") or asset.get("currency") or "USD", exchange_rate, start_day, fx_rates, fx_max_age_days)
        end_value = _value_usd(qty, float(end_price["price"]), end_price.get("currency") or asset.get("currency") or "USD", exchange_rate, end_day, fx_rates, fx_max_age_days)
        initial_total += start_value
        final_total += end_value
        contributors.append({"ticker": asset["ticker"], "start_value_usd": round(start_value, 2), "end_value_usd": round(end_value, 2), "contribution_usd": round(end_value - start_value, 2)})
    contributors.sort(key=lambda item: item["contribution_usd"], reverse=True)
    return {
        "status": "AVAILABLE" if contributors else "INSUFFICIENT_DATA",
        "start": start_day.isoformat(),
        "end": end_day.isoformat(),
        "initial_value_usd": round(initial_total, 2),
        "final_value_usd": round(final_total, 2),
        "change_usd": round(final_total - initial_total, 2),
        "contributors": contributors,
        "top_winners": contributors[:3],
        "top_detractors": sorted(contributors, key=lambda item: item["contribution_usd"])[:3],
    }


def get_rebalancing_plan(assets: List[Dict[str, Any]], contribution_usd: float = 0.0, exchange_rate: float = 4050.0, fx_rates: Optional[List[Dict[str, Any]]] = None, fx_max_age_days: int = 5) -> Dict[str, Any]:
    summary = get_portfolio_summary(assets, exchange_rate, fx_rates, fx_max_age_days)
    total = float(summary["total_value_usd"])
    rows = []
    target_sum = sum(float(a.get("target_allocation_pct") or 0) for a in summary["holdings"])
    for asset in summary["holdings"]:
        target = float(asset.get("target_allocation_pct") or 0)
        current_value = float(asset["market_value_usd"])
        current_pct = (current_value / total * 100) if total else 0.0
        target_value = total * target / 100
        delta = target_value - current_value
        rows.append({"ticker": asset["ticker"], "current_pct": round(current_pct, 2), "target_pct": round(target, 2), "drift_pct": round(current_pct - target, 2), "trade_usd": round(delta, 2), "contribution_usd": 0.0})
    contribution_rows = _allocate_contribution(rows, contribution_usd)
    return {
        "status": "AVAILABLE" if target_sum > 0 and total > 0 else "INSUFFICIENT_DATA",
        "reason": None if target_sum > 0 and total > 0 else "Need portfolio value and target allocation percentages.",
        "traditional": rows,
        "new_contribution": contribution_rows,
        "contribution_usd": contribution_usd,
    }


def _allocate_contribution(rows: List[Dict[str, Any]], contribution_usd: float) -> List[Dict[str, Any]]:
    if contribution_usd <= 0:
        return [{**row, "contribution_usd": 0.0} for row in rows]
    underweight = [row for row in rows if row["trade_usd"] > 0]
    need = sum(row["trade_usd"] for row in underweight)
    result = []
    for row in rows:
        amount = (contribution_usd * row["trade_usd"] / need) if need > 0 and row["trade_usd"] > 0 else 0.0
        result.append({**row, "contribution_usd": round(amount, 2)})
    return result


def compare_benchmark(history: Dict[str, Any], benchmark_prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    series = history.get("series", [])
    coverage = _benchmark_alignment_coverage(series, benchmark_prices)
    if len(series) < 2 or len(benchmark_prices) < 2:
        return {"status": "INSUFFICIENT_DATA", "reason": "Need portfolio and benchmark history.", "excess_return_pct": None, "coverage": coverage, "beta": {"status": "INSUFFICIENT_DATA", "value": None, "reason": "Need aligned observations."}}
    benchmark_prices = sorted(benchmark_prices, key=lambda item: item["valuation_date"])
    portfolio_return = (float(series[-1]["portfolio_value_usd"]) / float(series[0]["portfolio_value_usd"]) - 1) if float(series[0]["portfolio_value_usd"]) > 0 else None
    benchmark_return = (float(benchmark_prices[-1]["price"]) / float(benchmark_prices[0]["price"]) - 1) if float(benchmark_prices[0]["price"]) > 0 else None
    if portfolio_return is None or benchmark_return is None:
        return {"status": "INSUFFICIENT_DATA", "reason": "Initial values must be positive.", "excess_return_pct": None, "coverage": coverage}
    beta = _benchmark_beta(series, benchmark_prices)
    return {"status": "AVAILABLE", "portfolio_return_pct": round(portfolio_return * 100, 2), "benchmark_return_pct": round(benchmark_return * 100, 2), "excess_return_pct": round((portfolio_return - benchmark_return) * 100, 2), "coverage": coverage, "beta": beta}


def _benchmark_alignment_coverage(series: List[Dict[str, Any]], benchmark_prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    portfolio_dates = {row["date"][:10] for row in series}
    benchmark_dates = {row["valuation_date"][:10] for row in benchmark_prices}
    aligned = sorted(portfolio_dates & benchmark_dates)
    return {
        "portfolio_observations": len(portfolio_dates),
        "benchmark_observations": len(benchmark_dates),
        "aligned_observations": len(aligned),
        "common_period": {"from": aligned[0], "to": aligned[-1]} if aligned else None,
    }


def _benchmark_beta(series: List[Dict[str, Any]], benchmark_prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    portfolio_by_date = {row["date"][:10]: float(row["portfolio_value_usd"]) for row in series if float(row.get("portfolio_value_usd") or 0) > 0}
    benchmark_by_date = {row["valuation_date"][:10]: float(row["price"]) for row in benchmark_prices if float(row.get("price") or 0) > 0}
    dates = sorted(set(portfolio_by_date) & set(benchmark_by_date))
    if len(dates) < 4:
        return {"status": "INSUFFICIENT_DATA", "value": None, "reason": "Need at least four aligned observations."}
    portfolio_returns = []
    benchmark_returns = []
    for prev, cur in zip(dates, dates[1:]):
        if portfolio_by_date[prev] <= 0 or benchmark_by_date[prev] <= 0:
            continue
        portfolio_returns.append((portfolio_by_date[cur] / portfolio_by_date[prev]) - 1)
        benchmark_returns.append((benchmark_by_date[cur] / benchmark_by_date[prev]) - 1)
    if len(portfolio_returns) < 3:
        return {"status": "INSUFFICIENT_DATA", "value": None, "reason": "Need at least three aligned return observations."}
    mean_p = sum(portfolio_returns) / len(portfolio_returns)
    mean_b = sum(benchmark_returns) / len(benchmark_returns)
    variance_b = sum((ret - mean_b) ** 2 for ret in benchmark_returns)
    if variance_b <= 0:
        return {"status": "INSUFFICIENT_DATA", "value": None, "reason": "Benchmark variance is zero."}
    covariance = sum((p - mean_p) * (b - mean_b) for p, b in zip(portfolio_returns, benchmark_returns))
    return {"status": "AVAILABLE", "value": round(covariance / variance_b, 4), "reason": None, "aligned_observations": len(dates)}


def get_total_return_breakdown(assets: List[Dict[str, Any]], operations: List[Dict[str, Any]], opening_positions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    realized = get_realized_pnl(operations, opening_positions=opening_positions)
    unrealized = get_unrealized_pnl_from_lots(assets, operations, opening_positions)
    income = get_investment_income(operations)
    cashflows = get_investment_cashflows(operations)
    return {
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "dividends": income["dividends_total"],
        "interest": income["interest_total"],
        "fees": income["fees_total"],
        "external_contributions": cashflows["total_external_cashflow"],
        "status": "AVAILABLE" if operations else "INSUFFICIENT_DATA",
    }


def get_wealth_action_items(data_quality: Dict[str, Any], concentration: Dict[str, Any], rebalancing: Dict[str, Any], ledger_reconciliation: Optional[Dict[str, Any]] = None, ledger_issues: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    items = []
    for issue in data_quality.get("issues", []):
        items.append({"type": issue["type"], "severity": "medium", "title": "Dato de cartera pendiente", "why": issue["message"], "action": issue["action"]})
    for alert in concentration.get("alerts", []):
        items.append({"type": f"concentration_{alert['type']}", "severity": alert["severity"], "title": "Concentración relevante", "why": alert["message"], "action": alert["action"]})
    for row in rebalancing.get("traditional", []):
        if abs(float(row.get("drift_pct") or 0)) >= 5 and float(row.get("target_pct") or 0) > 0:
            items.append({"type": "target_drift", "severity": "medium", "title": "Desviación frente al target", "why": f"{row['ticker']} está {row['drift_pct']} pp lejos del objetivo.", "action": "Revisar plan de rebalanceo."})
    for issue in (ledger_reconciliation or {}).get("issues", []):
        items.append({"type": issue["type"], "severity": "medium", "title": "Ledger vs Holdings", "why": issue["message"], "action": issue["action"]})
    for issue in ledger_issues or []:
        items.append({"type": issue["type"], "severity": "high", "title": "Ledger incompleto", "why": issue["message"], "action": issue["action"]})
    return items[:20]
