"""Compatibility checks for optional buzzer claims before new firmware releases."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ota"))
from sign_release import feature_claim


class SignedBuzzerTests(unittest.TestCase):
    def test_legacy_profiles_still_validate(self):
        combos = (
            (), ("audio",), ("gateway",), ("gateway", "audio"),
            ("config_ap",), ("config_ap", "audio"),
            ("config_ap", "gateway"), ("config_ap", "gateway", "audio"),
        )
        for letter, names in zip("abcdefgh", combos):
            with self.subTest(letter=letter):
                claim = feature_claim(list(names), "f"*64, "000020D37E6E27AC",
                                      "0.6.17." + letter)
                self.assertEqual(claim["features"], sorted(names))

    def test_buzzer_feature_requires_new_version(self):
        for version in ("0.6.16.b", "0.6.17.b", "0.6.18", "0.6.18.i"):
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    feature_claim(["audio", "buzzer"], "f"*64,
                                  "000020D37E6E27AC", version)
        claim = feature_claim(["audio", "buzzer"], "f"*64,
                              "000020D37E6E27AC", "0.6.18.b")
        self.assertEqual(claim["features"], ["audio", "buzzer"])
        self.assertEqual(claim["version"], "0.6.18.b")

    def test_v0618_identities_always_require_buzzer(self):
        for suffix, required in (("a", []), ("b", ["audio"]), ("h", ["audio", "gateway", "config_ap"])):
            with self.subTest(suffix=suffix):
                with self.assertRaises(ValueError):
                    feature_claim(required, "f"*64, "000020D37E6E27AC",
                                  "0.6.18." + suffix)

    def test_buzzer_cannot_override_variant_roles(self):
        with self.assertRaises(ValueError):
            feature_claim(["gateway", "buzzer"], "f"*64,
                          "000020D37E6E27AC", "0.6.18.b")
        with self.assertRaises(ValueError):
            feature_claim(["audio", "buzzer", "buzzer"], "f"*64,
                          "000020D37E6E27AC", "0.6.18.b")

    def test_matrix_requires_explicit_opt_in(self):
        s = (ROOT / "tools" / "ota" / "build-release-matrix.ps1").read_text("utf-8")
        self.assertIn("[switch]$Buzzer", s)
        self.assertIn('if ($Version -eq "0.6.18" -and -not $Buzzer)', s)
        self.assertIn('[version]"0.6.18"', s)
        self.assertIn('"-DFEATURE_BUZZER=0"', s)
        self.assertIn('"-DFEATURE_BUZZER=1"', s)
        self.assertIn('if ($Buzzer) { $features += "buzzer" }', s)
        self.assertIn("if ($profile.Audio) { $features += \"audio\" }", s)


if __name__ == "__main__":
    unittest.main()
