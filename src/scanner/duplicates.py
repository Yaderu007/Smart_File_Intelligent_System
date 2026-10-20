"""duplicates.py — Duplicate detection via size-then-hash grouping (Aaryadeep)

Implements contract v1.2, section C3.
"""

import logging

from .hashing import hash_file

logger = logging.getLogger(__name__)


def detect_duplicates(files):
    """
    Per contract v1.2 (C3): size-then-hash two-stage grouping.
    - Only accessible files with size not None and size > 0 considered.
    - file_hashes contains ONLY files that were actually hashed.
    - Groups sorted by path; files[0] is the representative (is_primary).
    - potential_savings = (count - 1) * size.
    - Bad records skipped and logged, never raised. TypeError only if
      `files` itself is not a list.
    """
    if not isinstance(files, list):
        raise TypeError("files must be a list.")

    by_size = {}
    for record in files:
        try:
            if not isinstance(record, dict):
                raise TypeError("record is not a dict")
            if record.get("accessible") is not True:
                continue
            size = record.get("size")
            if size is None or size <= 0:
                continue
            _ = record["path"]  # validated here, used below
        except (TypeError, KeyError) as e:
            logger.warning("Skipping malformed record during grouping: %s", e)
            continue

        by_size.setdefault(size, []).append(record)

    candidates = [group for group in by_size.values() if len(group) > 1]

    file_hashes = {}
    duplicate_groups = []

    for group in candidates:
        by_hash = {}
        for record in group:
            path = record["path"]
            try:
                file_hash = hash_file(path)
            except OSError as e:
                logger.warning(
                    "Skipping unreadable file during hashing: %s (%s)", path, e
                )
                continue

            file_hashes[path] = file_hash
            by_hash.setdefault(file_hash, []).append(record)

        for file_hash, matched_files in by_hash.items():
            if len(matched_files) < 2:
                continue

            matched_files = sorted(matched_files, key=lambda r: r["path"])

            duplicate_groups.append({
                "hash": file_hash,
                "files": matched_files,
                "count": len(matched_files),
                "potential_savings": (
                    (len(matched_files) - 1) * matched_files[0]["size"]
                ),
            })

    return {
        "duplicate_groups": duplicate_groups,
        "file_hashes": file_hashes,
    }


def find_duplicates(files):
    """Backward-compatible wrapper: returns only the groups list."""
    return detect_duplicates(files)["duplicate_groups"]
