"""
main.py — Entry point for the Smart File Intelligence System.
Implements contract C6: scan -> detect_duplicates -> save_scan.
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scanner import scan_directory, detect_duplicates
from src.data_access.connection import initialize_database
from src.data_access.scan_repo import save_scan, get_scan
from src.data_access.report_repo import get_storage_report, get_storage_by_category
from src.data_access.file_repo import get_largest_files


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan a directory for storage usage and duplicate files."
    )
    parser.add_argument("path", help="Directory to scan")
    parser.add_argument("--db", default=None, help="Optional path to the database file")
    return parser.parse_args()


def run_pipeline(path: str, database_path=None) -> int:
    """The actual contract C6 sequence, nothing more."""
    initialize_database(database_path)

    start = time.monotonic()
    files = list(scan_directory(path))
    result = detect_duplicates(files)
    duration_seconds = int(time.monotonic() - start)

    return save_scan(path, files, result, duration_seconds, database_path)


def print_summary(scan_id: int, database_path=None):
    scan = get_scan(scan_id, database_path=database_path)
    report = get_storage_report(scan_id, database_path=database_path)
    categories = get_storage_by_category(scan_id, database_path=database_path)
    largest = get_largest_files(scan_id, limit=5, database_path=database_path)

    print(f"\n--- Scan {scan_id} ({scan.status}) ---")
    print(f"Files scanned:     {report['file_count']}")
    print(f"Total storage:     {report['total_size']:,} bytes")
    print(f"Duplicate groups:  {report['duplicate_groups']}")
    print(f"Potential savings: {report['potential_savings']:,} bytes")

    print("\nStorage by category:")
    for c in categories:
        print(f"  {c.category:<12} {c.file_count:>5} files   {c.total_size:>12,} bytes")

    print("\nLargest files:")
    for f in largest:
        print(f"  {f.size:>12,} bytes   {f.path}")


def main():
    args = parse_args()
    try:
        scan_id = run_pipeline(args.path, args.db)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print_summary(scan_id, args.db)


if __name__ == "__main__":
    main()