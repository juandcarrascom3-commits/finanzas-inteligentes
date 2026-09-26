"""S3 provider-security boundaries: bounded body reads, bounded retries, redaction.

Focused on the NEW S3 behavior only:
- shared primitives (body caps, bounded read, Retry-After, backoff, secrets)
- BudgetBakers: oversize + empty-body typing (its retry suite lives in
  test_budgetbakers_real_adapter.py)
- eToro: oversize/empty typing, bounded retry classification, bounded
  diagnostics, explicit timeout, dead-helper removal

NO real network (urlopen monkeypatched), NO real credentials (env
monkeypatched), NO real sleep (_retry_sleep monkeypatched).
"""

import json
import urllib.error

import pytest

import backend.integrations.budgetbakers_adapter as bb_module
from backend.integrations.budgetbakers_adapter import (
    BudgetBakersAdapter,
    BudgetBakersMalformedResponseError,
    BudgetBakersResponseTooLargeError,
)
from backend.integrations.etoro_adapter import (
    EtoroAdapter,
    EtoroAuthError,
    EtoroNetworkError,
    EtoroRateLimitError,
    EtoroResponseTooLargeError,
)
from backend.integrations.provider_security import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_DIAGNOSTIC_BODY_BYTES,
    MAX_RETRY_ATTEMPTS,
    MAX_RETRY_DELAY_SECONDS,
    MAX_SUCCESS_BODY_BYTES,
    ResponseTooLargeError,
    backoff_delay,
    parse_retry_after,
    read_bounded_response,
    sanitize_provider_message,
)


# --- helpers ---------------------------------------------------------------

class FakeResponse:
    """Context-managed urllib response with real read(amt) slicing semantics."""

    def __init__(self, body: bytes, headers=None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, amt=-1):
        return self.body if amt < 0 else self.body[:amt]


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeErrorBody:
    """HTTPError file-like body that records how many bytes were requested."""

    def __init__(self, body: bytes):
        self.body = body
        self.reads = []

    def read(self, amt=-1):
        self.reads.append(amt)
        return self.body if amt < 0 else self.body[:amt]

    def close(self):
        return None


def http_error(code, headers=None, body=b""):
    fp = FakeErrorBody(body) if body else None
    return urllib.error.HTTPError("url", code, "error", Headers(headers or {}), fp=fp)


def urlopen_sequence(*outcomes):
    """urlopen fake raising/returning outcomes in order; repeats the last one."""
    state = {"calls": 0}

    def fake(request, timeout=None):
        index = min(state["calls"], len(outcomes) - 1)
        state["calls"] += 1
        outcome = outcomes[index]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    fake.state = state
    return fake


def spy_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "backend.integrations.etoro_adapter._retry_sleep",
        lambda seconds: sleeps.append(seconds),
    )
    return sleeps


# --- provider-security primitives ------------------------------------------

def test_body_cap_constants_are_the_s3_policy():
    assert MAX_SUCCESS_BODY_BYTES == 5 * 1024 * 1024
    assert MAX_DIAGNOSTIC_BODY_BYTES == 64 * 1024


def test_read_bounded_response_accepts_exact_boundary():
    data = b"01234567"  # exactly 8 bytes
    assert read_bounded_response(FakeResponse(data), max_bytes=8) == data


def test_read_bounded_response_rejects_one_byte_past_boundary():
    with pytest.raises(ResponseTooLargeError) as exc_info:
        read_bounded_response(FakeResponse(b"012345678"), max_bytes=8)
    assert exc_info.value.limit_bytes == 8


def test_response_too_large_error_carries_limit_but_never_body():
    with pytest.raises(ResponseTooLargeError) as exc_info:
        read_bounded_response(FakeResponse(b"BODY-SECRET-VALUE" + b"x" * 8), max_bytes=8)
    err = exc_info.value
    assert err.limit_bytes == 8
    assert "8" in str(err)
    assert "BODY-SECRET-VALUE" not in str(err)


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("abc", None),
        ("-1", None),
        ("6", None),  # above MAX_RETRY_DELAY_SECONDS -> fail fast
        ("Mon, 02 Jan 2026 00:00:00 GMT", None),  # HTTP-date unsupported
        ("0", 0.0),
        ("1.5", 1.5),
        ("5", 5.0),
    ],
)
def test_parse_retry_after_is_bounded(value, expected):
    assert parse_retry_after(value) == expected


def test_backoff_delay_never_exceeds_cap():
    for attempt in range(1, 30):
        assert backoff_delay(attempt) <= MAX_RETRY_DELAY_SECONDS


def test_configured_secrets_are_redacted(monkeypatch):
    monkeypatch.setenv("BUDGETBAKERS_API_TOKEN", "bb-token-secret-123")
    monkeypatch.setenv("ETORO_API_KEY", "etoro-api-key-456")
    monkeypatch.setenv("ETORO_USER_KEY", "etoro-user-key-789")
    message = (
        "boom using Bearer bb-token-secret-123 and "
        "https://x?api_key=etoro-api-key-456 user etoro-user-key-789"
    )
    cleaned = sanitize_provider_message(message)
    for secret in ("bb-token-secret-123", "etoro-api-key-456", "etoro-user-key-789"):
        assert secret not in cleaned
    assert "[REDACTED]" in cleaned


