"""Local signed firmware release library: upload, verify and store. Never flashes nodes."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import zipfile
import shutil
import threading
from pathlib import Path
from flask import Blueprint, abort, jsonify, request
from node_role_policy import load_targets

ROOT = Path(__file__).resolve().parents[1]
OTA_TOOLS = ROOT / "tools" / "ota"
STORE = ROOT / "web" / "data" / "releases"
PUBLIC_KEY = Path(os.environ.get("SMOKE_OTA_PUBLIC_KEY", r"C:\mesh-ota-keys\signing-public.pem"))
MAX_BIN = 1310720
MAX_MANIFEST = 8192
GUARD = threading.RLock()
CSRF = secrets.token_urlsafe(32)
bp = Blueprint("release_library", __name__)


def _local():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)


def _manifest(path: Path) -> dict:
    payload = json.loads(path.read_text("utf-8"))
    return payload["signed"]


def _verify(image: Path, manifest: Path) -> dict:
    # Exactly the same signed manifest verification as the established OTA tool.
    sys.path.insert(0, str(OTA_TOOLS))
    try:
        from prepare_transfer import build_plan
        plan = build_plan(image, manifest, PUBLIC_KEY)
    finally:
        sys.path.remove(str(OTA_TOOLS))
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}(?:\.[a-h])?", plan["version"]):
        raise ValueError("Nur numerische Versionen X.Y.Z werden akzeptiert.")
    if not re.fullmatch(r"[0-9A-F]{16}", plan["target"]):
        raise ValueError("Ungültige Knoten-ID")
    return plan


def _identity(plan: dict) -> str:
    # Immutable content-addressed directory; signed target and version included.
    return plan["target"] + "_" + plan["version"] + "_" + plan["sha256"][:16]


def _summary(plan: dict, release_id: str) -> dict:
    return {"id": release_id, "target": plan["target"],
            "version": plan["version"], "sha256": plan["sha256"],
            "features": plan.get("features"),
            "label": plan.get("label"),
            "bytes": plan["size"], "blocks": plan["blocks"],
            "status": "verified", "transfer_enabled": False}


def list_releases() -> list[dict]:
    found = []
    if not STORE.is_dir():
        return found
    for folder in sorted(STORE.iterdir()):
        if not folder.is_dir() or not re.fullmatch(r"[0-9A-F]{16}_[0-9.]+(?:[a-h])?_[a-f0-9]{16}", folder.name):
            continue
        image = folder / "firmware.bin"
        manifest = folder / "manifest.json"
        if not image.is_file() or not manifest.is_file():
            continue
        try:
            plan = _verify(image, manifest)
            if _identity(plan) == folder.name:
                found.append(_summary(plan, folder.name))
        except (OSError, ValueError, TypeError, KeyError, ImportError):
            # Corrupt or unverifiable stored items must not be offered as releases.
            continue
    return found


@bp.post("/api/releases/upload-bundle")
def upload_bundle():
    """Upload ONE ZIP with firmware.bin and 1-5 node-specific signed manifests."""
    _local()
    if request.headers.get("X-Release-CSRF") != CSRF:
        return jsonify({"error": "CSRF-Prüfung fehlgeschlagen."}), 403
    bundle = request.files.get("bundle")
    if bundle is None:
        return jsonify({"error": "ZIP-Datei fehlt."}), 400
    if request.content_length and request.content_length > 3_000_000:
        return jsonify({"error": "ZIP-Upload zu groß."}), 413
    if not PUBLIC_KEY.is_file():
        return jsonify({"error": "Öffentlicher Prüfschlüssel fehlt."}), 400

    try:
        permitted_targets = load_targets()
    except (ValueError, OSError, TypeError) as exc:
        return jsonify({"error": "OTA-Zielkonfiguration: " + str(exc)}), 400
    tmp_root = ROOT / "web" / "data" / "uploads_tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    with GUARD, tempfile.TemporaryDirectory(dir=tmp_root) as temporary:
        base = Path(temporary)
        archive = base / "bundle.zip"
        with archive.open("xb") as out:
            data = bundle.stream.read(3_000_001)
            if len(data) > 3_000_000:
                return jsonify({"error": "ZIP-Upload zu groß."}), 413
            out.write(data)
        plans = []
        try:
            with zipfile.ZipFile(archive) as zipped:
                members = zipped.infolist()
                names = [item.filename for item in members]
                if len(names) < 2 or len(names) > 6 or len(names) != len(set(names)):
                    raise ValueError("Erwartet: genau eine BIN und 1–5 Manifeste ohne Duplikate")
                if "firmware.bin" not in names or any(
                    name != "firmware.bin" and
                    not re.fullmatch(r"manifest_[0-9A-F]{16}\.json", name)
                    for name in names
                ):
                    raise ValueError("Unbekannter Archivpfad oder falscher Dateiname")
                if any(info.is_dir() or info.flag_bits & 1 for info in members):
                    raise ValueError("Verzeichnisse und verschlüsselte Dateien sind nicht zugelassen")
                if any((info.file_size > (MAX_BIN if info.filename == "firmware.bin" else MAX_MANIFEST))
                       for info in members):
                    raise ValueError("Firmware oder Manifest zu groß")
                image = base / "firmware.bin"
                image.write_bytes(zipped.read("firmware.bin"))
                for name in names:
                    if name == "firmware.bin":
                        continue
                    target = name[len("manifest_"):-len(".json")]
                    if target not in permitted_targets:
                        raise ValueError("Unbekannter Zielknoten: " + target)
                    manifest = base / name
                    manifest.write_bytes(zipped.read(name))
                    plan = _verify(image, manifest)
                    if plan["target"] != target:
                        raise ValueError("Manifestsignatur passt nicht zum Dateinamen")
                    plans.append((plan, manifest))
            if not plans:
                raise ValueError("Keine signierten Manifeste enthalten")
            if len({p["version"] for p, _ in plans}) != 1:
                raise ValueError("Das Paket enthält unterschiedliche Firmwareversionen")
            STORE.mkdir(parents=True, exist_ok=True)
            created = []
            stored = []
            try:
                for plan, manifest in plans:
                    identifier = _identity(plan)
                    folder = STORE / identifier
                    if folder.exists():
                        stored.append({**_summary(plan, identifier), "already_present": True})
                        continue
                    folder.mkdir(mode=0o700)
                    created.append(folder)
                    shutil.copyfile(image, folder / "firmware.bin")
                    shutil.copyfile(manifest, folder / "manifest.json")
                    stored.append({**_summary(plan, identifier), "already_present": False})
            except OSError:
                for folder in created:
                    shutil.rmtree(folder, ignore_errors=True)
                raise
            return jsonify({"stored": True, "releases": stored}), 201
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
            return jsonify({"error": "Release-ZIP nicht gültig: " + str(exc)}), 400


@bp.get("/api/releases")
def releases():
    _local()
    with GUARD:
        return jsonify({"releases": list_releases(), "public_key_present": PUBLIC_KEY.is_file(),
                        "upload_csrf": CSRF,
                        "notice": "Signaturgeprüfte Ablage. OTA für hochgeladene Releases noch nicht freigeschaltet."})


@bp.post("/api/releases/upload")
def upload():
    _local()
    if request.headers.get("X-Release-CSRF") != CSRF:
        return jsonify({"error": "CSRF-Prüfung fehlgeschlagen."}), 403
    image = request.files.get("image")
    manifest = request.files.get("manifest")
    if image is None or manifest is None:
        return jsonify({"error": "Firmware-BIN und signiertes Manifest müssen beide hochgeladen werden."}), 400
    if request.content_length is not None and request.content_length > MAX_BIN + MAX_MANIFEST + 32768:
        return jsonify({"error": "Upload überschreitet die zulässige Größe."}), 413
    if not PUBLIC_KEY.is_file():
        return jsonify({"error": "Öffentlicher Prüfschlüssel fehlt: " + str(PUBLIC_KEY)}), 400

    # Receive only into a temporary folder; never trust client-provided filenames.
    temp_dir = ROOT / "web" / "data" / "uploads_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    with GUARD, tempfile.TemporaryDirectory(dir=temp_dir) as tmp:
        image_path = Path(tmp) / "firmware.bin"
        manifest_path = Path(tmp) / "manifest.json"
        for incoming, destination, limit in (
            (image, image_path, MAX_BIN), (manifest, manifest_path, MAX_MANIFEST)
        ):
            with destination.open("xb") as out:
                count = 0
                while True:
                    chunk = incoming.stream.read(min(65536, limit + 1 - count))
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > limit:
                        return jsonify({"error": "Datei zu groß: " + destination.name}), 413
                    out.write(chunk)
                if incoming.stream.read(1):
                    return jsonify({"error": "Datei zu groß: " + destination.name}), 413
        try:
            plan = _verify(image_path, manifest_path)
        except (OSError, ValueError, TypeError, KeyError, ImportError, json.JSONDecodeError) as exc:
            return jsonify({"error": "Release nicht gültig: " + str(exc)}), 400
        release_id = _identity(plan)
        STORE.mkdir(parents=True, exist_ok=True)
        final = STORE / release_id
        if final.exists():
            return jsonify({"error": "Dieses Release ist bereits vorhanden.", "release": _summary(plan, release_id)}), 409
        final.mkdir(mode=0o700)
        try:
            image_path.replace(final / "firmware.bin")
            manifest_path.replace(final / "manifest.json")
        except OSError:
            # Partial directories must not be considered verified on listing.
            import shutil
            shutil.rmtree(final, ignore_errors=True)
            raise
        return jsonify({"stored": True, "release": _summary(plan, release_id)}), 201
