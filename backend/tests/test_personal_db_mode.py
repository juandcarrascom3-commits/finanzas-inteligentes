from database.db_manager import DatabaseManager


def test_personal_db_can_start_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "finance.local.db"
    monkeypatch.setenv("FINANCE_DB_PATH", str(db_path))
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")

    db = DatabaseManager()

    assert db.get_data_source()["mode"] == "REAL"
    assert db.get_assets() == []
    assert db.get_accounts() == []
    assert db.get_transactions() == []


def test_sqlite_migrations_are_versioned_and_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "finance.personal.db"
    monkeypatch.setenv("FINANCE_DB_PATH", str(db_path))
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")

    db = DatabaseManager()
    db.save_account({"name": "Daily", "account_type": "checking", "currency": "USD"})
    first_schema = db.get_schema_info()

    assert first_schema["latest_version"] == "004"
    assert [item["version"] for item in first_schema["migrations"]] == ["001", "002", "003", "004"]

    reopened = DatabaseManager()
    assert reopened.get_accounts()[0]["name"] == "Daily"
    assert reopened.get_schema_info()["migrations"] == first_schema["migrations"]


def test_backup_validate_and_restore_roundtrip(tmp_path, monkeypatch):
    db_path = tmp_path / "finance.personal.db"
    monkeypatch.setenv("FINANCE_DB_PATH", str(db_path))
    monkeypatch.setenv("FINANCE_SEED_DEMO", "0")

    db = DatabaseManager()
    account = db.save_account({
        "name": "Backup account",
        "account_type": "checking",
        "currency": "USD",
        "current_balance": 150,
    })
    db.save_transaction({
        "account_id": account["id"],
        "amount": -20,
        "category": "General",
        "date": "2026-09-21",
        "description": "Before backup",
        "currency": "USD",
    })
    db.save_budget({"category": "General", "monthly_limit": 300, "currency": "USD"})

    backup = db.export_backup()
    validation = db.validate_backup(backup["db_backup_path"])
    assert validation["valid"] is True
    assert validation["latest_version"] == "004"

    db.delete_account(account["id"])
    assert db.get_accounts() == []

    restored = db.restore_backup(backup["db_backup_path"])
    assert restored["status"] == "RESTORED"
    assert db.get_accounts()[0]["name"] == "Backup account"
    assert db.get_transactions()[0]["description"] == "Before backup"
    assert db.get_budgets()[0]["category"] == "General"
