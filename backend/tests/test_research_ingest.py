"""Research R1B service tests: read-only preview and atomic ingestion.

No network. No sleeps: timestamp assertions seed legacy values explicitly.
"""

import json
import sqlite3

import pytest

from backend.analytics.research_normalize import normalize_research_item
from backend.services.research_service import (
    ResearchServiceError,
    ingest_research,
    preview_research,
)
from database.db_manager import DatabaseManager
from database.research_store import ResearchStore

# Mirrors the S2B payload-hygiene token list (read-only inspection of
# audit/feature conventions; this suite enforces it on Research events).
FORBIDDEN_PAYLOAD_TOKENS = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "raw",
    "content",
)


@pytest.fixture()
def db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "research.db"))


def _raw(**overrides):
    raw = {
        "source_id": "reuters",
        "external_ref": "acme-q4",
        "title": "Acme beats estimates",
        "url": "https://www.reuters.com/markets/acme?utm_source=x",
        "summary": "Acme reported Q4 results.",
        "published_at": "2026-01-02T08:00:00Z",
        "fetched_at": "2026-01-03T09:30:00Z",
        "epistemic": "REPORTED",
        "entity_tickers": ["ACME"],
    }
    raw.update(overrides)
    return raw


def _db_dump(db):
    """Full database snapshot: every table, every row."""
    connection = sqlite3.connect(db.db_path)
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        return {
            table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
            for table in tables
        }
    finally:
        connection.close()


def _research_rows(db):
    connection = sqlite3.connect(db.db_path)
    connection.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in connection.execute("SELECT * FROM research_items ORDER BY id")
        ]
    finally:
        connection.close()


def _seed_legacy_timestamps(db):
    connection = sqlite3.connect(db.db_path)
    try:
        connection.execute(
            "UPDATE research_items "
            "SET created_at = '2000-01-01 00:00:00', updated_at = '2000-01-01 00:00:00'"
        )
        connection.commit()
    finally:
        connection.close()


def _ingest_events(db):
    return [event for event in db.get_action_events(limit=1000) if event["event_type"] == "INGEST"]


# ---------------------------------------------------------------------------
# PREVIEW
# ---------------------------------------------------------------------------
def test_preview_is_read_only(db):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw(external_ref="exist-a"))])
    store.upsert_items_atomic([normalize_research_item(_raw(external_ref="exist-b"))])
    before = _db_dump(db)

    preview = preview_research(
        db,
        [
            _raw(external_ref="exist-a"),  # existing, unchanged
            _raw(external_ref="exist-b", summary="Revised Q4."),  # existing, changed
            _raw(external_ref="fresh-1"),  # new
        ],
    )

    assert preview["counts"]["new"] == 1
    assert preview["counts"]["changed"] == 1
    assert preview["counts"]["unchanged"] == 1
    assert _db_dump(db) == before  # zero DB writes, audit included


def test_preview_classifies_states_and_changed_fields(db):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw(external_ref="exist-a"))])
    store.upsert_items_atomic([normalize_research_item(_raw(external_ref="exist-b"))])

    preview = preview_research(
        db,
        [
            _raw(external_ref="exist-a"),
            _raw(external_ref="exist-b", summary="Revised."),
            _raw(external_ref="fresh-1"),
        ],
    )

    assert preview["counts"] == {
        "total": 3,
        "new": 1,
        "changed": 1,
        "unchanged": 1,
        "conflict": 0,
        "rejected": 0,
        "warnings": 0,
    }
    by_ref = {d["external_ref"]: d for d in preview["items"]}
    assert by_ref["exist-a"]["status"] == "UNCHANGED"
    assert by_ref["exist-b"]["status"] == "CHANGED"
    assert by_ref["exist-b"]["changed_fields"] == ["summary"]
    assert by_ref["fresh-1"]["status"] == "NEW"


def test_preview_rejects_invalid_input(db):
    preview = preview_research(db, ["not-a-dict"])
    assert preview["counts"]["rejected"] == 1
    decision = preview["items"][0]
    assert decision["status"] == "REJECTED"
    assert decision["reasons"] == ["INVALID_RESEARCH_ITEM_INPUT"]
    assert decision["id"] is None


def test_preview_rejects_missing_fetched_at(db):
    raw = _raw()
    del raw["fetched_at"]
    preview = preview_research(db, [raw])
    assert preview["counts"]["rejected"] == 1
    assert preview["items"][0]["reasons"] == ["FETCHED_AT_REQUIRED"]


