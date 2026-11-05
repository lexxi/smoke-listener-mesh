"""Static safeguards for all eight Windows Arduino-CLI builds."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT/"tools/ota/build-release-matrix.ps1").read_text(encoding="utf-8")

class MatrixTests(unittest.TestCase):
    def test_compile_all_eight_with_isolated_source(self):
        for flag in ("FEATURE_GATEWAY", "FEATURE_AUDIO", "FEATURE_CONFIG_AP",
                     "FEATURE_BATTERY=0", "FEATURE_BUZZER=0"):
            self.assertIn(flag,SCRIPT)
        for name in ("core", "audio", "gateway", "hybrid",
                     "core_ap", "audio_ap", "gateway_ap", "hybrid_ap"):
            self.assertIn('Name="'+name+'"',SCRIPT)
        self.assertIn("compiler.cpp.extra_flags",SCRIPT)
        self.assertIn("--build-path",SCRIPT)
        self.assertIn("--output-dir",SCRIPT)
        self.assertIn("Get-FileHash -Algorithm SHA256",SCRIPT)
        self.assertIn("$variantSketch",SCRIPT)

    def test_sign_every_variant_for_every_registered_target(self):
        self.assertIn("node_targets.json",SCRIPT)
        self.assertIn('foreach ($target in $targets)',SCRIPT)
        self.assertIn('--features',SCRIPT)
        self.assertIn('$release = $Version + "." + $letter',SCRIPT)
        self.assertIn('--version $release',SCRIPT)
        self.assertIn('$signer verify',SCRIPT)
        self.assertIn("if (-not $BuildOnly)",SCRIPT)

    def test_v0617_is_default_and_has_trusted_usb_gateway(self):
        self.assertIn('[string]$Version = "0.6.17"', SCRIPT)
        sketch = (ROOT/"firmware/mesh-v0.6.17/mesh-v0.6.17.ino").read_text(encoding="utf-8")
        self.assertIn('#define SMOKE_FIRMWARE_VERSION "0.6.17"', sketch)
        self.assertIn("MGMT_TRUST_GATEWAY=0x00000CEC7E6E27ACULL", sketch)
        self.assertIn("origin==MGMT_TRUST_GATEWAY", sketch)

    def test_json_target_array_is_not_double_wrapped(self):
        self.assertIn("$parsed = ConvertFrom-Json -InputObject $json", SCRIPT)
        self.assertNotIn("@(ConvertFrom-Json -InputObject $json)", SCRIPT)
        self.assertIn("foreach ($target in $parsed)", SCRIPT)

    def test_output_root_is_resolved_for_dotnet_writealltext(self):
        self.assertIn("GetUnresolvedProviderPathFromPSPath($OutputRoot)", SCRIPT)
        self.assertLess(
            SCRIPT.index("GetUnresolvedProviderPathFromPSPath($OutputRoot)"),
            SCRIPT.index("if (Test-Path -LiteralPath $OutputRoot)")
        )
        self.assertIn("[System.IO.File]::WriteAllText($variantSketch", SCRIPT)

    def test_safe_output(self):
        self.assertIn("Ausgabe existiert bereits",SCRIPT)
        self.assertNotIn("remote_ota.py",SCRIPT)
        self.assertNotIn("/api/remote/start",SCRIPT)

if __name__=="__main__":
    unittest.main()
