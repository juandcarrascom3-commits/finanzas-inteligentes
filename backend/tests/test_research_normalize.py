"""Pure tests for deterministic Research normalization (no DB, no network, no clock)."""

import hashlib

import pytest

from backend.analytics.research_normalize import (
    compute_content_hash,
    normalize_epistemic,
    normalize_external_ref,
    normalize_research_item,
    normalize_source_id,
    normalize_text_hash,
    normalize_timestamp,
    normalize_tickers,
    normalize_title_display,
    normalize_url,
    stable_research_id,
)


FETCHED = "2026-09-02T00:00:00+00:00"


def raw(**overrides):
    base = {
        "source_id": "sec",
        "title": "  Acme   reports  ",
        "url": "https://Example.com/News/?utm_source=x&page=2#top",
        "published_at": "2026-09-01T10:00:00Z",
        "entity_tickers": ["aapl"],
        "epistemic": "REPORTED",
    }
    base.update(overrides)
    return base


def item(**overrides):
    fetched = overrides.pop("fetched_at", FETCHED)
    return normalize_research_item(raw(**overrides), fetched_at=fetched)


# ------------------------------------------------------------- title


def test_title_nfc_normalization():
    composed = normalize_title_display("Cafe\u0301 Report")
    decomposed = "Caf\u00e9 Report"
    assert composed == decomposed


def test_title_whitespace_collapsed_and_stripped():
    assert normalize_title_display("  hello \t world \n end  ") == "hello world end"


def test_empty_title_is_invalid_input():
    with pytest.raises(ValueError):
        normalize_title_display("   ")
    with pytest.raises(ValueError):
        normalize_title_display(None)


def test_title_hash_is_stable_and_casefolded():
    assert normalize_text_hash("Cafe\u0301 Report") == normalize_text_hash("Café REPORT")
    assert normalize_text_hash("Same") == normalize_text_hash("same")


def test_item_title_not_truncated():
    long_title = "x" * 500
    built = item(title=long_title)
    assert built["title"] == long_title


# ------------------------------------------------------------- source_id


def test_source_id_strip_upper():
    assert normalize_source_id("  yahoo  ") == "YAHOO"
    assert normalize_source_id("rss-1.a_b") == "RSS-1.A_B"


def test_source_id_invalid_rejected():
    with pytest.raises(ValueError):
        normalize_source_id("bad id")
    with pytest.raises(ValueError):
        normalize_source_id("")
    with pytest.raises(ValueError):
        normalize_source_id(None)


# ------------------------------------------------------------- url


def test_url_normalization_full():
    url, status, reason = normalize_url("HTTPS://Example.COM:443/a/b/?utm_source=x&q=1#frag")
    assert status == "NORMALIZED"
    assert reason is None
    assert url == "https://example.com/a/b?q=1"


def test_url_tracking_params_removed():
    assert normalize_url("https://example.com/a?id=5&utm_medium=email&fbclid=xyz&gclid=123")[0] == \
        "https://example.com/a?id=5"


def test_url_unknown_params_preserved():
    url, status, _ = normalize_url("https://example.com/a?page=2&utm_campaign=c&keep=me")
    assert status == "NORMALIZED"
    assert "page=2" in url and "keep=me" in url
    assert "utm_campaign" not in url


def test_url_default_port_removed_non_default_kept():
    assert normalize_url("http://example.com:80/x")[0] == "http://example.com/x"
    assert normalize_url("https://example.com:8443/x")[0] == "https://example.com:8443/x"


def test_url_fragment_removed_and_root_slash_kept():
    assert normalize_url("https://example.com/page#section")[0] == "https://example.com/page"
    assert normalize_url("https://example.com/")[0] == "https://example.com/"
    assert normalize_url("https://example.com/dir/")[0] == "https://example.com/dir"


def test_url_unparseable_preserves_original_and_marks_unknown():
    url, status, reason = normalize_url("just some text")
    assert url == "just some text"
    assert status == "UNKNOWN"
    assert reason == "url_unparsed"


def test_url_unsupported_scheme_is_unknown_not_fabricated():
    url, status, reason = normalize_url("ftp://files.example.com/x")
    assert url == "ftp://files.example.com/x"
    assert (status, reason) == ("UNKNOWN", "url_unparsed")


