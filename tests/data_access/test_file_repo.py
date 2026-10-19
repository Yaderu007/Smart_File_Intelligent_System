
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


def test_save_file_hash_shared_connection_does_not_commit(
    test_database,
    sample_metadata,
):
    """
    Verify that saving a hash with a shared connection
    leaves commit and rollback responsibility to the caller.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Metadata for the file being hashed.

    Returns:
        None: Passes when the hash remains uncommitted and
            the caller can roll back the insertion.
    """

    file_id = file_repo.save_file_metadata(sample_metadata)

    connection = get_connection(test_database)

    try:
        connection.execute("BEGIN")

        hash_id = file_repo.save_file_hash(
            file_id=file_id,
            hash_value="a" * 64,
            hash_algorithm="sha256",
            connection=connection,
        )

        assert isinstance(hash_id, int)

        # The hash is visible inside the caller's transaction.
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM FileHashes WHERE file_id = ?",
            (file_id,),
        ).fetchone()

        assert row["count"] == 1

        # A separate connection cannot see the uncommitted hash.
        other_connection = get_connection(test_database)

        try:
            other_row = other_connection.execute(
                "SELECT COUNT(*) AS count FROM FileHashes WHERE file_id = ?",
                (file_id,),
            ).fetchone()

            assert other_row["count"] == 0

        finally:
            other_connection.close()

        # The caller can roll back the hash insertion.
        connection.rollback()

        row = connection.execute(
            "SELECT COUNT(*) AS count FROM FileHashes WHERE file_id = ?",
            (file_id,),
        ).fetchone()

        assert row["count"] == 0

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



def test_save_files_batch_success(test_database, sample_metadata):
    """
    Verify that multiple files are saved in one batch.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Base metadata for insertion.

    Returns:
        None: The test passes when every file is stored.
    """
    first_file = sample_metadata.copy()

    second_file = {
        **sample_metadata,
        "path": "/example/documents/notes.txt",
        "name": "notes.txt",
        "extension": ".txt",
        "size": 500,
    }

    file_ids = file_repo.save_files_batch([first_file, second_file])

    assert len(file_ids) == 2
    assert all(isinstance(file_id, int) for file_id in file_ids)
    assert all(file_id > 0 for file_id in file_ids)
    assert file_ids[0] != file_ids[1]

    saved_files = file_repo.get_files_by_scan(sample_metadata["scan_id"])

    assert len(saved_files) == 2


def test_save_files_batch_preserves_input_order(
    test_database,
    sample_metadata,
):
    """
    Verify that returned IDs correspond to input file order.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Base metadata for insertion.

    Returns:
        None: The test passes when IDs match their input files.
    """
    files = [
        {
            **sample_metadata,
            "path": f"/example/documents/file_{index}.txt",
            "name": f"file_{index}.txt",
        }
        for index in range(3)
    ]

    file_ids = file_repo.save_files_batch(files)

    connection = get_connection(test_database)

    try:
        for index, file_id in enumerate(file_ids):
            row = connection.execute(
                "SELECT path FROM Files WHERE file_id = ?",
                (file_id,),
            ).fetchone()

            assert row is not None
            assert row["path"] == files[index]["path"]

    finally:
        connection.close()


def test_save_files_batch_rolls_back_on_duplicate(
    test_database,
    sample_metadata,
):
    """
    Verify that one failed insertion rolls back the entire batch.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Base metadata for insertion.

    Returns:
        None: The test passes when no partial records remain.
    """
    first_file = sample_metadata.copy()

    duplicate_file = {
        **sample_metadata,
        "size": 999,
    }

    # Both files have the same scan_id and path.
    # This violates UNIQUE(scan_id, path).
    with pytest.raises(sqlite3.IntegrityError):
        file_repo.save_files_batch([first_file, duplicate_file])

    saved_files = file_repo.get_files_by_scan(sample_metadata["scan_id"])

    assert saved_files == []


def test_save_files_batch_empty_list(test_database):
    """
    Verify that saving an empty batch is handled safely.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when no IDs are returned.
    """
    file_ids = file_repo.save_files_batch([])

    assert file_ids == []


