"""Regression tests proving the suite runs on an isolated database.

These tests use actual runtime state: the ``backend.app`` singleton built
at import time and live writes through the same ``TestClient`` the API
suite uses. They never read or write the default (personal) database
location; they only assert that it is NOT in use.

Ported from feature/testing-foundation to CURRENT main semantics: the
authoritative contract is ``backend/tests/conftest.py`` on this branch
(``finance-pytest-`` temp directory + ``FINANCE_DB_PATH`` /
``FINANCE_SEED_DEMO`` exported before collection).
"""

import os
import sqlite3
import tempfile

import backend.app as app_module
from database.db_manager import DEFAULT_DB_FILE, resolve_db_path


def _abspath(path: str) -> str:
    return os.path.abspath(path)


def _under_os_temp(path: str) -> bool:
    return _abspath(path).startswith(_abspath(tempfile.gettempdir()))


def test_conftest_exports_isolated_db_path_before_collection():
    env_path = os.environ.get("FINANCE_DB_PATH")
    assert env_path, "backend/tests/conftest.py must set FINANCE_DB_PATH at import"
    # Never the module-relative default where a personal DB would live.
    assert _abspath(env_path) != _abspath(DEFAULT_DB_FILE)
    # Controlled location: a fresh temp directory, not the repository checkout.
    assert _under_os_temp(env_path)


def test_backend_app_singleton_uses_isolated_database():
    app_db = _abspath(app_module.db.db_path)
    env_db = _abspath(os.environ["FINANCE_DB_PATH"])
    assert app_db == env_db, "backend.app must be constructed on the test database"
    # The default path is where the personal database resolves when
    # FINANCE_DB_PATH is unset; it must not be in use by the suite.
    assert app_db != _abspath(DEFAULT_DB_FILE)
    assert os.path.dirname(app_db) != os.path.dirname(_abspath(DEFAULT_DB_FILE))
    assert _under_os_temp(app_db)
    assert os.path.isfile(app_db)


def test_resolve_db_path_follows_the_isolation_contract():
    assert _abspath(resolve_db_path()) == _abspath(os.environ["FINANCE_DB_PATH"])


def test_existing_api_suite_targets_the_isolated_app_singleton():
    # test_api_endpoints.py does `from backend.app import app` and builds
    # TestClient(app): the very singleton asserted above. Proving identity
    # proves its CRUD/CSV/backup mutations land in the isolated database.
    import test_api_endpoints

    assert test_api_endpoints.app is app_module.app
    assert test_api_endpoints.db is app_module.db


def test_live_write_lands_in_isolated_database():
    from fastapi.testclient import TestClient

    client = TestClient(app_module.app)
    created = client.post(
        "/api/accounts",
        json={
            "name": "T0 isolation probe",
            "account_type": "checking",
            "currency": "USD",
            "opening_balance": 1,
            "current_balance": 1,
        },
    )
    assert created.status_code == 200
    account_id = created.json()["id"]
    try:
        conn = sqlite3.connect(os.environ["FINANCE_DB_PATH"])
        try:
            (count,) = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
        finally:
            conn.close()
        assert count == 1, "write must be visible in the isolated database file"
    finally:
        deleted = client.delete(f"/api/accounts/{account_id}")
        assert deleted.status_code == 200


def test_demo_seed_control_is_deterministic():
    # conftest explicitly controls FINANCE_SEED_DEMO for the suite.
    assert os.environ.get("FINANCE_SEED_DEMO") == "1"
    assert app_module.db.seed_demo is True
