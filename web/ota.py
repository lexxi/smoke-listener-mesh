"""Local OTA coordinator for verified uploaded releases.

Only 1OG v0.6.9 -> v0.6.10 (app0 -> app1) is enabled for staging.
Requires the gateway on COM12 and target physically connected on COM15.
Does NOT activate, reboot or confirm firmware.
"""
from __future__ import annotations

import datetime as dt
import os
import secrets
import subprocess
import sys
import threading
from pathlib import Path
from flask import Blueprint, abort, jsonify, render_template, request
from release_library import STORE, PUBLIC_KEY, _identity, _verify, list_releases, GUARD

ROOT = Path(__file__).resolve().parents[1]
OTA = ROOT / "tools" / "ota"
GATEWAY_PORT = os.environ.get("SMOKE_OTA_GATEWAY_PORT", "COM12").upper()
TARGET_PORT = os.environ.get("SMOKE_OTA_TARGET_PORT", "COM15").upper()
ALLOWED_TARGET = "000010637C6E27AC"   # 1OG; verified on hardware in earlier tests
ALLOWED_UPGRADE = ("0.6.9", "0.6.10")

bp = Blueprint("ota", __name__)
lock = threading.RLock()
csrf_token = secrets.token_urlsafe(32)
MAX_LINES = 300
job = {"id": None, "state": "idle", "started": None, "ended": None,
       "release_id": None, "pid": None, "returncode": None, "lines": [],
       "message": "Noch kein OTA-Lauf ausgeführt."}


def _now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _local():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)


def _release(release_id: str):
    if not isinstance(release_id, str) or not release_id or "/" in release_id or "\\" in release_id:
        raise ValueError("Ungültige Release-ID")
    folder = STORE / release_id
    if not folder.is_dir():
        raise ValueError("Release nicht gefunden")
    image, manifest = folder / "firmware.bin", folder / "manifest.json"
    plan = _verify(image, manifest)
    if _identity(plan) != release_id:
        raise ValueError("Release-ID entspricht nicht dem signierten Inhalt")
    return image, manifest, plan


def _supported(plan: dict) -> bool:
    return plan["target"] == ALLOWED_TARGET and plan["version"] == ALLOWED_UPGRADE[1]


def _append(line: str):
    with lock:
        job["lines"].append(line.rstrip()[:700])
        if len(job["lines"]) > MAX_LINES:
            del job["lines"][:-MAX_LINES]


def _run(release_id: str):
    try:
        with GUARD:
            image, manifest, plan = _release(release_id)
            if not _supported(plan):
                raise ValueError("Knoten/Versionspaar nicht für OTA-Staging freigegeben")
        command = [
            sys.executable, "-u", str(OTA / "ota_test.py"),
            "--gateway", GATEWAY_PORT, "--target-port", TARGET_PORT,
            "--from-version", ALLOWED_UPGRADE[0],
            "--to-version", ALLOWED_UPGRADE[1],
            "--image", str(image), "--manifest", str(manifest),
            "--public-key", str(PUBLIC_KEY),
        ]
        # stdin=DEVNULL prohibits any interactive activation. No --activate flag.
        proc = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", bufsize=1)
        with lock:
            job["pid"] = proc.pid
        assert proc.stdout is not None
        with proc.stdout:
            for line in proc.stdout:
                _append(line)
        code = proc.wait()
        with lock:
            job["returncode"] = code
            job["state"] = "passed" if code == 0 else "failed"
            job["message"] = ("Staging und SHA-256-Readback erfolgreich. Boot unverändert."
                              if code == 0 else "Staging fehlgeschlagen. Log prüfen; Boot nicht umstellen.")
    except Exception as exc:
        _append("LOCAL ERROR: " + str(exc))
        with lock:
            job["state"] = "failed"
            job["message"] = "OTA-Lauf konnte nicht erfolgreich abgeschlossen werden."
    finally:
        with lock:
            job["pid"] = None
            job["ended"] = _now()


@bp.get("/ota")
def page():
    _local()
    return render_template("ota.html", csrf_token=csrf_token)


@bp.get("/api/ota/releases")
def available():
    _local()
    with GUARD:
        entries = list_releases()
    for entry in entries:
        entry["transfer_enabled"] = (
            entry["target"] == ALLOWED_TARGET and entry["version"] == ALLOWED_UPGRADE[1]
        )
        entry["transfer_note"] = (
            "1OG: v0.6.9 (app0) → v0.6.10 (app1), Staging ohne Bootwechsel"
            if entry["transfer_enabled"] else "Nur gespeichert – für dieses Gerät/Versionspaar kein Staging freigegeben"
        )
    return jsonify({"releases": entries, "gateway_port": GATEWAY_PORT,
                    "target_port": TARGET_PORT, "allowed_target": ALLOWED_TARGET,
                    "required_current_version": ALLOWED_UPGRADE[0]})


@bp.get("/api/ota/job")
def job_status():
    _local()
    with lock:
        return jsonify(dict(job))


@bp.post("/api/ota/start")
def start():
    _local()
    if request.headers.get("X-OTA-CSRF") != csrf_token:
        return jsonify({"error": "Ungültiges CSRF-Token"}), 403
    data = request.get_json(silent=True) or {}
    release_id = data.get("release_id")
    if GATEWAY_PORT == TARGET_PORT:
        return jsonify({"error": "Gateway und Target dürfen nicht denselben COM-Port verwenden"}), 400
    try:
        with GUARD:
            _, _, plan = _release(release_id)
            if not _supported(plan):
                return jsonify({"error": "Staging nur für signiertes 1OG v0.6.10 aus v0.6.9 freigegeben"}), 400
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        return jsonify({"error": "Release-Prüfung fehlgeschlagen: " + str(exc)}), 400
    with lock:
        if job["state"] == "running":
            return jsonify({"error": "Ein OTA-Lauf ist bereits aktiv"}), 409
        job.update({"id": secrets.token_hex(6), "state": "running",
                    "started": _now(), "ended": None, "release_id": release_id,
                    "pid": None, "returncode": None, "lines": [],
                    "message": "1OG v0.6.9 → v0.6.10: signiertes Staging gestartet; keine Bootaktivierung."})
    threading.Thread(target=_run, args=(release_id,), daemon=True).start()
    return jsonify({"accepted": True, "id": job["id"]}), 202
