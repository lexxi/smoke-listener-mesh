"""OTA target allowlist tests; all feature combinations allowed on every registered C3."""
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

class NodeTargetTests(unittest.TestCase):
    def test_all_eight_variants_allowed_for_registered_node(self):
        for gateway in (False, True):
            for audio in (False, True):
                for ap in (False, True):
                    features = ([ "gateway" ] if gateway else []) + ([ "audio" ] if audio else []) + ([ "config_ap" ] if ap else [])
                    module.check_release_target({"version":"0.6.150","features":features,"target":NODE},{NODE})

    def test_missing_target_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "nicht freigegeben"):
            module.check_release_target({"version":"0.6.150","features":["audio"],"target":NODE},set())

    def test_missing_signed_feature_claim_fails(self):
        with self.assertRaises(ValueError):
            module.check_release_target({"version":"0.6.150","features":None,"target":NODE},{NODE})

    def test_legacy_remains_compatible(self):
        module.check_release_target({"version":"0.6.14","features":None,"target":NODE},set())

    def test_file_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"node_targets.json"
            self.assertEqual(module.load_targets(path),set())
            path.write_text(json.dumps([NODE]),encoding="utf-8")
            self.assertEqual(module.load_targets(path),{NODE})
            for invalid in ([NODE,NODE], ["NOT_A_NODE"], {"node":NODE}, [NODE]*5):
                path.write_text(json.dumps(invalid),encoding="utf-8")
                with self.assertRaises(ValueError):
                    module.load_targets(path)

if __name__=="__main__":
    unittest.main()
