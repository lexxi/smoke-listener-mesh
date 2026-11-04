"""Static safeguards for the Windows Arduino-CLI release matrix."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT/"tools/ota/build-release-matrix.ps1").read_text(encoding="utf-8")

class MatrixTests(unittest.TestCase):
    def test_compiled_flags_and_separate_build_directories(self):
        for flag in ("FEATURE_GATEWAY", "FEATURE_AUDIO", "FEATURE_CONFIG_AP",
                     "FEATURE_BATTERY=0", "FEATURE_BUZZER=0"):
            self.assertIn(flag, SCRIPT)
        self.assertIn("compiler.cpp.extra_flags", SCRIPT)
        self.assertIn("--build-path", SCRIPT)
        self.assertIn("--output-dir", SCRIPT)
        self.assertIn("Get-FileHash -Algorithm SHA256", SCRIPT)

    def test_only_role_matched_targets_get_signatures(self):
        self.assertIn("node_roles.json", SCRIPT)
        self.assertIn('$roleMap[$_] -eq $profile.Role', SCRIPT)
        self.assertIn('"--features"', SCRIPT)
        self.assertIn('$signer verify', SCRIPT)
        self.assertIn("if ($BuildOnly)", SCRIPT) if "if ($BuildOnly)" in SCRIPT else self.assertIn("-not $BuildOnly", SCRIPT)

    def test_reject_overwrite_and_dont_upload(self):
        self.assertIn('Ausgabeverzeichnis existiert bereits', SCRIPT)
        self.assertNotIn("remote_ota.py",SCRIPT)
        self.assertNotIn("/api/remote/start",SCRIPT)

if __name__=="__main__":
    unittest.main()
