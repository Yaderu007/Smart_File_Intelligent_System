## traversal.py 

import os
from pathlib import Path

from .metadata import extract_metadata
from .classify import categorize


def scan_directory(root_path):
    """
    Recursively scans a directory and yields metadata for every file
    found. Files or directories that cannot be accessed are logged
    and skipped -- a single bad path never stops the scan.

    Args:
        root_path (str or Path): Path to the root directory.

    Yields:
        dict: Metadata for each file found, including its category.
    """
    root = Path(root_path)

    if not root.is_dir():
        raise ValueError(f"{root} is not a valid directory.")

    def on_walk_error(os_error):
        # Called by os.walk when a directory can't even be listed
        # (permission denied, etc.) -- log and keep walking instead
        # of letting the whole scan crash.
        print(f"Skipping unreadable directory: {os_error}")

    # followlinks=False (the default) means symlinked directories are
    # never followed. This is our chosen policy -- it guarantees the
    # walk terminates even if a symlink points back to an ancestor.
    for dirpath, dirnames, filenames in os.walk(
        root, onerror=on_walk_error, followlinks=False
    ):
        for filename in filenames:
            path = Path(dirpath) / filename

            if path.is_symlink():
                continue  # same policy: skip symlinked files too

            metadata = extract_metadata(path)
            metadata["category"] = categorize(metadata["extension"])
            yield metadata