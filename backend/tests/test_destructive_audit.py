"""S2B mutation audit: structured action_events for destructive and high-risk mutations.

Every test runs against the T0 temporary database and cleans up any entity it
creates, so no audited row is left behind for other suites.
"""

import json
import os
import tempfile

from fastapi.testclient import TestClient

from backend.app import app, db
from database.db_manager import DEFAULT_DB_FILE

client = TestClient(app)
lenient_client = TestClient(app, raise_server_exceptions=False)

AUDITED_EVENT_TYPES = {
    "BACKUP_RESTORE_SUCCESS",
    "BACKUP_RESTORE_FAILED",
    "ACCOUNT_DELETE",
    "ASSET_DELETE",
    "TRANSACTION_DELETE",
    "INVESTMENT_OPERATION_DELETE",
    "BUDGET_DELETE",
    "MAPPING_CONFIG_IMPORT_SUCCESS",
    "MAPPING_CONFIG_IMPORT_FAILED",
    "IMPORT_PLAN_SUCCESS",
    "IMPORT_PLAN_FAILED",
}

FORBIDDEN_PAYLOAD_TOKENS = ("token", "secret", "password", "api_key", "apikey", "authorization", "cookie", "raw", "content")


def _all_events():
    return db.get_action_events(limit=1000)


def _events_of(event_type):
    return [event for event in _all_events() if event["event_type"] == event_type]


def _snapshot_ids(event_type=None):
    events = _all_events() if event_type is None else _events_of(event_type)
    return {event["id"] for event in events}


def _new_events(before_ids, event_type=None):
    events = _all_events() if event_type is None else _events_of(event_type)
    return [event for event in events if event["id"] not in before_ids]


def _new_audited(before_ids):
    return [event for event in _new_events(before_ids) if event["event_type"] in AUDITED_EVENT_TYPES]


def _payload(event):
    return json.loads(event["payload"] or "{}")


def _row_count(table):
    conn = db.get_connection()
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _cleanup_sql(*statements):
    conn = db.get_connection()
    try:
        for statement, params in statements:
            conn.execute(statement, params)
        conn.commit()
    finally:
        conn.close()


# --- isolation proof (required before any mutating test) --------------------


def test_audit_suite_uses_isolated_temp_database():
    effective = os.path.abspath(db.db_path)
    configured = os.path.abspath(os.environ["FINANCE_DB_PATH"])
    temp_root = os.path.abspath(tempfile.gettempdir())

    assert effective == configured
    assert os.path.commonpath([effective, temp_root]) == temp_root
    assert effective != os.path.abspath(DEFAULT_DB_FILE)


# --- A. restore audit -------------------------------------------------------


def test_successful_restore_records_exactly_one_audit_event():
    backup = db.export_backup()
    before = _snapshot_ids()

    response = client.post("/api/backup/restore", json={"path": backup["db_backup_path"]})

    assert response.status_code == 200
    assert response.json()["status"] == "RESTORED"

    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    event = new_audited[0]
    assert event["event_type"] == "BACKUP_RESTORE_SUCCESS"
    assert event["severity"] == "INFO"
    payload = _payload(event)
    assert payload["backup_file"] == os.path.basename(backup["db_backup_path"])
    assert payload["schema_version"] is not None


def test_rejected_restore_path_records_no_audit_event():
    outside = os.path.join(tempfile.gettempdir(), "finance-audit-escape", "finance-backup-19990101-000000.db")
    before = _snapshot_ids()

    response = client.post("/api/backup/restore", json={"path": outside})

    assert response.status_code == 400
    assert _new_audited(before) == []


