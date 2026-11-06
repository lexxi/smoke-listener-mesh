"""Test safe log rotation chunks and inactive-file retention without serial hardware."""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "scripts"))
from log_retention import cleanup_logs
import importlib.util
spec = importlib.util.spec_from_file_location("smoke_serial_logger", ROOT / "scripts" / "logging.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RotatingSerialLog = module.RotatingSerialLog


class LogMaintenanceTests(unittest.TestCase):
    def test_log_rotates_in_complete_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "mesh_20261106.log"
            with RotatingSerialLog(base, 20) as logger:
                for i in range(5):
                    logger.write_line(f"line-{i}")
            parts = sorted(Path(temp).glob("mesh_*.log"))
            self.assertGreater(len(parts), 1)
            lines = [line for part in parts for line in part.read_text().splitlines()]
            self.assertEqual(lines, [f"line-{i}" for i in range(5)])
            self.assertTrue(all(p.stat().st_size <= 20 for p in parts))

    def test_serial_logger_writes_real_received_line(self):
        # Exercise main(), not only RotatingSerialLog, to catch stale file.write().
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "mesh_test.log"
            connection = MagicMock()
            connection.__enter__.return_value.readline.side_effect = [
                b"sample-heartbeat\\n", KeyboardInterrupt()
            ]
            with patch.object(module.serial, "Serial", return_value=connection):
                with patch.object(sys, "argv", ["logging.py", "--port", "FAKE",
                                                "--out", str(target), "--rotate-mb", "1",
                                                "--quiet-lines"]):
                    module.main()
            self.assertIn("sample-heartbeat", target.read_text())
            self.assertIn("[LOGGER] Connected", target.read_text())

    def test_dry_run_and_protect_newest(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            old = d / "mesh_old.log"
            current = d / "mesh_current.log"
            old.write_text("older")
            current.write_text("newer")
            now = time.time()
            import os
            os.utime(old, (now - 40 * 86400, now - 40 * 86400))
            selected = cleanup_logs(d, days=30, max_mb=512, now=now)
            self.assertEqual(selected, [old])
            self.assertTrue(old.exists())
            selected = cleanup_logs(d, days=30, max_mb=512, now=now, apply=True)
            self.assertEqual(selected, [old])
            self.assertFalse(old.exists())
            self.assertTrue(current.exists())

    def test_quota_and_no_unrelated_files(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            unrelated = d / "important.txt"
            unrelated.write_text("do not touch")
            older = d / "mesh_01.log"
            newer = d / "mesh_02.log"
            older.write_bytes(b"x" * 750000)
            newer.write_bytes(b"x" * 750000)
            import os
            os.utime(older, (time.time() - 100, time.time() - 100))
            selected = cleanup_logs(d, days=30, max_mb=1, apply=True)
            self.assertEqual(selected, [older])
            self.assertTrue(newer.exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
