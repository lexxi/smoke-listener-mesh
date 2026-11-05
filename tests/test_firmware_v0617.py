"""Static checks for the isolated v0.6.17 firmware release candidate."""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
V17 = REPO / "firmware" / "mesh-v0.6.17"
V16 = REPO / "firmware" / "mesh-v0.6.16"


class FirmwareV0617Tests(unittest.TestCase):
    def test_new_sketch_and_headers_available(self):
        for name in (
            "mesh-v0.6.17.ino", "audio_monitor.h", "buzzer_diagnostic.h",
            "feature_config.h", "ota_auth.h", "ota_version.h"
        ):
            self.assertTrue((V17 / name).is_file(), name)

    def test_firmware_identity_bumped_without_overwriting_old(self):
        new = (V17 / "mesh-v0.6.17.ino").read_text(encoding="utf-8")
        old = (V16 / "mesh-v0.6.16.ino").read_text(encoding="utf-8")
        self.assertIn('#define SMOKE_FIRMWARE_VERSION "0.6.17"', new)
        self.assertIn('Smoke Listener Mesh v0.6.17 |', new)
        self.assertIn('#define SMOKE_FIRMWARE_VERSION "0.6.16"', old)

    def test_buzzer_is_opt_in(self):
        config = (V17 / "feature_config.h").read_text(encoding="utf-8")
        self.assertRegex(config, r"#define FEATURE_BUZZER 0")
        sketch = (V17 / "mesh-v0.6.17.ino").read_text(encoding="utf-8")
        self.assertIn('command.equalsIgnoreCase("BUZZER 2X2")', sketch)
        self.assertIn('command.equalsIgnoreCase("BUZZER STOP")', sketch)

    def test_release_matrix_preserves_eight_profile_contract(self):
        matrix = (REPO / "tools" / "ota" / "build-release-matrix.ps1").read_text(encoding="utf-8")
        self.assertIn('[string]$Version = "0.6.17"', matrix)
        self.assertIn("-DFEATURE_BUZZER=0", matrix)
        self.assertEqual(len(re.findall(r'@\\{Name=', matrix)), 8)


if __name__ == "__main__":
    unittest.main()
