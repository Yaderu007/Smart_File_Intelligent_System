"""hashing.py — Chunked SHA-256 hashing (Aaryadeep)"""

import hashlib
from pathlib import Path


def hash_file(path, chunk_size=65536):
    """
    Computes the SHA-256 hash of a file in fixed-size chunks.

    Raises:
        OSError: on any failure. Callers (duplicates.py) catch this
        per-file and skip, rather than aborting the whole pass.
    """
    path = Path(path)
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)

    return sha256.hexdigest()
