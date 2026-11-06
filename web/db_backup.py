"""Consistent SQLite online backups with seven daily generations.

Opt-in via SMOKE_DB_BACKUP_DIR. Writes a temporary backup, validates it,
then atomically publishes it. Never copies a live SQLite database file.
"""
from __future__ import annotations

import datetime as dt
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def backup_database(source: Path, destination_dir: Path, *, keep: int = 7,
                    today: dt.date | None = None) -> Path:
    if not 1 <= keep <= 365:
        raise ValueError("keep must be between 1 and 365")
    if destination_dir.is_symlink():
        raise ValueError("Backup directory must not be a symlink")
    if not source.is_file():
        raise FileNotFoundError(source)
    destination_dir.mkdir(parents=True, exist_ok=True)
    date = today or dt.datetime.now(dt.timezone.utc).date()
    target = destination_dir / f"mesh_{date:%Y%m%d}.db"
    if target.exists():
        # Never overwrite a successful backup of the same day.
        with closing(sqlite3.connect(f"file:{target}?mode=ro", uri=True)) as check:
            if check.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError(f"Existing daily backup is corrupt: {target}")
        return target

    temporary = destination_dir / f".{target.name}.{os.getpid()}.partial"
    if temporary.exists():
        raise FileExistsError(temporary)
    try:
        with closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)) as original:
            with closing(sqlite3.connect(temporary)) as snapshot:
                original.backup(snapshot, pages=128, sleep=0.05)
                if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup failed SQLite integrity check")
        # Prevent a concurrent invocation from overwriting an existing backup.
        if target.exists():
            raise FileExistsError(target)
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

    # Keep only seven newest completed daily snapshots. Unknown files untouched.
    backups = sorted(destination_dir.glob("mesh_????????.db"), reverse=True)
    for expired in backups[keep:]:
        if expired.is_file() and not expired.is_symlink():
            expired.unlink()
    return target
