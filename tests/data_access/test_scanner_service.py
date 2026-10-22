
"""
Test scanner result persistence in the SQLite database.

Tests cover file metadata, hashes, duplicate groups, validation,
scan statistics, and transaction rollback.
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
    Create an isolated SQLite database for each test.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        Path: Path to the initialized test database.
    """
    database_path = tmp_path / "test_integration.db"
    initialize_database(database_path)
    return database_path


def make_file(path, size=10):
    """
    Build a valid scanner metadata record.

    Args:
        path (Path): Absolute path of the file.
        size (int | None): Size of the file in bytes.

    Returns:
        dict: File metadata suitable for database storage.
    """
    return {
        "path": str(path),
        "name": path.name,
        "extension": path.suffix.lower(),
        "size": size,
        "created": None,
        "modified": None,
        "accessible": True,
        "error": None,
        "category": "Documents",
    }


def empty_duplicate_result():
    """
    Build a duplicate detection result with no duplicates.

    Returns:
        dict: Empty duplicate groups and file hashes.
    """
    return {
        "duplicate_groups": [],
        "file_hashes": {},
    }


def assert_failed_scan_without_data(database_path):
    """
    Verify that failed persistence leaves no partial file data.

    Args:
        database_path (Path): Database to inspect.

    Returns:
        None: Assertions verify the failed scan and empty tables.
    """
    connection = get_connection(database_path)

    try:
        scans = connection.execute(
            "SELECT * FROM Scans"
        ).fetchall()

        assert len(scans) == 1
        assert scans[0]["status"] == "failed"
        assert scans[0]["file_count"] == 0
        assert scans[0]["total_size"] == 0

        # No file-related records should survive rollback.
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


