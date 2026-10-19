## metadata.py

from pathlib import Path
from datetime import datetime


def extract_metadata(file_path):
    """
    Extracts metadata for a single file.

    Args:
        file_path (str or Path): Path to the file.

    Returns:
        dict: Metadata for the file. If the file could not be accessed,
        'accessible' is False and 'error' explains why — callers never
        need to catch an exception from this function.
    """
    path = Path(file_path)

    metadata = {
        "path": str(path),
        "name": path.name,
        "extension": path.suffix.lower(),
        "size": None,
        "created": None,
        "modified": None,
        "accessible": True,
        "error": None,
    }

    try:
        stats = path.stat()
        metadata["size"] = stats.st_size
        metadata["modified"] = datetime.fromtimestamp(stats.st_mtime).isoformat()
        try:
            metadata["created"] = datetime.fromtimestamp(stats.st_ctime).isoformat()
        except (OSError, ValueError):
            metadata["created"] = None  # not every filesystem tracks this
    except (OSError, PermissionError) as e:
        metadata["accessible"] = False
        metadata["error"] = str(e)

    return metadata