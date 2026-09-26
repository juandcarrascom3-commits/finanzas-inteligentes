"""Market data sync and local valuation helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from database.db_manager import DatabaseManager
from backend.integrations.market_data_provider import MarketDataProvider, get_market_provider
from backend.integrations.provider_security import sanitize_provider_message
from backend.analytics.portfolio_xray import normalize_fund_composition_snapshot


def _today() -> str:
    return date.today().isoformat()


def _days_between(a: str, b: str) -> int:
    return (datetime.fromisoformat(a[:10]).date() - datetime.fromisoformat(b[:10]).date()).days


def _next_day(day: str) -> str:
    return (datetime.fromisoformat(day[:10]).date() + timedelta(days=1)).isoformat()


def _start_lookback(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _is_provider_compatible(symbol: str) -> bool:
    value = (symbol or "").strip()
    if not value or " " in value:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-=^/")
    return all(char.upper() in allowed for char in value)


def resolve_market_symbol(db: DatabaseManager, internal_symbol: str, provider_name: str = "YFINANCE") -> Dict[str, Any]:
    internal = internal_symbol.upper()
    provider = provider_name.upper()
    mappings = db.get_symbol_mappings(provider=provider, internal_symbol=internal)
    active = next((row for row in mappings if row.get("status") in {"ACTIVE", "VALIDATED"}), None)
    if active:
        return {"status": "RESOLVED", "internal_symbol": internal, "provider": provider, "provider_symbol": active["provider_symbol"], "source": "MAPPING", "mapping": active}
    if _is_provider_compatible(internal):
        return {"status": "RESOLVED", "internal_symbol": internal, "provider": provider, "provider_symbol": internal, "source": "INTERNAL_SYMBOL", "mapping": None}
    return {"status": "UNRESOLVED", "internal_symbol": internal, "provider": provider, "provider_symbol": None, "source": "UNRESOLVED", "mapping": None}


def convert_currency(db: DatabaseManager, amount: float, from_currency: str, to_currency: str, conversion_date: str, max_age_days: Optional[int] = None) -> Dict[str, Any]:
    source = (from_currency or "USD").upper()
    target = (to_currency or "USD").upper()
    if source == target:
        return {"status": "AVAILABLE", "amount": round(float(amount), 6), "rate": 1.0, "source": "IDENTITY", "rate_date": conversion_date[:10]}
    config = db.get_market_data_config()
    max_age = int(max_age_days if max_age_days is not None else config.get("fx_max_age_days") or 5)
    direct = db.get_fx_rate_on_or_before(source, target, conversion_date, max_age_days=max_age)
    if direct:
        return {"status": "AVAILABLE", "amount": round(float(amount) * float(direct["rate"]), 6), "rate": float(direct["rate"]), "source": direct.get("provider"), "rate_date": direct.get("rate_date")}
    inverse = db.get_fx_rate_on_or_before(target, source, conversion_date, max_age_days=max_age)
    if inverse:
        rate = 1 / float(inverse["rate"])
        return {"status": "AVAILABLE", "amount": round(float(amount) * rate, 6), "rate": rate, "source": inverse.get("provider"), "rate_date": inverse.get("rate_date")}
    return {"status": "INSUFFICIENT_FX_DATA", "amount": None, "rate": None, "source": None, "rate_date": None, "reason": f"Missing {source}/{target} FX near {conversion_date[:10]}."}


def market_price_status(row: Optional[Dict[str, Any]], stale_after_days: int) -> str:
    if not row:
        return "UNAVAILABLE"
    if row.get("source") == "MANUAL":
        return "MANUAL"
    age = _days_between(_today(), row["valuation_date"])
    return "FRESH" if age <= stale_after_days else "STALE"


def apply_market_prices(db: DatabaseManager, holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    config = db.get_market_data_config()
    stale_after = int(config.get("stale_after_days") or 7)
    latest_market = db.get_latest_asset_valuations(source="MARKET_DATA")
    authority = {row["ticker"].upper(): row for row in db.get_price_authority()}
    enriched = []
    issues = []
    for asset in holdings:
        ticker = asset["ticker"].upper()
        market = latest_market.get(ticker)
        authority_row = authority.get(ticker, {})
        mode = authority_row.get("authority_mode", "AUTO")
        manual_price = float(authority_row.get("manual_price") or asset.get("current_price") or 0)
        status = market_price_status(market, stale_after)
        chosen = "UNAVAILABLE"
        price = manual_price
        currency = (authority_row.get("manual_currency") or asset.get("currency") or "USD").upper()
        provider = None
        valuation_date = None
        retrieved_at = authority_row.get("manual_updated_at")
        if mode == "MANUAL":
            if manual_price > 0:
                chosen = "MANUAL"
                status = "MANUAL"
            else:
                status = "UNAVAILABLE"
                issues.append({"type": "missing_manual_price", "ticker": ticker, "message": f"{ticker} está en MANUAL sin precio manual.", "action": "Registrar precio manual o volver a AUTO."})
        elif status == "FRESH":
            price = float(market["price"])
            currency = (market.get("currency") or currency).upper()
            chosen = "MARKET_DATA"
            provider = market.get("provider")
            valuation_date = market.get("valuation_date")
            retrieved_at = market.get("retrieved_at")
        elif manual_price > 0:
            chosen = "MANUAL"
            status = "MANUAL"
        elif market:
            price = float(market["price"])
            currency = (market.get("currency") or currency).upper()
            chosen = "MARKET_DATA"
            status = "STALE"
            provider = market.get("provider")
            valuation_date = market.get("valuation_date")
            retrieved_at = market.get("retrieved_at")
        else:
            issues.append({"type": "missing_market_price", "ticker": ticker, "message": f"{ticker} no tiene precio de mercado ni precio manual.", "action": "Actualizar market data o registrar valoración manual."})
        if status == "STALE":
            issues.append({"type": "stale_price", "ticker": ticker, "message": f"{ticker} usa precio antiguo de {valuation_date}.", "action": "Actualizar datos de mercado."})
        enriched.append({
            **asset,
            "current_price": price,
            "currency": currency,
            "price_status": status,
            "price_source": chosen,
            "price_provider": provider,
            "price_date": valuation_date,
            "price_retrieved_at": retrieved_at,
            "price_authority": mode,
            "manual_price": authority_row.get("manual_price"),
            "manual_currency": authority_row.get("manual_currency"),
        })
    return {"holdings": enriched, "issues": issues, "status": "AVAILABLE" if not issues else "PARTIAL_DATA"}


def get_market_coverage(db: DatabaseManager, holdings: Optional[List[Dict[str, Any]]] = None, benchmark_key: Optional[str] = None) -> Dict[str, Any]:
    config = db.get_market_data_config()
    latest = db.get_latest_asset_valuations(source="MARKET_DATA")
    fx = db.get_fx_rates()
    stale_after = int(config.get("stale_after_days") or 7)
    priced = apply_market_prices(db, holdings or [])
    rows = []
    total_value = 0.0
    fresh_value = 0.0
    unresolved = []
    missing_fx = []
    for asset in priced["holdings"]:
        ticker = asset["ticker"].upper()
        resolved = resolve_market_symbol(db, ticker, config.get("provider") or "YFINANCE")
        history = db.get_asset_valuations(ticker=ticker)
        history_count = len([row for row in history if row.get("source") == "MARKET_DATA"])
        fx_status = "OK"
        if (asset.get("currency") or "USD").upper() != "USD":
            fx_row = db.get_fx_rate_on_or_before((asset.get("currency") or "USD").upper(), "USD", _today(), int(config.get("fx_max_age_days") or 5))
            fx_status = "OK" if fx_row else "MISSING_FX"
            if not fx_row:
                missing_fx.append(f"{asset.get('currency')}/USD")
        if resolved["status"] == "UNRESOLVED":
            unresolved.append(ticker)
        status = "OK"
        if resolved["status"] == "UNRESOLVED":
            status = "UNRESOLVED_SYMBOL"
        elif asset.get("price_status") == "UNAVAILABLE":
            status = "MISSING_PRICE"
        elif asset.get("price_status") == "STALE":
            status = "STALE"
        elif history_count == 0:
            status = "MISSING_HISTORY"
        elif fx_status != "OK":
            status = "MISSING_FX"
        value = float(asset.get("quantity") or 0) * float(asset.get("current_price") or 0)
        total_value += value
        if asset.get("price_status") == "FRESH":
            fresh_value += value
        rows.append({
            "ticker": ticker,
            "provider": resolved["provider"],
            "provider_symbol": resolved.get("provider_symbol"),
            "symbol_status": resolved["status"],
            "mapping_source": resolved["source"],
            "current_price": asset.get("current_price"),
            "currency": asset.get("currency"),
            "freshness": asset.get("price_status"),
            "price_source": asset.get("price_source"),
            "price_authority": asset.get("price_authority"),
            "history_count": history_count,
            "fx_status": fx_status,
            "status": status,
        })
    benchmark_prices = db.get_benchmark_prices(benchmark_key=benchmark_key or config.get("benchmark_symbol")) if (benchmark_key or config.get("benchmark_symbol")) else []
    return {
        "rows": rows,
        "summary": {
            "holdings_total": len(rows),
            "holdings_ok": len([row for row in rows if row["status"] == "OK"]),
            "fresh_value_pct": round((fresh_value / total_value * 100) if total_value else 0.0, 2),
            "stale_count": len([row for row in rows if row["status"] == "STALE"]),
            "unresolved_symbols": unresolved,
            "missing_fx": sorted(set(missing_fx)),
            "benchmark_status": "OK" if len(benchmark_prices) >= 2 else "INSUFFICIENT_DATA",
            "benchmark_observations": len(benchmark_prices),
        },
    }


def get_market_data_status(db: DatabaseManager, holdings: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    config = db.get_market_data_config()
    latest = db.get_latest_asset_valuations(source="MARKET_DATA")
    fx = db.get_fx_rates()
    tickers = [row["ticker"].upper() for row in holdings or [] if not row.get("is_watchlist")]
    stale_after = int(config.get("stale_after_days") or 7)
    stale = []
    missing = []
    for ticker in tickers:
        row = latest.get(ticker)
        status = market_price_status(row, stale_after)
        if status == "UNAVAILABLE":
            missing.append(ticker)
        elif status == "STALE":
            stale.append(ticker)
    state = db.get_sync_state("MARKET_DATA")
    provider_health = "AVAILABLE"
    if state.get("status") == "FAILED":
        provider_health = "OFFLINE"
    elif state.get("status") == "PARTIAL" or state.get("last_error"):
        provider_health = "DEGRADED"
    coverage = get_market_coverage(db, holdings or [], benchmark_key=config.get("benchmark_symbol"))
    return {
        "provider": config.get("provider") or "YFINANCE",
        "benchmark_symbol": config.get("benchmark_symbol"),
        "last_sync_at": state.get("last_sync_at"),
        "last_success_at": state.get("last_success_at"),
        "last_error": state.get("last_error"),
        "updated_assets": len(latest),
        "fx_pairs": len({f"{row['base_currency']}/{row['quote_currency']}" for row in fx}),
        "stale_tickers": stale,
        "missing_tickers": missing,
        "status": state.get("status") or "NOT_SYNCED",
        "provider_health": provider_health,
        "coverage": coverage,
        "price_policy": "External fresh > manual current price > stale external > unavailable.",
        "history_policy": "Adjusted close from provider when available; no provider calls during normal reads.",
    }


def _fund_cache_key(provider: str, symbol: str) -> str:
    return f"fund_composition:{provider.upper()}:{symbol.upper()}"


def get_cached_fund_compositions(db: DatabaseManager, symbols: List[str], provider_name: str = "YFINANCE") -> Dict[str, Dict[str, Any]]:
    snapshots: Dict[str, Dict[str, Any]] = {}
    for symbol in sorted({s.upper() for s in symbols if s}):
        cached = db.get_market_cache(_fund_cache_key(provider_name, symbol))
        if cached:
            snapshots[symbol] = cached["payload"]
    return snapshots


def refresh_fund_compositions(db: DatabaseManager, symbols: List[str], provider: Optional[MarketDataProvider] = None) -> Dict[str, Any]:
    config = db.get_market_data_config()
    provider = provider or get_market_provider(config.get("provider") or "YFINANCE")
    now = datetime.now().isoformat()
    ttl = int(config.get("quote_ttl_minutes") or 720)
    expires = (datetime.now() + timedelta(minutes=ttl)).isoformat()
    rows = []
    errors = []
    for symbol in sorted({s.upper() for s in symbols if s}):
        try:
            raw = provider.get_etf_holdings(symbol)
            snapshot = normalize_fund_composition_snapshot(symbol, provider.name, raw, fetched_at=now)
            db.set_market_cache(_fund_cache_key(provider.name, symbol), snapshot, provider.name, expires)
            rows.append({"symbol": symbol, "status": snapshot["status"], "known_holdings_weight": snapshot["known_holdings_weight"], "residual_weight": snapshot["residual_weight"], "reasons": snapshot["reasons"]})
        except Exception as exc:
            message = sanitize_provider_message(str(exc))
            rows.append({"symbol": symbol, "status": "FAILED", "error": message})
            errors.append({"symbol": symbol, "error": message})
    status = "PARTIAL" if errors else "CONNECTED"
    db.set_sync_state("FUND_COMPOSITIONS", {"status": status, "last_sync_at": now, "last_success_at": now if not errors else None, "last_error": errors[0]["error"] if errors else None})
    return {"provider": provider.name, "status": status, "started_at": now, "completed_at": datetime.now().isoformat(), "symbols": rows, "errors": errors}


def _relevant_fx_pairs(holdings: List[Dict[str, Any]], operations: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    currencies = {(row.get("currency") or "USD").upper() for row in holdings}
    currencies.update({(row.get("currency") or "USD").upper() for row in operations})
    return {("USD", cur) for cur in currencies if cur and cur != "USD"}


def _last_market_date(rows: List[Dict[str, Any]]) -> Optional[str]:
    market_rows = [row for row in rows if row.get("source") == "MARKET_DATA"]
    if not market_rows:
        return None
    return max(row["valuation_date"] for row in market_rows)


def sync_market_data(db: DatabaseManager, provider: Optional[MarketDataProvider] = None, include_watchlist: bool = False, benchmark_symbol: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, mode: str = "FULL") -> Dict[str, Any]:
    config = db.get_market_data_config()
    provider = provider or get_market_provider(config.get("provider") or "YFINANCE")
    sync_mode = (mode or "FULL").upper()
    end_date = (end or _today())[:10]
    start_default = start or _start_lookback(int(config.get("history_lookback_days") or 365))
    assets = db.get_assets(include_watchlist=include_watchlist)
    holdings = [a for a in assets if not a.get("is_watchlist") and float(a.get("quantity") or 0) > 0]
    holding_by_ticker = {row["ticker"].upper(): row for row in holdings}
    operations = db.get_investment_transactions()
    tickers = sorted({row["ticker"].upper() for row in holdings if row.get("ticker")})
    result = {"provider": provider.name, "mode": sync_mode, "started_at": datetime.now().isoformat(), "assets": [], "fx": [], "benchmark": None, "errors": []}

    for ticker in tickers:
        resolved = resolve_market_symbol(db, ticker, provider.name)
        if resolved["status"] == "UNRESOLVED":
            result["assets"].append({"ticker": ticker, "status": "UNRESOLVED_SYMBOL", "provider_symbol": None})
            result["errors"].append({"symbol": ticker, "error": "Unresolved provider symbol."})
            continue
        provider_symbol = resolved["provider_symbol"]
        try:
            existing = db.get_asset_valuations(ticker=ticker)
            last = _last_market_date(existing)
            cached = db.get_market_cache(f"quote:{provider.name}:{provider_symbol}")
            quote = cached["payload"] if cached else provider.get_quote(provider_symbol).to_dict()
            if not cached:
                expires = (datetime.now() + timedelta(minutes=int(config.get("quote_ttl_minutes") or 720))).isoformat()
                db.set_market_cache(f"quote:{provider.name}:{provider_symbol}", quote, provider.name, expires)
            db.save_asset_valuation({
                "ticker": ticker,
                "price": quote["price"],
                "currency": quote.get("currency") or holding_by_ticker.get(ticker, {}).get("currency") or "USD",
                "valuation_date": quote.get("as_of") or end_date,
                "source": "MARKET_DATA",
                "provider": provider.name,
                "retrieved_at": quote.get("retrieved_at"),
                "metadata": {**(quote.get("metadata") or {}), "provider_symbol": provider_symbol, "symbol_source": resolved["source"]},
            })
            history_start = _next_day(last) if last else start_default[:10]
            history_count = 0
            if sync_mode == "FULL" and history_start <= end_date:
                for row in provider.get_price_history(provider_symbol, history_start, end_date):
                    db.save_asset_valuation({
                        "ticker": ticker,
                        "price": row.price,
                        "currency": row.currency,
                        "valuation_date": row.price_date,
                        "source": "MARKET_DATA",
                        "provider": row.provider,
                        "retrieved_at": row.retrieved_at,
                        "metadata": {**row.metadata, "provider_symbol": provider_symbol, "symbol_source": resolved["source"]},
                    })
                    history_count += 1
            result["assets"].append({"ticker": ticker, "provider_symbol": provider_symbol, "status": "UPDATED", "history_rows": history_count})
        except Exception as exc:
            message = sanitize_provider_message(str(exc))
            result["assets"].append({"ticker": ticker, "status": "FAILED", "error": message})
            result["errors"].append({"symbol": ticker, "error": message})

    for base, quote in sorted(_relevant_fx_pairs(holdings, operations)):
        pair = f"{base}/{quote}"
        try:
            fx_start = start_default if sync_mode == "FULL" else end_date
            fx_rows = provider.get_fx_history(pair, fx_start, end_date)
            count = 0
            for row in fx_rows:
                db.save_fx_rate({
                    "base_currency": base,
                    "quote_currency": quote,
                    "rate": row.price,
                    "rate_date": row.price_date,
                    "provider": row.provider,
                    "source": "MARKET_DATA",
                    "retrieved_at": row.retrieved_at,
                    "metadata": row.metadata,
                })
                count += 1
            result["fx"].append({"pair": pair, "status": "UPDATED", "rows": count})
        except Exception as exc:
            message = sanitize_provider_message(str(exc))
            result["fx"].append({"pair": pair, "status": "FAILED", "error": message})
            result["errors"].append({"symbol": pair, "error": message})

    bench = (benchmark_symbol if benchmark_symbol is not None else config.get("benchmark_symbol") or "").upper()
    if bench:
        resolved_benchmark = resolve_market_symbol(db, bench, provider.name)
        bench_provider_symbol = resolved_benchmark.get("provider_symbol") or bench
        try:
            bench_start = start_default if sync_mode == "FULL" else end_date
            rows = provider.get_benchmark_history(bench_provider_symbol, bench_start, end_date)
            count = 0
            for row in rows:
                db.save_benchmark_price({
                    "benchmark_key": bench,
                    "label": config.get("benchmark_label") or bench,
                    "price": row.price,
                    "currency": row.currency,
                    "valuation_date": row.price_date,
                    "source": "MARKET_DATA",
                    "provider": row.provider,
                    "retrieved_at": row.retrieved_at,
                    "metadata": {**row.metadata, "provider_symbol": bench_provider_symbol, "symbol_source": resolved_benchmark["source"]},
                })
                count += 1
            result["benchmark"] = {"symbol": bench, "provider_symbol": bench_provider_symbol, "status": "UPDATED", "rows": count}
        except Exception as exc:
            message = sanitize_provider_message(str(exc))
            result["benchmark"] = {"symbol": bench, "status": "FAILED", "error": message}
            result["errors"].append({"symbol": bench, "error": message})

    now = datetime.now().isoformat()
    status = "PARTIAL" if result["errors"] else "CONNECTED"
    db.set_sync_state("MARKET_DATA", {"status": status, "last_sync_at": now, "last_success_at": now if status == "CONNECTED" else None, "last_error": result["errors"][0]["error"] if result["errors"] else None})
    result["completed_at"] = now
    result["status"] = status
    return result
