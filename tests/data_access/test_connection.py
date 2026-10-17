
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
