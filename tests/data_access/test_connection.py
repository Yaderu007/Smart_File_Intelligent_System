
import sqlite3

import pytest

from src.data_access.connection import (
    get_connection,
    initialize_database,
)


def test_initialize_database_creates_tables(tmp_path):
    """
    Verify that initialization creates all required database tables.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        None: The test passes when all expected tables exist.
    """

    # Create a temporary database instead of using smart_files.db.
    test_db = tmp_path / "test_files.db"

    # Initialize the database using the project's schema.sql.
    initialize_database(test_db)

    # Open the temporary database to inspect its tables.
    connection = get_connection(test_db)

    try:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        # Extract table names from the query results.
        actual_tables = {row["name"] for row in rows}

        expected_tables = {
            "Scans",
            "Files",
            "FileHashes",
            "DuplicateGroups",
            "DuplicateMembers",
        }

        # Check that every required table was created.
        assert expected_tables.issubset(actual_tables)

    finally:
        connection.close()


def test_files_table_columns(tmp_path):
    """
    Verify that the Files table contains the expected columns.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        None: The test passes when the column names match.
    """

    test_db = tmp_path / "test_files.db"
    initialize_database(test_db)

    connection = get_connection(test_db)

    try:
        # PRAGMA table_info returns information about table columns.
        rows = connection.execute(
            "PRAGMA table_info(Files)"
        ).fetchall()

        actual_columns = {row["name"] for row in rows}

        expected_columns = {
            "file_id",
            "scan_id",
            "path",
            "name",
            "size",
            "extension",
            "category",
            "created",
            "modified",
            "accessed_timestamp",
            "accessible",
            "error",
        }

        # Ensure the database matches our updated schema.
        assert actual_columns == expected_columns

    finally:
        connection.close()


def test_connection_uses_row_factory(tmp_path):
    """
    Verify that database columns can be accessed by name.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        None: The test passes when named access works.
    """

    test_db = tmp_path / "test_files.db"

    connection = get_connection(test_db)

    try:
        # Select a sample value with a named column.
        row = connection.execute(
            "SELECT 42 AS example_value"
        ).fetchone()

        # sqlite3.Row allows access using column names.
        assert isinstance(row, sqlite3.Row)
        assert row["example_value"] == 42

    finally:
        connection.close()


def test_foreign_keys_enabled(tmp_path):
    """
    Verify that foreign-key enforcement is enabled.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        None: The test passes when foreign keys are enabled.
    """

    test_db = tmp_path / "test_files.db"

    connection = get_connection(test_db)

    try:
        # SQLite returns 1 when foreign-key enforcement is active.
        row = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()

        assert row[0] == 1

    finally:
        connection.close()


def test_foreign_key_rejects_invalid_scan(tmp_path):
    """
    Verify that a file cannot reference a nonexistent scan.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        None: The test passes when SQLite rejects the insertion.
    """

    test_db = tmp_path / "test_files.db"
    initialize_database(test_db)

    connection = get_connection(test_db)

    try:
        # Scan ID 999 does not exist in this fresh database.
        # SQLite should reject this file because of the foreign key.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO Files (scan_id, path, name)
                VALUES (?, ?, ?)
                """,
                (999, "/example/file.txt", "file.txt"),
            )

    finally:
        connection.rollback()
        connection.close()


def test_duplicate_groups_table_has_scan_id(tmp_path):
    """
    Verify that duplicate groups belong to a specific scan.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        None: The test passes when scan_id exists in the table.
    """
    test_db = tmp_path / "test_files.db"
    initialize_database(test_db)

    connection = get_connection(test_db)

    try:
        # Check the columns in the updated DuplicateGroups table.
        rows = connection.execute(
            "PRAGMA table_info(DuplicateGroups)"
        ).fetchall()

        actual_columns = {row["name"] for row in rows}

        # Our updated schema associates each group with a scan.
        assert "scan_id" in actual_columns

    finally:
        connection.close()


def test_initialize_database_is_idempotent(tmp_path):
    """
    Verify that initializing an existing database is safe.

    Running initialization twice should not delete existing
    records or recreate tables.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        None: The test passes when existing data is preserved.
    """
    test_db = tmp_path / "test_files.db"

    # Create the database and its tables.
    initialize_database(test_db)

    connection = get_connection(test_db)

    try:
        # Insert a record that should survive reinitialization.
        connection.execute(
            """
            INSERT INTO Scans (scan_path, scan_timestamp)
            VALUES (?, ?)
            """,
            ("/example", "2026-10-17T12:00:00+00:00"),
        )
        connection.commit()

    finally:
        connection.close()

    # Initialize the same database a second time.
    initialize_database(test_db)

    connection = get_connection(test_db)

    try:
        # Verify the existing scan was not removed.
        count = connection.execute(
            "SELECT COUNT(*) FROM Scans"
        ).fetchone()[0]

        assert count == 1

    finally:
        connection.close()


def test_initialize_database_rolls_back_on_sql_error(
    tmp_path,
    monkeypatch
):
    """
    Verify that schema initialization is atomic.

    If a SQL statement fails after creating a table, the
    entire initialization transaction should roll back.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        monkeypatch (pytest.MonkeyPatch): Fixture for temporarily
            replacing the schema file location.

    Returns:
        None: The test passes when partial tables are not retained.
    """
    from src.data_access import connection as connection_module

    # Create a temporary project root containing an invalid schema.
    fake_root = tmp_path / "fake_project"
    fake_root.mkdir()

    fake_schema = fake_root / "schema.sql"

    fake_schema.write_text(
        """
        CREATE TABLE TemporaryTest (id INTEGER PRIMARY KEY);
        THIS IS INVALID SQL;
        """,
        encoding="utf-8",
    )

    # Make initialize_database() read our temporary schema
    # instead of the real project's schema.sql.
    monkeypatch.setattr(
        connection_module,
        "PROJECT_ROOT",
        fake_root,
    )

    test_db = tmp_path / "rollback_test.db"

    # The invalid SQL must cause initialization to fail.
    with pytest.raises(sqlite3.Error):
        initialize_database(test_db)

    connection = get_connection(test_db)

    try:
        # The earlier CREATE TABLE must also have been undone.
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            ("TemporaryTest",),
        ).fetchone()

        assert row is None

    finally:
        connection.close()

