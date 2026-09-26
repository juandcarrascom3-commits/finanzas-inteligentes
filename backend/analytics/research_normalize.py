"""Deterministic Research normalization: titles, URLs, IDs, timestamps, hashes.

Research is EXTERNAL KNOWLEDGE. This module is pure input -> output:
no I/O, no network, no DB, no randomness, no system clock. Every temporal
value enters explicitly as an argument.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit


EPISTEMIC_DEFAULT = "UNSPECIFIED"
EPISTEMIC_VALUES = {"FACT", "REPORTED", "ANALYSIS", "UNSPECIFIED"}
SOURCE_ID_PATTERN = re.compile(r"^[A-Z0-9._-]+$")
TICKER_ALLOWED_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-=^/")
TRACKING_PARAM_NAMES = {"fbclid", "gclid"}
TRACKING_PARAM_PREFIXES = ("utm_",)
SUPPORTED_URL_SCHEMES = {"http", "https"}
DEFAULT_PORTS = {"http": 80, "https": 443}
DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UNIX_MILLIS_THRESHOLD = 100_000_000_000  # at or above this magnitude: milliseconds


def _text_display(value: Any) -> str:
    """Unicode NFC, strip, collapse internal whitespace."""
    text = unicodedata.normalize("NFC", str(value if value is not None else ""))
    return re.sub(r"\s+", " ", text).strip()


def normalize_title_display(value: Any) -> str:
    """Display form of a title. An empty title is invalid input."""
    title = _text_display(value)
    if not title:
        raise ValueError("TITLE_REQUIRED")
    return title


def normalize_text_hash(value: Any) -> str:
    """Hash representation of text: display normalization + casefold()."""
    return _text_display(value).casefold()


def normalize_source_id(value: Any) -> str:
    """strip + upper, validated against [A-Z0-9._-]+. Never inferred."""
    source_id = str(value if value is not None else "").strip().upper()
    if not source_id:
        raise ValueError("SOURCE_ID_REQUIRED")
    if not SOURCE_ID_PATTERN.match(source_id):
        raise ValueError("SOURCE_ID_INVALID")
    return source_id


def _is_tracking_param(key: str) -> bool:
    lowered = unquote(key).lower()
    if lowered in TRACKING_PARAM_NAMES:
        return True
    return any(lowered.startswith(prefix) for prefix in TRACKING_PARAM_PREFIXES)


def _filter_query(query: str) -> str:
    """Drop only known tracking params; preserve everything else verbatim."""
    if not query:
        return ""
    kept = []
    for part in query.split("&"):
        if not part:
            continue
        key = part.split("=", 1)[0]
        if _is_tracking_param(key):
            continue
        kept.append(part)
    return "&".join(kept)


def normalize_url(value: Any) -> Tuple[Optional[str], str, Optional[str]]:
    """Deterministic URL normalization.

    Returns (url, status, reason):
      - empty input       -> (None, "MISSING", None)
      - parseable http(s) -> (normalized, "NORMALIZED", None)
      - unsafe/unparseable-> (original preserved, "UNKNOWN", "url_unparsed")

    Normalization: scheme lowercased, host lowercased, default port removed,
    fragment removed, trailing slash removed (except root), known tracking
    params (utm_*, fbclid, gclid) removed. Unknown params are preserved.
    No network requests are made and no URL is fabricated.
    """
    raw = str(value if value is not None else "").strip()
    if not raw:
        return None, "MISSING", None
    try:
        parts = urlsplit(raw)
        scheme = (parts.scheme or "").lower()
        if scheme not in SUPPORTED_URL_SCHEMES:
            return raw, "UNKNOWN", "url_unparsed"
        host = (parts.hostname or "").lower()
        if not host:
            return raw, "UNKNOWN", "url_unparsed"
        port = parts.port  # raises ValueError on malformed ports
        userinfo = ""
        if "@" in parts.netloc:
            userinfo = parts.netloc.rsplit("@", 1)[0] + "@"
        if port is not None and port == DEFAULT_PORTS.get(scheme):
            port = None
        netloc = f"{userinfo}{host}:{port}" if port is not None else host
        path = parts.path or ""
        if path.endswith("/") and path != "/":
            path = path.rstrip("/")
        query = _filter_query(parts.query)
        normalized = urlunsplit((scheme, netloc, path, query, ""))
        return normalized, "NORMALIZED", None
    except (ValueError, TypeError):
        return raw, "UNKNOWN", "url_unparsed"


def normalize_external_ref(
    value: Any, normalized_url: Optional[str]
) -> Tuple[Optional[str], bool, Optional[str]]:
    """Caller-provided ref is preserved; otherwise derived from the
    normalized (usable) URL. With neither, identity is not fabricated:
    returns (None, False, "external_ref_not_identifiable")."""
    ref = str(value if value is not None else "").strip()
    if ref:
        return ref, False, None
    if normalized_url:
        digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
        return digest[:16], True, None
    return None, False, "external_ref_not_identifiable"


def normalize_tickers(value: Any) -> Tuple[List[str], List[str]]:
    """strip + upper per ticker with market-data compatible charset semantics.

    Invalid tickers are dropped (never turned into a literal "UNKNOWN"
    entity) and surfaced as the reason ``ticker_unnormalized``. An empty
    result list is a valid UNLINKED state, not an error.
    """
    if value is None:
        return [], []
    if isinstance(value, str):
        values: List[Any] = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        return [], ["ticker_unnormalized"]
    tickers: List[str] = []
    invalid = False
    for item in values:
        ticker = str(item if item is not None else "").strip().upper()
        if not ticker or not all(char in TICKER_ALLOWED_CHARS for char in ticker):
            invalid = True
            continue
        if ticker not in tickers:
            tickers.append(ticker)
    return tickers, (["ticker_unnormalized"] if invalid else [])


def normalize_timestamp(
    value: Any, *, required: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """Normalize a timestamp to UTC ISO-8601.

    Accepts: ISO-8601 (with or without ``Z``), date-only, unix seconds,
    unix milliseconds, datetime instances. Naive values are treated as UTC.

    Returns (iso_or_None, reason). Invalid input -> (None, "invalid_timestamp").
    Missing input -> (None, None) unless required -> ValueError.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError("TIMESTAMP_REQUIRED")
        return None, None
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, bool):
            return None, "invalid_timestamp"
        elif isinstance(value, (int, float)):
            seconds = float(value) / 1000.0 if abs(float(value)) >= UNIX_MILLIS_THRESHOLD else float(value)
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
        else:
            text = str(value).strip()
            if text.isdigit() and len(text) >= 10:
                numeric = int(text)
                seconds = numeric / 1000 if abs(numeric) >= UNIX_MILLIS_THRESHOLD else numeric
                parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
            elif DATE_ONLY_PATTERN.match(text):
                parsed = datetime(int(text[0:4]), int(text[5:7]), int(text[8:10]), tzinfo=timezone.utc)
            else:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(), None
    except (ValueError, TypeError, OverflowError, OSError):
        return None, "invalid_timestamp"


