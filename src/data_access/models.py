
from dataclasses import dataclass


@dataclass
class Scan:
    """
    Represents one directory scanning session.

    Corresponds to a record in the Scans table.
    """

    scan_id: int
    scan_path: str
    scan_timestamp: str
    scan_duration: int | None
    file_count: int
    total_size: int
    status: str


@dataclass
class FileMetadata:
    """
    Represents metadata for one discovered file.

    Corresponds to a record in the Files table.
    The scanner's field names will be converted to these
    database field names during integration.
    """

    file_id: int
    scan_id: int
    file_path: str
    file_name: str
    file_size: int | None
    file_extension: str | None
    category: str
    created_timestamp: str | None
    modified_timestamp: str | None
    accessed_timestamp: str | None
    is_accessible: bool
    error_message: str | None


@dataclass
class FileHash:
    """
    Represents a calculated hash for a file.

    Corresponds to a record in the FileHashes table.
    """

    hash_id: int
    file_id: int
    hash_value: str
    hash_algorithm: str


@dataclass
class DuplicateGroup:
    """
    Represents a group of files with matching content hashes.

    Corresponds to a record in the DuplicateGroups table.
    """

    group_id: int
    hash_value: str
    duplicate_count: int
    potential_savings: int
