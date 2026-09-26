"""S1A security boundaries: local `.env` loading and FINANCE backup path scope."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import PROJECT_ROOT, app, db as app_db, load_local_env
from database.db_manager import DatabaseManager, DEFAULT_DB_FILE

client = TestClient(app)

ENV_MARKER = "FINANCE_TEST_ENV_MARKER"
ENV_FILE_CONTENT = f"{ENV_MARKER}=from_env_file\n"


def _app_source() -> str:
    return (Path(PROJECT_ROOT) / "backend" / "app.py").read_text(encoding="utf-8")


def _link_directory(source: str, link: str) -> bool:
    """Create a directory reparse point; junctions avoid the admin requirement on Windows."""
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", link, source],
            capture_output=True,
        )
        if result.returncode == 0:
            return True
    try:
        os.symlink(source, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


# --- ENV loading -----------------------------------------------------------


def test_env_loading_is_harmless_when_env_file_is_absent(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_MARKER, raising=False)

    load_local_env(str(tmp_path / ".env"))

    assert ENV_MARKER not in os.environ


def test_env_file_values_are_loaded(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(ENV_FILE_CONTENT, encoding="utf-8")
    monkeypatch.delenv(ENV_MARKER, raising=False)

    load_local_env(str(env_file))

    assert os.environ[ENV_MARKER] == "from_env_file"


def test_process_environment_overrides_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(ENV_FILE_CONTENT, encoding="utf-8")
    monkeypatch.setenv(ENV_MARKER, "process_wins")

    load_local_env(str(env_file))

    assert os.environ[ENV_MARKER] == "process_wins"


def test_env_load_runs_before_application_configuration():
    source = _app_source()
    load_at = source.index("\nload_local_env()")
    cors_at = source.index("cors_origins = [")
    db_at = source.index("\ndb = DatabaseManager()")

    assert load_at < cors_at < db_at


def test_t0_database_isolation_still_applies():
    assert app_db.db_path == os.environ["FINANCE_DB_PATH"]
    assert os.path.abspath(app_db.db_path) != os.path.abspath(DEFAULT_DB_FILE)
    assert os.environ.get("FINANCE_SEED_DEMO") == "1"

    response = client.get("/api/data-source")
    assert response.status_code == 200
    assert os.path.abspath(response.json()["db_path"]) == os.path.abspath(os.environ["FINANCE_DB_PATH"])


# --- Backup path boundary --------------------------------------------------


@pytest.fixture
def backup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")
    return DatabaseManager(db_path=str(tmp_path / "finance.db"))


def test_generated_backup_path_is_accepted(backup_db):
    backup = backup_db.export_backup()
    path = backup["db_backup_path"]

    assert os.path.basename(path).startswith("finance-backup-")

    validation = backup_db.validate_backup(path)
    assert validation["valid"] is True
    assert validation["path"] == path


def test_generated_pre_restore_path_is_accepted(backup_db):
    backup = backup_db.export_backup()
    restored = backup_db.restore_backup(backup["db_backup_path"])
    pre_restore = restored["pre_restore_backup_path"]

    assert pre_restore is not None
    assert os.path.basename(pre_restore).startswith("finance-pre-restore-")
    assert backup_db.validate_backup(pre_restore)["valid"] is True
    assert restored["status"] == "RESTORED"
    assert backup_db.get_accounts() == []


def test_traversal_path_is_rejected(backup_db, tmp_path):
    backup_dir = os.path.dirname(os.path.abspath(backup_db.db_path))
    outside = tmp_path / "outside.db"
    shutil.copy2(backup_db.db_path, outside)

    traversal = os.path.join(backup_dir, "backups", "..", "outside.db")
    with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
        backup_db.validate_backup(traversal)

    deep = os.path.join(backup_dir, "backups", "..", "..", "missing", "finance-backup-1.db")
    with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
        backup_db.validate_backup(deep)


def test_foreign_absolute_path_is_rejected(backup_db, tmp_path):
    foreign_dir = tmp_path / "elsewhere"
    foreign_dir.mkdir()
    foreign = foreign_dir / "finance-backup-20260101-000000.db"
    shutil.copy2(backup_db.db_path, foreign)

    with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
        backup_db.validate_backup(str(foreign))
    with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
        backup_db.restore_backup(str(foreign))
    with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
        backup_db.validate_backup(os.path.join("\\\\server\\share", "finance-backup-1.db"))


def test_sibling_backup_directory_is_rejected(backup_db, tmp_path):
    sibling = tmp_path / "sibling" / "backups"
    sibling.mkdir(parents=True)
    copy = sibling / "finance-backup-20260101-000000.db"
    shutil.copy2(backup_db.db_path, copy)

    with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
        backup_db.validate_backup(str(copy))


def test_invalid_filename_patterns_are_rejected(backup_db):
    backup_dir = backup_db._backup_directory()
    os.makedirs(backup_dir, exist_ok=True)

    for name in (
        "random.db",
        "finance-export-20260101.db",
        "finance-backup-20260101-000000.txt",
        "not-a-backup.txt",
    ):
        candidate = os.path.join(backup_dir, name)
        Path(candidate).write_text("not a backup", encoding="utf-8")
        with pytest.raises(ValueError):
            backup_db.validate_backup(candidate)

    os.makedirs(os.path.join(backup_dir, "finance-backup-directory.db"))
    with pytest.raises(ValueError, match="does not exist"):
        backup_db.validate_backup(os.path.join(backup_dir, "finance-backup-directory.db"))


def test_symlink_outside_backup_directory_is_rejected(backup_db, tmp_path):
    backup_dir = backup_db._backup_directory()
    os.makedirs(backup_dir, exist_ok=True)
    target = tmp_path / "linked-outside.db"
    shutil.copy2(backup_db.db_path, target)
    link = os.path.join(backup_dir, "finance-backup-linked.db")

    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted for this user/platform")

    try:
        with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
            backup_db.validate_backup(link)
    finally:
        os.unlink(link)


def test_directory_link_resolving_outside_backup_directory_is_rejected(backup_db, tmp_path):
    backup_dir = backup_db._backup_directory()
    os.makedirs(backup_dir, exist_ok=True)
    outside = tmp_path / "outside-dir"
    outside.mkdir()
    shutil.copy2(backup_db.db_path, str(outside / "finance-backup-20260101-000000.db"))
    link = os.path.join(backup_dir, "finance-backup-trick.db")

    if not _link_directory(str(outside), link):
        pytest.skip("directory link creation is not permitted for this user/platform")

    try:
        nested = os.path.join(link, "finance-backup-20260101-000000.db")
        with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
            backup_db.validate_backup(nested)
        with pytest.raises(ValueError, match="inside the FINANCE backup directory"):
            backup_db.validate_backup(link)
    finally:
        try:
            os.rmdir(link)  # removes only the link, never the target contents
        except OSError:
            pass


def test_non_sqlite_backup_returns_controlled_validation_error():
    backup_dir = app_db._backup_directory()
    os.makedirs(backup_dir, exist_ok=True)
    fake = os.path.join(backup_dir, "finance-backup-00000000-000000-invalid.db")
    Path(fake).write_bytes(b"this is definitely not a sqlite database file")

    try:
        with pytest.raises(ValueError) as exc_info:
            app_db.validate_backup(fake)
        assert str(exc_info.value) == "Backup file is not a valid SQLite database."
        assert fake not in str(exc_info.value)

        validate = client.post("/api/backup/validate", json={"path": fake})
        assert validate.status_code == 400
        assert validate.json()["detail"] == "Backup file is not a valid SQLite database."

        restore = client.post("/api/backup/restore", json={"path": fake})
        assert restore.status_code == 400
        assert restore.json()["detail"] == "Backup file is not a valid SQLite database."
    finally:
        os.remove(fake)


def test_api_backup_endpoints_reject_foreign_path(tmp_path):
    foreign = tmp_path / "finance-backup-20260101-000000.db"
    shutil.copy2(app_db.db_path, foreign)

    validate = client.post("/api/backup/validate", json={"path": str(foreign)})
    assert validate.status_code == 400

    restore = client.post("/api/backup/restore", json={"path": str(foreign)})
    assert restore.status_code == 400
    assert os.path.exists(app_db.db_path)


def test_restore_with_rejected_path_performs_no_replacement(backup_db, tmp_path):
    account = backup_db.save_account({
        "name": "Untouched",
        "account_type": "checking",
        "currency": "USD",
        "current_balance": 100,
    })
    db_file = Path(backup_db.db_path)
    before = db_file.read_bytes()

    foreign_dir = tmp_path / "foreign-backups"
    foreign_dir.mkdir()
    foreign = foreign_dir / "finance-backup-20260101-000000.db"
    shutil.copy2(backup_db.db_path, foreign)

    with pytest.raises(ValueError):
        backup_db.restore_backup(str(foreign))

    assert db_file.read_bytes() == before
    assert backup_db.get_accounts()[0]["id"] == account["id"]
    assert not os.path.exists(backup_db._backup_directory())
