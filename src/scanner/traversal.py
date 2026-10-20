"""traversal.py — Recursive directory scanning (Aaryadeep)"""

import os
import logging
from pathlib import Path

from .metadata import extract_metadata
from .classify import categorize

logger = logging.getLogger(__name__)


def scan_directory(root_path):
    """
    Recursively scans a directory and yields metadata for every file
    found. Per contract v1.2 (C1, S2, S4): root resolved to absolute
    before walking; problems logged via `logging`, not printed;
    symlinks never followed; hidden files included.
    """
    root = Path(root_path).resolve()

    if not root.is_dir():
        raise ValueError(f"{root} is not a valid directory.")

    def on_walk_error(os_error):
        logger.warning("Skipping unreadable directory: %s", os_error)

    for dirpath, dirnames, filenames in os.walk(
        root, onerror=on_walk_error, followlinks=False
    ):
        for filename in filenames:
            path = Path(dirpath) / filename

            if path.is_symlink():
                continue

            metadata = extract_metadata(path)
            metadata["category"] = categorize(metadata["extension"])
            yield metadata
