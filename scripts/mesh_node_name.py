#!/usr/bin/env python3
"""Configure a Smoke Listener Mesh v0.5.3 node over USB serial (pyserial)."""
import argparse
import re
import sys
import time
import serial

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("port", help="Windows COM port, e.g. COM7")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--set", dest="name", help="Set persistent name (1-24: A-Z, 0-9, - and _)")
    g.add_argument("--get", action="store_true", help="Read name")
    g.add_argument("--reset", action="store_true", help="Clear name")
    args = p.parse_args()
    if args.name is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", args.name):
        p.error("invalid name; allowed: 1-24 ASCII letters/digits/hyphen/underscore")
    command = "NAME SET " + args.name if args.name is not None else ("NAME RESET" if args.reset else "NAME GET")
    try:
        with serial.Serial(args.port, 115200, timeout=0.25, write_timeout=3) as ser:
            # USB CDC may reset the board when opened.
            time.sleep(2)
            ser.reset_input_buffer()
            ser.write((command + "\n").encode("ascii"))
            ser.flush()
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("[CONFIG]"):
                    print(line)
                    if " ERROR" in line or " WARNING" in line:
                        return 1
                    if line.startswith("[CONFIG] OK") or line.startswith("[CONFIG] name="):
                        return 0
            print("No configuration reply (check port, firmware version and USB CDC settings)", file=sys.stderr)
            return 2
    except serial.SerialException as exc:
        print("Serial error:", exc, file=sys.stderr)
        return 3

if __name__ == "__main__":
    sys.exit(main())
