"""Regression for audio management replies and version-gated actions."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "ota"))
from remote_ota import ACTIONS, AUDIO_FIELDS, REPLY, numeric


class AudioManagementTests(unittest.TestCase):
    def test_audio_actions_registered(self):
        self.assertTrue({"AUDIO_STATUS", "AUDIO_RESET"} <= ACTIONS)

    def test_audio_status_reply(self):
        line = (
            "[MGMT] REPLY origin=000020D37E6E27AC action=AUDIO_STATUS result=0 "
            "nonce=F59F1B01EE0885AA running=app0 boot=app0 "
            "state=2 staged=0 verified=0 peer=1 version=0.6.21.b "
            "name=Testknoten audio_ready=1 beeps=24 rejected=3 "
            "groups=5 candidates=2 errors=0"
        )
        base = REPLY.search(line)
        self.assertIsNotNone(base)
        self.assertEqual(base.group(2), "AUDIO_STATUS")
        audio = AUDIO_FIELDS.search(line)
        self.assertIsNotNone(audio)
        self.assertEqual(tuple(map(int, audio.groups())), (1, 24, 3, 5, 2, 0))

    def test_audio_reset_zero_counters(self):
        line = (
            "[MGMT] REPLY origin=000020D37E6E27AC action=AUDIO_RESET result=0 "
            "nonce=F59F1B01EE0885AA running=app0 boot=app0 "
            "state=2 staged=0 verified=0 peer=1 version=0.6.21.b "
            "name=Testknoten audio_ready=1 beeps=0 rejected=0 "
            "groups=0 candidates=0 errors=0"
        )
        self.assertEqual(REPLY.search(line).group(2), "AUDIO_RESET")
        self.assertEqual(tuple(map(int, AUDIO_FIELDS.search(line).groups())),
                         (1, 0, 0, 0, 0, 0))

    def test_incomplete_audio_payload_rejected(self):
        line = "name=Testknoten audio_ready=1 beeps=2 rejected=0 groups=0"
        self.assertIsNone(AUDIO_FIELDS.search(line))

    def test_version_supported(self):
        self.assertLess(numeric("0.6.20.b"), (0, 6, 21))
        self.assertGreaterEqual(numeric("0.6.21.b"), (0, 6, 21))


if __name__ == "__main__":
    unittest.main()
