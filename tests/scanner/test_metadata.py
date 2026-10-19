""" Tests for the metadata extraction functionality. """


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
    assert result["modified"] is not None


def test_extract_metadata_nonexistent_file(tmp_path):
    missing_path = tmp_path / "does_not_exist.txt"

    result = extract_metadata(missing_path)

    assert result["accessible"] is False
    assert result["error"] is not None
    assert result["size"] is None


def test_extract_metadata_extension_lowercased(tmp_path):
    file_path = tmp_path / "IMAGE.JPG"
    file_path.write_text("x")

    result = extract_metadata(file_path)

    assert result["extension"] == ".jpg"