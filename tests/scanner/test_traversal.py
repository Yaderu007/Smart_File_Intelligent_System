import os, sys, pytest
from src.scanner.traversal import scan_directory

def test_scan_finds_all_files(tmp_path):
    (tmp_path / "report.pdf").write_text("a")
    photos = tmp_path / "photos"; photos.mkdir()
    (photos / "img001.jpg").write_text("b")
    results = list(scan_directory(tmp_path))
    assert {r["name"] for r in results} == {"report.pdf", "img001.jpg"}

def test_all_paths_are_absolute(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    results = list(scan_directory(tmp_path))
    assert all(os.path.isabs(r["path"]) for r in results)

def test_empty_directory_yields_nothing(tmp_path):
    assert list(scan_directory(tmp_path)) == []

def test_invalid_root_raises():
    with pytest.raises(ValueError):
        list(scan_directory("/path/does/not/exist"))

@pytest.mark.skipif(sys.platform.startswith("win"), reason="chmod differs on Windows")
def test_unreadable_subdirectory_does_not_stop_scan(tmp_path):
    (tmp_path / "readable.txt").write_text("a")
    blocked = tmp_path / "blocked"; blocked.mkdir()
    (blocked / "secret.txt").write_text("b")
    os.chmod(blocked, 0o000)
    try:
        results = list(scan_directory(tmp_path))
    finally:
        os.chmod(blocked, 0o755)
    assert "readable.txt" in {r["name"] for r in results}
