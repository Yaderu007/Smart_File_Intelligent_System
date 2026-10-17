from src.data_access import file_repo
import pytest

from src.data_access import scan_repo
from src.data_access.connection import (
    get_connection,
    initialize_database,
)
from src.data_access.models import Scan


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    """
    Create an isolated SQLite database for repository tests.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        monkeypatch (pytest.MonkeyPatch): Fixture for replacing
            the repository's database connection function.

    Returns:
        Path: Path to the initialized temporary database.
    """

    # Create a fresh database for this test.
    database_path = tmp_path / "test_scans.db"

    # Create all required tables using schema.sql.
    initialize_database(database_path)

    # Save the original connection function before replacing it.
    original_get_connection = get_connection

    # Redirect repository connections to our temporary database.
    # This avoids changing the real smart_files.db.
    monkeypatch.setattr(
        scan_repo,
        "get_connection",
        lambda: original_get_connection(database_path),
    )

    monkeypatch.setattr(
        file_repo,
        "get_connection",
        lambda: original_get_connection(database_path),
    )

    return database_path

def make_file_metadata(path: str, size: int = 100, accessible: bool = True) -> dict:
    """
    Build a scanner-style metadata dictionary for repository tests.

    Args:
        path (str): Full path of the sample file.
        size (int): File size in bytes.
        accessible (bool): Whether the file was successfully accessed.

    Returns:
        dict: File metadata compatible with save_files_batch().
    """
    from pathlib import Path

    file_path = Path(path)

    return {
        "path": path,
        "name": file_path.name,
        "size": size,
        "extension": file_path.suffix,
        "category": "Documents",
        "created": None,
        "modified": None,
        "accessed_timestamp": None,
        "accessible": accessible,
        "error": None if accessible else "Permission denied",
    }


def test_create_scan(test_database):
    """
    Verify that create_scan inserts a new scan successfully.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes if a valid scan is created.
    """

    # Create a new scanning session.
    scan_id = scan_repo.create_scan("/example/documents")

    # SQLite should generate a positive scan ID.
    assert isinstance(scan_id, int)
    assert scan_id > 0

    # Retrieve the scan to confirm it was saved.
    scan = scan_repo.get_scan(scan_id)

    assert scan is not None
    assert scan.scan_path == "/example/documents"
    assert scan.status == "incomplete"
    assert scan.file_count == 0
    assert scan.total_size == 0


def test_get_scan_returns_dataclass(test_database):
    """
    Verify that get_scan returns a Scan dataclass.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes if the returned object is correct.
    """

    scan_id = scan_repo.create_scan("/example/photos")

    scan = scan_repo.get_scan(scan_id)

    # Repository functions should return dataclasses,
    # rather than raw SQLite rows or dictionaries.
    assert isinstance(scan, Scan)

    assert scan.scan_id == scan_id
    assert scan.scan_path == "/example/photos"
    assert isinstance(scan.scan_timestamp, str)


def test_update_scan(test_database):
    """
    Verify that scan statistics can be updated.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes if all updated values match.
    """

    scan_id = scan_repo.create_scan("/example/documents")

    # Simulate a completed directory scan.
    scan_repo.update_scan(
        scan_id=scan_id,
        file_count=12,
        total_size=4096,
        scan_duration=3,
        status="completed",
    )

    # Retrieve the updated record.
    scan = scan_repo.get_scan(scan_id)

    assert scan.file_count == 12
    assert scan.total_size == 4096
    assert scan.scan_duration == 3
    assert scan.status == "completed"


def test_list_scans(test_database):
    """
    Verify that list_scans returns all saved scanning sessions.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes if both scans are returned.
    """

    first_id = scan_repo.create_scan("/example/first")
    second_id = scan_repo.create_scan("/example/second")

    scans = scan_repo.list_scans()

    assert len(scans) == 2
    assert all(isinstance(scan, Scan) for scan in scans)

    # Compare IDs without relying on timestamp ordering.
    returned_ids = {scan.scan_id for scan in scans}

    assert returned_ids == {first_id, second_id}


def test_get_nonexistent_scan(test_database):
    """
    Verify that requesting an unknown scan returns None.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes if no scan is returned.
    """

    result = scan_repo.get_scan(999)

    assert result is None


@pytest.mark.parametrize(
    "invalid_path",
    ["", "   ", None, 123],
)
def test_create_scan_rejects_invalid_paths(
    test_database,
    invalid_path,
):
    """
    Verify that create_scan rejects invalid directory paths.

    Args:
        test_database (Path): Initialized temporary database.
        invalid_path: Invalid path value being tested.

    Returns:
        None: The test passes if an appropriate error is raised.
    """

    # Both TypeError and ValueError are expected for
    # different invalid inputs.
    with pytest.raises((TypeError, ValueError)):
        scan_repo.create_scan(invalid_path)


def test_update_nonexistent_scan(test_database):
    """
    Verify that updating a nonexistent scan raises LookupError.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes if LookupError is raised.
    """

    with pytest.raises(LookupError):
        scan_repo.update_scan(
            scan_id=999,
            file_count=5,
            total_size=1024,
            scan_duration=2,
            status="completed",
        )


