"""Trusted-LAN OTA authorization: node-admin CIDR, never logger-only."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from access_control import ota_admin_allowed, lan_ota_admin_allowed

app = Flask(__name__)


class LanOtaAuthorizationTests(unittest.TestCase):
    def check(self, ip, node_ips, logger_ips="192.168.98.0/24"):
        env = {
            "SMOKE_WEB_LAN": "1",
            "SMOKE_LAN_NODE_ADMIN_IPS": node_ips,
            "SMOKE_LAN_LOGGER_IPS": logger_ips,
        }
        with patch.dict(os.environ, env, clear=False):
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": ip}):
                return ota_admin_allowed()

    def test_trusted_admin_subnet(self):
        self.assertTrue(self.check("192.168.98.20", "192.168.98.0/24"))

    def test_other_subnet_denied(self):
        self.assertFalse(self.check("192.168.99.20", "192.168.98.0/24"))

    def test_logger_only_not_enough(self):
        self.assertFalse(self.check("192.168.98.20", ""))

    def test_loopback_still_allowed(self):
        self.assertTrue(self.check("127.0.0.1", ""))

    def test_no_lan_not_allowed(self):
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "0", "SMOKE_LAN_NODE_ADMIN_IPS": "192.168.98.0/24"}):
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.20"}):
                self.assertFalse(lan_ota_admin_allowed())


if __name__ == "__main__":
    unittest.main()
