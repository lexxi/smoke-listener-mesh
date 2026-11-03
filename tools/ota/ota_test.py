#!/usr/bin/env python3
"""One-command signed ESP-NOW OTA staging + readback; NEVER activate boot slot.

The target's COM port stays open throughout the transfer. This prevents a
serial-monitor reconnect from resetting the device and losing auth/arm state.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import serial

from prepare_transfer import build_plan

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_IMAGE = ROOT / "firmware/mesh-v0.6.7/build/esp32.esp32.XIAO_ESP32C3/mesh-v0.6.7.ino.bin"
DEFAULT_MANIFEST = Path(r"C:\mesh-ota-keys\release-1og-067.json")
DEFAULT_KEY = Path(r"C:\mesh-ota-keys\signing-public.pem")
TARGET_NODE = "000010637C6E27AC"


class TargetConsole:
    def __init__(self, port: str, logfile):
        self.port_name = port
        self.logfile = logfile
        self.lines = queue.Queue(maxsize=4096)
        self.history = collections.deque(maxlen=1500)
        self.stop = threading.Event()
        self.ser = serial.Serial(port=None, baudrate=115200, timeout=0.25, write_timeout=5)
        # Avoid deliberately toggling reset/control lines when opening port.
        self.ser.dtr = False
        self.ser.rts = False
        self.ser.port = port
        self.ser.open()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        while not self.stop.is_set():
            try:
                line = self.ser.readline().decode("utf-8", "replace").strip()
            except (serial.SerialException, OSError) as exc:
                self._append(f"[LOCAL SERIAL ERROR] {exc}")
                return
            if line:
                self._append(line)

    def _append(self, line: str):
        self.history.append(line)
        self.logfile.write(f"{datetime.datetime.now().astimezone().isoformat()} TARGET {line}\n")
        self.logfile.flush()
        if any(tag in line for tag in
               ("[FLASH]", "[BOOT]", "[IMAGE] RESULT", "[IMAGE] FLASH_", "[AUTH] REJECT")):
            print("1OG:", line, flush=True)
        try:
            self.lines.put_nowait(line)
        except queue.Full:
            try:
                self.lines.get_nowait()
            except queue.Empty:
                pass
            self.lines.put_nowait(line)

    def _clear(self):
        while True:
            try:
                self.lines.get_nowait()
            except queue.Empty:
                return

    def command(self, text: str, pattern: str, timeout: int = 12) -> str:
        self._clear()
        self.ser.write((text + "\n").encode("ascii"))
        self.ser.flush()
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            try:
                line = self.lines.get(timeout=min(0.5, max(0.01, until - time.monotonic())))
            except queue.Empty:
                if not self.reader.is_alive():
                    raise RuntimeError("COM15 serial reader stopped")
                continue
            if "[CONFIG] ERROR" in line or "[BOOT] VERIFY FAIL" in line:
                raise RuntimeError(f"{text}: {line}")
            if re.search(pattern, line):
                return line
        raise RuntimeError(f"{text}: missing expected response / timeout")

    def close(self):
        self.stop.set()
        self.reader.join(timeout=1)
        self.ser.close()


def run_child(label: str, args: list[str], logfile) -> None:
    print(f"\n== {label} ==", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-u", *args],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        logfile.write(f"{datetime.datetime.now().astimezone().isoformat()} {label} {line}\n")
        logfile.flush()
        print(line, flush=True)
    code = proc.wait()
    if code:
        raise RuntimeError(f"{label}: returned exit code {code}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gateway", default="COM12")
    ap.add_argument("--target-port", default="COM15")
    ap.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--public-key", type=Path, default=DEFAULT_KEY)
    ap.add_argument("--dry-run", action="store_true", help="Only offline verification; never open COM ports")
    args = ap.parse_args()
    if args.gateway.upper() == args.target_port.upper():
        ap.error("Gateway and target must use different COM ports")
    try:
        plan = build_plan(args.image, args.manifest, args.public_key)
        if plan["target"] != TARGET_NODE or plan["version"] != "0.6.7":
            raise ValueError("This test is locked to signed v0.6.7 for the 1OG node")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"STOP: signed release preflight: {exc}", file=sys.stderr)
        return 2
    print(f"Verified offline: version={plan['version']} node={plan['target']} "
          f"bytes={plan['size']} sha256={plan['sha256']}", flush=True)
    print(f"Ports: Kueche={args.gateway} 1OG={args.target_port}; BOOT ACTIVATE is NEVER sent.")
    if args.dry_run:
        print("DRY RUN OK: serial ports untouched.")
        return 0

    folder = ROOT / "log"
    folder.mkdir(exist_ok=True)
    logpath = folder / ("ota_test_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
    target = None
    with logpath.open("w", encoding="utf-8", buffering=1) as logfile:
        print(f"Log: {logpath}")
        try:
            target = TargetConsole(args.target_port, logfile)
            time.sleep(2)
            name = target.command("NAME GET", r"\[CONFIG\] name=.*node=([0-9A-F]{16})")
            if TARGET_NODE not in name:
                raise RuntimeError(f"Wrong target device on {args.target_port}: {name}")
            status = target.command("BOOT STATUS", r"\[BOOT\] running=.*version=0\.6\.6\b")
            if "running=app0" not in status or "boot=app0" not in status or "inactive=app1" not in status:
                raise RuntimeError(f"Unexpected boot slot: {status}")
            target.command("FLASH ARM", r"\[FLASH\] ARMED local_serial_only window=300s")
            common = ["--port", args.gateway, "--image", str(args.image),
                      "--manifest", str(args.manifest), "--public-key", str(args.public_key)]
            run_child("MANIFEST", [str(HERE / "send_manifest.py"), *common], logfile)
            run_child("IMAGE", [str(HERE / "send_image.py"), *common,
                                "--flash-stage", "--timeout", "1800"], logfile)
            flash = target.command("FLASH STATUS", r"\[FLASH\] running=.*staged_valid=[01].*BOOT_UNCHANGED")
            if "running=0.6.6" not in flash or "staged_valid=1" not in flash:
                raise RuntimeError(f"Unexpected flash status: {flash}")
            verified = target.command("BOOT VERIFY",
                r"\[BOOT\] VERIFY PASS signed=0\.6\.7 bytes=1034128 slot=app1 SHA256_OK BOOT_UNCHANGED",
                timeout=40)
            boot = target.command("BOOT STATUS", r"\[BOOT\] running=.*version=0\.6\.6")
            if "running=app0" not in boot or "boot=app0" not in boot:
                raise RuntimeError(f"Boot selection unexpectedly changed: {boot}")
            flags = target.command("BOOT STATUS",
                r"\[BOOT\] activation=LOCAL_ARM_ONLY verified=[01] arm_valid=[01]")
            if "verified=1" not in flags or "arm_valid=0" not in flags:
                raise RuntimeError(f"Unverified/armed state: {flags}")
            print("\nPASS: v0.6.7 signed OTA staged and read back on 1OG."
                  " Boot remains app0/v0.6.6. No activation, no reboot.", flush=True)
            return 0
        except (RuntimeError, OSError, serial.SerialException, subprocess.SubprocessError) as exc:
            print(f"\nSTOP: {exc}\nNo boot activation was requested. Log: {logpath}", file=sys.stderr, flush=True)
            return 1
        finally:
            if target is not None:
                try:
                    # Do not send BOOT ACTIVATE or reset the node.
                    target.close()
                except (serial.SerialException, OSError):
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