def test_failed_restore_with_rollback_records_failure_event(monkeypatch):
    backup = db.export_backup()
    before = _snapshot_ids()

    def fail_verification():
        raise ValueError("simulated post-restore validation failure")

    monkeypatch.setattr(db, "_verify_restored_database", fail_verification)
    response = lenient_client.post("/api/backup/restore", json={"path": backup["db_backup_path"]})

    assert response.status_code == 400
    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    event = new_audited[0]
    assert event["event_type"] == "BACKUP_RESTORE_FAILED"
    assert event["severity"] == "ERROR"
    payload = _payload(event)
    assert payload["backup_file"] == os.path.basename(backup["db_backup_path"])
    assert payload["recovered"] is True

    conn = db.get_connection()
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


# --- B-F. delete audits -----------------------------------------------------


def test_account_delete_records_audit_event_and_absent_row_is_honest():
    account = client.post("/api/accounts", json={"name": "Audit Account"}).json()
    before = _snapshot_ids("ACCOUNT_DELETE")

    response = client.delete(f"/api/accounts/{account['id']}")

    assert response.status_code == 200
    assert response.json() == {"status": "SUCCESS"}
    created = _new_events(before, "ACCOUNT_DELETE")
    assert len(created) == 1
    assert created[0]["source"] == "MANUAL"
    assert created[0]["severity"] == "INFO"
    assert _payload(created[0]) == {"entity_id": account["id"], "deleted": True}

    # A request for a row that never existed keeps the API contract but must not
    # claim a deletion happened.
    before_missing = _snapshot_ids("ACCOUNT_DELETE")
    missing = client.delete("/api/accounts/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 200
    created_missing = _new_events(before_missing, "ACCOUNT_DELETE")
    assert len(created_missing) == 1
    assert _payload(created_missing[0])["deleted"] is False


def test_asset_delete_records_audit_event():
    asset = client.post("/api/assets", json={"ticker": "AUDITTEST", "name": "Audit Asset"}).json()
    before = _snapshot_ids()

    response = client.delete(f"/api/assets/{asset['ticker']}")

    assert response.status_code == 200
    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    assert new_audited[0]["event_type"] == "ASSET_DELETE"
    assert _payload(new_audited[0]) == {"entity_id": "AUDITTEST", "deleted": True}


def test_transaction_delete_records_audit_event():
    account = client.post("/api/accounts", json={"name": "Audit Tx Account"}).json()
    tx = client.post(
        "/api/transactions",
        json={
            "account_id": account["id"],
            "amount": -10.5,
            "category": "General",
            "date": "2026-09-22",
            "description": "Audit transaction",
        },
    ).json()
    before = _snapshot_ids()

    response = client.delete(f"/api/transactions/{tx['id']}")

    assert response.status_code == 200
    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    assert new_audited[0]["event_type"] == "TRANSACTION_DELETE"
    assert _payload(new_audited[0]) == {"entity_id": tx["id"], "deleted": True}

    client.delete(f"/api/accounts/{account['id']}")


def test_investment_operation_delete_records_audit_event():
    operation = client.post(
        "/api/investment-ledger",
        json={
            "occurred_at": "2026-09-20",
            "ticker": "AUDITTEST",
            "operation_type": "BUY",
            "quantity": 1,
            "price": 10,
            "amount": 10,
        },
    ).json()
    before = _snapshot_ids()

    response = client.delete(f"/api/investment-ledger/{operation['id']}")

    assert response.status_code == 200
    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    assert new_audited[0]["event_type"] == "INVESTMENT_OPERATION_DELETE"
    assert _payload(new_audited[0]) == {"entity_id": operation["id"], "deleted": True}


def test_budget_delete_records_audit_event():
    budget = client.post(
        "/api/budgets",
        json={"category": "Audit Budget", "monthly_limit": 100, "currency": "USD"},
    ).json()
    before = _snapshot_ids()

    response = client.delete(f"/api/budgets/{budget['id']}")

    assert response.status_code == 200
    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    assert new_audited[0]["event_type"] == "BUDGET_DELETE"
    assert _payload(new_audited[0]) == {"entity_id": budget["id"], "deleted": True}


# --- G. mapping-config import audit -----------------------------------------


def test_mapping_config_import_records_single_audit_event():
    config = {
        "etoro_instrument_mappings": [
            {"external_id": "AUDIT-1", "external_name": "Audit Instrument", "local_id": "AUDITTEST", "local_type": "ticker", "is_active": True}
        ],
        "market_symbol_mappings": [
            {"internal_symbol": "AUDITTEST", "provider": "YFINANCE", "provider_symbol": "AUDITTEST", "instrument_type": "EQUITY"}
        ],
        "price_authority": [{"ticker": "AUDITTEST", "authority_mode": "AUTO"}],
    }
    before = _snapshot_ids()

    try:
        response = client.post("/api/mapping-config/import", json={"config": config})

        assert response.status_code == 200
        assert response.json() == {
            "status": "IMPORTED",
            "imported": {"etoro_instrument_mappings": 1, "market_symbol_mappings": 1, "price_authority": 1},
        }
        new_audited = _new_audited(before)
        assert len(new_audited) == 1
        assert new_audited[0]["event_type"] == "MAPPING_CONFIG_IMPORT_SUCCESS"
        assert _payload(new_audited[0])["imported"] == {
            "etoro_instrument_mappings": 1,
            "market_symbol_mappings": 1,
            "price_authority": 1,
        }
    finally:
        _cleanup_sql(
            ("DELETE FROM source_mappings WHERE external_id = ?", ("AUDIT-1",)),
            ("DELETE FROM market_symbol_mappings WHERE internal_symbol = ?", ("AUDITTEST",)),
            ("DELETE FROM price_authority WHERE ticker = ?", ("AUDITTEST",)),
        )


def test_rejected_mapping_config_import_records_failure_not_success():
    before = _snapshot_ids()

    response = client.post("/api/mapping-config/import", json={"config": {}})

    assert response.status_code == 400
    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    assert new_audited[0]["event_type"] == "MAPPING_CONFIG_IMPORT_FAILED"
    assert "errors" in _payload(new_audited[0])


def test_failed_mapping_config_import_rolls_back_and_records_only_failure():
    # Valid top-level config, malformed item: fails mid-transaction.
    config = {"etoro_instrument_mappings": [{"external_name": "Missing external id"}], "market_symbol_mappings": [], "price_authority": []}
    before = _snapshot_ids()
    conn = db.get_connection()
    try:
        etoro_before = conn.execute("SELECT COUNT(*) FROM source_mappings WHERE source = 'ETORO'").fetchone()[0]
    finally:
        conn.close()

    response = lenient_client.post("/api/mapping-config/import", json={"config": config})

    assert response.status_code == 500
    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    assert new_audited[0]["event_type"] == "MAPPING_CONFIG_IMPORT_FAILED"
    assert _payload(new_audited[0])["error_type"] == "KeyError"

    conn = db.get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM source_mappings WHERE source = 'ETORO'").fetchone()[0] == etoro_before
    finally:
        conn.close()


# --- H. BudgetBakers import-plan audit --------------------------------------


def test_import_plan_records_single_audit_event():
    before = _snapshot_ids()

    try:
        response = client.post(
            "/api/budgetbakers/import-plan",
            json={
                "budgets": [{"category": "Audit Plan Budget", "monthly_limit": 50, "currency": "USD", "external_id": "audit-plan-b-1"}],
                "standing_orders": [
                    {
                        "merchant": "Audit Plan Rent",
                        "typical_amount": -100,
                        "category": "Vivienda",
                        "frequency": "monthly",
                        "external_id": "audit-plan-so-1",
                        "next_expected": "2026-10-01",
                    }
                ],
            },
        )

        assert response.status_code == 200
        assert response.json() == {"imported_budgets": 1, "imported_standing_orders": 1}
        new_audited = _new_audited(before)
        assert len(new_audited) == 1
        event = new_audited[0]
        assert event["event_type"] == "IMPORT_PLAN_SUCCESS"
        assert event["source"] == "BUDGETBAKERS"
        assert _payload(event) == {"imported_budgets": 1, "imported_standing_orders": 1}
    finally:
        _cleanup_sql(
            ("DELETE FROM budgets WHERE external_id = ?", ("audit-plan-b-1",)),
            ("DELETE FROM recurring_rules WHERE external_id = ?", ("audit-plan-so-1",)),
        )


def test_failed_import_plan_records_failure_not_success(monkeypatch):
    before = _snapshot_ids()
    budgets_before = _row_count("budgets")

    # Malformed client structure no longer reaches the db (typed 422, zero
    # events); the S2B contract still governs genuine persistence failures,
    # forced deterministically here at the first write.
    def boom(conn, budget, preserve_manual=False):
        raise RuntimeError("simulated plan persistence failure")

    monkeypatch.setattr(db, "_upsert_budget", boom)
    response = lenient_client.post(
        "/api/budgetbakers/import-plan",
        json={"budgets": [{"category": "Audit Fail Budget", "monthly_limit": 1, "currency": "USD"}], "standing_orders": []},
    )

    assert response.status_code == 500
    assert _row_count("budgets") == budgets_before
    new_audited = _new_audited(before)
    assert len(new_audited) == 1
    event = new_audited[0]
    assert event["event_type"] == "IMPORT_PLAN_FAILED"
    assert event["severity"] == "ERROR"
    assert _payload(event)["imported_budgets"] == 0
    assert _payload(event)["error_type"] == "RuntimeError"


# --- metadata minimization and untouched subsystems -------------------------


def test_audit_metadata_contains_no_secrets_or_raw_payloads():
    seen = 0
    for event in _all_events():
        if event["event_type"] not in AUDITED_EVENT_TYPES:
            continue
        seen += 1
        serialized = json.dumps(_payload(event), ensure_ascii=False).lower() + (event["message"] or "").lower()
        for token in FORBIDDEN_PAYLOAD_TOKENS:
            assert token not in serialized, f"{event['event_type']} leaks {token!r}"
    assert seen > 0, "expected audited events from the earlier tests in this module"


def test_audited_mutations_do_not_touch_reconciliation_audit_events():
    before = _row_count("reconciliation_audit_events")

    account = client.post("/api/accounts", json={"name": "Audit Recon Account"}).json()
    client.delete(f"/api/accounts/{account['id']}")

    assert _row_count("reconciliation_audit_events") == before


def test_audited_mutations_do_not_touch_source_sync_state():
    before = _row_count("source_sync_state")

    budget = client.post(
        "/api/budgets",
        json={"category": "Audit Sync Budget", "monthly_limit": 10, "currency": "USD"},
    ).json()
    client.delete(f"/api/budgets/{budget['id']}")

    assert _row_count("source_sync_state") == before


# --- audit source vocabulary (S2 closeout) ---------------------------------


def test_add_action_event_preserves_research_source_and_sanitizes_unknown():
    """VALID_SOURCES is the audit vocabulary.

    RESEARCH is a known domain source (Research R1C dependency resolved by
    this S2 closeout), while genuinely unknown/invalid sources keep the
    existing sanitation to MANUAL.
    """
    db.add_action_event(
        "RESEARCH",
        "AUDIT_SOURCE_CHECK",
        "Vocabulario de auditoría: fuente RESEARCH.",
        "INFO",
        {"check": "research"},
    )
    db.add_action_event(
        "definitely_not_a_source",
        "AUDIT_SOURCE_CHECK",
        "Vocabulario de auditoría: fuente desconocida.",
        "INFO",
        {"check": "unknown"},
    )

    events = _events_of("AUDIT_SOURCE_CHECK")
    research_event = next(
        event for event in events if event["message"] == "Vocabulario de auditoría: fuente RESEARCH."
    )
    unknown_event = next(
        event for event in events if event["message"] == "Vocabulario de auditoría: fuente desconocida."
    )

    assert research_event["source"] == "RESEARCH"
    assert unknown_event["source"] == "MANUAL"  # unchanged sanitation for invalid sources
