"""Research R1B: read-only preview and atomic ingestion orchestration.

Service layer between raw Research payloads and the R1A persistence
boundary. It consumes the locked R0 domain exactly as-is (normalization,
stable identities, dedupe, delta states, cross-source signals) and keeps
HTTP concerns out: callers (R1C) map ``ResearchServiceError.code`` to
HTTP statuses.

Policies implemented here:
- fetched_at is caller-supplied (request default may fill missing item
  values); the system clock is never used silently.
- Rejected items stay in the preview, are never written; ingest applies
  only when there is no blocking CONFLICT and at least one NEW/CHANGED
  item exists (NOTHING_TO_APPLY otherwise).
- Research ingest V1 has no backup gate (external knowledge, re-ingestible,
  not ledger authority).

Audit debt: R1B_AUDIT_SOURCE_BLOCKED_BY_S2
-------------------------------------------
R1B never writes action_events. ``db.add_action_event`` sanitizes
``source`` through ``VALID_SOURCES`` (database/db_manager.py), which does
not include "RESEARCH", so an INGEST event would be silently persisted as
``source="MANUAL"`` — a false attribution. Emitting nothing is the
truthful behavior: the ready-to-emit event is returned instead in
``result["audit"]["pending_event"]`` (keyword-compatible with
``db.add_action_event(source, event_type, message, severity, payload)``)
and ``result["audit"]["recorded"]`` stays ``False``.

Minimal unblock, owned by S2: add ``"RESEARCH"`` to ``VALID_SOURCES`` (or
expose an audit helper that accepts the RESEARCH source). Once that lands,
R1C/S2 integration emits the pending event — no service redesign needed.

Blocked-path events (confirmation/stale/conflict/nothing-to-apply) were
already deferred to R1C/S2 for the same truthfulness reason: with no
successful convention for blocked-event naming AND no valid source, an
emitted event would either be misnamed or misattributed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.analytics.research_normalize import normalize_research_item
from backend.analytics.research_snapshot import (
    compute_delta,
    cross_source_duplicate_signals,
    deduplicate_research_batch,
)
from database.db_manager import DatabaseManager
from database.research_store import ResearchStore

PREVIEW_HASH_VERSION = 1
ACCEPTED_STATUSES = ("NEW", "CHANGED")


class ResearchServiceError(Exception):
    """Stable domain error. R1C maps ``code`` to an HTTP response.

    Stable codes raised here: CONFIRMATION_REQUIRED, STALE_PREVIEW,
    CONFLICTS_BLOCKED, NOTHING_TO_APPLY. Normalization failures
    (INVALID_RESEARCH_ITEM_INPUT, FETCHED_AT_REQUIRED, RESEARCH_ID_REQUIRED)
    surface per item as REJECTED reasons instead of raised errors.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def preview_research(
    db: DatabaseManager,
    items: List[Dict[str, Any]],
    *,
    fetched_at: Any = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a read-only preview: normalize -> validate -> dedupe -> compare.

    Performs SELECT-only work: no research_items writes, no action_events.
    ``fetched_at`` fills item-level gaps only; it is never a clock fallback.
    """
    prepared, _context = _prepare(db, items, fetched_at=fetched_at, meta=meta)
    return prepared


def ingest_research(
    db: DatabaseManager,
    items: List[Dict[str, Any]],
    *,
    preview_hash: Optional[str] = None,
    confirm_import: bool = False,
    fetched_at: Any = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Confirm and apply a batch through one atomic store transaction.

    Sequence: confirmation gate -> re-preview against the CURRENT DB ->
    stale hash gate -> conflict gate -> accepted-only atomic write ->
    deferred audit event -> result.

    Audit: no action_events row is written in R1B
    (R1B_AUDIT_SOURCE_BLOCKED_BY_S2, module docstring). The APPLIED event
    cannot be recorded before the write because it is never recorded at
    all; the result carries it under ``audit.pending_event`` with
    ``audit.recorded = False``. Blocked paths (confirmation, stale,
    conflict, nothing-to-apply) emit nothing either — blocked-event naming
    also stays deferred to R1C/S2 integration.
    """
    if not confirm_import:
        raise ResearchServiceError(
            "CONFIRMATION_REQUIRED",
            "Se requiere confirmación explícita para aplicar la ingesta.",
        )

    preview, context = _prepare(db, items, fetched_at=fetched_at, meta=meta)

    if not preview_hash or preview_hash != preview["preview_hash"]:
        raise ResearchServiceError(
            "STALE_PREVIEW",
            "La vista previa ya no refleja el estado actual; vuelva a generarla.",
            {"current_preview_hash": preview["preview_hash"], "counts": preview["counts"]},
        )

    if preview["counts"]["conflict"] > 0:
        raise ResearchServiceError(
            "CONFLICTS_BLOCKED",
            "El lote contiene conflictos de identidad; la ingesta fue bloqueada.",
            {"conflicts": context["conflicts"], "counts": preview["counts"]},
        )

    if not context["accepted_items"]:
        raise ResearchServiceError(
            "NOTHING_TO_APPLY",
            "No hay elementos nuevos ni modificados que aplicar.",
            {"counts": preview["counts"], "preview_hash": preview["preview_hash"]},
        )

    write_counts = ResearchStore(db).upsert_items_atomic(context["accepted_items"])

    return {
        "result": "APPLIED",
        "scope_key": preview["scope_key"],
        "ingest_complete": preview["ingest_complete"],
        "preview_hash": preview["preview_hash"],
        "counts": preview["counts"],
        "write_counts": write_counts,
        "audit": _deferred_audit_event(preview),
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _prepare(
    db: DatabaseManager,
    items: List[Dict[str, Any]],
    *,
    fetched_at: Any,
    meta: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run the full read-only pipeline once; returns (preview, context)."""
    meta = meta or {}
    raw_items = list(items or [])
    scope_key = _scope_key(raw_items, meta)
    ingest_complete = bool(meta.get("ingest_complete", False))

    # 1-4: normalize each raw item; invalid normalization or missing stable
    # identity becomes REJECTED (never raised to the caller).
    slots: List[Tuple[str, Any]] = []
    normalized: List[Dict[str, Any]] = []
    for raw in raw_items:
        candidate = raw
        if isinstance(raw, dict) and not raw.get("fetched_at") and fetched_at:
            candidate = {**raw, "fetched_at": fetched_at}
        try:
            item = normalize_research_item(candidate)
        except ValueError as exc:
            slots.append(("rejected", _rejected_decision(raw, str(exc))))
            continue
        if not item.get("id"):
            slots.append((
                "rejected",
                {
                    "id": None,
                    "source_id": item.get("source_id"),
                    "external_ref": item.get("external_ref"),
                    "status": "REJECTED",
                    "content_hash": None,
                    "reasons": ["RESEARCH_ID_REQUIRED"],
                },
            ))
            continue
        slots.append(("valid", (item["source_id"], item["external_ref"])))
        normalized.append(item)

    # 5-6: R0 in-batch dedupe; same identity + different hash is CONFLICT.
    deduped = deduplicate_research_batch(normalized)
    conflicts = deduped["in_batch_conflicts"]
    conflict_ids = {row.get("id") for row in conflicts if row.get("id")}

    # 7: load ONLY existing rows for this batch's identities.
    identities = [
        (item["source_id"], item["external_ref"]) for item in deduped["items"]
    ]
    store = ResearchStore(db)
    existing = store.get_by_identities(identities)

    # 8-9: R0 delta semantics over batch-scoped identities
    # (missing_from_current stays neutral: scope is the batch intersection).
    delta = compute_delta(existing, deduped["items"])
    delta_by_id = {row.get("id"): row for row in delta.get("items", [])}

    # 10: warnings = item-level normalization reasons + cross-source signals.
    cross_signals = cross_source_duplicate_signals(deduped["items"])

    decisions_by_identity: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in deduped["items"]:
        row = delta_by_id.get(item["id"]) or {"state": "NEW"}
        if item["id"] in conflict_ids:
            status = "CONFLICT"
            reasons = ["IN_BATCH_CONFLICT"]
        else:
            status = row.get("state", "NEW")
            reasons = list(item.get("reasons") or [])
        decision: Dict[str, Any] = {
            "id": item["id"],
            "source_id": item["source_id"],
            "external_ref": item["external_ref"],
            "status": status,
            "content_hash": item["content_hash"],
        }
        if status == "CHANGED" and row.get("changed_fields"):
            decision["changed_fields"] = list(row["changed_fields"])
        if reasons:
            decision["reasons"] = reasons
        decisions_by_identity[(item["source_id"], item["external_ref"])] = decision

    # Decisions keep raw input order; collapsed duplicates emit once
    # (first occurrence), rejected items keep their own slot.
    filled: List[Dict[str, Any]] = []
    emitted: Set[Tuple[str, str]] = set()
    for kind, payload in slots:
        if kind == "rejected":
            filled.append(payload)
        elif payload not in emitted:
            emitted.add(payload)
            filled.append(decisions_by_identity[payload])

    counts = {
        "total": len(raw_items),
        "new": sum(1 for d in filled if d["status"] == "NEW"),
        "changed": sum(1 for d in filled if d["status"] == "CHANGED"),
        "unchanged": sum(1 for d in filled if d["status"] == "UNCHANGED"),
        "conflict": sum(1 for d in filled if d["status"] == "CONFLICT"),
        "rejected": sum(1 for d in filled if d["status"] == "REJECTED"),
        "warnings": sum(
            1
            for d in filled
            if d.get("reasons") and d["status"] in ACCEPTED_STATUSES + ("UNCHANGED",)
        ) + len(cross_signals),
    }

    # 11: fingerprint over ONLY the batch-relevant identities.
    fingerprint = store.relevant_state_fingerprint(identities)

    # 12: deterministic preview hash (eToro pattern, domain-adapted).
    preview_hash = _preview_hash(
        scope_key=scope_key,
        ingest_complete=ingest_complete,
        decisions=filled,
        fingerprint=fingerprint,
    )

    preview = {
        "scope_key": scope_key,
        "ingest_complete": ingest_complete,
        "counts": counts,
        "items": filled,
        "cross_source_signals": cross_signals,
        "preview_hash": preview_hash,
    }

    accepted_identities = {
        (d["source_id"], d["external_ref"])
        for d in filled
        if d["status"] in ACCEPTED_STATUSES
    }
    accepted_items = [
        item
        for item in deduped["items"]
        if (item["source_id"], item["external_ref"]) in accepted_identities
    ]
    context = {"accepted_items": accepted_items, "conflicts": conflicts}
    return preview, context


def _rejected_decision(raw: Any, code: str) -> Dict[str, Any]:
    return {
        "id": None,
        "source_id": raw.get("source_id") if isinstance(raw, dict) else None,
        "external_ref": raw.get("external_ref") if isinstance(raw, dict) else None,
        "status": "REJECTED",
        "content_hash": None,
        "reasons": [code],
    }


def _scope_key(raw_items: List[Any], meta: Dict[str, Any]) -> str:
    override = meta.get("scope_key")
    if override is not None:
        return str(override)
    sources = sorted(
        {
            str(raw.get("source_id"))
            for raw in raw_items
            if isinstance(raw, dict) and raw.get("source_id")
        }
    )
    return ",".join(sources)


def _preview_hash(
    *,
    scope_key: str,
    ingest_complete: bool,
    decisions: List[Dict[str, Any]],
    fingerprint: str,
) -> str:
    """sha256 over normalized identities/status + relevant DB fingerprint.

    Rejected items (no stable identity) are excluded; identified decisions
    are sorted by id so the hash is order-independent. No clock participates.
    """
    material: List[Dict[str, Any]] = []
    identified = sorted(
        (d for d in decisions if d.get("id")), key=lambda d: str(d["id"])
    )
    for decision in identified:
        entry: Dict[str, Any] = {
            "id": decision["id"],
            "source_id": decision["source_id"],
            "external_ref": decision["external_ref"],
            "content_hash": decision["content_hash"],
            "status": decision["status"],
        }
        if decision.get("changed_fields"):
            entry["changed_fields"] = list(decision["changed_fields"])
        material.append(entry)
    payload = {
        "v": PREVIEW_HASH_VERSION,
        "scope_key": scope_key,
        "ingest_complete": ingest_complete,
        "items": material,
        "db_fingerprint": fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _deferred_audit_event(preview: Dict[str, Any]) -> Dict[str, Any]:
    """Build the ready-to-emit INGEST/APPLIED event WITHOUT persisting it.

    R1B writes no action_events rows: ``add_action_event`` sanitizes
    ``source`` through ``VALID_SOURCES``, which lacks "RESEARCH", so the
    row would be stored as ``source="MANUAL"`` — a false attribution.
    See R1B_AUDIT_SOURCE_BLOCKED_BY_S2 in the module docstring. Payload
    keeps the S2 house hygiene (no bodies, tokens, or raw payloads).
    """
    sources = sorted(
        {
            d["source_id"]
            for d in preview["items"]
            if d.get("source_id") and d["status"] != "REJECTED"
        }
    )
    return {
        "recorded": False,
        "debt": "R1B_AUDIT_SOURCE_BLOCKED_BY_S2",
        "pending_event": {
            "source": "RESEARCH",
            "event_type": "INGEST",
            "message": "Ingesta de Research aplicada.",
            "severity": "INFO",
            "payload": {
                "counts": preview["counts"],
                "sources": sources,
                "scope_key": preview["scope_key"],
                "preview_hash": preview["preview_hash"],
                "result": "APPLIED",
            },
        },
    }
