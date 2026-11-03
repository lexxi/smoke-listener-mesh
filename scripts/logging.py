#!/usr/bin/env python3
"""Continuous raw serial log of the smoke-listener mesh (pyserial)."""
import argparse
import datetime as dt
import time
from pathlib import Path

import serial
from serial.tools import list_ports


def stamp():
    return dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="Continuous XIAO ESP-NOW logger")
    parser.add_argument("--port", help="e.g. COM5 (required unless exactly one serial port)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--hours", type=float, default=0,
                        help="0 (default) means unlimited; otherwise stop after N hours")
    parser.add_argument("--retry", type=float, default=5,
                        help="Seconds between reconnect attempts")
    args = parser.parse_args()
    if args.hours < 0 or args.retry <= 0:
        parser.error("--hours must be >= 0 and --retry > 0")
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
        with output.open("a", encoding="utf-8", buffering=1) as file:
            while args.hours == 0 or time.monotonic()-started < args.hours*3600:
                try:
                    with serial.Serial(device, args.baud, timeout=1) as port:
                        msg = f"{stamp()} [LOGGER] Connected to {device}"
                        print(msg)
                        file.write(msg + "\n")
                        while args.hours == 0 or time.monotonic()-started < args.hours*3600:
                            raw = port.readline()
                            if not raw:
                                continue
                            line = raw.decode("utf-8", errors="replace").strip()
                            if not line:
                                continue
                            msg = f"{stamp()} {line}"
                            file.write(msg + "\n")
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
