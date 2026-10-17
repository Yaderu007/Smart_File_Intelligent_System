## hashing.py

import hashlib
from pathlib import Path


def hash_file(path, chunk_size=65536):
    """
    Computes the SHA-256 hash of a file, reading it in fixed-size
    chunks so the full file is never held in memory at once.

    Args:
        path (str or Path): Path to the file.
        chunk_size (int): Size of chunks to read at a time (default: 65536 bytes).

    Returns:
        str: The hex digest of the file's SHA-256 hash.

    Raises:
        OSError: If the file cannot be opened or read (missing,
        permission denied, deleted mid-read, etc.). This function
        does not swallow errors — callers (duplicates.py) are
        expected to catch the failure per-file and skip that file
        rather than aborting the whole duplicate-detection pass.
    """
    path = Path(path)
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)

    return sha256.hexdigest()