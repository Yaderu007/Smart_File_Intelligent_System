## duplicates.py 
# ##Duplicate detection via size-then-hash grouping

from .hashing import hash_file


def find_duplicates(file_metadata_list):
    """
    Identifies duplicate files using a two-stage approach: group by
    size first (cheap), then hash only the files that share a size
    with at least one other file (expensive, so done as rarely as
    possible).

    Args:
        file_metadata_list (list): Metadata dicts from scan_directory()
            (no 'hash' field required — it's computed here, only for
            files that actually need it).

    Returns:
        list[dict]: One entry per duplicate group found, each with
        'hash', 'files' (the metadata dicts involved), 'count', and
        'potential_savings' (bytes recoverable if all but one copy
        were removed).
    """
    # Group by size -- an O(n) pass, no file content read at all
    by_size = {}
    for metadata in file_metadata_list:
        by_size.setdefault(metadata["size"], []).append(metadata)

    # Only files sharing a size with at least one other file could
    # possibly be duplicates -- everything else is eliminated here,
    # before a single byte of file content gets read.
    candidates = [group for group in by_size.values() if len(group) > 1]

    # Stage 2: within each size group, hash only these candidates,
    # then group again by hash to confirm actual duplicates.
    duplicate_groups = []
    for group in candidates:
        by_hash = {}
        for metadata in group:
            try:
                file_hash = hash_file(metadata["path"])
            except OSError as e:
                # Per hash_file()'s contract: skip just this file,
                # don't abort the whole duplicate-detection pass.
                print(f"Skipping unreadable file during hashing: {metadata['path']} ({e})")
                continue
            by_hash.setdefault(file_hash, []).append(metadata)

        for file_hash, files in by_hash.items():
            if len(files) > 1:
                duplicate_groups.append({
                    "hash": file_hash,
                    "files": files,
                    "count": len(files),
                    "potential_savings": (len(files) - 1) * files[0]["size"],
                })

    return duplicate_groups