def test_update_scan_rejects_invalid_status(test_database):
    """
    Verify that unsupported scan statuses are rejected.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes if ValueError is raised.
    """

    scan_id = scan_repo.create_scan("/example/documents")

    with pytest.raises(ValueError):
        scan_repo.update_scan(
            scan_id=scan_id,
            file_count=5,
            total_size=1024,
            scan_duration=2,
            status="unknown",
        )



def test_save_scan_results_success(test_database):
    """
    Verify that accessible files are saved and the scan completes.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when scan statistics and saved
            metadata match the input files.
    """
    files = [
        make_file_metadata("/example/a.pdf", size=100),
        make_file_metadata("/example/b.txt", size=200),
    ]

    scan_id = scan_repo.save_scan_results("/example", files)

    scan = scan_repo.get_scan(scan_id)

    assert scan is not None
    assert scan.status == "completed"
    assert scan.file_count == 2
    assert scan.total_size == 300

    # Verify that the metadata was actually inserted.
    connection = get_connection(test_database)

    try:
        rows = connection.execute(
            "SELECT path FROM Files WHERE scan_id = ? ORDER BY file_id",
            (scan_id,),
        ).fetchall()

        assert [row["path"] for row in rows] == [
            "/example/a.pdf",
            "/example/b.txt",
        ]

    finally:
        connection.close()


def test_save_scan_results_skips_inaccessible_files(test_database):
    """
    Verify that inaccessible files are excluded from the database.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when only accessible files are saved.
    """
    files = [
        make_file_metadata("/example/a.pdf", size=100),
        make_file_metadata(
            "/example/secret.pdf",
            size=200,
            accessible=False,
        ),
        make_file_metadata("/example/c.pdf", size=300),
    ]

    scan_id = scan_repo.save_scan_results("/example", files)

    scan = scan_repo.get_scan(scan_id)

    assert scan.status == "completed"
    assert scan.file_count == 2
    assert scan.total_size == 400

    connection = get_connection(test_database)

    try:
        rows = connection.execute(
            "SELECT path FROM Files WHERE scan_id = ?",
            (scan_id,),
        ).fetchall()

        saved_paths = {row["path"] for row in rows}

        assert saved_paths == {
            "/example/a.pdf",
            "/example/c.pdf",
        }

        assert "/example/secret.pdf" not in saved_paths

    finally:
        connection.close()


def test_save_scan_results_rolls_back_failed_batch(test_database):
    """
    Verify that a failed insertion rolls back the entire file batch.

    A duplicate path violates the Files table's unique constraint.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when no files are saved and
            the scan is marked failed.
    """
    import sqlite3

    files = [
        make_file_metadata("/example/a.pdf", size=100),
        make_file_metadata("/example/a.pdf", size=200),
    ]

    with pytest.raises(sqlite3.IntegrityError):
        scan_repo.save_scan_results("/example", files)

    connection = get_connection(test_database)

    try:
        # The scan record survives, but the failed batch does not.
        scan_row = connection.execute(
            "SELECT scan_id, status FROM Scans"
        ).fetchone()

        assert scan_row is not None
        assert scan_row["status"] == "failed"

        count = connection.execute(
            "SELECT COUNT(*) FROM Files"
        ).fetchone()[0]

        assert count == 0

    finally:
        connection.close()


def test_save_scan_results_with_no_files(test_database):
    """
    Verify that an empty scan can finish successfully.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when statistics remain zero.
    """
    scan_id = scan_repo.save_scan_results("/empty", [])

    scan = scan_repo.get_scan(scan_id)

    assert scan.status == "completed"
    assert scan.file_count == 0
    assert scan.total_size == 0


def test_save_scan_results_rejects_invalid_metadata(test_database):
    """
    Verify that invalid metadata causes a failed scan.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when the invalid item is rejected
            and the scan is marked failed.
    """
    files = [
        make_file_metadata("/example/a.pdf"),
        "not a dictionary",
    ]

    with pytest.raises(TypeError):
        scan_repo.save_scan_results("/example", files)

    connection = get_connection(test_database)

    try:
        scan_row = connection.execute(
            "SELECT status FROM Scans"
        ).fetchone()

        assert scan_row is not None
        assert scan_row["status"] == "failed"

        # Validation happens before batch insertion.
        count = connection.execute(
            "SELECT COUNT(*) FROM Files"
        ).fetchone()[0]

        assert count == 0

    finally:
        connection.close()


def test_update_scan_can_mark_failed(test_database):
    """
    Verify that an existing scan can be marked failed.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when the status is updated.
    """
    scan_id = scan_repo.create_scan("/example")

    scan_repo.update_scan(
        scan_id=scan_id,
        file_count=0,
        total_size=0,
        scan_duration=2,
        status="failed",
    )

    scan = scan_repo.get_scan(scan_id)

    assert scan.status == "failed"
