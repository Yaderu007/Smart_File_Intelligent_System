
"""Flask web application for the Smart File Intelligence System."""

from flask import Flask, flash, redirect, render_template, request, url_for

from src.data_access.scan_repo import list_scans
from src.data_access.file_repo import (
    get_files_by_scan,
    get_largest_files as get_largest_files_from_db,
    get_total_storage,
)
from src.interface.cli_report import (
    calc_avg_size,
    get_category_stats,
)

from pathlib import Path
from time import monotonic

from src.data_access.scan_repo import save_scan_results
from src.scanner.traversal import scan_directory


app = Flask(__name__)

app.config["SECRET_KEY"] = "dev-only-change-this-before-deployment"


def format_bytes(size: int | float) -> str:
    """Format a byte count as a human-readable storage value.

    Args:
        size: Storage size in bytes.

    Returns:
        str: Formatted size using B, KB, MB, GB, or TB.
    """
    value = float(size)
    units = ("B", "KB", "MB", "GB", "TB")

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024

    return "0 B"


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
    total_storage = 0
    average_size = 0.0

    if scans:
        requested_id = request.args.get("scan_id", type=int)

        if requested_id is not None:
            selected_scan = next(
                (scan for scan in scans if scan.scan_id == requested_id),
                None,
            )

        if selected_scan is None:
            selected_scan = scans[0]

        files = get_files_by_scan(selected_scan.scan_id)
        largest_files = get_largest_files_from_db(
            selected_scan.scan_id,
            limit=5,
        )
        category_stats = get_category_stats(files)
        total_storage = get_total_storage(selected_scan.scan_id)
        average_size = calc_avg_size(files)

    return render_template(
        "index.html",
        scans=scans,
        selected_scan=selected_scan,
        files=files,
        largest_files=largest_files,
        category_stats=category_stats,
        total_storage=total_storage,
        average_size=average_size,
        format_bytes=format_bytes,
    )
    


@app.route("/scan", methods=["POST"])
def start_scan():
    """Scan a directory and save its results to the database.

    Returns:
        A redirect to the dashboard with a success or error message.
    """
    scan_path = request.form.get("scan_path", "").strip()

    if not scan_path:
        flash("Please enter a directory path.", "error")
        return redirect(url_for("dashboard"))

    root = Path(scan_path).expanduser()

    if not root.is_dir():
        flash("The specified path is not a valid directory.", "error")
        return redirect(url_for("dashboard"))

    try:
        normalized_path = str(root.resolve())
        start_time = monotonic()

        file_data_list = list(scan_directory(root))

        scan_id = save_scan_results(
            normalized_path,
            file_data_list,
        )

        duration = monotonic() - start_time

        flash(
            f"Scan completed: {len(file_data_list)} files found "
            f"in {duration:.2f} seconds.",
            "success",
        )

        return redirect(url_for("dashboard", scan_id=scan_id))

    except Exception:
        app.logger.exception("Directory scan failed.")
        flash(
            "The scan could not be completed. Check the application "
            "terminal for details.",
            "error",
        )
        return redirect(url_for("dashboard"))



if __name__ == "__main__":
    app.run(debug=True)