def test_save_files_batch_rejects_invalid_metadata(
    test_database,
    sample_metadata,
):
    """
    Verify that invalid metadata does not leave partial records.

    Args:
        test_database (Path): Initialized temporary database.
        sample_metadata (dict): Base metadata for insertion.

    Returns:
        None: The test passes when validation rejects the batch.
    """
    invalid_file = {
        **sample_metadata,
        "path": "/example/documents/invalid.txt",
        "name": "invalid.txt",
        "size": -100,
    }

    with pytest.raises((TypeError, ValueError)):
        file_repo.save_files_batch([
            sample_metadata,
            invalid_file,
        ])

    # The valid first file must not remain after failure.
    saved_files = file_repo.get_files_by_scan(sample_metadata["scan_id"])

    assert saved_files == []


def test_save_files_batch_shared_connection_does_not_commit(
    test_database,
    sample_metadata,
):
    """
    Verify that a batch using a caller-provided connection
    does not commit automatically.
    """

    connection = get_connection(test_database)

    try:
        connection.execute("BEGIN")

        file_ids = file_repo.save_files_batch(
            [sample_metadata],
            connection=connection,
        )

        assert len(file_ids) == 1

        # The inserted file is visible inside its own transaction.
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM Files WHERE scan_id = ?",
            (sample_metadata["scan_id"],),
        ).fetchone()

        assert row["count"] == 1

        # A separate connection cannot see uncommitted inserts.
        other_connection = get_connection(test_database)

        try:
            other_row = other_connection.execute(
                "SELECT COUNT(*) AS count FROM Files WHERE scan_id = ?",
                (sample_metadata["scan_id"],),
            ).fetchone()

            assert other_row["count"] == 0

        finally:
            other_connection.close()

        # The caller can discard the batch.
        connection.rollback()

        assert file_repo.get_files_by_scan(
            sample_metadata["scan_id"]
        ) == []

    finally:
        connection.close()


def test_save_files_batch_shared_connection_caller_commits(
    test_database,
    sample_metadata,
):
    """
    Verify that a caller can commit files inserted through
    a shared connection.
    """

    connection = get_connection(test_database)

    try:
        connection.execute("BEGIN")

        file_ids = file_repo.save_files_batch(
            [sample_metadata],
            connection=connection,
        )

        assert len(file_ids) == 1

        # The caller, not save_files_batch(), commits.
        connection.commit()

        saved_files = file_repo.get_files_by_scan(
            sample_metadata["scan_id"]
        )

        assert len(saved_files) == 1
        assert saved_files[0].file_id == file_ids[0]

    finally:
        connection.close()


def test_save_files_batch_shared_connection_failure(
    test_database,
    sample_metadata,
):
    """
    Verify that a failed shared batch leaves rollback
    responsibility with the caller.
    """

    first_file = sample_metadata.copy()

    second_file = {
        **sample_metadata,
        "path": "/example/documents/notes.txt",
        "name": "notes.txt",
    }

    # Duplicate the first file's path to trigger a constraint error.
    third_file = sample_metadata.copy()

    connection = get_connection(test_database)

    try:
        connection.execute("BEGIN")

        with pytest.raises(sqlite3.IntegrityError):
            file_repo.save_files_batch(
                [first_file, second_file, third_file],
                connection=connection,
            )

        # The caller rolls back every insertion.
        connection.rollback()

        saved_files = file_repo.get_files_by_scan(
            sample_metadata["scan_id"]
        )

        assert saved_files == []

    finally:
        connection.close()


def test_save_files_batch_preserves_inaccessible_file(
    test_database,
    sample_metadata,
):
    """
    Verify that batch insertion preserves inaccessible
    files with unknown sizes and error messages.
    """

    inaccessible_file = {
        **sample_metadata,
        "size": None,
        "accessible": False,
        "error": "Permission denied",
    }

    file_ids = file_repo.save_files_batch([inaccessible_file])

    assert len(file_ids) == 1

    saved_files = file_repo.get_files_by_scan(
        sample_metadata["scan_id"]
    )

    assert len(saved_files) == 1
    assert saved_files[0].size is None
    assert saved_files[0].accessible is False
    assert saved_files[0].error == "Permission denied"



