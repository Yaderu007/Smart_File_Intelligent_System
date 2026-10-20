from pathlib import Path
from src.scanner.metadata import extract_metadata

def test_extract_metadata_valid_file(tmp_path):
    file_path = tmp_path / "report.pdf"
    file_path.write_text("some content")
    result = extract_metadata(file_path)
    assert result["name"] == "report.pdf"
    assert result["extension"] == ".pdf"
    assert result["size"] == len("some content")
    assert result["accessible"] is True
    assert result["error"] is None

def test_extract_metadata_nonexistent_file(tmp_path):
    result = extract_metadata(tmp_path / "does_not_exist.txt")
    assert result["accessible"] is False
    assert result["error"] is not None

def test_extract_metadata_extension_lowercased(tmp_path):
    file_path = tmp_path / "IMAGE.JPG"
    file_path.write_text("x")
    assert extract_metadata(file_path)["extension"] == ".jpg"

def test_path_is_absolute(tmp_path):
    file_path = tmp_path / "report.pdf"
    file_path.write_text("x")
    assert Path(extract_metadata(file_path)["path"]).is_absolute()

def test_modified_timestamp_has_utc_offset(tmp_path):
    file_path = tmp_path / "report.pdf"
    file_path.write_text("x")
    assert extract_metadata(file_path)["modified"].endswith("+00:00")
