"""Shared security primitives for external provider boundaries (S3).

A deliberately small vocabulary shared by the eToro, BudgetBakers and
market-data providers: secret redaction, a common timeout policy,
bounded-retry math, and upstream message sanitization.

This is NOT a generic networking framework — each adapter keeps its own HTTP
loop and exception vocabulary; only the security-relevant constants and
helpers live here. The future AI/Gemini provider contract flows through the
same primitives: bounded request -> sanitized diagnostics -> typed errors.
"""

import os
import re
from typing import Any, Iterable, Optional, Tuple

# --- Timeout policy -------------------------------------------------------
# Existing providers all default to 15s; keep that as the shared bound.
DEFAULT_TIMEOUT_SECONDS = 15.0

# --- Bounded retry policy -------------------------------------------------
# 1 initial attempt + at most 2 retries. Transient-only, never infinite.
MAX_RETRY_ATTEMPTS = 3
# Hard cap for ANY sleep: Retry-After hints above this fail fast instead of
# blocking the worker (and keep tests deterministic).
MAX_RETRY_DELAY_SECONDS = 5.0
# "Selected" 5xx: classic transient upstream failures. Deterministic codes
# such as 501/505 are never retried.
RETRYABLE_SERVER_STATUS_CODES = frozenset({500, 502, 503, 504})
_BACKOFF_BASE_SECONDS = 0.1

# --- Response body bounds -------------------------------------------------
# Our code owns every provider body read (urllib response.read / HTTPError
# read): bound them before parsing. yfinance internals are library-managed
# and deliberately out of S3 scope.
# Successful provider body: pages carry <=200 items, so 5 MiB is far above
# any honest page while cutting off a hostile or misrouted stream quickly.
MAX_SUCCESS_BODY_BYTES = 5 * 1024 * 1024
# Diagnostic/error body: only the first 1000 chars are ever displayed, and
# provider block markers (e.g. Cloudflare) sit at the body start.
MAX_DIAGNOSTIC_BODY_BYTES = 64 * 1024


class ResponseTooLargeError(Exception):
    """Provider body exceeded the local bound; aborted before parsing.

    Carries only the limit — never response body bytes — so the message is
    safe to log, persist and surface verbatim.
    """

    def __init__(self, limit_bytes: int):
        super().__init__(
            f"Provider response exceeded the {limit_bytes}-byte limit."
        )
        self.limit_bytes = limit_bytes


def read_bounded_response(
    response: Any,
    max_bytes: int = MAX_SUCCESS_BODY_BYTES,
) -> bytes:
    """Read at most ``max_bytes`` from response, raising if the body is larger.

    Reads one byte past the limit to distinguish "fits" from "oversized"
    without ever buffering an unbounded body; a body of exactly
    ``max_bytes`` passes. Oversized bodies raise ``ResponseTooLargeError``
    before any parsing, so truncated bytes are never fed to a parser.
    """
    data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ResponseTooLargeError(max_bytes)
    return data


# --- Redaction ------------------------------------------------------------
REDACTED = "[REDACTED]"
MAX_UPSTREAM_MESSAGE_CHARS = 500
# Configured provider secrets (collection-side guard: trivially short values
# are never treated as secrets, to avoid over-redacting harmless domain text).
_SECRET_ENV_VARS = ("BUDGETBAKERS_API_TOKEN", "ETORO_API_KEY", "ETORO_USER_KEY")
_MIN_SECRET_CHARS = 4
_BEARER_RE = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+")
_SECRET_PARAM_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|client[_-]?secret|password|token)=[^&\s\"']+"
)


def redact_secrets(value: str, secrets: Iterable[str] = ()) -> str:
    """Replace configured secret values and token-shaped strings with [REDACTED].

    The configured-secret replacement is byte-for-byte the behavior eToro
    previously kept inline (``EtoroAdapter._sanitize_text``); the bearer /
    credential-parameter patterns are additive and only match
    credential-shaped text.
    """
    text = value or ""
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    text = _BEARER_RE.sub(lambda match: f"{match.group(1)}{REDACTED}", text)
    text = _SECRET_PARAM_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", text)
    return text


def configured_secrets(extra: Iterable[str] = ()) -> Tuple[str, ...]:
    """Configured provider secret values, filtered to avoid over-redaction."""
    raw_values = [os.getenv(name, "") for name in _SECRET_ENV_VARS]
    raw_values.extend(extra or ())
    cleaned: list = []
    for raw in raw_values:
        value = str(raw or "").strip()
        if len(value) >= _MIN_SECRET_CHARS and value != REDACTED:
            cleaned.append(value)
    return tuple(cleaned)


def sanitize_provider_message(
    value: Any,
    secrets: Optional[Iterable[str]] = None,
    max_chars: int = MAX_UPSTREAM_MESSAGE_CHARS,
) -> str:
    """Redacted + truncated provider message safe for logs, sync state and HTTP detail."""
    text = redact_secrets(
        str(value if value is not None else ""),
        configured_secrets() if secrets is None else secrets,
    )
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Parse Retry-After as seconds, bounded by MAX_RETRY_DELAY_SECONDS.

    Returns None when the header is absent, malformed, an HTTP-date, or larger
    than the safe cap — callers must then fail fast instead of sleeping long.
    """
    if value is None:
        return None
    try:
        seconds = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not 0.0 <= seconds <= MAX_RETRY_DELAY_SECONDS:
        return None
    return seconds


def backoff_delay(attempt: int) -> float:
    """Deterministic exponential backoff for the failed attempt (1-based): 0.1s, 0.2s, ... capped."""
    exponent = max(0, attempt - 1)
    return min(MAX_RETRY_DELAY_SECONDS, _BACKOFF_BASE_SECONDS * (2 ** exponent))
