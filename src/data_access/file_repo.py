
import sqlite3

from .connection import get_connection
from .models import FileMetadata, FileHash


def save_file_metadata(file_data: dict) -> int:
    """
    Save one file's metadata in the Files table.

    Accepts database field names such as file_path and file_size.
    Returns the newly generated file_id.
    """

    if not isinstance(file_data, dict):
        raise TypeError("file_data must be a dictionary.")

    # These fields are required to identify and store a file.
    required_fields = ("scan_id", "file_path", "file_name")

    for field in required_fields:
        if field not in file_data:
            raise ValueError(f"Missing required field: {field}")

    scan_id = file_data["scan_id"]
    file_path = file_data["file_path"]
    file_name = file_data["file_name"]
    file_size = file_data.get("file_size")

    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")

    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("file_path must be a non-empty string.")

    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("file_name must be a non-empty string.")

    # An inaccessible file may have an unknown size.
    if file_size is not None:
        if type(file_size) is not int or file_size < 0:
            raise ValueError("file_size must be a non-negative integer or None.")

    is_accessible = file_data.get("is_accessible", True)

    if type(is_accessible) is not bool:
        raise TypeError("is_accessible must be a boolean.")

    connection = get_connection()

    try:
        # Parameter placeholders keep values separate from SQL syntax.
        cursor = connection.execute(
            """
            INSERT INTO Files (
                scan_id,
                file_path,
                file_name,
                file_size,
                file_extension,
                created_timestamp,
                modified_timestamp,
                accessed_timestamp,
                is_accessible,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan_id,
                file_path,
                file_name,
                file_size,
                file_data.get("file_extension"),
                file_data.get("created_timestamp"),
                file_data.get("modified_timestamp"),
                file_data.get("accessed_timestamp"),
                int(is_accessible),
                file_data.get("error_message")
            )
        )

        file_id = cursor.lastrowid

        if file_id is None:
            raise sqlite3.DatabaseError("Failed to retrieve the new file ID.")

        connection.commit()
        return file_id

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_file_hash(
    file_id: int,
    hash_value: str,
    hash_algorithm: str
) -> int:
    """
    Save a file's calculated hash and return its hash_id.
    """

    if type(file_id) is not int or file_id <= 0:
        raise ValueError("file_id must be a positive integer.")

    if not isinstance(hash_value, str) or not hash_value.strip():
        raise ValueError("hash_value must be a non-empty string.")

    if not isinstance(hash_algorithm, str) or not hash_algorithm.strip():
        raise ValueError("hash_algorithm must be a non-empty string.")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO FileHashes (
                file_id,
                hash_value,
                hash_algorithm
            )
            VALUES (?, ?, ?)
            """,
            (file_id, hash_value, hash_algorithm)
        )

        hash_id = cursor.lastrowid

        if hash_id is None:
            raise sqlite3.DatabaseError("Failed to retrieve the new hash ID.")

        connection.commit()
        return hash_id

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_files_by_scan(scan_id: int) -> list[FileMetadata]:
    """
    Retrieve all files belonging to a particular scan.
    """

    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM Files
            WHERE scan_id = ?
            ORDER BY file_path
            """,
            (scan_id,)
        )

        # Convert SQLite rows into FileMetadata objects.
        return [
            _row_to_file_metadata(row)
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


def get_files_by_extension(
    scan_id: int,
    extension: str
) -> list[FileMetadata]:
    """
    Retrieve files with a specific extension from one scan.
    """

    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")

    if not isinstance(extension, str) or not extension.strip():
        raise ValueError("extension must be a non-empty string.")

    # Accept both "pdf" and ".pdf" as input.
    extension = extension.strip().lower()

    if not extension.startswith("."):
        extension = "." + extension

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM Files
            WHERE scan_id = ?
              AND LOWER(file_extension) = ?
            ORDER BY file_path
            """,
            (scan_id, extension)
        )

        return [
            _row_to_file_metadata(row)
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


def get_largest_files(
    scan_id: int,
    limit: int = 10
) -> list[FileMetadata]:
    """
    Retrieve the largest files from a scan.

    Files with unknown sizes are excluded.
    """

    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")

    if type(limit) is not int or limit <= 0:
        raise ValueError("limit must be a positive integer.")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM Files
            WHERE scan_id = ?
              AND file_size IS NOT NULL
            ORDER BY file_size DESC, file_id ASC
            LIMIT ?
            """,
            (scan_id, limit)
        )

        return [
            _row_to_file_metadata(row)
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


def get_total_storage(scan_id: int) -> int:
    """
    Calculate the total size of files belonging to a scan.

    Returns zero if no files have known sizes.
    """

    if type(scan_id) is not int or scan_id <= 0:
        raise ValueError("scan_id must be a positive integer.")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT COALESCE(SUM(file_size), 0) AS total_storage
            FROM Files
            WHERE scan_id = ?
            """,
            (scan_id,)
        )

        row = cursor.fetchone()
        return row["total_storage"]

    finally:
        connection.close()


def _row_to_file_metadata(row: sqlite3.Row) -> FileMetadata:
    """
    Convert a SQLite Files row into a FileMetadata object.

    SQLite stores booleans as integers, so convert the
    accessibility flag back to a Python boolean.
    """

    data = dict(row)
    data["is_accessible"] = bool(data["is_accessible"])

    return FileMetadata(**data)
