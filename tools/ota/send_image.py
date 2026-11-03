#!/usr/bin/env python3
"""Send a signed firmware image as verified bytes via serial gateway and ESP-NOW.

Requires v0.5.9 on both gateway and target; NO FLASH WRITES.
The manifest signature is verified on the PC only. Device signature verification
must be added before any firmware flash mode is enabled.
"""
import argparse
import datetime as dt
import re
import sys
import time
from pathlib import Path

import serial

from prepare_transfer import build_plan, BLOCK_SIZE


def run():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", required=True, help="Gateway COM port, e.g. COM13")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--public-key", type=Path, required=True)
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--timeout", type=int, default=1200)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    try:
        plan = build_plan(args.image, args.manifest, args.public_key)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        p.exit(2, f"ERROR: release preflight failed: {exc}\n")
    if args.timeout <= 0:
        p.error("--timeout must be > 0")
    outfile = args.out or Path("log") / ("image_transfer_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
    outfile.parent.mkdir(parents=True, exist_ok=True)
    print(f"Verified signed release: {plan['version']} target={plan['target']} "
          f"bytes={plan['size']} blocks={plan['blocks']}", flush=True)
    print(f"NO FLASH: log={outfile}", flush=True)
    try:
        with serial.Serial(args.port, args.baud, timeout=1, write_timeout=5) as com, \
                args.image.open("rb") as image, outfile.open("w", encoding="utf-8", buffering=1) as logfile:
            time.sleep(3)
            com.reset_input_buffer()
            com.write(f"IMG BEGIN {plan['target']} {plan['size']} {plan['sha256']}\n".encode("ascii"))
            com.flush()
            next_index = 0
            deadline = time.monotonic() + args.timeout
            started = False
            while time.monotonic() < deadline:
                raw = com.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                logfile.write(f"{dt.datetime.now().astimezone().isoformat()} {line}\n")
                if any(term in line for term in ("[IMAGE] START", "[IMAGE] DONE",
                                                 "[IMAGE] FAIL", "[IMAGE] ERROR",
                                                 "[IMAGE] NEXT", "[IMAGE] SEND")):
                    print(line, flush=True)
                if "[IMAGE] START" in line:
                    started = True
                if "[IMAGE] DONE" in line:
                    if not started or "SHA256_OK" not in line or f"bytes={plan['size']}" not in line:
                        print("FAIL: unexpected completion fields", file=sys.stderr)
                        return 1
                    print("PASS: complete real-image transport + target SHA256; nothing flashed.")
                    return 0
                if "[IMAGE] FAIL" in line or "[IMAGE] ERROR" in line:
                    return 1
                match = re.search(r"\[IMAGE\] NEXT index=(\d+)/(\d+)\b", line)
                if match:
                    index, total = map(int, match.groups())
                    if total != plan["blocks"] or index >= total or index != next_index:
                        print(f"FAIL: invalid gateway request index={index}, expected={next_index}", file=sys.stderr)
                        com.write(b"IMG STOP\n")
                        return 1
                    image.seek(index * BLOCK_SIZE)
                    chunk = image.read(BLOCK_SIZE)
                    if len(chunk) != min(BLOCK_SIZE, plan["size"] - index * BLOCK_SIZE):
                        print("FAIL: image changed while reading", file=sys.stderr)
                        com.write(b"IMG STOP\n")
                        return 1
                    com.write(b"IMG DATA " + chunk.ljust(BLOCK_SIZE, b"\x00").hex().encode("ascii") + b"\n")
                    com.flush()
                    next_index += 1
            com.write(b"IMG STOP\n")
            print("FAIL: timeout waiting for firmware transfer completion", file=sys.stderr)
            return 1
    except (serial.SerialException, OSError) as exc:
        print(f"ERROR: serial/image I/O: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
