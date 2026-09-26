"""S2A database integrity: SQLite-consistent backups, safe restore, deterministic closes."""

import glob
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from database.db_manager import DatabaseManager


@pytest.fixture
def finance_db(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    db = DatabaseManager(db_path=str(tmp_path / "finance.db"))
    db.save_account({
        "name": "Original",
        "account_type": "checking",
        "currency": "USD",
        "current_balance": 100,
    })
    return db


def _backup_directory(db) -> str:
    return os.path.join(os.path.dirname(db.db_path), "backups")


def _account_names(db):
    return [account["name"] for account in db.get_accounts()]


def _table_names(db_path):
    connection = sqlite3.connect(db_path)
    try:
        return {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        connection.close()


def _account_names_file(db_path):
    connection = sqlite3.connect(db_path)
    try:
        return [row[0] for row in connection.execute("SELECT name FROM accounts")]
    finally:
        connection.close()


def _integrity(db_path) -> str:
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()


def test_export_backup_produces_valid_sqlite_snapshot(finance_db):
    backup = finance_db.export_backup()

    validation = finance_db.validate_backup(backup["db_backup_path"])

    assert validation["valid"] is True
    assert "accounts" in validation["tables"]
    assert "schema_migrations" in validation["tables"]
    assert validation["latest_version"] is not None


def test_export_backup_contains_data_committed_before_backup(finance_db):
    finance_db.save_account({
        "name": "Snapshot",
        "account_type": "savings",
        "currency": "USD",
        "current_balance": 5,
    })

    backup = finance_db.export_backup()

    connection = sqlite3.connect(backup["db_backup_path"])
    try:
        names = [row[0] for row in connection.execute("SELECT name FROM accounts")]
    finally:
        connection.close()
    assert "Original" in names
    assert "Snapshot" in names


def test_restore_replaces_live_database_with_backup_state(finance_db):
    backup = finance_db.export_backup()
    finance_db.save_account({
        "name": "AfterBackup",
        "account_type": "checking",
        "currency": "USD",
        "current_balance": 1,
    })
    assert "AfterBackup" in _account_names(finance_db)

    result = finance_db.restore_backup(backup["db_backup_path"])

    assert result["status"] == "RESTORED"
    names = _account_names(finance_db)
    assert "Original" in names
    assert "AfterBackup" not in names


def test_restore_creates_valid_pre_restore_snapshot(finance_db):
    finance_db.save_account({
        "name": "ToBeReplaced",
        "account_type": "checking",
        "currency": "USD",
        "current_balance": 7,
    })
    backup = finance_db.export_backup()

    result = finance_db.restore_backup(backup["db_backup_path"])

    pre_restore = result["pre_restore_backup_path"]
    assert pre_restore is not None
    assert os.path.basename(pre_restore).startswith("finance-pre-restore-")
    assert finance_db.validate_backup(pre_restore)["valid"] is True
    assert "ToBeReplaced" in _account_names_file(pre_restore)


def test_restore_rejects_source_outside_backup_directory(finance_db, tmp_path):
    outside = tmp_path / "outside" / "finance-backup-20260101-000000.db"
    outside.parent.mkdir()
    shutil.copy2(finance_db.db_path, str(outside))
    before = Path(finance_db.db_path).read_bytes()

    with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
        finance_db.restore_backup(str(outside))

    assert Path(finance_db.db_path).read_bytes() == before
    assert not os.path.exists(_backup_directory(finance_db))
    assert "Original" in _account_names(finance_db)


def test_restore_rejects_non_sqlite_source(finance_db):
    backup_dir = _backup_directory(finance_db)
    os.makedirs(backup_dir, exist_ok=True)
    fake = os.path.join(backup_dir, "finance-backup-00000000-000000-invalid.db")
    Path(fake).write_bytes(b"this is not a sqlite database file")
    before = Path(finance_db.db_path).read_bytes()

    try:
        with pytest.raises(ValueError, match="not a valid SQLite database"):
            finance_db.restore_backup(fake)

        assert Path(finance_db.db_path).read_bytes() == before
        assert _integrity(finance_db.db_path) == "ok"
        assert "Original" in _account_names(finance_db)
    finally:
        os.remove(fake)


def test_failed_post_restore_validation_recovers_previous_database(finance_db, monkeypatch):
    backup = finance_db.export_backup()
    finance_db.save_account({
        "name": "LiveOnly",
        "account_type": "checking",
        "currency": "USD",
        "current_balance": 3,
    })

    def fail_verification():
        raise ValueError("simulated post-restore validation failure")

    monkeypatch.setattr(finance_db, "_verify_restored_database", fail_verification)

    with pytest.raises(ValueError, match="previous database was left unchanged"):
        finance_db.restore_backup(backup["db_backup_path"])

    assert _integrity(finance_db.db_path) == "ok"
    names = _account_names(finance_db)
    assert "Original" in names
    assert "LiveOnly" in names

    pre_restore_files = glob.glob(os.path.join(_backup_directory(finance_db), "finance-pre-restore-*.db"))
    assert len(pre_restore_files) == 1
    assert finance_db.validate_backup(pre_restore_files[0])["valid"] is True


def test_generated_backup_paths_keep_contract(finance_db):
    backup = finance_db.export_backup()
    path = backup["db_backup_path"]

    assert os.path.realpath(os.path.dirname(path)) == os.path.realpath(_backup_directory(finance_db))
    assert os.path.basename(path).startswith("finance-backup-")
    assert path.endswith(".db")


def test_backup_and_restore_release_file_handles(finance_db):
    backup = finance_db.export_backup()
    result = finance_db.restore_backup(backup["db_backup_path"])
    pre_restore = result["pre_restore_backup_path"]
    assert pre_restore is not None

    for path in (backup["db_backup_path"], pre_restore):
        os.remove(path)  # PermissionError on Windows if a handle leaked

    assert _integrity(finance_db.db_path) == "ok"

    reopened = DatabaseManager(db_path=finance_db.db_path)
    assert "Original" in _account_names(reopened)
    assert _table_names(finance_db.db_path) >= {"accounts", "assets", "transactions", "schema_migrations"}
