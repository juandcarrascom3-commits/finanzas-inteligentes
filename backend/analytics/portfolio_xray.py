"""Portfolio X-Ray look-through exposure analytics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional, Tuple

getcontext().prec = 28

TOLERANCE = Decimal("0.0001")


def _d(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _round(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def _pct(value: Decimal) -> float:
    return float((value * Decimal("100")).quantize(Decimal("0.01")))


def _security_identity(symbol: str, row: Optional[Dict[str, Any]] = None) -> str:
    row = row or {}
    for key in ["canonical_id", "security_id", "isin"]:
        if row.get(key):
            return f"{key}:{str(row[key]).upper()}"
    exchange = row.get("exchange")
    if exchange:
        return f"ticker_exchange:{str(symbol).upper()}:{str(exchange).upper()}"
    return f"symbol:{str(symbol).upper()}"


def _normalize_component(row: Dict[str, Any]) -> Dict[str, Any]:
    weight = _d(row.get("weight"))
    return {**row, "weight": _round(weight), "symbol": str(row.get("symbol") or row.get("ticker") or "").upper()}


def normalize_fund_composition_snapshot(symbol: str, provider: str, raw: Dict[str, Any], fetched_at: Optional[str] = None) -> Dict[str, Any]:
    reasons = list(raw.get("reasons") or [])
    status = raw.get("status") or "READY"
    holdings = [_normalize_component(row) for row in raw.get("holdings", []) if row.get("weight") is not None]
    asset_classes = [_normalize_component(row) for row in raw.get("asset_classes", []) if row.get("weight") is not None]
    sectors = [_normalize_component(row) for row in raw.get("sectors", []) if row.get("weight") is not None]
    negative = any(_d(row["weight"]) < 0 for row in holdings + asset_classes + sectors)
    for family, rows in [("holdings", holdings), ("asset_classes", asset_classes), ("sectors", sectors)]:
        total = sum((_d(row["weight"]) for row in rows), Decimal("0"))
        if total > Decimal("1.0001") or total < Decimal("-0.0001"):
            status = "PARTIAL"
            reasons.append(f"{family}_weight_total_invalid")
    if negative:
        status = "PARTIAL"
        reasons.append("negative_weights_unsupported")
    known_holdings_weight = sum((_d(row["weight"]) for row in holdings if _d(row["weight"]) > 0), Decimal("0"))
    residual = Decimal("1") - known_holdings_weight
    if residual < Decimal("0") and abs(residual) <= TOLERANCE:
        residual = Decimal("0")
    return {
        "symbol": symbol.upper(),
        "provider": provider.upper(),
        "fetched_at": fetched_at or datetime.now().isoformat(),
        "source_as_of": raw.get("source_as_of"),
        "status": status if holdings or asset_classes or sectors else "UNAVAILABLE",
        "reasons": sorted(set(reasons or ([] if holdings or asset_classes or sectors else ["no_composition_data"]))),
        "holdings": holdings,
        "asset_classes": asset_classes,
        "sectors": sectors,
        "known_holdings_weight": _round(max(known_holdings_weight, Decimal("0"))),
        "residual_weight": _round(max(residual, Decimal("0"))),
        "provenance": {"provider": provider.upper(), "fetched_at": fetched_at, "source_as_of": raw.get("source_as_of")},
    }


def _source_position(asset: Dict[str, Any], portfolio_value: Decimal) -> Optional[Dict[str, Any]]:
    value = _d(asset.get("market_value_usd"))
    if value <= 0 or portfolio_value <= 0:
        return None
    ticker = str(asset.get("ticker") or "").upper()
    return {
        "source_position_id": ticker,
        "source_symbol": ticker,
        "portfolio_weight": value / portfolio_value,
        "market_value_usd": value,
        "asset_type": asset.get("asset_type"),
        "sector": asset.get("sector"),
        "currency": asset.get("currency"),
        "provenance": asset.get("provenance") or "CANONICAL_HOLDING",
    }


def _contribution(source: Dict[str, Any], exposure_type: str, label: str, source_weight: Decimal, identity: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    effective = source["portfolio_weight"] * source_weight
    return {
        "source_position_id": source["source_position_id"],
        "source_symbol": source["source_symbol"],
        "exposure_type": exposure_type,
        "underlying_id": identity,
        "underlying_symbol": extra.get("symbol") if extra else None,
        "label": label,
        "portfolio_weight": _round(source["portfolio_weight"]),
        "source_weight": _round(source_weight),
        "effective_weight": _round(effective),
        "classification_source": extra.get("classification_source") if extra else None,
        "confidence": extra.get("confidence") if extra else "HIGH",
        "provenance": extra.get("provenance") if extra else source["provenance"],
    }


def _aggregate_contributions(contributions: List[Dict[str, Any]], dimension: str, portfolio_value: Decimal) -> Dict[str, Any]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in contributions:
        key = row["underlying_id"]
        if key not in grouped:
            grouped[key] = {"id": key, "label": row["label"], "effective_weight": Decimal("0"), "value_usd": Decimal("0"), "contributors": []}
        eff = _d(row["effective_weight"])
        grouped[key]["effective_weight"] += eff
        grouped[key]["value_usd"] += eff * portfolio_value
        grouped[key]["contributors"].append(row)
    items = []
    for item in grouped.values():
        contributors = sorted(item["contributors"], key=lambda row: (-float(row["effective_weight"]), row["source_symbol"]))
        items.append({
            "id": item["id"],
            "label": item["label"],
            "effective_weight": _round(item["effective_weight"]),
            "allocation_pct": _pct(item["effective_weight"]),
            "value_usd": _money(item["value_usd"]),
            "contributors": contributors,
        })
    items.sort(key=lambda item: (-item["effective_weight"], item["id"]))
    coverage = sum((_d(item["effective_weight"]) for item in items if "OPAQUE" not in item["id"] and "UNKNOWN_RESIDUAL" not in item["id"] and "UNCLASSIFIED" not in item["id"]), Decimal("0"))
    residual = sum((_d(item["effective_weight"]) for item in items if "UNKNOWN_RESIDUAL" in item["id"]), Decimal("0"))
    opaque = sum((_d(item["effective_weight"]) for item in items if "OPAQUE" in item["id"]), Decimal("0"))
    unclassified = sum((_d(item["effective_weight"]) for item in items if "UNCLASSIFIED" in item["id"]), Decimal("0"))
    reasons = []
    if residual > 0:
        reasons.append("UNKNOWN_RESIDUAL_PRESENT")
    if opaque > 0:
        reasons.append("OPAQUE_POSITIONS_PRESENT")
    if unclassified > 0:
        reasons.append("UNCLASSIFIED_PRESENT")
    return {
        "dimension": dimension,
        "status": "READY" if not reasons else "PARTIAL",
        "coverage_ratio": _round(coverage),
        "coverage_pct": _pct(coverage),
        "classified_ratio": _round(coverage),
        "items": items,
        "residual_weight": _round(residual),
        "unclassified_weight": _round(unclassified),
        "opaque_weight": _round(opaque),
        "reasons": reasons,
    }


def calculate_portfolio_exposure(assets: List[Dict[str, Any]], fund_compositions: Dict[str, Dict[str, Any]], base_currency: str = "USD") -> Dict[str, Any]:
    active = [asset for asset in assets if not asset.get("is_watchlist") and _d(asset.get("market_value_usd")) > 0]
    portfolio_value = sum((_d(asset.get("market_value_usd")) for asset in active), Decimal("0"))
    if portfolio_value <= 0:
        return {
            "status": "UNEVALUABLE",
            "reason": "MISSING_VALUATION",
            "base_currency": base_currency,
            "portfolio_value": 0,
            "lenses": {},
            "intersections": [],
            "opaque_positions": [],
            "concentration": {"status": "DEFERRED", "reason": "Exposure unavailable without canonical valuation."},
            "provenance": {"positions": "canonical_effective_holdings", "valuations": "canonical_market_value_usd", "fund_compositions": "market_data_cache"},
        }

    asset_class_contribs: List[Dict[str, Any]] = []
    sector_contribs: List[Dict[str, Any]] = []
    underlying_contribs: List[Dict[str, Any]] = []
    opaque_positions = []
    reasons = []

    for asset in active:
        source = _source_position(asset, portfolio_value)
        if not source:
            reasons.append(f"missing_valuation:{asset.get('ticker')}")
            continue
        ticker = source["source_symbol"]
        asset_type = str(asset.get("asset_type") or "").upper()
        composition = fund_compositions.get(ticker)
        is_fund = asset_type in {"ETF", "FUND", "MUTUAL_FUND", "INDEX_FUND"} or bool(composition)
        if is_fund:
            if not composition or composition.get("status") not in {"READY", "PARTIAL"}:
                opaque_positions.append({"ticker": ticker, "portfolio_weight": _round(source["portfolio_weight"]), "reason": "MISSING_FUND_COMPOSITION"})
                asset_class_contribs.append(_contribution(source, "ASSET_CLASS", "OPAQUE", Decimal("1"), "OPAQUE", {"symbol": ticker, "provenance": "FUND_COMPOSITION_MISSING"}))
                sector_contribs.append(_contribution(source, "SECTOR", "OPAQUE", Decimal("1"), "OPAQUE", {"symbol": ticker, "provenance": "FUND_COMPOSITION_MISSING"}))
                underlying_contribs.append(_contribution(source, "UNDERLYING_SECURITY", "OPAQUE", Decimal("1"), f"OPAQUE:{ticker}", {"symbol": ticker, "provenance": "FUND_COMPOSITION_MISSING"}))
                reasons.append(f"missing_fund_composition:{ticker}")
                continue
            if any(reason in set(composition.get("reasons") or []) for reason in {"negative_weights_unsupported", "holdings_weight_total_invalid", "asset_classes_weight_total_invalid", "sectors_weight_total_invalid"}):
                opaque_positions.append({"ticker": ticker, "portfolio_weight": _round(source["portfolio_weight"]), "reason": "INVALID_FUND_COMPOSITION"})
                asset_class_contribs.append(_contribution(source, "ASSET_CLASS", "OPAQUE", Decimal("1"), f"OPAQUE:{ticker}", {"symbol": ticker, "provenance": composition["provider"]}))
                sector_contribs.append(_contribution(source, "SECTOR", "OPAQUE", Decimal("1"), f"OPAQUE:{ticker}", {"symbol": ticker, "provenance": composition["provider"]}))
                underlying_contribs.append(_contribution(source, "UNDERLYING_SECURITY", "OPAQUE", Decimal("1"), f"OPAQUE:{ticker}", {"symbol": ticker, "provenance": composition["provider"]}))
                reasons.append(f"invalid_fund_composition:{ticker}")
                continue
            for row in composition.get("asset_classes", []):
                asset_class_contribs.append(_contribution(source, "ASSET_CLASS", row.get("label") or row.get("symbol") or "UNCLASSIFIED", _d(row["weight"]), f"asset_class:{str(row.get('label') or row.get('symbol')).upper()}", {"symbol": row.get("symbol"), "provenance": composition["provider"], "classification_source": "FUND_COMPOSITION"}))
            if not composition.get("asset_classes"):
                asset_class_contribs.append(_contribution(source, "ASSET_CLASS", "UNCLASSIFIED", Decimal("1"), f"UNCLASSIFIED_ASSET_CLASS:{ticker}", {"symbol": ticker, "provenance": composition["provider"]}))
            for row in composition.get("sectors", []):
                sector_contribs.append(_contribution(source, "SECTOR", row.get("label") or row.get("symbol") or "UNCLASSIFIED_SECTOR", _d(row["weight"]), f"sector:{str(row.get('label') or row.get('symbol')).upper()}", {"symbol": row.get("symbol"), "provenance": composition["provider"], "classification_source": "FUND_COMPOSITION"}))
            if not composition.get("sectors"):
                sector_contribs.append(_contribution(source, "SECTOR", "UNCLASSIFIED_SECTOR", Decimal("1"), f"UNCLASSIFIED_SECTOR:{ticker}", {"symbol": ticker, "provenance": composition["provider"]}))
            for row in composition.get("holdings", []):
                identity = _security_identity(row.get("symbol") or row.get("label"), row)
                underlying_contribs.append(_contribution(source, "UNDERLYING_SECURITY", row.get("label") or row.get("symbol") or identity, _d(row["weight"]), identity, {"symbol": row.get("symbol"), "provenance": composition["provider"], "classification_source": "FUND_HOLDING"}))
            residual = _d(composition.get("residual_weight"))
            if residual > TOLERANCE:
                underlying_contribs.append(_contribution(source, "UNDERLYING_SECURITY", "UNKNOWN_RESIDUAL", residual, f"UNKNOWN_RESIDUAL:{ticker}", {"symbol": ticker, "provenance": composition["provider"]}))
            continue
        class_label = asset.get("asset_type") or "UNCLASSIFIED"
        sector_label = asset.get("sector") or "UNCLASSIFIED_SECTOR"
        asset_class_contribs.append(_contribution(source, "ASSET_CLASS", class_label, Decimal("1"), f"asset_class:{str(class_label).upper()}", {"symbol": ticker, "provenance": source["provenance"], "classification_source": "CANONICAL_ASSET"}))
        sector_contribs.append(_contribution(source, "SECTOR", sector_label, Decimal("1"), f"sector:{str(sector_label).upper()}" if asset.get("sector") else f"UNCLASSIFIED_SECTOR:{ticker}", {"symbol": ticker, "provenance": source["provenance"], "classification_source": "CANONICAL_ASSET"}))
        underlying_contribs.append(_contribution(source, "UNDERLYING_SECURITY", ticker, Decimal("1"), _security_identity(ticker, asset), {"symbol": ticker, "provenance": source["provenance"], "classification_source": "DIRECT_HOLDING"}))

    lenses = {
        "asset_class": _aggregate_contributions(asset_class_contribs, "asset_class", portfolio_value),
        "sector": _aggregate_contributions(sector_contribs, "sector", portfolio_value),
        "underlying_security": _aggregate_contributions(underlying_contribs, "underlying_security", portfolio_value),
    }
    intersections = [
        {"id": item["id"], "label": item["label"], "effective_weight": item["effective_weight"], "allocation_pct": item["allocation_pct"], "contributors": item["contributors"]}
        for item in lenses["underlying_security"]["items"]
        if len({row["source_symbol"] for row in item["contributors"]}) >= 2
    ]
    status = "PARTIAL" if reasons or any(lens["status"] == "PARTIAL" for lens in lenses.values()) else "READY"
    return {
        "as_of": datetime.now().date().isoformat(),
        "base_currency": base_currency,
        "portfolio_value": _money(portfolio_value),
        "status": status,
        "reasons": sorted(set(reasons)),
        "valuation_coverage": 1.0,
        "lenses": lenses,
        "intersections": intersections,
        "opaque_positions": opaque_positions,
        "concentration": {"status": "DEFERRED", "reason": "Existing concentration primitive is visible-holding based and uses allocation_pct percentages; underlying partial-weight concentration would risk analyzable-subset renormalization confusion."},
        "provenance": {"positions": "canonical_effective_holdings", "valuations": "canonical_market_value_usd", "fund_compositions": "market_data_cache"},
    }
