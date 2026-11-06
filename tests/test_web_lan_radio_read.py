"""LAN may request radio status but must not mutate nodes or perform OTA."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))


class LANRadioReadTests(unittest.TestCase):
    def test_lan_read_action_whitelist(self):
        with patch.dict(os.environ, {"SMOKE_WEB_LAN": "1"}):
            import app as webapp
            import remote
            client = webapp.app.test_client()
            lan = {"REMOTE_ADDR": "192.168.98.42"}
            cfg = client.get("/api/remote/config", environ_overrides=lan)
            self.assertEqual(cfg.status_code, 200)
            data = cfg.get_json()
            self.assertTrue(data["lan_read_only"])
            self.assertTrue(data["csrf"])
            gateway = data["logger_gateway"]
            target = "000094457F6E27AC"
            headers = {"X-Remote-CSRF": data["csrf"]}

            for action in ("NAME_SET", "NAME_RESET", "RESTART"):
                result = client.post("/api/remote/node-action", json={
                    "target": target, "gateway": gateway, "action": action
                }, headers=headers, environ_overrides=lan)
                self.assertEqual(result.status_code, 403)

            result = client.post("/api/remote/start", json={},
                                 headers=headers, environ_overrides=lan)
            self.assertEqual(result.status_code, 403)
            for action in ("STATUS", "NAME_GET"):
                # Invalid gateway should pass the LAN action allowlist and be
                # rejected by ordinary input validation; no radio thread starts.
                result = client.post("/api/remote/node-action", json={
                    "target": target, "gateway": "/invalid", "action": action
                }, headers=headers, environ_overrides=lan)
                self.assertEqual(result.status_code, 400)
            self.assertEqual(client.get("/api/remote/config").status_code, 200)


if __name__ == "__main__":
    unittest.main()
