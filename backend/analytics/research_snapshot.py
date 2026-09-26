"""Deterministic Research snapshot: dedupe, delta, freshness, coverage, composition.

Research is EXTERNAL KNOWLEDGE — a read model over normalized items.
Pure and provider-neutral: no I/O, no network, no DB, no LLM, no system
clock in deterministic outputs (``generated_at`` is the only non-deterministic
field and is excluded by ``stable_snapshot_content``).
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.analytics.financial_snapshot import (
    section_envelope,
    stable_snapshot_content,  # noqa: F401  (re-exported for convenience)
    unavailable_section,
)


RESEARCH_SCHEMA_VERSION = "research_snapshot.v1"
RESEARCH_FRESH_DAYS = 7
RESEARCH_STALE_DAYS = 30

# A resolution state is deliberately NOT a delta state: absence from the
# latest snapshot does not prove resolution.
DELTA_STATES = {"NEW", "CHANGED", "UNCHANGED"}
FRESHNESS_STATES = {"FRESH", "AGING", "STALE", "UNKNOWN"}

DELTA_CHANGED_FIELDS = ("title", "url", "published_at", "summary", "epistemic", "entity_tickers")


def _as_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value).strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- dedupe


def deduplicate_research_batch(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministic in-batch dedupe on primary identity (source_id, external_ref).

    - same identity + same content_hash  -> collapsed, duplicate_rows += 1
    - same identity + different content_hash -> first occurrence kept,
      conflict recorded as IN_BATCH_CONFLICT (never silently overwritten)
    - items without an external_ref cannot be identified -> kept as-is
    """
    ordered: List[Dict[str, Any]] = []
    first_by_identity: Dict[Tuple[str, str], Dict[str, Any]] = {}
    duplicate_rows = 0
    conflicts: List[Dict[str, Any]] = []
    for item in items:
        identity = (item.get("source_id"), item.get("external_ref"))
        if not identity[1]:
            ordered.append(deepcopy(item))
            continue
        existing = first_by_identity.get(identity)
        if existing is None:
            kept = deepcopy(item)
            first_by_identity[identity] = kept
            ordered.append(kept)
            continue
        if existing.get("content_hash") == item.get("content_hash"):
            duplicate_rows += 1
            continue
        conflicts.append({
            "id": existing.get("id"),
            "source_id": identity[0],
            "external_ref": identity[1],
            "kept_content_hash": existing.get("content_hash"),
            "conflicting_content_hash": item.get("content_hash"),
            "state": "IN_BATCH_CONFLICT",
        })
    return {
        "items": ordered,
        "duplicate_rows": duplicate_rows,
        "in_batch_conflicts": conflicts,
    }


