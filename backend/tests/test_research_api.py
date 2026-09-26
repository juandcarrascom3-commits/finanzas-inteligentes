"""Research R1C API tests: preview, ingest, list and detail endpoints.

Runs against the T0 conftest temp database (never the personal DB).
No network, no providers: every fixture supplies ``fetched_at`` explicitly
and every test uses a unique ``source_id`` so shared-DB state stays isolated.
"""

import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

import backend.app as app_module
from backend.analytics.research_normalize import normalize_research_item
from backend.app import app, db
from database.research_store import ResearchStore

client = TestClient(app)

# Mirrors the S2B payload-hygiene token list (enforced on Research events).
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

# R1C batch/list boundary: house per-list import cap (MAX_IMPORT_PLAN_ITEMS).
RESEARCH_MAX_ITEMS = 5_000


@pytest.fixture()
def source():
    return f"apiwire{uuid.uuid4().hex[:8]}"


def _raw(source, external_ref="acme-q4", **overrides):
    raw = {
        "source_id": source,
        "external_ref": external_ref,
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


def _preview(items, **extra):
    response = client.post("/api/research/preview", json={"items": items, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def _ingest(items, preview_hash=None, confirm_import=True, **extra):
    return client.post(
        "/api/research/ingest",
        json={
            "items": items,
            "preview_hash": preview_hash,
            "confirm_import": confirm_import,
            **extra,
        },
    )


def _db_dump():
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


def _research_rows(source=None):
    connection = sqlite3.connect(db.db_path)
    connection.row_factory = sqlite3.Row
    try:
        if source is None:
            sql = "SELECT * FROM research_items ORDER BY id"
            params: tuple = ()
        else:
            sql = "SELECT * FROM research_items WHERE source_id = ? ORDER BY id"
            params = (source.upper(),)
        return [dict(row) for row in connection.execute(sql, params)]
    finally:
        connection.close()


def _all_event_ids():
    return {event["id"] for event in db.get_action_events(limit=5000)}


def _new_events(before_ids):
    return [
        event
        for event in db.get_action_events(limit=5000)
        if event["id"] not in before_ids
    ]


# ---------------------------------------------------------------------------
# 1-3 PREVIEW
# ---------------------------------------------------------------------------
def test_preview_endpoint_is_read_only(source):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw(source, "exist-a"))])
    store.upsert_items_atomic([normalize_research_item(_raw(source, "exist-b"))])
    before = _db_dump()
    events_before = _all_event_ids()

    response = client.post(
        "/api/research/preview",
        json={
            "items": [
                _raw(source, "exist-a"),
                _raw(source, "exist-b", summary="Revised Q4."),
                _raw(source, "fresh-1"),
                "not-a-dict",
            ]
        },
    )

    assert response.status_code == 200
    assert _db_dump() == before  # zero DB writes, audit included
    assert _all_event_ids() == events_before


def test_preview_classifications_and_counts(source):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw(source, "exist-a"))])
    store.upsert_items_atomic([normalize_research_item(_raw(source, "exist-b"))])

    data = _preview(
        [
            _raw(source, "exist-a"),
            _raw(source, "exist-b", summary="Revised."),
            _raw(source, "fresh-1"),
        ]
    )

    assert data["counts"] == {
        "total": 3,
        "new": 1,
        "changed": 1,
        "unchanged": 1,
        "conflict": 0,
        "rejected": 0,
        "warnings": 0,
    }
    by_ref = {entry["external_ref"]: entry for entry in data["items"]}
    assert by_ref["exist-a"]["status"] == "UNCHANGED"
    assert by_ref["exist-b"]["status"] == "CHANGED"
    assert by_ref["exist-b"]["changed_fields"] == ["summary"]
    assert by_ref["fresh-1"]["status"] == "NEW"
    assert data["scope_key"] == source
    assert data["ingest_complete"] is False

    # In-batch identity conflict: CONFLICT overrides the delta state.
    conflict_data = _preview(
        [_raw(source, "conf-1"), _raw(source, "conf-1", summary="Conflicting body.")]
    )
    assert conflict_data["counts"]["total"] == 2
    assert conflict_data["counts"]["conflict"] == 1
    assert conflict_data["counts"]["new"] == 0
    conflict_decisions = [
        entry for entry in conflict_data["items"] if entry["status"] == "CONFLICT"
    ]
    assert len(conflict_decisions) == 1
    assert conflict_decisions[0]["reasons"] == ["IN_BATCH_CONFLICT"]