def test_url_missing_is_none_without_error():
    assert normalize_url(None) == (None, "MISSING", None)
    assert normalize_url("") == (None, "MISSING", None)


def test_item_with_unparseable_url_is_unknown_and_not_identifiable():
    built = item(url="nope", external_ref=None)
    assert built["url"] == "nope"  # original preserved, not fabricated
    assert built["normalization_status"] == "UNKNOWN"
    assert "url_unparsed" in built["reasons"]
    assert built["external_ref"] is None
    assert built["id"] is None
    assert "external_ref_not_identifiable" in built["reasons"]


# ------------------------------------------------------------- external_ref


def test_external_ref_provided_is_preserved_not_derived():
    ref, derived, reason = normalize_external_ref("  ref-1 ", None)
    assert (ref, derived, reason) == ("ref-1", False, None)


def test_external_ref_derived_from_normalized_url():
    ref, derived, reason = normalize_external_ref(None, "https://example.com/x")
    expected = hashlib.sha256(b"https://example.com/x").hexdigest()[:16]
    assert ref == expected
    assert derived is True
    assert reason is None


def test_external_ref_not_fabricated_without_ref_or_url():
    ref, derived, reason = normalize_external_ref(None, None)
    assert (ref, derived, reason) == (None, False, "external_ref_not_identifiable")


def test_item_derives_external_ref_and_stable_id_from_url():
    built = item(url="https://example.com/story", external_ref=None)
    normalized_url = normalize_url("https://example.com/story")[0]
    assert built["external_ref"] == hashlib.sha256(normalized_url.encode()).hexdigest()[:16]
    assert built["external_ref_derived"] is True
    assert built["id"] == stable_research_id(built["source_id"], built["external_ref"])


# ------------------------------------------------------------- tickers


def test_ticker_valid_normalized():
    tickers, reasons = normalize_tickers([" aapl ", "BRK.B"])
    assert tickers == ["AAPL", "BRK.B"]
    assert reasons == []


def test_invalid_ticker_never_becomes_literal_unknown_entity():
    tickers, reasons = normalize_tickers(["bad ticker"])
    assert tickers == []
    assert "UNKNOWN" not in tickers
    assert reasons == ["ticker_unnormalized"]
    built = item(entity_tickers=["bad ticker"])
    assert built["entity_tickers"] == []
    assert "ticker_unnormalized" in built["reasons"]


def test_empty_ticker_list_is_unlinked_not_error():
    built = item(entity_tickers=[])
    assert built["entity_tickers"] == []
    assert "ticker_unnormalized" not in built.get("reasons", [])
    assert built["normalization_status"] == "READY"


# ------------------------------------------------------------- timestamps


def test_timestamp_iso_and_z_and_date_only():
    assert normalize_timestamp("2026-09-01T10:00:00") == ("2026-09-01T10:00:00+00:00", None)
    assert normalize_timestamp("2026-09-01T10:00:00Z") == ("2026-09-01T10:00:00+00:00", None)
    assert normalize_timestamp("2026-09-01") == ("2026-09-01T00:00:00+00:00", None)
    assert normalize_timestamp("2026-09-01T12:00:00+02:00") == ("2026-09-01T10:00:00+00:00", None)


def test_timestamp_unix_seconds_and_millis():
    from datetime import datetime, timezone

    epoch = 1788276000
    expected = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    assert normalize_timestamp(epoch) == (expected, None)
    assert normalize_timestamp(epoch * 1000) == (expected, None)
    assert normalize_timestamp(str(epoch)) == (expected, None)


def test_timestamp_invalid_returns_none_with_reason():
    assert normalize_timestamp("not-a-timestamp") == (None, "invalid_timestamp")
    assert normalize_timestamp("2026-13-45") == (None, "invalid_timestamp")
    assert normalize_timestamp(None) == (None, None)


