"""eToro read-only adapter.

eToro API -> Adapter -> Canonical investment operations -> Preview -> Ledger.
Trading/order endpoints are intentionally not implemented here.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class EtoroAuthError(Exception):
    pass


class EtoroRateLimitError(Exception):
    def __init__(self, message: str, retry_after: Optional[str] = None):
        super().__init__(message)
        self.retry_after = retry_after


class EtoroNetworkError(Exception):
    pass


class EtoroAdapter:
    source = "ETORO"

    def __init__(
        self,
        api_key: Optional[str] = None,
        user_key: Optional[str] = None,
        base_url: Optional[str] = None,
        environment: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("ETORO_API_KEY", "")
        self.user_key = user_key if user_key is not None else os.getenv("ETORO_USER_KEY", "")
        self.base_url = (base_url or os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com/api/v1")).rstrip("/")
        self.environment = (environment or os.getenv("ETORO_ENVIRONMENT", "demo")).strip().lower()
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
        return self._get(f"/trading/info/{self.environment}/portfolio")

    def fetch_pnl(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return self._get(f"/trading/info/{self.environment}/pnl")

    def fetch_history(self) -> Dict[str, Any]:
        return self._fetch_paginated(f"/trading/info/{self.environment}/history", "orders")

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
                value = value.get("value") or value.get("amount")
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
            if exc.code in {401, 403}:
                raise EtoroAuthError("Credenciales eToro inválidas o sin permiso read-only.") from exc
            if exc.code == 429:
                raise EtoroRateLimitError("Rate limit de eToro alcanzado.", retry_after=exc.headers.get("Retry-After")) from exc
            raise EtoroNetworkError(f"eToro respondió HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise EtoroNetworkError("No se pudo conectar con eToro.") from exc
