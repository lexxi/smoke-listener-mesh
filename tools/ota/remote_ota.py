#!/usr/bin/env python3
"""Signed remote OTA over ESP-NOW via one USB gateway. Requires v0.6.11+ mesh firmware.

No USB cable to the target. Run in stage-only mode or explicitly --deploy.
Never put the signing private key on this computer/service.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

import serial
from prepare_transfer import build_plan

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ACTIONS = {"STATUS", "ARM", "VERIFY", "ACTIVATE", "REBOOT", "CONFIRM"}
REPLY = re.compile(
    r"\[MGMT\] REPLY origin=([0-9A-F]{16}) action=([A-Z]+) result=(\d+)"
    r" nonce=([0-9A-F]{16}) running=app(\d+) boot=app(\d+)"
    r" state=(\d+) staged=(\d+) verified=(\d+) peer=(\d+)"
    r" version=(\d+\.\d+\.\d+)"
)


def numeric(v: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}", v):
        raise ValueError("Version must be numeric X.Y.Z")
    return tuple(map(int, v.split(".")))


def mgmt(port_name: str, target: str, action: str = "STATUS",
         nonce: str = "") -> dict:
    if action not in ACTIONS:
        raise ValueError("Invalid remote command")
    if action != "STATUS" and not re.fullmatch(r"[0-9A-F]{16}", nonce):
        raise ValueError("Missing target-issued one-time nonce")
    command = f"MGMT {target} {action}"
    if action != "STATUS":
        command += " " + nonce
    print(f"[REMOTE] {action} target={target} gateway={port_name}", flush=True)
    ser = serial.Serial(port=None, baudrate=115200, timeout=0.35, write_timeout=5)
    try:
        ser.dtr = False
        ser.rts = False
        ser.port = port_name
        ser.open()
        time.sleep(2.5)  # allow ESP32-C3 USB gateway boot/serial initialization
        ser.reset_input_buffer()
        ser.write((command + "\n").encode("ascii"))
        ser.flush()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", "replace").strip()
            match = REPLY.search(line)
            if match and match[1] == target and match[2] == action:
                d = match.groups()
                status = {
                    "target": d[0], "action": d[1], "result": int(d[2]),
                    "nonce": d[3], "running": int(d[4]), "boot": int(d[5]),
                    "state": int(d[6]), "staged": bool(int(d[7])),
                    "verified": bool(int(d[8])), "peer": bool(int(d[9])),
                    "version": d[10],
                }
                print("[REMOTE] STATUS " + " ".join(f"{k}={v}" for k, v in status.items()), flush=True)
                if status["result"] != 0:
                    raise RuntimeError(f"{action} refused by target (result={status['result']}); inspect remote status")
                return status
            if line.startswith("[MGMT] ERROR") or line.startswith("[MGMT] TIMEOUT"):
                raise RuntimeError(f"Gateway: {line}")
    finally:
        if ser.is_open:
            ser.close()
    raise RuntimeError(f"{action}: no authenticated reply from target; do NOT assume that command failed or succeeded")


def command_child(label: str, arguments: list[str]) -> None:
    print(f"[REMOTE] == {label} ==", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-u", *arguments], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line.rstrip(), flush=True)
    result = proc.wait()
    if result:
        raise RuntimeError(f"{label}: exit code {result}; boot unchanged unless separately activated")


def deploy(args, plan: dict) -> None:
    target = plan["target"]
    first = mgmt(args.gateway, target)
    if first["running"] not in (0, 1) or first["boot"] != first["running"] or first["state"] not in (0, 2):
        raise RuntimeError("Target boot state unsuitable for OTA; inspect running/boot/state")
    if numeric(plan["version"]) <= numeric(first["version"]):
        raise RuntimeError("Same/older signed release refused (no downgrade)")
    if not args.deploy:
        print("[REMOTE] MODE: STAGE_ONLY; boot is not changed", flush=True)
    else:
        print("[REMOTE] MODE: DEPLOY; stage, verify, activate, reboot, confirm", flush=True)

    common = ["--port", args.gateway, "--image", str(args.image),
              "--manifest", str(args.manifest), "--public-key", str(args.public_key)]
    command_child("SIGNATURE", [str(HERE / "send_manifest.py"), *common])
    armed = mgmt(args.gateway, target, "ARM", mgmt(args.gateway, target)["nonce"])
    if armed["version"] != first["version"]:
        raise RuntimeError("Target version changed during preparation")

    command_child("IMAGE", [str(HERE / "send_image.py"), *common,
                            "--flash-stage", "--timeout", "1800"])
    verified = mgmt(args.gateway, target, "VERIFY", mgmt(args.gateway, target)["nonce"])
    if not verified["verified"] or not verified["staged"] or verified["boot"] != verified["running"]:
        raise RuntimeError("Remote flash readback or boot invariants failed")
    print("[REMOTE] STAGED_AND_VERIFIED; inactive firmware ready, old boot still selected", flush=True)

    if not args.deploy:
        print("[REMOTE] DONE STAGE_ONLY BOOT_UNCHANGED", flush=True)
        return

    activated = mgmt(args.gateway, target, "ACTIVATE", verified["nonce"])
    if activated["boot"] == activated["running"]:
        raise RuntimeError("ACTIVATE did not change selected boot slot")
    print("[REMOTE] ACTIVATED. Requesting reboot; new image must pass mesh health check.", flush=True)
    reboot = mgmt(args.gateway, target, "REBOOT", activated["nonce"])
    if reboot["boot"] == reboot["running"]:
        raise RuntimeError("REBOOT response does not show new boot slot")

    deadline = time.monotonic() + 75
    pending = None
    time.sleep(8)
    while time.monotonic() < deadline:
        try:
            current = mgmt(args.gateway, target)
        except RuntimeError as exc:
            print(f"[REMOTE] Awaiting new boot/mesh: {exc}", flush=True)
            time.sleep(4)
            continue
        if current["version"] == first["version"] and current["boot"] == current["running"]:
            raise RuntimeError("Old firmware running: rollback or boot change failed; old version retained")
        if current["version"] == plan["version"] and current["state"] == 2:
            print("[REMOTE] VALID: target already confirmed new firmware", flush=True)
            return
        if current["version"] == plan["version"] and current["state"] == 1:
            pending = current
            if current["peer"]:
                # Device also requires 15s uptime and PENDING_VERIFY state.
                try:
                    confirmed = mgmt(args.gateway, target, "CONFIRM", current["nonce"])
                    if confirmed["state"] != 2:
                        raise RuntimeError("Confirmation did not reach VALID")
                    print("[REMOTE] SUCCESS: signed image booted and VALID; rollback not needed", flush=True)
                    return
                except RuntimeError as exc:
                    print(f"[REMOTE] Confirmation pending: {exc}", flush=True)
        time.sleep(5)
    raise RuntimeError("No safe confirmation within timeout; pending image must roll back on its watchdog reboot")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gateway", required=True, help="COM14 (Garage) or COM12 (Kueche)")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--public-key", type=Path, required=True)
    p.add_argument("--deploy", action="store_true", help="Explicitly allow activate/reboot/confirm after stage")
    p.add_argument("--status-only", action="store_true", help="Only interrogate remote node; never flash")
    args = p.parse_args()
    try:
        plan = build_plan(args.image, args.manifest, args.public_key)
        numeric(plan["version"])
        if args.status_only:
            mgmt(args.gateway, plan["target"])
        else:
            deploy(args, plan)
        return 0
    except (ValueError, OSError, RuntimeError, serial.SerialException) as exc:
        print(f"[REMOTE] FAILED: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
