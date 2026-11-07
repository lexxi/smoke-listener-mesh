"""LAN logger control is opt-in and must not grant other privileged APIs."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

from app import app
import logger_control


class LoggerLanAccessTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.env = patch.dict(os.environ, {
            "SMOKE_WEB_LAN": "1",
            "SMOKE_LAN_LOGGER_IPS": "192.168.98.50",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def request_status(self, address):
        return self.client.get("/api/logger/status", environ_overrides={"REMOTE_ADDR": address})

    def test_logger_token_only_for_allowed_client(self):
        self.assertNotIn("token", self.request_status("192.168.98.51").get_json())
        self.assertEqual(logger_control.token, self.request_status("192.168.98.50").get_json()["token"])

    def test_disallowed_client_cannot_stop(self):
        result = self.client.post("/api/logger/stop", headers={"X-Logger-CSRF": logger_control.token},
                                  environ_overrides={"REMOTE_ADDR": "192.168.98.51"})
        self.assertEqual(403, result.status_code)

    def test_allowed_client_must_supply_csrf(self):
        result = self.client.post("/api/logger/stop", environ_overrides={"REMOTE_ADDR": "192.168.98.50"})
        self.assertEqual(403, result.status_code)

    def test_allowed_client_can_stop_when_idle(self):
        with patch.object(logger_control, "running", return_value=False):
            result = self.client.post("/api/logger/stop", headers={"X-Logger-CSRF": logger_control.token},
                                      environ_overrides={"REMOTE_ADDR": "192.168.98.50"})
        self.assertEqual(200, result.status_code)

    def test_ota_remains_forbidden_on_allowlisted_ip(self):
        result = self.client.post("/api/remote/ota", environ_overrides={"REMOTE_ADDR": "192.168.98.50"})
        self.assertEqual(403, result.status_code)

    def test_no_allowlist_means_no_logger_access(self):
        with patch.dict(os.environ, {"SMOKE_LAN_LOGGER_IPS": ""}):
            self.assertNotIn("token", self.request_status("192.168.98.50").get_json())
            result = self.client.post("/api/logger/stop", environ_overrides={"REMOTE_ADDR": "192.168.98.50"})
            self.assertEqual(403, result.status_code)

    def test_ota_reservation_blocks_stop(self):
        with patch.object(logger_control, "ota_reserved", True):
            result = self.client.post("/api/logger/stop", headers={"X-Logger-CSRF": logger_control.token},
                                      environ_overrides={"REMOTE_ADDR": "192.168.98.50"})
        self.assertEqual(409, result.status_code)


if __name__ == "__main__":
    unittest.main()
