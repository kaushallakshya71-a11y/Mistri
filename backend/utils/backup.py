"""
Mistri Database Backup & Disaster Recovery Utility
Implements safe, non-blocking online SQLite backups via sqlite3.Connection.backup.
"""
import sqlite3
import os
import re
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
DB_PATH = Path(__file__).resolve().parent.parent / "db" / "mistri.db"

SAFE_FILENAME_PATTERN = re.compile(r'^[A-Za-z0-9_\-]+\.db$')

def ensure_backup_dir():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def create_database_backup() -> dict:
    """
    Creates an atomic, consistent online backup of the SQLite database.
    Does not lock concurrent readers or writers in WAL mode.
    """
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mistri_backup_{timestamp}.db"
    dest_path = BACKUP_DIR / filename

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Source database not found at {DB_PATH}")

    src_conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    dest_conn = sqlite3.connect(str(dest_path))

    try:
        # Use SQLite online backup API
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    size_bytes = dest_path.stat().st_size
    return {
        "filename": filename,
        "path": str(dest_path),
        "size_bytes": size_bytes,
        "size_kb": round(size_bytes / 1024, 2),
        "created_at": datetime.now().isoformat()
    }

def list_database_backups() -> list:
    """List all available SQLite database backups sorted newest first."""
    ensure_backup_dir()
    backups = []
    for f in BACKUP_DIR.glob("*.db"):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups

def restore_database_backup(backup_filename: str) -> dict:
    """
    Restores the database from a verified backup snapshot.
    Guards against path traversal attacks.
    """
    ensure_backup_dir()
    if "/" in backup_filename or "\\" in backup_filename or ".." in backup_filename or not SAFE_FILENAME_PATTERN.match(backup_filename):
        raise ValueError(f"Invalid backup filename '{backup_filename}'. Slashes and path traversal sequences are forbidden. Only filenames ending with .db are allowed.")

    filename = backup_filename

    src_backup_path = BACKUP_DIR / filename
    if not src_backup_path.exists():
        raise FileNotFoundError(f"Backup file '{filename}' does not exist.")

    # Create safety backup of current state before restoring
    pre_restore_backup = create_database_backup()

    backup_conn = sqlite3.connect(str(src_backup_path))
    live_conn = sqlite3.connect(str(DB_PATH), timeout=30.0)

    try:
        backup_conn.backup(live_conn)
    finally:
        live_conn.close()
        backup_conn.close()

    return {
        "message": f"Database successfully restored from {filename}.",
        "restored_from": filename,
        "safety_snapshot": pre_restore_backup["filename"]
    }
