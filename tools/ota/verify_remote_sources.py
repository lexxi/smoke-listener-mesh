#!/usr/bin/env python3
"""Offline preflight: syntax-check Python sources and protocol invariants, no USB or flash."""
from __future__ import annotations
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "web/app.py", "web/ota.py", "web/remote.py", "web/logger_control.py",
    "web/release_library.py", "tools/ota/remote_ota.py",
    "tools/ota/prepare_transfer.py", "tools/ota/send_manifest.py", "tools/ota/send_image.py",
]

def main() -> int:
    for relative in FILES:
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        print(f"[OK] Python syntax: {relative}")
    for version in ("0.6.11", "0.6.12", "0.6.13"):
        path = ROOT / f"firmware/mesh-v{version}/mesh-v{version}.ino"
        source = path.read_text(encoding="utf-8")
        checks = {
            "version": f'CURRENT_FW_VERSION[]="{version}"' in source,
            "wire compatibility": "MGMT_REQUEST=9, MGMT_REPLY=10" in source and "sizeof(OtaFrame)==165" in source,
            "HMAC validation": "if(!otaVerify(frame))" in source,
            "signed flash verification": "verifyStagedImageReadback();" in source,
            "remote reboot guard": "mgmtActivationDone" in source,
            "pending rollback watchdog": "PENDING_VERIFY timeout" in source,
            "manual rollback hook": "verifyRollbackLater()" in source,
            "trusted garage gateway": "MGMT_TRUST_GARAGE" in source,
            "trusted kueche gateway": "MGMT_TRUST_KUECHE" in source,
        }
        if version == "0.6.13":
            checks.update({
                "authenticated name operations": all(x in source for x in (
                    "MGMT_NAME_GET", "MGMT_NAME_SET", "MGMT_NAME_RESET",
                    "mgmtNonce", "prefs.putString(\"name\",name)")),
                "independent reboot guard": "MGMT_RESTART" in source and "mgmtRebootAt" in source,
                "name reply": "safeName.c_str()" in source,
            })
        for item, valid in checks.items():
            if not valid:
                raise AssertionError(f"{version}: missing {item}")
        print(f"[OK] Firmware source invariants: v{version} (not a C++ compile)")
    print("PASS: offline source preflight. Still compile with Arduino IDE and test on hardware.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
