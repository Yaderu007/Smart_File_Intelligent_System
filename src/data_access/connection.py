
import sqlite3
from pathlib import Path


# Find the root directory of our project.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define the location of our SQLite database file.
DATABASE_PATH = PROJECT_ROOT / "smart_files.db"


def get_connection():
    """
    Open and configure a connection to our SQLite database.

    Returns:
        sqlite3.Connection: An open database connection.

    Raises:
        sqlite3.Error: If opening or configuring the database fails.
    """

    # Start with no connection so we can safely handle failures.
    connection = None

    try:

        connection = sqlite3.connect(DATABASE_PATH)

        # Enables coloumn access by name instead of index, which is more readable.
        connection.row_factory = sqlite3.Row

        # Enable foreign key constraints for the connection.
        connection.execute("PRAGMA foreign_keys = ON;")

        return connection

    except sqlite3.Error as error:

        # Close the connection if it was opened before the error.
        if connection is not None:
            connection.close()

        # Add context to the error and propagate it to the caller.
        raise sqlite3.Error(
            f"Failed to connect to SQLite database at {DATABASE_PATH}: {error}"
        ) from error



def initialize_database():
    """
    Initialize the SQLite database using schema.sql.

    Creates the database tables if they do not already exist.

    Raises:
        FileNotFoundError: If schema.sql cannot be found.
        OSError: If schema.sql cannot be read.
        sqlite3.Error: If SQLite cannot execute the schema.
    """

    # Locate schema.sql in the project root directory.
    schema_path = PROJECT_ROOT / "schema.sql"

    # Check that the schema file exists before attempting to read it.
    if not schema_path.is_file():
        raise FileNotFoundError(
            f"Database schema file not found: {schema_path}"
        )

    try:
        # Read the SQL statements from schema.sql.
        schema_sql = schema_path.read_text(encoding="utf-8")

    except OSError as error:
        # Report filesystem errors, such as permission problems.
        raise OSError(
            f"Failed to read database schema at {schema_path}"
        ) from error

    # Open a database connection using our existing helper function.
    connection = get_connection()

    try:
        # Execute all CREATE TABLE statements in schema.sql.
        connection.executescript(schema_sql)

    except sqlite3.Error:
        # Preserve the original SQLite error for the caller.
        raise

    finally:
        # Always close the connection when initialization finishes.
        connection.close()
