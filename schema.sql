-- Stores information about each directory scanning operation.
-- Each scan has a unique ID, even if the same directory is scanned multiple times.
CREATE TABLE IF NOT EXISTS Scans (
    scan_id INTEGER PRIMARY KEY,
    scan_path TEXT NOT NULL,
    scan_timestamp TEXT NOT NULL,
    scan_duration INTEGER CHECK (scan_duration IS NULL OR scan_duration >= 0),
    file_count INTEGER NOT NULL DEFAULT 0 CHECK (file_count >= 0),
    total_size INTEGER NOT NULL DEFAULT 0 CHECK (total_size >= 0),
    status TEXT NOT NULL DEFAULT 'incomplete'
        CHECK (status IN ('incomplete', 'completed', 'failed'))
);

-- Stores metadata collected for each file during a scan.
-- Each file record belongs to one scan through scan_id.
CREATE TABLE IF NOT EXISTS Files (
    file_id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL,

    path TEXT NOT NULL,
    name TEXT NOT NULL,
    -- Unknown file sizes are allowed, but negative sizes are invalid.
    size INTEGER CHECK (size IS NULL OR size >= 0),
    extension TEXT,
    category TEXT NOT NULL DEFAULT 'Other',
    created TEXT,
    modified TEXT,
    accessed_timestamp TEXT,
    accessible INTEGER NOT NULL DEFAULT 1
        CHECK (accessible IN (0, 1)),
    error TEXT,
    UNIQUE (scan_id, path),

    -- Delete the associated file records when a scan is deleted.
    FOREIGN KEY (scan_id) REFERENCES Scans(scan_id)
        ON DELETE CASCADE
);

-- Stores the hashes calculated for files discovered during scans.
-- Hashes help identify files with identical contents, even if their names differ.
-- A file can have multiple hashes if different algorithms are used.
CREATE TABLE IF NOT EXISTS FileHashes (
    hash_id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL,
    hash_value TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL,

    UNIQUE (file_id, hash_algorithm),

    -- Delete a file's hashes when the file is deleted.
    FOREIGN KEY (file_id) REFERENCES Files(file_id)
        ON DELETE CASCADE
);

-- Stores groups of identical files found within a specific scan.
-- Each group belongs to one scan, allowing automatic cleanup.
CREATE TABLE IF NOT EXISTS DuplicateGroups (
    group_id INTEGER PRIMARY KEY,

    -- Identifies the scan in which these duplicates were discovered.
    scan_id INTEGER NOT NULL,

    hash_value TEXT NOT NULL,
    duplicate_count INTEGER NOT NULL
        CHECK (duplicate_count >= 2),
    potential_savings INTEGER NOT NULL DEFAULT 0
        CHECK (potential_savings >= 0),

    -- Delete duplicate groups when their parent scan is deleted.
    FOREIGN KEY (scan_id) REFERENCES Scans(scan_id)
        ON DELETE CASCADE
);


-- Connects duplicate groups to the individual files belonging to them.
-- One group can contain multiple files.
-- Each row represents one file's membership in a duplicate group.
CREATE TABLE IF NOT EXISTS DuplicateMembers (
    group_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0
        CHECK (is_primary IN (0, 1)),
    PRIMARY KEY (group_id, file_id),

    -- Remove group memberships when their duplicate group is deleted.
    FOREIGN KEY (group_id) REFERENCES DuplicateGroups(group_id)
        ON DELETE CASCADE,

    -- Remove group memberships when their file is deleted.
    FOREIGN KEY (file_id) REFERENCES Files(file_id)
        ON DELETE CASCADE
);

-- Allow at most one primary file per duplicate group.
CREATE UNIQUE INDEX IF NOT EXISTS idx_duplicate_members_one_primary
ON DuplicateMembers(group_id)
WHERE is_primary = 1;

-- Speeds up retrieving files belonging to a particular scan
-- and sorting them by size.
CREATE INDEX IF NOT EXISTS idx_files_scan_size
ON Files(scan_id, size DESC);

-- Supports case-insensitive extension filtering used by file_repo.py.
CREATE INDEX IF NOT EXISTS idx_files_scan_extension
ON Files(scan_id, LOWER(extension));

-- Speeds up searching for files with matching content hashes.
CREATE INDEX IF NOT EXISTS idx_hashes_value
ON FileHashes(hash_value);

-- Speeds up retrieving duplicate groups belonging to a scan.
CREATE INDEX IF NOT EXISTS idx_duplicate_groups_scan
ON DuplicateGroups(scan_id);