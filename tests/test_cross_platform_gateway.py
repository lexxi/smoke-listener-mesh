"""Cross-platform gateway configuration regression tests (no USB needed)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
from gateway_config import load_gateway_config, normalize_gateway_port


class CrossPlatformGatewayTests(unittest.TestCase):
    def test_windows_com_unchanged(self):
        self.assertEqual(normalize_gateway_port("com16"), "COM16")
        self.assertEqual(normalize_gateway_port("COM1"), "COM1")

    def test_linux_serial_names(self):
        self.assertEqual(normalize_gateway_port("/dev/ttyACM0"), "/dev/ttyACM0")
        self.assertEqual(normalize_gateway_port("/dev/ttyUSB2"), "/dev/ttyUSB2")
        device = "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_001-if00"
        self.assertEqual(normalize_gateway_port(device), device)

    def test_reject_unsafe_ports(self):
        for port in ("COM0", "/dev/null", "/dev/ttyS0",
                     "/dev/serial/by-id/../../etc/passwd", "/tmp/foo", "", 5):
            with self.subTest(port=port), self.assertRaises(ValueError):
                normalize_gateway_port(port)

    def test_linux_config_and_node(self):
        port = "/dev/serial/by-id/usb-test_gateway-if00"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gateways.json"
            path.write_text(json.dumps({
                "logger_gateway": port, "gateways": {
                    port: {"name": "Gateway", "node": "00000CEC7E6E27AC"}
                }
            }), encoding="utf-8")
            logger, gateways = load_gateway_config(path)
            self.assertEqual(logger, port)
            self.assertEqual(gateways[logger], ("Gateway", "00000CEC7E6E27AC"))

    def test_linux_bad_duplicate_node_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gateways.json"
            path.write_text(json.dumps({
                "logger_gateway": "/dev/ttyACM0",
                "gateways": {
                    "/dev/ttyACM0": {"name": "A", "node": "00000CEC7E6E27AC"},
                    "/dev/ttyUSB0": {"name": "B", "node": "00000CEC7E6E27AC"},
                }
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_gateway_config(path)


if __name__ == "__main__":
    unittest.main()