def test_preview_hash_is_deterministic(source):
    batch = [_raw(source, "b-1"), _raw(source, "a-1", summary="Alt.")]

    first = _preview(batch)
    again = _preview(batch)
    reversed_order = _preview(list(reversed(batch)))

    assert len(first["preview_hash"]) == 64
    assert again["preview_hash"] == first["preview_hash"]
    assert reversed_order["preview_hash"] == first["preview_hash"]

    # A rival writer touching the scoped identity invalidates the hash.
    ResearchStore(db).upsert_items_atomic(
        [normalize_research_item(_raw(source, "b-1", summary="Rival edit."))]
    )
    after = _preview(batch)
    assert after["preview_hash"] != first["preview_hash"]


# ---------------------------------------------------------------------------
# 4-7 INGEST GATES
# ---------------------------------------------------------------------------
def test_valid_ingest_succeeds(source):
    items = [_raw(source, "fresh-1")]
    preview = _preview(items)

    response = _ingest(items, preview_hash=preview["preview_hash"])

    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "APPLIED"
    assert data["write_counts"] == {"inserted": 1, "updated": 0, "unchanged": 0}
    assert data["counts"]["new"] == 1
    assert data["preview_hash"] == preview["preview_hash"]
    assert len(_research_rows(source)) == 1


def test_stale_preview_hash_rejected(source):
    store = ResearchStore(db)
    store.upsert_items_atomic([normalize_research_item(_raw(source, "stale-1"))])
    items = [_raw(source, "stale-1", summary="Revised.")]
    preview = _preview(items)
    # Another writer touches the scoped identity between preview and confirm.
    store.upsert_items_atomic(
        [normalize_research_item(_raw(source, "stale-1", summary="Rival edit."))]
    )
    rows_before = _research_rows(source)
    events_before = _all_event_ids()

    response = _ingest(items, preview_hash=preview["preview_hash"])

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "STALE_PREVIEW"
    assert detail["current_preview_hash"] != preview["preview_hash"]
    assert _research_rows(source) == rows_before  # rival row untouched
    assert _all_event_ids() == events_before


def test_ingest_without_preview_hash_is_stale(source):
    items = [_raw(source, "nohash-1")]
    events_before = _all_event_ids()

    response = _ingest(items, preview_hash=None)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "STALE_PREVIEW"
    assert _research_rows(source) == []
    assert _all_event_ids() == events_before


def test_ingest_conflict_rejected(source):
    items = [_raw(source, "conf-9"), _raw(source, "conf-9", summary="Conflicting body.")]
    preview = _preview(items)
    events_before = _all_event_ids()

    response = _ingest(items, preview_hash=preview["preview_hash"])

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "CONFLICTS_BLOCKED"
    assert detail["conflicts"][0]["state"] == "IN_BATCH_CONFLICT"
    assert detail["counts"]["conflict"] == 1
    assert _research_rows(source) == []
    assert _all_event_ids() == events_before


# ---------------------------------------------------------------------------
# 8-9 BOUNDARY BEHAVIOR
# ---------------------------------------------------------------------------
def test_malformed_payload_is_controlled(source):
    events_before = _all_event_ids()
    not_a_list = client.post("/api/research/preview", json={"items": "not-a-list"})
    assert not_a_list.status_code == 422
    scalar_batch = client.post(
        "/api/research/ingest", json={"items": 42, "confirm_import": True}
    )
    assert scalar_batch.status_code == 422

    # Controlled shape: structured validation tree, never a traceback.
    body = json.dumps(not_a_list.json()).lower()
    assert "traceback" not in body
    assert _research_rows(source) == []
    assert _all_event_ids() == events_before  # 422 paths emit zero events


def test_ingest_without_confirmation_is_400(source):
    items = [_raw(source, "unconf-1")]
    events_before = _all_event_ids()

    response = _ingest(items, confirm_import=False)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "CONFIRMATION_REQUIRED"
    assert set(detail) == {"code", "message"}  # documented fields only
    assert _research_rows(source) == []
    assert _all_event_ids() == events_before  # blocked path: zero events


def test_non_dict_item_is_rejected_not_422(source):
    response = client.post("/api/research/preview", json={"items": ["not-a-dict"]})

    assert response.status_code == 200
    data = response.json()
    assert data["counts"]["rejected"] == 1
    decision = data["items"][0]
    assert decision["status"] == "REJECTED"
    assert decision["reasons"] == ["INVALID_RESEARCH_ITEM_INPUT"]
    assert decision["id"] is None


def test_oversized_research_batch_is_422_with_zero_persistence(source):
    before = _db_dump()
    events_before = _all_event_ids()
    oversized = [_raw(source, f"big-{index}") for index in range(RESEARCH_MAX_ITEMS + 1)]

    preview_response = client.post("/api/research/preview", json={"items": oversized})
    ingest_response = client.post(
        "/api/research/ingest",
        json={"items": oversized, "confirm_import": True, "preview_hash": "a" * 64},
    )

    assert preview_response.status_code == 422
    assert ingest_response.status_code == 422
    assert _db_dump() == before  # zero persistence, audit included
    assert _all_event_ids() == events_before


