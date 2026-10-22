"""B7: full pipeline integration test — scan, save, read back, verify."""

import pytest
from src.scanner import scan_directory, detect_duplicates
from src.data_access.connection import initialize_database
from src.data_access.scan_repo import save_scan, get_scan
from src.data_access.file_repo import get_files_by_scan, get_total_storage
from src.data_access.duplicate_repo import get_duplicate_groups, get_duplicate_members
from src.data_access.report_repo import get_storage_by_category, get_storage_report


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    initialize_database(str(path))
    return str(path)


@pytest.fixture
def sample_directory(tmp_path):
    scan_dir = tmp_path / "scan_me"
    scan_dir.mkdir()
    (scan_dir / "dup1.txt").write_text("identical content, twice")
    (scan_dir / "dup2.txt").write_text("identical content, twice")
    (scan_dir / "unique.txt").write_text("nothing else looks like this one")
    (scan_dir / "photo.jpg").write_bytes(b"\xff\xd8\xff" * 50)
    return scan_dir


def test_full_pipeline_end_to_end(sample_directory, db_path):
    files = list(scan_directory(sample_directory))
    result = detect_duplicates(files)
    scan_id = save_scan(str(sample_directory), files, result, duration_seconds=1,
                         database_path=db_path)

    scan = get_scan(scan_id, database_path=db_path)
    assert scan.status == "completed"
    assert scan.file_count == 4

    stored = get_files_by_scan(scan_id, database_path=db_path)
    assert len(stored) == 4

    expected_total = sum(len(f.read_bytes()) for f in sample_directory.iterdir())
    assert get_total_storage(scan_id, database_path=db_path) == expected_total

    groups = get_duplicate_groups(scan_id, database_path=db_path)
    assert len(groups) == 1
    assert groups[0].duplicate_count == 2
    assert groups[0].potential_savings == len("identical content, twice")

    members = get_duplicate_members(groups[0].group_id, database_path=db_path)
    primaries = [m for m in members if m["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["name"] == "dup1.txt"

    report = get_storage_report(scan_id, database_path=db_path)
    assert report["file_count"] == 4
    assert report["duplicate_groups"] == 1


def test_scan_with_no_duplicates_still_completes(tmp_path, db_path):
    scan_dir = tmp_path / "no_dupes"
    scan_dir.mkdir()
    (scan_dir / "only_one.txt").write_text("nothing to duplicate here")

    files = list(scan_directory(scan_dir))
    result = detect_duplicates(files)
    scan_id = save_scan(str(scan_dir), files, result, database_path=db_path)

    scan = get_scan(scan_id, database_path=db_path)
    assert scan.status == "completed"
    assert get_duplicate_groups(scan_id, database_path=db_path) == []