def cross_source_duplicate_signals(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Weak, conservative (entity_ticker, content_hash) cross-source SIGNAL.

    Informational only — never a merge key. Because content_hash embeds the
    normalized URL, this does not claim to detect all cross-source
    syndication; it only reports exact hash+ticker matches spanning
    two or more distinct sources. Records are never merged.
    """
    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in items:
        content_hash = item.get("content_hash")
        if not content_hash:
            continue
        for ticker in item.get("entity_tickers") or []:
            key = (ticker, content_hash)
            group = groups.setdefault(key, {"source_ids": set(), "item_ids": []})
            if item.get("source_id"):
                group["source_ids"].add(item["source_id"])
            if item.get("id"):
                group["item_ids"].append(item["id"])
    signals = [
        {
            "entity_ticker": ticker,
            "content_hash": content_hash,
            "source_ids": sorted(group["source_ids"]),
            "item_ids": sorted(set(group["item_ids"])),
            "signal": "POSSIBLE_CROSS_SOURCE_DUPLICATE",
        }
        for (ticker, content_hash), group in sorted(groups.items())
        if len(group["source_ids"]) >= 2
    ]
    return signals


# ---------------------------------------------------------------- delta


def _changed_fields(previous: Dict[str, Any], current: Dict[str, Any]) -> List[str]:
    return [field for field in DELTA_CHANGED_FIELDS if previous.get(field) != current.get(field)]


def compute_delta(
    previous_items: Optional[List[Dict[str, Any]]],
    current_items: List[Dict[str, Any]],
    *,
    previous_scope: Any = None,
    current_scope: Any = None,
    previous_ingest_complete: Optional[bool] = None,
    current_ingest_complete: Optional[bool] = None,
) -> Dict[str, Any]:
    """Deterministic delta: NEW | CHANGED | UNCHANGED only.

    A resolution state is not implemented in any form. A neutral
    ``missing_from_current`` collection is exposed instead. When scope or
    completeness contexts make the
    two sides non-comparable, no conclusion is fabricated: counts become None
    and no missing list is produced.
    """
    if previous_items is None:
        return {
            "status": "EMPTY",
            "comparable": False,
            "reasons": ["no_previous_snapshot"],
            "new_count": 0,
            "changed_count": 0,
            "unchanged_count": 0,
            "missing_count": 0,
            "missing_from_current": [],
            "items": [],
        }

    reasons: List[str] = []
    if previous_scope is not None and current_scope is not None and previous_scope != current_scope:
        reasons.append("scope_mismatch")
    if previous_ingest_complete is False or current_ingest_complete is False:
        reasons.append("ingest_incomplete")
    if reasons:
        return {
            "status": "NOT_COMPARABLE",
            "comparable": False,
            "reasons": reasons,
            "new_count": None,
            "changed_count": None,
            "unchanged_count": None,
            "missing_count": None,
            "missing_from_current": [],
            "items": [],
        }

    previous_by_id = {item.get("id"): item for item in previous_items if item.get("id")}
    current_by_id = {item.get("id"): item for item in current_items if item.get("id")}

    rows: List[Dict[str, Any]] = []
    new_count = changed_count = unchanged_count = 0
    for item in current_items:
        item_id = item.get("id")
        if not item_id or item_id not in previous_by_id:
            new_count += 1
            rows.append({"id": item_id, "state": "NEW"})
            continue
        previous = previous_by_id[item_id]
        if previous.get("content_hash") == item.get("content_hash"):
            unchanged_count += 1
            rows.append({"id": item_id, "state": "UNCHANGED"})
            continue
        changed_count += 1
        rows.append({"id": item_id, "state": "CHANGED", "changed_fields": _changed_fields(previous, item)})

    missing_ids = [item_id for item_id in previous_by_id if item_id not in current_by_id]
    missing_ids.sort()
    return {
        "status": "READY",
        "comparable": True,
        "reasons": [],
        "new_count": new_count,
        "changed_count": changed_count,
        "unchanged_count": unchanged_count,
        "missing_count": len(missing_ids),
        "missing_from_current": missing_ids,
        "items": rows,
    }


# ---------------------------------------------------------------- freshness


def compute_freshness(
    item: Dict[str, Any],
    reference: Any,
    *,
    fresh_days: int = RESEARCH_FRESH_DAYS,
    stale_days: int = RESEARCH_STALE_DAYS,
) -> Dict[str, Any]:
    """FRESH | AGING | STALE | UNKNOWN from explicit reference time.

    Basis: valid published_at preferred; valid fetched_at as fallback;
    neither valid -> UNKNOWN. Thresholds are explicit arguments (no DB
    config is read).
    """
    reference_dt = _as_utc(reference)
    thresholds = {"fresh_days": fresh_days, "stale_days": stale_days}
    if reference_dt is None:
        return {"status": "UNKNOWN", "basis": None, "age_days": None, "thresholds": thresholds}

    basis: Optional[str] = None
    moment: Optional[datetime] = None
    published = _as_utc(item.get("published_at"))
    if published is not None:
        basis, moment = "published_at", published
    else:
        fetched = _as_utc(item.get("fetched_at"))
        if fetched is not None:
            basis, moment = "fetched_at", fetched
    if moment is None:
        return {"status": "UNKNOWN", "basis": None, "age_days": None, "thresholds": thresholds}

    age_days = int((reference_dt - moment).total_seconds() // 86400)
    if age_days <= fresh_days:
        status = "FRESH"
    elif age_days <= stale_days:
        status = "AGING"
    else:
        status = "STALE"
    return {"status": status, "basis": basis, "age_days": age_days, "thresholds": thresholds}


# ---------------------------------------------------------------- coverage


def compute_coverage(
    items: List[Dict[str, Any]],
    freshness_rows: List[Dict[str, Any]],
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Factual counts only: no quality score, no ranking, no confidence."""
    linked = [item for item in items if item.get("entity_tickers")]
    entities = sorted({ticker for item in items for ticker in item.get("entity_tickers") or []})
    freshness_counts = {state: 0 for state in sorted(FRESHNESS_STATES)}
    for row in freshness_rows:
        freshness_counts[row["status"]] = freshness_counts.get(row["status"], 0) + 1
    return {
        "total_items": len(items),
        "entity_linked_items": len(linked),
        "unlinked_items": len(items) - len(linked),
        "distinct_entities": len(entities),
        "entities": entities,
        "unknown_normalization_items": sum(
            1 for item in items if item.get("normalization_status") == "UNKNOWN"
        ),
        "partial_normalization_items": sum(
            1 for item in items if item.get("normalization_status") == "PARTIAL"
        ),
        "possible_cross_source_duplicate_signals": len(signals),
        "freshness_counts": freshness_counts,
    }


# ---------------------------------------------------------------- composition


def compose_research_snapshot(
    *,
    as_of: str,
    scope: Dict[str, Any],
    sections: Dict[str, Dict[str, Any]],
    generated_at: str,
) -> Dict[str, Any]:
    """Compose a ResearchSnapshot with FinancialSnapshot-compatible roll-up.

    Roll-up rules mirror compose_financial_snapshot (read from source, not
    from memory): available in {READY, EMPTY, PARTIAL}; partial in
    {PARTIAL, UNAVAILABLE, DEFERRED, UNEVALUABLE}; no sections -> UNEVALUABLE;
    available == 0 -> EMPTY; else PARTIAL or READY.
    """
    copied_sections = deepcopy(sections)
    reasons: List[str] = []
    available = 0
    partial = False
    for name, section in copied_sections.items():
        status = section.get("status")
        if status in {"READY", "EMPTY", "PARTIAL"}:
            available += 1
        if status in {"PARTIAL", "UNAVAILABLE", "DEFERRED", "UNEVALUABLE"}:
            partial = True
            reasons.append(f"{name}:{status}")
    if not copied_sections or available == 0:
        status = "EMPTY" if copied_sections else "UNEVALUABLE"
    else:
        status = "PARTIAL" if partial else "READY"
    return {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "as_of": as_of,
        "generated_at": generated_at,
        "scope": deepcopy(scope),
        "status": status,
        "reasons": reasons,
        "sections": copied_sections,
        "provenance": {
            "composition": "ResearchSnapshot",
            "policy": "Outer envelope normalized; research section payloads preserved.",
        },
    }


def build_research_snapshot(
    items: List[Dict[str, Any]],
    *,
    as_of: str,
    generated_at: str,
    scope: Optional[Dict[str, Any]] = None,
    reference: Any = None,
    fresh_days: int = RESEARCH_FRESH_DAYS,
    stale_days: int = RESEARCH_STALE_DAYS,
    previous_items: Optional[List[Dict[str, Any]]] = None,
    previous_scope: Any = None,
    current_scope: Any = None,
    previous_ingest_complete: Optional[bool] = None,
    current_ingest_complete: Optional[bool] = None,
) -> Dict[str, Any]:
    """Build the five-section ResearchSnapshot from normalized items.

    ``reference`` (freshness clock) defaults to ``as_of`` — never a system
    clock, keeping composition deterministic.
    """
    deduped = deduplicate_research_batch(items)
    clean = deduped["items"]
    conflicts = deduped["in_batch_conflicts"]
    reference_value = reference if reference is not None else as_of

    freshness_rows = []
    for item in clean:
        result = compute_freshness(
            item, reference_value, fresh_days=fresh_days, stale_days=stale_days
        )
        freshness_rows.append({
            "id": item.get("id"),
            "source_id": item.get("source_id"),
            "status": result["status"],
            "basis": result["basis"],
            "age_days": result["age_days"],
            "thresholds": result["thresholds"],
        })
    unknown_freshness = sum(1 for row in freshness_rows if row["status"] == "UNKNOWN")

    signals = cross_source_duplicate_signals(clean)
    delta = compute_delta(
        previous_items,
        clean,
        previous_scope=previous_scope,
        current_scope=current_scope,
        previous_ingest_complete=previous_ingest_complete,
        current_ingest_complete=current_ingest_complete,
    )

    # -- items section
    item_reasons: List[str] = []
    unknown_norm = sum(1 for item in clean if item.get("normalization_status") == "UNKNOWN")
    partial_norm = sum(1 for item in clean if item.get("normalization_status") == "PARTIAL")
    if unknown_norm:
        item_reasons.append(f"normalization_unknown:{unknown_norm}")
    if partial_norm:
        item_reasons.append(f"normalization_partial:{partial_norm}")
    if deduped["duplicate_rows"]:
        item_reasons.append(f"duplicate_rows:{deduped['duplicate_rows']}")
    if conflicts:
        item_reasons.append(f"in_batch_conflict:{len(conflicts)}")
    if not clean:
        items_status = "EMPTY"
    elif unknown_norm or conflicts:
        items_status = "PARTIAL"
    else:
        items_status = "READY"

    # -- entities section
    linked_tickers = sorted({ticker for item in clean for ticker in item.get("entity_tickers") or []})
    entities_data = {
        "entities": [
            {"ticker": ticker, "item_count": sum(
                1 for item in clean if ticker in (item.get("entity_tickers") or [])
            )}
            for ticker in linked_tickers
        ],
        "distinct_entities": len(linked_tickers),
        "unlinked_items": sum(1 for item in clean if not item.get("entity_tickers")),
    }
    entities_status = "EMPTY" if not clean else "READY"

    # -- freshness section
    if not clean:
        freshness_status = "EMPTY"
        freshness_reasons: List[str] = []
    elif unknown_freshness:
        freshness_status = "PARTIAL"
        freshness_reasons = [f"freshness_unknown:{unknown_freshness}"]
    else:
        freshness_status = "READY"
        freshness_reasons = []
    freshness_data = {
        "reference": str(reference_value),
        "rows": freshness_rows,
        "counts": {
            state: sum(1 for row in freshness_rows if row["status"] == state)
            for state in sorted(FRESHNESS_STATES)
        },
        "thresholds": {"fresh_days": fresh_days, "stale_days": stale_days},
    }

    # -- delta section
    if delta["status"] == "EMPTY":
        delta_section = unavailable_section("research.delta", "no_previous_snapshot")
        delta_section["data"] = deepcopy(delta)
    elif delta["status"] == "NOT_COMPARABLE":
        delta_section = section_envelope(
            source="research.delta",
            data=deepcopy(delta),
            status="PARTIAL",
            reasons=list(delta["reasons"]),
            as_of=as_of,
        )
    else:
        delta_section = section_envelope(
            source="research.delta", data=deepcopy(delta), status="READY", as_of=as_of
        )

    # -- coverage section
    coverage = compute_coverage(clean, freshness_rows, signals)
    coverage_section = section_envelope(
        source="research.coverage",
        data=coverage,
        status="EMPTY" if not clean else "READY",
        as_of=as_of,
        provenance={"owner": "research.coverage", "policy": "factual counts only; no scoring"},
    )
    if signals:
        coverage_section["reasons"] = [f"cross_source_signals:{len(signals)}"]
        coverage_section["data"] = {**coverage, "cross_source_duplicate_signals": signals}

    sections = {
        "items": section_envelope(
            source="research.items",
            data=clean,
            status=items_status,
            reasons=item_reasons,
            as_of=as_of,
        ),
        "entities": section_envelope(
            source="research.entities",
            data=entities_data,
            status=entities_status,
            as_of=as_of,
        ),
        "freshness": section_envelope(
            source="research.freshness",
            data=freshness_data,
            status=freshness_status,
            reasons=freshness_reasons,
            as_of=as_of,
        ),
        "delta": delta_section,
        "coverage": coverage_section,
    }
    return compose_research_snapshot(
        as_of=as_of,
        scope=scope if scope is not None else {},
        sections=sections,
        generated_at=generated_at,
    )