def test_preview_request_fetched_at_fills_missing_items(db):
    raw = _raw()
    del raw["fetched_at"]
    preview = preview_research(db, [raw], fetched_at="2026-01-03T09:30:00Z")
    assert preview["counts"]["rejected"] == 0
    assert preview["counts"]["new"] == 1


def test_preview_rejects_identity_less_item(db):
    preview = preview_research(db, [_raw(external_ref=None, url=None)])
    decision = preview["items"][0]
    assert preview["counts"]["rejected"] == 1
    assert decision["reasons"] == ["RESEARCH_ID_REQUIRED"]
    assert decision["id"] is None


def test_preview_dedupes_identical_identity(db):
    preview = preview_research(db, [_raw(), _raw()])
    assert preview["counts"]["total"] == 2
    assert len(preview["items"]) == 1
    assert preview["counts"]["new"] == 1


def test_preview_flags_in_batch_conflict(db):
    preview = preview_research(db, [_raw(), _raw(summary="Conflicting body.")])
    assert preview["counts"]["conflict"] == 1
    assert preview["counts"]["new"] == 0  # CONFLICT overrides the delta state
    conflict = [d for d in preview["items"] if d["status"] == "CONFLICT"]
    assert len(conflict) == 1
    assert conflict[0]["reasons"] == ["IN_BATCH_CONFLICT"]


def test_preview_warnings_are_not_failures(db):
    preview = preview_research(db, [_raw(published_at="not-a-date")])
    assert preview["counts"]["rejected"] == 0
    decision = preview["items"][0]
    assert decision["status"] == "NEW"
    assert decision.get("reasons")
    assert preview["counts"]["warnings"] >= 1


def test_preview_reports_cross_source_duplicate_signals(db):
    preview = preview_research(
        db,
        [
            _raw(source_id="reuters", external_ref="wire-a"),
            _raw(source_id="bloomberg", external_ref="wire-b"),
        ],
    )
    assert len(preview["cross_source_signals"]) == 1
    signal = preview["cross_source_signals"][0]
    assert signal["source_ids"] == ["BLOOMBERG", "REUTERS"]
    assert signal["signal"] == "POSSIBLE_CROSS_SOURCE_DUPLICATE"
    assert preview["counts"]["warnings"] == 1


def test_preview_output_shape_matches_contract(db):
    preview = preview_research(db, [_raw()])
    assert set(preview) == {
        "scope_key",
        "ingest_complete",
        "counts",
        "items",
        "cross_source_signals",
        "preview_hash",
    }
    assert set(preview["counts"]) == {
        "total",
        "new",
        "changed",
        "unchanged",
        "conflict",
        "rejected",
        "warnings",
    }
    allowed = {
        "id",
        "source_id",
        "external_ref",
        "status",
        "content_hash",
        "changed_fields",
        "reasons",
    }
    for decision in preview["items"]:
        assert set(decision) <= allowed
    assert preview["scope_key"] == "reuters"
    assert preview["ingest_complete"] is False
    assert len(preview["preview_hash"]) == 64


def test_preview_hash_is_deterministic(db):
    ResearchStore(db).upsert_items_atomic([normalize_research_item(_raw())])
    batch = [_raw(external_ref="b-1"), _raw(external_ref="a-1", summary="Alt.")]

    first = preview_research(db, batch)
    again = preview_research(db, batch)
    reversed_order = preview_research(db, list(reversed(batch)))

    assert first == again  # identical input -> identical output
    assert reversed_order["preview_hash"] == first["preview_hash"]  # order-independent


def test_preview_hash_ignores_unrelated_rows(db):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw())])
    batch = [_raw()]

    before = preview_research(db, batch)
    store.upsert_items_atomic(
        [normalize_research_item(_raw(source_id="bloomberg", external_ref="wire-z"))]
    )
    after = preview_research(db, batch)

    assert after["preview_hash"] == before["preview_hash"]


def test_preview_hash_changes_when_scoped_identity_changes(db):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw())])
    batch = [_raw()]

    before = preview_research(db, batch)
    store.upsert_items_atomic([normalize_research_item(_raw(summary="Rival edit."))])
    after = preview_research(db, batch)

    assert after["preview_hash"] != before["preview_hash"]


# ---------------------------------------------------------------------------
# INGEST
# ---------------------------------------------------------------------------
def test_ingest_requires_confirmation(db):
    events_before = db.get_action_events(limit=1000)
    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(db, [_raw()], confirm_import=False)
    assert exc.value.code == "CONFIRMATION_REQUIRED"
    assert _research_rows(db) == []
    assert db.get_action_events(limit=1000) == events_before


def test_ingest_without_preview_hash_is_stale(db):
    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(db, [_raw()], confirm_import=True, preview_hash=None)
    assert exc.value.code == "STALE_PREVIEW"
    assert _research_rows(db) == []
    assert _ingest_events(db) == []


