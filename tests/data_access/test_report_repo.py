
"""Tests for scan and storage reporting queries."""

import pytest

from src.data_access import report_repo, scan_repo
from src.data_access.connection import get_connection, initialize_database


@pytest.fixture
def report_database(tmp_path):
    """
    Create an isolated SQLite database for reporting tests.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Path: Path to the initialized SQLite database.

    Raises:
        sqlite3.Error: If database initialization fails.
    """
    database_path = tmp_path / "report_test.db"
    initialize_database(database_path)
    return database_path


def _insert_file(
    database_path,
    scan_id,
    path,
    category,
    size,
):
    """
    Insert a test file with the required metadata.

    Args:
        database_path: Path to the test database.
        scan_id (int): Owning scan identifier.
        path (str): File path.
        category (str): File category.
        size (int | None): File size in bytes.

    Returns:
        int: Identifier of the inserted file.

    Raises:
        sqlite3.Error: If insertion fails.
    """
    connection = get_connection(database_path)

    try:
        cursor = connection.execute(
            """
            INSERT INTO Files (
                scan_id, path, name, size, category, accessible
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                scan_id,
                path,
                path.rsplit("/", 1)[-1],
                size,
                category,
                1,
            ),
        )
        connection.commit()
        return cursor.lastrowid

    finally:
        connection.close()


def test_get_latest_completed_scan(report_database):
    """
    Verify that incomplete scans are ignored.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertions verify the selected scan.
    """
    first_id = scan_repo.create_scan(
        "/example/first",
        database_path=report_database,
    )
    second_id = scan_repo.create_scan(
        "/example/second",
        database_path=report_database,
    )
    third_id = scan_repo.create_scan(
        "/example/third",
        database_path=report_database,
    )

    # Complete the first two scans.
    scan_repo.update_scan(
        first_id,
        file_count=0,
        total_size=0,
        scan_duration=0,
        status="completed",
        database_path=report_database,
    )
    scan_repo.update_scan(
        second_id,
        file_count=0,
        total_size=0,
        scan_duration=0,
        status="completed",
        database_path=report_database,
    )

    # The third scan remains incomplete.
    latest = report_repo.get_latest_completed_scan(
        database_path=report_database,
    )

    assert latest is not None
    assert latest.scan_id == second_id
    assert latest.scan_path == "/example/second"
    assert latest.status == "completed"
    assert latest.scan_id != third_id


def test_latest_completed_scan_is_none_when_missing(report_database):
    """
    Verify that no completed scan returns None.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertion verifies the empty result.
    """
    scan_repo.create_scan(
        "/example/incomplete",
        database_path=report_database,
    )

    assert (
        report_repo.get_latest_completed_scan(
            database_path=report_database,
        )
        is None
    )


def test_latest_completed_scan_uses_timestamp_then_id(report_database):
    """
    Verify deterministic ordering by timestamp and scan ID.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertions verify ordering.
    """
    first_id = scan_repo.create_scan(
        "/example/first",
        database_path=report_database,
    )
    second_id = scan_repo.create_scan(
        "/example/second",
        database_path=report_database,
    )

    # Complete both scans using valid integer durations.
    for scan_id in (first_id, second_id):
        scan_repo.update_scan(
            scan_id,
            file_count=0,
            total_size=0,
            scan_duration=0,
            status="completed",
            database_path=report_database,
        )

    # Force identical timestamps to test the ID tie-breaker.
    connection = get_connection(report_database)

    try:
        connection.execute(
            """
            UPDATE Scans
            SET scan_timestamp = ?
            WHERE scan_id IN (?, ?)
            """,
            (
                "2026-01-01T12:00:00+00:00",
                first_id,
                second_id,
            ),
        )
        connection.commit()

    finally:
        connection.close()

    latest = report_repo.get_latest_completed_scan(
        database_path=report_database,
    )

    assert latest is not None
    assert latest.scan_id == second_id


def test_storage_by_category(report_database):
    """
    Verify file counts, storage totals, and ordering by category.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertions verify category statistics.
    """
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=report_database,
    )

    _insert_file(
        report_database,
        scan_id,
        "/example/a.jpg",
        "Images",
        300,
    )
    _insert_file(
        report_database,
        scan_id,
        "/example/b.jpg",
        "Images",
        200,
    )
    _insert_file(
        report_database,
        scan_id,
        "/example/c.pdf",
        "Documents",
        100,
    )
    _insert_file(
        report_database,
        scan_id,
        "/example/d.pdf",
        "Documents",
        None,
    )

    categories = report_repo.get_storage_by_category(
        scan_id,
        database_path=report_database,
    )

    assert len(categories) == 2

    assert categories[0] == report_repo.CategoryStorage(
        category="Images",
        file_count=2,
        total_size=500,
    )

    assert categories[1] == report_repo.CategoryStorage(
        category="Documents",
        file_count=2,
        total_size=100,
    )


def test_storage_by_category_empty_scan(report_database):
    """
    Verify that an empty scan has no category rows.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertion verifies the empty list.
    """
    scan_id = scan_repo.create_scan(
        "/empty",
        database_path=report_database,
    )

    assert report_repo.get_storage_by_category(
        scan_id,
        database_path=report_database,
    ) == []


def test_storage_report_with_duplicates(report_database):
    """
    Verify file totals and duplicate savings without double-counting.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertions verify the report values.
    """
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=report_database,
    )

    file_ids = [
        _insert_file(
            report_database,
            scan_id,
            f"/example/file{i}.txt",
            "Documents",
            100,
        )
        for i in range(3)
    ]

    connection = get_connection(report_database)

    try:
        # One group with three files and two redundant copies.
        cursor = connection.execute(
            """
            INSERT INTO DuplicateGroups (
                scan_id,
                hash_value,
                duplicate_count,
                potential_savings
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                scan_id,
                "example-hash",
                3,
                200,
            ),
        )

        group_id = cursor.lastrowid

        for index, file_id in enumerate(file_ids):
            connection.execute(
                """
                INSERT INTO DuplicateMembers (
                    group_id,
                    file_id,
                    is_primary
                )
                VALUES (?, ?, ?)
                """,
                (
                    group_id,
                    file_id,
                    int(index == 0),
                ),
            )

        connection.commit()

    finally:
        connection.close()

    report = report_repo.get_storage_report(
        scan_id,
        database_path=report_database,
    )

    assert report == report_repo.StorageReport(
        scan_id=scan_id,
        file_count=3,
        total_size=300,
        category_count=1,
        duplicate_group_count=1,
        duplicate_file_count=3,
        potential_savings=200,
    )


