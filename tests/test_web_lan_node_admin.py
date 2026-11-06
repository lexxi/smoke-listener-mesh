"""Only a specifically configured LAN host can modify remote node state."""
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

    def test_no_cidr_or_proxy_headers(self):
        app = Flask(__name__)
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "1", "SMOKE_LAN_NODE_ADMIN_IPS": "192.168.98.0/24"}, clear=True):
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.50"}):
                self.assertFalse(lan_node_write_allowed())
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "1", "SMOKE_LAN_NODE_ADMIN_IPS": "192.168.98.50"}, clear=True):
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.98.60"}, headers={"X-Forwarded-For": "192.168.98.50"}):
                self.assertFalse(lan_node_write_allowed())


if __name__ == "__main__":
    unittest.main()
