
"""
Repository functions for creating, updating, and retrieving scans.

Also coordinates saving scan results as a single transaction.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from time import monotonic

from .connection import get_connection
from .models import Scan
from .file_repo import save_files_batch


logger = logging.getLogger(__name__)



def create_scan(
    scan_path: str,
    connection: sqlite3.Connection | None = None,
    database_path: str | None = None
) -> int:
    """
    Create a new directory scan record.

    If a connection is supplied, the caller manages its transaction.
    Otherwise, this function commits and closes its own connection.

    Args:
        scan_path (str): Directory being scanned.
        connection (sqlite3.Connection | None): Optional existing
            SQLite connection.
        database_path (str | None): Optional SQLite database path.
            Defaults to the project's database.

    Returns:
        int: The generated scan ID.

    Raises:
        TypeError: If scan_path is not a string.
        ValueError: If scan_path is empty.
        sqlite3.Error: If the database operation fails.
    """

    if not isinstance(scan_path, str):
        raise TypeError("scan_path must be a string.")

    if not scan_path.strip():
        raise ValueError("scan_path cannot be empty.")

    # Record when this scan was created, using UTC.
    scan_timestamp = datetime.now(timezone.utc).isoformat()

    # Only the function that creates a connection should close it.
    owns_connection = connection is None

    # Use the requested database only when a path was supplied.
    if owns_connection:
        conn = (
            get_connection()
            if database_path is None
            else get_connection(database_path)
        )
    else:
        conn = connection

    try:
        cursor = conn.execute(
            """
            INSERT INTO Scans (scan_path, scan_timestamp)
            VALUES (?, ?)
            """,
            (scan_path, scan_timestamp)
        )

        scan_id = cursor.lastrowid

        if scan_id is None:
            raise sqlite3.DatabaseError(
                "Failed to retrieve the new scan ID."
            )

        # Do not commit another function's transaction.
        if owns_connection:
            conn.commit()

        return scan_id

    except sqlite3.Error:
        if owns_connection:
            conn.rollback()
        raise

    finally:
        if owns_connection:
            conn.close()


def update_scan(
    scan_id: int,
    file_count: int,
    total_size: int,
    scan_duration: int | None,
    status: str,
    connection: sqlite3.Connection | None = None,
    database_path: str | None = None
) -> None:
    """
    Update an existing scan's statistics and status.

    A scan can be marked as incomplete, completed, or failed.
    The scan duration may be None if the scanner did not provide it.

    When an existing connection is provided, the caller manages
    committing, rolling back, and closing the connection.

    Args:
        scan_id (int): Unique ID of the scan to update.
        file_count (int): Number of files discovered during the scan.
        total_size (int): Total size of discovered files in bytes.
        scan_duration (int | None): Scan duration in whole seconds,
            or None if the duration is unknown.
        status (str): Scan status: incomplete, completed, or failed.
        connection (sqlite3.Connection | None): Optional existing
            SQLite connection for a shared transaction.
        database_path (str | None): Optional SQLite database path.
            Used only when no connection is supplied.

    Returns:
        None: The scan record is updated successfully.

    Raises:
        TypeError: If an argument has an invalid type.
        ValueError: If a numeric value is negative, scan_id is invalid,
            or the status is not supported.
        LookupError: If the specified scan does not exist.
        sqlite3.Error: If a database operation fails.
    """

    # Validate the scan ID.
    if type(scan_id) is not int:
        raise TypeError("scan_id must be an integer.")

    if scan_id <= 0:
        raise ValueError("scan_id must be positive.")

    # Validate file count and total size.
    for name, value in {
        "file_count": file_count,
        "total_size": total_size
    }.items():

        if type(value) is not int:
            raise TypeError(f"{name} must be an integer.")

        if value < 0:
            raise ValueError(f"{name} cannot be negative.")

    # Allow None when the scanner does not provide a duration.
    if scan_duration is not None:

        if type(scan_duration) is not int:
            raise TypeError("scan_duration must be an integer or None.")

        if scan_duration < 0:
            raise ValueError("scan_duration cannot be negative.")

    # Validate the scan status.
    if not isinstance(status, str):
        raise TypeError("status must be a string.")

    if status not in {"incomplete", "completed", "failed"}:
        raise ValueError("Invalid scan status.")

    # Only the function that creates a connection should close it.
    owns_connection = connection is None

    # Reuse a supplied connection or open the requested database.
    if owns_connection:
        conn = (
            get_connection()
            if database_path is None
            else get_connection(database_path)
        )
    else:
        conn = connection

    try:
        # Update the scan statistics and status.
        cursor = conn.execute(
            """
            UPDATE Scans
            SET file_count = ?,
                total_size = ?,
                scan_duration = ?,
                status = ?
            WHERE scan_id = ?
            """,
            (
                file_count,
                total_size,
                scan_duration,
                status,
                scan_id
            )
        )

        # Raise an error if the scan ID does not exist.
        if cursor.rowcount == 0:
            raise LookupError(
                f"Scan with ID {scan_id} does not exist."
            )

        # Commit only when this function owns the connection.
        if owns_connection:
            conn.commit()

    except Exception:
        # Roll back only transactions owned by this function.
        if owns_connection:
            conn.rollback()

        raise

    finally:
        # Never close a connection supplied by another function.
        if owns_connection:
            conn.close()



def get_scan(
    scan_id: int,
    database_path: str | None = None
) -> Scan | None:
    """
    Retrieve a scan by its ID.

    Args:
        scan_id (int): ID of the scan to retrieve.
        database_path (str | None): Optional SQLite database path.

    Returns:
        Scan | None: The matching scan or None if not found.

    Raises:
        TypeError: If scan_id is not an integer.
        ValueError: If scan_id is not positive.
        sqlite3.Error: If the database operation fails.
    """

    if type(scan_id) is not int:
        raise TypeError("scan_id must be an integer.")

    if scan_id <= 0:
        raise ValueError("scan_id must be positive.")

    # Open the requested database or use the default connection.
    connection = (
        get_connection()
        if database_path is None
        else get_connection(database_path)
    )

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

        return Scan(**dict(row))

    finally:
        # Close the connection after retrieving the scan.
        connection.close()




def list_scans(
    database_path: str | None = None
) -> list[Scan]:
    """
    Retrieve all scans, newest first.

    Args:
        database_path (str | None): Optional SQLite database path.

    Returns:
        list[Scan]: Scans ordered by timestamp and scan ID.

    Raises:
        sqlite3.Error: If the database operation fails.
    """

    # Open the requested database or use the default connection.
    connection = (
        get_connection()
        if database_path is None
        else get_connection(database_path)
    )

    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM Scans
            ORDER BY scan_timestamp DESC, scan_id DESC
            """
        )

        return [
            Scan(**dict(row))
            for row in cursor.fetchall()
        ]

    finally:
        # Close the connection after retrieving the scans.
        connection.close()



