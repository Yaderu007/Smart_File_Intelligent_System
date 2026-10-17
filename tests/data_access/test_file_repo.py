
import sqlite3

import pytest

from src.data_access import file_repo, scan_repo
from src.data_access.connection import get_connection, initialize_database
from src.data_access.models import FileMetadata


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    """
    Create an isolated database for testing file repository functions.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        monkeypatch (pytest.MonkeyPatch): Replaces database connections
            temporarily so tests cannot modify smart_files.db.

    Returns:
        Path: Path to the initialized temporary SQLite database.
    """

    database_path = tmp_path / "test_files.db"

    # Create the five database tables in a temporary database.
    initialize_database(database_path)

    # Both repositories must use the same temporary database.
    # The scanner's metadata needs a valid scan_id before insertion.
    def temporary_connection():
        return get_connection(database_path)

    monkeypatch.setattr(
        file_repo,
        "get_connection",
        temporary_connection,
    )

    monkeypatch.setattr(
        scan_repo,
        "get_connection",
        temporary_connection,
    )

    return database_path


@pytest.fixture
def scan_id(test_database):
    """
    Create a scan record that file metadata can reference.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        int: ID of the newly created scan.
    """

    return scan_repo.create_scan("/example/documents")


@pytest.fixture
def sample_metadata(scan_id):
    """
    Build a metadata dictionary matching the scanner's output.

    Args:
        scan_id (int): ID of the scan owning the file.

    Returns:
        dict: File metadata ready for database insertion.
    """

    return {
        "scan_id": scan_id,
        "path": "/example/documents/report.pdf",
        "name": "report.pdf",
        "extension": ".pdf",
        "size": 2048,
        "category": "Documents",
        "created": "2026-10-17T10:00:00",
        "modified": "2026-10-17T11:00:00",
        "accessible": True,
        "error": None,
    }


def test_save_file_metadata(test_database, sample_metadata):
    """
    Verify that scanner metadata can be saved successfully.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Metadata to insert.

    Returns:
        None: The test passes when the record is stored correctly.
    """

    file_id = file_repo.save_file_metadata(sample_metadata)

    assert isinstance(file_id, int)
    assert file_id > 0

    files = file_repo.get_files_by_scan(sample_metadata["scan_id"])

    assert len(files) == 1

    saved_file = files[0]

    assert saved_file.file_id == file_id
    assert saved_file.path == sample_metadata["path"]
    assert saved_file.name == sample_metadata["name"]
    assert saved_file.extension == ".pdf"
    assert saved_file.size == 2048
    assert saved_file.category == "Documents"
    assert saved_file.accessible is True


def test_get_files_by_scan_returns_dataclasses(
    test_database,
    sample_metadata,
):
    """
    Verify that retrieved files are FileMetadata dataclasses.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Metadata to insert.

    Returns:
        None: The test passes when the returned type is correct.
    """

    file_repo.save_file_metadata(sample_metadata)

    files = file_repo.get_files_by_scan(sample_metadata["scan_id"])

    assert len(files) == 1
    assert isinstance(files[0], FileMetadata)

    # SQLite stores booleans as integers, so the repository
    # must convert accessible back to a Python boolean.
    assert type(files[0].accessible) is bool


def test_save_inaccessible_file(test_database, sample_metadata):
    """
    Verify that inaccessible files can be stored with unknown size.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Metadata to modify.

    Returns:
        None: The test passes when nullable fields are preserved.
    """

    sample_metadata["size"] = None
    sample_metadata["accessible"] = False
    sample_metadata["error"] = "Permission denied"

    file_repo.save_file_metadata(sample_metadata)

    files = file_repo.get_files_by_scan(sample_metadata["scan_id"])

    assert len(files) == 1
    assert files[0].size is None
    assert files[0].accessible is False
    assert files[0].error == "Permission denied"


def test_get_files_by_extension(test_database, sample_metadata):
    """
    Verify that files can be filtered by extension.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Base metadata for insertion.

    Returns:
        None: The test passes when only matching files are returned.
    """

    file_repo.save_file_metadata(sample_metadata)

    # Create another file with a different extension.
    text_file = {
        **sample_metadata,
        "path": "/example/documents/notes.txt",
        "name": "notes.txt",
        "extension": ".txt",
        "size": 500,
    }

    file_repo.save_file_metadata(text_file)

    pdf_files = file_repo.get_files_by_extension(
        sample_metadata["scan_id"],
        ".pdf",
    )

    assert len(pdf_files) == 1
    assert pdf_files[0].name == "report.pdf"


