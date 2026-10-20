from pathlib import Path
import pytest
from src.scanner.metadata import extract_metadata
from src.scanner.duplicates import find_duplicates, detect_duplicates

def _record(**overrides):
    base = {"path": "/tmp/dummy", "name": "dummy", "extension": "",
            "size": 10, "accessible": True, "error": None,
            "created": None, "modified": None, "category": "Other"}
    base.update(overrides)
    return base

def test_duplicate_files_detected(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("same content"); b.write_text("same content")
    records = [extract_metadata(a), extract_metadata(b)]
    groups = find_duplicates(records)
    assert len(groups) == 1
    assert groups[0]["potential_savings"] == records[0]["size"]

def test_same_size_different_content_not_flagged(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("aaaa"); b.write_text("bbbb")
    assert find_duplicates([extract_metadata(a), extract_metadata(b)]) == []

def test_detect_duplicates_shape(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("same"); b.write_text("same")
    result = detect_duplicates([extract_metadata(a), extract_metadata(b)])
    assert set(result.keys()) == {"duplicate_groups", "file_hashes"}

def test_file_hashes_contains_only_hashed_candidates(tmp_path):
    a, b, unique = tmp_path / "a.txt", tmp_path / "b.txt", tmp_path / "unique.txt"
    a.write_text("same content"); b.write_text("same content")
    unique.write_text("a totally different, much longer piece of text")
    records = [extract_metadata(f) for f in (a, b, unique)]
    result = detect_duplicates(records)
    unique_path = next(r["path"] for r in records if r["name"] == "unique.txt")
    assert unique_path not in result["file_hashes"]
    assert len(result["file_hashes"]) == 2

def test_zero_byte_files_excluded(tmp_path):
    a, b = tmp_path / "empty_a.txt", tmp_path / "empty_b.txt"
    a.write_text(""); b.write_text("")
    result = detect_duplicates([extract_metadata(a), extract_metadata(b)])
    assert result["duplicate_groups"] == []
    assert result["file_hashes"] == {}

def test_inaccessible_files_excluded():
    records = [_record(path="/no/such/a", accessible=False, size=None),
               _record(path="/no/such/b", accessible=False, size=None)]
    assert detect_duplicates(records)["duplicate_groups"] == []

def test_group_representative_is_lowest_path_alphabetically(tmp_path):
    z, a = tmp_path / "z_file.txt", tmp_path / "a_file.txt"
    z.write_text("identical"); a.write_text("identical")
    records = [extract_metadata(z), extract_metadata(a)]  # out of order on purpose
    result = detect_duplicates(records)
    a_path = next(r["path"] for r in records if r["name"] == "a_file.txt")
    assert result["duplicate_groups"][0]["files"][0]["path"] == a_path

def test_potential_savings_formula(tmp_path):
    files = [tmp_path / f"dup{i}.txt" for i in range(3)]
    for f in files:
        f.write_text("identical content")
    records = [extract_metadata(f) for f in files]
    group = detect_duplicates(records)["duplicate_groups"][0]
    assert group["count"] == 3
    assert group["potential_savings"] == 2 * records[0]["size"]

def test_detect_duplicates_rejects_non_list_input():
    with pytest.raises(TypeError):
        detect_duplicates("not a list")

def test_malformed_record_is_skipped_not_raised():
    records = [{"not": "valid"}, _record(path="/tmp/ok", accessible=True, size=5)]
    assert detect_duplicates(records)["duplicate_groups"] == []
