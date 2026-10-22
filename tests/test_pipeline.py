
"""
Test the complete scanner-to-database integration pipeline.

These tests verify that the scanner output passes through
duplicate detection, database persistence, and reporting.
"""

import pytest

from src.data_access.connection import (
    get_connection,
    initialize_database,
)
from src.main import run_application


@pytest.fixture
def test_database(tmp_path):
    """
    Create a fresh SQLite database for each pipeline test.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.

    Returns:
        Path: Path to the initialized test database.
    """
    database_path = tmp_path / "pipeline.db"
    initialize_database(database_path)
    return database_path


def test_pipeline_saves_files_and_duplicates(
    tmp_path,
    test_database,
    capsys,
):
    """
    Verify scanning, duplicate detection, persistence, and reporting.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized SQLite database.
        capsys (pytest.CaptureFixture): Captures terminal output.

    Returns:
        None: Assertions verify the complete pipeline.
    """
    scan_directory = tmp_path / "documents"
    scan_directory.mkdir()

    # Create two duplicate files and one unique file.
    first = scan_directory / "first.txt"
    second = scan_directory / "second.txt"
    unique = scan_directory / "unique.txt"

    first.write_text("Identical content")
    second.write_text("Identical content")
    unique.write_text("Different content")

    # Run the real scanner, duplicate detector, and database layer.
    result = run_application(
        scan_path=str(scan_directory),
        database_path=str(test_database),
    )

    assert result == 0

    output = capsys.readouterr().out

    assert "Scan completed successfully" in output
    assert "Smart File Intelligence Report" in output

    connection = get_connection(test_database)

    try:
        # Verify the scan completed with the expected statistics.
        scan = connection.execute(
            "SELECT * FROM Scans"
        ).fetchone()

        assert scan is not None
        assert scan["status"] == "completed"
        assert scan["file_count"] == 3
        assert scan["total_size"] == sum(
            path.stat().st_size
            for path in (first, second, unique)
        )
        assert isinstance(scan["scan_duration"], int)
        assert scan["scan_duration"] >= 0

        # Verify all scanned files were saved.
        files = connection.execute(
            "SELECT * FROM Files WHERE scan_id = ?",
            (scan["scan_id"],),
        ).fetchall()

        assert len(files) == 3

        # Verify duplicate detection produced one group.
        groups = connection.execute(
            "SELECT * FROM DuplicateGroups WHERE scan_id = ?",
            (scan["scan_id"],),
        ).fetchall()

        assert len(groups) == 1
        assert groups[0]["duplicate_count"] == 2
        assert groups[0]["potential_savings"] == first.stat().st_size

        # Verify that the first sorted path is the primary member.
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

        # Verify that duplicate candidates have saved hashes.
        hashes = connection.execute(
            """
            SELECT fh.hash_algorithm
            FROM FileHashes AS fh
            JOIN Files AS f ON f.file_id = fh.file_id
            WHERE f.scan_id = ?
            """,
            (scan["scan_id"],),
        ).fetchall()

        assert len(hashes) == 3
        assert all(
            row["hash_algorithm"] == "sha256"
            for row in hashes
        )

    finally:
        connection.close()


def test_pipeline_handles_empty_directory(
    tmp_path,
    test_database,
):
    """
    Verify that scanning an empty directory completes successfully.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized SQLite database.

    Returns:
        None: Assertions verify zero file counts and storage.
    """
    empty_directory = tmp_path / "empty"
    empty_directory.mkdir()

    result = run_application(
        scan_path=str(empty_directory),
        database_path=str(test_database),
    )

    assert result == 0

    connection = get_connection(test_database)

    try:
        scan = connection.execute(
            "SELECT * FROM Scans"
        ).fetchone()

        assert scan is not None
        assert scan["status"] == "completed"
        assert scan["file_count"] == 0
        assert scan["total_size"] == 0

    finally:
        connection.close()


def test_pipeline_reports_latest_completed_scan(
    tmp_path,
    test_database,
    capsys,
):
    """
    Verify that an existing scan can be reported without rescanning.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        test_database (Path): Initialized SQLite database.
        capsys (pytest.CaptureFixture): Captures terminal output.

    Returns:
        None: Assertions verify the existing report is displayed.
    """
    scan_directory = tmp_path / "documents"
    scan_directory.mkdir()

    (scan_directory / "example.txt").write_text("Example content")

    # Create the first completed scan.
    assert run_application(
        scan_path=str(scan_directory),
        database_path=str(test_database),
    ) == 0

    capsys.readouterr()

    # Omit the path to request the latest completed report.
    result = run_application(
        database_path=str(test_database),
    )

    assert result == 0

    output = capsys.readouterr().out

    assert "Smart File Intelligence Report" in output
    assert "Total files: 1" in output

    connection = get_connection(test_database)

    try:
        # Reporting an existing scan must not create a new scan.
        count = connection.execute(
            "SELECT COUNT(*) FROM Scans"
        ).fetchone()[0]

        assert count == 1

    finally:
        connection.close()
