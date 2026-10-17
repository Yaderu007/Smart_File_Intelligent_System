## classify.py

# Category -> extensions, defined once at module load time
_CATEGORY_EXTENSIONS = {
    "Documents": {".pdf", ".docx", ".txt", ".md"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg"},
    "Videos": {".mp4", ".avi", ".mov", ".mkv"},
    "Audio": {".mp3", ".wav", ".flac"},
    "Code": {".py", ".js", ".java", ".cpp", ".c", ".html", ".css"},
    "Archives": {".zip", ".tar", ".rar", ".gz"},
}

# Reverse lookup, built once: extension -> category
_EXTENSION_TO_CATEGORY = {
    ext: category
    for category, extensions in _CATEGORY_EXTENSIONS.items()
    for ext in extensions
}


def categorize(extension):
    """
    Categorizes a file based on its extension.

    Args:
        extension (str): The file extension (including the dot).

    Returns:
        str: The category of the file, or "Other" if unrecognized.
    """
    return _EXTENSION_TO_CATEGORY.get(extension.lower(), "Other")