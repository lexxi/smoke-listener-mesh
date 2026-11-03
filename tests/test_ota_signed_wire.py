"""Offline protocol checks for v0.6.0 signed manifest wire encoding."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"/"ota"))
from sign_release import make_key, sign, canonical_bytes
from send_manifest import encode_manifest
from prepare_transfer import build_plan


class SignedManifestWire(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.image=self.root/"test.bin"
        header=bytearray(24)
        header[0]=0xE9
        header[12:14]=(5).to_bytes(2,"little")
        self.image.write_bytes(bytes(header)+b"\x01"*123)
        self.private=self.root/"private.pem"
        self.public=self.root/"public.pem"
        self.manifest=self.root/"release.json"
        make_key(SimpleNamespace(private_key=self.private,public_key=self.public))
        sign(SimpleNamespace(image=self.image,private_key=self.private,
             target="000010637C6E27AC",version="0.6.0",
             out=self.manifest,overwrite=False))

    def test_canonical_signed_wire(self):
        envelope=json.loads(self.manifest.read_text())
        canonical=canonical_bytes(envelope["signed"])
        sig=bytes.fromhex(envelope["signature_der_hex"])
        blob=encode_manifest(self.manifest)
        self.assertEqual(int.from_bytes(blob[:2],"little"),len(blob))
        self.assertEqual(int.from_bytes(blob[2:4],"little"),len(canonical))
        self.assertEqual(blob[4:4+len(canonical)],canonical)
        self.assertEqual(blob[4+len(canonical)],len(sig))
        self.assertEqual(blob[-len(sig):],sig)
        self.assertLessEqual(len(blob),576)
        self.assertLessEqual((len(blob)+95)//96,6)

    def test_changed_image_is_rejected_before_transport(self):
        self.image.write_bytes(self.image.read_bytes()+b"x")
        with self.assertRaises(ValueError):
            build_plan(self.image,self.manifest,self.public)


if __name__=="__main__":
    unittest.main()
