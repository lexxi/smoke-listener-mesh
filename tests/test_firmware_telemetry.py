"""Regression check: the heartbeat version must match the running firmware version."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKETCH = ROOT / "firmware" / "mesh-v0.6.14" / "mesh-v0.6.14.ino"

class FirmwareTelemetryTests(unittest.TestCase):
    def test_heartbeat_version_comes_from_current_version(self):
        source = SKETCH.read_text(encoding="utf-8")
        self.assertIn('CURRENT_FW_VERSION[]="0.6.14"', source)
        match = re.search(r"void sendLocal\(uint8_t type\)\s*\{(.*?)\n\}", source, re.S)
        self.assertIsNotNone(match, "sendLocal() not found")
        function = match.group(1)
        self.assertIn('sscanf(CURRENT_FW_VERSION', function)
        self.assertIn('p.name[21]=(char)major', function)
        self.assertIn('p.name[22]=(char)minor', function)
        self.assertIn('p.name[23]=(char)patch', function)
        self.assertNotRegex(function, r"p\.name\[21\]\s*=\s*0\s*;")

if __name__ == "__main__":
    unittest.main()
