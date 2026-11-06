"""Ensure LAN access is opt-in and protected by a strong configuration."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from access_control import check_configuration, lan_enabled, verify_password
from werkzeug.security import generate_password_hash


class LanAccessTests(unittest.TestCase):
    def test_off_by_default(self):
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "0"}, clear=True):
            self.assertFalse(lan_enabled())
            check_configuration()

    def test_requires_password_and_secret(self):
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "1"}, clear=True):
            with self.assertRaises(RuntimeError):
                check_configuration()
        with patch.dict(os.environ, {
            "SMOKE_WEB_LAN": "1",
            "SMOKE_WEB_PASSWORD_HASH": generate_password_hash("test-password"),
            "SMOKE_WEB_SECRET_KEY": "short"
        }, clear=True):
            with self.assertRaises(RuntimeError):
                check_configuration()

    def test_password_check(self):
        values = {
            "SMOKE_WEB_LAN": "1",
            "SMOKE_WEB_PASSWORD_HASH": generate_password_hash("correct-password"),
            "SMOKE_WEB_SECRET_KEY": "a" * 48,
        }
        with patch.dict(os.environ, values, clear=True):
            check_configuration()
            self.assertTrue(verify_password("correct-password"))
            self.assertFalse(verify_password("wrong-password"))


if __name__ == "__main__":
    unittest.main()
