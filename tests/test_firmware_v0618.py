"""Static safeguards for the v0.6.18 opt-in buzzer release candidate."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "firmware" / "mesh-v0.6.18"


class FirmwareV0618Tests(unittest.TestCase):
    def test_release_sources_present(self):
        for name in ("mesh-v0.6.18.ino", "audio_monitor.h", "buzzer_diagnostic.h",
                     "feature_config.h", "ota_auth.h", "ota_version.h"):
            self.assertTrue((FIRMWARE / name).is_file(), name)

    def test_version_and_local_only_buzzer(self):
        sketch = (FIRMWARE / "mesh-v0.6.18.ino").read_text("utf-8")
        self.assertIn('#define SMOKE_FIRMWARE_VERSION "0.6.18"', sketch)
        self.assertIn("Smoke Listener Mesh v0.6.18 |", sketch)
        self.assertIn('command.equalsIgnoreCase("BUZZER 2X2")', sketch)
        self.assertIn("SmokeBuzzer::poll();", sketch)
        self.assertIn("diagnostic_only=1", (FIRMWARE / "audio_monitor.h").read_text("utf-8"))

    def test_default_safe_for_usb(self):
        config = (FIRMWARE / "feature_config.h").read_text("utf-8")
        self.assertIn("#ifndef FEATURE_BUZZER", config)
        self.assertRegex(config, r"#define FEATURE_BUZZER [01]\b")
        self.assertIn("#if FEATURE_BATTERY", config)

    def test_signed_matrix_is_reserved(self):
        script = (ROOT / "tools/ota/build-release-matrix.ps1").read_text("utf-8")
        self.assertIn('[string]$Version = "0.6.18"', script)
        self.assertIn('if ($Version -eq "0.6.18" -and -not $Buzzer)', script)
        self.assertIn('if ($Buzzer) { $features += "buzzer" }', script)
        self.assertEqual(script.count('@{Name='), 8)


if __name__ == "__main__":
    unittest.main()
