"""Research persistence foundation tests (R1A) against an isolated database.

No network. No system clock: every fixture supplies ``fetched_at`` explicitly.
"""

import hashlib
import os
import sqlite3

import pytest

from backend.analytics.research_normalize import normalize_research_item
from database import db_manager
from database.db_manager import DatabaseManager
from database.research_store import ResearchStore

MIGRATION_FILENAME = "008_sqlite_research.sql"

EXPECTED_COLUMNS = [
    "id",
    "source_id",
    "external_ref",
    "title",
    "url",
    "summary",
    "published_at",
    "fetched_at",
    "content_hash",
    "epistemic",
    "entity_tickers",
    "normalization_status",
    "provider",
    "ingestion_method",
    "language",
    "reasons",
    "external_ref_derived",
    "created_at",
    "updated_at",
]


@pytest.fixture()
def db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "research.db"))


@pytest.fixture()
def store(db):
    return ResearchStore(db)


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
        "provider": "MANUAL",
        "ingestion_method": "MANUAL",
        "language": "en",
    }
    raw.update(overrides)
    return raw


def _file_checksum(filename):
    # Mirrors DatabaseManager._run_migrations: text-mode read (universal
    # newlines) then sha256 over the UTF-8 encoding.
    path = os.path.join(db_manager.MIGRATIONS_DIR, filename)
    with open(path, "r", encoding="utf-8") as handle:
        return hashlib.sha256(handle.read().encode("utf-8")).hexdigest()


def _raw_rows(db):
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


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------
def test_migration_applies_on_clean_db(db):
    connection = sqlite3.connect(db.db_path)
    connection.row_factory = sqlite3.Row
    try:
        columns = [
            row["name"]
            for row in connection.execute("PRAGMA table_info(research_items)")
        ]
        index_names = {
            row["name"]
            for row in connection.execute("PRAGMA index_list(research_items)")
        }
    finally:
        connection.close()

    assert columns == EXPECTED_COLUMNS
    assert {
        "idx_research_items_source_external",
        "idx_research_items_source",
        "idx_research_items_published",
        "idx_research_items_epistemic",
    } <= index_names


