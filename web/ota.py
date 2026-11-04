"""Local-only signed OTA staging web UI. Boot activation is intentionally excluded."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import secrets
import subprocess
import sys
import threading
from pathlib import Path

from flask import Blueprint, abort, jsonify, render_template, request

ROOT = Path(__file__).resolve().parents[1]
OTA = ROOT / "tools" / "ota"
KEY = Path(r"C:\mesh-ota-keys\signing-public.pem")
RELEASES = {
    "0.6.9": {
        "image": ROOT / "firmware/mesh-v0.6.9/build/esp32.esp32.XIAO_ESP32C3/mesh-v0.6.9.ino.bin",
        "manifest": Path(r"C:\mesh-ota-keys\release-1og-069.json"),
        "from_version": "0.6.7",
        "to_version": "0.6.9",
        "node": "000010637C6E27AC",
        "from_slot": "app1",
        "to_slot": "app0",
    },
}
GATEWAY_PORT = "COM12"
TARGET_PORT = "COM15"

bp = Blueprint("ota", __name__)
lock = threading.Lock()
job = {"id": None, "state": "idle", "started": None, "ended": None,
       "version": None, "pid": None, "returncode": None, "lines": [],
       "message": "Noch kein OTA-Test ausgeführt."}
MAX_LINES = 240
csrf_token = secrets.token_urlsafe(32)


def _now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _plan(version: str):
    if version not in RELEASES:
        raise ValueError("Unbekanntes Release.")
    release = RELEASES[version]
    sys.path.insert(0, str(OTA))
    try:
        from prepare_transfer import build_plan
        p = build_plan(release["image"], release["manifest"], KEY)
    finally:
        sys.path.remove(str(OTA))
    if p["target"] != release["node"] or p["version"] != version:
        raise ValueError("Signiertes Manifest passt nicht zu Zielknoten/Version.")
    return p


def _add_line(value: str):
    with lock:
        job["lines"].append(value.rstrip()[:600])
        if len(job["lines"]) > MAX_LINES:
            del job["lines"][:-MAX_LINES]


def _run(version: str):
    release = RELEASES[version]
    command = [
        sys.executable, "-u", str(OTA / "ota_test.py"),
        "--gateway", GATEWAY_PORT,
        "--target-port", TARGET_PORT,
        "--from-version", release["from_version"],
        "--to-version", release["to_version"],
        "--image", str(release["image"]),
        "--manifest", str(release["manifest"]),
        "--public-key", str(KEY),
    ]
    result = None
    try:
        # No shell=True, no user-provided paths/COM ports, no activation flag.
        proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", bufsize=1)
        with lock:
            job["pid"] = proc.pid
        assert proc.stdout is not None
        with proc.stdout:
            for line in proc.stdout:
                _add_line(line)
        result = proc.wait()
        with lock:
            job["returncode"] = result
            job["state"] = "passed" if result == 0 else "failed"
            job["message"] = ("Firmware in inaktivem Slot geprüft; Bootauswahl unverändert."
                              if result == 0 else "OTA-Test fehlgeschlagen. Gerät und Log kontrollieren.")
    except Exception as exc:
        _add_line(f"LOCAL ERROR: {exc}")
        with lock:
            job["state"] = "failed"
            job["message"] = "OTA-Skript konnte nicht ausgeführt werden."
    finally:
        with lock:
            job["ended"] = _now()
            job["pid"] = None


def _local_only():
    # This application must be bound to loopback for command functionality.
    # Reject non-loopback requests even if the server is launched incorrectly.
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)


@bp.get("/ota")
def ota_page():
    _local_only()
    return render_template("ota.html", releases=RELEASES, csrf_token=csrf_token)


@bp.get("/api/ota/releases")
def ota_releases():
    _local_only()
    items = []
    for version, release in RELEASES.items():
        info = {"version": version, "target": release["node"],
                "from_version": release["from_version"], "from_slot": release["from_slot"],
                "to_slot": release["to_slot"]}
        try:
            p = _plan(version)
            info.update({"ready": True, "bytes": p["size"], "sha256": p["sha256"],
                         "blocks": p["blocks"]})
        except (OSError, ValueError, ImportError, TypeError, KeyError) as exc:
            info.update({"ready": False, "error": str(exc)})
        items.append(info)
    return jsonify({"releases": items, "gateway_port": GATEWAY_PORT,
                    "target_port": TARGET_PORT,
                    "notice": "Firmwareversionen sind statisch konfiguriert; keine Live-Geräteerkennung."})


@bp.get("/api/ota/job")
def ota_job():
    _local_only()
    with lock:
        return jsonify(dict(job))


@bp.post("/api/ota/start")
def ota_start():
    _local_only()
    if request.headers.get("X-OTA-CSRF") != csrf_token:
        return jsonify({"error": "Ungültiger CSRF-Schutz."}), 403
    data = request.get_json(silent=True) or {}
    version = data.get("version")
    if version not in RELEASES:
        return jsonify({"error": "Unbekanntes Release."}), 400
    try:
        plan = _plan(version)
    except (OSError, ValueError, ImportError, TypeError, KeyError) as exc:
        return jsonify({"error": "Signaturprüfung fehlgeschlagen: " + str(exc)}), 400
    with lock:
        if job["state"] == "running":
            return jsonify({"error": "Bereits ein OTA-Job aktiv."}), 409
        job.update({"id": secrets.token_hex(6), "state": "running",
                    "started": _now(), "ended": None, "version": version, "pid": None,
                    "returncode": None, "lines": [],
                    "message": f"Signiertes Release {version} geprüft ({plan['size']} Byte). Starte OTA-Staging."})
    threading.Thread(target=_run, args=(version,), daemon=True).start()
    return jsonify({"accepted": True, "id": job["id"]}), 202