def test_save_scan_stores_files_and_duplicates(tmp_path, test_database):
    """
    Verify that files, hashes, and duplicate groups are saved.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized test database.

    Returns:
        None: Assertions verify persisted scan information.
    """
    scan_directory = tmp_path / "documents"
    scan_directory.mkdir()

    first = scan_directory / "first.txt"
    second = scan_directory / "second.txt"
    unique = scan_directory / "unique.txt"

    first.write_text("Same content")
    second.write_text("Same content")
    unique.write_text("Different content")

    duplicate_size = first.stat().st_size

    files = [
        make_file(first, duplicate_size),
        make_file(second, duplicate_size),
        make_file(unique, unique.stat().st_size),
    ]

    # Duplicate members arrive in plain path-sorted order.
    duplicate_result = {
        "duplicate_groups": [
            {
                "hash": "a" * 64,
                "files": [files[0], files[1]],
                "count": 2,
                "potential_savings": duplicate_size,
            }
        ],
        "file_hashes": {
            str(first): "a" * 64,
            str(second): "a" * 64,
        },
    }

    scan_id = save_scan(
        scan_path=str(scan_directory),
        files=files,
        duplicate_result=duplicate_result,
        duration_seconds=3,
        database_path=str(test_database),
    )

    connection = get_connection(test_database)

    try:
        scan = connection.execute(
            "SELECT * FROM Scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

        assert scan is not None
        assert scan["scan_path"] == str(scan_directory)
        assert scan["status"] == "completed"
        assert scan["file_count"] == 3
        assert scan["total_size"] == sum(
            file["size"] for file in files
        )
        assert scan["scan_duration"] == 3

        saved_files = connection.execute(
            "SELECT * FROM Files WHERE scan_id = ?",
            (scan_id,),
        ).fetchall()

        assert len(saved_files) == 3

        groups = connection.execute(
            "SELECT * FROM DuplicateGroups WHERE scan_id = ?",
            (scan_id,),
        ).fetchall()

        assert len(groups) == 1
        assert groups[0]["duplicate_count"] == 2
        assert groups[0]["potential_savings"] == duplicate_size

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
        assert members[0]["path"] == str(first)
        assert members[0]["is_primary"] == 1
        assert members[1]["path"] == str(second)
        assert members[1]["is_primary"] == 0

        hashes = connection.execute(
            """
            SELECT f.path, fh.hash_algorithm, fh.hash_value
            FROM FileHashes AS fh
            JOIN Files AS f ON f.file_id = fh.file_id
            WHERE f.scan_id = ?
            """,
            (scan_id,),
        ).fetchall()

        assert len(hashes) == 2
        assert {row["path"] for row in hashes} == {
            str(first),
            str(second),
        }
        assert all(
            row["hash_algorithm"] == "sha256"
            and row["hash_value"] == "a" * 64
            for row in hashes
        )

    finally:
        connection.close()


def test_save_scan_empty_directory(tmp_path, test_database):
    """
    Verify that an empty file list creates a completed scan.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized test database.

    Returns:
        None: Assertions verify zero counts and a null duration.
    """
    empty_directory = tmp_path / "empty"
    empty_directory.mkdir()

    scan_id = save_scan(
        scan_path=str(empty_directory),
        files=[],
        duplicate_result=empty_duplicate_result(),
        duration_seconds=None,
        database_path=str(test_database),
    )

    connection = get_connection(test_database)

    try:
        scan = connection.execute(
            "SELECT * FROM Scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

        assert scan is not None
        assert scan["status"] == "completed"
        assert scan["file_count"] == 0
        assert scan["total_size"] == 0
        assert scan["scan_duration"] is None

        file_count = connection.execute(
            "SELECT COUNT(*) FROM Files WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()[0]

        assert file_count == 0

    finally:
        connection.close()


@pytest.mark.parametrize(
    "invalid_path",
    ["", "   ", None, 123],
)
def test_save_scan_rejects_invalid_paths(
    invalid_path,
    test_database,
):
    """
    Verify that invalid scan paths are rejected.

    Args:
        invalid_path: Invalid path value.
        test_database (Path): Initialized test database.

    Returns:
        None: The test passes when validation raises an error.
    """
    with pytest.raises((TypeError, ValueError)):
        save_scan(
            scan_path=invalid_path,
            files=[],
            database_path=str(test_database),
        )


def test_save_scan_accepts_previously_scanned_path(
    tmp_path,
    test_database,
):
    """
    Verify that persistence does not scan the filesystem again.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized test database.

    Returns:
        None: The test passes when supplied metadata is saved.
    """
    # The backend receives metadata, not a directory to traverse.
    scan_path = tmp_path / "already_scanned"

    scan_id = save_scan(
        scan_path=str(scan_path),
        files=[],
        duplicate_result=empty_duplicate_result(),
        duration_seconds=0,
        database_path=str(test_database),
    )

    connection = get_connection(test_database)

    try:
        scan = connection.execute(
            "SELECT * FROM Scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

        assert scan["status"] == "completed"
        assert scan["scan_duration"] == 0

    finally:
        connection.close()


@pytest.mark.parametrize(
    "invalid_field",
    ["path", "name"],
)
def test_save_scan_rejects_empty_file_metadata(
    tmp_path,
    test_database,
    invalid_field,
):
    """
    Verify that empty file paths and names cause a failed scan.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized test database.
        invalid_field (str): Metadata field to invalidate.

    Returns:
        None: Assertions verify rejection and rollback.
    """
    record = make_file(tmp_path / "invalid.txt")
    record[invalid_field] = ""

    with pytest.raises(
        ValueError,
        match="non-empty path and name",
    ):
        save_scan(
            scan_path=str(tmp_path),
            files=[record],
            duplicate_result=empty_duplicate_result(),
            duration_seconds=1,
            database_path=str(test_database),
        )

    assert_failed_scan_without_data(test_database)


def test_save_scan_rejects_unknown_hash_path(
    tmp_path,
    test_database,
):
    """
    Verify that a hash cannot reference an unsaved file.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized test database.

    Returns:
        None: Assertions verify rejection and rollback.
    """
    known = tmp_path / "known.txt"
    unknown = tmp_path / "unknown.txt"

    duplicate_result = {
        "duplicate_groups": [],
        "file_hashes": {
            str(unknown): "a" * 64,
        },
    }

    with pytest.raises(KeyError, match="unknown file path"):
        save_scan(
            scan_path=str(tmp_path),
            files=[make_file(known)],
            duplicate_result=duplicate_result,
            duration_seconds=2,
            database_path=str(test_database),
        )

    assert_failed_scan_without_data(test_database)


def test_save_scan_rejects_unknown_duplicate_path(
    tmp_path,
    test_database,
):
    """
    Verify that duplicate members reference saved files only.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized test database.

    Returns:
        None: Assertions verify rejection and rollback.
    """
    known = tmp_path / "known.txt"
    unknown = tmp_path / "unknown.txt"

    duplicate_result = {
        "duplicate_groups": [
            {
                "hash": "a" * 64,
                "count": 2,
                "potential_savings": 10,
                "files": [
                    {"path": str(known)},
                    {"path": str(unknown)},
                ],
            }
        ],
        "file_hashes": {},
    }

    with pytest.raises(KeyError, match="unknown file path"):
        save_scan(
            scan_path=str(tmp_path),
            files=[make_file(known)],
            duplicate_result=duplicate_result,
            duration_seconds=2,
            database_path=str(test_database),
        )

    assert_failed_scan_without_data(test_database)


def test_save_scan_rolls_back_on_storage_failure(
    tmp_path,
    test_database,
    monkeypatch,
):
    """
    Verify rollback and failed status after a storage error.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized test database.
        monkeypatch (pytest.MonkeyPatch): Replaces hash storage.

    Returns:
        None: Assertions verify atomic database persistence.
    """
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"

    files = [
        make_file(first),
        make_file(second),
    ]

    duplicate_result = {
        "duplicate_groups": [
            {
                "hash": "a" * 64,
                "count": 2,
                "potential_savings": 10,
                "files": files,
            }
        ],
        "file_hashes": {
            str(first): "a" * 64,
            str(second): "a" * 64,
        },
    }

    def failing_save_file_hash(*args, **kwargs):
        """
        Simulate a failure while storing a file hash.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            None: This function always raises an exception.

        Raises:
            RuntimeError: Always raised for this test.
        """
        raise RuntimeError("Simulated hash storage failure")

    # Fail after file records have been inserted.
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
            scan_path=str(tmp_path),
            files=files,
            duplicate_result=duplicate_result,
            duration_seconds=4,
            database_path=str(test_database),
        )

    assert_failed_scan_without_data(test_database)

    connection = get_connection(test_database)

    try:
        scan = connection.execute(
            "SELECT * FROM Scans"
        ).fetchone()

        assert scan["scan_duration"] == 4

    finally:
        connection.close()
