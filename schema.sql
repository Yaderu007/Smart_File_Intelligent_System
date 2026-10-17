-- Stores information about each directory scanning operation.
-- Each scan has a unique ID, even if the same directory is scanned multiple times.
CREATE TABLE IF NOT EXISTS Scans (
    scan_id INTEGER PRIMARY KEY,
    scan_path TEXT NOT NULL,
    scan_timestamp TEXT NOT NULL,
    scan_duration INTEGER,
    file_count INTEGER NOT NULL DEFAULT 0,
    total_size INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'incomplete'
);

-- Stores metadata collected for each file during a scan.
-- Each file record belongs to one scan through scan_id.
CREATE TABLE IF NOT EXISTS Files (
    file_id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL,

    path TEXT NOT NULL,
    name TEXT NOT NULL,
    size INTEGER,
    extension TEXT,
    category TEXT NOT NULL DEFAULT 'Other',
    created TEXT,
    modified TEXT,
    accessed_timestamp TEXT,
    accessible INTEGER NOT NULL DEFAULT 1,
    error TEXT,

    FOREIGN KEY (scan_id) REFERENCES Scans(scan_id)
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

    FOREIGN KEY (file_id) REFERENCES Files(file_id)
);

-- Stores information about groups of files with identical contents.
-- Individual files belonging to each group are stored in DuplicateMembers.
CREATE TABLE IF NOT EXISTS DuplicateGroups (
    group_id INTEGER PRIMARY KEY,
    hash_value TEXT NOT NULL,
    duplicate_count INTEGER NOT NULL
        CHECK (duplicate_count >= 2),
    potential_savings INTEGER NOT NULL DEFAULT 0
        CHECK (potential_savings >= 0)
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
    FOREIGN KEY (group_id) REFERENCES DuplicateGroups(group_id),
    FOREIGN KEY (file_id) REFERENCES Files(file_id)
);