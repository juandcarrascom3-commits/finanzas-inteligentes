"""Pure tests for deterministic Research dedupe, cross-source signal and delta."""

import json
from copy import deepcopy

from backend.analytics.research_normalize import normalize_research_item
from backend.analytics.research_snapshot import (
    DELTA_STATES,
    compute_delta,
    cross_source_duplicate_signals,
    deduplicate_research_batch,
)


FETCHED = "2026-09-20T00:00:00+00:00"


def make_item(source_id="SRC", external_ref="r1", title="Acme raises guidance", **overrides):
    raw = {
        "source_id": source_id,
        "external_ref": external_ref,
        "title": title,
        "url": "https://example.com/story",
        "published_at": "2026-09-01T00:00:00Z",
        "epistemic": "REPORTED",
        "entity_tickers": ["AAPL"],
    }
    raw.update(overrides)
    return normalize_research_item(raw, fetched_at=FETCHED)


# ------------------------------------------------------------- dedupe


def test_exact_in_batch_duplicate_collapses():
    batch = [make_item(), make_item()]
    result = deduplicate_research_batch(batch)
    assert len(result["items"]) == 1
    assert result["duplicate_rows"] == 1
    assert result["in_batch_conflicts"] == []


def test_same_identity_different_hash_is_in_batch_conflict():
    first = make_item(title="Version one")
    second = make_item(title="Version two rewritten")
    result = deduplicate_research_batch([first, second])
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "Version one"  # first occurrence kept
    assert result["duplicate_rows"] == 0
    assert len(result["in_batch_conflicts"]) == 1
    conflict = result["in_batch_conflicts"][0]
    assert conflict["state"] == "IN_BATCH_CONFLICT"
    assert conflict["kept_content_hash"] == first["content_hash"]
    assert conflict["conflicting_content_hash"] == second["content_hash"]


def test_different_identities_never_collapsed():
    batch = [make_item(external_ref="r1"), make_item(external_ref="r2")]
    result = deduplicate_research_batch(batch)
    assert len(result["items"]) == 2
    assert result["duplicate_rows"] == 0


def test_items_without_external_ref_kept_as_is():
    a = normalize_research_item(
        {"source_id": "SRC", "title": "No ref A", "url": None, "epistemic": "REPORTED"},
        fetched_at=FETCHED,
    )
    b = normalize_research_item(
        {"source_id": "SRC", "title": "No ref B", "url": None, "epistemic": "REPORTED"},
        fetched_at=FETCHED,
    )
    result = deduplicate_research_batch([a, b])
    assert len(result["items"]) == 2


def test_dedupe_does_not_mutate_inputs():
    batch = [make_item(), make_item()]
    before = deepcopy(batch)
    deduplicate_research_batch(batch)
    assert batch == before


# ------------------------------------------------------------- cross-source signal


def test_cross_source_signal_reported_but_records_never_merged():
    a = make_item(source_id="SRC_A", external_ref="a1")
    b = make_item(source_id="SRC_B", external_ref="b1")
    assert a["content_hash"] == b["content_hash"]  # same material content + URL
    assert a["id"] != b["id"]

    result = deduplicate_research_batch([a, b])
    assert len(result["items"]) == 2  # never merged across sources

    signals = cross_source_duplicate_signals(result["items"])
    assert len(signals) == 1
    assert signals[0]["source_ids"] == ["SRC_A", "SRC_B"]
    assert signals[0]["entity_ticker"] == "AAPL"
    assert signals[0]["signal"] == "POSSIBLE_CROSS_SOURCE_DUPLICATE"


def test_cross_source_signal_absent_for_distinct_content():
    a = make_item(source_id="SRC_A", external_ref="a1", title="Story one")
    b = make_item(source_id="SRC_B", external_ref="b1", title="Story two different")
    assert cross_source_duplicate_signals([a, b]) == []


def test_same_source_cross_url_not_reported_as_cross_source():
    a = make_item(external_ref="r1")
    b = make_item(external_ref="r2")
    signals = cross_source_duplicate_signals([a, b])
    assert signals == []  # only one distinct source_id