def save_scan_results(
    scan_path: str,
    file_data_list: list[dict],
    database_path: str | None = None
) -> int:
    """
    Save file metadata and finalize a scan.

    Every discovered file is stored, including inaccessible files.

    The scan record is committed separately so a failed attempt
    remains visible in scan history.

    File insertion and the final scan update share one transaction.
    If either operation fails, both are rolled back and the scan
    is marked as failed.

    Args:
        scan_path: Directory that was scanned.
        file_data_list: Metadata dictionaries from the scanner.
        database_path (str | None): Optional SQLite database path.

    Returns:
        The scan ID when saving succeeds.

    Raises:
        TypeError: If the file collection or an item is invalid.
        ValueError: If scan_path or file metadata is invalid.
        sqlite3.Error: If a database operation fails.
        Other exceptions from validation or processing are propagated.
    """

    if not isinstance(file_data_list, list):
        raise TypeError("file_data_list must be a list.")

    # Measure the time spent processing and saving the results.
    start_time = monotonic()

    # Create a persistent scan record before inserting files.
    # It initially has status="incomplete".
    # Create the scan in the requested database.
    scan_id = create_scan(
        scan_path,
        database_path=database_path,
    )

    connection = None

    try:
        # Prepare all files before beginning database writes.
        # Do not modify the scanner's original dictionaries.
        prepared_files = []

        for file_data in file_data_list:
            if not isinstance(file_data, dict):
                raise TypeError(
                    "Each file metadata item must be a dictionary."
                )

            prepared_files.append({
                **file_data,
                "scan_id": scan_id
            })

        # Count every discovered file, including inaccessible ones.
        file_count = len(prepared_files)

        # Missing or unknown sizes contribute zero bytes.
        # Invalid non-numeric sizes will be rejected by batch validation.
        total_size = sum(
            file_data.get("size") or 0
            for file_data in prepared_files
        )

    # Use the requested database for all file insertions.
        connection = (
            get_connection()
            if database_path is None
            else get_connection(database_path)
        )

        # Explicitly start the transaction.
        connection.execute("BEGIN")

        # This function must NOT commit or close our connection.
        save_files_batch(
            prepared_files,
            connection=connection
        )

        duration = int(monotonic() - start_time)

        # Finalize the scan inside the same transaction.
        update_scan(
            scan_id=scan_id,
            file_count=file_count,
            total_size=total_size,
            scan_duration=duration,
            status="completed",
            connection=connection
        )

        # Both file insertion and scan finalization succeed together.
        connection.commit()

        return scan_id

    except Exception:
        # Discard all changes made during the shared transaction.
        if connection is not None:
            connection.rollback()

        duration = int(monotonic() - start_time)

        try:
            # Use a separate connection to preserve the failed scan.
            update_scan(
                scan_id=scan_id,
                file_count=0,
                total_size=0,
                scan_duration=duration,
                status="failed",
                database_path=database_path,
            )

        except Exception:
            # Preserve the original failure while recording the
            # secondary failure for debugging.
            logger.exception(
                "Failed to mark scan %s as failed.",
                scan_id
            )

        # Let the caller know the save operation failed.
        raise

    finally:
        # Always release the shared connection.
        if connection is not None:
            connection.close()
