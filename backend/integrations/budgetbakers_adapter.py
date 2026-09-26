"""BudgetBakers Wallet adapter.

External Source -> Adapter -> Canonical Model -> Validation -> Preview -> Persistence.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.integrations.provider_security import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RETRY_ATTEMPTS,
    RETRYABLE_SERVER_STATUS_CODES,
    ResponseTooLargeError,
    backoff_delay,
    parse_retry_after,
    read_bounded_response,
)


class BudgetBakersAuthError(Exception):
    pass


class BudgetBakersRateLimitError(Exception):
    def __init__(self, message: str, retry_after: Optional[str] = None):
        super().__init__(message)
        self.retry_after = retry_after


class BudgetBakersInitSyncError(Exception):
    pass


class BudgetBakersNetworkError(Exception):
    pass


class BudgetBakersPaginationError(Exception):
    """Pagination exceeded the safety cap or failed to advance.

    Deliberately NOT a BudgetBakersNetworkError subclass: preview fallbacks that
    tolerate unavailable optional endpoints must not swallow a broken-pagination
    truncation — it has to surface as a clear error instead.
    """


class BudgetBakersMalformedResponseError(Exception):
    """BudgetBakers answered 2xx with a body that is not usable JSON.

    Deliberately a SIBLING of BudgetBakersNetworkError (like
    BudgetBakersPaginationError): preview fallbacks that tolerate unavailable
    optional endpoints must not treat a broken upstream payload as an empty
    collection — it has to surface as a controlled 502 instead of silently
    pretending the account has no data.
    """


class BudgetBakersResponseTooLargeError(BudgetBakersMalformedResponseError):
    """Provider body exceeded MAX_SUCCESS_BODY_BYTES; aborted before parsing.

    Subclasses BudgetBakersMalformedResponseError so the existing app.py
    handler (502 + NETWORK_ERROR sync state) and the preview fallback rules
    apply unchanged — no API-layer change is needed. Carries only the limit,
    never response body bytes.
    """


MAX_FETCH_PAGES = 200  # safety cap: 200 pages x 200 items = 40k items per collection


def _retry_sleep(seconds: float) -> None:
    """Single indirection point for retry delays so tests never really sleep."""
    time.sleep(seconds)


class BudgetBakersAdapter:
    source = "BUDGETBAKERS"

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.token = token if token is not None else os.getenv("BUDGETBAKERS_API_TOKEN", "")
        self.base_url = (base_url or os.getenv("BUDGETBAKERS_BASE_URL", "https://rest.budgetbakers.com/wallet")).rstrip("/")
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.token)

    def test_connection(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"status": "NOT_CONFIGURED", "message": "BUDGETBAKERS_API_TOKEN no está configurado."}
        started = time.time()
        data, meta = self._get("/v1/api/accounts", {"limit": 1})
        return {
            "status": "CONNECTED",
            "elapsed_ms": round((time.time() - started) * 1000),
            "rate_limit": meta.get("rate_limit"),
            "last_data_change_at": meta.get("last_data_change_at"),
            "sync_in_progress": meta.get("sync_in_progress"),
            "sample_count": len(self._extract_items(data, "accounts")),
        }

    def fetch_accounts(self) -> Dict[str, Any]:
        return self._fetch_paginated("/v1/api/accounts", "accounts")

    def fetch_records(self) -> Dict[str, Any]:
        return self._fetch_paginated("/v1/api/records", "records")

    def fetch_categories(self) -> Dict[str, Any]:
        return self._fetch_paginated("/v1/api/categories", "categories")

    def fetch_budgets(self) -> Dict[str, Any]:
        return self._fetch_paginated("/v1/api/budgets", "budgets")

    def fetch_standing_orders(self) -> Dict[str, Any]:
        return self._fetch_paginated("/v1/api/standing-orders", "standingOrders")

    def normalize_accounts(self, raw_accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for account in raw_accounts:
            amount = account.get("balance") or account.get("currentBalance") or account.get("amount") or {}
            if isinstance(amount, dict):
                balance = amount.get("value") or amount.get("amount") or 0
                currency = amount.get("currencyCode") or account.get("currencyCode") or "USD"
            else:
                balance = amount or 0
                currency = account.get("currencyCode") or account.get("currency") or "USD"
            external_id = str(account.get("id") or account.get("accountId") or "")
            if not external_id:
                continue
            normalized.append({
                "name": account.get("name") or account.get("title") or f"Wallet {external_id}",
                "account_type": account.get("accountType") or account.get("type") or "wallet",
                "currency": str(currency).upper(),
                "opening_balance": float(balance or 0),
                "current_balance": float(balance or 0),
                "source": self.source,
                "external_id": external_id,
                "raw_payload": account,
            })
        return normalized

    def normalize_categories(self, raw_categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for category in raw_categories:
            external_id = str(category.get("id") or category.get("categoryId") or category.get("name") or "")
            name = category.get("name") or category.get("title")
            if not external_id or not name:
                continue
            parent_obj = category.get("parent")
            parent_external_id = category.get("parentId")
            if not parent_external_id and isinstance(parent_obj, dict):
                parent_external_id = parent_obj.get("id")
            normalized.append({
                "external_id": external_id,
                "external_name": name,
                "parent_external_id": parent_external_id,
                "raw_payload": category,
            })
        return normalized

    def normalize_budgets(self, raw_budgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for budget in raw_budgets:
            external_id = str(budget.get("id") or budget.get("budgetId") or "")
            if not external_id:
                continue
            amount_obj = budget.get("amount") or budget.get("limit") or budget.get("planned") or {}
            if isinstance(amount_obj, dict):
                amount = amount_obj.get("value") or amount_obj.get("amount") or 0
                currency = amount_obj.get("currencyCode") or budget.get("currencyCode") or "USD"
            else:
                amount = amount_obj or 0
                currency = budget.get("currencyCode") or budget.get("currency") or "USD"
            category_obj = budget.get("category") or {}
            category = category_obj.get("name") if isinstance(category_obj, dict) else budget.get("categoryName")
            normalized.append({
                "category": category or budget.get("name") or f"Wallet Budget {external_id}",
                "monthly_limit": float(amount or 0),
                "currency": str(currency).upper(),
                "source": self.source,
                "period": budget.get("period") or budget.get("frequency") or "MONTHLY",
                "is_active": not bool(budget.get("archived") or budget.get("disabled")),
                "external_id": external_id,
                "raw_payload": budget,
            })
        return normalized

    def normalize_standing_orders(self, raw_orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for order in raw_orders:
            external_id = str(order.get("id") or order.get("standingOrderId") or "")
            if not external_id:
                continue
            amount_obj = order.get("amount", 0)
            amount = amount_obj.get("value") if isinstance(amount_obj, dict) else amount_obj
            category_obj = order.get("category") or {}
            category = category_obj.get("name") if isinstance(category_obj, dict) else order.get("categoryName")
            normalized.append({
                "merchant": order.get("counterParty") or order.get("name") or order.get("description") or f"Wallet Standing Order {external_id}",
                "category": category or "General",
                "typical_amount": float(amount or 0),
                "frequency": order.get("frequency") or order.get("period") or "monthly",
                "status": "confirmed",
                "source": self.source,
                "external_id": external_id,
                "next_expected": (order.get("nextDate") or order.get("nextPaymentDate") or "")[:10] or None,
                "last_seen": (order.get("lastDate") or order.get("updatedAt") or "")[:10] or None,
                "raw_payload": order,
            })
        return normalized

    def normalize_records(self, raw_records: List[Dict[str, Any]], category_mappings: Optional[Dict[str, str]] = None, account_mappings: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        category_mappings = category_mappings or {}
        account_mappings = account_mappings or {}
        normalized = []
        for record in raw_records:
            amount_obj = record.get("amount", record.get("amountAmount", 0))
            if isinstance(amount_obj, dict):
                amount = amount_obj.get("value") or amount_obj.get("amount") or 0
                currency = amount_obj.get("currencyCode") or "USD"
            else:
                amount = amount_obj or 0
                currency = record.get("currencyCode") or record.get("currency") or "USD"

            category_obj = record.get("category") or {}
            external_category = (
                category_obj.get("name")
                if isinstance(category_obj, dict)
                else record.get("categoryName")
            ) or record.get("categoryName") or "General"

            account_obj = record.get("account")
            account_external_id = record.get("accountId")
            if not account_external_id and isinstance(account_obj, dict):
                account_external_id = account_obj.get("id")
            account_external_id = str(account_external_id or "")
            external_id = str(record.get("id") or record.get("recordId") or "")
            if not external_id:
                continue

            description = record.get("counterParty") or record.get("payee") or record.get("note") or record.get("description") or ""
            record_date = record.get("recordDate") or record.get("date") or datetime.now().date().isoformat()
            normalized.append({
                "account_id": account_mappings.get(account_external_id) or None,
                "amount": float(amount or 0),
                "category": category_mappings.get(external_category, external_category),
                "date": str(record_date)[:10],
                "description": description,
                "currency": str(currency).upper(),
                "source": self.source,
                "external_id": external_id,
                "external_account_id": account_external_id,
                "external_category": external_category,
                "raw_payload": record,
            })
        return normalized

    def _fetch_paginated(self, path: str, collection_key: str, limit: int = 200, max_pages: int = MAX_FETCH_PAGES) -> Dict[str, Any]:
        offset = 0
        items: List[Dict[str, Any]] = []
        pages = 0
        meta: Dict[str, Any] = {}
        while True:
            if pages >= max_pages:
                raise BudgetBakersPaginationError(
                    f"BudgetBakers superó el límite de {max_pages} páginas para {path}; paginación detenida por seguridad."
                )
            data, page_meta = self._get(path, {"limit": limit, "offset": offset})
            meta.update(page_meta)
            page_items = self._extract_items(data, collection_key)
            items.extend(page_items)
            pages += 1
            next_offset = data.get("nextOffset") if isinstance(data, dict) else None
            if next_offset is None:
                break
            try:
                parsed_offset = int(next_offset)
            except (TypeError, ValueError) as exc:
                raise BudgetBakersPaginationError(
                    f"BudgetBakers devolvió nextOffset inválido ({next_offset!r}) en {path}."
                ) from exc
            if parsed_offset <= offset:
                raise BudgetBakersPaginationError(
                    f"La paginación de BudgetBakers no avanzó en {path} (offset {offset} -> {parsed_offset})."
                )
            offset = parsed_offset
        return {"items": items, "pages": pages, "meta": meta}

    def _extract_items(self, data: Any, collection_key: str) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            value = data.get(collection_key) or data.get("items") or data.get("data")
            if isinstance(value, list):
                return value
        return []

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
        if not self.token:
            raise BudgetBakersAuthError("BUDGETBAKERS_API_TOKEN no está configurado.")
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            method="GET",
        )
        attempt = 0
        while True:
            attempt += 1
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    try:
                        raw = read_bounded_response(response)
                    except ResponseTooLargeError as exc:
                        raise BudgetBakersResponseTooLargeError(
                            f"BudgetBakers devolvió una respuesta demasiado grande "
                            f"(supera el límite de {exc.limit_bytes} bytes)."
                        ) from exc
                    if not raw.strip():
                        raise BudgetBakersMalformedResponseError(
                            "BudgetBakers devolvió una respuesta vacía."
                        )
                    try:
                        body = raw.decode("utf-8")
                        data = json.loads(body)
                    except ValueError as exc:
                        raise BudgetBakersMalformedResponseError(
                            "BudgetBakers devolvió una respuesta inválida (JSON malformado)."
                        ) from exc
                    if not isinstance(data, (dict, list)):
                        raise BudgetBakersMalformedResponseError(
                            "BudgetBakers devolvió una respuesta inválida (estructura inesperada)."
                        )
                    return data, self._response_meta(response.headers)
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 403}:
                    raise BudgetBakersAuthError("Token BudgetBakers inválido o sin permisos.") from exc
                if exc.code == 409:
                    raise BudgetBakersInitSyncError("Wallet todavía está preparando/sincronizando datos. Intente más tarde.") from exc
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = parse_retry_after(retry_after)
                    if delay is None or attempt >= MAX_RETRY_ATTEMPTS:
                        raise BudgetBakersRateLimitError("Rate limit de BudgetBakers alcanzado.", retry_after=retry_after) from exc
                    _retry_sleep(delay)
                    continue
                if exc.code in RETRYABLE_SERVER_STATUS_CODES and attempt < MAX_RETRY_ATTEMPTS:
                    server_delay = parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None)
                    _retry_sleep(server_delay if server_delay is not None else backoff_delay(attempt))
                    continue
                raise BudgetBakersNetworkError(f"BudgetBakers respondió HTTP {exc.code}.") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < MAX_RETRY_ATTEMPTS:
                    _retry_sleep(backoff_delay(attempt))
                    continue
                raise BudgetBakersNetworkError("No se pudo conectar con BudgetBakers.") from exc

    def _response_meta(self, headers: Any) -> Dict[str, Any]:
        return {
            "rate_limit": {
                "limit": headers.get("X-RateLimit-Limit"),
                "remaining": headers.get("X-RateLimit-Remaining"),
                "retry_after": headers.get("Retry-After"),
            },
            "last_data_change_at": headers.get("X-Last-Data-Change-At"),
            "last_data_change_rev": headers.get("X-Last-Data-Change-Rev"),
            "sync_in_progress": headers.get("X-Sync-In-Progress"),
        }