def test_trivially_short_env_values_are_not_treated_as_secrets(monkeypatch):
    monkeypatch.delenv("BUDGETBAKERS_API_TOKEN", raising=False)
    monkeypatch.delenv("ETORO_USER_KEY", raising=False)
    monkeypatch.setenv("ETORO_API_KEY", "ab")  # below the 4-char floor
    assert sanitize_provider_message("ab cd") == "ab cd"


# --- BudgetBakers -----------------------------------------------------------

def _bb_adapter():
    return BudgetBakersAdapter(token="test-token")


def test_bb_oversized_success_body_is_typed_before_parsing(monkeypatch):
    adapter = _bb_adapter()
    # Invariant: maps through the existing app.py 502 handler, is NOT
    # swallowed by the optional-endpoint BudgetBakersNetworkError fallback.
    assert issubclass(BudgetBakersResponseTooLargeError, BudgetBakersMalformedResponseError)
    assert not issubclass(BudgetBakersResponseTooLargeError, bb_module.BudgetBakersNetworkError)
    oversized = b"x" * (MAX_SUCCESS_BODY_BYTES + 1)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(oversized))
    with pytest.raises(BudgetBakersResponseTooLargeError) as exc_info:
        adapter._get("/v1/api/accounts")
    assert "5242880" in str(exc_info.value)
    assert "xxxx" not in str(exc_info.value)  # no body bytes leak


def test_bb_oversized_body_never_reaches_json_parser(monkeypatch):
    adapter = _bb_adapter()
    oversized = b"x" * (MAX_SUCCESS_BODY_BYTES + 1)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(oversized))
    spy = _JsonLoadSpy()
    monkeypatch.setattr("backend.integrations.budgetbakers_adapter.json", spy)
    with pytest.raises(BudgetBakersResponseTooLargeError):
        adapter._get("/v1/api/accounts")
    assert spy.loads_calls == []


@pytest.mark.parametrize("body", [b"", b"   ", b"\n\t"])
def test_bb_empty_or_whitespace_200_is_malformed(monkeypatch, body):
    adapter = _bb_adapter()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(body))
    with pytest.raises(BudgetBakersMalformedResponseError) as exc_info:
        adapter._get("/v1/api/accounts")
    assert type(exc_info.value) is BudgetBakersMalformedResponseError
    assert "vacía" in str(exc_info.value)


class _JsonLoadSpy:
    """Adapter-scoped json stand-in recording loads() calls."""

    def __init__(self):
        self.loads_calls = []
        self._real = json.loads

    def loads(self, value, *args, **kwargs):
        self.loads_calls.append(value)
        return self._real(value, *args, **kwargs)


# --- eToro ------------------------------------------------------------------

def _etoro_adapter():
    return EtoroAdapter(api_key="api-key", user_key="user-key")


def test_etoro_oversized_success_body_is_typed_before_parsing(monkeypatch):
    adapter = _etoro_adapter()
    # Invariant: maps through the existing app.py 502 handler with zero
    # app.py changes.
    assert issubclass(EtoroResponseTooLargeError, EtoroNetworkError)
    oversized = b"x" * (MAX_SUCCESS_BODY_BYTES + 1)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(oversized))
    with pytest.raises(EtoroResponseTooLargeError) as exc_info:
        adapter._get("/trading/info/demo/portfolio")
    assert "5242880" in str(exc_info.value)
    assert "xxxx" not in str(exc_info.value)


@pytest.mark.parametrize("body", [b"", b"   ", b"\n"])
def test_etoro_empty_or_whitespace_200_is_typed(monkeypatch, body):
    adapter = _etoro_adapter()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(body))
    with pytest.raises(EtoroNetworkError) as exc_info:
        adapter._get("/trading/info/demo/portfolio")
    assert "cuerpo vacío" in str(exc_info.value)


def test_etoro_transient_503_retries_then_succeeds(monkeypatch):
    adapter = _etoro_adapter()
    sleeps = spy_sleep(monkeypatch)
    ok = FakeResponse(b'{"positions": []}')
    fake = urlopen_sequence(http_error(503), ok)
    monkeypatch.setattr("urllib.request.urlopen", fake)
    payload, _ = adapter._get("/trading/info/demo/portfolio")
    assert payload == {"positions": []}
    assert fake.state["calls"] == 2
    assert len(sleeps) == 1
    assert sleeps[0] <= MAX_RETRY_DELAY_SECONDS


def test_etoro_503_retry_exhaustion_is_finite(monkeypatch):
    adapter = _etoro_adapter()
    sleeps = spy_sleep(monkeypatch)
    fake = urlopen_sequence(http_error(503))  # always 503
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(EtoroNetworkError) as exc_info:
        adapter._get("/trading/info/demo/portfolio")
    assert "HTTP 503" in str(exc_info.value)
    assert fake.state["calls"] == MAX_RETRY_ATTEMPTS
    assert len(sleeps) == MAX_RETRY_ATTEMPTS - 1
    assert all(delay <= MAX_RETRY_DELAY_SECONDS for delay in sleeps)