# ------------------------------------------------------------- delta


def test_delta_new_unchanged_changed():
    previous = [
        make_item(external_ref="r1", title="Old title"),
        make_item(external_ref="r2", title="Stable story"),
    ]
    current = [
        make_item(external_ref="r1", title="New title rewritten"),
        make_item(external_ref="r2", title="Stable story"),
        make_item(external_ref="r3", title="Brand new story"),
    ]
    delta = compute_delta(previous, current)
    assert delta["status"] == "READY"
    states = {row["id"]: row["state"] for row in delta["items"]}
    assert states[make_item(external_ref="r1", title="New title rewritten")["id"]] == "CHANGED"
    assert states[make_item(external_ref="r2")["id"]] == "UNCHANGED"
    assert states[make_item(external_ref="r3")["id"]] == "NEW"
    assert (delta["new_count"], delta["changed_count"], delta["unchanged_count"]) == (1, 1, 1)


def test_delta_changed_fields_deterministic():
    previous = [make_item(external_ref="r1", title="Old title")]
    current = [make_item(external_ref="r1", title="New title")]
    delta = compute_delta(previous, current)
    row = next(r for r in delta["items"] if r["state"] == "CHANGED")
    assert row["changed_fields"] == ["title"]


def test_delta_missing_from_current_neutral_collection():
    keep = make_item(external_ref="r1")
    gone = make_item(external_ref="r2")
    delta = compute_delta([keep, gone], [keep])
    assert delta["missing_count"] == 1
    assert delta["missing_from_current"] == [gone["id"]]
    assert "RESOLVED" not in json.dumps(delta)


def test_delta_no_previous_snapshot_is_empty_not_a_conclusion():
    delta = compute_delta(None, [make_item()])
    assert delta["status"] == "EMPTY"
    assert delta["reasons"] == ["no_previous_snapshot"]
    assert delta["missing_from_current"] == []


def test_incompatible_scope_does_not_fabricate_missing_conclusion():
    previous = [make_item(external_ref="r1")]
    current = []
    delta = compute_delta(
        previous,
        current,
        previous_scope={"ticker": "AAPL"},
        current_scope={"ticker": "MSFT"},
    )
    assert delta["status"] == "NOT_COMPARABLE"
    assert delta["reasons"] == ["scope_mismatch"]
    assert delta["missing_count"] is None
    assert delta["missing_from_current"] == []
    assert delta["items"] == []


def test_incomplete_ingest_blocks_conclusions():
    previous = [make_item(external_ref="r1")]
    delta = compute_delta(previous, [], previous_ingest_complete=True, current_ingest_complete=False)
    assert delta["status"] == "NOT_COMPARABLE"
    assert delta["reasons"] == ["ingest_incomplete"]
    assert delta["missing_count"] is None
    assert delta["missing_from_current"] == []


def test_matching_scopes_and_complete_ingest_allow_comparison():
    keep = make_item(external_ref="r1")
    delta = compute_delta(
        [keep],
        [keep],
        previous_scope={"ticker": "AAPL"},
        current_scope={"ticker": "AAPL"},
        previous_ingest_complete=True,
        current_ingest_complete=True,
    )
    assert delta["status"] == "READY"
    assert delta["missing_from_current"] == []


# ------------------------------------------------------------- RESOLVED prohibition


def test_resolved_is_not_a_supported_state():
    assert "RESOLVED" not in DELTA_STATES
    assert DELTA_STATES == {"NEW", "CHANGED", "UNCHANGED"}

    previous = [make_item(external_ref="r1")]
    delta = compute_delta(previous, [])
    allowed = {"NEW", "CHANGED", "UNCHANGED"}
    assert all(row["state"] in allowed for row in delta["items"])
    assert "RESOLVED" not in json.dumps(delta)

    # State vocabulary never leaks a resolution alias in roll-up keys.
    assert not any(key.startswith("resolved") for key in delta)
