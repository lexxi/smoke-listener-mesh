#!/usr/bin/env python3
"""Receive a service's stdout on stdin and keep bounded web-server logs.

Use as the right-hand side of a shell pipe (not on an already-open log file).
No external Python dependencies. The process ends on EOF.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


class RotatingStream:
    def __init__(self, path: Path, max_bytes: int, keep: int):
        if max_bytes < 1 or not 1 <= keep <= 100:
            raise ValueError("max_bytes must be positive; keep must be 1..100")
        self.path = path
        self.max_bytes = max_bytes
        self.keep = keep
        self.handle = None
        self.size = 0

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError("Refusing symlink log file")
        self.handle = self.path.open("ab", buffering=0)
        self.size = self.path.stat().st_size
        return self

    def _rotate(self):
        self.handle.close()
        oldest = self.path.with_name(self.path.name + f".{self.keep}")
        oldest.unlink(missing_ok=True)
        for number in range(self.keep - 1, 0, -1):
            previous = self.path.with_name(self.path.name + f".{number}")
            following = self.path.with_name(self.path.name + f".{number + 1}")
            if previous.is_file() and not previous.is_symlink():
                previous.replace(following)
        if self.path.is_file() and not self.path.is_symlink():
            self.path.replace(self.path.with_name(self.path.name + ".1"))
        self.handle = self.path.open("ab", buffering=0)
        self.size = 0

    def write(self, data: bytes):
        # Split only at newline when possible; preserve all bytes even for
        # non-newline output and extremely long lines.
        while data:
            if self.size >= self.max_bytes:
                self._rotate()
            room = self.max_bytes - self.size
            chunk = data[:room]
            self.handle.write(chunk)
            self.size += len(chunk)
            data = data[len(chunk):]

    def __exit__(self, *_):
        if self.handle:
            self.handle.close()


def main():
    parser = argparse.ArgumentParser(description="Size-bounded piCore web log stream")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-kb", type=int, default=1024)
    parser.add_argument("--keep", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.max_kb <= 102400 or not 1 <= args.keep <= 100:
        parser.error("max-kb must be 1..102400 and keep 1..100")
    with RotatingStream(args.output, args.max_kb * 1024, args.keep) as writer:
        while True:
            piece = os.read(sys.stdin.fileno(), 65536)
            if not piece:
                break
            writer.write(piece)


if __name__ == "__main__":
    main()