def normalize_epistemic(value: Any) -> Tuple[str, Optional[str]]:
    """Source-provided / ingestion-declared epistemic kind.

    Missing or invalid values are never rejected and never inferred from
    content: they normalize to UNSPECIFIED + ``epistemic_unspecified``.
    """
    label = str(value if value is not None else "").strip().upper()
    if label in EPISTEMIC_VALUES:
        return label, None
    return EPISTEMIC_DEFAULT, "epistemic_unspecified"


def compute_content_hash(
    *,
    title_hash: str,
    url: Optional[str] = None,
    published_at: Optional[str] = None,
    summary: Optional[str] = None,
    body: Optional[str] = None,
    content: Optional[str] = None,
) -> str:
    """sha256 over canonical JSON of already-normalized material content.

    Excludes ``fetched_at`` and ``source_id``: re-downloading the same
    content (or the same content under another source) must not change the
    hash; changing material content must.
    """
    payload: Dict[str, Any] = {"title": title_hash}
    for key, value in (
        ("url", url),
        ("published_at", published_at),
        ("summary", summary),
        ("body", body),
        ("content", content),
    ):
        if value is not None:
            payload[key] = value
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stable_research_id(source_id: str, external_ref: str) -> str:
    """Primary identity: source_id + external_ref. Never the content hash."""
    raw = f"{source_id}|{external_ref}"
    return f"research:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def normalize_research_item(
    raw: Dict[str, Any], *, fetched_at: Optional[Any] = None
) -> Dict[str, Any]:
    """Normalize raw input into the ResearchItem contract.

    Required input: source_id, title, and a caller-supplied fetched_at
    (parameter or field). No system-clock fallback exists anywhere.
    """
    if not isinstance(raw, dict):
        raise ValueError("INVALID_RESEARCH_ITEM_INPUT")

    source_id = normalize_source_id(raw.get("source_id"))
    title = normalize_title_display(raw.get("title"))

    url, url_status, url_reason = normalize_url(raw.get("url"))
    normalized_url = url if url_status == "NORMALIZED" else None
    external_ref, ref_derived, ref_reason = normalize_external_ref(
        raw.get("external_ref"), normalized_url
    )

    entity_tickers, ticker_reasons = normalize_tickers(raw.get("entity_tickers"))

    published_at, published_reason = normalize_timestamp(raw.get("published_at"))

    fetched_raw = fetched_at if fetched_at is not None else raw.get("fetched_at")
    if fetched_raw is None or (isinstance(fetched_raw, str) and not fetched_raw.strip()):
        raise ValueError("FETCHED_AT_REQUIRED")
    fetched_iso, fetched_reason = normalize_timestamp(fetched_raw)

    epistemic, epistemic_reason = normalize_epistemic(raw.get("epistemic"))

    summary = raw.get("summary")
    normalized_summary = _text_display(summary) if summary is not None else None

    content_hash = compute_content_hash(
        title_hash=normalize_text_hash(title),
        url=url,
        published_at=published_at,
        summary=normalized_summary,
        body=raw.get("body"),
        content=raw.get("content"),
    )

    reasons: List[str] = []
    for reason in (url_reason, ref_reason, published_reason, fetched_reason, epistemic_reason):
        if reason and reason not in reasons:
            reasons.append(reason)
    for reason in ticker_reasons:
        if reason not in reasons:
            reasons.append(reason)

    if url_reason == "url_unparsed" or ref_reason == "external_ref_not_identifiable":
        normalization_status = "UNKNOWN"
    elif reasons:
        normalization_status = "PARTIAL"
    else:
        normalization_status = "READY"

    item: Dict[str, Any] = {
        "id": stable_research_id(source_id, external_ref) if external_ref else None,
        "source_id": source_id,
        "external_ref": external_ref,
        "title": title,
        "url": url,
        "published_at": published_at,
        "fetched_at": fetched_iso,
        "content_hash": content_hash,
        "epistemic": epistemic,
        "entity_tickers": entity_tickers,
        "normalization_status": normalization_status,
        "provenance": {
            "source_id": source_id,
            "external_ref": external_ref,
            "url": url,
            "published_at": published_at,
            "fetched_at": fetched_iso,
            "content_hash": content_hash,
        },
    }
    if ref_derived:
        item["external_ref_derived"] = True
    if reasons:
        item["reasons"] = reasons
    if normalized_summary is not None:
        item["summary"] = normalized_summary
    provider = str(raw.get("provider") or "").strip().upper()
    if provider:
        item["provider"] = provider
        item["provenance"]["provider"] = provider
    ingestion_method = str(raw.get("ingestion_method") or "").strip().upper()
    if ingestion_method:
        item["ingestion_method"] = ingestion_method
        item["provenance"]["ingestion_method"] = ingestion_method
    language = str(raw.get("language") or "").strip().lower()
    if language:
        item["language"] = language
    return item