def test_storage_report_empty_scan(report_database):
    """
    Verify that an empty scan produces zero-valued statistics.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertions verify zero totals.
    """
    scan_id = scan_repo.create_scan(
        "/empty",
        database_path=report_database,
    )

    report = report_repo.get_storage_report(
        scan_id,
        database_path=report_database,
    )

    assert report is not None
    assert report.file_count == 0
    assert report.total_size == 0
    assert report.category_count == 0
    assert report.duplicate_group_count == 0
    assert report.duplicate_file_count == 0
    assert report.potential_savings == 0


def test_storage_report_nonexistent_scan(report_database):
    """
    Verify that a missing scan returns None.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertion verifies the missing result.
    """
    assert report_repo.get_storage_report(
        99999,
        database_path=report_database,
    ) is None


@pytest.mark.parametrize(
    "invalid_id",
    [0, -1, True, "1", None],
)
def test_reporting_rejects_invalid_scan_id(
    report_database,
    invalid_id,
):
    """
    Verify that reporting rejects invalid scan identifiers.

    Args:
        report_database: Initialized test database path.
        invalid_id: Invalid scan identifier to test.

    Returns:
        None: Assertions verify input validation.
    """
    with pytest.raises(ValueError):
        report_repo.get_storage_by_category(
            invalid_id,
            database_path=report_database,
        )

    with pytest.raises(ValueError):
        report_repo.get_storage_report(
            invalid_id,
            database_path=report_database,
        )


def test_storage_reports_are_scan_specific(report_database):
    """
    Verify that data from other scans is not included.

    Args:
        report_database: Initialized test database path.

    Returns:
        None: Assertions verify scan isolation.
    """
    first_id = scan_repo.create_scan(
        "/first",
        database_path=report_database,
    )
    second_id = scan_repo.create_scan(
        "/second",
        database_path=report_database,
    )

    _insert_file(
        report_database,
        first_id,
        "/first/a.txt",
        "Documents",
        50,
    )

    _insert_file(
        report_database,
        second_id,
        "/second/b.jpg",
        "Images",
        900,
    )

    report = report_repo.get_storage_report(
        first_id,
        database_path=report_database,
    )

    categories = report_repo.get_storage_by_category(
        first_id,
        database_path=report_database,
    )

    assert report is not None
    assert report.file_count == 1
    assert report.total_size == 50

    assert categories == [
        report_repo.CategoryStorage(
            "Documents",
            1,
            50,
        )
    ]
