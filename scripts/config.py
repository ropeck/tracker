"""Configuration constants for database backup paths.

Defines the location for database backup files used by the inventory app.
Ensures the backup directory exists on startup.
"""

from pathlib import Path

#: Directory where backup SQLite database files are stored
DB_BACKUP_DIR = Path("backups")
DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

#: Path to the main backup database file used at runtime
BACKUP_DB_PATH = DB_BACKUP_DIR / "metadata.db"
