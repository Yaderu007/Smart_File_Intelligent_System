from src.data_access.models import FileMetadata

sample_files = [
    {
        "file_id": 1,
        "path": "/demo/notes.pdf",
        "name": "notes.pdf",
        "extension": ".pdf",
        "size": 2_000,
    },
    {
        "file_id": 2,
        "path": "/demo/report.pdf",
        "name": "report.pdf",
        "extension": ".pdf",
        "size": 4_000,
    },
    {
        "file_id": 3,
        "path": "/demo/photo.jpg",
        "name": "photo.jpg",
        "extension": ".jpg",
        "size": 6_000,
    },
    {
        "file_id": 4,
        "path": "/demo/photo_copy.jpg",
        "name": "photo_copy.jpg",
        "extension": ".jpg",
        "size": 6_000,
    },
    {
        "file_id": 5,
        "path": "/demo/model.stl",
        "name": "model.stl",
        "extension": ".stl",
        "size": 0,
    },
    {
        "file_id": 6,
        "path": "/demo/data.xyz",
        "name": "data.xyz",
        "extension": ".xyz",
        "size": 1_000,
    },
]


sample_duplicate_groups = [
    {
        "group_id": 1,
        "file_ids": [3, 4],
    }
]


"""
Each category has a dedicated integer value. This will be used to allow for any future modifications required
"""

categories = [
    "Other",
    "Documents",
    "Photos",
    "Videos",
    "Audios",
    "Code",
]



def get_category_stats(files: list[FileMetadata]) -> dict[str, dict[str, int]]:
    """Calculate file counts and known storage totals for each category.

    Args:
        files (list[FileMetadata]): The file metadata records to analyze.
            Each record must contain a category and a size, which may be None.

    Returns:
        dict[str, dict[str, int]]: A dictionary mapping each category to
            its statistics:
            - "file_count": Number of files in the category.
            - "total_size": Total size in bytes of files with known sizes.

    Notes:
        Files with unknown sizes (None) are included in the file count,
        but excluded from the storage total. A known size of zero is valid.
        Categories with no files are not included in the result.
    """

    stats: dict[str, dict[str, int]] = {}

    for file in files:
        category = file.category

        if category not in stats:
            stats[category] = {
                "file_count": 0,
                "total_size": 0,
            }

        stats[category]["file_count"] += 1

        if file.size is not None:
            stats[category]["total_size"] += file.size

    return stats


def calc_tot_storage(files: list[FileMetadata]) -> int:
    """Calculate the total known storage occupied by a list of files.

    Args:
        files (list[FileMetadata]): The file metadata records to analyze.
            File sizes may be None when the size is unknown.

    Returns:
        int: The sum of known file sizes, in bytes.
            Returns 0 if the list is empty or all sizes are unknown.

    Notes:
        Files with unknown sizes (None) are ignored.
        Files with a known size of zero are included.
    """

    total = 0

    for file in files:
        if file.size is not None:
            total += file.size

    return total


def calc_avg_size(files: list[FileMetadata]) -> float:
    """Calculates the average size of a list of files, in bytes

    Args:
        files (list[FileMetaData]): The list of files to be used for calculation

    Returns:
        float: The average storage, in bytes, that the files occupy
    """
    
    known_sizes = [
        file.size
        for file in files
        if file.size is not None
    ]

    if len(known_sizes) == 0:
        return 0.0

    return sum(known_sizes) / len(known_sizes)


def get_largest_files(
    files: list[FileMetadata],
    n: int,
) -> list[FileMetadata]:
    """Return the n largest files, ordered by descending size.

    Args:
        files (list[FileMetadata]): The file metadata records to sort.
        n (int): Maximum number of files to return. Must be non-negative.

    Returns:
        list[FileMetadata]: Files sorted from largest to smallest.
            Files with unknown sizes are excluded.
            Returns an empty list if n is zero or negative.

    Notes:
        Files with equal sizes retain their relative input order.
    """

    if n <= 0:
        return []

    known_size_files = [
        file for file in files
        if file.size is not None
    ]

    return sorted(
        known_size_files,
        key=lambda file: file.size,
        reverse=True,
    )[:n]