def test_ingest_stale_preview_blocks(db):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw())])
    stale = preview_research(db, [_raw(summary="Revised.")])
    # Another writer touches the scoped identity between preview and confirm.
    store.upsert_items_atomic([normalize_research_item(_raw(summary="Rival edit."))])
    before = _db_dump(db)

    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(
            db,
            [_raw(summary="Revised.")],
            confirm_import=True,
            preview_hash=stale["preview_hash"],
        )

    assert exc.value.code == "STALE_PREVIEW"
    assert exc.value.details["current_preview_hash"] != stale["preview_hash"]
    assert _db_dump(db) == before  # zero research writes
    assert _ingest_events(db) == []


def test_ingest_conflict_blocks(db):
    batch = [_raw(), _raw(summary="Conflicting body.")]
    preview = preview_research(db, batch)

    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(
            db, batch, confirm_import=True, preview_hash=preview["preview_hash"]
        )

    assert exc.value.code == "CONFLICTS_BLOCKED"
    assert exc.value.details["conflicts"][0]["state"] == "IN_BATCH_CONFLICT"
    assert _research_rows(db) == []
    assert _ingest_events(db) == []


def test_ingest_applies_new_items_with_deferred_audit(db):
    preview = preview_research(db, [_raw()])
    result = ingest_research(
        db, [_raw()], confirm_import=True, preview_hash=preview["preview_hash"]
    )

    assert result["result"] == "APPLIED"
    assert result["write_counts"] == {"inserted": 1, "updated": 0, "unchanged": 0}
    assert len(_research_rows(db)) == 1

    # R1B_AUDIT_SOURCE_BLOCKED_BY_S2: no action_events row is written.
    audit = result["audit"]
    assert audit["recorded"] is False
    assert audit["debt"] == "R1B_AUDIT_SOURCE_BLOCKED_BY_S2"
    assert db.get_action_events(limit=1000) == []

    pending = audit["pending_event"]
    assert pending["source"] == "RESEARCH"
    assert pending["event_type"] == "INGEST"
    assert pending["severity"] == "INFO"
    payload = pending["payload"]
    assert payload["result"] == "APPLIED"
    assert payload["preview_hash"] == preview["preview_hash"]
    assert payload["scope_key"] == "reuters"
    assert payload["counts"]["new"] == 1
    assert payload["sources"] == ["REUTERS"]


def test_ingest_never_calls_add_action_event(db, monkeypatch):
    """No event can be sanitized to source=MANUAL: the service never routes
    RESEARCH through add_action_event while VALID_SOURCES lacks it."""

    def _forbidden(*args, **kwargs):
        raise AssertionError("add_action_event must not be called in R1B")

    monkeypatch.setattr(db, "add_action_event", _forbidden)

    preview = preview_research(db, [_raw()])
    result = ingest_research(
        db, [_raw()], confirm_import=True, preview_hash=preview["preview_hash"]
    )

    assert result["result"] == "APPLIED"
    assert result["audit"]["recorded"] is False
    events = db.get_action_events(limit=1000)
    assert events == []  # zero events, hence zero falsely-attributed MANUAL rows


def test_ingest_applies_changed_preserving_created_at(db):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw())])
    _seed_legacy_timestamps(db)

    batch = [_raw(summary="Revised.")]
    preview = preview_research(db, batch)
    assert preview["counts"]["changed"] == 1

    result = ingest_research(
        db, batch, confirm_import=True, preview_hash=preview["preview_hash"]
    )

    assert result["write_counts"] == {"inserted": 0, "updated": 1, "unchanged": 0}
    row = _research_rows(db)[0]
    assert row["created_at"] == "2000-01-01 00:00:00"
    assert row["updated_at"] != "2000-01-01 00:00:00"
    assert row["summary"] == "Revised."


def test_ingest_never_rewrites_unchanged(db):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw(external_ref="keep-1"))])
    _seed_legacy_timestamps(db)
    before_keep = [
        row for row in _research_rows(db) if row["external_ref"] == "keep-1"
    ][0]

    batch = [_raw(external_ref="keep-1"), _raw(external_ref="new-2")]
    preview = preview_research(db, batch)
    assert preview["counts"]["unchanged"] == 1
    assert preview["counts"]["new"] == 1

    result = ingest_research(
        db, batch, confirm_import=True, preview_hash=preview["preview_hash"]
    )

    assert result["write_counts"]["inserted"] == 1
    assert result["write_counts"]["updated"] == 0
    after_keep = [
        row for row in _research_rows(db) if row["external_ref"] == "keep-1"
    ][0]
    assert after_keep == before_keep  # untouched, timestamps included