def test_save_file_metadata_with_custom_database_path(
    tmp_path,
    monkeypatch
):
    """
    Verify that file metadata is saved to a custom SQLite database.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest fixture for replacing dependencies.

    Returns:
        None: Assertions verify the saved file.
    """

    from src.data_access.connection import (
        initialize_database,
        get_connection,
    )

    # Create a separate database for this test.
    custom_path = tmp_path / "custom_files.db"
    initialize_database(custom_path)

    # Restore the real connection function for this test.
    monkeypatch.setattr(scan_repo, "get_connection", get_connection)
    monkeypatch.setattr(file_repo, "get_connection", get_connection)

    # Create a scan in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Save file metadata to the custom database.
    file_id = file_repo.save_file_metadata(
        {
            "scan_id": scan_id,
            "path": "/example/report.pdf",
            "name": "report.pdf",
            "size": 1024,
            "extension": ".pdf",
            "category": "Documents",
            "accessible": True,
        },
        database_path=custom_path,
    )

    # Verify the saved file using a separate connection.
    connection = get_connection(custom_path)

    try:
        row = connection.execute(
            "SELECT * FROM Files WHERE file_id = ?",
            (file_id,),
        ).fetchone()

        assert row is not None
        assert row["path"] == "/example/report.pdf"
        assert row["name"] == "report.pdf"
        assert row["size"] == 1024

    finally:
        connection.close()


def test_save_files_batch_with_custom_database_path(tmp_path):
    """
    Verify that a batch is saved to a custom SQLite database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify both saved files.
    """

    from src.data_access.connection import (
        initialize_database,
        get_connection,
    )

    # Create an isolated database.
    custom_path = tmp_path / "custom_batch.db"
    initialize_database(custom_path)

    # Create a scan using the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Save two files in one transaction.
    file_ids = file_repo.save_files_batch(
        [
            {
                "scan_id": scan_id,
                "path": "/example/a.txt",
                "name": "a.txt",
                "size": 100,
            },
            {
                "scan_id": scan_id,
                "path": "/example/b.txt",
                "name": "b.txt",
                "size": 200,
            },
        ],
        database_path=custom_path,
    )

    assert len(file_ids) == 2

    # Confirm both files were committed.
    connection = get_connection(custom_path)

    try:
        rows = connection.execute(
            """
            SELECT path
            FROM Files
            WHERE scan_id = ?
            ORDER BY path
            """,
            (scan_id,),
        ).fetchall()

        assert [row["path"] for row in rows] == [
            "/example/a.txt",
            "/example/b.txt",
        ]

    finally:
        connection.close()


def test_save_file_hash_with_custom_database_path(tmp_path):
    """
    Verify that a file hash is saved to a custom SQLite database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the stored hash.
    """

    from src.data_access.connection import (
        initialize_database,
        get_connection,
    )

    # Create a separate temporary database.
    custom_path = tmp_path / "custom_hashes.db"
    initialize_database(custom_path)

    # Create a scan and file in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    file_id = file_repo.save_file_metadata(
        {
            "scan_id": scan_id,
            "path": "/example/report.pdf",
            "name": "report.pdf",
            "size": 1024,
        },
        database_path=custom_path,
    )

    # Save the hash to the same database.
    hash_id = file_repo.save_file_hash(
        file_id,
        "abc123",
        "sha256",
        database_path=custom_path,
    )

    # Verify the hash using a separate connection.
    connection = get_connection(custom_path)

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
        assert row["hash_value"] == "abc123"
        assert row["hash_algorithm"] == "sha256"

    finally:
        connection.close()


