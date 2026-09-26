"""Pure tests for ResearchSnapshot composition, freshness, coverage and roll-up parity."""

import json
from copy import deepcopy

from backend.analytics.financial_snapshot import (
    compose_financial_snapshot,
    section_envelope,
    stable_snapshot_content,
    unavailable_section,
)
from backend.analytics.research_normalize import normalize_research_item
from backend.analytics.research_snapshot import (
    build_research_snapshot,
    compose_research_snapshot,
    compute_freshness,
)


FETCHED = "2026-09-20T00:00:00+00:00"
AS_OF = "2026-09-25"
REFERENCE = "2026-09-25T00:00:00+00:00"


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


# ------------------------------------------------------------- composition


def test_deterministic_composition_stable_content_ignores_generated_at():
    items = [make_item()]
    first = build_research_snapshot(items, as_of=AS_OF, generated_at="one")
    second = build_research_snapshot(items, as_of=AS_OF, generated_at="two")
    assert first["generated_at"] == "one"
    assert second["generated_at"] == "two"
    assert stable_snapshot_content(first) == stable_snapshot_content(second)


def test_composition_does_not_mutate_inputs():
    items = [make_item()]
    before = deepcopy(items)
    build_research_snapshot(items, as_of=AS_OF, generated_at="x")
    assert items == before


def test_snapshot_top_level_contract():
    snapshot = build_research_snapshot([make_item()], as_of=AS_OF, scope={"ticker": "AAPL"}, generated_at="g")
    assert snapshot["schema_version"] == "research_snapshot.v1"
    assert set(snapshot) == {
        "schema_version", "as_of", "generated_at", "scope", "status", "reasons", "sections", "provenance",
    }
    assert snapshot["as_of"] == AS_OF
    assert snapshot["scope"] == {"ticker": "AAPL"}
    assert set(snapshot["sections"]) == {"items", "entities", "freshness", "delta", "coverage"}
    assert snapshot["provenance"]["composition"] == "ResearchSnapshot"


# ------------------------------------------------------------- roll-up


def test_roll_up_ready():
    snapshot = build_research_snapshot([make_item()], as_of=AS_OF, previous_items=[], generated_at="g")
    assert snapshot["status"] == "READY"
    assert snapshot["reasons"] == []


def test_roll_up_partial_when_section_partial():
    sections = {
        "a": section_envelope(source="a", status="READY"),
        "b": section_envelope(source="b", status="PARTIAL", reasons=["broken"]),
    }
    snapshot = compose_research_snapshot(as_of=AS_OF, scope={}, sections=sections, generated_at="g")
    assert snapshot["status"] == "PARTIAL"
    assert snapshot["reasons"] == ["b:PARTIAL"]


def test_roll_up_empty_when_all_sections_unavailable():
    sections = {"a": unavailable_section("a"), "b": unavailable_section("b")}
    snapshot = compose_research_snapshot(as_of=AS_OF, scope={}, sections=sections, generated_at="g")
    assert snapshot["status"] == "EMPTY"


def test_roll_up_unevaluable_without_sections():
    snapshot = compose_research_snapshot(as_of=AS_OF, scope={}, sections={}, generated_at="g")
    assert snapshot["status"] == "UNEVALUABLE"


def test_roll_up_parity_with_financial_snapshot():
    sections = {
        "a": section_envelope(source="a", status="READY"),
        "b": section_envelope(source="b", status="PARTIAL", reasons=["x"]),
        "c": unavailable_section("c"),
    }
    research = compose_research_snapshot(as_of=AS_OF, scope={}, sections=sections, generated_at="g")
    financial = compose_financial_snapshot(as_of=AS_OF, scope={}, sections=sections, generated_at="g")
    assert research["status"] == financial["status"] == "PARTIAL"
    assert research["reasons"] == financial["reasons"]


# ------------------------------------------------------------- freshness


def _freshness(published_at, fetched_at="2026-01-01T00:00:00+00:00", **kwargs):
    return compute_freshness(
        {"published_at": published_at, "fetched_at": fetched_at}, REFERENCE, **kwargs
    )


def test_freshness_fresh_at_fresh_days_boundary():
    result = _freshness("2026-09-18T00:00:00+00:00")  # exactly 7 days
    assert result["status"] == "FRESH"
    assert result["age_days"] == 7
    assert result["basis"] == "published_at"
    assert result["thresholds"] == {"fresh_days": 7, "stale_days": 30}


def test_freshness_aging_at_fresh_days_plus_one():
    result = _freshness("2026-09-17T00:00:00+00:00")  # 8 days
    assert result["status"] == "AGING"
    assert result["age_days"] == 8


def test_freshness_aging_at_stale_boundary_and_stale_beyond():
    assert _freshness("2026-08-26T00:00:00+00:00")["status"] == "AGING"  # exactly 30
    stale = _freshness("2026-08-25T00:00:00+00:00")  # 31
    assert stale["status"] == "STALE"
    assert stale["age_days"] == 31


