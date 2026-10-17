
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

    return database_path


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
