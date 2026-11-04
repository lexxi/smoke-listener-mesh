"""Offline transport parser tests; no serial device required."""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ota"))
import remote_ota

TARGET = "000010637C6E27AC"

class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.port = None
        self.dtr = True
        self.rts = True
        self.is_open = False
        self.writes = []
        self.result = 0
    def open(self):
        if not self.port:
            raise AssertionError("Serial port was not configured")
        self.is_open = True
    def close(self):
        self.is_open = False
    def reset_input_buffer(self):
        pass
    def write(self, data):
        self.writes.append(data)
        return len(data)
    def flush(self):
        pass
    def readline(self):
        if self.writes:
            return (
                f"[MGMT] REPLY origin={TARGET} action=STATUS result={self.result} "
                "nonce=ABCDEF0123456789 running=app0 boot=app0 state=2 "
                "staged=0 verified=0 peer=1 version=0.6.11\n"
            ).encode("ascii")
        return b""

class RemoteProtocolTests(unittest.TestCase):
    def test_version_comparison(self):
        self.assertLess(remote_ota.numeric("0.6.11"), remote_ota.numeric("0.6.12"))
        with self.assertRaises(ValueError):
            remote_ota.numeric("0.6.beta")
    def test_status_parser_with_configured_serial(self):
        dummy = FakeSerial()
        with mock.patch.object(remote_ota.serial, "Serial", return_value=dummy), \
             mock.patch.object(remote_ota.time, "sleep", return_value=None):
            result = remote_ota.mgmt("COM14", TARGET)
        self.assertEqual(result["version"], "0.6.11")
        self.assertEqual(result["state"], 2)
        self.assertTrue(result["peer"])
        self.assertEqual(dummy.writes[0], f"MGMT {TARGET} STATUS\n".encode())
        self.assertFalse(dummy.is_open)
    def test_name_command_preserves_case_and_parses_name(self):
        class NameSerial(FakeSerial):
            def readline(self):
                if self.writes:
                    return (
                        f"[MGMT] REPLY origin={TARGET} action=NAME_SET result=0 "
                        "nonce=ABCDEF0123456789 running=app1 boot=app1 state=2 "
                        "staged=0 verified=0 peer=1 version=0.6.13 name=Keller_Abgang\\n"
                    ).encode("ascii")
                return b""
        dummy = NameSerial()
        with mock.patch.object(remote_ota.serial, "Serial", return_value=dummy), \\
             mock.patch.object(remote_ota.time, "sleep", return_value=None):
            reply = remote_ota.mgmt("COM14", TARGET, "NAME_SET",
                                    "ABCDEF0123456789", "Keller_Abgang")
        self.assertEqual(reply["name"], "Keller_Abgang")
        self.assertEqual(dummy.writes[0],
                         f"MGMT {TARGET} NAME_SET ABCDEF0123456789 Keller_Abgang\\n".encode())

    def test_reject_invalid_names(self):
        for name in ("", "two words", "äbc", "x" * 20, "bad;command"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                remote_ota.mgmt("COM14", TARGET, "NAME_SET",
                                "ABCDEF0123456789", name)

    def test_manage_requires_version_013_before_sending_commands(self):
        args = mock.Mock(manage_target=TARGET, manage_action="NAME_SET", manage_name="Foo",
                         gateway="COM14")
        old = {"version": "0.6.12", "state": 2, "nonce": "ABCDEF0123456789"}
        with mock.patch.object(remote_ota, "mgmt", return_value=old) as action:
            with self.assertRaisesRegex(RuntimeError, "v0.6.13"):
                remote_ota.manage(args)
        action.assert_called_once_with("COM14", TARGET)

    def test_privileged_command_requires_nonce(self):
        with self.assertRaises(ValueError):
            remote_ota.mgmt("COM14", TARGET, "ACTIVATE")

if __name__ == "__main__":
    unittest.main()