def test_freshness_unknown_without_valid_dates():
    result = _freshness(None, fetched_at=None)
    assert result["status"] == "UNKNOWN"
    assert result["basis"] is None
    assert result["age_days"] is None


def test_freshness_prefers_published_at_over_fetched_at():
    result = _freshness("2026-09-24T00:00:00+00:00", fetched_at="2026-01-01T00:00:00+00:00")
    assert result["basis"] == "published_at"
    assert result["status"] == "FRESH"


def test_freshness_falls_back_to_fetched_at():
    result = _freshness(None, fetched_at="2026-09-24T00:00:00+00:00")
    assert result["basis"] == "fetched_at"
    assert result["status"] == "FRESH"


def test_freshness_thresholds_are_explicit_arguments():
    result = _freshness("2026-09-17T00:00:00+00:00", fresh_days=1, stale_days=5)
    assert result["status"] == "STALE"
    assert result["thresholds"] == {"fresh_days": 1, "stale_days": 5}


def test_freshness_invalid_reference_is_unknown_not_a_clock():
    result = compute_freshness({"published_at": "2026-09-18T00:00:00+00:00"}, "not-a-time")
    assert result["status"] == "UNKNOWN"


def test_snapshot_freshness_section_exposes_status_basis_age_thresholds():
    snapshot = build_research_snapshot(
        [make_item()], as_of=AS_OF, reference=REFERENCE, previous_items=[], generated_at="g"
    )
    rows = snapshot["sections"]["freshness"]["data"]["rows"]
    assert set(rows[0]) == {"id", "source_id", "status", "basis", "age_days", "thresholds"}
    assert snapshot["sections"]["freshness"]["data"]["reference"] == REFERENCE
    assert snapshot["sections"]["freshness"]["data"]["thresholds"] == {"fresh_days": 7, "stale_days": 30}


def test_snapshot_freshness_unknown_makes_section_and_snapshot_partial():
    item = normalize_research_item(
        {
            "source_id": "SRC",
            "external_ref": "r1",
            "title": "No dates story",
            "url": "https://example.com/nd",
            "epistemic": "REPORTED",
            "entity_tickers": [],
        },
        fetched_at="garbage",
    )
    assert item["published_at"] is None and item["fetched_at"] is None
    snapshot = build_research_snapshot([item], as_of=AS_OF, generated_at="g")
    assert snapshot["sections"]["freshness"]["status"] == "PARTIAL"
    assert "freshness_unknown:1" in snapshot["sections"]["freshness"]["reasons"]
    assert snapshot["status"] == "PARTIAL"
    assert "freshness:PARTIAL" in snapshot["reasons"]


# ------------------------------------------------------------- sections


def test_missing_provenance_leads_to_truthful_partial_with_reason():
    item = normalize_research_item(
        {"source_id": "SRC", "external_ref": "r9", "title": "Weak provenance",
         "url": "https://example.com/weak", "epistemic": "REPORTED", "entity_tickers": []},
        fetched_at="garbage",
    )
    assert "invalid_timestamp" in item["reasons"]
    snapshot = build_research_snapshot([item], as_of=AS_OF, generated_at="g")
    assert snapshot["status"] == "PARTIAL"
    assert snapshot["reasons"]
    # provenance keys remain present even when values are None
    assert set(item["provenance"]) >= {"source_id", "external_ref", "published_at", "fetched_at", "content_hash"}


def test_unparseable_url_makes_items_section_partial():
    item = normalize_research_item(
        {"source_id": "SRC", "title": "Broken link", "url": "not a url",
         "epistemic": "REPORTED", "entity_tickers": ["AAPL"]},
        fetched_at=FETCHED,
    )
    snapshot = build_research_snapshot([item], as_of=AS_OF, generated_at="g")
    assert snapshot["sections"]["items"]["status"] == "PARTIAL"
    assert "normalization_unknown:1" in snapshot["sections"]["items"]["reasons"]
    assert snapshot["status"] == "PARTIAL"


def test_entities_section_reports_linked_and_unlinked():
    linked = make_item(external_ref="r1", entity_tickers=["AAPL", "MSFT"])
    unlinked = make_item(external_ref="r2", entity_tickers=[])
    snapshot = build_research_snapshot([linked, unlinked], as_of=AS_OF, previous_items=[], generated_at="g")
    data = snapshot["sections"]["entities"]["data"]
    assert data["distinct_entities"] == 2
    assert data["unlinked_items"] == 1
    counts = {row["ticker"]: row["item_count"] for row in data["entities"]}
    assert counts == {"AAPL": 1, "MSFT": 1}


