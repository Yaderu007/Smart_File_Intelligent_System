
"""
Save scanner results and duplicate information in SQLite.

The initial scan record is committed separately. File metadata,
hashes, duplicate groups, and completion statistics are saved
within one transaction.
"""

import sqlite3

from src.data_access.connection import get_connection
from src.data_access.scan_repo import create_scan, update_scan
from src.data_access.file_repo import save_files_batch, save_file_hash
from src.data_access.duplicates_repo import (
    create_duplicate_group,
    add_duplicate_member,
)


def save_scan(
    scan_path: str,
    files: list[dict],
    duplicate_result: dict | None = None,
    duration_seconds: int | None = None,
    database_path: str | None = None,
) -> int:
    """
    Save scanner results and return the completed scan ID.

    First commits an incomplete scan record. All file metadata,
    hashes, duplicate groups, members, and the final status update
    are saved in one transaction. On failure, the transaction is
    rolled back and the scan is marked failed separately.

    Args:
        scan_path (str): Root directory that was scanned.
        files (list[dict]): File metadata returned by the scanner.
        duplicate_result (dict | None): Duplicate groups and hashes
            returned by duplicate detection, or None if unavailable.
        duration_seconds (int | None): Scan duration in rounded whole
            seconds, excluding database persistence.
        database_path (str | None): Optional SQLite database path.

    Returns:
        int: Unique ID of the completed scan.

    Raises:
        TypeError: If an argument has an unsupported type.
        ValueError: If the scan path, file metadata, or duration
            is invalid.
        KeyError: If duplicate information references a file
            that was not saved, or a required result key is missing.
        sqlite3.Error: If a database operation fails.
    """

    # Validate inputs before creating the scan record.
    if not isinstance(scan_path, str):
        raise TypeError("scan_path must be a string.")

    if not scan_path.strip():
        raise ValueError("scan_path cannot be empty.")

    if not isinstance(files, list):
        raise TypeError("files must be a list.")

    if duplicate_result is not None and not isinstance(
        duplicate_result, dict
    ):
        raise TypeError("duplicate_result must be a dictionary or None.")

    if duration_seconds is not None:
        if type(duration_seconds) is not int:
            raise TypeError("duration_seconds must be an integer or None.")

        if duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative.")

    # Create the incomplete scan using the requested database.
    scan_id = create_scan(
        scan_path=scan_path,
        database_path=database_path,
    )

    conn = None

    try:
        # Begin the shared transaction for all scan data.
        conn = get_connection(database_path)
        conn.execute("BEGIN")

        # Reject malformed scanner records.
        for file in files:
            if not isinstance(file, dict):
                raise TypeError("Each file record must be a dictionary.")

            path = file.get("path")
            name = file.get("name")

            if (
                not isinstance(path, str)
                or not path.strip()
                or not isinstance(name, str)
                or not name.strip()
            ):
                raise ValueError(
                    "Each file must have a non-empty path and name."
                )

        # Calculate total size from known nonnegative file sizes.
        total_size = sum(
            file["size"]
            for file in files
            if type(file.get("size")) is int
            and file["size"] >= 0
        )

        # Save file records under the committed scan ID.
        file_records = [
            {**file, "scan_id": scan_id}
            for file in files
        ]

        file_ids = save_files_batch(
            file_data_list=file_records,
            connection=conn,
        )

        # Build the path lookup from the IDs returned by storage.
        path_to_id = {
            file["path"]: file_id
            for file, file_id in zip(files, file_ids, strict=True)
        }

        if len(path_to_id) != len(files):
            raise ValueError("Scanner returned duplicate file paths.")

        # Store hashes and duplicate groups when provided.
        if duplicate_result is not None:
            file_hashes = duplicate_result["file_hashes"]
            duplicate_groups = duplicate_result["duplicate_groups"]

            for path, hash_value in file_hashes.items():
                if path not in path_to_id:
                    raise KeyError(
                        f"Hash references unknown file path: {path}"
                    )

                save_file_hash(
                    file_id=path_to_id[path],
                    hash_value=hash_value,
                    hash_algorithm="sha256",
                    connection=conn,
                )

            for group in duplicate_groups:
                # Validate every member before inserting the group.
                for file in group["files"]:
                    path = file["path"]

                    if path not in path_to_id:
                        raise KeyError(
                            "Duplicate group references unknown "
                            f"file path: {path}"
                        )

                group_id = create_duplicate_group(
                    scan_id=scan_id,
                    hash_value=group["hash"],
                    duplicate_count=group["count"],
                    potential_savings=group["potential_savings"],
                    connection=conn,
                )

                # The scanner's first sorted member is primary.
                for index, file in enumerate(group["files"]):
                    add_duplicate_member(
                        group_id=group_id,
                        file_id=path_to_id[file["path"]],
                        is_primary=(index == 0),
                        connection=conn,
                    )

        # Mark the scan completed within the same transaction.
        update_scan(
            scan_id=scan_id,
            file_count=len(files),
            total_size=total_size,
            scan_duration=duration_seconds,
            status="completed",
            connection=conn,
        )

        conn.commit()
        return scan_id

    except Exception:
        # Undo all file-related changes from this transaction.
        if conn is not None:
            conn.rollback()

        # Preserve the committed scan record with failed status.
        failure_conn = get_connection(database_path)

        try:
            update_scan(
                scan_id=scan_id,
                file_count=0,
                total_size=0,
                scan_duration=duration_seconds,
                status="failed",
                connection=failure_conn,
            )
            failure_conn.commit()

        finally:
            failure_conn.close()

        raise

    finally:
        if conn is not None:
            conn.close()
