import sqlite3
from pathlib import Path


# Find the root directory of our project.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define the default location of our SQLite database file.
DATABASE_PATH = PROJECT_ROOT / "smart_files.db"


def get_connection(database_path: str | Path | None = None) -> sqlite3.Connection:
    """
    Open and configure a connection to a SQLite database.

    Enables named column access and foreign-key enforcement.

    Args:
        database_path (str | Path | None): Optional path to the database.
            Defaults to the project's smart_files.db.

    Returns:
        sqlite3.Connection: An open, configured SQLite connection.

    Raises:
        sqlite3.Error: If opening or configuring the database fails.
    """

    # Use the project's database unless a custom path is provided.
    # Custom paths allow tests to use temporary databases.
    db_path = DATABASE_PATH if database_path is None else database_path

    # Start with no connection so failures can be handled safely.
    connection = None

    try:
        # Open a connection to the selected SQLite database.
        connection = sqlite3.connect(db_path)

        # Enable column access by name instead of numeric index.
        # This allows expressions such as row["scan_id"].
        connection.row_factory = sqlite3.Row

        # Enforce foreign-key relationships between database tables.
        connection.execute("PRAGMA foreign_keys = ON;")

        return connection

    except sqlite3.Error as error:
        # Close the connection if it was opened before the error.
        if connection is not None:
            connection.close()

        # Include the selected database path in the error message.
        raise sqlite3.Error(
            f"Failed to connect to SQLite database at {db_path}: {error}"
        ) from error


def initialize_database(database_path: str | Path | None = None) -> None:
    """
    Initialize a SQLite database using schema.sql.

    Creates the database tables if they do not already exist.
    Existing tables are not modified or migrated.

    Args:
        database_path (str | Path | None): Optional path to the database.
            Defaults to the project's smart_files.db.

    Returns:
        None: Creates the database tables without returning a value.

    Raises:
        FileNotFoundError: If schema.sql cannot be found.
        OSError: If schema.sql cannot be read.
        sqlite3.Error: If SQLite cannot execute the schema.
    """

    # Locate schema.sql in the project root directory.
    schema_path = PROJECT_ROOT / "schema.sql"

    # Check that the schema file exists before reading it.
    if not schema_path.is_file():
        raise FileNotFoundError(
            f"Database schema file not found: {schema_path}"
        )

    try:
        # Read the SQL statements defining our database tables.
        schema_sql = schema_path.read_text(encoding="utf-8")

    except OSError as error:
        # Report filesystem errors, such as permission problems.
        raise OSError(
            f"Failed to read database schema at {schema_path}"
        ) from error

    # Open a connection to the selected database.
    # During testing, this can be a temporary database.
    connection = get_connection(database_path)

    try:
        # Execute all CREATE TABLE statements from schema.sql.
        # IF NOT EXISTS prevents errors for existing tables,
        # but does not update their existing columns.
        connection.executescript(schema_sql)

        # Commit the initialization changes.
        connection.commit()

    except sqlite3.Error:
        # Roll back any pending transaction if execution fails.
        connection.rollback()
        raise

    finally:
        # Always close the connection, even if an error occurs.
        connection.close()