def test_duplicate_rows_surfaced_in_items_section():
    snapshot = build_research_snapshot(
        [make_item(), make_item()], as_of=AS_OF, previous_items=[], generated_at="g"
    )
    assert len(snapshot["sections"]["items"]["data"]) == 1
    assert "duplicate_rows:1" in snapshot["sections"]["items"]["reasons"]


def test_in_batch_conflict_makes_items_section_partial():
    snapshot = build_research_snapshot(
        [make_item(title="One"), make_item(title="Two other")],
        as_of=AS_OF,
        generated_at="g",
    )
    assert snapshot["sections"]["items"]["status"] == "PARTIAL"
    assert "in_batch_conflict:1" in snapshot["sections"]["items"]["reasons"]


def test_delta_section_unavailable_without_previous_snapshot():
    snapshot = build_research_snapshot([make_item()], as_of=AS_OF, generated_at="g")
    assert snapshot["sections"]["delta"]["status"] == "UNAVAILABLE"
    assert snapshot["sections"]["delta"]["reasons"] == ["no_previous_snapshot"]
    assert snapshot["status"] == "PARTIAL"
    assert "delta:UNAVAILABLE" in snapshot["reasons"]


def test_delta_section_ready_with_previous_snapshot():
    previous = [make_item(external_ref="r1"), make_item(external_ref="r2")]
    snapshot = build_research_snapshot(
        [make_item(external_ref="r1")], as_of=AS_OF, previous_items=previous, generated_at="g"
    )
    assert snapshot["sections"]["delta"]["status"] == "READY"
    assert snapshot["sections"]["delta"]["data"]["missing_count"] == 1


def test_incompatible_scope_makes_delta_section_partial_not_a_conclusion():
    previous = [make_item(external_ref="r1")]
    snapshot = build_research_snapshot(
        [],
        as_of=AS_OF,
        previous_items=previous,
        previous_scope={"ticker": "AAPL"},
        current_scope={"ticker": "MSFT"},
        generated_at="g",
    )
    delta = snapshot["sections"]["delta"]
    assert delta["status"] == "PARTIAL"
    assert delta["reasons"] == ["scope_mismatch"]
    assert delta["data"]["missing_from_current"] == []
    assert delta["data"]["missing_count"] is None


# ------------------------------------------------------------- coverage


def test_coverage_is_factual_counts_only():
    linked = make_item(external_ref="r1")
    unlinked = make_item(external_ref="r2", entity_tickers=[])
    snapshot = build_research_snapshot(
        [linked, unlinked], as_of=AS_OF, reference=REFERENCE, previous_items=[], generated_at="g"
    )
    coverage = snapshot["sections"]["coverage"]["data"]
    assert coverage["total_items"] == 2
    assert coverage["entity_linked_items"] == 1
    assert coverage["unlinked_items"] == 1
    assert coverage["distinct_entities"] == 1
    assert coverage["freshness_counts"]["AGING"] == 2  # published 2026-09-01 vs 2026-09-25
    blob = json.dumps(coverage).lower()
    for forbidden in ("score", "rank", "recommend", "confidence"):
        assert forbidden not in blob


def test_cross_source_signal_present_in_coverage_without_merging():
    a = make_item(source_id="SRC_A", external_ref="a1")
    b = make_item(source_id="SRC_B", external_ref="b1")
    snapshot = build_research_snapshot([a, b], as_of=AS_OF, previous_items=[], generated_at="g")
    coverage = snapshot["sections"]["coverage"]
    assert coverage["data"]["possible_cross_source_duplicate_signals"] == 1
    assert coverage["data"]["cross_source_duplicate_signals"][0]["source_ids"] == ["SRC_A", "SRC_B"]
    assert "cross_source_signals:1" in coverage["reasons"]
    assert len(snapshot["sections"]["items"]["data"]) == 2  # never merged


# ------------------------------------------------------------- honesty guards


def test_negative_urgent_text_does_not_determine_snapshot_status():
    alarming = make_item(
        title="URGENT: ACME COLLAPSE IMMINENT, SELL EVERYTHING",
        external_ref="r1",
    )
    snapshot = build_research_snapshot([alarming], as_of=AS_OF, previous_items=[], generated_at="g")
    assert snapshot["status"] == "READY"
    assert snapshot["reasons"] == []


def test_snapshot_contains_no_resolved_state():
    previous = [make_item(external_ref="r1")]
    snapshot = build_research_snapshot([make_item(external_ref="r1")], as_of=AS_OF, previous_items=previous, generated_at="g")
    assert "RESOLVED" not in json.dumps(snapshot)


def test_snapshot_contains_no_ai_or_market_authority_tokens():
    snapshot = build_research_snapshot([make_item()], as_of=AS_OF, previous_items=[], generated_at="g")
    blob = json.dumps(snapshot).lower()
    for forbidden in ("sentiment", "gemini", "openai", "embedding", "recommendation", "price_authority"):
        assert forbidden not in blob
