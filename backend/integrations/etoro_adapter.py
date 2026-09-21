"""eToro read-only adapter.

eToro API -> Adapter -> Canonical investment operations -> Preview -> Ledger.
Trading/order endpoints are intentionally not implemented here.
"""

import json
import logging
import os
import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EtoroAuthError(Exception):
    def __init__(self, message: str, diagnostic: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.diagnostic = diagnostic or {}


class EtoroRateLimitError(Exception):
    def __init__(self, message: str, retry_after: Optional[str] = None):
        super().__init__(message)
        self.retry_after = retry_after


class EtoroNetworkError(Exception):
    def __init__(self, message: str, diagnostic: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.diagnostic = diagnostic or {}


class EtoroAdapter:
    source = "ETORO"
    user_agent = "FinancePersonal/1.0"
    reconciliation_tolerance = 0.05

    def __init__(
        self,
        api_key: Optional[str] = None,
        user_key: Optional[str] = None,
        base_url: Optional[str] = None,
        environment: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.api_key = self._clean_env_value(api_key if api_key is not None else os.getenv("ETORO_API_KEY", ""))
        self.user_key = self._clean_env_value(user_key if user_key is not None else os.getenv("ETORO_USER_KEY", ""))
        self.base_url = self._clean_env_value(base_url or os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com/api/v1")).rstrip("/")
        self.environment = self._clean_env_value(environment or os.getenv("ETORO_ENVIRONMENT", "demo")).lower()
        if self.environment not in {"demo", "real"}:
            self.environment = "demo"
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key and self.user_key)

    def test_connection(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"status": "NOT_CONFIGURED", "message": "ETORO_API_KEY y ETORO_USER_KEY no están configurados."}
        started = time.time()
        data, meta = self.fetch_portfolio()
        return {
            "status": "CONNECTED",
            "environment": self.environment,
            "elapsed_ms": round((time.time() - started) * 1000),
            "sample_count": len(self.extract_items(data, "positions")),
            "rate_limit": meta.get("rate_limit"),
        }

    def fetch_portfolio(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return self._get(self._portfolio_path())

    def fetch_pnl(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return self._get(self._pnl_path())

    def fetch_history(self, min_date: Optional[str] = None, page_size: int = 200, max_pages: int = 50) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        duplicates = 0
        identity_conflicts = 0
        pages = 0
        meta: Dict[str, Any] = {"endpoint": self._history_path(), "page_start": 1, "page_size": page_size}
        seen_exact = set()
        seen_by_primary: Dict[str, str] = {}
        stop_reason = "MAX_PAGES"
        clean_min_date = min_date or self._clean_env_value(os.getenv("ETORO_HISTORY_MIN_DATE", "")) or "2000-01-01"

        for page in range(1, max_pages + 1):
            params: Dict[str, Any] = {"page": page, "pageSize": page_size}
            params["minDate"] = clean_min_date
            data, page_meta = self._get(self._history_path(), params)
            meta.update(page_meta)
            rows = self.extract_items(data, "history")
            pages += 1
            if not rows:
                stop_reason = "EMPTY_PAGE"
                break

            new_identities = 0
            for raw in rows:
                primary, fingerprint = self._history_identity(raw)
                exact_key = f"{primary}:{fingerprint}"
                if exact_key in seen_exact:
                    duplicates += 1
                    continue
                row = dict(raw)
                row["_etoro_identity"] = exact_key
                if primary in seen_by_primary and seen_by_primary[primary] != fingerprint:
                    row["_etoro_identity_conflict"] = True
                    identity_conflicts += 1
                seen_by_primary[primary] = fingerprint
                seen_exact.add(exact_key)
                items.append(row)
                new_identities += 1

            if new_identities == 0:
                stop_reason = "NO_NEW_IDENTITIES"
                break
        else:
            stop_reason = "MAX_PAGES"

        return {
            "items": items,
            "pages": pages,
            "meta": {**meta, "stop_reason": stop_reason},
            "history_status": "READY",
            "trade_history_status": "READY",
            "rows_downloaded": len(items),
            "duplicate_rows": duplicates,
            "identity_conflicts": identity_conflicts,
            "stop_reason": stop_reason,
        }

    def fetch_instrument_metadata(self, instrument_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return self._get("/market-data/search", {"instrumentId": instrument_id, "pageSize": 1})

    def fetch_metadata_for_instruments(self, instrument_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        metadata_by_instrument: Dict[str, Dict[str, Any]] = {}
        for instrument_id in sorted({str(value) for value in instrument_ids if str(value or "")}):
            payload, _ = self.fetch_instrument_metadata(instrument_id)
            items = self.extract_items(payload, "instruments")
            metadata_by_instrument[instrument_id] = items[0] if items else payload
        return metadata_by_instrument

    def normalize_history_rows(
        self,
        rows: List[Dict[str, Any]],
        metadata_by_instrument: Optional[Dict[str, Dict[str, Any]]] = None,
        instrument_mappings: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        metadata_by_instrument = metadata_by_instrument or {}
        mappings = instrument_mappings or {}
        operations: List[Dict[str, Any]] = []
        accepted_rows: List[Dict[str, Any]] = []
        rejected_rows: List[Dict[str, Any]] = []
        unsupported_rows: List[Dict[str, Any]] = []
        partial_rows: List[Dict[str, Any]] = []
        net_profit_reconciliation: List[Dict[str, Any]] = []
        periods: List[str] = []

        for index, raw in enumerate(rows, start=1):
            status, reason = self._classify_history_row(raw)
            instrument_id = self._history_instrument_id(raw)
            metadata = metadata_by_instrument.get(str(instrument_id), {})
            ticker = self._history_ticker(raw, metadata, mappings)
            raw_net_profit = self._first(raw, ["netProfit"])
            if not ticker and status == "SUPPORTED_DIRECT":
                status, reason = "PARTIAL_DATA", "Missing confirmed ticker/mapping for eToro instrument."

            normalized = {
                "source": self.source,
                "environment": self.environment.upper(),
                "classification": status,
                "reason": reason,
                "positionId": self._first(raw, ["positionId", "positionID"]),
                "parentPositionId": self._first(raw, ["parentPositionId", "parentPositionID"]),
                "orderId": self._first(raw, ["orderId", "orderID"]),
                "instrumentId": instrument_id,
                "socialTradeId": self._first(raw, ["socialTradeId", "socialTradeID"]),
                "ticker": ticker,
                "openTimestamp": self._first(raw, ["openTimestamp", "openDateTime", "openDate"]),
                "closeTimestamp": self._first(raw, ["closeTimestamp", "closeDateTime", "closeDate"]),
                "units": self._num(self._first(raw, ["units", "quantity"])),
                "openRate": self._num(self._first(raw, ["openRate"])),
                "closeRate": self._num(self._first(raw, ["closeRate"])),
                "investment": self._num(self._first(raw, ["investment"])),
                "initialInvestment": self._num(self._first(raw, ["initialInvestment"])),
                "fees": self._num(self._first(raw, ["fees", "totalFees"])),
                "netProfit": None if raw_net_profit is None else self._num(raw_net_profit),
                "isBuy": self._first(raw, ["isBuy"]),
                "leverage": self._num(self._first(raw, ["leverage"]) or 1),
                "provenance": "ETORO_HISTORY_DIRECT",
                "raw_payload": raw,
            }
            if normalized["openTimestamp"]:
                periods.append(str(normalized["openTimestamp"])[:10])
            if normalized["closeTimestamp"]:
                periods.append(str(normalized["closeTimestamp"])[:10])

            if status != "SUPPORTED_DIRECT":
                rejected = {"row_number": index, "row": normalized, "error": reason}
                rejected_rows.append(rejected)
                if status == "PARTIAL_DATA":
                    partial_rows.append(normalized)
                else:
                    unsupported_rows.append(normalized)
                continue

            accepted_rows.append(normalized)
            buy, sell = self._history_row_to_operations(normalized)
            operations.extend([buy, sell])
            net_profit_reconciliation.append(self._reconcile_history_net_profit(normalized))

        return {
            "operations": operations,
            "accepted_history_rows": accepted_rows,
            "rejected_rows": rejected_rows,
            "unsupported_rows": unsupported_rows,
            "partial_rows": partial_rows,
            "net_profit_reconciliation": net_profit_reconciliation,
            "summary": {
                "rows": len(rows),
                "compatible": len(accepted_rows),
                "unsupported": len(unsupported_rows),
                "partial": len(partial_rows),
                "operations": len(operations),
            },
            "period": {"from": min(periods) if periods else None, "to": max(periods) if periods else None},
        }

    def build_snapshot(self, portfolio_payload: Dict[str, Any], pnl_payload: Dict[str, Any], metadata_by_instrument: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
        metadata_by_instrument = metadata_by_instrument or {}
        portfolio_positions = self._extract_positions(portfolio_payload)
        pnl_positions = self._extract_positions(pnl_payload)
        pnl_by_position = {self._position_id(row): row for row in pnl_positions if self._position_id(row)}
        direct_positions = []
        partial_count = 0
        for row in portfolio_positions:
            if self._is_mirror_internal_position(row):
                continue
            pnl_row = pnl_by_position.get(self._position_id(row))
            if not pnl_row:
                partial_count += 1
            direct_positions.append(self._merge_position(row, pnl_row, metadata_by_instrument))

        mirrors = self._extract_mirrors(portfolio_payload, pnl_payload, metadata_by_instrument)
        account_pnl = self._account_unrealized_pnl(pnl_payload)
        direct_pnl = round(sum(float(row.get("unrealized_pnl") or 0) for row in direct_positions if row.get("unrealized_pnl") is not None), 2)
        mirror_pnl = round(sum(float(mirror.get("internal_positions_pnl") or 0) for mirror in mirrors), 2)
        reconstructed = round(direct_pnl + mirror_pnl, 2)
        pnl_diff = None if account_pnl is None else round(reconstructed - account_pnl, 2)
        pnl_status = "NOT_AVAILABLE" if account_pnl is None else ("MATCH" if abs(pnl_diff or 0) <= self.reconciliation_tolerance else "MISMATCH")
        return {
            "snapshot_status": "PARTIAL_DATA" if partial_count else "READY",
            "history_status": "NOT_AVAILABLE",
            "positions": direct_positions,
            "direct_positions": direct_positions,
            "mirrors": mirrors,
            "direct_summary": {
                "positions": len(direct_positions),
                "unrealized_pnl": direct_pnl,
            },
            "mirror_summary": {
                "mirrors": len(mirrors),
                "internal_positions": sum(len(mirror.get("positions", [])) for mirror in mirrors),
                "unrealized_pnl": mirror_pnl,
            },
            "account_pnl_reconciliation": {
                "direct_pnl": direct_pnl,
                "mirror_pnl": mirror_pnl,
                "reconstructed_total_pnl": reconstructed,
                "etoro_account_pnl": account_pnl,
                "difference": pnl_diff,
                "status": pnl_status,
            },
            "warnings": [{"type": "MISSING_PNL", "count": partial_count, "message": "Some portfolio positions have no matching PnL row."}] if partial_count else [],
        }

    def normalize_positions(self, payload: Dict[str, Any], instrument_mappings: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        mappings = instrument_mappings or {}
        positions, unsupported, unmapped = [], [], []
        for raw in self.extract_items(payload, "positions"):
            external_id = self._external_instrument_id(raw)
            external_name = self._external_instrument_name(raw)
            mapped_ticker = self._mapped_ticker(external_id, external_name, mappings)
            position_id = str(self._first(raw, ["positionId", "positionID", "id", "orderId"]) or external_id or uuid.uuid4())
            status, reason = self._instrument_status(raw, external_id, mapped_ticker)
            quantity = abs(self._num(self._first(raw, ["quantity", "units", "amount", "shares", "openQuantity"])))
            avg_price = self._num(self._first(raw, ["averageOpen", "avgOpen", "openRate", "averagePrice", "price"]))
            current_price = self._num(self._first(raw, ["currentRate", "currentPrice", "marketPrice", "rate"]))
            row = {
                "source": self.source,
                "external_id": position_id,
                "external_instrument_id": external_id,
                "external_name": external_name,
                "symbol": external_name,
                "instrument_type": self._instrument_type(raw),
                "account_external_id": self._account_external_id(raw),
                "ticker": mapped_ticker,
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": current_price,
                "currency": self._currency(raw),
                "status": status,
                "reason": reason,
                "raw_payload": raw,
            }
            positions.append(row)
            if status == "UNSUPPORTED_INSTRUMENT":
                unsupported.append(row)
            elif status == "MISSING_MAPPING":
                unmapped.append(row)
        return {"positions": positions, "unsupported": unsupported, "unmapped": unmapped}

    def normalize_operations(self, payload: Dict[str, Any], instrument_mappings: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        mappings = instrument_mappings or {}
        accepted, rejected = [], []
        for index, raw in enumerate(self.extract_items(payload, "orders"), start=1):
            try:
                operation = self._normalize_operation(raw, mappings)
                accepted.append(operation)
            except ValueError as exc:
                rejected.append({"row_number": index, "row": raw, "error": str(exc)})
        return {"operations": accepted, "rejected_rows": rejected}

    def reconcile_positions(self, etoro_positions: List[Dict[str, Any]], ledger_positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        ledger_by_ticker = {row["ticker"].upper(): row for row in ledger_positions}
        rows, issues = [], []
        for position in etoro_positions:
            ticker = (position.get("ticker") or "").upper()
            if position.get("status") != "READY":
                status = position["status"]
                diff = None
            else:
                ledger = ledger_by_ticker.get(ticker)
                if not ledger:
                    status = "INSUFFICIENT_HISTORY"
                    diff = position["quantity"]
                else:
                    diff = round(float(position["quantity"]) - float(ledger.get("quantity") or 0), 8)
                    status = "MATCH" if abs(diff) <= 1e-6 else "QUANTITY_MISMATCH"
            row = {**position, "ledger_quantity_diff": diff, "reconciliation_status": status}
            rows.append(row)
            if status != "MATCH":
                issues.append({
                    "type": status,
                    "ticker": ticker or position.get("external_name"),
                    "message": position.get("reason") or f"eToro position {ticker or position.get('external_name')} no coincide con el ledger.",
                    "action": "Mapear instrumento o importar historial antes de confiar en holdings efectivos.",
                })
        return {"rows": rows, "issues": issues, "summary": {"positions": len(rows), "issues": len(issues)}}

    def extract_items(self, data: Any, collection_key: str) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in [collection_key, "items", "data", "orders", "positions", "tradeHistory", "history"]:
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            for value in data.values():
                if isinstance(value, dict):
                    items = self.extract_items(value, collection_key)
                    if items:
                        return items
        return []

    def _fetch_paginated(self, path: str, collection_key: str, limit: int = 200) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        pages = 0
        meta: Dict[str, Any] = {}
        cursor: Optional[str] = None
        offset = 0
        while True:
            params: Dict[str, Any] = {"limit": limit}
            if cursor:
                params["cursor"] = cursor
            elif offset:
                params["offset"] = offset
            data, page_meta = self._get(path, params)
            meta.update(page_meta)
            items.extend(self.extract_items(data, collection_key))
            pages += 1
            cursor = data.get("nextCursor") or data.get("nextPageToken") if isinstance(data, dict) else None
            next_offset = data.get("nextOffset") if isinstance(data, dict) else None
            if cursor:
                continue
            if next_offset is not None:
                offset = int(next_offset)
                continue
            break
        return {"items": items, "pages": pages, "meta": meta}

    def _normalize_operation(self, raw: Dict[str, Any], mappings: Dict[str, str]) -> Dict[str, Any]:
        external_id = str(self._first(raw, ["id", "orderId", "positionId", "tradeId", "dealId"]) or "")
        if not external_id:
            raise ValueError("Missing external_id from eToro operation.")
        external_instrument_id = self._external_instrument_id(raw)
        external_name = self._external_instrument_name(raw)
        ticker = self._mapped_ticker(external_instrument_id, external_name, mappings)
        status, reason = self._instrument_status(raw, external_instrument_id, ticker)
        if status != "READY":
            raise ValueError(reason)

        operation_type = self._operation_type(raw)
        if operation_type in {"BUY", "SELL"} and not ticker:
            raise ValueError("Mapped ticker is required for trade operations.")
        if operation_type is None:
            raise ValueError("Unsupported eToro operation type.")

        quantity = abs(self._num(self._first(raw, ["quantity", "units", "amount", "shares", "filledQuantity"])))
        price = self._num(self._first(raw, ["price", "rate", "openRate", "closeRate", "executionPrice", "averagePrice"]))
        cash_amount = abs(self._num(self._first(raw, ["cashAmount", "realizedAmount", "totalAmount", "value", "invested", "proceeds"])))
        if operation_type in {"BUY", "SELL"} and cash_amount <= 0:
            cash_amount = quantity * price
        fee = abs(self._num(self._first(raw, ["fee", "commission", "spread", "overnightFee"])))
        occurred_at = self._date(self._first(raw, ["executedAt", "closedAt", "openedAt", "createdAt", "date", "timestamp"]))

        return {
            "occurred_at": occurred_at,
            "ticker": ticker,
            "operation_type": operation_type,
            "quantity": quantity if operation_type in {"BUY", "SELL", "SPLIT"} else 0,
            "price": price,
            "amount": cash_amount or fee,
            "fee": fee,
            "currency": self._currency(raw),
            "source": self.source,
            "external_id": external_id,
            "external_instrument_id": external_instrument_id,
            "external_name": external_name,
            "symbol": external_name,
            "instrument_type": self._instrument_type(raw),
            "account_external_id": self._account_external_id(raw),
            "notes": f"eToro {operation_type.lower()} read-only import",
            "metadata": {
                "source": self.source,
                "environment": self.environment,
                "external_instrument_id": external_instrument_id,
                "external_name": external_name,
                "account_external_id": self._account_external_id(raw),
                "instrument_type": self._instrument_type(raw),
            },
        }

    def _operation_type(self, raw: Dict[str, Any]) -> Optional[str]:
        value = str(self._first(raw, ["operationType", "type", "action", "side", "direction"]) or "").upper()
        if any(token in value for token in ["DIVIDEND"]):
            return "DIVIDEND"
        if any(token in value for token in ["INTEREST"]):
            return "INTEREST"
        if any(token in value for token in ["FEE", "COMMISSION"]):
            return "FEE"
        if any(token in value for token in ["DEPOSIT", "CONTRIBUTION"]):
            return "CONTRIBUTION"
        if any(token in value for token in ["WITHDRAW"]):
            return "WITHDRAWAL"
        if any(token in value for token in ["SELL", "CLOSE"]):
            return "SELL"
        if any(token in value for token in ["BUY", "OPEN"]):
            return "BUY"
        return None

    def _instrument_status(self, raw: Dict[str, Any], external_id: str, ticker: Optional[str]) -> Tuple[str, str]:
        leverage = self._num(self._first(raw, ["leverage", "leverageX", "xLeverage"]) or 1)
        is_cfd = bool(self._first(raw, ["isCfd", "isCFD", "cfd"]))
        direction = str(self._first(raw, ["direction", "side", "action"]) or "").upper()
        is_short = "SHORT" in direction or "SELL" == direction and bool(self._first(raw, ["isOpen", "open"]))
        asset_type = str(self._first(raw, ["assetType", "instrumentType", "type"]) or "").upper()
        if is_cfd or leverage not in {0, 1} or is_short or "CFD" in asset_type:
            return "UNSUPPORTED_INSTRUMENT", "CFD, leverage or short exposure is read-only reconciliation only."
        if not external_id:
            return "MISSING_MAPPING", "eToro instrument id/name is missing."
        if not ticker:
            return "MISSING_MAPPING", "eToro instrument must be mapped before import."
        return "READY", ""

    def _instrument_type(self, raw: Dict[str, Any]) -> str:
        instrument = raw.get("instrument")
        if isinstance(instrument, dict):
            value = self._first(instrument, ["assetType", "instrumentType", "type", "category"])
        else:
            value = self._first(raw, ["assetType", "instrumentType", "type", "category"])
        return str(value or "").upper()

    def _account_external_id(self, raw: Dict[str, Any]) -> str:
        account = raw.get("account") or raw.get("portfolio") or raw.get("portfolioContext")
        if isinstance(account, dict):
            return str(self._first(account, ["id", "accountId", "portfolioId", "name"]) or "")
        return str(self._first(raw, ["accountId", "portfolioId", "portfolioName", "accountName"]) or "")

    def _mapped_ticker(self, external_id: str, external_name: str, mappings: Dict[str, str]) -> Optional[str]:
        return (mappings.get(external_id) or mappings.get(external_name) or mappings.get(external_name.upper()) or "").upper() or None

    def _external_instrument_id(self, raw: Dict[str, Any]) -> str:
        instrument = raw.get("instrument")
        if isinstance(instrument, dict):
            return str(self._first(instrument, ["id", "instrumentId", "instrumentID", "symbol", "ticker"]) or "")
        return str(self._first(raw, ["instrumentId", "instrumentID", "instrument_id", "symbol", "ticker", "isin"]) or "")

    def _external_instrument_name(self, raw: Dict[str, Any]) -> str:
        instrument = raw.get("instrument")
        if isinstance(instrument, dict):
            return str(self._first(instrument, ["symbol", "ticker", "name", "displayName", "id"]) or "")
        return str(self._first(raw, ["symbol", "ticker", "instrumentName", "name", "displayName", "isin"]) or "")

    def _currency(self, raw: Dict[str, Any]) -> str:
        value = self._first(raw, ["currency", "currencyCode", "baseCurrency", "quoteCurrency"]) or "USD"
        if isinstance(value, dict):
            value = value.get("code") or value.get("currencyCode") or "USD"
        return str(value).upper()

    def _date(self, value: Any) -> str:
        if not value:
            return datetime.now().date().isoformat()
        text = str(value)
        if text.isdigit() and len(text) >= 10:
            return datetime.fromtimestamp(int(text[:10])).date().isoformat()
        return text[:19]

    def _num(self, value: Any) -> float:
        try:
            if isinstance(value, dict):
                value = value.get("value") or value.get("amount") or value.get("pnL") or value.get("pnl")
            return float(value or 0)
        except Exception:
            return 0.0

    def _first(self, payload: Dict[str, Any], keys: List[str]) -> Any:
        for key in keys:
            if key in payload and payload.get(key) is not None:
                return payload.get(key)
        return None

    def _response_meta(self, headers: Any) -> Dict[str, Any]:
        return {
            "rate_limit": headers.get("x-rate-limit-limit") if headers else None,
            "rate_remaining": headers.get("x-rate-limit-remaining") if headers else None,
            "rate_reset": headers.get("x-rate-limit-reset") if headers else None,
        }

    def _portfolio_path(self) -> str:
        if self.environment == "demo":
            return "/trading/info/demo/portfolio"
        return "/trading/info/portfolio"

    def _pnl_path(self) -> str:
        if self.environment == "demo":
            return "/trading/info/demo/pnl"
        return "/trading/info/real/pnl"

    def _history_path(self) -> str:
        if self.environment == "demo":
            return "/trading/info/trade/demo/history"
        return "/trading/info/trade/history"

    def _history_identity(self, row: Dict[str, Any]) -> Tuple[str, str]:
        primary = str(self._first(row, ["positionId", "positionID"]) or "")
        if not primary:
            primary = f"missing:{self._first(row, ['instrumentId', 'instrumentID']) or ''}:{self._first(row, ['openTimestamp']) or ''}:{self._first(row, ['closeTimestamp']) or ''}"
        fingerprint = hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return primary, fingerprint

    def _history_instrument_id(self, raw: Dict[str, Any]) -> str:
        return str(self._first(raw, ["instrumentId", "instrumentID", "instrument_id"]) or "")

    def _history_ticker(self, raw: Dict[str, Any], metadata: Dict[str, Any], mappings: Dict[str, str]) -> Optional[str]:
        instrument_id = self._history_instrument_id(raw)
        metadata_symbol = str(self._first(metadata, ["symbol", "ticker", "name", "instrumentDisplayName"]) or "")
        return (mappings.get(instrument_id) or mappings.get(metadata_symbol) or mappings.get(metadata_symbol.upper()) or metadata_symbol or "").upper() or None

    def _classify_history_row(self, raw: Dict[str, Any]) -> Tuple[str, str]:
        if raw.get("_etoro_identity_conflict"):
            return "UNSUPPORTED", "Repeated positionId has different payload; manual review required."
        if self._first(raw, ["parentPositionId", "parentPositionID"]) or self._first(raw, ["socialTradeId", "socialTradeID"]):
            return "PARTIAL_DATA", "Copy/Mirror/social trade history is ambiguous for normal ledger import."
        leverage = self._num(self._first(raw, ["leverage"]) or 1)
        if leverage != 1:
            return "UNSUPPORTED", "Leveraged/CFD trade is read-only reconciliation only."
        is_buy = self._first(raw, ["isBuy"])
        if is_buy is False or str(is_buy).lower() == "false":
            return "UNSUPPORTED", "Short/sell-open trade is read-only reconciliation only."
        required = ["positionId", "instrumentId", "openTimestamp", "closeTimestamp", "openRate", "closeRate", "units"]
        missing = [key for key in required if self._first(raw, [key, key.replace("Id", "ID")]) in {None, ""}]
        if missing:
            return "PARTIAL_DATA", f"Missing required eToro history fields: {', '.join(missing)}."
        return "SUPPORTED_DIRECT", ""

    def _history_row_to_operations(self, row: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        quantity = abs(float(row.get("units") or 0))
        open_rate = float(row.get("openRate") or 0)
        close_rate = float(row.get("closeRate") or 0)
        investment = abs(float(row.get("investment") or row.get("initialInvestment") or quantity * open_rate))
        proceeds = abs(quantity * close_rate)
        fees_raw = float(row.get("fees") or 0)
        fee_cost = abs(fees_raw)
        base_external_id = f"{self.source}:{self.environment.upper()}:history:{row.get('positionId')}"
        common_metadata = {
            "source": self.source,
            "environment": self.environment.upper(),
            "positionId": row.get("positionId"),
            "parentPositionId": row.get("parentPositionId"),
            "orderId": row.get("orderId"),
            "instrumentId": row.get("instrumentId"),
            "socialTradeId": row.get("socialTradeId"),
            "fees_raw": fees_raw,
            "netProfit": row.get("netProfit"),
            "provenance": row.get("provenance"),
        }
        # eToro reports closed-trade fees once for the position. Keep the signed raw
        # value in both legs for traceability, but assign the positive ledger cost
        # only to CLOSE so FIFO realized P&L does not count fees twice.
        buy = {
            "occurred_at": self._date(row.get("openTimestamp")),
            "ticker": row.get("ticker"),
            "operation_type": "BUY",
            "quantity": quantity,
            "price": open_rate,
            "amount": investment,
            "fee": 0,
            "currency": "USD",
            "source": self.source,
            "external_id": f"{base_external_id}:OPEN",
            "notes": "eToro history dry-run BUY",
            "metadata": {**common_metadata, "history_leg": "BUY"},
        }
        sell = {
            "occurred_at": self._date(row.get("closeTimestamp")),
            "ticker": row.get("ticker"),
            "operation_type": "SELL",
            "quantity": quantity,
            "price": close_rate,
            "amount": proceeds,
            "fee": fee_cost,
            "currency": "USD",
            "source": self.source,
            "external_id": f"{base_external_id}:CLOSE",
            "notes": "eToro history dry-run SELL",
            "metadata": {**common_metadata, "history_leg": "SELL"},
        }
        return buy, sell

    def _reconcile_history_net_profit(self, row: Dict[str, Any]) -> Dict[str, Any]:
        quantity = abs(float(row.get("units") or 0))
        finance_pnl = quantity * float(row.get("closeRate") or 0) - abs(float(row.get("investment") or row.get("initialInvestment") or quantity * float(row.get("openRate") or 0))) - abs(float(row.get("fees") or 0))
        external_pnl = row.get("netProfit")
        if external_pnl is None:
            status = "NOT_COMPARABLE"
            difference = None
        else:
            difference = round(finance_pnl - float(external_pnl or 0), 2)
            status = "MATCH" if abs(difference) <= self.reconciliation_tolerance else ("ROUNDING_DIFFERENCE" if abs(difference) <= 0.5 else "MISMATCH")
        return {
            "positionId": row.get("positionId"),
            "ticker": row.get("ticker"),
            "finance_realized_pnl": round(finance_pnl, 2),
            "etoro_netProfit": external_pnl,
            "difference": difference,
            "status": status,
        }

    def _extract_positions(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        direct = payload.get("positions")
        if isinstance(direct, list):
            return [item for item in direct if isinstance(item, dict)]
        client = payload.get("clientPortfolio")
        if isinstance(client, dict) and isinstance(client.get("positions"), list):
            return [item for item in client["positions"] if isinstance(item, dict)]
        return self.extract_items(payload, "positions")

    def _extract_mirrors(self, portfolio_payload: Dict[str, Any], pnl_payload: Dict[str, Any], metadata_by_instrument: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        portfolio_mirrors = self._mirror_rows(portfolio_payload)
        pnl_mirrors = {self._mirror_id(row): row for row in self._mirror_rows(pnl_payload) if self._mirror_id(row)}
        mirrors = []
        for mirror in portfolio_mirrors:
            mirror_id = self._mirror_id(mirror)
            pnl_mirror = pnl_mirrors.get(mirror_id, {})
            raw_positions = self._extract_positions(mirror)
            pnl_positions_by_id = {self._position_id(row): row for row in self._extract_positions(pnl_mirror) if self._position_id(row)}
            positions = [self._merge_position(row, pnl_positions_by_id.get(self._position_id(row)), metadata_by_instrument, provenance="ETORO_MIRROR", mirror=mirror) for row in raw_positions]
            internal_pnl = round(sum(float(row.get("unrealized_pnl") or 0) for row in positions if row.get("unrealized_pnl") is not None), 2)
            available = self._num(self._first(mirror, ["availableAmount", "available"]))
            exposure = round(sum(float(row.get("current_value_account") or row.get("exposure_in_account_currency") or 0) for row in positions), 2)
            return_row = {
                "provenance": "ETORO_MIRROR",
                "mirrorID": mirror_id,
                "parentCID": self._first(mirror, ["parentCID", "parentCid", "cid"]),
                "parentUsername": self._first(mirror, ["parentUsername", "username", "name"]),
                "initialInvestment": self._first(mirror, ["initialInvestment"]),
                "availableAmount": available,
                "closedPositionsNetProfit": self._first(mirror, ["closedPositionsNetProfit"]),
                "depositSummary": mirror.get("depositSummary"),
                "withdrawalSummary": mirror.get("withdrawalSummary"),
                "positions": positions,
                "internal_positions_pnl": internal_pnl,
                "operating_value": round(available + exposure, 2),
                "raw_payload": mirror,
            }
            mirrors.append(return_row)
        return mirrors

    def _mirror_rows(self, payload: Any) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        rows = []
        for key in ["mirrors", "mirrorPositions", "copyPositions"]:
            value = payload.get(key)
            if isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, dict))
        client = payload.get("clientPortfolio")
        if isinstance(client, dict):
            for key in ["mirrors", "mirrorPositions", "copyPositions"]:
                value = client.get(key)
                if isinstance(value, list):
                    rows.extend(item for item in value if isinstance(item, dict))
        return rows

    def _merge_position(self, portfolio_row: Dict[str, Any], pnl_row: Optional[Dict[str, Any]], metadata_by_instrument: Dict[str, Dict[str, Any]], provenance: str = "ETORO_DIRECT", mirror: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pnl_row = pnl_row or {}
        instrument_id = self._instrument_id(portfolio_row)
        metadata = metadata_by_instrument.get(str(instrument_id), {})
        units = self._num(self._first(portfolio_row, ["units", "quantity", "shares"]))
        open_rate = self._num(self._first(portfolio_row, ["openRate", "open_rate", "price"]))
        close_rate = self._nested_num(pnl_row, ["closeRate", "close_rate", "rate"])
        open_fx = self._num(self._first(portfolio_row, ["openConversionRate", "openFxRate", "conversionRate"]) or 1)
        close_fx = self._nested_num(pnl_row, ["closeConversionRate", "closeFxRate", "conversionRate"]) or 1
        raw_amount = self._first(portfolio_row, ["amount", "initialAmountInDollars"])
        open_value = self._num(raw_amount) if raw_amount is not None else units * open_rate * open_fx
        exposure_value = self._nested_num(pnl_row, ["exposureInAccountCurrency"])
        current_value = exposure_value if exposure_value is not None else (units * close_rate * close_fx if close_rate is not None else None)
        unrealized_pnl = self._nested_num(pnl_row, ["unrealizedPnL.pnL", "unrealizedPnl.pnl", "pnL", "pnl"])
        margin = self._nested_num(pnl_row, ["marginInAccountCurrency"])
        exposure_recon = None
        if margin is not None and unrealized_pnl is not None and current_value is not None:
            diff = round(float(current_value) - (float(margin) + float(unrealized_pnl)), 2)
            exposure_recon = {"difference": diff, "status": "MATCH" if abs(diff) <= self.reconciliation_tolerance else "MISMATCH"}
        return {
            "source": self.source,
            "environment": self.environment.upper(),
            "provenance": provenance,
            "CID": self._first(portfolio_row, ["CID", "cid"]),
            "positionID": self._position_id(portfolio_row),
            "external_id": f"{self.source}:{self.environment.upper()}:{self._first(portfolio_row, ['CID', 'cid'])}:{self._position_id(portfolio_row)}",
            "orderID": self._first(portfolio_row, ["orderID", "orderId"]),
            "instrumentID": instrument_id,
            "external_instrument_id": str(instrument_id or ""),
            "ticker": metadata.get("ticker") or metadata.get("symbol") or self._external_instrument_name(portfolio_row),
            "external_name": metadata.get("name") or self._external_instrument_name(portfolio_row),
            "asset_class": metadata.get("assetClass") or metadata.get("instrumentType"),
            "exchange": metadata.get("exchange"),
            "isin": metadata.get("isin") or metadata.get("ISIN"),
            "openDateTime": self._first(portfolio_row, ["openDateTime", "openDate", "openedAt"]),
            "quantity": units,
            "units": units,
            "open_rate": open_rate,
            "close_rate": close_rate,
            "open_conversion_rate": open_fx,
            "close_conversion_rate": close_fx,
            "open_value_account": round(open_value, 6) if open_value is not None else None,
            "current_value_account": round(current_value, 6) if current_value is not None else None,
            "unrealized_pnl": unrealized_pnl,
            "amount": raw_amount,
            "totalFees": self._first(portfolio_row, ["totalFees"]),
            "totalExternalFees": self._first(portfolio_row, ["totalExternalFees"]),
            "totalExternalTaxes": self._first(portfolio_row, ["totalExternalTaxes"]),
            "fees_cost_abs": abs(self._num(self._first(portfolio_row, ["totalFees"]))),
            "leverage": self._first(portfolio_row, ["leverage"]),
            "isBuy": self._first(portfolio_row, ["isBuy"]),
            "timestamp": self._first(pnl_row, ["timestamp"]),
            "source_endpoint": {"portfolio": self._portfolio_path(), "pnl": self._pnl_path()},
            "status": "PARTIAL_DATA" if not pnl_row else "READY",
            "exposure_reconciliation": exposure_recon,
            "mirrorID": self._mirror_id(mirror or {}) if mirror else None,
            "raw_payload": {"portfolio": portfolio_row, "pnl": pnl_row},
        }

    def _account_unrealized_pnl(self, payload: Dict[str, Any]) -> Optional[float]:
        value = self._nested_num(payload, ["clientPortfolio.unrealizedPnL", "unrealizedPnL", "unrealizedPnl", "unrealizedPnL.pnL"])
        return round(value, 2) if value is not None else None

    def _position_id(self, row: Dict[str, Any]) -> str:
        return str(self._first(row, ["positionID", "positionId", "position_id", "id"]) or "")

    def _instrument_id(self, row: Dict[str, Any]) -> str:
        return str(self._first(row, ["instrumentID", "instrumentId", "instrument_id", "CID"]) or "")

    def _mirror_id(self, row: Dict[str, Any]) -> str:
        return str(self._first(row, ["mirrorID", "mirrorId", "copyID", "copyId", "id"]) or "")

    def _is_mirror_internal_position(self, row: Dict[str, Any]) -> bool:
        return bool(self._first(row, ["mirrorID", "mirrorId", "parentCID", "parentUsername"]))

    def _nested_num(self, payload: Dict[str, Any], paths: List[str]) -> Optional[float]:
        for path in paths:
            value: Any = payload
            for part in path.split("."):
                if not isinstance(value, dict) or part not in value:
                    value = None
                    break
                value = value.get(part)
            if value is not None:
                return self._num(value)
        return None

    def _clean_env_value(self, value: Any) -> str:
        return str(value or "").strip().strip("\"'")

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if not self.is_configured():
            raise EtoroAuthError("ETORO_API_KEY y ETORO_USER_KEY no están configurados.")
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
                "x-api-key": self.api_key,
                "x-user-key": self.user_key,
                "x-request-id": str(uuid.uuid4()),
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body or "{}"), self._response_meta(response.headers)
        except urllib.error.HTTPError as exc:
            diagnostic = self._safe_http_diagnostic(request, exc)
            logger.warning("eToro HTTP error diagnostic: %s", json.dumps(diagnostic, ensure_ascii=False))
            if exc.code == 403 and self._is_cloudflare_client_block(diagnostic):
                raise EtoroNetworkError("eToro/Cloudflare bloqueó la firma del cliente HTTP local.", diagnostic=diagnostic) from exc
            if exc.code in {401, 403}:
                raise EtoroAuthError("Credenciales eToro inválidas o sin permiso read-only.", diagnostic=diagnostic) from exc
            if exc.code == 429:
                raise EtoroRateLimitError("Rate limit de eToro alcanzado.", retry_after=exc.headers.get("Retry-After")) from exc
            raise EtoroNetworkError(f"eToro respondió HTTP {exc.code}.", diagnostic=diagnostic) from exc
        except urllib.error.URLError as exc:
            raise EtoroNetworkError("No se pudo conectar con eToro.") from exc

    def _safe_http_diagnostic(self, request: urllib.request.Request, exc: urllib.error.HTTPError) -> Dict[str, Any]:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        body = self._sanitize_text(body)[:1000]
        return {
            "url": request.full_url,
            "method": request.get_method(),
            "status_code": exc.code,
            "request_header_names": sorted(name for name, _ in request.header_items()),
            "response_content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "response_body": body,
        }

    def _sanitize_text(self, value: str) -> str:
        text = value or ""
        for secret in [self.api_key, self.user_key]:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        return text

    def _is_cloudflare_client_block(self, diagnostic: Dict[str, Any]) -> bool:
        body = diagnostic.get("response_body") or ""
        return "cloudflare_error" in body and ("browser_signature_banned" in body or "Error 1010" in body)
