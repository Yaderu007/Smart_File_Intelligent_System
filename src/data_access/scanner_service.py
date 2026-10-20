
"""
Coordinate directory scanning and database storage.

This module saves scanned files, calculated hashes, and duplicate
information while preserving the status of each scan.
"""

import sqlite3
import time
from pathlib import Path

from src.scanner import scan_directory, detect_duplicates
from src.data_access.connection import get_connection
from src.data_access.scan_repo import create_scan, update_scan
from src.data_access.file_repo import save_files_batch, save_file_hash
from src.data_access.duplicates_repo import (
    create_duplicate_group,
    add_duplicate_member,
)


def save_scan(
    scan_path: str,
    database_path: str | None = None
) -> int:
    """
    Scan a directory and save its results in the database.

    The initial scan record is committed before file storage begins.
    File metadata, hashes, duplicate groups, and completion statistics
    are then saved within one transaction.

    If saving fails, file-related changes are rolled back and the
    existing scan record is marked as failed.

    Args:
        scan_path (str): Directory to scan.
        database_path (str | None): Optional SQLite database path.
            Uses the configured database when not provided.

    Returns:
        int: Unique ID of the completed scan.

    Raises:
        TypeError: If scan_path is not a string or scanner metadata
            is not a dictionary.
        ValueError: If the directory or scanner file metadata is invalid.
        KeyError: If scanner results contain missing required fields
            or reference a file that was not saved.
        sqlite3.Error: If a database operation fails.
        RuntimeError: If a scanner or storage operation raises this error.
    """

    # Validate the supplied directory path.
    if not isinstance(scan_path, str):
        raise TypeError("scan_path must be a string.")

    if not scan_path.strip():
        raise ValueError("scan_path cannot be empty.")

    root = Path(scan_path).resolve()

    if not root.is_dir():
        raise ValueError(f"{root} is not a valid directory.")

    # Measure scanning and duplicate detection only.
    start_time = time.perf_counter()

    files = list(scan_directory(str(root)))
    duplicate_result = detect_duplicates(files)

    scan_duration = round(time.perf_counter() - start_time)

    # Validate scanner metadata before saving any file records.
    for file in files:
        if not isinstance(file, dict):
            raise TypeError("Scanner file metadata must be a dictionary.")

        path = file.get("path")
        name = file.get("name")

        if (
            not isinstance(path, str)
            or not path.strip()
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise ValueError(
                "Scanner file metadata must contain a non-empty path and name."
            )

    duplicate_groups = duplicate_result["duplicate_groups"]
    file_hashes = duplicate_result["file_hashes"]

    # Calculate total storage from valid file sizes.
    total_size = sum(
        file["size"]
        for file in files
        if type(file.get("size")) is int
        and file["size"] >= 0
    )

    # Create and commit the initial incomplete scan record.
    scan_id = create_scan(
        scan_path=str(root),
        database_path=database_path
    )

    # Open one connection for the remaining database operations.
    conn = get_connection(database_path)

    try:
        conn.execute("BEGIN")

        # Associate each file with the committed scan.
        file_records = [
            {**file, "scan_id": scan_id}
            for file in files
        ]

        # Save file metadata and retrieve generated IDs.
        file_ids = save_files_batch(
            file_data_list=file_records,
            connection=conn
        )

        # Match scanner paths to database file IDs.
        path_to_id = {
            file["path"]: file_id
            for file, file_id in zip(files, file_ids, strict=True)
        }

        # Save hashes only for known file paths.
        for path, hash_value in file_hashes.items():
            if path not in path_to_id:
                raise KeyError(f"Hash references unknown file path: {path}")

            save_file_hash(
                file_id=path_to_id[path],
                hash_value=hash_value,
                hash_algorithm="sha256",
                connection=conn
            )

        # Save duplicate groups and their members.
        for group in duplicate_groups:
            # Validate all group members before inserting the group.
            for file in group["files"]:
                if file["path"] not in path_to_id:
                    raise KeyError(
                        f"Duplicate group references unknown file path: "
                        f"{file['path']}"
                    )

            group_id = create_duplicate_group(
                scan_id=scan_id,
                hash_value=group["hash"],
                duplicate_count=group["count"],
                potential_savings=group["potential_savings"],
                connection=conn
            )

            # Select the first sorted file as the primary member.
            for index, file in enumerate(group["files"]):
                add_duplicate_member(
                    group_id=group_id,
                    file_id=path_to_id[file["path"]],
                    is_primary=(index == 0),
                    connection=conn
                )

        # Complete the scan with its measured duration.
        update_scan(
            scan_id=scan_id,
            file_count=len(files),
            total_size=total_size,
            scan_duration=scan_duration,
            status="completed",
            connection=conn
        )

        # Commit all file-related records and the completed status.
        conn.commit()

        return scan_id

    except Exception:
        # Roll back incomplete file and duplicate records.
        conn.rollback()

        # Mark the existing scan as failed using a separate connection.
        failure_conn = get_connection(database_path)

        try:
            update_scan(
                scan_id=scan_id,
                file_count=0,
                total_size=0,
                scan_duration=scan_duration,
                status="failed",
                connection=failure_conn
            )

            failure_conn.commit()

        finally:
            failure_conn.close()

        raise

    finally:
        # Close the original database connection.
        conn.close()
