"""Local no-radio tests for signing and real-image chunk preparation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TOOLS = Path(__file__).resolve().parents[1] / "tools" / "ota"
sys.path.insert(0, str(TOOLS))
from sign_release import make_key, sign
from prepare_transfer import build_plan, chunks


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "test.bin"
        header = bytearray(24)
        header[0] = 0xE9
        header[12:14] = (5).to_bytes(2, "little")
        # Header shape + arbitrary payload; not a bootable firmware image.
        self.image.write_bytes(bytes(header) + bytes(range(256)) * 2)
        self.priv = self.root / "private.pem"
        self.pub = self.root / "public.pem"
        self.manifest = self.root / "manifest.json"
        make_key(SimpleNamespace(private_key=self.priv, public_key=self.pub))
        sign(SimpleNamespace(image=self.image, private_key=self.priv,
            target="000094457F6E27AC", version="test-only", out=self.manifest,
            overwrite=False))

    def test_signature_plan_and_padded_chunks(self):
        plan = build_plan(self.image, self.manifest, self.pub)
        payload = list(chunks(self.image))
        self.assertEqual(plan["blocks"], len(payload))
        self.assertEqual(plan["size"], self.image.stat().st_size)
        self.assertEqual(payload[0][0], 0)
        self.assertEqual(len(payload[-1][1]), 96)
        assembled = b"".join(c for _, c in payload)
        self.assertEqual(assembled[:plan["size"]], self.image.read_bytes())

    def test_signed_feature_claim_roundtrip(self):
        self.manifest.unlink()
        sign(SimpleNamespace(image=self.image, private_key=self.priv,
            target="000094457F6E27AC", version="0.6.15", out=self.manifest,
            overwrite=False, features="audio"))
        plan = build_plan(self.image, self.manifest, self.pub)
        self.assertEqual(plan["features"], ["audio"])

    def test_letter_label_is_signed_and_preserved(self):
        self.manifest.unlink()
        sign(SimpleNamespace(image=self.image, private_key=self.priv,
            target="000094457F6E27AC", version="0.6.151", out=self.manifest,
            overwrite=False, features="audio", label="0.6.15b"))
        plan = build_plan(self.image, self.manifest, self.pub)
        self.assertEqual(plan["version"], "0.6.151")
        self.assertEqual(plan["label"], "0.6.15b")
        doc = json.loads(self.manifest.read_text())
        doc["feature_claim"]["label"] = "0.6.15c"
        self.manifest.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, "[Ff]eature"):
            build_plan(self.image, self.manifest, self.pub)

    def test_native_four_component_version_signed(self):
        self.manifest.unlink()
        sign(SimpleNamespace(image=self.image, private_key=self.priv,
            target="000094457F6E27AC", version="0.6.15.b", out=self.manifest,
            overwrite=False, features="audio"))
        plan = build_plan(self.image,self.manifest,self.pub)
        self.assertEqual(plan["version"],"0.6.15.b")
        self.assertEqual(plan["features"],["audio"])

    def test_variant_letter_must_match_features(self):
        self.manifest.unlink()
        with self.assertRaisesRegex(ValueError, "letter"):
            sign(SimpleNamespace(image=self.image, private_key=self.priv,
                target="000094457F6E27AC", version="0.6.15.a",
                out=self.manifest, overwrite=False, features="audio"))

    def test_tampered_feature_claim_is_rejected(self):
        self.manifest.unlink()
        sign(SimpleNamespace(image=self.image, private_key=self.priv,
            target="000094457F6E27AC", version="0.6.15", out=self.manifest,
            overwrite=False, features="audio"))
        doc = json.loads(self.manifest.read_text())
        doc["feature_claim"]["features"] = ["gateway"]
        self.manifest.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, "feature"):
            build_plan(self.image, self.manifest, self.pub)

    def test_unsigned_feature_claim_is_rejected(self):
        doc = json.loads(self.manifest.read_text())
        doc["feature_claim"] = {"features": ["audio"]}
        self.manifest.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            build_plan(self.image, self.manifest, self.pub)

    def test_tampered_image_rejected(self):
        raw = bytearray(self.image.read_bytes())
        raw[-1] ^= 1
        self.image.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            build_plan(self.image, self.manifest, self.pub)

    def test_tampered_manifest_rejected(self):
        doc = json.loads(self.manifest.read_text())
        doc["signed"]["version"] = "forged"
        self.manifest.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            build_plan(self.image, self.manifest, self.pub)


if __name__ == "__main__":
    unittest.main()
