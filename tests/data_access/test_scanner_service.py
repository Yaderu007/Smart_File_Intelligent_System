
"""
Test scanner integration with SQLite database storage.

These tests verify scan records, file metadata, duplicate groups,
hash storage, validation, and transaction rollback.
"""

import pytest

from src.data_access.connection import (
    get_connection,
    initialize_database,
)
from src.data_access.scanner_service import save_scan
import src.data_access.scanner_service as scanner_service


@pytest.fixture
def test_database(tmp_path):
    """
    Create an isolated SQLite database for integration tests.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        Path: Path to the initialized test database.
    """

    # Create a fresh database for each test.
    database_path = tmp_path / "test_integration.db"

    # Initialize all database tables.
    initialize_database(database_path)

    return database_path


def test_save_scan_stores_files_and_duplicates(tmp_path, test_database):
    """
    Verify that a scan stores files, hashes, and duplicate groups.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when all scan data is saved correctly.
    """

    # Create a temporary directory containing test files.
    scan_directory = tmp_path / "documents"
    scan_directory.mkdir()

    # Create two identical files and one unique file.
    (scan_directory / "first.txt").write_text("Same content")
    (scan_directory / "second.txt").write_text("Same content")
    (scan_directory / "unique.txt").write_text("Different content")

    # Scan the directory and save the results.
    scan_id = save_scan(
        str(scan_directory),
        database_path=str(test_database),
    )

    connection = get_connection(test_database)

    try:
        # Verify that the scan was completed successfully.
        scan = connection.execute(
            "SELECT * FROM Scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

        assert scan is not None
        assert scan["scan_path"] == str(scan_directory.resolve())
        assert scan["status"] == "completed"
        assert scan["file_count"] == 3

        expected_size = (
            len("Same content".encode()) * 2
            + len("Different content".encode())
        )

        assert scan["total_size"] == expected_size

        # Verify that the scan duration is stored in whole seconds.
        assert isinstance(scan["scan_duration"], int)
        assert scan["scan_duration"] >= 0

        # Verify that all three files were saved.
        files = connection.execute(
            "SELECT * FROM Files WHERE scan_id = ?",
            (scan_id,),
        ).fetchall()

        assert len(files) == 3

        # Verify that one duplicate group was created.
        groups = connection.execute(
            "SELECT * FROM DuplicateGroups WHERE scan_id = ?",
            (scan_id,),
        ).fetchall()

        assert len(groups) == 1
        assert groups[0]["duplicate_count"] == 2
        assert groups[0]["potential_savings"] == len(
            "Same content".encode()
        )

        # Verify that both duplicate files belong to the group.
        members = connection.execute(
            """
            SELECT f.path, dm.is_primary
            FROM DuplicateMembers AS dm
            JOIN Files AS f ON f.file_id = dm.file_id
            WHERE dm.group_id = ?
            ORDER BY f.path
            """,
            (groups[0]["group_id"],),
        ).fetchall()

        assert len(members) == 2

        # The first path in plain string sort must be primary.
        assert members[0]["path"] == str(scan_directory / "first.txt")
        assert members[0]["is_primary"] == 1
        assert members[1]["is_primary"] == 0

        # Verify that both duplicate candidates have SHA-256 hashes.
        hashes = connection.execute(
            """
            SELECT fh.hash_algorithm
            FROM FileHashes AS fh
            JOIN Files AS f ON f.file_id = fh.file_id
            WHERE f.scan_id = ?
            """,
            (scan_id,),
        ).fetchall()

        assert len(hashes) == 2
        assert all(
            row["hash_algorithm"] == "sha256"
            for row in hashes
        )

    finally:
        # Close the verification connection.
        connection.close()


def test_save_scan_empty_directory(tmp_path, test_database):
    """
    Verify that scanning an empty directory creates a completed scan.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when scan statistics remain zero.
    """

    # Create an empty directory.
    empty_directory = tmp_path / "empty"
    empty_directory.mkdir()

    scan_id = save_scan(
        str(empty_directory),
        database_path=str(test_database),
    )

    connection = get_connection(test_database)

    try:
        # Verify that the empty scan completed successfully.
        scan = connection.execute(
            "SELECT * FROM Scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

        assert scan is not None
        assert scan["status"] == "completed"
        assert scan["file_count"] == 0
        assert scan["total_size"] == 0
        assert isinstance(scan["scan_duration"], int)

        # Verify that no files were inserted.
        count = connection.execute(
            "SELECT COUNT(*) FROM Files WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()[0]

        assert count == 0

    finally:
        connection.close()


@pytest.mark.parametrize(
    "invalid_path",
    ["", "   ", None, 123],
)
def test_save_scan_rejects_invalid_paths(invalid_path, test_database):
    """
    Verify that invalid directory paths are rejected.

    Args:
        invalid_path: Invalid directory path to test.
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when an appropriate error is raised.
    """

    # Reject empty paths and unsupported input types.
    with pytest.raises((TypeError, ValueError)):
        save_scan(
            invalid_path,
            database_path=str(test_database),
        )


def test_save_scan_rejects_missing_directory(tmp_path, test_database):
    """
    Verify that a nonexistent directory cannot be scanned.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when ValueError is raised.
    """

    missing_directory = tmp_path / "missing"

    # A nonexistent directory must not start a scan.
    with pytest.raises(ValueError):
        save_scan(
            str(missing_directory),
            database_path=str(test_database),
        )


def test_save_scan_rejects_empty_file_path(
    tmp_path,
    test_database,
    monkeypatch,
):
    """
    Verify that scanner metadata with an empty path is rejected.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized temporary database.
        monkeypatch (pytest.MonkeyPatch): Replaces scanner functions.

    Returns:
        None: The test passes when invalid metadata is rejected.
    """

    # Return a scanner record with an invalid path.
    monkeypatch.setattr(
        scanner_service,
        "scan_directory",
        lambda path: [
            {
                "path": "",
                "name": "invalid.txt",
                "size": 10,
                "accessible": True,
            }
        ],
    )

    monkeypatch.setattr(
        scanner_service,
        "detect_duplicates",
        lambda files: {
            "duplicate_groups": [],
            "file_hashes": {},
        },
    )

    # The backend must reject the invalid scanner record.
    with pytest.raises(ValueError, match="non-empty path and name"):
        save_scan(
            str(tmp_path),
            database_path=str(test_database),
        )


def test_save_scan_rejects_empty_file_name(
    tmp_path,
    test_database,
    monkeypatch,
):
    """
    Verify that scanner metadata with an empty name is rejected.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized temporary database.
        monkeypatch (pytest.MonkeyPatch): Replaces scanner functions.

    Returns:
        None: The test passes when invalid metadata is rejected.
    """

    # Return a scanner record with an invalid name.
    monkeypatch.setattr(
        scanner_service,
        "scan_directory",
        lambda path: [
            {
                "path": str(tmp_path / "invalid.txt"),
                "name": "",
                "size": 10,
                "accessible": True,
            }
        ],
    )

    monkeypatch.setattr(
        scanner_service,
        "detect_duplicates",
        lambda files: {
            "duplicate_groups": [],
            "file_hashes": {},
        },
    )

    # The backend must reject the invalid scanner record.
    with pytest.raises(ValueError, match="non-empty path and name"):
        save_scan(
            str(tmp_path),
            database_path=str(test_database),
        )


def test_save_scan_rejects_unknown_hash_path(
    tmp_path,
    test_database,
    monkeypatch,
):
    """
    Verify that a hash referencing an unknown file causes failure.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized temporary database.
        monkeypatch (pytest.MonkeyPatch): Replaces duplicate detection.

    Returns:
        None: The test passes when the scan fails and rolls back.
    """

    # Create a valid file for the scanner.
    (tmp_path / "known.txt").write_text("Known content")

    # Return a hash for a file that was never scanned.
    monkeypatch.setattr(
        scanner_service,
        "detect_duplicates",
        lambda files: {
            "duplicate_groups": [],
            "file_hashes": {
                str(tmp_path / "unknown.txt"): "a" * 64,
            },
        },
    )

    with pytest.raises(KeyError, match="unknown file path"):
        save_scan(
            str(tmp_path),
            database_path=str(test_database),
        )

    connection = get_connection(test_database)

    try:
        # The scan remains failed without any saved files.
        scan = connection.execute(
            "SELECT * FROM Scans"
        ).fetchone()

        assert scan is not None
        assert scan["status"] == "failed"

        count = connection.execute(
            "SELECT COUNT(*) FROM Files"
        ).fetchone()[0]

        assert count == 0

    finally:
        connection.close()


def test_save_scan_rejects_unknown_duplicate_path(
    tmp_path,
    test_database,
    monkeypatch,
):
    """
    Verify that duplicate members must reference saved files.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized temporary database.
        monkeypatch (pytest.MonkeyPatch): Replaces duplicate detection.

    Returns:
        None: The test passes when the scan fails and rolls back.
    """

    # Create a valid file for the scanner.
    (tmp_path / "known.txt").write_text("Known content")

    # Return a duplicate group referencing an unknown file.
    monkeypatch.setattr(
        scanner_service,
        "detect_duplicates",
        lambda files: {
            "duplicate_groups": [
                {
                    "hash": "a" * 64,
                    "count": 2,
                    "potential_savings": 10,
                    "files": [
                        {"path": str(tmp_path / "known.txt")},
                        {"path": str(tmp_path / "unknown.txt")},
                    ],
                }
            ],
            "file_hashes": {},
        },
    )

    with pytest.raises(KeyError, match="unknown file path"):
        save_scan(
            str(tmp_path),
            database_path=str(test_database),
        )

    connection = get_connection(test_database)

    try:
        # No duplicate group or file records should remain.
        scan = connection.execute(
            "SELECT * FROM Scans"
        ).fetchone()

        assert scan is not None
        assert scan["status"] == "failed"

        for table in (
            "Files",
            "DuplicateGroups",
            "DuplicateMembers",
        ):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            assert count == 0

    finally:
        connection.close()


def test_save_scan_rolls_back_on_storage_failure(
    tmp_path,
    test_database,
    monkeypatch,
):
    """
    Verify that a storage error rolls back files and marks the scan failed.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized temporary database.
        monkeypatch (pytest.MonkeyPatch): Replaces the hash-saving function.

    Returns:
        None: The test passes when only the failed scan record remains.
    """

    scan_directory = tmp_path / "rollback"
    scan_directory.mkdir()

    # Create matching files so duplicate detection calculates hashes.
    (scan_directory / "first.txt").write_text("Identical")
    (scan_directory / "second.txt").write_text("Identical")

    def failing_save_file_hash(*args, **kwargs):
        """
        Simulate a database failure while saving a file hash.

        Args:
            *args: Positional arguments passed to the function.
            **kwargs: Keyword arguments passed to the function.

        Returns:
            None: This function always raises an error.

        Raises:
            RuntimeError: Always raised to simulate a storage failure.
        """
        raise RuntimeError("Simulated hash storage failure")

    # Force an error after the scan and files have been inserted.
    monkeypatch.setattr(
        scanner_service,
        "save_file_hash",
        failing_save_file_hash,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated hash storage failure",
    ):
        save_scan(
            str(scan_directory),
            database_path=str(test_database),
        )

    connection = get_connection(test_database)

    try:
        # Verify that the original scan remains marked as failed.
        scans = connection.execute(
            "SELECT * FROM Scans"
        ).fetchall()

        assert len(scans) == 1
        assert scans[0]["status"] == "failed"
        assert scans[0]["file_count"] == 0
        assert scans[0]["total_size"] == 0
        assert isinstance(scans[0]["scan_duration"], int)

        # Verify that no partial file or duplicate records remain.
        for table in (
            "Files",
            "FileHashes",
            "DuplicateGroups",
            "DuplicateMembers",
        ):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            assert count == 0

    finally:
        connection.close()
