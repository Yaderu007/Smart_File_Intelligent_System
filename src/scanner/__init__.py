"""Scanner, hashing, and duplicate-detection package."""

from .traversal import scan_directory
from .duplicates import find_duplicates, detect_duplicates

__all__ = ["scan_directory", "find_duplicates", "detect_duplicates"]
