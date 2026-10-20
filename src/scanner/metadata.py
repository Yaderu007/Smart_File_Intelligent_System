"""metadata.py — Per-file metadata extraction (Aaryadeep)"""

from pathlib import Path
from datetime import datetime, timezone


def extract_metadata(file_path):
    """
    Extracts metadata for a single file.

    Per contract v1.2 (C1, S2, S3):
    - 'path' is always an absolute path.
    - 'modified' and 'created' are ISO-8601 strings in UTC, with an
      explicit UTC offset.
    - 'created' is None where the OS does not track file creation
      time -- an expected, normal case, not an error.
    """
    original = Path(file_path)

    metadata = {
        "path": str(original),
        "name": original.name,
        "extension": original.suffix.lower(),
        "size": None,
        "created": None,
        "modified": None,
        "accessible": True,
        "error": None,
    }

    try:
        path = original.resolve()
        metadata["path"] = str(path)

        stats = path.stat()
        metadata["size"] = stats.st_size
        metadata["modified"] = datetime.fromtimestamp(
            stats.st_mtime, tz=timezone.utc
        ).isoformat()
        try:
            metadata["created"] = datetime.fromtimestamp(
                stats.st_ctime, tz=timezone.utc
            ).isoformat()
        except (OSError, ValueError):
            metadata["created"] = None
    except (OSError, PermissionError) as e:
        metadata["accessible"] = False
        metadata["error"] = str(e)

    return metadata
