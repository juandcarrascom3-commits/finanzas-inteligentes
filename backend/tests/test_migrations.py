"""Migration integrity tests against an isolated temporary database."""

import os
import sqlite3

import pytest

from database import db_manager
from database.db_manager import DatabaseManager


def _schema_state(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        versions = [
            row["version"]
            for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        ]
    finally:
        connection.close()
    return tables, versions


def test_modified_applied_migration_checksum_is_rejected(tmp_path):
    db_path = tmp_path / "migration-checksum.db"
    manager = DatabaseManager(db_path=str(db_path))

    with manager.get_connection() as connection:
        migrations = connection.execute(
            "SELECT version, filename, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert migrations

        affected = migrations[0]
        connection.execute(
            "UPDATE schema_migrations SET checksum = ? WHERE version = ?",
            ("invalid-checksum", affected["version"]),
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="was modified after being applied") as exc_info:
        DatabaseManager(db_path=str(db_path))

    assert affected["filename"] in str(exc_info.value)


def test_failed_migration_rolls_back_and_is_not_recorded(tmp_path, monkeypatch):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_sqlite_fixture.sql").write_text(
        "CREATE TABLE fixture_a (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    (migrations_dir / "002_sqlite_fixture.sql").write_text(
        "CREATE TABLE fixture_c (id INTEGER PRIMARY KEY);\n"
        "THIS IS NOT VALID SQL;\n"
        "CREATE TABLE fixture_e (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(db_manager, "MIGRATIONS_DIR", str(migrations_dir))
    db_path = tmp_path / "atomic.db"

    with pytest.raises(sqlite3.DatabaseError):
        DatabaseManager(db_path=str(db_path))

    tables, versions = _schema_state(db_path)
    assert "fixture_a" in tables          # previously applied migration stays applied
    assert "fixture_c" not in tables       # mutation A of the failed migration rolled back
    assert "fixture_e" not in tables       # mutation C never ran
    assert versions == ["001"]             # no record written for the failed migration

    with pytest.raises(sqlite3.DatabaseError):
        DatabaseManager(db_path=str(db_path))
    _, versions = _schema_state(db_path)
    assert versions == ["001"]

    os.remove(db_path)  # deterministic close: no handle left behind on Windows
