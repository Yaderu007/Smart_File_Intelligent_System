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


def get_category(ext: str) -> int:
    """Assign a particular category based on the file extention passed

    Args:
        ext (str): The file extension

    Returns:
        int: The index number for the category in belongs to
    """
    
    ext = ext.lower()
    
    if (ext in [".pdf", ".doc", ".docx"]):
        return 1
    elif (ext in [".png", ".jpg", ".svg"]):
        return 2
    elif (ext in [".mp4"]):
        return 3
    elif (ext in [".mp3", ".amv"]):
        return 4
    elif (ext in [".py", ".cpp", ".c", ".js", ".sql"]):
        return 5
    else:
        return 0


def  calc_tot_storage(files: list[dict]) -> int:
    """Total amount of storage occupied by a given list of files

    Args:
        files (list[dict]): The list of file objects

    Returns:    
        int: The total storage, in bytes, occupied by the files
    """
    
    tot: int = 0
    
    for file in files:
        tot += file["size"]
        
    return tot


def calc_avg_size(files: list[dict]) -> float:
    """Calculates the average size of a list of files, in bytes

    Args:
        files (list[dict]): The list of files to be used for calculation

    Returns:
        float: The average storage, in bytes, that the files occupy
    """
    if len(files) == 0:
        return 0.0
    
    avg: float = calc_tot_storage(files) / len(files)
    
    return avg


def get_largest_files(files: list[dict], n: int) -> list[dict]:
    """Returns a sorted list of files, based on the largest to smallest file sizes, and up to a certain chosen amount.

    Args:
        files (list[dict]): The list of files to be sorted in descending order
        n (int): The number of files to return

    Returns:
        list[dict]: The shortened, sorted files (in descending order)
    """
    
    # If the number of files wanted is negative, then none is returnedx
    if n < 0: 
        return []
    
    sortFiles: list[dict] = sorted(files, key = lambda file: file["size"], reverse = True)[:n]

    
    return sortFiles