# ---------------------------------------------------------------------------
# 10-11 IDEMPOTENCY
# ---------------------------------------------------------------------------
def test_repeated_ingest_is_idempotent(source):
    items = [_raw(source, "dup-1")]
    preview = _preview(items)

    first = _ingest(items, preview_hash=preview["preview_hash"])
    assert first.status_code == 200
    rows_after_first = _research_rows(source)
    events_after_first = _all_event_ids()

    # Replaying the consumed hash is stale: no duplicate write, no 2nd event.
    replay = _ingest(items, preview_hash=preview["preview_hash"])
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "STALE_PREVIEW"
    assert _research_rows(source) == rows_after_first
    assert _all_event_ids() == events_after_first


def test_all_unchanged_ingest_is_nothing_to_apply(source):
    items = [_raw(source, "noop-1")]
    ResearchStore(db).upsert_items_atomic([normalize_research_item(items[0])])

    fresh = _preview(items)
    assert fresh["counts"]["unchanged"] == 1
    rows_before = _research_rows(source)
    events_before = _all_event_ids()

    response = _ingest(items, preview_hash=fresh["preview_hash"])

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "NOTHING_TO_APPLY"
    assert _research_rows(source) == rows_before
    assert _all_event_ids() == events_before


# ---------------------------------------------------------------------------
# 12-16 AUDIT ACTIVATION
# ---------------------------------------------------------------------------
def test_preview_creates_zero_action_events(source):
    events_before = _all_event_ids()

    response = client.post(
        "/api/research/preview", json={"items": [_raw(source, "quiet-1")]}
    )

    assert response.status_code == 200
    assert _all_event_ids() == events_before
    assert [
        event
        for event in _new_events(events_before)
        if event["source"] == "RESEARCH"
    ] == []


def test_ingest_success_writes_exactly_one_research_event(source):
    items = [_raw(source, "audit-1")]
    preview = _preview(items)
    events_before = _all_event_ids()

    response = _ingest(items, preview_hash=preview["preview_hash"])
    assert response.status_code == 200

    new = _new_events(events_before)
    assert len(new) == 1
    event = new[0]
    assert event["source"] == "RESEARCH"
    assert event["event_type"] == "INGEST"
    assert event["severity"] == "INFO"
    payload = json.loads(event["payload"])
    assert payload["counts"] == response.json()["counts"]
    assert payload["preview_hash"] == preview["preview_hash"]
    assert payload["scope_key"] == source
    assert payload["sources"] == [source.upper()]
    assert payload["result"] == "APPLIED"
    assert response.json()["audit"] == {
        "recorded": True,
        "source": "RESEARCH",
        "event_type": "INGEST",
    }


def test_audit_payload_excludes_bodies_and_secrets(source):
    body = "SENTINEL_ARTICLE_BODY_9000"
    item = _raw(source, "hygiene-1", body=body)
    preview = _preview([item])
    events_before = _all_event_ids()

    response = _ingest([item], preview_hash=preview["preview_hash"])
    assert response.status_code == 200

    new = _new_events(events_before)
    assert len(new) == 1
    event_text = json.dumps(new[0], ensure_ascii=False).lower()
    assert body.lower() not in event_text
    for token in FORBIDDEN_PAYLOAD_TOKENS:
        assert token not in event_text


def test_failed_persistence_is_sanitized_500_without_audit(
    source, monkeypatch, caplog
):
    items = [_raw(source, "boom-1")]
    preview = _preview(items)
    events_before = _all_event_ids()
    rows_before = _research_rows(source)

    def _boom(self, batch):
        raise RuntimeError("store write failed")

    monkeypatch.setattr(ResearchStore, "upsert_items_atomic", _boom)

    with caplog.at_level("ERROR"):
        response = _ingest(items, preview_hash=preview["preview_hash"])

    assert response.status_code == 500
    # The response stays sanitized, but the original failure is logged
    # server-side so a production 500 is diagnosable.
    assert "store write failed" in caplog.text
    detail = response.json()["detail"]
    assert detail == {
        "code": "INTERNAL_ERROR",
        "message": "Error interno de Research.",
    }
    assert "store write failed" not in json.dumps(response.json())
    assert _research_rows(source) == rows_before
    assert _all_event_ids() == events_before  # APPLIED is never recorded


def test_audit_write_failure_keeps_ingest_and_reports_false(source, monkeypatch):
    items = [_raw(source, "noaudit-1")]
    preview = _preview(items)

    def _denied(*args, **kwargs):
        raise RuntimeError("audit write denied")

    monkeypatch.setattr(app_module.db, "add_action_event", _denied)

    response = _ingest(items, preview_hash=preview["preview_hash"])

    assert response.status_code == 200  # committed ingest is not reversed
    data = response.json()
    assert data["result"] == "APPLIED"
    assert data["audit"] == {
        "recorded": False,
        "source": "RESEARCH",
        "event_type": "INGEST",
    }
    assert len(_research_rows(source)) == 1


