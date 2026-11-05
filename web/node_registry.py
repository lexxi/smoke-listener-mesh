"""Local-only node inventory and OTA enrollment from the Web UI.

Discover is read-only; registering a node is an explicit authorized operation.
Changes are persisted in the existing CSV and private OTA allowlist.
"""
from __future__ import annotations

import csv
import json
import os
import re
import secrets
import tempfile
import threading
from pathlib import Path

from flask import Blueprint, abort, jsonify, request
from node_role_policy import TARGETS_FILE, load_targets
from gateway_config import LOGGER_PORT, TRUSTED_GATEWAYS

ROOT = Path(__file__).resolve().parents[1]
NODES_FILE = ROOT / "config" / "nodes.csv"
bp = Blueprint("node_registry", __name__)
csrf = secrets.token_urlsafe(32)
guard = threading.RLock()
MAX_TARGETS = 5
ID_RE = re.compile(r"0000[0-9A-F]{12}$")
NAME_RE = re.compile(r"[A-Za-z0-9_-]{1,19}$")


def _local():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)


def _authorize():
    _local()
    if request.headers.get("X-Registry-CSRF") != csrf:
        abort(403)


def _mac(node_id: str) -> str:
    return ":".join(reversed([node_id[i:i+2] for i in range(4, 16, 2)]))


def _inventory() -> dict[str, dict]:
    result = {}
    if NODES_FILE.exists():
        with NODES_FILE.open(encoding="utf-8-sig", newline="") as handle:
            for entry in csv.DictReader(handle):
                mac = (entry.get("mac") or "").strip().upper()
                if re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", mac):
                    result[mac] = {
                        "mac": mac,
                        "name": (entry.get("name") or "").strip(),
                        "location": (entry.get("location") or "").strip(),
                    }
    return result


def _write_atomic(path: Path, payload: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _save_inventory(entries: dict):
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["mac", "name", "location"], lineterminator="\n")
    writer.writeheader()
    for mac in sorted(entries):
        writer.writerow(entries[mac])
    _write_atomic(NODES_FILE, stream.getvalue())


def _save_targets(targets: set[str]):
    _write_atomic(TARGETS_FILE, json.dumps(sorted(targets), indent=2) + "\n")


@bp.get("/api/nodes/registry")
def registry():
    _local()
    with guard:
        targets = load_targets()
        return jsonify({
            "entries": list(_inventory().values()),
            "ota_targets": sorted(targets),
            "gateway_nodes": [TRUSTED_GATEWAYS[LOGGER_PORT][1]],
            "max_ota_targets": MAX_TARGETS,
            "csrf": csrf,
        })


@bp.post("/api/nodes/registry")
def save_node():
    _authorize()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON-Objekt erwartet"}), 400
    node_id = data.get("node_id")
    name = data.get("name")
    location = data.get("location")
    ota = data.get("ota")
    if not isinstance(node_id, str) or not ID_RE.fullmatch(node_id) or int(node_id, 16) == 0:
        return jsonify({"error": "Ungueltige Node-ID"}), 400
    if not isinstance(name, str) or (name and not NAME_RE.fullmatch(name)):
        return jsonify({"error": "Name: maximal 19 Zeichen (A-Z, 0-9, - oder _)"}), 400
    if not isinstance(location, str) or len(location) > 80 or any(c in location for c in "\r\n\0"):
        return jsonify({"error": "Standort: maximal 80 Zeichen, ohne Zeilenumbruch"}), 400
    if not isinstance(ota, bool):
        return jsonify({"error": "OTA-Freigabe muss true/false sein"}), 400
    if ota and node_id == TRUSTED_GATEWAYS[LOGGER_PORT][1]:
        return jsonify({"error": "Dedizierter USB-Logger-Gateway darf kein OTA-Ziel sein"}), 400
    with guard:
        try:
            entries = _inventory()
            targets = load_targets()
            if ota:
                targets.add(node_id)
            else:
                targets.discard(node_id)
            if len(targets) > MAX_TARGETS:
                return jsonify({"error": f"Maximal {MAX_TARGETS} OTA-Zielknoten; zuerst einen anderen abmelden"}), 409
            mac = _mac(node_id)
            entries[mac] = {"mac": mac, "name": name, "location": location}
            # Validate both targets and data before modifying either file.
            _save_inventory(entries)
            _save_targets(targets)
        except (OSError, ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 500
    return jsonify({"ok": True, "node_id": node_id, "mac": mac, "ota": ota,
                    "note": "OTA-Freigabe wirkt sofort, aber bestehende signierte ZIPs erhalten dadurch kein neues Manifest."})
