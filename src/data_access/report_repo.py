
"""Read-only reporting queries for the Smart File Intelligence System."""

import sqlite3
from typing import NamedTuple

from src.data_access.connection import get_connection
from src.data_access.models import Scan


class CategoryStorage(NamedTuple):
    """Storage usage for one file category."""

    category: str
    file_count: int
    total_size: int


class StorageReport(NamedTuple):
    """Storage and duplicate statistics for a scan."""

    scan_id: int
    file_count: int
    total_size: int
    category_count: int
    duplicate_group_count: int
    duplicate_file_count: int
    potential_savings: int


def _validate_scan_id(scan_id: int) -> None:
    """
    Validate a scan identifier.

    Args:
        scan_id (int): Identifier to validate.

    Returns:
        None: The identifier is valid.

    Raises:
        ValueError: If scan_id is not a positive integer.
    """
    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")


def get_latest_completed_scan(
    database_path: str | None = None,
) -> Scan | None:
    """
    Return the latest successfully completed scan.

    Args:
        database_path (str | None): Optional SQLite database path.

    Returns:
        Scan | None: Latest completed scan, or None if none exists.

    Raises:
        sqlite3.Error: If the database query fails.
    """
    connection = (
        get_connection()
        if database_path is None
        else get_connection(database_path)
    )

    try:
        row = connection.execute(
            """
            SELECT
                scan_id,
                scan_path,
                scan_timestamp,
                scan_duration,
                file_count,
                total_size,
                status
            FROM Scans
            WHERE status = 'completed'
            ORDER BY scan_timestamp DESC, scan_id DESC
            LIMIT 1
            """
        ).fetchone()

        return None if row is None else Scan(**dict(row))

    finally:
        connection.close()


def get_storage_by_category(
    scan_id: int,
    database_path: str | None = None,
) -> list[CategoryStorage]:
    """
    Return file counts and storage totals grouped by category.

    Unknown file sizes contribute zero bytes but are still counted.

    Args:
        scan_id (int): Identifier of the scan.
        database_path (str | None): Optional SQLite database path.

    Returns:
        list[CategoryStorage]: Categories ordered by storage descending,
            then category name ascending. Empty if no files exist.

    Raises:
        ValueError: If scan_id is invalid.
        sqlite3.Error: If the database query fails.
    """
    _validate_scan_id(scan_id)

    connection = (
        get_connection()
        if database_path is None
        else get_connection(database_path)
    )

    try:
        rows = connection.execute(
            """
            SELECT
                category,
                COUNT(*) AS file_count,
                COALESCE(SUM(size), 0) AS total_size
            FROM Files
            WHERE scan_id = ?
            GROUP BY category
            ORDER BY total_size DESC, category ASC
            """,
            (scan_id,),
        ).fetchall()

        return [
            CategoryStorage(
                category=row["category"],
                file_count=row["file_count"],
                total_size=row["total_size"],
            )
            for row in rows
        ]

    finally:
        connection.close()


def get_storage_report(
    scan_id: int,
    database_path: str | None = None,
) -> StorageReport | None:
    """
    Return storage and duplicate statistics for one scan.

    File counts and sizes come from the Files table. Duplicate savings
    are summed once per duplicate group to avoid double-counting.

    Args:
        scan_id (int): Identifier of the scan.
        database_path (str | None): Optional SQLite database path.

    Returns:
        StorageReport | None: Scan statistics, or None if the scan
            does not exist.

    Raises:
        ValueError: If scan_id is invalid.
        sqlite3.Error: If the database query fails.
    """
    _validate_scan_id(scan_id)

    connection = (
        get_connection()
        if database_path is None
        else get_connection(database_path)
    )

    try:
        # Confirm the scan exists, even if it contains no files.
        scan = connection.execute(
            "SELECT scan_id FROM Scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

        if scan is None:
            return None

        # Calculate file statistics without joining duplicate tables.
        file_stats = connection.execute(
            """
            SELECT
                COUNT(*) AS file_count,
                COALESCE(SUM(size), 0) AS total_size,
                COUNT(DISTINCT category) AS category_count
            FROM Files
            WHERE scan_id = ?
            """,
            (scan_id,),
        ).fetchone()

        # Aggregate duplicate groups separately to avoid multiplying
        # savings by the number of duplicate members.
        duplicate_stats = connection.execute(
            """
            SELECT
                COUNT(*) AS duplicate_group_count,
                COALESCE(SUM(duplicate_count), 0)
                    AS duplicate_file_count,
                COALESCE(SUM(potential_savings), 0)
                    AS potential_savings
            FROM DuplicateGroups
            WHERE scan_id = ?
            """,
            (scan_id,),
        ).fetchone()

        return StorageReport(
            scan_id=scan_id,
            file_count=file_stats["file_count"],
            total_size=file_stats["total_size"],
            category_count=file_stats["category_count"],
            duplicate_group_count=duplicate_stats["duplicate_group_count"],
            duplicate_file_count=duplicate_stats["duplicate_file_count"],
            potential_savings=duplicate_stats["potential_savings"],
        )

    finally:
        connection.close()
