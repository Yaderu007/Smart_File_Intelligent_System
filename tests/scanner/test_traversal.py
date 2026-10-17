import os
import sys
import pytest

from src.scanner.traversal import scan_directory


def test_scan_finds_all_files(tmp_path):
    (tmp_path / "report.pdf").write_text("a")
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "img001.jpg").write_text("b")
    backups = tmp_path / "backups" / "old_backups"
    backups.mkdir(parents=True)
    (backups / "archive.zip").write_text("c")

    results = list(scan_directory(tmp_path))
    found_names = {r["name"] for r in results}

    assert found_names == {"report.pdf", "img001.jpg", "archive.zip"}
    # every record should have a category attached
    assert all("category" in r for r in results)


def test_empty_directory_yields_nothing(tmp_path):
    results = list(scan_directory(tmp_path))
    assert results == []


def test_invalid_root_raises():
    with pytest.raises(ValueError):
        list(scan_directory("/path/does/not/exist"))


@pytest.mark.skipif(sys.platform.startswith("win"), reason="chmod permissions differ on Windows")
def test_unreadable_subdirectory_does_not_stop_scan(tmp_path):
    (tmp_path / "readable.txt").write_text("a")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "secret.txt").write_text("b")

    os.chmod(blocked, 0o000)
    try:
        results = list(scan_directory(tmp_path))
    finally:
        os.chmod(blocked, 0o755)  # restore so pytest can clean up tmp_path

    found_names = {r["name"] for r in results}
    assert "readable.txt" in found_names