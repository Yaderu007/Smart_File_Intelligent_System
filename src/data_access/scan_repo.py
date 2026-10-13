import sqlite3
from datetime import datetime, timezone

from .connection import get_connection


def create_scan(scan_path: str) -> int:
    """
    Create a new scan record in the Scans table.

    Args:
        scan_path: Directory being scanned.

    Returns:
        The newly generated scan_id.

    Raises:
        TypeError: If scan_path is not a string.
        ValueError: If scan_path is empty.
        sqlite3.Error: If the database operation fails.
    """

    # Checks input is a string and not None.
    if not isinstance(scan_path, str):
        raise TypeError("scan_path must be a string.")

    # Check whether the path is empty or contains only whitespace.
    if not scan_path.strip():
        raise ValueError("scan_path cannot be empty.")

    # Record the scan's starting time in UTC.
    scan_timestamp = datetime.now(timezone.utc).isoformat()

    # Open a connection to our SQLite database.
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO Scans (scan_path, scan_timestamp)
            VALUES (?, ?)
            """,
            (scan_path, scan_timestamp)
        )

        # Retrieve the automatically generated scan ID.
        scan_id = cursor.lastrowid

        if scan_id is None:
            raise sqlite3.DatabaseError(
                "Failed to retrieve the new scan ID."
            )

        # Save the new scan record permanently.
        connection.commit()

        return scan_id

    except sqlite3.Error:
        # Undo any uncommitted changes if the operation fails.
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
    Update an existing scan with its final statistics.

    Args:
        scan_id: ID of the scan to update.
        file_count: Number of files discovered.
        total_size: Total size of discovered files in bytes.
        scan_duration: Time taken to scan, in seconds.
        status: Current scan status.

    Raises:
        TypeError: If an argument has an incorrect type.
        ValueError: If an argument has an invalid value.
        LookupError: If the scan does not exist.
        sqlite3.Error: If a database operation fails.
    """

    # Validate the scan ID.
    if type(scan_id) is not int:
        raise TypeError("scan_id must be an integer.")

    if scan_id <= 0:
        raise ValueError("scan_id must be positive.")

    # Validate the file count.
    if type(file_count) is not int:
        raise TypeError("file_count must be an integer.")

    if file_count < 0:
        raise ValueError("file_count cannot be negative.")

    # Validate the total storage size.
    if type(total_size) is not int:
        raise TypeError("total_size must be an integer.")

    if total_size < 0:
        raise ValueError("total_size cannot be negative.")

    # Validate the scan duration.
    if type(scan_duration) is not int:
        raise TypeError("scan_duration must be an integer.")

    if scan_duration < 0:
        raise ValueError("scan_duration cannot be negative.")

    # Validate the scan status.
    if not isinstance(status, str):
        raise TypeError("status must be a string.")

    allowed_statuses = {"completed", "incomplete", "failed"}

    if status not in allowed_statuses:
        raise ValueError(
            f"Invalid status '{status}'. "
            f"Allowed statuses: {sorted(allowed_statuses)}"
        )

    # Open a connection to SQLite.
    connection = get_connection()

    try:
        # Update the existing scan record.
        cursor = connection.execute(
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

        # Check whether a matching scan was found.
        if cursor.rowcount == 0:
            raise LookupError(
                f"Scan with ID {scan_id} does not exist."
            )

        # Save the changes permanently.
        connection.commit()

    except Exception:
        # Undo uncommitted changes if something goes wrong.
        connection.rollback()
        raise

    finally:
        # Close the database connection.
        connection.close()

def get_scan(scan_id: int) -> dict | None:
    """
    Retrieve a scan record using its scan ID.

    Args:
        scan_id: ID of the scan to retrieve.

    Returns:
        dict: Scan information if the scan exists.
        None: If no scan exists with the given ID.

    Raises:
        TypeError: If scan_id is not an integer.
        ValueError: If scan_id is not positive.
        sqlite3.Error: If a database operation fails.
    """

    # Validate the scan ID.
    if type(scan_id) is not int:
        raise TypeError("scan_id must be an integer.")

    if scan_id <= 0:
        raise ValueError("scan_id must be positive.")

    # Open a connection to SQLite.
    connection = get_connection()

    try:
        # Retrieve the scan matching the given ID.
        cursor = connection.execute(
            """
            SELECT *
            FROM Scans
            WHERE scan_id = ?
            """,
            (scan_id,)
        )

        # Retrieve the first matching row.
        scan = cursor.fetchone()

        # Return None if the scan does not exist.
        if scan is None:
            return None

        # Convert the SQLite row into a dictionary.
        return dict(scan)

    finally:
        # Close the connection.
        connection.close()


def list_scans() -> list[dict]:
    """
    Retrieve all scan records, ordered from newest to oldest.

    Returns:
        list[dict]: A list of scan records.
                    Returns an empty list if no scans exist.

    Raises:
        sqlite3.Error: If a database operation fails.
    """

    # Open a connection to SQLite.
    connection = get_connection()

    try:
        # Retrieve all scans, newest first.
        cursor = connection.execute(
            """
            SELECT *
            FROM Scans
            ORDER BY scan_timestamp DESC, scan_id DESC
            """
        )

        # Retrieve all rows returned by the query.
        scans = cursor.fetchall()

        # Convert each SQLite row into a dictionary.
        return [dict(scan) for scan in scans]

    finally:
        # Always close the database connection.
        connection.close()



