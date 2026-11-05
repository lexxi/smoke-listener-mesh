"""Guard Web gateway logger autostart and stopped-status disclosure."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import logger_control


class LoggerStartupTests(unittest.TestCase):
    def test_autostart_launches_once(self):
        state = logger_control.status_data()
        self.assertIn("ota_reserved", state)
        self.assertIn("running", state)
        class FakeProcess:
            pid = 12345
            def poll(self):
                return None

        def fake_start():
            logger_control.process = FakeProcess()

        with patch.object(logger_control, "process", None), \
             patch.object(logger_control, "_start_owned_locked", side_effect=fake_start) as launch:
            first = logger_control.autostart()
            second = logger_control.autostart()
            self.assertEqual(launch.call_count, 1)
            self.assertTrue(first["running"])
            self.assertTrue(second["running"])
            self.assertEqual(second["pid"], 12345)

    def test_autostart_does_not_open_port_when_reserved(self):
        previous = logger_control.ota_reserved
        try:
            logger_control.ota_reserved = True
            with patch.object(logger_control, "_start_owned_locked") as launch:
                logger_control.autostart()
                launch.assert_not_called()
        finally:
            logger_control.ota_reserved = previous

    def test_running_pid_does_not_imply_serial_connection(self):
        class FakeProcess:
            pid = 613
            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "serial.log"
            logfile.write_text("2026-11-05 [LOGGER] Disconnected: COM16 unavailable; retry in 5s\\n", encoding="utf-8")
            # FakeProcess provides a live PID, but disconnected log takes priority.
            with patch.object(logger_control, "process", FakeProcess()), \\
                 patch.object(logger_control, "session", logfile):
                data = logger_control.status_data()
                self.assertTrue(data["running"])
                self.assertFalse(data["connected"])
                self.assertEqual(data["connection_state"], "disconnected")
                logfile.write_text(
                    "2026-11-05 [LOGGER] Disconnected: COM16 unavailable; retry in 5s\\n"
                    "2026-11-05 [LOGGER] Connected to COM16\\n", encoding="utf-8"
                )
                data = logger_control.status_data()
                self.assertTrue(data["connected"])
                self.assertEqual(data["connection_state"], "connected")
                logfile.write_text(
                    "2026-11-05 [LOGGER] Connected to COM16\\n"
                    "2026-11-05 [LOGGER] Disconnected: unplugged; retry in 5s\\n", encoding="utf-8"
                )
                self.assertFalse(logger_control.status_data()["connected"])

    def test_ui_warns_when_stopped(self):
        dashboard = (ROOT / "web/templates/index.html").read_text(encoding="utf-8")
        self.assertIn('id="logger-warning"', dashboard)
        self.assertIn("Knotenstatus derzeit nicht aktuell", dashboard)
        self.assertIn("Nicht verbunden · PID", dashboard)
        app = (ROOT / "web/app.py").read_text(encoding="utf-8")
        self.assertIn("logger_state = autostart()", app)


if __name__ == "__main__":
    unittest.main()
