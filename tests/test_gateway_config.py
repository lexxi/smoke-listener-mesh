"""Central gateway configuration and consumers must not diverge."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
sys.path.insert(0, str(WEB))
from gateway_config import load_gateway_config, LOGGER_PORT, LOGGER_NAME, TRUSTED_GATEWAYS
import logger_control
import remote


class GatewayConfigTests(unittest.TestCase):
    def test_default_gateway_is_shared_across_logger_and_ota(self):
        self.assertEqual(LOGGER_PORT, "COM16")
        self.assertEqual(LOGGER_NAME, "Gateway")
        self.assertEqual(TRUSTED_GATEWAYS[LOGGER_PORT][1], "00000CEC7E6E27AC")
        self.assertEqual(logger_control.PORT, LOGGER_PORT)
        self.assertIs(remote.TRUSTED_GATEWAYS, TRUSTED_GATEWAYS)
        self.assertEqual(logger_control.status_data()["port"], LOGGER_PORT)
        self.assertEqual(logger_control.status_data()["name"], LOGGER_NAME)

    def test_config_file_is_single_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gateways.json"
            payload = {
                "logger_gateway": "COM21",
                "gateways": {
                    "COM21": {"name": "Test", "node": "00000CEC7E6E27AC"},
                    "COM22": {"name": "Backup", "node": "000058FE7D6E27AC"}
                }
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            port, gateways = load_gateway_config(path)
            self.assertEqual(port, "COM21")
            self.assertEqual(gateways["COM22"][0], "Backup")
            for update in (
                {"logger_gateway": "COM99"},
                {"gateways": {"COM22": {"name": "Dup", "node": "00000CEC7E6E27AC"}}},
                {"gateways": {"COM21": {"name": "", "node": "00000CEC7E6E27AC"}}},
            ):
                invalid = {**payload, **update}
                path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_gateway_config(path)

    def test_dashboard_has_no_hardcoded_com_port(self):
        template = (WEB / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn("logger-gateway", template)
        self.assertNotIn("Garage · COM14", template)
        self.assertNotIn("Garage Logger an COM14", template)


if __name__ == "__main__":
    unittest.main()
