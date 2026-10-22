
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

    All three repositories use the same temporary database because
    duplicate groups reference files, and files reference scans.

    Args:
        tmp_path (Path): Temporary directory provided by pytest.
        monkeypatch (pytest.MonkeyPatch): Temporarily replaces
            repository connection functions.

    Returns:
        Path: Path to the initialized temporary database.
    """
    database_path = tmp_path / "test_duplicates.db"

    # Initialize a fresh database using the latest schema.
    initialize_database(database_path)

    def temporary_connection():
        """Connect to the temporary test database."""
        return get_connection(database_path)

    # Prevent repository functions from accessing smart_files.db.
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
    Create one scan containing three sample files.

    The first two represent duplicates. The third is unrelated.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        dict: Scan ID and the three generated file IDs.
    """
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

    for file_data in files:
        # Build metadata matching the file repository's input format.
        metadata = {
            "scan_id": scan_id,
            "path": file_data["path"],
            "name": file_data["name"],
            "size": file_data["size"],
            "extension": (
                ".pdf"
                if file_data["name"].endswith(".pdf")
                else ".txt"
            ),
            "category": "Documents",
            "created": "2026-10-17T10:00:00",
            "modified": "2026-10-17T11:00:00",
            "accessed_timestamp": None,
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
    Create a duplicate group with two members.

    Args:
        sample_files (dict): Existing scan and file IDs.

    Returns:
        int: ID of the populated duplicate group.
    """
    group_id = duplicates_repo.create_duplicate_group(
        scan_id=sample_files["scan_id"],
        hash_value="a" * 64,
        duplicate_count=2,
        potential_savings=2048,
    )

    # The original file is the representative member.
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
    Verify that duplicate groups are stored with their scan IDs.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: Passes when the stored values match the input.
    """
    scan_id = scan_repo.create_scan("/example/documents")

    group_id = duplicates_repo.create_duplicate_group(
        scan_id=scan_id,
        hash_value="a" * 64,
        duplicate_count=2,
        potential_savings=2048,
    )

    assert isinstance(group_id, int)
    assert group_id > 0

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
        assert row["scan_id"] == scan_id
        assert row["hash_value"] == "a" * 64
        assert row["duplicate_count"] == 2
        assert row["potential_savings"] == 2048

    finally:
        connection.close()


def test_add_duplicate_member(test_database, sample_files):
    """
    Verify that a file can be added to a duplicate group.

    Args:
        test_database (Path): Initialized temporary database.
        sample_files (dict): Existing scan and file IDs.

    Returns:
        None: Passes when membership is stored correctly.
    """
    group_id = duplicates_repo.create_duplicate_group(
        scan_id=sample_files["scan_id"],
        hash_value="a" * 64,
        duplicate_count=2,
        potential_savings=2048,
    )

    duplicates_repo.add_duplicate_member(
        group_id=group_id,
        file_id=sample_files["first_file_id"],
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
    Verify that duplicate groups are returned as dataclasses.

    Args:
        sample_files (dict): Existing scan and file IDs.
        duplicate_group (int): Existing duplicate group ID.

    Returns:
        None: Passes when the correct group is returned.
    """
    groups = duplicates_repo.get_duplicate_groups(
        sample_files["scan_id"]
    )

    assert len(groups) == 1
    assert isinstance(groups[0], DuplicateGroup)

    assert groups[0].group_id == duplicate_group
    assert groups[0].scan_id == sample_files["scan_id"]
    assert groups[0].hash_value == "a" * 64
    assert groups[0].duplicate_count == 2
    assert groups[0].potential_savings == 2048


def test_create_group_shared_connection_does_not_commit(
    test_database,
):
    """
    Verify that creating a duplicate group with a shared
    connection leaves the transaction under caller control.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: Passes when the group remains uncommitted and
            the caller can roll back the insertion.
    """

    scan_id = scan_repo.create_scan("/example/documents")

    connection = get_connection(test_database)

    try:
        connection.execute("BEGIN")

        group_id = duplicates_repo.create_duplicate_group(
            scan_id=scan_id,
            hash_value="a" * 64,
            duplicate_count=2,
            potential_savings=2048,
            connection=connection,
        )

        assert isinstance(group_id, int)

        # The group exists inside the caller's transaction.
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM DuplicateGroups WHERE group_id = ?",
            (group_id,),
        ).fetchone()

        assert row["count"] == 1

        # A separate connection cannot see the uncommitted group.
        other_connection = get_connection(test_database)

        try:
            other_row = other_connection.execute(
                "SELECT COUNT(*) AS count FROM DuplicateGroups WHERE group_id = ?",
                (group_id,),
            ).fetchone()

            assert other_row["count"] == 0

        finally:
            other_connection.close()

        # The caller can discard the new group.
        connection.rollback()

        assert duplicates_repo.get_duplicate_groups(scan_id) == []

    finally:
        connection.close()



def test_add_member_shared_connection_does_not_commit(
    test_database,
    sample_files,
):
    """
    Verify that adding a duplicate member with a shared
    connection does not commit the caller's transaction.

    Args:
        test_database (Path): Initialized temporary database.
        sample_files (dict): Existing scan and file IDs.

    Returns:
        None: Passes when the membership remains uncommitted
            and the caller can roll back the insertion.
    """

    group_id = duplicates_repo.create_duplicate_group(
        scan_id=sample_files["scan_id"],
        hash_value="a" * 64,
        duplicate_count=2,
        potential_savings=2048,
    )

    connection = get_connection(test_database)

    try:
        connection.execute("BEGIN")

        duplicates_repo.add_duplicate_member(
            group_id=group_id,
            file_id=sample_files["first_file_id"],
            is_primary=True,
            connection=connection,
        )

        # The membership exists inside the caller's transaction.
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM DuplicateMembers WHERE group_id = ?",
            (group_id,),
        ).fetchone()

        assert row["count"] == 1

        # A separate connection cannot see the uncommitted member.
        other_connection = get_connection(test_database)

        try:
            other_row = other_connection.execute(
                "SELECT COUNT(*) AS count FROM DuplicateMembers WHERE group_id = ?",
                (group_id,),
            ).fetchone()

            assert other_row["count"] == 0

        finally:
            other_connection.close()

        # The caller can roll back the membership insertion.
        connection.rollback()

        assert duplicates_repo.get_duplicate_members(group_id) == []

    finally:
        connection.close()



def test_add_member_shared_connection_failure_leaves_rollback_to_caller(
    test_database,
    sample_files,
):
    """
    Verify that a failed shared membership insertion
    does not roll back earlier work in the transaction.

    Args:
        test_database (Path): Initialized temporary database.
        sample_files (dict): Existing scan and file IDs.

    Returns:
        None: Passes when earlier changes remain pending after
            the failure and the caller can roll them back.
    """

    connection = get_connection(test_database)

    try:
        connection.execute("BEGIN")

        # Create a group within the caller's transaction.
        group_id = duplicates_repo.create_duplicate_group(
            scan_id=sample_files["scan_id"],
            hash_value="a" * 64,
            duplicate_count=2,
            potential_savings=2048,
            connection=connection,
        )

        # An unknown file ID must cause an integrity error.
        with pytest.raises(sqlite3.IntegrityError):
            duplicates_repo.add_duplicate_member(
                group_id=group_id,
                file_id=999999,
                connection=connection,
            )

        # The earlier group insertion must still be pending.
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM DuplicateGroups WHERE group_id = ?",
            (group_id,),
        ).fetchone()

        assert row["count"] == 1

        # The caller decides to roll back the entire transaction.
        connection.rollback()

        assert duplicates_repo.get_duplicate_groups(
            sample_files["scan_id"]
        ) == []

    finally:
        connection.close()



def test_get_duplicate_members(sample_files, duplicate_group):
    """
    Verify that duplicate members are returned as FileMetadata objects.

    Args:
        sample_files (dict): Existing file IDs.
        duplicate_group (int): Existing duplicate group ID.

    Returns:
        None: Passes when both members are returned correctly.
    """
    members = duplicates_repo.get_duplicate_members(duplicate_group)

    assert len(members) == 2
    assert all(isinstance(member, FileMetadata) for member in members)

    member_ids = {member.file_id for member in members}

    assert member_ids == {
        sample_files["first_file_id"],
        sample_files["second_file_id"],
    }

    # The representative file should appear first.
    assert members[0].file_id == sample_files["first_file_id"]


def test_duplicate_group_excludes_unrelated_files(
    sample_files,
    duplicate_group,
):
    """
    Verify that unrelated files are excluded from duplicate groups.

    Args:
        sample_files (dict): Existing file IDs.
        duplicate_group (int): Existing duplicate group ID.

    Returns:
        None: Passes when the unrelated file is absent.
    """
    members = duplicates_repo.get_duplicate_members(duplicate_group)

    member_ids = {member.file_id for member in members}

    assert sample_files["third_file_id"] not in member_ids


def test_get_groups_for_nonexistent_scan(test_database):
    """
    Verify that requesting groups for an unknown scan returns [].

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: Passes when no groups are returned.
    """
    groups = duplicates_repo.get_duplicate_groups(999)

    assert groups == []


def test_get_members_for_nonexistent_group(test_database):
    """
    Verify that requesting members of an unknown group returns [].

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: Passes when no members are returned.
    """
    members = duplicates_repo.get_duplicate_members(999)

    assert members == []


def test_duplicate_membership_cannot_be_repeated(
    sample_files,
    duplicate_group,
):
    """
    Verify that duplicate membership cannot be inserted twice.

    Args:
        sample_files (dict): Existing file IDs.
        duplicate_group (int): Existing duplicate group ID.

    Returns:
        None: Passes when SQLite rejects duplicate membership.
    """
    # The composite primary key prevents duplicate group/file pairs.
    with pytest.raises(sqlite3.IntegrityError):
        duplicates_repo.add_duplicate_member(
            group_id=duplicate_group,
            file_id=sample_files["first_file_id"],
        )


def test_add_member_rejects_nonexistent_file(
    test_database,
    duplicate_group,
):
    """
    Verify that nonexistent files cannot join duplicate groups.

    Args:
        test_database (Path): Initialized temporary database.
        duplicate_group (int): Existing duplicate group ID.

    Returns:
        None: Passes when foreign-key enforcement rejects the file.
    """
    with pytest.raises(sqlite3.IntegrityError):
        duplicates_repo.add_duplicate_member(
            group_id=duplicate_group,
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
        invalid_count: Invalid duplicate-count value.

    Returns:
        None: Passes when invalid counts are rejected.
    """
    scan_id = scan_repo.create_scan("/example/documents")

    with pytest.raises(ValueError):
        duplicates_repo.create_duplicate_group(
            scan_id=scan_id,
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
    Verify that potential savings must be a nonnegative integer.

    Args:
        test_database (Path): Initialized temporary database.
        invalid_savings: Invalid potential-savings value.

    Returns:
        None: Passes when invalid values are rejected.
    """
    scan_id = scan_repo.create_scan("/example/documents")

    with pytest.raises(ValueError):
        duplicates_repo.create_duplicate_group(
            scan_id=scan_id,
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
        None: Passes when an invalid primary flag is rejected.
    """
    with pytest.raises(TypeError):
        duplicates_repo.add_duplicate_member(
            group_id=duplicate_group,
            file_id=sample_files["third_file_id"],
            is_primary=1,
        )


def test_add_member_rejects_file_from_different_scan(
    test_database,
    sample_files,
):
    """
    Verify that duplicate groups cannot contain files from another scan.

    Args:
        test_database (Path): Initialized temporary database.
        sample_files (dict): Files belonging to the first scan.

    Returns:
        None: Passes when cross-scan membership is rejected.
    """
    group_id = duplicates_repo.create_duplicate_group(
        scan_id=sample_files["scan_id"],
        hash_value="a" * 64,
        duplicate_count=2,
        potential_savings=2048,
    )

    # Create an unrelated scan and a file belonging to it.
    second_scan_id = scan_repo.create_scan("/example/other")

    other_file_id = file_repo.save_file_metadata({
        "scan_id": second_scan_id,
        "path": "/example/other/file.txt",
        "name": "file.txt",
        "size": 100,
        "extension": ".txt",
        "category": "Documents",
        "created": None,
        "modified": None,
        "accessed_timestamp": None,
        "accessible": True,
        "error": None,
    })

    # A file from another scan must not be added to this group.
    with pytest.raises(ValueError):
        duplicates_repo.add_duplicate_member(
            group_id=group_id,
            file_id=other_file_id,
        )

    assert duplicates_repo.get_duplicate_members(group_id) == []


def test_get_duplicate_groups_only_returns_requested_scan(
    test_database,
):
    """
    Verify that duplicate groups are isolated by scan.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: Passes when each scan retrieves only its own groups.
    """
    first_scan = scan_repo.create_scan("/example/first")
    second_scan = scan_repo.create_scan("/example/second")

    first_group = duplicates_repo.create_duplicate_group(
        scan_id=first_scan,
        hash_value="a" * 64,
        duplicate_count=2,
        potential_savings=100,
    )

    second_group = duplicates_repo.create_duplicate_group(
        scan_id=second_scan,
        hash_value="b" * 64,
        duplicate_count=2,
        potential_savings=200,
    )

    first_results = duplicates_repo.get_duplicate_groups(first_scan)
    second_results = duplicates_repo.get_duplicate_groups(second_scan)

    assert [group.group_id for group in first_results] == [first_group]
    assert [group.group_id for group in second_results] == [second_group]

    assert first_results[0].scan_id == first_scan
    assert second_results[0].scan_id == second_scan


def test_create_group_rejects_nonexistent_scan(test_database):
    """
    Verify that a duplicate group cannot reference an unknown scan.

    Args:
        test_database (Path): Initialized temporary database.

    Returns:
        None: Passes when SQLite rejects the nonexistent scan.
    """
    with pytest.raises(sqlite3.IntegrityError):
        duplicates_repo.create_duplicate_group(
            scan_id=999,
            hash_value="a" * 64,
            duplicate_count=2,
            potential_savings=100,
        )


def test_deleting_scan_cascades_to_duplicate_records(
    test_database,
    sample_files,
    duplicate_group,
):
    """
    Verify that deleting a scan removes its related records.

    Args:
        test_database (Path): Initialized temporary database.
        sample_files (dict): Existing scan and file IDs.
        duplicate_group (int): Existing duplicate group ID.

    Returns:
        None: Passes when cascading deletion removes all child records.
    """
    connection = get_connection(test_database)

    try:
        # Foreign keys are enabled by get_connection().
        # Deleting the parent scan should delete dependent records.
        connection.execute(
            "DELETE FROM Scans WHERE scan_id = ?",
            (sample_files["scan_id"],),
        )
        connection.commit()

        # All tables should now be empty.
        for table in (
            "Scans",
            "Files",
            "DuplicateGroups",
            "DuplicateMembers",
        ):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            assert count == 0, f"{table} still contains records"

    finally:
        connection.close()


def test_create_duplicate_group_with_custom_database_path(tmp_path):
    """
    Verify duplicate group creation in a custom SQLite database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the saved duplicate group.
    """

    from src.data_access.connection import (
        initialize_database,
        get_connection,
    )

    # Create a separate temporary database.
    custom_path = tmp_path / "custom_duplicates.db"
    initialize_database(custom_path)

    # Create a scan in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Create a duplicate group in the same database.
    group_id = duplicates_repo.create_duplicate_group(
        scan_id,
        "abc123",
        2,
        1024,
        database_path=custom_path,
    )

    # Verify the saved group using a separate connection.
    connection = get_connection(custom_path)

    try:
        row = connection.execute(
            """
            SELECT scan_id, hash_value, duplicate_count, potential_savings
            FROM DuplicateGroups
            WHERE group_id = ?
            """,
            (group_id,),
        ).fetchone()

        assert row is not None
        assert row["scan_id"] == scan_id
        assert row["hash_value"] == "abc123"
        assert row["duplicate_count"] == 2
        assert row["potential_savings"] == 1024

    finally:
        connection.close()


def test_add_duplicate_member_with_custom_database_path(tmp_path):
    """
    Verify duplicate membership in a custom SQLite database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the saved membership.
    """

    from src.data_access.connection import (
        initialize_database,
        get_connection,
    )

    # Create a separate temporary database.
    custom_path = tmp_path / "custom_members.db"
    initialize_database(custom_path)

    # Create a scan and file in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    file_id = file_repo.save_file_metadata(
        {
            "scan_id": scan_id,
            "path": "/example/copy.txt",
            "name": "copy.txt",
            "size": 100,
        },
        database_path=custom_path,
    )

    # Create a duplicate group in the same database.
    group_id = duplicates_repo.create_duplicate_group(
        scan_id,
        "abc123",
        2,
        100,
        database_path=custom_path,
    )

    # Add the file as the group's primary member.
    duplicates_repo.add_duplicate_member(
        group_id,
        file_id,
        is_primary=True,
        database_path=custom_path,
    )

    # Verify the membership using a separate connection.
    connection = get_connection(custom_path)

    try:
        row = connection.execute(
            """
            SELECT group_id, file_id, is_primary
            FROM DuplicateMembers
            WHERE group_id = ? AND file_id = ?
            """,
            (group_id, file_id),
        ).fetchone()

        assert row is not None
        assert row["group_id"] == group_id
        assert row["file_id"] == file_id
        assert row["is_primary"] == 1

    finally:
        connection.close()


def test_get_duplicate_groups_with_custom_database_path(tmp_path):
    """
    Verify duplicate groups can be retrieved from a custom database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the retrieved groups.
    """

    from src.data_access.connection import initialize_database

    # Create an independent temporary database.
    custom_path = tmp_path / "custom_groups.db"
    initialize_database(custom_path)

    # Create a scan in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Create groups with different potential savings.
    duplicates_repo.create_duplicate_group(
        scan_id,
        "hash-small",
        2,
        100,
        database_path=custom_path,
    )

    duplicates_repo.create_duplicate_group(
        scan_id,
        "hash-large",
        3,
        1000,
        database_path=custom_path,
    )

    # Retrieve groups from the custom database.
    groups = duplicates_repo.get_duplicate_groups(
        scan_id,
        database_path=custom_path,
    )

    assert len(groups) == 2
    assert [group.hash_value for group in groups] == [
        "hash-large",
        "hash-small",
    ]
    assert [group.potential_savings for group in groups] == [
        1000,
        100,
    ]



def test_get_duplicate_members_with_custom_database_path(tmp_path):
    """
    Verify duplicate members can be retrieved from a custom database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the retrieved members.
    """

    from src.data_access.connection import initialize_database

    # Create a separate temporary database.
    custom_path = tmp_path / "custom_members_read.db"
    initialize_database(custom_path)

    # Create a scan in the custom database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=custom_path,
    )

    # Save two files in the custom database.
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
                "size": 100,
            },
        ],
        database_path=custom_path,
    )

    # Create a duplicate group.
    group_id = duplicates_repo.create_duplicate_group(
        scan_id,
        "abc123",
        2,
        100,
        database_path=custom_path,
    )

    # Add the second file as primary to test ordering.
    duplicates_repo.add_duplicate_member(
        group_id,
        file_ids[0],
        is_primary=False,
        database_path=custom_path,
    )

    duplicates_repo.add_duplicate_member(
        group_id,
        file_ids[1],
        is_primary=True,
        database_path=custom_path,
    )

    # Retrieve members from the custom database.
    members = duplicates_repo.get_duplicate_members(
        group_id,
        database_path=custom_path,
    )

    assert len(members) == 2
    assert [member.name for member in members] == [
        "b.txt",
        "a.txt",
    ]


