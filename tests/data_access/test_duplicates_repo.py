
import sqlite3

import pytest

from src.data_access import (
    duplicates_repo,
    file_repo,
    scan_repo,
)
from src.data_access.connection import (
    get_connection,
    initialize_database,
)
from src.data_access.models import (
    DuplicateGroup,
    FileMetadata,
)


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    """
    Create an isolated SQLite database for duplicate repository tests.

    All three repositories must use the same temporary database
    because duplicate groups reference files, and files reference scans.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        monkeypatch (pytest.MonkeyPatch): Replaces repository connections.

    Returns:
        Path: Path to the initialized temporary database.
    """

    database_path = tmp_path / "test_duplicates.db"

    # Create all five tables in a fresh temporary database.
    initialize_database(database_path)

    # Redirect each repository to the same temporary database.
    def temporary_connection():
        return get_connection(database_path)

    monkeypatch.setattr(
        scan_repo,
        "get_connection",
        temporary_connection,
    )

    monkeypatch.setattr(
        file_repo,
        "get_connection",
        temporary_connection,
    )

    monkeypatch.setattr(
        duplicates_repo,
        "get_connection",
        temporary_connection,
    )

    return database_path


@pytest.fixture
def sample_files(test_database):
    """
    Create a scan containing three files for duplicate testing.

    The first two files represent duplicates. The third file
    represents an unrelated file.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        dict: Scan ID and generated file IDs.
    """

    # Every file must belong to an existing scan.
    scan_id = scan_repo.create_scan("/example/documents")

    files = [
        {
            "path": "/example/documents/report.pdf",
            "name": "report.pdf",
            "size": 2048,
        },
        {
            "path": "/example/documents/report_copy.pdf",
            "name": "report_copy.pdf",
            "size": 2048,
        },
        {
            "path": "/example/documents/notes.txt",
            "name": "notes.txt",
            "size": 500,
        },
    ]

    file_ids = []

    for file in files:
        # Save metadata using the same field names as the scanner.
        metadata = {
            "scan_id": scan_id,
            "path": file["path"],
            "name": file["name"],
            "size": file["size"],
            "extension": ".pdf" if file["name"].endswith(".pdf") else ".txt",
            "category": "Documents",
            "created": "2026-10-17T10:00:00",
            "modified": "2026-10-17T11:00:00",
            "accessible": True,
            "error": None,
        }

        file_id = file_repo.save_file_metadata(metadata)
        file_ids.append(file_id)

    return {
        "scan_id": scan_id,
        "first_file_id": file_ids[0],
        "second_file_id": file_ids[1],
        "third_file_id": file_ids[2],
    }


@pytest.fixture
def duplicate_group(sample_files):
    """
    Create a duplicate group containing two files.

    Args:
        sample_files (dict): Existing scan and file IDs.

    Returns:
        int: ID of the created duplicate group.
    """

    # This is a sample hash, not a hash computed from real files.
    hash_value = "a" * 64

    group_id = duplicates_repo.create_duplicate_group(
        hash_value=hash_value,
        duplicate_count=2,
        potential_savings=2048,
    )

    # Mark the first file as the representative file.
    duplicates_repo.add_duplicate_member(
        group_id=group_id,
        file_id=sample_files["first_file_id"],
        is_primary=True,
    )

    duplicates_repo.add_duplicate_member(
        group_id=group_id,
        file_id=sample_files["second_file_id"],
        is_primary=False,
    )

    return group_id


def test_create_duplicate_group(test_database):
    """
    Verify that a duplicate group is inserted correctly.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when the stored values match.
    """

    group_id = duplicates_repo.create_duplicate_group(
        hash_value="a" * 64,
        duplicate_count=2,
        potential_savings=2048,
    )

    assert isinstance(group_id, int)
    assert group_id > 0

    # Inspect the database directly to verify the inserted record.
    connection = get_connection(test_database)

    try:
        row = connection.execute(
            """
            SELECT *
            FROM DuplicateGroups
            WHERE group_id = ?
            """,
            (group_id,),
        ).fetchone()

        assert row is not None
        assert row["hash_value"] == "a" * 64
        assert row["duplicate_count"] == 2
        assert row["potential_savings"] == 2048

    finally:
        connection.close()


def test_add_duplicate_member(test_database, sample_files):
    """
    Verify that files can be associated with duplicate groups.

    Args:
        test_database (Path): Initialized temporary database.
        sample_files (dict): Existing file IDs.

    Returns:
        None: The test passes when membership is saved correctly.
    """

    group_id = duplicates_repo.create_duplicate_group(
        "a" * 64,
        2,
        2048,
    )

    duplicates_repo.add_duplicate_member(
        group_id,
        sample_files["first_file_id"],
        is_primary=True,
    )

    connection = get_connection(test_database)

    try:
        row = connection.execute(
            """
            SELECT group_id, file_id, is_primary
            FROM DuplicateMembers
            WHERE group_id = ? AND file_id = ?
            """,
            (group_id, sample_files["first_file_id"]),
        ).fetchone()

        assert row is not None
        assert row["group_id"] == group_id
        assert row["file_id"] == sample_files["first_file_id"]
        assert row["is_primary"] == 1

    finally:
        connection.close()


