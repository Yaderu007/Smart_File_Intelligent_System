
"""
Command-line application for the Smart File Intelligence System.

This module connects directory scanning, SQLite storage, and
read-only reporting through a simple command-line interface.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from src.data_access.connection import initialize_database
from src.data_access.scanner_service import save_scan
from src.data_access.report_repo import (
    get_latest_completed_scan,
    get_storage_by_category,
    get_storage_report,
)


def display_report(
    scan_id: int,
    database_path: str | None = None,
) -> None:
    """
    Display storage statistics for a completed scan.

    Args:
        scan_id (int): Identifier of the scan to display.
        database_path (str | None): Optional SQLite database path.

    Returns:
        None: Prints the scan report to the terminal.

    Raises:
        ValueError: If scan_id is invalid.
        sqlite3.Error: If a database query fails.
    """

    # Retrieve the summary for the requested scan.
    report = get_storage_report(
        scan_id=scan_id,
        database_path=database_path,
    )

    if report is None:
        print(f"No report found for scan {scan_id}.")
        return

    # Display the overall storage statistics.
    print("\n=== Smart File Intelligence Report ===")
    print(f"Scan ID: {report.scan_id}")
    print(f"Total files: {report.file_count}")
    print(f"Total storage: {report.total_size} bytes")
    print(f"Categories: {report.category_count}")
    print(f"Duplicate groups: {report.duplicate_group_count}")
    print(f"Duplicate files: {report.duplicate_file_count}")
    print(f"Potential savings: {report.potential_savings} bytes")

    # Retrieve and display category-level storage usage.
    categories = get_storage_by_category(
        scan_id=scan_id,
        database_path=database_path,
    )

    print("\n--- Storage by Category ---")

    if not categories:
        print("No files found.")
    else:
        for category in categories:
            print(
                f"{category.category}: "
                f"{category.file_count} files, "
                f"{category.total_size} bytes"
            )


def run_application(
    scan_path: str | None = None,
    database_path: str | None = None,
) -> int:
    """
    Initialize storage, scan a directory, and display its report.

    When no directory is provided, display the latest completed
    scan report instead.

    Args:
        scan_path (str | None): Directory to scan, or None to show
            the latest completed scan.
        database_path (str | None): Optional SQLite database path.

    Returns:
        int: Zero on success, or one if an operation fails.
    """

    try:
        # Ensure the SQLite database schema is initialized.
        initialize_database(database_path)

        if scan_path is not None:
            # Scan the requested directory and save its results.
            scan_id = save_scan(
                scan_path=scan_path,
                database_path=database_path,
            )

            print(f"Scan completed successfully. Scan ID: {scan_id}")

        else:
            # Load the most recent completed scan.
            latest_scan = get_latest_completed_scan(
                database_path=database_path,
            )

            if latest_scan is None:
                print("No completed scans found.")
                return 0

            scan_id = latest_scan.scan_id

        # Display the report for the selected scan.
        display_report(
            scan_id=scan_id,
            database_path=database_path,
        )

        return 0

    except (TypeError, ValueError, KeyError, sqlite3.Error, OSError) as error:
        # Report expected input and database failures.
        print(f"Error: {error}", file=sys.stderr)
        return 1

    except Exception as error:
        # Report unexpected scanner or integration failures.
        print(f"Unexpected error: {error}", file=sys.stderr)
        return 1


def main() -> int:
    """
    Parse command-line arguments and start the application.

    Returns:
        int: Application exit code.
    """

    # Configure the command-line interface.
    parser = argparse.ArgumentParser(
        description="Scan directories and report file storage statistics."
    )

    parser.add_argument(
        "scan_path",
        nargs="?",
        default=None,
        help="Directory to scan. Omit to show the latest completed scan.",
    )

    parser.add_argument(
        "--database",
        default=None,
        help="Optional path to the SQLite database.",
    )

    args = parser.parse_args()

    # Start the application with the supplied arguments.
    return run_application(
        scan_path=args.scan_path,
        database_path=args.database,
    )


if __name__ == "__main__":
    sys.exit(main())
