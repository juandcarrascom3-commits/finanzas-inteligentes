from copy import deepcopy

from backend.analytics.financial_snapshot import build_financial_summary_report, compose_financial_snapshot, section_envelope, stable_snapshot_content, unavailable_section


def test_snapshot_preserves_canonical_payloads_and_known_metrics_exactly():
    cash = {"facts": {"cashflow": -123.45}, "by_currency": {"USD": {"cashflow": -123.45}, "COP": {"cashflow": 1000}}}
    wealth = {"summary": {"total_value_usd": 999.99}, "performance": {"twr": {"status": "AVAILABLE", "value_pct": 1.23}}}
    snapshot = compose_financial_snapshot(
        as_of="2026-09-22",
        scope={"currency": None, "period": "current_month"},
        sections={
            "cash_flow": section_envelope(source="understand", data=cash),
            "wealth": section_envelope(source="wealth", data=wealth),
        },
        generated_at="one",
    )
    assert snapshot["sections"]["cash_flow"]["data"] == cash
    assert snapshot["sections"]["wealth"]["data"]["summary"]["total_value_usd"] == 999.99
    assert snapshot["status"] == "READY"


def test_missing_owner_and_partial_sections_make_truthful_partial_snapshot():
    partial_xray = {"status": "PARTIAL", "coverage": 0.4, "provenance": {"fund_compositions": "cache"}}
    snapshot = compose_financial_snapshot(
        as_of="2026-09-22",
        scope={},
        sections={
            "xray": section_envelope(source="portfolio_xray", data=partial_xray, status="PARTIAL", reasons=["missing_fund_composition"], provenance=partial_xray["provenance"]),
            "goals": unavailable_section("goal_summary", "DEFERRED_NO_CLEAN_CANONICAL_SUMMARY_OWNER"),
        },
        generated_at="one",
    )
    assert snapshot["status"] == "PARTIAL"
    assert snapshot["sections"]["xray"]["data"] == partial_xray
    assert snapshot["sections"]["goals"]["status"] == "UNAVAILABLE"


def test_negative_or_urgent_financial_facts_do_not_drive_snapshot_status():
    inbox = {"status": "READY", "summary": {"urgent_count": 1}, "attention_items": [{"type": "PROJECTED_CASH_SHORTFALL"}]}
    snapshot = compose_financial_snapshot(
        as_of="2026-09-22",
        scope={},
        sections={
            "cash_flow": section_envelope(source="understand", data={"cashflow": -999}),
            "inbox": section_envelope(source="financial_inbox", data=inbox, status=inbox["status"]),
        },
        generated_at="one",
    )
    assert snapshot["status"] == "READY"


def test_generated_at_does_not_affect_financial_content_and_no_mutation():
    sections = {"cash_flow": section_envelope(source="understand", data={"cashflow": 1})}
    before = deepcopy(sections)
    first = compose_financial_snapshot(as_of="2026-09-22", scope={}, sections=sections, generated_at="one")
    second = compose_financial_snapshot(as_of="2026-09-22", scope={}, sections=sections, generated_at="two")
    assert stable_snapshot_content(first) == stable_snapshot_content(second)
    assert sections == before


def test_report_consumes_snapshot_only_and_serializes_available_sections():
    snapshot = compose_financial_snapshot(
        as_of="2026-09-22",
        scope={"period": "current_month"},
        sections={
            "cash_flow": section_envelope(source="understand", data={"cashflow": 1}),
            "goals": unavailable_section("goal_summary", "DEFERRED"),
        },
        generated_at="one",
    )
    report = build_financial_summary_report(snapshot, generated_at="report")
    assert report["source"] == "FinancialSnapshot"
    assert [row["section"] for row in report["sections"]] == ["cash_flow"]
    assert report["data_limitations"][0]["section"] == "goals"
