
"""Flask web application for the Smart File Intelligence System."""

import logging
from pathlib import Path
from time import monotonic

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from src.data_access.duplicates_repo import (
    add_duplicate_member,
    create_duplicate_group,
    get_duplicate_groups,
    get_duplicate_members,
)
from src.data_access.file_repo import (
    get_files_by_scan,
    get_largest_files as get_largest_files_from_db,
    get_total_storage,
)
from src.data_access.scan_repo import list_scans, save_scan_results
from src.interface.cli_report import calc_avg_size, get_category_stats
from src.scanner.duplicates import find_duplicates
from src.scanner.traversal import scan_directory


app = Flask(__name__)

# Development-only key. Use an environment variable for deployment.
app.config["SECRET_KEY"] = "dev-only-change-this-before-deployment"


def format_bytes(size: int | float | None) -> str:
    """Format a byte count as a human-readable storage value.

    Args:
        size: Storage size in bytes. None is treated as zero.

    Returns:
        str: Formatted size using B, KB, MB, GB, or TB.
    """
    value = float(size or 0)
    units = ("B", "KB", "MB", "GB", "TB")

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"

        value /= 1024

    return "0 B"


def find_scan(scans: list, scan_id: int):
    """Find a saved scan by its ID.

    Args:
        scans: Scan objects returned by the scan repository.
        scan_id: ID of the scan to find.

    Returns:
        The matching scan object, or None if it does not exist.
    """
    return next(
        (scan for scan in scans if scan.scan_id == scan_id),
        None,
    )


def build_duplicate_details(scan_id: int) -> list[dict]:
    """Build display-ready duplicate information for one saved scan.

    Args:
        scan_id: ID of the scan whose duplicate groups should be retrieved.

    Returns:
        list[dict]: Dictionaries containing 'group', 'files', and 'name'.
    """
    groups = get_duplicate_groups(scan_id)
    duplicate_details = []

    for group in groups:
        files = get_duplicate_members(group.group_id)

        if files:
            display_name = files[0].name
        else:
            display_name = group.hash_value

        duplicate_details.append(
            {
                "group": group,
                "files": files,
                "name": display_name,
            }
        )

    return duplicate_details


def save_detected_duplicates(
    scan_id: int,
    file_data_list: list[dict],
) -> int:
    """Detect duplicate files and save their groups and memberships.

    Files must already have been saved to the database for this scan.

    Args:
        scan_id: ID of the saved scan that owns the files.
        file_data_list: Metadata dictionaries returned by scan_directory().

    Returns:
        int: Number of duplicate groups saved.

    Raises:
        ValueError: If a detected file cannot be matched to a saved file.
        KeyError: If a detector result is missing a required field.
        sqlite3.Error: If a database operation fails.
    """
    duplicate_results = find_duplicates(file_data_list)

    if not duplicate_results:
        return 0

    saved_files = get_files_by_scan(scan_id)

    # Match paths using their normalized absolute representation.
    file_ids_by_path = {
        str(Path(file.path).resolve()): file.file_id
        for file in saved_files
    }

    groups_saved = 0

    for result in duplicate_results:
        group_files = result["files"]
        member_ids = []

        for file_data in group_files:
            file_path = str(Path(file_data["path"]).resolve())
            file_id = file_ids_by_path.get(file_path)

            if file_id is None:
                raise ValueError(
                    "Could not find a saved database record for "
                    f"duplicate file: {file_data['path']}"
                )

            member_ids.append(file_id)

        # Create the group only after confirming all members exist.
        group_id = create_duplicate_group(
            scan_id=scan_id,
            hash_value=result["hash"],
            duplicate_count=result["count"],
            potential_savings=result["potential_savings"],
        )

        # Mark the first member as the representative file.
        for index, file_id in enumerate(member_ids):
            add_duplicate_member(
                group_id=group_id,
                file_id=file_id,
                is_primary=(index == 0),
            )

        groups_saved += 1

    return groups_saved


