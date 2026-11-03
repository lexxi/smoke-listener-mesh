#!/usr/bin/env python3
"""Exclusive serial runner for the mesh OTA RAM-only transport test."""
import argparse
import datetime as dt
import re
import sys
import time
from pathlib import Path

import serial


def main():
    parser = argparse.ArgumentParser(description="ESP-NOW OTA RAM-only test (not firmware flashing)")
    parser.add_argument("--port", required=True, help="Gateway serial port, e.g. COM15")
    parser.add_argument("--target", required=True, help="16 hex chars of target node ID")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--blocks", type=int, default=16, help="v0.5.7: 1..4096 RAM-only blocks of 96 bytes; v0.5.6 only supports 16")
    parser.add_argument("--timeout", type=float, default=900, help="Stop after N seconds; default 900 for stress tests")
    parser.add_argument("--out", type=Path, default=None, help="Optional timestamped test log file")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9A-Fa-f]{16}", args.target):
        parser.error("--target must be 16 hexadecimal digits, e.g. 000094457F6E27AC")
    if not 1 <= args.blocks <= 4096:
        parser.error("--blocks must be 1..4096")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    output = args.out or Path("log") / ("ota_test_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
    output.parent.mkdir(parents=True, exist_ok=True)
    print("STOP the normal logger before this command; only one process can own the COM port.")
    print(f"Target: {args.target.upper()} | blocks: {args.blocks} | bytes: {args.blocks * 96} | output: {output}")
    try:
        with serial.Serial(args.port, args.baud, timeout=1, write_timeout=3) as port:
            # Opening a serial port can reset some boards. Allow the C3 to boot.
            time.sleep(3)
            port.reset_input_buffer()
            command = f"OTA TEST {args.target.upper()}{' ' + str(args.blocks) if args.blocks != 16 else ''}\n".encode("ascii")
            port.write(command)
            port.flush()
            deadline = time.monotonic() + args.timeout
            outcome = None
            with output.open("w", encoding="utf-8", buffering=1) as logfile:
                while time.monotonic() < deadline:
                    raw = port.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    stamped = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S") + " " + line
                    print(stamped, flush=True)
                    logfile.write(stamped + "\n")
                    if "[OTA] DONE" in line:
                        if f"blocks={args.blocks}" in line:
                            outcome = "success"
                        elif args.blocks == 16 and "blocks=" not in line:
                            outcome = "success"  # v0.5.6 legacy response
                        else:
                            print("FAIL: firmware reported unexpected block count.", file=sys.stderr)
                            outcome = "failure"
                        break
                    if "[OTA] FAIL" in line or "[OTA] ERROR" in line or "[OTA] HMAC_FAILED" in line:
                        outcome = "failure"
                        break
            if outcome == "success":
                print("PASS: target acknowledged all test blocks. No firmware was written.")
                return 0
            print("FAIL: OTA transport incomplete (see log).")
            return 1
    except (serial.SerialException, OSError) as exc:
        print(f"Serial port unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
