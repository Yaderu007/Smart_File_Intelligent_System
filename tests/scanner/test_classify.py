from src.scanner.classify import categorize


def test_known_extensions_map_correctly():
    assert categorize(".jpg") == "Images"
    assert categorize(".mp4") == "Videos"
    assert categorize(".pdf") == "Documents"
    assert categorize(".py") == "Code"
    assert categorize(".zip") == "Archives"
    assert categorize(".mp3") == "Audio"


def test_unknown_extension_returns_other():
    assert categorize(".xyz123") == "Other"
    assert categorize("") == "Other"


def test_case_insensitivity():
    assert categorize(".JPG") == "Images"
    assert categorize(".jpg") == "Images"
    assert categorize(".JPG") == categorize(".jpg")