@app.route("/")
def dashboard():
    """Render the dashboard using saved scan data.

    Returns:
        str: Rendered dashboard HTML.
    """
    scans = list_scans()

    selected_scan = None
    files = []
    largest_files = []
    category_stats = {}
    duplicate_groups = []
    total_storage = 0
    average_size = 0.0
    potential_savings = 0

    if scans:
        requested_id = request.args.get("scan_id", type=int)

        if requested_id is not None:
            selected_scan = find_scan(scans, requested_id)

        if selected_scan is None:
            selected_scan = scans[0]

        scan_id = selected_scan.scan_id

        files = get_files_by_scan(scan_id)
        largest_files = get_largest_files_from_db(
            scan_id,
            limit=5,
        )
        category_stats = get_category_stats(files)
        total_storage = get_total_storage(scan_id)
        average_size = calc_avg_size(files)

        duplicate_details = build_duplicate_details(scan_id)

        # Display up to three groups in the dashboard preview.
        duplicate_groups = [
            {
                "name": detail["name"],
                "count": detail["group"].duplicate_count,
                "savings": detail["group"].potential_savings,
                "files": [file.path for file in detail["files"]],
            }
            for detail in duplicate_details[:3]
        ]

        # Calculate savings across all groups, not just the preview.
        potential_savings = sum(
            detail["group"].potential_savings
            for detail in duplicate_details
        )

    return render_template(
        "index.html",
        scans=scans,
        selected_scan=selected_scan,
        files=files,
        largest_files=largest_files,
        category_stats=category_stats,
        duplicate_groups=duplicate_groups,
        total_storage=total_storage,
        average_size=average_size,
        potential_savings=potential_savings,
        format_bytes=format_bytes,
    )


@app.route("/duplicates")
def duplicates():
    """Display all duplicate groups for a selected scan.

    Returns:
        str: Rendered duplicate report, or a redirect if the scan ID is
        missing or does not refer to an existing scan.
    """
    scans = list_scans()
    scan_id = request.args.get("scan_id", type=int)

    if scan_id is None:
        flash(
            "Please select a scan to view its duplicate report.",
            "error",
        )
        return redirect(url_for("dashboard"))

    selected_scan = find_scan(scans, scan_id)

    if selected_scan is None:
        flash("The selected scan could not be found.", "error")
        return redirect(url_for("dashboard"))

    duplicate_details = build_duplicate_details(scan_id)

    total_duplicate_groups = len(duplicate_details)

    total_duplicate_files = sum(
        detail["group"].duplicate_count
        for detail in duplicate_details
    )

    potential_savings = sum(
        detail["group"].potential_savings
        for detail in duplicate_details
    )

    return render_template(
        "duplicates.html",
        selected_scan=selected_scan,
        duplicate_details=duplicate_details,
        total_duplicate_groups=total_duplicate_groups,
        total_duplicate_files=total_duplicate_files,
        potential_savings=potential_savings,
        format_bytes=format_bytes,
    )


@app.route("/scan", methods=["POST"])
def start_scan():
    """Scan a directory, save its metadata, and analyze duplicate files.

    The metadata scan is saved before duplicate analysis starts. If duplicate
    analysis fails, the saved scan remains available.

    Returns:
        Response: Redirect to the dashboard with a status message.
    """
    scan_path = request.form.get("scan_path", "").strip()

    if not scan_path:
        flash("Please enter a directory path.", "error")
        return redirect(url_for("dashboard"))

    root = Path(scan_path).expanduser()

    if not root.is_dir():
        flash(
            "The specified path is not a valid directory.",
            "error",
        )
        return redirect(url_for("dashboard"))

    try:
        normalized_path = str(root.resolve())
        start_time = monotonic()

        # Step 1: Collect file metadata.
        file_data_list = list(scan_directory(root))

        # Step 2: Save the scan and its file metadata.
        scan_id = save_scan_results(
            normalized_path,
            file_data_list,
        )

        duration = monotonic() - start_time

    except Exception:
        app.logger.exception("Directory scan failed.")
        flash(
            "The scan could not be completed. Check the application "
            "terminal for details.",
            "error",
        )
        return redirect(url_for("dashboard"))

    # Step 3: Detect duplicates and save the resulting groups.
    try:
        groups_saved = save_detected_duplicates(
            scan_id,
            file_data_list,
        )

        flash(
            f"Scan completed: {len(file_data_list)} files found "
            f"in {duration:.2f} seconds. "
            f"{groups_saved} duplicate groups saved.",
            "success",
        )

    except Exception:
        app.logger.exception(
            "Duplicate analysis failed for scan %s.",
            scan_id,
        )
        flash(
            f"Scan completed with {len(file_data_list)} files, "
            "but duplicate analysis could not be fully saved. "
            "Check the application terminal for details.",
            "error",
        )

    return redirect(url_for("dashboard", scan_id=scan_id))


if __name__ == "__main__":
    app.run(debug=True)
