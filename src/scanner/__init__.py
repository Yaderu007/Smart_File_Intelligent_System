# __init__.py 

"""
Scanner module for scanning directories and finding duplicates.
"""

from .traversal import scan_directory
from .duplicates import find_duplicates 

__all__ = ["scan_directory", "find_duplicates"]