"""Webserver regression checks for four-component firmware versions."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"web"))
SPEC=importlib.util.spec_from_file_location("mesh_web_four_part", ROOT/"web"/"app.py")
mesh=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mesh)

class WebFirmwareVersionsTests(unittest.TestCase):
    def test_receiver_logs_keep_variant(self):
        line=("2026-11-04 10:00:00 [RX] name=1OG origin=000010637C6E27AC "
              "via=AC:27:6E:7C:63:10 boot=ABCDEF seq=1 ttl=3 hops=0 "
              "type=HEARTBEAT rssi=-60 dBm channel=6 fw=0.6.15.b AUTH=OK")
        parsed=mesh.parse_line(line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[-1],"0.6.15.b")

    def test_sender_logs_keep_variant(self):
        line=("2026-11-04 10:00:00 [TX] origin=000010637C6E27AC "
              "boot=ABCDEF seq=2 ttl=3 status=0 fw=0.6.15.c")
        parsed=mesh.parse_tx(line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[-1],"0.6.15.c")

if __name__=="__main__":
    unittest.main()