def test_get_duplicate_groups(sample_files, duplicate_group):
    """
    Verify that duplicate groups can be retrieved by scan ID.

    Args:
        sample_files (dict): Existing scan and file IDs.
        duplicate_group (int): ID of a populated duplicate group.

    Returns:
        None: The test passes when the correct group is returned.
    """

    groups = duplicates_repo.get_duplicate_groups(
        sample_files["scan_id"]
    )

    assert len(groups) == 1
    assert isinstance(groups[0], DuplicateGroup)

    assert groups[0].group_id == duplicate_group
    assert groups[0].duplicate_count == 2
    assert groups[0].potential_savings == 2048


def test_get_duplicate_members(sample_files, duplicate_group):
    """
    Verify that duplicate members are returned as dataclasses.

    Args:
        sample_files (dict): Existing file IDs.
        duplicate_group (int): ID of the populated group.

    Returns:
        None: The test passes when both members are returned.
    """

    members = duplicates_repo.get_duplicate_members(duplicate_group)

    assert len(members) == 2

    # The repository should return FileMetadata objects.
    assert all(isinstance(member, FileMetadata) for member in members)

    member_ids = {member.file_id for member in members}

    assert member_ids == {
        sample_files["first_file_id"],
        sample_files["second_file_id"],
    }

    # The primary file should appear first.
    assert members[0].file_id == sample_files["first_file_id"]


def test_duplicate_group_excludes_unrelated_files(
    sample_files,
    duplicate_group,
):
    """
    Verify that unrelated files are not returned as duplicate members.

    Args:
        sample_files (dict): Existing file IDs.
        duplicate_group (int): ID of the populated group.

    Returns:
        None: The test passes when unrelated files are excluded.
    """

    members = duplicates_repo.get_duplicate_members(duplicate_group)

    member_ids = {member.file_id for member in members}

    assert sample_files["third_file_id"] not in member_ids


def test_get_groups_for_nonexistent_scan(test_database):
    """
    Verify that unknown scans return an empty duplicate-group list.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when an empty list is returned.
    """

    groups = duplicates_repo.get_duplicate_groups(999)

    assert groups == []


def test_get_members_for_nonexistent_group(test_database):
    """
    Verify that unknown duplicate groups return an empty list.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: The test passes when an empty list is returned.
    """

    members = duplicates_repo.get_duplicate_members(999)

    assert members == []


def test_duplicate_membership_cannot_be_repeated(
    sample_files,
    duplicate_group,
):
    """
    Verify that a file cannot be added twice to the same group.

    Args:
        sample_files (dict): Existing file IDs.
        duplicate_group (int): ID of the populated group.

    Returns:
        None: The test passes when duplicate membership is rejected.
    """

    # The composite primary key (group_id, file_id)
    # prevents duplicate membership records.
    with pytest.raises(sqlite3.IntegrityError):
        duplicates_repo.add_duplicate_member(
            duplicate_group,
            sample_files["first_file_id"],
        )


def test_add_member_rejects_nonexistent_file(
    test_database,
    duplicate_group,
):
    """
    Verify that a nonexistent file cannot join a duplicate group.

    Args:
        test_database (Path): Initialized temporary database.
        duplicate_group (int): Existing duplicate group ID.

    Returns:
        None: The test passes when the foreign key rejects the file.
    """

    with pytest.raises(sqlite3.IntegrityError):
        duplicates_repo.add_duplicate_member(
            duplicate_group,
            file_id=999,
        )


@pytest.mark.parametrize(
    "invalid_count",
    [0, 1, -1, "two", True],
)
def test_create_group_rejects_invalid_count(
    test_database,
    invalid_count,
):
    """
    Verify that duplicate groups require at least two files.

    Args:
        test_database (Path): Initialized temporary database.
        invalid_count: Invalid duplicate count.

    Returns:
        None: The test passes when invalid values are rejected.
    """

    with pytest.raises(ValueError):
        duplicates_repo.create_duplicate_group(
            hash_value="a" * 64,
            duplicate_count=invalid_count,
            potential_savings=2048,
        )


@pytest.mark.parametrize(
    "invalid_savings",
    [-1, "large", True],
)
def test_create_group_rejects_invalid_savings(
    test_database,
    invalid_savings,
):
    """
    Verify that potential savings cannot be negative or non-integer.

    Args:
        test_database (Path): Initialized temporary database.
        invalid_savings: Invalid potential-savings value.

    Returns:
        None: The test passes when invalid values are rejected.
    """

    with pytest.raises(ValueError):
        duplicates_repo.create_duplicate_group(
            hash_value="a" * 64,
            duplicate_count=2,
            potential_savings=invalid_savings,
        )


def test_add_member_rejects_invalid_primary_flag(
    sample_files,
    duplicate_group,
):
    """
    Verify that is_primary must be a Python boolean.

    Args:
        sample_files (dict): Existing file IDs.
        duplicate_group (int): Existing duplicate group ID.

    Returns:
        None: The test passes when an invalid flag is rejected.
    """

    with pytest.raises(TypeError):
        duplicates_repo.add_duplicate_member(
            duplicate_group,
            sample_files["third_file_id"],
            is_primary=1,
        )