def test_ingest_excludes_rejected_items(db):
    invalid = _raw(external_ref="bad-9")
    del invalid["fetched_at"]  # no request-level fallback -> REJECTED
    batch = [_raw(external_ref="good-7"), invalid]

    preview = preview_research(db, batch)
    assert preview["counts"]["rejected"] == 1

    result = ingest_research(
        db, batch, confirm_import=True, preview_hash=preview["preview_hash"]
    )

    assert result["result"] == "APPLIED"
    assert result["counts"]["rejected"] == 1  # preserved in the response
    rows = _research_rows(db)
    assert len(rows) == 1
    assert rows[0]["external_ref"] == "good-7"


def test_ingest_replay_without_repreview_is_stale(db):
    preview = preview_research(db, [_raw()])
    ingest_research(
        db, [_raw()], confirm_import=True, preview_hash=preview["preview_hash"]
    )
    before = _db_dump(db)

    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(
            db, [_raw()], confirm_import=True, preview_hash=preview["preview_hash"]
        )

    assert exc.value.code == "STALE_PREVIEW"
    assert _db_dump(db) == before  # zero duplicate writes
    assert _ingest_events(db) == []  # R1B writes no audit rows (deferred)


def test_repreview_after_success_is_all_unchanged_then_noop(db):
    first = preview_research(db, [_raw()])
    ingest_research(
        db, [_raw()], confirm_import=True, preview_hash=first["preview_hash"]
    )

    second = preview_research(db, [_raw()])
    assert second["counts"]["unchanged"] == 1
    assert second["counts"]["new"] == 0

    before = _db_dump(db)
    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(
            db, [_raw()], confirm_import=True, preview_hash=second["preview_hash"]
        )

    assert exc.value.code == "NOTHING_TO_APPLY"
    assert _db_dump(db) == before  # zero writes
    assert _ingest_events(db) == []  # no audit rows (deferred in R1B)


def test_store_failure_leaves_db_unchanged_and_skips_audit(db, monkeypatch):
    preview = preview_research(db, [_raw()])
    before = _db_dump(db)

    def _boom(self, items):
        raise RuntimeError("store write failed")

    monkeypatch.setattr(ResearchStore, "upsert_items_atomic", _boom)

    with pytest.raises(RuntimeError):
        ingest_research(
            db, [_raw()], confirm_import=True, preview_hash=preview["preview_hash"]
        )

    assert _db_dump(db) == before
    assert _ingest_events(db) == []  # APPLIED is never recorded on failure


def test_audit_payload_excludes_bodies_and_secrets(db):
    body = "SENTINEL_ARTICLE_BODY_9000"
    raw = _raw(body=body)
    preview = preview_research(db, [raw])
    result = ingest_research(
        db, [raw], confirm_import=True, preview_hash=preview["preview_hash"]
    )

    assert db.get_action_events(limit=1000) == []  # nothing persisted at all
    pending = result["audit"]["pending_event"]
    pending_text = json.dumps(pending, ensure_ascii=False).lower()
    assert body.lower() not in pending_text
    for token in FORBIDDEN_PAYLOAD_TOKENS:
        assert token not in pending_text


def test_blocked_paths_emit_no_audit_events(db):
    # §13 policy: R1B emits no blocked events at all — deferred to R1C/S2
    # (R1B_AUDIT_SOURCE_BLOCKED_BY_S2 covers the success path as well).
    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(db, [_raw()], confirm_import=False)
    assert exc.value.code == "CONFIRMATION_REQUIRED"

    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(db, [_raw()], confirm_import=True, preview_hash=None)
    assert exc.value.code == "STALE_PREVIEW"

    conflict_batch = [_raw(), _raw(summary="Conflicting body.")]
    conflict_preview = preview_research(db, conflict_batch)
    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(
            db,
            conflict_batch,
            confirm_import=True,
            preview_hash=conflict_preview["preview_hash"],
        )
    assert exc.value.code == "CONFLICTS_BLOCKED"

    rejected_only = _raw(external_ref="ghost-1")
    del rejected_only["fetched_at"]
    rejected_preview = preview_research(db, [rejected_only])
    assert rejected_preview["counts"]["rejected"] == 1
    with pytest.raises(ResearchServiceError) as exc:
        ingest_research(
            db,
            [rejected_only],
            confirm_import=True,
            preview_hash=rejected_preview["preview_hash"],
        )
    assert exc.value.code == "NOTHING_TO_APPLY"

    assert _research_rows(db) == []
    assert db.get_action_events(limit=1000) == []
