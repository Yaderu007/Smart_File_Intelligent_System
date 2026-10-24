# Smart File Intelligence System

Smart File Intelligence System (SFI) is a local Flask web application for inspecting storage usage in a directory. It scans file metadata, groups files into categories, lists the largest files, and detects identical files so you can review possible storage savings.

It is a Python project, not a standalone installer. You need Python installed and must install the project's dependencies before running it.

## Features

- **Storage by category:** Summarises the storage used by each file category.
- **Largest file categories:** Shows the largest individual file in each category as a percentage of that category's total size.
- **Largest files:** Lists the largest files found in a scan.
- **Duplicate files:** Groups identical files and estimates the storage that could be saved if only one copy in each group were retained.
- **Scan history:** Saves scan results locally so previous reports can be reviewed.
- **Light and dark themes:** Includes matching green/teal themes.
- **Local-first operation:** Runs in your browser while the Flask application runs on your computer.

The app does **not** delete, move, or modify files. Review duplicate groups before removing anything yourself.

## Requirements

- Python **3.10 or newer**
- `pip` (included with most Python installations)
- A modern browser
- Permission to read the directory you want to scan

The application is intended to run on Windows, macOS, and Linux. Exact behavior depends on the Python installation, file-system permissions, and the directories selected for scanning.

## Installation

### 1. Download and extract the project

Download the project ZIP and extract it. Open a terminal in the extracted `Smart_File_Intelligent_System` folder—the folder containing `requirements.txt` and `schema.sql`.

All commands below should be run from that folder.

### 2. Create a virtual environment

A virtual environment keeps this project's Python packages separate from other projects.

**Windows (PowerShell):**

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If `py -3.10` is not available, install Python 3.10 or newer and use the appropriate `py` or `python` command. If PowerShell blocks activation, you can use the environment's Python executable directly; see the alternative commands below.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

With the virtual environment activated, run this on Windows, macOS, or Linux:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you could not activate the environment in Windows PowerShell, run:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Initialise the database

The app stores scan history in a local SQLite file named `smart_files.db`. The ZIP supplied with the project may already contain a database with previously saved scan results. The initialisation command creates any missing tables and does not erase existing saved results.

Run:

```bash
python -c "from src.data_access.connection import initialize_database; initialize_database()"
```

Run this from the project root. It is especially important for a fresh checkout or if `smart_files.db` is not present.

### 5. Start the application

```bash
python -m src.interface.web_app
```

Open this address in your browser:

<http://127.0.0.1:5000>

To stop the server, return to the terminal and press **Ctrl+C**.

## How to use the application

### Scan a directory

1. Open the dashboard in your browser.
2. In **Scan a directory**, enter the full path of a folder on the computer running the app.
3. Select **Scan directory** and wait for the scan to finish.
4. Use **Scan history** to open a previous scan report.

Examples of directory paths:

- Windows: `C:\Users\YourName\Documents`
- macOS: `/Users/YourName/Documents`
- Linux: `/home/yourname/Documents`

Use a path that exists on the computer running the app and that your account is allowed to read. The input expects a typed directory path; it is not a native file-picker dialog. Start with a small folder before scanning a large drive, as duplicate detection may take time when many or very large files are present.

### Read the dashboard

- **Storage by category** shows how scanned file sizes are distributed among categories.
- **Largest file categories** compares each category's largest file with that category's total size. The percentage is calculated as:

  `largest file in category / total size of that category × 100%`

- **Largest files** lists the largest individual files discovered in the scan.
- **Duplicate files** opens the full duplicate report. Expand a group to inspect the paths of its matching files.
- Use the right-side section navigator to jump between dashboard sections. Use the theme toggle to switch between light and dark mode.

Potential savings are estimates based on keeping one copy from each duplicate group. The app does not automatically remove duplicates.

## Where data is stored

The SQLite database is stored at the project root as `smart_files.db`. It contains scan history and file metadata, including paths, sizes, timestamps, categories, and duplicate-analysis results. Duplicate detection reads file contents to compute hashes, but the application does not upload those files to a remote service or save their contents as file copies in the database.

- **Keep history:** Back up `smart_files.db` before moving the project or making database/schema changes.
- **Start with a clean history:** Stop the application, back up the database if needed, delete `smart_files.db`, then run the database initialisation command above. The app will create a new database when it starts after initialisation.
- **Moving to another computer:** The bundled database may contain scans from the original computer. Old reports can display paths that do not exist on the new computer. Run a new scan of a directory on the new computer to create a relevant report.

## Running the tests

Install the dependencies first, then run:

```bash
python -m pytest -q
```

## Troubleshooting

**`ModuleNotFoundError: No module named 'flask'`**
Activate the virtual environment and rerun `python -m pip install -r requirements.txt`.

**`no such table` / SQLite table errors**
Confirm you are in the project root and run the database initialisation command in the installation section.

**The folder path is rejected or some files are missing**
Check that the path exists on this computer and your account has permission to read it. Some protected system directories may not be accessible; the scanner may skip unreadable directories or files.

**Port 5000 is already in use**
Stop the other application using port 5000, then start SFI again.

**The page does not open**
Check the terminal for startup errors, confirm the Flask server is still running, and open `http://127.0.0.1:5000`.

## Security and limitations

- The built-in Flask development server is for local development and testing only. Do not expose it directly to the internet or an untrusted network.
- The app currently uses a development fallback for Flask's secret key. Set the `FLASK_SECRET_KEY` environment variable to a strong random value before using the app in any shared or deployed environment.
- Database schema migrations are not provided. Back up `smart_files.db` before changing the schema or code that depends on it.
- This is a development-stage application, so installation and scanning behavior should be tested with representative folders before relying on its reports.