def test_get_files_by_scan_with_custom_database_path(tmp_path):
    """
    Verify that files are retrieved from a custom database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the retrieved files.
    """

    from src.data_access.connection import initialize_database

    # Create an independent temporary database.
    custom_path = tmp_path / "custom_scan_files.db"
    initialize_database(custom_path)

    # Create a scan in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Save files in reverse alphabetical order.
    file_repo.save_files_batch(
        [
            {
                "scan_id": scan_id,
                "path": "/example/b.txt",
                "name": "b.txt",
                "size": 200,
            },
            {
                "scan_id": scan_id,
                "path": "/example/a.txt",
                "name": "a.txt",
                "size": 100,
            },
        ],
        database_path=custom_path,
    )

    # Retrieve files using the custom database path.
    files = file_repo.get_files_by_scan(
        scan_id,
        database_path=custom_path,
    )

    assert len(files) == 2
    assert [file.path for file in files] == [
        "/example/a.txt",
        "/example/b.txt",
    ]



def test_get_files_by_extension_with_custom_database_path(tmp_path):
    """
    Verify extension filtering using a custom SQLite database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the matching files.
    """

    from src.data_access.connection import initialize_database

    # Create a separate temporary database.
    custom_path = tmp_path / "custom_extensions.db"
    initialize_database(custom_path)

    # Create a scan in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Save files with different extensions.
    file_repo.save_files_batch(
        [
            {
                "scan_id": scan_id,
                "path": "/example/report.PDF",
                "name": "report.PDF",
                "extension": ".PDF",
                "size": 100,
            },
            {
                "scan_id": scan_id,
                "path": "/example/notes.txt",
                "name": "notes.txt",
                "extension": ".txt",
                "size": 200,
            },
        ],
        database_path=custom_path,
    )

    # Search using an extension without a leading dot.
    files = file_repo.get_files_by_extension(
        scan_id,
        "pdf",
        database_path=custom_path,
    )

    assert len(files) == 1
    assert files[0].name == "report.PDF"
    assert files[0].extension == ".PDF"



def test_get_largest_files_with_custom_database_path(tmp_path):
    """
    Verify largest-file retrieval from a custom SQLite database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify file ordering and limits.
    """

    from src.data_access.connection import initialize_database

    # Create an independent temporary database.
    custom_path = tmp_path / "custom_largest.db"
    initialize_database(custom_path)

    # Create a scan in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Save files with different sizes.
    file_repo.save_files_batch(
        [
            {
                "scan_id": scan_id,
                "path": "/example/small.txt",
                "name": "small.txt",
                "size": 100,
            },
            {
                "scan_id": scan_id,
                "path": "/example/large.txt",
                "name": "large.txt",
                "size": 1000,
            },
            {
                "scan_id": scan_id,
                "path": "/example/medium.txt",
                "name": "medium.txt",
                "size": 500,
            },
            {
                "scan_id": scan_id,
                "path": "/example/unknown.txt",
                "name": "unknown.txt",
                "size": None,
            },
        ],
        database_path=custom_path,
    )

    # Retrieve only the two largest files.
    files = file_repo.get_largest_files(
        scan_id,
        limit=2,
        database_path=custom_path,
    )

    assert len(files) == 2
    assert [file.name for file in files] == [
        "large.txt",
        "medium.txt",
    ]
    assert [file.size for file in files] == [1000, 500]


def test_get_total_storage_with_custom_database_path(tmp_path):
    """
    Verify total storage calculation using a custom database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the total storage.
    """

    from src.data_access.connection import initialize_database

    # Create a separate temporary database.
    custom_path = tmp_path / "custom_storage.db"
    initialize_database(custom_path)

    # Create a scan in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Save files with known and unknown sizes.
    file_repo.save_files_batch(
        [
            {
                "scan_id": scan_id,
                "path": "/example/a.txt",
                "name": "a.txt",
                "size": 100,
            },
            {
                "scan_id": scan_id,
                "path": "/example/b.txt",
                "name": "b.txt",
                "size": 250,
            },
            {
                "scan_id": scan_id,
                "path": "/example/c.txt",
                "name": "c.txt",
                "size": None,
            },
        ],
        database_path=custom_path,
    )

    # Unknown file sizes should not affect the total.
    total = file_repo.get_total_storage(
        scan_id,
        database_path=custom_path,
    )

    assert total == 350
