
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
    Metadata field names match Aaryadeep's scanner output.
    The database additionally stores file_id, scan_id,
    and accessed_timestamp.
    """

    file_id: int
    scan_id: int
    path: str
    name: str
    size: int | None
    extension: str | None
    category: str
    created: str | None
    modified: str | None
    accessed_timestamp: str | None
    accessible: bool
    error: str | None


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
    group_id: int
    scan_id: int  # Scan that owns this duplicate group.
    hash_value: str
    duplicate_count: int
    potential_savings: int
