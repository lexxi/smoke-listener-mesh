"""LAN dashboard is read-only; no login or password requirement."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from access_control import check_configuration, lan_enabled, authorized
from flask import Flask


class LanAccessTests(unittest.TestCase):
    def test_off_by_default(self):
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "0"}, clear=True):
            self.assertFalse(lan_enabled())
            check_configuration()

    def test_lan_requires_no_password(self):
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "1"}, clear=True):
            self.assertTrue(lan_enabled())
            check_configuration()

    def test_privileged_is_loopback_only(self):
        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.23"}):
            self.assertFalse(authorized())
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            self.assertTrue(authorized())


if __name__ == "__main__":
    unittest.main()
