""" Tests for the duplicate detection functionality. """


from src.scanner.metadata import extract_metadata
from src.scanner.duplicates import find_duplicates


def test_duplicate_files_detected(tmp_path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("same content")
    file_b.write_text("same content")

    records = [extract_metadata(file_a), extract_metadata(file_b)]
    groups = find_duplicates(records)

    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert groups[0]["potential_savings"] == records[0]["size"]
    

def test_same_size_different_content_not_flagged(tmp_path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("aaaa")  # same length, different bytes
    file_b.write_text("bbbb")

    records = [extract_metadata(file_a), extract_metadata(file_b)]
    groups = find_duplicates(records)

    assert groups == []


def test_unique_file_not_in_any_group(tmp_path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_c = tmp_path / "c.txt"
    file_a.write_text("same")
    file_b.write_text("same")
    file_c.write_text("completely different and longer")

    records = [extract_metadata(f) for f in (file_a, file_b, file_c)]
    groups = find_duplicates(records)

    assert len(groups) == 1
    all_duplicate_names = {f["name"] for f in groups[0]["files"]}
    assert all_duplicate_names == {"a.txt", "b.txt"}
    assert "c.txt" not in all_duplicate_names