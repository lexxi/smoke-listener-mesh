"""Guard Web gateway logger autostart and stopped-status disclosure."""
import sys
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
        with patch.object(logger_control, "_start_owned_locked") as launch, \
             patch.object(logger_control, "running", side_effect=[False, True]):
            first = logger_control.autostart()
            second = logger_control.autostart()
            self.assertEqual(launch.call_count, 1)
            self.assertTrue(second["running"])

    def test_autostart_does_not_open_port_when_reserved(self):
        previous = logger_control.ota_reserved
        try:
            logger_control.ota_reserved = True
            with patch.object(logger_control, "_start_owned_locked") as launch:
                logger_control.autostart()
                launch.assert_not_called()
        finally:
            logger_control.ota_reserved = previous

    def test_ui_warns_when_stopped(self):
        dashboard = (ROOT / "web/templates/index.html").read_text(encoding="utf-8")
        self.assertIn('id="logger-warning"', dashboard)
        self.assertIn("Knotenstatus derzeit nicht aktuell", dashboard)
        app = (ROOT / "web/app.py").read_text(encoding="utf-8")
        self.assertIn("logger_state = autostart()", app)


if __name__ == "__main__":
    unittest.main()
