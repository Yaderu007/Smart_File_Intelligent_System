from src.scanner.classify import categorize

def test_known_extensions_map_correctly():
    assert categorize(".jpg") == "Images"
    assert categorize(".mp4") == "Videos"
    assert categorize(".pdf") == "Documents"
    assert categorize(".py") == "Code"
    assert categorize(".zip") == "Archives"

def test_unknown_extension_returns_other():
    assert categorize(".xyz123") == "Other"

def test_case_insensitivity():
    assert categorize(".JPG") == categorize(".jpg")
