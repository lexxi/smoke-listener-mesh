"""Control the existing Garage serial logger on COM14 from the local dashboard.

Does not open COM14 until explicitly started. Never kills unrelated processes.
"""
from __future__ import annotations
import atexit
import datetime as dt
import secrets
import subprocess
import sys
import threading
from pathlib import Path
from flask import Blueprint, abort, jsonify, request

ROOT = Path(__file__).resolve().parents[1]
LOGGER = ROOT / "scripts" / "logging.py"
PORT = "COM14"
bp = Blueprint("logger_control", __name__)
guard = threading.RLock()
token = secrets.token_urlsafe(32)
process = None
output_handle = None
session = None
note = "Logger nicht über die Webapp gestartet."


def local():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)


def running():
    return process is not None and process.poll() is None


def status_data():
    return {"port": PORT, "running": running(),
            "pid": process.pid if running() else None,
            "session": str(session.relative_to(ROOT)) if session else None,
            "note": note, "token": token, "ota_reserved": ota_reserved}


# Reservation prevents the dashboard from reopening COM14 during remote OTA.
ota_reserved = False


def _stop_owned_locked():
    global output_handle, note
    if running():
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if output_handle is not None:
        output_handle.close()
        output_handle = None


def _start_owned_locked():
    global process, output_handle, session, note
    output = ROOT / "log"
    output.mkdir(parents=True, exist_ok=True)
    session = output / ("mesh_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
    diagnostics = output / ("logger_control_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
    output_handle = diagnostics.open("a", encoding="utf-8", buffering=1)
    try:
        process = subprocess.Popen(
            [sys.executable, "-u", str(LOGGER), "--port", PORT, "--out", str(session)],
            cwd=ROOT, stdin=subprocess.DEVNULL,
            stdout=output_handle, stderr=subprocess.STDOUT,
        )
    except Exception:
        output_handle.close()
        output_handle = None
        process = None
        raise
    note = "Garage-Logger läuft auf COM14."


def pause_for_remote_ota():
    """Reserve COM14, and pause only the logger owned by this Flask process."""
    global ota_reserved, note
    with guard:
        if ota_reserved:
            raise RuntimeError("COM14 is already reserved for OTA")
        ota_reserved = True
        was_running = running()
        try:
            if was_running:
                _stop_owned_locked()
            note = "COM14 für Remote-OTA freigegeben; Web-Logger pausiert."
            return was_running
        except Exception:
            ota_reserved = False
            raise


def resume_after_remote_ota(was_running):
    """Release reservation, restoring the logger if it was running beforehand."""
    global ota_reserved, note
    with guard:
        try:
            if was_running:
                _start_owned_locked()
            else:
                note = "COM14 nach OTA wieder freigegeben."
        finally:
            ota_reserved = False


@bp.get("/api/logger/status")
def status():
    local()
    with guard:
        return jsonify(status_data())


@bp.post("/api/logger/start")
def start():
    global process, output_handle, session, note
    local()
    if request.headers.get("X-Logger-CSRF") != token:
        abort(403)
    with guard:
        if ota_reserved:
            return jsonify({"error": "COM14 ist für OTA reserviert."}), 409
        if running():
            return jsonify(status_data())
        try:
            _start_owned_locked()
        except (OSError, ValueError) as exc:
            return jsonify({"error": "Logger konnte nicht gestartet werden: " + str(exc)}), 500
        return jsonify(status_data()), 202


@bp.post("/api/logger/stop")
def stop():
    global note, output_handle
    local()
    if request.headers.get("X-Logger-CSRF") != token:
        abort(403)
    with guard:
        if ota_reserved:
            return jsonify({"error": "COM14 ist für OTA reserviert."}), 409
        if running():
            _stop_owned_locked()
            note = "Web-Logger beendet. Externe PowerShell-Logger unverändert."
        else:
            note = "Kein über die Webapp laufender Logger."
        return jsonify(status_data())


def shutdown():
    global process
    with guard:
        if running():
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if output_handle is not None:
            output_handle.close()


atexit.register(shutdown)
