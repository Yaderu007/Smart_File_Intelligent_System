
import sqlite3
from datetime import datetime, timezone

from .connection import get_connection
from .models import Scan


def create_scan(scan_path: str) -> int:
    """
    Create a new scan record and return its generated ID.
    """

    # Validate the directory path before saving it.
    if not isinstance(scan_path, str):
        raise TypeError("scan_path must be a string.")

    if not scan_path.strip():
        raise ValueError("scan_path cannot be empty.")

    # Store the scan's starting time in UTC.
    scan_timestamp = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        # SQLite automatically generates the scan_id.
        cursor = connection.execute(
            """
            INSERT INTO Scans (scan_path, scan_timestamp)
            VALUES (?, ?)
            """,
            (scan_path, scan_timestamp)
        )

        scan_id = cursor.lastrowid

        if scan_id is None:
            raise sqlite3.DatabaseError("Failed to retrieve the new scan ID.")

        connection.commit()
        return scan_id

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def update_scan(
    scan_id: int,
    file_count: int,
    total_size: int,
    scan_duration: int,
    status: str
) -> None:
    """
    Update an existing scan with its statistics and status.
    """

    # Reject invalid IDs and negative statistics.
    if type(scan_id) is not int:
        raise TypeError("scan_id must be an integer.")

    if scan_id <= 0:
        raise ValueError("scan_id must be positive.")

    for name, value in {
        "file_count": file_count,
        "total_size": total_size,
        "scan_duration": scan_duration
    }.items():
        if type(value) is not int:
            raise TypeError(f"{name} must be an integer.")

        if value < 0:
            raise ValueError(f"{name} cannot be negative.")

    if not isinstance(status, str):
        raise TypeError("status must be a string.")

    if status not in {"incomplete", "completed", "failed"}:
        raise ValueError("Invalid scan status.")

    connection = get_connection()

    try:
        # Update only the scan matching the supplied scan_id.
        cursor = connection.execute(
            """
            UPDATE Scans
            SET file_count = ?,
                total_size = ?,
                scan_duration = ?,
                status = ?
            WHERE scan_id = ?
            """,
            (file_count, total_size, scan_duration, status, scan_id)
        )

        if cursor.rowcount == 0:
            raise LookupError(f"Scan with ID {scan_id} does not exist.")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_scan(scan_id: int) -> Scan | None:
    """
    Retrieve a scan by ID.

    Returns a Scan object, or None if the scan does not exist.
    """

    if type(scan_id) is not int:
        raise TypeError("scan_id must be an integer.")

    if scan_id <= 0:
        raise ValueError("scan_id must be positive.")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM Scans
            WHERE scan_id = ?
            """,
            (scan_id,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        # Convert the SQLite row into our Scan dataclass.
        return Scan(**dict(row))

    finally:
        connection.close()


def list_scans() -> list[Scan]:
    """
    Retrieve all scans, ordered from newest to oldest.

    Returns an empty list if no scans exist.
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM Scans
            ORDER BY scan_timestamp DESC, scan_id DESC
            """
        )

        # Convert every database row into a Scan object.
        return [Scan(**dict(row)) for row in cursor.fetchall()]

    finally:
        connection.close()
