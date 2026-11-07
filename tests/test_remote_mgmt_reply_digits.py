"""Regression: remote management replies may contain digits in action names."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "ota"))
from remote_ota import REPLY


class RemoteReplyActionTests(unittest.TestCase):
    def test_buzzer_2x2_reply(self):
        line = (
            "[MGMT] REPLY origin=000020D37E6E27AC action=BUZZER_2X2 result=0 "
            "nonce=7D1D16D628E824EB running=app0 boot=app0 "
            "state=2 staged=0 verified=0 peer=1 version=0.6.20.b name=Testknoten"
        )
        match = REPLY.search(line)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(2), "BUZZER_2X2")
        self.assertEqual(match.group(3), "0")

    def test_existing_commands_still_parse(self):
        for action in ("STATUS", "NAME_SET", "RESTART", "BUZZER_TEST"):
            with self.subTest(action=action):
                line = (
                    "[MGMT] REPLY origin=000020D37E6E27AC action=" + action +
                    " result=0 nonce=7D1D16D628E824EB running=app0 boot=app0 "
                    "state=2 staged=0 verified=0 peer=1 version=0.6.20.b name=Testknoten"
                )
                self.assertEqual(REPLY.search(line).group(2), action)


if __name__ == "__main__":
    unittest.main()
