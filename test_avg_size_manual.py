from types import SimpleNamespace

from src.interface.cli_report import (
    calc_avg_size,
    calc_tot_storage,
    get_category_stats,
    get_largest_files,
)

files = [
    SimpleNamespace(category="Documents", size=1000, name="small.pdf"),
    SimpleNamespace(category="Images", size=0, name="empty.jpg"),
    SimpleNamespace(category="Documents", size=None, name="unknown.pdf"),
    SimpleNamespace(category="Images", size=3000, name="large.jpg"),
]

# Test average size
assert calc_avg_size(files) == 1333.3333333333333
assert calc_avg_size([]) == 0.0

# Test total storage
assert calc_tot_storage(files) == 4000
assert calc_tot_storage([]) == 0

# Test largest files
largest = get_largest_files(files, 2)
assert [file.name for file in largest] == ["large.jpg", "small.pdf"]
assert get_largest_files(files, 0) == []
assert get_largest_files(files, -1) == []

# Test category statistics
stats = get_category_stats(files)
assert stats == {
    "Documents": {"file_count": 2, "total_size": 1000},
    "Images": {"file_count": 2, "total_size": 3000},
}

print("All manual analysis tests passed.")