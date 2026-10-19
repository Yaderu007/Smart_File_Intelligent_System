
"""Test the scanner, SQLite repositories, and analysis functions together."""

from src.scanner import scan_directory
from src.data_access.scan_repo import save_scan_results
from src.data_access.file_repo import get_files_by_scan
from src.data_access.connection import initialize_database
from src.interface.cli_report import (
    calc_tot_storage,
    calc_avg_size,
    get_category_stats,
    get_largest_files,
)


def main() -> None:
    """Scan test files, save them, retrieve them, and check the statistics."""
    initialize_database()

    # scan_directory yields one dictionary per discovered file.
    file_data = list(scan_directory("test_data"))

    # Save the scanner dictionaries and receive the database scan ID.
    scan_id = save_scan_results("test_data", file_data)
    print(f"Scan ID: {scan_id}")

    # Retrieve FileMetadata objects from SQLite.
    files = get_files_by_scan(scan_id)
    print(f"Files retrieved: {len(files)}")

    # Calculate statistics from actual database records.
    print(f"Total storage: {calc_tot_storage(files)} bytes")
    print(f"Average size: {calc_avg_size(files):.2f} bytes")
    print(f"Category statistics: {get_category_stats(files)}")

    print("Largest files:")
    for file in get_largest_files(files, 3):
        print(f"  {file.name}: {file.size} bytes")


if __name__ == "__main__":
    main()