def test_etoro_urlerror_exhaustion_is_finite(monkeypatch):
    adapter = _etoro_adapter()
    sleeps = spy_sleep(monkeypatch)
    fake = urlopen_sequence(urllib.error.URLError("down"))
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(EtoroNetworkError) as exc_info:
        adapter._get("/trading/info/demo/portfolio")
    assert "No se pudo conectar" in str(exc_info.value)
    assert fake.state["calls"] == MAX_RETRY_ATTEMPTS
    assert len(sleeps) == MAX_RETRY_ATTEMPTS - 1


def test_etoro_401_auth_error_never_retries(monkeypatch):
    adapter = _etoro_adapter()
    sleeps = spy_sleep(monkeypatch)
    fake = urlopen_sequence(http_error(401, body=b'{"title": "Unauthorized"}'))
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(EtoroAuthError):
        adapter._get("/trading/info/demo/portfolio")
    assert fake.state["calls"] == 1
    assert sleeps == []


def test_etoro_404_never_retries(monkeypatch):
    adapter = _etoro_adapter()
    sleeps = spy_sleep(monkeypatch)
    fake = urlopen_sequence(http_error(404, body=b'{"title": "RouteNotFound"}'))
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(EtoroNetworkError) as exc_info:
        adapter._get("/bad-route")
    assert "HTTP 404" in str(exc_info.value)
    assert fake.state["calls"] == 1
    assert sleeps == []


def test_etoro_cloudflare_403_never_retries_and_is_not_auth(monkeypatch):
    adapter = _etoro_adapter()
    sleeps = spy_sleep(monkeypatch)
    cf_body = json.dumps({
        "title": "Error 1010: Access denied",
        "status": 403,
        "error_name": "browser_signature_banned",
        "cloudflare_error": True,
    }).encode("utf-8")
    fake = urlopen_sequence(http_error(403, body=cf_body))
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(EtoroNetworkError) as exc_info:
        adapter._get("/trading/info/demo/portfolio")
    assert "Cloudflare" in str(exc_info.value)
    assert not isinstance(exc_info.value, EtoroAuthError)
    assert fake.state["calls"] == 1
    assert sleeps == []


def test_etoro_short_bounded_retry_after_429_retries(monkeypatch):
    adapter = _etoro_adapter()
    sleeps = spy_sleep(monkeypatch)
    ok = FakeResponse(b'{"positions": []}')
    fake = urlopen_sequence(http_error(429, headers={"Retry-After": "1"}), ok)
    monkeypatch.setattr("urllib.request.urlopen", fake)
    payload, _ = adapter._get("/trading/info/demo/portfolio")
    assert payload == {"positions": []}
    assert fake.state["calls"] == 2
    assert sleeps == [1.0]


def test_etoro_excessive_retry_after_429_fails_fast(monkeypatch):
    adapter = _etoro_adapter()
    sleeps = spy_sleep(monkeypatch)
    fake = urlopen_sequence(http_error(429, headers={"Retry-After": "60"}))
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(EtoroRateLimitError) as exc_info:
        adapter._get("/trading/info/demo/portfolio")
    assert exc_info.value.retry_after == "60"
    assert fake.state["calls"] == 1
    assert sleeps == []


def test_etoro_diagnostic_read_is_bounded_and_redacted(monkeypatch):
    adapter = EtoroAdapter(api_key="secret-api-123", user_key="user-key-456")
    big_body = (
        "Authorization: Bearer secret-api-123; " + "A" * (MAX_DIAGNOSTIC_BODY_BYTES * 2)
    ).encode("utf-8")
    error_body = FakeErrorBody(big_body)
    fake = urlopen_sequence(
        urllib.error.HTTPError("url", 404, "not found", Headers({"Content-Type": "text/html"}), fp=error_body)
    )
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(EtoroNetworkError) as exc_info:
        adapter._get("/bad-route")
    diagnostic = exc_info.value.diagnostic
    assert error_body.reads == [MAX_DIAGNOSTIC_BODY_BYTES]  # bounded read
    assert len(diagnostic["response_body"]) <= 1000  # bounded display
    assert "secret-api-123" not in diagnostic["response_body"]
    assert "[REDACTED]" in diagnostic["response_body"]


def test_etoro_timeout_passed_explicitly(monkeypatch):
    adapter = _etoro_adapter()
    captured = {}

    def fake(request, timeout=None):
        captured["timeout"] = timeout
        return FakeResponse(b"{}")

    monkeypatch.setattr("urllib.request.urlopen", fake)
    adapter._get("/trading/info/demo/portfolio")
    assert captured["timeout"] == DEFAULT_TIMEOUT_SECONDS


def test_etoro_dead_unbounded_helper_is_removed():
    assert not hasattr(EtoroAdapter, "_fetch_paginated")
