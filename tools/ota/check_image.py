#!/usr/bin/env python3
"""Preflight an ESP32-C3 application image against an explicitly specified OTA slot."""
import argparse
import hashlib
from pathlib import Path


def number(value):
    return int(value, 0)


def check(image, slot_bytes):
    data = image.read_bytes()
    problems = []
    if not data:
        problems.append("Firmware image is empty.")
    elif data[0] != 0xE9:
        problems.append("Image header has no ESP-IDF magic 0xE9.")
    elif len(data) < 32:
        problems.append("Image header is too short.")
    if len(data) > slot_bytes:
        problems.append(f"Image ({len(data)} bytes) exceeds OTA partition ({slot_bytes} bytes).")
    print(f"Image       : {image}")
    print(f"Size        : {len(data):,} bytes")
    print(f"OTA slot    : {slot_bytes:,} bytes (entered by user)")
    print(f"Free space  : {slot_bytes-len(data):,} bytes")
    print(f"SHA-256     : {hashlib.sha256(data).hexdigest()}")
    if problems:
        for item in problems:
            print("FAIL:", item)
        return 1
    print("PASS: Basic image-format and size preflight.")
    print("NOT VERIFIED: target chip, signature, firmware compatibility, OTA partitions on device, rollback.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Check .bin size against actual OTA slot size")
    parser.add_argument("image", type=Path)
    parser.add_argument("--ota-slot-bytes", type=number, required=True,
                        help="Actual OTA partition size from selected partition table (decimal or 0xhex)")
    args = parser.parse_args()
    if args.ota_slot_bytes <= 0:
        parser.error("--ota-slot-bytes must be positive")
    if not args.image.is_file():
        parser.error("Firmware file not found")
    raise SystemExit(check(args.image, args.ota_slot_bytes))


if __name__ == "__main__":
    main()
