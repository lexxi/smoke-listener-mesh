#!/usr/bin/env python3
"""Continuous raw serial log of the smoke-listener mesh (pyserial)."""
import argparse
import datetime as dt
import time
import os
from pathlib import Path

import serial
from serial.tools import list_ports


def stamp():
    return dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


class RotatingSerialLog:
    """Rotate line-buffered output at a configured size; 0 disables rotation.

    Each chunk is a separate mesh_*.log file. Never renames or deletes a file
    currently open by this logger; existing files are append-only.
    """

    def __init__(self, base: Path, max_bytes: int):
        self.base = base
        self.max_bytes = max_bytes
        self.part = 0
        self.file = None
        self.size = 0

    def _path(self):
        if self.part == 0:
            return self.base
        return self.base.with_name(f"{self.base.stem}_part{self.part:04d}{self.base.suffix}")

    def __enter__(self):
        self.base.parent.mkdir(parents=True, exist_ok=True)
        self._open()
        return self

    def _open(self):
        path = self._path()
        self.file = path.open("a", encoding="utf-8", buffering=1)
        self.size = path.stat().st_size

    def write_line(self, message: str):
        data = (message + "\n").encode("utf-8")
        if self.max_bytes and self.size and self.size + len(data) > self.max_bytes:
            self.file.close()
            self.part += 1
            self._open()
        self.file.write(message + "\n")
        self.size += len(data)

    def __exit__(self, *_):
        if self.file is not None:
            self.file.close()


def main():
    parser = argparse.ArgumentParser(description="Continuous XIAO ESP-NOW logger")
    parser.add_argument("--port", help="e.g. COM5 (required unless exactly one serial port)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--hours", type=float, default=0,
                        help="0 (default) means unlimited; otherwise stop after N hours")
    parser.add_argument("--rotate-mb", type=int, default=0,
                        help="Rotate raw log in MB chunks (0 = off, Windows default)")
    parser.add_argument("--quiet-lines", action="store_true",
                        help="Do not duplicate each raw line to stdout/diagnostics")
    parser.add_argument("--retry", type=float, default=5,
                        help="Seconds between reconnect attempts")
    args = parser.parse_args()
    if args.hours < 0 or args.retry <= 0 or args.rotate_mb < 0:
        parser.error("--hours and --rotate-mb must be >= 0; --retry must be > 0")
    ports = list(list_ports.comports())
    if args.port:
        device = args.port
    elif len(ports) == 1:
        device = ports[0].device
    else:
        print("Available ports:", ", ".join(p.device for p in ports) or "none")
        parser.error("Specify --port COMx")
    output = args.out or Path("log") / ("mesh_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    print(f"Port={device}; output={output}; hours={args.hours or 'unlimited'}")
    print("Stop with Ctrl+C")
    try:
        with RotatingSerialLog(output, args.rotate_mb * 1024 * 1024) as file:
            while args.hours == 0 or time.monotonic()-started < args.hours*3600:
                try:
                    with serial.Serial(device, args.baud, timeout=1) as port:
                        msg = f"{stamp()} [LOGGER] Connected to {device}"
                        print(msg)
                        file.write_line(msg)
                        while args.hours == 0 or time.monotonic()-started < args.hours*3600:
                            raw = port.readline()
                            if not raw:
                                continue
                            line = raw.decode("utf-8", errors="replace").strip()
                            if not line:
                                continue
                            msg = f"{stamp()} {line}"
                            file.write(msg + "\n")
                            if not args.quiet_lines:
                                print(msg, flush=True)
                except (serial.SerialException, OSError) as exc:
                    msg = f"{stamp()} [LOGGER] Disconnected: {exc}; retry in {args.retry}s"
                    print(msg, flush=True)
                    file.write(msg + "\n")
                    time.sleep(args.retry)
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()
