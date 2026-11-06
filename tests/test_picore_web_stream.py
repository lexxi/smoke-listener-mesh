"""Tests for the piCore webserver stdout stream rotator."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "picore" / "rotate-web-stream.py"
spec = importlib.util.spec_from_file_location("web_stream_rotation", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WebStreamRotationTests(unittest.TestCase):
    def test_rotates_at_limit_and_keeps_five_generations(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "web-server.log"
            with module.RotatingStream(output, max_bytes=10, keep=5) as log:
                log.write(b"0123456789" * 9)
            self.assertEqual(output.stat().st_size, 10)
            self.assertEqual(len(list(Path(temp).glob("web-server.log*"))), 6)
            self.assertEqual(output.read_bytes(), b"0123456789")
            self.assertTrue(all(p.stat().st_size <= 10 for p in Path(temp).glob("*")))

    def test_appends_existing_log_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "web-server.log"
            output.write_bytes(b"old\n")
            with module.RotatingStream(output, max_bytes=10, keep=3) as log:
                log.write(b"new\r\nnext\n")
            self.assertEqual((Path(temp) / "web-server.log.1").read_bytes(), b"old\nnew\r\nnext")
            self.assertEqual(output.read_bytes(), b"\n")

    def test_real_pipe_and_eof(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "web-server.log"
            result = subprocess.run([sys.executable, str(SCRIPT),
                                     "--output", str(output), "--max-kb", "1",
                                     "--keep", "2"],
                                    input=b"Hello Pi\n", capture_output=True,
                                    timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(output.read_bytes(), b"Hello Pi\n")


if __name__ == "__main__":
    unittest.main()
