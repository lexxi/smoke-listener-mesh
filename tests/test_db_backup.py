"""SQLite snapshot tests: live WAL database, generation cap, corrupted backup."""
import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from db_backup import backup_database


class DatabaseBackupTests(unittest.TestCase):
    def test_online_backup_includes_committed_wal_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "mesh.db"
            with sqlite3.connect(source) as con:
                con.execute("PRAGMA journal_mode=WAL")
                con.execute("CREATE TABLE messages (payload TEXT)")
                con.execute("INSERT INTO messages VALUES ('first')")
            writer = sqlite3.connect(source)
            try:
                writer.execute("INSERT INTO messages VALUES ('second')")
                writer.commit()
                writer.execute("INSERT INTO messages VALUES ('uncommitted')")
                dest = backup_database(source, root / "backup", today=dt.date(2026, 11, 6))
                with sqlite3.connect(dest) as snapshot:
                    rows = snapshot.execute("SELECT payload FROM messages ORDER BY rowid").fetchall()
                    self.assertEqual(rows, [("first",), ("second",)])
                    self.assertEqual(snapshot.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                writer.rollback()
            finally:
                writer.close()

    def test_seven_daily_generations_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "mesh.db"
            with sqlite3.connect(source) as con:
                con.execute("CREATE TABLE events (id INTEGER)")
            backup_dir = root / "backups"
            for day in range(1, 10):
                with sqlite3.connect(source) as con:
                    con.execute("INSERT INTO events VALUES (?)", (day,))
                backup_database(source, backup_dir, today=dt.date(2026, 11, day))
            files = sorted(path.name for path in backup_dir.glob("mesh_*.db"))
            self.assertEqual(len(files), 7)
            self.assertEqual(files[0], "mesh_20261103.db")
            self.assertEqual(files[-1], "mesh_20261109.db")
            existing = backup_database(source, backup_dir, today=dt.date(2026, 11, 6))
            with sqlite3.connect(existing) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM events").fetchone()[0], 6)
            self.assertEqual(len(list(backup_dir.glob("mesh_*.db"))), 7)

    def test_backup_file_can_be_removed_after_connections_close(self):
        # On Windows unlink fails while sqlite3 connections still hold handles.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "mesh.db"
            with sqlite3.connect(source) as con:
                con.execute("CREATE TABLE messages (payload TEXT)")
            backup_dir = root / "backup"
            target = backup_database(source, backup_dir, today=dt.date(2026, 11, 6))
            self.assertEqual(backup_database(source, backup_dir,
                                             today=dt.date(2026, 11, 6)), target)
            target.unlink()
            self.assertFalse(target.exists())

    def test_missing_source_and_bad_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(FileNotFoundError):
                backup_database(root / "missing.db", root / "backup")
            source = root / "mesh.db"
            with sqlite3.connect(source) as con:
                con.execute("CREATE TABLE messages (payload TEXT)")
            backup_dir = root / "backup"
            backup_dir.mkdir()
            invalid = backup_dir / "mesh_20261106.db"
            invalid.write_bytes(b"not a sqlite database")
            with self.assertRaises(sqlite3.DatabaseError):
                backup_database(source, backup_dir, today=dt.date(2026, 11, 6))
            self.assertEqual(invalid.read_bytes(), b"not a sqlite database")


if __name__ == "__main__":
    unittest.main()
