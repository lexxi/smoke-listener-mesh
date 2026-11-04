"""Browser-only remote OTA orchestration via a trusted USB-connected ESP-NOW gateway.

No target USB. Only previously verified and locally stored releases.
A single job per process; Garage COM14 logger is paused/restored automatically.
"""
from __future__ import annotations

import atexit
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Blueprint, abort, jsonify, request

from release_library import STORE, PUBLIC_KEY, GUARD, _identity, _verify
from logger_control import pause_for_remote_ota, resume_after_remote_ota

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "ota" / "remote_ota.py"
TRUSTED_GATEWAYS = {"COM14": ("Garage", "000058FE7D6E27AC"),
                    "COM12": ("Kueche", "000094457F6E27AC")}
bp = Blueprint("remote_ota", __name__)
csrf = secrets.token_urlsafe(32)
lock = threading.RLock()
process = None
job = {
    "id": None, "state": "idle", "mode": None, "started": None, "ended": None,
    "release_id": None, "target": None, "gateway": None,
    "progress": 0, "lines": [], "log_file": None, "message": "Noch kein Remote-OTA-Lauf.",
}
MAX_LINES = 450


def _local():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)


def _verify_release(release_id):
    if not isinstance(release_id, str) or not re.fullmatch(
        r"[0-9A-F]{16}_[0-9.]+_[a-f0-9]{16}", release_id
    ):
        raise ValueError("Unzulässige Release-ID")
    folder = STORE / release_id
    if not folder.is_dir():
        raise ValueError("Release wurde nicht gefunden")
    image, manifest = folder / "firmware.bin", folder / "manifest.json"
    plan = _verify(image, manifest)
    if _identity(plan) != release_id:
        raise ValueError("Signiertes Release entspricht nicht der Release-ID")
    return image, manifest, plan


def _log(line):
    with lock:
        shortened = line.rstrip()[:900]
        job["lines"].append(shortened)
        if job.get("log_file"):
            destination = ROOT / job["log_file"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("a", encoding="utf-8") as out:
                out.write(shortened + "\n")
        if len(job["lines"]) > MAX_LINES:
            del job["lines"][:-MAX_LINES]
        m = re.search(r"\[IMAGE\] NEXT index=(\d+)/(\d+)", line)
        if m and int(m.group(2)):
            job["progress"] = min(99, int(100 * int(m.group(1)) / int(m.group(2))))


def _run(release_id, port, mode):
    global process
    paused = False
    try:
        with GUARD:
            image, manifest, plan = _verify_release(release_id)
            if plan["target"] == TRUSTED_GATEWAYS[port][1]:
                raise ValueError("Ein Knoten kann nicht über sich selbst als USB-Gateway aktualisiert werden")
        if port == "COM14":
            paused = pause_for_remote_ota()
            _log("[WEB] Garage-Logger pausiert, COM14 exklusiv für Remote-OTA.")
            time.sleep(0.7)
        args = [
            sys.executable, "-u", str(SCRIPT), "--gateway", port,
            "--image", str(image), "--manifest", str(manifest),
            "--public-key", str(PUBLIC_KEY),
        ]
        if mode == "deploy":
            args.append("--deploy")
        elif mode == "status":
            args.append("--status-only")
        proc = subprocess.Popen(
            args, cwd=ROOT, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace", text=True, bufsize=1,
        )
        with lock:
            process = proc
        assert proc.stdout is not None
        with proc.stdout:
            for line in proc.stdout:
                _log(line)
        code = proc.wait()
        with lock:
            job["state"] = "passed" if code == 0 else "failed"
            if code == 0 and mode == "deploy":
                job["progress"] = 100
                job["message"] = "Update bestätigt: Ziel meldet neue Firmware als VALID."
            elif code == 0 and mode == "stage":
                job["progress"] = 100
                job["message"] = "Signierte Firmware im inaktiven Slot geprüft. Boot unverändert."
            elif code == 0:
                job["message"] = "Remote-Knoten erfolgreich abgefragt."
            else:
                job["message"] = "Vorgang nicht erfolgreich. Log und Zustand vor neuem Versuch prüfen."
    except Exception as exc:
        _log(f"[WEB] ERROR: {exc}")
        with lock:
            job["state"] = "failed"
            job["message"] = "OTA-Vorgang abgebrochen oder fehlgeschlagen."
    finally:
        if port == "COM14":
            try:
                resume_after_remote_ota(paused)
                _log("[WEB] COM14 freigegeben; Garage-Logger bei Bedarf neu gestartet.")
            except Exception as exc:
                _log(f"[WEB] WARN: Garage-Logger Neustart fehlgeschlagen: {exc}")
        with lock:
            process = None
            job["ended"] = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")


@bp.get("/api/remote/config")
def config():
    _local()
    return jsonify({
        "gateways": [{"port": port, "name": info[0], "node": info[1]}
                     for port, info in TRUSTED_GATEWAYS.items()],
        "csrf": csrf,
        "notice": "v0.6.11+ auf Gateway und Ziel erforderlich. Fern-OTA ist bis zum Hardwaretest experimentell.",
    })


@bp.get("/api/remote/job")
def current_job():
    _local()
    with lock:
        return jsonify(dict(job))


@bp.post("/api/remote/start")
def start():
    _local()
    if request.headers.get("X-Remote-CSRF") != csrf:
        return jsonify({"error": "CSRF-Prüfung fehlgeschlagen"}), 403
    data = request.get_json(silent=True) or {}
    release_id, port, mode = data.get("release_id"), data.get("gateway"), data.get("mode")
    if port not in TRUSTED_GATEWAYS or mode not in ("status", "stage", "deploy"):
        return jsonify({"error": "Unzulässiges Gateway oder Betriebsmodus"}), 400
    try:
        with GUARD:
            _, _, plan = _verify_release(release_id)
            if plan["target"] == TRUSTED_GATEWAYS[port][1]:
                raise ValueError("Gateway und Zielknoten müssen unterschiedliche C3 sein")
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        return jsonify({"error": "Release-Prüfung: " + str(exc)}), 400
    with lock:
        if job["state"] == "running":
            return jsonify({"error": "Es läuft bereits ein OTA-/Statusvorgang"}), 409
        job.update({
            "id": secrets.token_hex(8), "state": "running", "mode": mode,
            "started": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            "ended": None, "release_id": release_id, "target": plan["target"],
            "gateway": port, "progress": 0, "lines": [],
            "log_file": "web/data/ota_jobs/" + secrets.token_hex(8) + ".log",
            "message": "Remote-" + mode + " läuft über Gateway " + port,
        })
    threading.Thread(target=_run, args=(release_id, port, mode), daemon=True).start()
    return jsonify({"accepted": True, "job_id": job["id"]}), 202


@atexit.register
def shutdown():
    global process
    with lock:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=4)