def test_get_largest_files(test_database, sample_metadata):
    """
    Verify that files are ordered from largest to smallest.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Base metadata for insertion.

    Returns:
        None: The test passes when file sizes are ordered correctly.
    """

    sizes = [100, 5000, 1000]

    for index, size in enumerate(sizes):
        metadata = {
            **sample_metadata,
            "path": f"/example/documents/file_{index}.txt",
            "name": f"file_{index}.txt",
            "extension": ".txt",
            "size": size,
        }

        file_repo.save_file_metadata(metadata)

    largest_files = file_repo.get_largest_files(
        sample_metadata["scan_id"],
        limit=2,
    )

    assert len(largest_files) == 2
    assert [file.size for file in largest_files] == [5000, 1000]


def test_get_total_storage(test_database, sample_metadata):
    """
    Verify that total storage is calculated correctly.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Base metadata for insertion.

    Returns:
        None: The test passes when the calculated sum is correct.
    """

    sizes = [100, 200, 300]

    for index, size in enumerate(sizes):
        metadata = {
            **sample_metadata,
            "path": f"/example/documents/file_{index}.txt",
            "name": f"file_{index}.txt",
            "size": size,
        }

        file_repo.save_file_metadata(metadata)

    total = file_repo.get_total_storage(sample_metadata["scan_id"])

    assert total == 600


def test_total_storage_ignores_unknown_size(
    test_database,
    sample_metadata,
):
    """
    Verify that NULL file sizes do not affect the total.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Base metadata for insertion.

    Returns:
        None: The test passes when unknown sizes are ignored.
    """

    file_repo.save_file_metadata(sample_metadata)

    unknown_file = {
        **sample_metadata,
        "path": "/example/documents/unreadable.txt",
        "name": "unreadable.txt",
        "size": None,
        "accessible": False,
        "error": "Permission denied",
    }

    file_repo.save_file_metadata(unknown_file)

    total = file_repo.get_total_storage(sample_metadata["scan_id"])

    assert total == 2048


def test_save_file_hash(test_database, sample_metadata):
    """
    Verify that a file hash can be saved to FileHashes.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Metadata for the file being hashed.

    Returns:
        None: The test passes when the hash record is correct.
    """

    file_id = file_repo.save_file_metadata(sample_metadata)

    # Use a valid-looking SHA-256 digest for testing.
    hash_value = "a" * 64

    hash_id = file_repo.save_file_hash(
        file_id=file_id,
        hash_value=hash_value,
        hash_algorithm="sha256",
    )

    assert isinstance(hash_id, int)
    assert hash_id > 0

    # There is no hash retrieval repository function yet,
    # so inspect the temporary database directly.
    connection = get_connection(test_database)

    try:
        row = connection.execute(
            """
            SELECT file_id, hash_value, hash_algorithm
            FROM FileHashes
            WHERE hash_id = ?
            """,
            (hash_id,),
        ).fetchone()

        assert row is not None
        assert row["file_id"] == file_id
        assert row["hash_value"] == hash_value
        assert row["hash_algorithm"] == "sha256"

    finally:
        connection.close()


def test_duplicate_hash_algorithm_is_rejected(
    test_database,
    sample_metadata,
):
    """
    Verify that a file cannot have two hashes for one algorithm.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Metadata for the file being hashed.

    Returns:
        None: The test passes when SQLite rejects the duplicate.
    """

    file_id = file_repo.save_file_metadata(sample_metadata)

    file_repo.save_file_hash(file_id, "a" * 64, "sha256")

    # The schema has UNIQUE(file_id, hash_algorithm).
    with pytest.raises(sqlite3.IntegrityError):
        file_repo.save_file_hash(file_id, "b" * 64, "sha256")


def test_save_file_rejects_nonexistent_scan(
    test_database,
    sample_metadata,
):
    """
    Verify that a file cannot reference a nonexistent scan.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Metadata to insert.

    Returns:
        None: The test passes when foreign-key enforcement works.
    """

    sample_metadata["scan_id"] = 999

    with pytest.raises(sqlite3.IntegrityError):
        file_repo.save_file_metadata(sample_metadata)


@pytest.mark.parametrize(
    "invalid_size",
    [-1, "large", True],
)
def test_save_file_rejects_invalid_size(
    test_database,
    sample_metadata,
    invalid_size,
):
    """
    Verify that invalid file sizes are rejected.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Metadata to modify.
        invalid_size: Invalid size being tested.

    Returns:
        None: The test passes when validation rejects the value.
    """

    sample_metadata["size"] = invalid_size

    with pytest.raises((TypeError, ValueError)):
        file_repo.save_file_metadata(sample_metadata)
