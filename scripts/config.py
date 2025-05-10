from pathlib import Path

DB_BACKUP_DIR = Path("backups")
DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DB_PATH = DB_BACKUP_DIR / "metadata.db"
