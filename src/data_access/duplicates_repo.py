
import sqlite3

from .connection import get_connection
from .models import DuplicateGroup, FileMetadata
from .file_repo import _row_to_file_metadata


def create_duplicate_group(
    hash_value: str,
    duplicate_count: int,
    potential_savings: int
) -> int:
    """
    Create a duplicate group and return its generated group_id.
    """

    if not isinstance(hash_value, str) or not hash_value.strip():
        raise ValueError("hash_value must be a non-empty string.")

    if type(duplicate_count) is not int or duplicate_count < 2:
        raise ValueError("duplicate_count must be an integer of at least 2.")

    if type(potential_savings) is not int or potential_savings < 0:
        raise ValueError("potential_savings must be a non-negative integer.")

    connection = get_connection()

    try:
        # Store the duplicate group's hash and summary statistics.
        cursor = connection.execute(
            """
            INSERT INTO DuplicateGroups (
                hash_value,
                duplicate_count,
                potential_savings
            )
            VALUES (?, ?, ?)
            """,
            (hash_value, duplicate_count, potential_savings)
        )

        group_id = cursor.lastrowid

        if group_id is None:
            raise sqlite3.DatabaseError(
                "Failed to retrieve the new duplicate group ID."
            )

        connection.commit()
        return group_id

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def add_duplicate_member(
    group_id: int,
    file_id: int,
    is_primary: bool = False
) -> None:
    """
    Associate an existing file with a duplicate group.

    is_primary identifies the representative file in the group.
    It does not mean the file is the original.
    """

    if type(group_id) is not int or group_id <= 0:
        raise ValueError("group_id must be a positive integer.")

    if type(file_id) is not int or file_id <= 0:
        raise ValueError("file_id must be a positive integer.")

    if type(is_primary) is not bool:
        raise TypeError("is_primary must be a boolean.")

    connection = get_connection()

    try:
        # The composite primary key prevents duplicate memberships.
        connection.execute(
            """
            INSERT INTO DuplicateMembers (
                group_id,
                file_id,
                is_primary
            )
            VALUES (?, ?, ?)
            """,
            (group_id, file_id, int(is_primary))
        )

        connection.commit()

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_duplicate_groups(scan_id: int) -> list[DuplicateGroup]:
    """
    Retrieve duplicate groups containing files from a given scan.

    Returns an empty list when no groups are found.
    """

    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")

    connection = get_connection()

    try:
        # DuplicateGroups has no scan_id column, so find groups
        # through DuplicateMembers and the Files table.
        cursor = connection.execute(
            """
            SELECT DISTINCT
                dg.group_id,
                dg.hash_value,
                dg.duplicate_count,
                dg.potential_savings
            FROM DuplicateGroups AS dg
            JOIN DuplicateMembers AS dm
                ON dg.group_id = dm.group_id
            JOIN Files AS f
                ON dm.file_id = f.file_id
            WHERE f.scan_id = ?
            ORDER BY dg.potential_savings DESC, dg.group_id ASC
            """,
            (scan_id,)
        )

        return [
            DuplicateGroup(**dict(row))
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


def get_duplicate_members(group_id: int) -> list[FileMetadata]:
    """
    Retrieve all files belonging to a duplicate group.

    Returns an empty list when the group has no members.
    """

    if type(group_id) is not int or group_id <= 0:
        raise ValueError("group_id must be a positive integer.")

    connection = get_connection()

    try:
        # Join the membership table with Files to retrieve
        # the complete metadata of each duplicate file.
        cursor = connection.execute(
            """
            SELECT f.*
            FROM Files AS f
            JOIN DuplicateMembers AS dm
                ON f.file_id = dm.file_id
            WHERE dm.group_id = ?
            ORDER BY dm.is_primary DESC, f.file_path ASC
            """,
            (group_id,)
        )

        return [
            _row_to_file_metadata(row)
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()
