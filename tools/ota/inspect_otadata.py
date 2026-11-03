#!/usr/bin/env python3
"""Read-only ESP32 ESP-IDF OTA selection inspection for a saved 8192-byte otadata dump."""
import argparse
import struct
import zlib
from pathlib import Path

STATES = {
    0: "NEW",
    1: "PENDING_VERIFY",
    2: "VALID",
    3: "INVALID",
    4: "ABORTED",
    0xFFFFFFFF: "UNDEFINED",
}
SECTOR_SIZE = 4096
ENTRY_SIZE = 32


def inspect(path: Path, partitions: int) -> int:
    data = path.read_bytes()
    if len(data) != 2 * SECTOR_SIZE:
        raise ValueError(f"Expected 8192 bytes of otadata, got {len(data)}")
    print(f"Source: {path} (READ ONLY)")
    candidates = []
    for slot in range(2):
        raw = data[slot * SECTOR_SIZE:slot * SECTOR_SIZE + ENTRY_SIZE]
        seq = struct.unpack_from("<I", raw, 0)[0]
        state = struct.unpack_from("<I", raw, 24)[0]
        stored_crc = struct.unpack_from("<I", raw, 28)[0]
        # ESP-IDF computes the CRC32 with a 0xFFFFFFFF initial value.
        crc = zlib.crc32(raw[:4], 0xFFFFFFFF) & 0xFFFFFFFF
        erased = raw == b"\xff" * ENTRY_SIZE
        usable = seq != 0xFFFFFFFF and stored_crc == crc and state in (0, 1, 2, 0xFFFFFFFF)
        app = f"ota_{(seq - 1) % partitions}" if usable else "-"
        print(
            f"Entry {slot}: seq=0x{seq:08X} state={STATES.get(state, f'UNKNOWN({state})')} "
            f"crc={'OK' if stored_crc == crc else 'MISMATCH'} "
            f"erased={erased} usable={usable} selected={app}"
        )
        if usable:
            candidates.append((seq, slot, app, state))
    if not candidates:
        print("No usable otadata entry; fallback boot selection depends on partition table.")
    elif len(candidates) == 1:
        print(f"Only usable selection: entry={candidates[0][1]} app={candidates[0][2]}")
    else:
        print("Multiple usable entries: exact boot decision depends on ESP-IDF selection/rollback rules.")
        for item in candidates:
            print(f"  candidate entry={item[1]} seq={item[0]} app={item[2]}")
    print("This cannot prove the installed bootloader's rollback behavior.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Previously saved 8192-byte otadata binary")
    parser.add_argument("--ota-app-count", type=int, default=2, help="Number of OTA app partitions, default: 2")
    args = parser.parse_args()
    if args.ota_app_count < 1:
        parser.error("--ota-app-count must be positive")
    try:
        raise SystemExit(inspect(args.file, args.ota_app_count))
    except (OSError, ValueError) as error:
        parser.exit(2, f"ERROR: {error}\n")
