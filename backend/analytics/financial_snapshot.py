"""Financial Snapshot composition and JSON report foundation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional


SCHEMA_VERSION = "financial_snapshot.v1"


def section_envelope(
    *,
    source: str,
    data: Any = None,
    status: str = "READY",
    reasons: Optional[list[str]] = None,
    as_of: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "reasons": reasons or [],
        "source": source,
        "data": deepcopy(data),
        "as_of": as_of,
        "provenance": provenance or {"owner": source},
    }


def unavailable_section(source: str, reason: str = "NO_CLEAN_CANONICAL_OWNER") -> Dict[str, Any]:
    return section_envelope(source=source, data=None, status="UNAVAILABLE", reasons=[reason], provenance={"owner": source})


def compose_financial_snapshot(
    *,
    as_of: str,
    scope: Dict[str, Any],
    sections: Dict[str, Dict[str, Any]],
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    copied_sections = deepcopy(sections)
    reasons = []
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
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of,
        "generated_at": generated_at or datetime.now().isoformat(),
        "scope": deepcopy(scope),
        "status": status,
        "reasons": reasons,
        "sections": copied_sections,
        "provenance": {
            "composition": "FinancialSnapshot",
            "policy": "Outer envelope normalized; canonical section payloads preserved.",
        },
    }


def stable_snapshot_content(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    content = deepcopy(snapshot)
    content.pop("generated_at", None)
    return content


def build_financial_summary_report(snapshot: Dict[str, Any], generated_at: Optional[str] = None) -> Dict[str, Any]:
    sections = snapshot.get("sections", {})
    rows = []

    def add(section_key: str, title: str):
        section = sections.get(section_key)
        if not section or section.get("status") in {"UNAVAILABLE", "DEFERRED"}:
            return
        rows.append({
            "section": section_key,
            "title": title,
            "status": section.get("status"),
            "reasons": section.get("reasons", []),
            "source": section.get("source"),
            "data": deepcopy(section.get("data")),
        })

    for key, title in [
        ("cash_flow", "Cash Flow"),
        ("changes", "What Changed"),
        ("budgets", "Budgets"),
        ("recurring", "Recurring"),
        ("inbox", "Upcoming / Inbox"),
        ("timeline", "Timeline"),
        ("wealth", "Wealth"),
        ("portfolio", "Portfolio"),
        ("xray", "Portfolio X-Ray"),
        ("confidence", "Data Confidence"),
        ("monthly_review", "Monthly Review"),
    ]:
        add(key, title)

    limitations = [
        {"section": key, "status": value.get("status"), "reasons": value.get("reasons", [])}
        for key, value in sections.items()
        if value.get("status") in {"PARTIAL", "UNAVAILABLE", "DEFERRED", "UNEVALUABLE"}
    ]
    return {
        "schema_version": "financial_summary_report.v1",
        "generated_at": generated_at or datetime.now().isoformat(),
        "snapshot_schema_version": snapshot.get("schema_version"),
        "as_of": snapshot.get("as_of"),
        "scope": deepcopy(snapshot.get("scope", {})),
        "status": snapshot.get("status"),
        "sections": rows,
        "data_limitations": limitations,
        "source": "FinancialSnapshot",
    }
