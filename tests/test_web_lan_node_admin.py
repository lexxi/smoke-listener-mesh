"""Configured LAN IPs and CIDR networks can modify remote node state."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from flask import Flask
from access_control import lan_node_write_allowed


class LanNodeAdminTests(unittest.TestCase):
    def test_exact_ip_and_no_default(self):
        app = Flask(__name__)
        env = {"SMOKE_WEB_LAN": "1", "SMOKE_LAN_NODE_ADMIN_IPS": "192.168.98.50"}
        with patch.dict(os.environ, env, clear=True):
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.50"}):
                self.assertTrue(lan_node_write_allowed())
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.51"}):
                self.assertFalse(lan_node_write_allowed())
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "1"}, clear=True):
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.50"}):
                self.assertFalse(lan_node_write_allowed())

    def test_cidr_and_mixed_entries(self):
        app = Flask(__name__)
        values = {"SMOKE_WEB_LAN": "1", "SMOKE_LAN_NODE_ADMIN_IPS":
                  "192.168.98.0/24, 10.1.2.3, 2001:db8:1::/64"}
        with patch.dict(os.environ, values, clear=True):
            for address, expected in (
                ("192.168.98.39", True),
                ("192.168.98.254", True),
                ("192.168.99.1", False),
                ("10.1.2.3", True),
                ("10.1.2.4", False),
                ("2001:db8:1::50", True),
                ("2001:db8:2::50", False),
            ):
                with self.subTest(address=address):
                    with app.test_request_context("/", environ_base={"REMOTE_ADDR": address}):
                        self.assertEqual(lan_node_write_allowed(), expected)

    def test_invalid_cidr_and_proxy_headers(self):
        app = Flask(__name__)
        values = {"SMOKE_WEB_LAN": "1", "SMOKE_LAN_NODE_ADMIN_IPS":
                  "192.168.98.5/24, invalid, 192.168.98.50"}
        with patch.dict(os.environ, values, clear=True):
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.42"}):
                self.assertFalse(lan_node_write_allowed())
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.60"},
                                          headers={"X-Forwarded-For": "192.168.98.50"}):
                self.assertFalse(lan_node_write_allowed())
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.50"}):
                self.assertTrue(lan_node_write_allowed())

    def test_disabled_lan_denies_cidr(self):
        app = Flask(__name__)
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "0",
                                     "SMOKE_LAN_NODE_ADMIN_IPS": "192.168.98.0/24"}, clear=True):
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.50"}):
                self.assertFalse(lan_node_write_allowed())


if __name__ == "__main__":
    unittest.main()
