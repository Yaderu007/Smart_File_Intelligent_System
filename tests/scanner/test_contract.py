"""Verifies scanner output matches docs/INTERFACES.md (contract v1.2)."""

from pathlib import Path
from src.scanner import scan_directory
from src.scanner.duplicates import detect_duplicates

REQUIRED_KEYS = {"path", "name", "extension", "size", "created", "modified",
                  "accessible", "error", "category"}

def test_scanner_output_matches_contract_fields(tmp_path):
    (tmp_path / "a.txt").write_text("same content")
    (tmp_path / "b.txt").write_text("same content")
    records = list(scan_directory(tmp_path))
    assert len(records) == 2
    for record in records:
        assert REQUIRED_KEYS.issubset(record.keys())
        assert Path(record["path"]).is_absolute()

def test_detect_duplicates_paths_match_scanner_paths(tmp_path):
    (tmp_path / "a.txt").write_text("same content")
    (tmp_path / "b.txt").write_text("same content")
    records = list(scan_directory(tmp_path))
    result = detect_duplicates(records)
    scanner_paths = {r["path"] for r in records}
    assert set(result["file_hashes"].keys()).issubset(scanner_paths)
    for group in result["duplicate_groups"]:
        for fr in group["files"]:
            assert fr["path"] in scanner_paths

def test_category_values_are_from_the_fixed_set(tmp_path):
    (tmp_path / "doc.pdf").write_text("x")
    (tmp_path / "mystery.xyz123").write_text("x")
    allowed = {"Documents", "Images", "Videos", "Audio", "Code", "Archives", "Other"}
    for record in scan_directory(tmp_path):
        assert record["category"] in allowed
