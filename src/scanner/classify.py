"""classify.py — File categorization by extension (Aaryadeep)"""

_CATEGORY_EXTENSIONS = {
    "Documents": {".pdf", ".docx", ".txt", ".md"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg"},
    "Videos": {".mp4", ".avi", ".mov", ".mkv"},
    "Audio": {".mp3", ".wav", ".flac"},
    "Code": {".py", ".js", ".java", ".cpp", ".c", ".html", ".css"},
    "Archives": {".zip", ".tar", ".rar", ".gz"},
}

_EXTENSION_TO_CATEGORY = {
    ext: category
    for category, extensions in _CATEGORY_EXTENSIONS.items()
    for ext in extensions
}


def categorize(extension):
    """Per contract v1.2 (C2): fixed category names, computed once at
    scan time; downstream components read but never recompute this."""
    return _EXTENSION_TO_CATEGORY.get(extension.lower(), "Other")