def test_migration_registered_and_checksummed(db):
    expected_checksum = _file_checksum(MIGRATION_FILENAME)

    connection = sqlite3.connect(db.db_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT version, filename, checksum FROM schema_migrations WHERE filename = ?",
            (MIGRATION_FILENAME,),
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row["version"] == "008"
    assert row["checksum"] == expected_checksum


def test_migration_reinit_is_idempotent_and_existing_migrations_untouched(db):
    DatabaseManager(db_path=db.db_path)  # second construction must not raise

    connection = sqlite3.connect(db.db_path)
    connection.row_factory = sqlite3.Row
    try:
        migrations = connection.execute(
            "SELECT version, filename, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
    finally:
        connection.close()

    versions = [row["version"] for row in migrations]
    assert versions[:7] == ["001", "002", "003", "004", "005", "006", "007"]
    assert versions.count("008") == 1

    for row in migrations:
        assert _file_checksum(row["filename"]) == row["checksum"]


# ---------------------------------------------------------------------------
# Store round-trip
# ---------------------------------------------------------------------------
def test_insert_round_trip_is_faithful(store):
    # Published timestamp unparsable on purpose -> normalization reasons exist.
    item = normalize_research_item(_raw(published_at="ASAP", body="raw article body"))
    assert "reasons" in item

    counts = store.upsert_items_atomic([item])
    assert counts == {"inserted": 1, "updated": 0, "unchanged": 0}

    # Identity queries use the R0-normalized source_id (uppercase).
    loaded = store.get_by_identities([(item["source_id"], item["external_ref"])])
    assert loaded == [item]
    assert "body" not in loaded[0]
    assert "content" not in loaded[0]
    assert loaded[0]["provenance"]["content_hash"] == item["content_hash"]


def test_json_entity_tickers_and_reasons_round_trip(db, store):
    item = normalize_research_item(
        _raw(
            title="Acme reporta utilidades — año 2026",
            entity_tickers=["ACME", "NYQ"],
            published_at="not-a-date",
        )
    )
    assert item.get("reasons")

    store.upsert_items_atomic([item])
    loaded = store.get_by_identities([(item["source_id"], item["external_ref"])])[0]

    assert loaded["entity_tickers"] == item["entity_tickers"]
    assert isinstance(loaded["entity_tickers"], list)
    assert loaded["reasons"] == item["reasons"]
    assert loaded["title"] == item["title"]

    raw_row = _raw_rows(db)[0]
    assert isinstance(raw_row["entity_tickers"], str)
    assert isinstance(raw_row["reasons"], str)


def test_external_ref_derived_flag_round_trips(store):
    item = normalize_research_item(_raw(external_ref=None))
    assert item.get("external_ref_derived") is True

    store.upsert_items_atomic([item])
    loaded = store.list_items()
    assert loaded == [item]
    assert loaded[0].get("external_ref_derived") is True


def test_minimal_item_round_trip_omits_optional_keys(store):
    item = normalize_research_item(
        {
            "source_id": "wire",
            "external_ref": "brief-1",
            "title": "Short brief",
            "fetched_at": "2026-01-03T09:30:00Z",
        }
    )
    for key in ("summary", "provider", "ingestion_method", "language"):
        assert key not in item

    store.upsert_items_atomic([item])
    assert store.list_items() == [item]


# ---------------------------------------------------------------------------
# Idempotency / update semantics
# ---------------------------------------------------------------------------
def test_same_identity_same_hash_is_true_noop(db, store):
    item = normalize_research_item(_raw())
    store.upsert_items_atomic([item])
    _seed_legacy_timestamps(db)
    before = _raw_rows(db)

    counts = store.upsert_items_atomic([item])
    assert counts == {"inserted": 0, "updated": 0, "unchanged": 1}
    assert _raw_rows(db) == before  # created_at and updated_at untouched


def test_same_identity_new_hash_updates_and_preserves_created_at(db, store):
    item = normalize_research_item(_raw())
    store.upsert_items_atomic([item])
    _seed_legacy_timestamps(db)
    before = _raw_rows(db)[0]

    changed = normalize_research_item(_raw(summary="Acme Q4 results, revised."))
    counts = store.upsert_items_atomic([changed])
    assert counts == {"inserted": 0, "updated": 1, "unchanged": 0}

    after = _raw_rows(db)[0]
    assert after["id"] == before["id"]
    assert after["created_at"] == "2000-01-01 00:00:00"
    assert after["updated_at"] != "2000-01-01 00:00:00"
    assert after["content_hash"] != before["content_hash"]
    assert after["summary"] == "Acme Q4 results, revised."
    assert after["entity_tickers"] == before["entity_tickers"]


def test_new_identity_inserts(store):
    counts = store.upsert_items_atomic([normalize_research_item(_raw())])
    assert counts == {"inserted": 1, "updated": 0, "unchanged": 0}


def test_cross_source_same_external_ref_is_independent(db, store):
    reuters_item = normalize_research_item(_raw(source_id="reuters", external_ref="wire-1"))
    bloomberg_item = normalize_research_item(
        _raw(source_id="bloomberg", external_ref="wire-1", title="Different wire story")
    )
    store.upsert_items_atomic([reuters_item, bloomberg_item])

    loaded = store.get_by_identities(
        [
            (reuters_item["source_id"], "wire-1"),
            (bloomberg_item["source_id"], "wire-1"),
        ]
    )
    assert len(loaded) == 2
    by_source = {entry["source_id"]: entry for entry in loaded}
    assert by_source[reuters_item["source_id"]]["title"] == "Acme beats estimates"
    assert by_source[bloomberg_item["source_id"]]["title"] == "Different wire story"

    before_other = [
        r for r in _raw_rows(db) if r["source_id"] == bloomberg_item["source_id"]
    ][0]
    changed = normalize_research_item(
        _raw(source_id="reuters", external_ref="wire-1", title="Updated wire story")
    )
    store.upsert_items_atomic([changed])
    after_other = [
        r for r in _raw_rows(db) if r["source_id"] == bloomberg_item["source_id"]
    ][0]
    assert after_other == before_other


# ---------------------------------------------------------------------------
# Queries: ordering and filters
# ---------------------------------------------------------------------------
def test_deterministic_ordering_with_ties_and_nulls(store):
    items = [
        normalize_research_item(_raw(external_ref="a-old", published_at="2026-01-01T00:00:00Z")),
        normalize_research_item(_raw(external_ref="b-tie2", published_at="2026-01-03T00:00:00Z")),
        normalize_research_item(_raw(external_ref="c-null", published_at=None)),
        normalize_research_item(_raw(external_ref="d-tie1", published_at="2026-01-03T00:00:00Z")),
        normalize_research_item(_raw(external_ref="e-tie3", published_at="2026-01-03T00:00:00Z")),
    ]
    store.upsert_items_atomic(items)

    tie_ids = sorted(entry["id"] for entry in (items[1], items[3], items[4]))
    expected = tie_ids + [items[0]["id"], items[2]["id"]]
    assert [entry["id"] for entry in store.list_items()] == expected


def test_list_items_filters_source_epistemic_and_limit(store):
    reuters_row = normalize_research_item(_raw(source_id="reuters", external_ref="r1"))
    bloomberg_row = normalize_research_item(
        _raw(source_id="bloomberg", external_ref="b1", epistemic="ANALYSIS")
    )
    store.upsert_items_atomic(
        [
            reuters_row,
            normalize_research_item(_raw(source_id="reuters", external_ref="r2")),
            bloomberg_row,
        ]
    )

    reuters_rows = store.list_items(source_id=reuters_row["source_id"])
    assert len(reuters_rows) == 2
    assert all(row["source_id"] == reuters_row["source_id"] for row in reuters_rows)

    analysis_rows = store.list_items(epistemic="ANALYSIS")
    assert len(analysis_rows) == 1
    assert analysis_rows[0]["source_id"] == bloomberg_row["source_id"]

    limited = store.list_items(limit=1)
    assert len(limited) == 1
    assert limited[0]["id"] == store.list_items()[0]["id"]


# ---------------------------------------------------------------------------
# Relevant-state fingerprint
# ---------------------------------------------------------------------------
def test_fingerprint_is_deterministic_and_order_independent(store):
    reuters_item = normalize_research_item(_raw(source_id="reuters", external_ref="acme-q4"))
    bloomberg_item = normalize_research_item(
        _raw(source_id="bloomberg", external_ref="wire-1")
    )
    store.upsert_items_atomic([reuters_item, bloomberg_item])
    identities = [
        (reuters_item["source_id"], reuters_item["external_ref"]),
        (bloomberg_item["source_id"], bloomberg_item["external_ref"]),
    ]

    fingerprint = store.relevant_state_fingerprint(identities)
    assert fingerprint == store.relevant_state_fingerprint(list(reversed(identities)))
    assert fingerprint == store.relevant_state_fingerprint(identities)
    assert len(fingerprint) == 64
    assert fingerprint != store.relevant_state_fingerprint([identities[0]])


def test_fingerprint_changes_for_affected_identity(store):
    item = normalize_research_item(_raw())
    store.upsert_items_atomic([item])
    scope = [(item["source_id"], item["external_ref"])]
    before = store.relevant_state_fingerprint(scope)

    changed = normalize_research_item(_raw(summary="Revised summary."))
    store.upsert_items_atomic([changed])

    assert store.relevant_state_fingerprint(scope) != before


def test_fingerprint_ignores_unrelated_research_rows(store):
    item = normalize_research_item(_raw())
    store.upsert_items_atomic([item])
    scope = [(item["source_id"], item["external_ref"])]
    before = store.relevant_state_fingerprint(scope)

    unrelated_new = normalize_research_item(
        _raw(source_id="bloomberg", external_ref="wire-9")
    )
    store.upsert_items_atomic([unrelated_new])
    unrelated_changed = normalize_research_item(
        _raw(source_id="bloomberg", external_ref="wire-9", title="Rewritten wire")
    )
    store.upsert_items_atomic([unrelated_changed])

    assert store.relevant_state_fingerprint(scope) == before


# ---------------------------------------------------------------------------
# Atomicity and integrity guards
# ---------------------------------------------------------------------------
def test_atomic_rollback_when_nth_write_fails(db, store):
    good_first = normalize_research_item(_raw(external_ref="ok-1"))
    good_second = normalize_research_item(_raw(external_ref="ok-2"))
    failing = dict(normalize_research_item(_raw(external_ref="bad-3")), title=None)

    with pytest.raises(sqlite3.IntegrityError):
        store.upsert_items_atomic([good_first, good_second, failing])

    assert _raw_rows(db) == []  # zero partial Research writes


def test_batch_identity_conflict_fails_without_writes(db, store):
    first = normalize_research_item(_raw())
    conflicting = normalize_research_item(_raw(summary="Same identity, other hash."))

    with pytest.raises(ValueError, match="RESEARCH_BATCH_IDENTITY_CONFLICT"):
        store.upsert_items_atomic([first, conflicting])

    assert _raw_rows(db) == []


def test_missing_id_is_rejected(db, store):
    identity_less = normalize_research_item(_raw(external_ref=None, url=None))
    assert identity_less["id"] is None

    with pytest.raises(ValueError, match="RESEARCH_ID_REQUIRED"):
        store.upsert_items_atomic([identity_less])

    assert _raw_rows(db) == []
