
import sqlite3

from .connection import get_connection
from .models import DuplicateGroup, FileMetadata
from .file_repo import _row_to_file_metadata




def create_duplicate_group(
    scan_id: int,
    hash_value: str,
    duplicate_count: int,
    potential_savings: int,
    connection: sqlite3.Connection | None = None,
    database_path: str | None = None
) -> int:
    """
    Create a duplicate group for files sharing the same hash.

    When an existing connection is provided, the caller manages
    the transaction, including commit, rollback, and close.

    Args:
        scan_id (int): ID of the scan containing the duplicates.
        hash_value (str): Hash shared by the duplicate files.
        duplicate_count (int): Number of files in the group.
        potential_savings (int): Recoverable storage in bytes.
        connection (sqlite3.Connection | None): Optional existing
            database connection.
        database_path (str | None): Optional SQLite database path.
            Used only when no connection is supplied.

    Returns:
        int: ID of the newly created duplicate group.

    Raises:
        ValueError: If any argument is invalid.
        sqlite3.Error: If the database operation fails.
    """

    # Validate the scan ID.
    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")

    # Validate the hash value.
    if not isinstance(hash_value, str) or not hash_value.strip():
        raise ValueError("hash_value must be a non-empty string.")

    # A duplicate group must contain at least two files.
    if type(duplicate_count) is not int or duplicate_count < 2:
        raise ValueError("duplicate_count must be at least 2.")

    # Potential savings cannot be negative.
    if type(potential_savings) is not int or potential_savings < 0:
        raise ValueError("potential_savings must be non-negative.")

    # Determine who owns the connection.
    owns_connection = connection is None

    # Open the requested database only when needed.
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
            INSERT INTO DuplicateGroups (
                scan_id,
                hash_value,
                duplicate_count,
                potential_savings
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                scan_id,
                hash_value,
                duplicate_count,
                potential_savings,
            )
        )

        # Retrieve the generated duplicate group ID.
        group_id = cursor.lastrowid

        if group_id is None:
            raise sqlite3.DatabaseError(
                "Failed to retrieve the new duplicate group ID."
            )

        # Commit only when this function owns the connection.
        if owns_connection:
            conn.commit()

        return group_id

    except sqlite3.Error:
        # Shared transaction rollback belongs to the caller.
        if owns_connection:
            conn.rollback()
        raise

    finally:
        # Close only connections opened here.
        if owns_connection:
            conn.close()






def add_duplicate_member(
    group_id: int,
    file_id: int,
    is_primary: bool = False,
    connection: sqlite3.Connection | None = None,
    database_path: str | None = None
) -> None:
    """
    Add a file to a duplicate group.

    The file and duplicate group must belong to the same scan.
    When an existing connection is supplied, the caller manages
    its transaction, including commit, rollback, and close.

    Args:
        group_id (int): ID of the duplicate group.
        file_id (int): ID of the file being added.
        is_primary (bool): Whether this is the primary file.
            Defaults to False.
        connection (sqlite3.Connection | None): Optional existing
            database connection.
        database_path (str | None): Optional SQLite database path.
            Used only when no connection is supplied.

    Returns:
        None: The membership is stored in the database.

    Raises:
        TypeError: If is_primary is not a boolean.
        ValueError: If IDs are invalid or the file and group
            belong to different scans.
        sqlite3.Error: If the database operation fails.
    """

    # Validate the duplicate group ID.
    if type(group_id) is not int or group_id <= 0:
        raise ValueError("group_id must be a positive integer.")

    # Validate the file ID.
    if type(file_id) is not int or file_id <= 0:
        raise ValueError("file_id must be a positive integer.")

    # Ensure the primary flag is a boolean.
    if type(is_primary) is not bool:
        raise TypeError("is_primary must be a boolean.")

    # Determine whether this function owns the connection.
    owns_connection = connection is None

    # Open the requested database only when needed.
    if owns_connection:
        conn = (
            get_connection()
            if database_path is None
            else get_connection(database_path)
        )
    else:
        conn = connection

    try:
        # Check that the file and group belong to the same scan.
        cursor = conn.execute(
            """
            SELECT 1
            FROM DuplicateGroups AS dg
            JOIN Files AS f ON f.scan_id = dg.scan_id
            WHERE dg.group_id = ?
            AND f.file_id = ?
            """,
            (group_id, file_id),
        )

        if cursor.fetchone() is None:
            # Distinguish a scan mismatch from a missing record.
            group_row = conn.execute(
                "SELECT scan_id FROM DuplicateGroups WHERE group_id = ?",
                (group_id,),
            ).fetchone()

            file_row = conn.execute(
                "SELECT scan_id FROM Files WHERE file_id = ?",
                (file_id,),
            ).fetchone()

            if group_row is not None and file_row is not None:
                raise ValueError(
                    "The file and duplicate group must belong "
                    "to the same scan."
                )

            raise sqlite3.IntegrityError(
                "The duplicate group or file does not exist."
            )

        # Insert the file into the duplicate group.
        conn.execute(
            """
            INSERT INTO DuplicateMembers (
                group_id,
                file_id,
                is_primary
            )
            VALUES (?, ?, ?)
            """,
            (group_id, file_id, int(is_primary)),
        )

        # Commit only when this function owns the connection.
        if owns_connection:
            conn.commit()

    except Exception:
        # Leave rollback to the caller for shared transactions.
        if owns_connection:
            conn.rollback()
        raise

    finally:
        # Close only connections created by this function.
        if owns_connection:
            conn.close()






