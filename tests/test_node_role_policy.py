"""Fail-closed node-role policy tests, no ESP32 hardware needed."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("node_role_policy", ROOT/"web"/"node_role_policy.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
NODE = "000010637C6E27AC"

class NodeRoleTests(unittest.TestCase):
    def test_missing_role_blocks_new_release(self):
        with self.assertRaisesRegex(ValueError, "Keine freigegebene"):
            module.check_release_role({"version":"0.6.15","features":["audio"],"target":NODE}, {})

    def test_wrong_role_blocks(self):
        with self.assertRaisesRegex(ValueError, "nicht für Zielrolle"):
            module.check_release_role({"version":"0.6.15","features":["gateway"],"target":NODE}, {NODE:"listener"})

    def test_exact_roles(self):
        for role,features in [
            ("mesh",[]), ("listener",["audio"]), ("gateway",["gateway"]),
            ("hybrid",["audio","gateway"]), ("listener",["audio","config_ap"])]:
            self.assertEqual(module.check_release_role(
                {"version":"0.6.15","features":features,"target":NODE},
                {NODE:role}),role)

    def test_unknown_features_or_unsigned_claim_block(self):
        with self.assertRaises(ValueError):
            module.check_release_role({"version":"0.6.15","features":None,"target":NODE},{NODE:"mesh"})

    def test_legacy_release_not_blocked(self):
        self.assertEqual(module.check_release_role(
            {"version":"0.6.14","features":None,"target":NODE},{}),"legacy")

    def test_explicit_file_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"roles.json"
            self.assertEqual(module.load_roles(path),{})
            path.write_text(json.dumps({NODE:"listener"}),encoding="utf-8")
            self.assertEqual(module.load_roles(path),{NODE:"listener"})
            path.write_text(json.dumps({NODE:"invented"}),encoding="utf-8")
            with self.assertRaises(ValueError):module.load_roles(path)
            path.write_text(json.dumps({"NOT_A_NODE":"listener"}),encoding="utf-8")
            with self.assertRaises(ValueError):module.load_roles(path)

if __name__=="__main__":
    unittest.main()
