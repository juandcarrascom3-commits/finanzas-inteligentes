"""Migration integrity tests against an isolated temporary database."""

import pytest

from database.db_manager import DatabaseManager


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
