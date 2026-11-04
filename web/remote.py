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

from flask import Blueprint, abort, jsonify, request, send_file, Response

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
    "progress": 0, "lines": [], "log_file": None, "log_line_count": 0, "message": "Noch kein Remote-OTA-Lauf.",
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
    # Legacy signed firmware is still accepted. New feature-capable builds
    # must carry an additional publisher-signed claim, never a guessed role.
    if tuple(map(int, plan["version"].split("."))) >= (0, 6, 15) and plan.get("features") is None:
        raise ValueError("v0.6.15+ benötigt signierte Feature-Metadaten für Remote-OTA")
    return image, manifest, plan


def _log(line):
    with lock:
        shortened = line.rstrip()[:900]
        job["log_line_count"] = job.get("log_line_count", 0) + 1
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
        elif mode == "activate_staged":
            args.append("--activate-staged")
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
            if code == 0 and mode in ("deploy", "activate_staged"):
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


def _saved_log():
    """Only server-generated logs; fall back to newest completed job after restart."""
    base = ROOT / "web" / "data" / "ota_jobs"
    with lock:
        current = job.get("log_file")
    if current:
        path = ROOT / current
        if path.is_file() and path.parent.resolve() == base.resolve():
            return path
    if base.is_dir():
        candidates = (item for item in base.glob("*.log") if item.is_file())
        return max(candidates, key=lambda item: item.stat().st_mtime, default=None)
    return None


@bp.get("/api/remote/log")
def full_log():
    _local()
    path = _saved_log()
    if path is None:
        return jsonify({"error": "Noch kein gespeichertes OTA-Protokoll vorhanden."}), 404
    # No paths from the client. Stream rather than embed in JSON responses.
    return send_file(path, mimetype="text/plain; charset=utf-8",
                     as_attachment=False, max_age=0)


@bp.get("/api/remote/log/download")
def download_log():
    _local()
    path = _saved_log()
    if path is None:
        return jsonify({"error": "Noch kein gespeichertes OTA-Protokoll vorhanden."}), 404
    return send_file(path, mimetype="text/plain; charset=utf-8",
                     as_attachment=True, download_name="smoke-mesh-ota-"+path.stem+".txt",
                     max_age=0)


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
    if port not in TRUSTED_GATEWAYS or mode not in ("status", "stage", "deploy", "activate_staged"):
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
            "gateway": port, "progress": 0, "lines": [], "log_line_count": 0,
            "log_file": "web/data/ota_jobs/" + secrets.token_hex(8) + ".log",
            "message": "Remote-" + mode + " läuft über Gateway " + port,
        })
    threading.Thread(target=_run, args=(release_id, port, mode), daemon=True).start()
    return jsonify({"accepted": True, "job_id": job["id"]}), 202


@bp.post("/api/remote/node-action")
def node_action():
    _local()
    if request.headers.get("X-Remote-CSRF") != csrf:
        return jsonify({"error": "CSRF-Prüfung fehlgeschlagen"}), 403
    data = request.get_json(silent=True) or {}
    target, port, action, name = (data.get("target"), data.get("gateway"),
                                  data.get("action"), data.get("name", ""))
    if not isinstance(target, str) or not re.fullmatch(r"[0-9A-F]{16}", target):
        return jsonify({"error": "Ungültige Knoten-ID"}), 400
    if port not in TRUSTED_GATEWAYS or target == TRUSTED_GATEWAYS[port][1]:
        return jsonify({"error": "Ungültiges Gateway oder Gateway=Ziel"}), 400
    if action not in ("STATUS", "NAME_GET", "NAME_SET", "NAME_RESET", "RESTART"):
        return jsonify({"error": "Unzulässiger Managementbefehl"}), 400
    if action == "NAME_SET":
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,19}", name):
            return jsonify({"error": "Name: 1–19 Zeichen A-Z a-z 0-9 - _"}), 400
    elif name:
        return jsonify({"error": "Unzulässiger Namensparameter"}), 400
    with lock:
        if job["state"] == "running":
            return jsonify({"error": "Ein OTA- oder Managementvorgang läuft bereits"}), 409
        job.update({
            "id": secrets.token_hex(8), "state": "running", "mode": "node_" + action,
            "started": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            "ended": None, "release_id": None, "target": target,
            "gateway": port, "progress": 0, "lines": [], "log_line_count": 0,
            "log_file": "web/data/ota_jobs/" + secrets.token_hex(8) + ".log",
            "message": "Knotenverwaltung: " + action + " über " + port,
        })
    threading.Thread(target=_run_node_action, args=(target, port, action, name), daemon=True).start()
    return jsonify({"accepted": True, "job_id": job["id"]}), 202


def _run_node_action(target, port, action, name):
    global process
    paused = False
    try:
        if port == "COM14":
            paused = pause_for_remote_ota()
            _log("[WEB] Garage-Logger für Knotenverwaltung pausiert.")
            time.sleep(0.7)
        args = [sys.executable, "-u", str(SCRIPT), "--gateway", port,
                "--manage-target", target, "--manage-action", action]
        if action == "NAME_SET":
            args += ["--manage-name", name]
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
            job["message"] = ("Befehl abgeschlossen: " + action if code == 0 else
                              "Befehl fehlgeschlagen; Protokoll prüfen.")
            if code == 0:
                job["progress"] = 100
    except Exception as exc:
        _log("[WEB] ERROR: " + str(exc))
        with lock:
            job["state"] = "failed"
            job["message"] = "Knotenverwaltung fehlgeschlagen."
    finally:
        if port == "COM14":
            try:
                resume_after_remote_ota(paused)
                _log("[WEB] Garage-Logger wieder freigegeben.")
            except Exception as exc:
                _log("[WEB] WARN: Logger-Neustart fehlgeschlagen: " + str(exc))
        with lock:
            process = None
            job["ended"] = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")


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