def test_fetched_at_parameter_and_field_fallback():
    from_field = normalize_research_item(raw(fetched_at=FETCHED))
    assert from_field["fetched_at"] == FETCHED
    from_param = normalize_research_item(raw(), fetched_at=FETCHED)
    assert from_param["fetched_at"] == FETCHED
    with pytest.raises(ValueError):
        normalize_research_item(raw())  # no system-clock fallback exists
    invalid = normalize_research_item(raw(), fetched_at="garbage")
    assert invalid["fetched_at"] is None
    assert "invalid_timestamp" in invalid["reasons"]
    assert invalid["normalization_status"] == "PARTIAL"


def test_invalid_published_at_is_none_with_reason_but_not_fatal():
    built = item(published_at="not-a-date")
    assert built["published_at"] is None
    assert "invalid_timestamp" in built["reasons"]


# ------------------------------------------------------------- content_hash


def test_content_hash_deterministic():
    first = compute_content_hash(title_hash="acme", url="https://e.com/a", published_at="2026-09-01T00:00:00+00:00")
    second = compute_content_hash(published_at="2026-09-01T00:00:00+00:00", url="https://e.com/a", title_hash="acme")
    assert first == second
    assert len(first) == 64


def test_content_hash_changes_on_material_content():
    base = compute_content_hash(title_hash="acme", url="https://e.com/a")
    other = compute_content_hash(title_hash="acme corp", url="https://e.com/a")
    assert base != other


def test_fetched_at_change_does_not_alter_content_hash():
    a = item(fetched_at="2026-09-02T00:00:00Z")
    b = item(fetched_at="2026-09-21T12:00:00Z")
    assert a["content_hash"] == b["content_hash"]
    assert a["fetched_at"] != b["fetched_at"]


def test_source_id_change_does_not_alter_content_hash():
    a = item(source_id="sec-a", external_ref="r1")
    b = item(source_id="sec-b", external_ref="r1")
    assert a["content_hash"] == b["content_hash"]
    assert a["id"] != b["id"]


def test_never_uses_builtin_hash():
    built = item()
    assert built["content_hash"] != str(hash(built["title"]))
    assert len(built["content_hash"]) == 64


# ------------------------------------------------------------- stable id


def test_stable_id_deterministic_and_format():
    first = stable_research_id("SEC", "r1")
    assert first == stable_research_id("SEC", "r1")
    assert first.startswith("research:")
    assert len(first) == len("research:") + 12
    assert first != stable_research_id("SEC", "r2")
    assert first != stable_research_id("OTHER", "r1")


# ------------------------------------------------------------- epistemic


def test_missing_epistemic_defaults_to_unspecified_with_reason():
    assert normalize_epistemic(None) == ("UNSPECIFIED", "epistemic_unspecified")
    built = normalize_research_item(raw(epistemic=None), fetched_at=FETCHED)
    assert built["epistemic"] == "UNSPECIFIED"
    assert "epistemic_unspecified" in built["reasons"]


def test_invalid_epistemic_normalizes_not_rejected():
    assert normalize_epistemic("totally made up") == ("UNSPECIFIED", "epistemic_unspecified")
    built = normalize_research_item(raw(epistemic="sentiment: bullish"), fetched_at=FETCHED)
    assert built["epistemic"] == "UNSPECIFIED"
    assert "epistemic_unspecified" in built["reasons"]


def test_valid_epistemic_preserved():
    assert normalize_epistemic("fact") == ("FACT", None)
    assert normalize_epistemic("  reported ") == ("REPORTED", None)
    assert normalize_epistemic("analysis") == ("ANALYSIS", None)


# ------------------------------------------------------------- item contract


def test_item_contract_fields_present():
    built = item()
    for field in (
        "id", "source_id", "external_ref", "title", "url", "published_at",
        "fetched_at", "content_hash", "epistemic", "entity_tickers",
        "normalization_status",
    ):
        assert field in built
    assert set(built["provenance"]) >= {
        "source_id", "external_ref", "url", "published_at", "fetched_at", "content_hash",
    }
    assert built["normalization_status"] == "READY"


def test_no_secret_bearing_fields_written():
    built = item(provider="RSS", ingestion_method="import")
    blob = str(built)
    for forbidden in ("token", "cookie", "authorization", "api_key", "password"):
        assert forbidden not in blob.lower()
