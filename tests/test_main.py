
"""
Test the main application and its database integration.

These tests verify command-line application behavior using
isolated temporary SQLite databases.
"""

import sqlite3

from src.data_access.connection import get_connection
from src.main import display_report, run_application


def test_run_application_scans_directory(tmp_path, capsys):
    """
    Verify that the application scans files and displays a report.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        capsys (pytest.CaptureFixture): Captures terminal output.

    Returns:
        None: The test passes when the scan completes successfully.
    """

    # Create an isolated directory and database.
    scan_directory = tmp_path / "documents"
    scan_directory.mkdir()

    database_path = tmp_path / "application.db"

    # Create duplicate and unique files.
    (scan_directory / "first.txt").write_text("Same content")
    (scan_directory / "second.txt").write_text("Same content")
    (scan_directory / "unique.txt").write_text("Unique content")

    # Run the complete scan and reporting workflow.
    result = run_application(
        scan_path=str(scan_directory),
        database_path=str(database_path),
    )

    output = capsys.readouterr()

    assert result == 0
    assert "Scan completed successfully" in output.out
    assert "Total files: 3" in output.out
    assert "Duplicate groups: 1" in output.out
    assert "Potential savings:" in output.out

    # Verify that scan records were actually persisted.
    connection = get_connection(database_path)

    try:
        scan = connection.execute(
            "SELECT status, file_count FROM Scans"
        ).fetchone()

        assert scan is not None
        assert scan["status"] == "completed"
        assert scan["file_count"] == 3

    finally:
        connection.close()


def test_run_application_displays_latest_scan(tmp_path, capsys):
    """
    Verify that the latest completed scan can be displayed.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        capsys (pytest.CaptureFixture): Captures terminal output.

    Returns:
        None: The test passes when the latest report is displayed.
    """

    # Create a directory and database for the first scan.
    scan_directory = tmp_path / "documents"
    scan_directory.mkdir()

    database_path = tmp_path / "application.db"

    (scan_directory / "example.txt").write_text("Example content")

    # Create a completed scan.
    first_result = run_application(
        scan_path=str(scan_directory),
        database_path=str(database_path),
    )

    assert first_result == 0

    # Clear the first run's output.
    capsys.readouterr()

    # Display the latest scan without scanning again.
    second_result = run_application(
        database_path=str(database_path),
    )

    output = capsys.readouterr()

    assert second_result == 0
    assert "Smart File Intelligence Report" in output.out
    assert "Total files: 1" in output.out


def test_run_application_with_no_scans(tmp_path, capsys):
    """
    Verify that an empty database is handled gracefully.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        capsys (pytest.CaptureFixture): Captures terminal output.

    Returns:
        None: The test passes when no scan is available.
    """

    database_path = tmp_path / "empty.db"

    # Request the latest report from a new database.
    result = run_application(
        database_path=str(database_path),
    )

    output = capsys.readouterr()

    assert result == 0
    assert "No completed scans found." in output.out


def test_run_application_rejects_missing_directory(tmp_path, capsys):
    """
    Verify that invalid scan directories produce an error.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        capsys (pytest.CaptureFixture): Captures terminal output.

    Returns:
        None: The test passes when the application returns an error.
    """

    database_path = tmp_path / "application.db"
    missing_directory = tmp_path / "missing"

    # Attempt to scan a directory that does not exist.
    result = run_application(
        scan_path=str(missing_directory),
        database_path=str(database_path),
    )

    output = capsys.readouterr()

    assert result == 1
    assert "Error:" in output.err


def test_display_report_missing_scan(tmp_path, capsys):
    """
    Verify that requesting a missing report displays a message.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        capsys (pytest.CaptureFixture): Captures terminal output.

    Returns:
        None: The test passes when the missing report is handled.
    """

    from src.data_access.connection import initialize_database

    database_path = tmp_path / "application.db"

    # Initialize an empty database.
    initialize_database(database_path)

    # Request a scan report that does not exist.
    display_report(
        scan_id=999,
        database_path=str(database_path),
    )

    output = capsys.readouterr()

    assert "No report found for scan 999." in output.out


def test_run_application_handles_database_error(
    tmp_path,
    capsys,
    monkeypatch,
):
    """
    Verify that database failures produce a nonzero exit code.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        capsys (pytest.CaptureFixture): Captures terminal output.
        monkeypatch (pytest.MonkeyPatch): Replaces database initialization.

    Returns:
        None: The test passes when the failure is reported.
    """

    import src.main as main_module

    # Simulate a database initialization failure.
    def failing_initialize_database(database_path):
        """
        Simulate a database initialization error.

        Args:
            database_path (str | None): Database path supplied by the app.

        Returns:
            None: This function always raises an error.

        Raises:
            sqlite3.OperationalError: Always raised for this test.
        """
        raise sqlite3.OperationalError("Simulated database failure")

    monkeypatch.setattr(
        main_module,
        "initialize_database",
        failing_initialize_database,
    )

    result = run_application(
        database_path=str(tmp_path / "application.db"),
    )

    output = capsys.readouterr()

    assert result == 1
    assert "Simulated database failure" in output.err
