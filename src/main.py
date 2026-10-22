
"""
Command-line entry point for the Smart File Intelligence System.

Coordinates scanning, duplicate detection, database persistence,
and storage reporting.
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # Allow running from the project root.

from src.scanner import scan_directory, detect_duplicates
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
    Print the storage report for a scan.

    Args:
        scan_id (int): ID of the scan to display.
        database_path (str | None): Optional SQLite database path.

    Returns:
        None: Prints the report to the terminal.

    Raises:
        ValueError: If the scan ID is invalid.
        sqlite3.Error: If a reporting query fails.
    """
    report = get_storage_report(
        scan_id=scan_id,
        database_path=database_path,
    )

    if report is None:
        print(f"No report found for scan {scan_id}.")
        return

    print("\n=== Smart File Intelligence Report ===")
    print(f"Scan ID: {report.scan_id}")
    print(f"Total files: {report.file_count}")
    print(f"Total storage: {report.total_size} bytes")
    print(f"Categories: {report.category_count}")
    print(f"Duplicate groups: {report.duplicate_group_count}")
    print(f"Duplicate files: {report.duplicate_file_count}")
    print(f"Potential savings: {report.potential_savings} bytes")

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
    Run a scan or display the latest completed scan.

    Args:
        scan_path (str | None): Directory to scan, or None to
            display the latest completed scan.
        database_path (str | None): Optional SQLite database path.

    Returns:
        int: Zero on success and one on failure.
    """
    try:
        # Ensure database tables exist before saving scan results.
        initialize_database(database_path)

        if scan_path is not None:
            # Measure traversal and duplicate detection only.
            start_time = time.perf_counter()

            files = list(scan_directory(scan_path))
            duplicate_result = detect_duplicates(files)

            duration_seconds = round(
                time.perf_counter() - start_time
            )

            # Save the already collected scanner results.
            scan_id = save_scan(
                scan_path=scan_path,
                files=files,
                duplicate_result=duplicate_result,
                duration_seconds=duration_seconds,
                database_path=database_path,
            )

            print(f"Scan completed successfully. Scan ID: {scan_id}")

        else:
            # Display the latest completed scan without rescanning.
            latest_scan = get_latest_completed_scan(
                database_path=database_path,
            )

            if latest_scan is None:
                print("No completed scans found.")
                return 0

            scan_id = latest_scan.scan_id

        display_report(
            scan_id=scan_id,
            database_path=database_path,
        )

        return 0

    except Exception as error:
        # Report failures without displaying a Python traceback.
        print(f"Error: {error}", file=sys.stderr)
        return 1


def main() -> int:
    """
    Parse command-line arguments and run the application.

    Returns:
        int: Application exit code.
    """
    parser = argparse.ArgumentParser(
        description="Scan directories and report storage statistics."
    )

    parser.add_argument(
        "scan_path",
        nargs="?",
        default=None,
        help="Directory to scan; omit to show the latest report.",
    )

    parser.add_argument(
        "--database",
        default=None,
        help="Optional SQLite database path.",
    )

    args = parser.parse_args()

    return run_application(
        scan_path=args.scan_path,
        database_path=args.database,
    )


if __name__ == "__main__":
    sys.exit(main())
