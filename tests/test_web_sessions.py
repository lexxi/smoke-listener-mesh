"""Regression tests for session isolation and logger selection."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("mesh_web", Path(__file__).resolve().parents[1] / "web" / "app.py")
mesh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mesh)


def rx(stamp, name, origin, via, seq):
    return (f"{stamp} [RX] name={name} origin={origin} via={via} boot=ABCD "
            f"seq={seq} ttl=3 hops=0 type=HEARTBEAT rssi=-70 dBm channel=6 AUTH=OK\n")


def tx(stamp, origin, seq):
    return f"{stamp} [TX] origin={origin} boot=ABCD seq={seq} ttl=3 status=0\n"


class SessionTests(unittest.TestCase):
    def test_current_and_archived_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            logs = base / "logs"
            logs.mkdir()
            archive = logs / "mesh_20261101_120000.log"
            current = logs / "mesh_20261103_120000.log"
            node = "000094457F6E27AC"
            old_logger = "000020D37E6E27AC"
            new_logger = "000010637C6E27AC"
            archive.write_text(tx("2026-11-01 12:00:00", old_logger, 1) +
                               rx("2026-11-01 12:00:01", "Kueche", node, "AC:27:6E:7F:45:94", 1))
            current.write_text(tx("2026-11-03 12:00:00", new_logger, 1) +
                               rx("2026-11-03 12:00:01", "Kueche", node, "AC:27:6E:7F:45:94", 2) +
                               rx("2026-11-03 12:00:16", "Kueche", node, "AC:27:6E:7F:45:94", 3))
            with patch.object(mesh, "db_path", base / "web" / "data" / "mesh.db"), \
                 patch.object(mesh, "log_dirs", [logs]), \
                 patch.object(mesh, "offsets", {}), \
                 patch.object(mesh, "nodes_config", return_value={}):
                live = mesh.snapshot()
                self.assertEqual(live["total"], 2)
                self.assertEqual(live["logger_mac"], "AC:27:6E:7C:63:10")
                self.assertEqual(live["selected_file"], str(current.resolve()))
                archived = mesh.snapshot(str(archive.resolve()))
                self.assertEqual(archived["total"], 1)
                self.assertEqual(archived["logger_mac"], "AC:27:6E:7E:D3:20")
                self.assertEqual(len(live["sessions"]), 2)
                with self.assertRaises(ValueError):
                    mesh.snapshot(str(base / "secret.log"))


if __name__ == "__main__":
    unittest.main()