def test_duplicate_group_rejects_second_primary(tmp_path):
    """
    Verify that a duplicate group cannot contain two primary files.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        None: Assertions verify the database constraint.
    """

    import sqlite3
    import pytest

    from src.data_access.connection import initialize_database

    # Initialize a fresh database with the updated schema.
    database_path = tmp_path / "primary_constraint.db"
    initialize_database(database_path)

    # Create a scan in the test database.
    scan_id = scan_repo.create_scan(
        "/example",
        database_path=database_path,
    )

    # Create two files belonging to the same scan.
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
                "size": 100,
            },
        ],
        database_path=database_path,
    )

    # Create a duplicate group.
    group_id = duplicates_repo.create_duplicate_group(
        scan_id,
        "abc123",
        2,
        100,
        database_path=database_path,
    )

    # The first primary member should be accepted.
    duplicates_repo.add_duplicate_member(
        group_id,
        file_ids[0],
        is_primary=True,
        database_path=database_path,
    )

    # A second primary member must be rejected.
    with pytest.raises(sqlite3.IntegrityError):
        duplicates_repo.add_duplicate_member(
            group_id,
            file_ids[1],
            is_primary=True,
            database_path=database_path,
        )

    # The rejected insertion must not remove the first primary.
    members = duplicates_repo.get_duplicate_members(
        group_id,
        database_path=database_path,
    )

    assert len(members) == 1
    assert members[0].file_id == file_ids[0]