# ---------------------------------------------------------------------------
# 17-19 LIST
# ---------------------------------------------------------------------------
def test_list_items_order_filter_and_limit(source):
    other = f"apiother{uuid.uuid4().hex[:8]}"
    store = ResearchStore(db)
    seeded = [
        normalize_research_item(_raw(source, "a-old", published_at="2026-01-01T00:00:00Z")),
        normalize_research_item(_raw(source, "b-tie2", published_at="2026-01-03T00:00:00Z")),
        normalize_research_item(_raw(source, "c-null", published_at=None)),
        normalize_research_item(
            _raw(source, "d-tie1", published_at="2026-01-03T00:00:00Z", epistemic="ANALYSIS")
        ),
        normalize_research_item(_raw(source, "e-tie3", published_at="2026-01-03T00:00:00Z")),
        normalize_research_item(
            _raw(other, "f-only", published_at="2026-01-04T00:00:00Z")
        ),
    ]
    store.upsert_items_atomic(seeded)

    response = client.get("/api/research/items", params={"source_id": source})
    assert response.status_code == 200
    rows = response.json()
    tie_ids = sorted(entry["id"] for entry in (seeded[1], seeded[3], seeded[4]))
    expected = tie_ids + [seeded[0]["id"], seeded[2]["id"]]  # NULLs last
    assert [row["id"] for row in rows] == expected  # published_at DESC, id ASC
    assert all(row["source_id"] == source.upper() for row in rows)

    # Lowercase input normalizes to the canonical Store representation.
    normalized = client.get("/api/research/items", params={"source_id": source.lower()})
    assert [row["id"] for row in normalized.json()] == expected

    analysis = client.get(
        "/api/research/items", params={"source_id": source, "epistemic": "ANALYSIS"}
    )
    assert [row["id"] for row in analysis.json()] == [seeded[3]["id"]]

    limited = client.get(
        "/api/research/items", params={"source_id": source, "limit": 1}
    )
    assert [row["id"] for row in limited.json()] == [expected[0]]


def test_list_rejects_invalid_filters(source):
    invalid_epistemic = client.get("/api/research/items", params={"epistemic": "GOSSIP"})
    assert invalid_epistemic.status_code == 422
    assert invalid_epistemic.json()["detail"] == {"code": "EPISTEMIC_INVALID"}

    invalid_source = client.get("/api/research/items", params={"source_id": "bad id!"})
    assert invalid_source.status_code == 422
    assert invalid_source.json()["detail"] == {"code": "SOURCE_ID_INVALID"}

    # Existing vocabulary, case-insensitively normalized.
    accepted = client.get("/api/research/items", params={"epistemic": "reported"})
    assert accepted.status_code == 200


def test_list_limit_boundaries(source):
    below = client.get("/api/research/items", params={"limit": 0})
    above = client.get("/api/research/items", params={"limit": RESEARCH_MAX_ITEMS + 1})
    at_min = client.get("/api/research/items", params={"limit": 1})
    at_max = client.get("/api/research/items", params={"limit": RESEARCH_MAX_ITEMS})

    assert below.status_code == 422
    assert above.status_code == 422
    assert at_min.status_code == 200
    assert at_max.status_code == 200


# ---------------------------------------------------------------------------
# 20-22 DETAIL
# ---------------------------------------------------------------------------
def test_detail_returns_item_with_provenance(source):
    item = normalize_research_item(_raw(source, "det-1"))
    ResearchStore(db).upsert_items_atomic([item])

    response = client.get(f"/api/research/items/{source.upper()}/det-1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item["id"]
    assert data["source_id"] == source.upper()
    assert data["external_ref"] == "det-1"
    assert data["provenance"]["source_id"] == source.upper()
    assert data["provenance"]["content_hash"] == item["content_hash"]


def test_detail_unknown_identity_is_404(source):
    response = client.get(f"/api/research/items/{source.upper()}/ghost-ref")

    assert response.status_code == 404
    assert response.json()["detail"] == {"code": "RESEARCH_ITEM_NOT_FOUND"}


def test_detail_supports_external_ref_with_slash(source):
    item = normalize_research_item(_raw(source, "markets/acme-live"))
    ResearchStore(db).upsert_items_atomic([item])

    response = client.get(f"/api/research/items/{source.upper()}/markets/acme-live")

    assert response.status_code == 200
    assert response.json()["id"] == item["id"]
    assert response.json()["external_ref"] == "markets/acme-live"