def get_duplicate_groups(
    scan_id: int,
    database_path: str | None = None
) -> list[DuplicateGroup]:
    """
    Retrieve all duplicate groups belonging to a scan.

    Groups are ordered by potential savings in descending order.
    Groups with equal savings are ordered by group ID.

    Args:
        scan_id (int): Unique ID of the scan to search.
        database_path (str | None): Optional SQLite database path.
            Defaults to the project's database.

    Returns:
        list[DuplicateGroup]: Duplicate groups belonging to the scan.
            Returns an empty list if no groups exist.

    Raises:
        ValueError: If scan_id is not a positive integer.
        sqlite3.Error: If a database operation fails.
    """

    # Ensure the scan ID is a positive integer.
    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")

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
            FROM DuplicateGroups
            WHERE scan_id = ?
            ORDER BY potential_savings DESC, group_id ASC
            """,
            (scan_id,)
        )

        # Convert database rows into DuplicateGroup objects.
        return [
            DuplicateGroup(**dict(row))
            for row in cursor.fetchall()
        ]

    finally:
        # Always close the database connection.
        connection.close()




def get_duplicate_members(
    group_id: int,
    database_path: str | None = None
) -> list[FileMetadata]:
    """
    Retrieve all files belonging to a duplicate group.

    The primary file is returned first, followed by other files
    in ascending order of their paths.

    Args:
        group_id (int): Unique ID of the duplicate group.
        database_path (str | None): Optional SQLite database path.
            Defaults to the project's database.

    Returns:
        list[FileMetadata]: Files belonging to the duplicate group.
            Returns an empty list if no members exist.

    Raises:
        ValueError: If group_id is not a positive integer.
        sqlite3.Error: If a database operation fails.
    """

    # Ensure the group ID is a positive integer.
    if type(group_id) is not int or group_id <= 0:
        raise ValueError("group_id must be a positive integer.")

    # Open the requested database or use the default connection.
    connection = (
        get_connection()
        if database_path is None
        else get_connection(database_path)
    )

    try:
        cursor = connection.execute(
            """
            SELECT f.*
            FROM DuplicateMembers AS dm
            JOIN Files AS f ON f.file_id = dm.file_id
            WHERE dm.group_id = ?
            ORDER BY dm.is_primary DESC, f.path ASC
            """,
            (group_id,)
        )

        # Convert database rows into FileMetadata objects.
        return [
            _row_to_file_metadata(row)
            for row in cursor.fetchall()
        ]

    finally:
        # Always close the database connection.
        connection.close()
