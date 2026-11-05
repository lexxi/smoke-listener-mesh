"""Control the configured USB gateway logger from the local dashboard.

Starts the configured logger when the Web server starts. Never kills unrelated processes.
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
from gateway_config import LOGGER_PORT, LOGGER_NAME

ROOT = Path(__file__).resolve().parents[1]
LOGGER = ROOT / "scripts" / "logging.py"
PORT = LOGGER_PORT
bp = Blueprint("logger_control", __name__)
guard = threading.RLock()
token = secrets.token_urlsafe(32)
process = None
output_handle = None
session = None
note = "Logger noch nicht gestartet."


def local():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)


def running():
    return process is not None and process.poll() is None



def connection_state():
    """Read the logger's latest serial connect/disconnect event.

    A live Python PID is not proof of an open serial connection.
    """
    if not running() or session is None:
        return "stopped"
    try:
        with session.open("rb") as stream:
            stream.seek(0, 2)
            length = stream.tell()
            stream.seek(max(0, length - 65536))
            lines = stream.read().decode("utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            if "[LOGGER] Disconnected:" in line:
                return "disconnected"
            if "[LOGGER] Connected to " in line:
                return "connected"
    except OSError:
        pass
    return "connecting"


def status_data():
    is_running = running()
    serial_state = connection_state() if is_running else "stopped"
    current_note = note
    if serial_state == "connecting":
        current_note = f"{PORT}: Logger gestartet, wartet auf serielle Verbindung."
    elif serial_state == "disconnected":
        current_note = f"{PORT}: keine serielle Verbindung; Logger versucht erneut zu verbinden."
    if not is_running and process is not None:
        current_note = f"Logger beendet (Exit-Code {process.returncode}). COM-Port/Diagnoselog prüfen."
    return {"port": PORT, "name": LOGGER_NAME, "running": is_running,
            "pid": process.pid if is_running and process is not None else None,
            "connected": serial_state == "connected", "connection_state": serial_state,
            "session": str(session.relative_to(ROOT)) if session else None,
            "note": current_note, "token": token, "ota_reserved": ota_reserved}


# Reservation prevents the dashboard from reopening {PORT} during remote OTA.
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
    session = output / ("mesh_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".log")
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
    note = f"{LOGGER_NAME}-Logger läuft auf {PORT}."


def autostart():
    """Start our own logger once, only from the actual Web server entrypoint.

    A COM port owned by another process is never seized. In that case our
    logger process exits, and the status endpoint reports the failure.
    """
    global note
    with guard:
        if ota_reserved or running():
            return status_data()
        try:
            _start_owned_locked()
            note = f"{LOGGER_NAME}-Logger automatisch auf {PORT} gestartet."
        except (OSError, ValueError) as exc:
            note = f"Logger-Autostart fehlgeschlagen: {exc}"
        return status_data()


def pause_for_remote_ota():
    """Reserve {PORT}, and pause only the logger owned by this Flask process."""
    global ota_reserved, note
    with guard:
        if ota_reserved:
            raise RuntimeError(f"{PORT} is already reserved for OTA")
        ota_reserved = True
        was_running = running()
        try:
            if was_running:
                _stop_owned_locked()
            note = f"{PORT} für Remote-OTA freigegeben; Web-Logger pausiert."
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
                note = f"{PORT} nach OTA wieder freigegeben."
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
            return jsonify({"error": f"{PORT} ist für OTA reserviert."}), 409
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
            return jsonify({"error": f"{PORT} ist für OTA reserviert."}), 409
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
