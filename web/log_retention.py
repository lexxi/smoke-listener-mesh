"""Opt-in retention for completed mesh and logger-control logs.

Never touches the newest log of either type; avoids unlinking active files.
The CLI defaults to dry-run. Only the designated ROOT/log directory is scanned.
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

PATTERNS = ("mesh_*.log", "logger_control_*.log")


def cleanup_logs(directory: Path, *, days: int, max_mb: int,
                 now: float | None = None, apply: bool = False) -> list[Path]:
    if not 1 <= days <= 3650 or not 1 <= max_mb <= 10240:
        raise ValueError("days must be 1..3650 and max_mb 1..10240")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Log directory must exist and must not be a symlink")
    cutoff = (time.time() if now is None else now) - days * 86400
    size_limit = max_mb * 1024 * 1024
    groups = []
    for pattern in PATTERNS:
        items = [p for p in directory.glob(pattern)
                 if p.is_file() and not p.is_symlink() and p.parent == directory]
        groups.append(items)
    all_files = [p for group in groups for p in group]
    # A currently open file is normally the newest of its group.
    # Keep newest files even if old or above the configured quota.
    protected = {max(group, key=lambda p: (p.stat().st_mtime_ns, p.name))
                 for group in groups if group}

    # Additionally preserve files opened by any visible process. On piCore,
    # the logger and this process share the same UID, making /proc readable.
    proc = Path("/proc")
    if proc.is_dir():
        for pid in proc.iterdir():
            if not pid.name.isdigit():
                continue
            fd_dir = pid / "fd"
            try:
                handles = list(fd_dir.iterdir())
            except (OSError, PermissionError):
                continue
            for handle in handles:
                try:
                    resolved = Path(os.readlink(handle))
                    if resolved in all_files:
                        protected.add(resolved)
                except (OSError, ValueError):
                    continue

    candidates = [p for p in all_files if p not in protected]
    ordered = sorted(candidates, key=lambda p: (p.stat().st_mtime_ns, p.name))
    removed: list[Path] = []
    total = sum(p.stat().st_size for p in all_files)
    for path in ordered:
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        if stat.st_mtime < cutoff or total > size_limit:
            if apply:
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
            removed.append(path)
            total -= stat.st_size
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup completed Smoke Mesh logs")
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--max-mb", type=int, default=512)
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete old files (default: dry-run)")
    args = parser.parse_args()
    selected = cleanup_logs(args.dir, days=args.days, max_mb=args.max_mb,
                            apply=args.apply)
    for item in selected:
        print(("DELETE " if args.apply else "WOULD DELETE ") + str(item))
    print(f"{len(selected)} completed log file(s) selected")


if __name__ == "__main__":
    main()
