"""Single source of truth for trusted USB gateways and the dashboard logger.

Optional gateways are managed in web/data/managed_gateways.json; restart applies changes.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

CONFIG_FILE = Path(os.environ.get("SMOKE_GATEWAYS_FILE", str(Path(__file__).with_name("gateways.json"))))
MANAGED_FILE = Path(os.environ.get("SMOKE_MANAGED_GATEWAYS_FILE", str(Path(__file__).with_name("data") / "managed_gateways.json")))

def normalize_gateway_port(port: str) -> str:
    """Allow existing Windows COM ports and local Linux serial devices only."""
    if not isinstance(port, str):
        raise ValueError("Gateway-Port muss eine Zeichenkette sein")
    if re.fullmatch(r"COM[1-9][0-9]*", port, re.I):
        return port.upper()
    if (re.fullmatch(r"/dev/serial/by-id/[A-Za-z0-9_.:+@-]+", port) or
            re.fullmatch(r"/dev/tty(?:ACM|USB)[0-9]+", port)):
        return port
    raise ValueError("Ungueltiger Gateway-Port (COMx oder /dev/serial/by-id/...)")


def load_gateway_config(path: Path = CONFIG_FILE):
    effective_path = MANAGED_FILE if path == CONFIG_FILE and MANAGED_FILE.exists() else path
    payload = json.loads(effective_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("gateways"), dict):
        raise ValueError("gateways.json: 'gateways' muss ein Objekt sein")
    gateways = {}
    nodes = set()
    for port, entry in payload["gateways"].items():
        port = normalize_gateway_port(port)
        if not isinstance(entry, dict):
            raise ValueError("gateways.json: Gateway-Eintrag muss ein Objekt sein")
        name, node = entry.get("name"), entry.get("node")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("gateways.json: Gateway-Name fehlt")
        if not isinstance(node, str) or not re.fullmatch(r"[0-9A-F]{16}", node) or int(node, 16) == 0:
            raise ValueError("gateways.json: ungueltige Knoten-ID")
        if port in gateways or node in nodes:
            raise ValueError("gateways.json: COM-Port oder Knoten-ID doppelt")
        gateways[port] = (name.strip(), node)
        nodes.add(node)
    logger_port = payload.get("logger_gateway")
    logger_port = normalize_gateway_port(logger_port)
    if logger_port not in gateways:
        raise ValueError("gateways.json: logger_gateway muss ein registrierter Gateway-Port sein")
    return logger_port, gateways


LOGGER_PORT, TRUSTED_GATEWAYS = load_gateway_config()
LOGGER_NAME = TRUSTED_GATEWAYS[LOGGER_PORT][0]

def current_gateway_payload():
    """Return pending local settings, otherwise the tracked defaults."""
    path = MANAGED_FILE if MANAGED_FILE.exists() else CONFIG_FILE
    return json.loads(path.read_text(encoding="utf-8"))


def save_optional_gateways(gateways: list[dict]) -> None:
    """Keep dedicated logger gateway fixed; validate optional USB gateways."""
    if not isinstance(gateways, list) or len(gateways) > 12:
        raise ValueError("Maximal 12 zusaetzliche Gateways")
    current = current_gateway_payload()
    dedicated = current["logger_gateway"]
    dedicated_entry = current["gateways"][dedicated]
    entries = {dedicated: dedicated_entry}
    for item in gateways:
        if not isinstance(item, dict):
            raise ValueError("Gateway-Eintrag ungueltig")
        port = item.get("port")
        name = item.get("name")
        node = item.get("node")
        port = normalize_gateway_port(port)
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 40:
            raise ValueError("Gateway-Name muss 1 bis 40 Zeichen enthalten")
        if not isinstance(node, str) or not re.fullmatch(r"[0-9A-F]{16}", node) or int(node, 16) == 0:
            raise ValueError("Gateway benoetigt 16-stellige Node-ID in Grossbuchstaben")
        if port in entries or node == dedicated_entry["node"] or any(x["node"] == node for x in entries.values()):
            raise ValueError("Doppelte COM-Port- oder Node-ID-Zuordnung")
        entries[port] = {"name": name.strip(), "node": node}
    config = {"logger_gateway": dedicated, "gateways": entries}
    MANAGED_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=MANAGED_FILE.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(config, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Validate the entire config before committing.
        load_gateway_config(temporary)
        os.replace(temporary, MANAGED_FILE)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()



def _preference_file(config_path: Path) -> Path:
    return config_path.parent / "data" / "gateway_preferences.json"


def default_remote_gateway(path: Path = CONFIG_FILE) -> str:
    """Read user preference live from ignored web/data, falling back to logger."""
    logger_port, gateways = load_gateway_config(path)
    preference_file = _preference_file(path)
    if not preference_file.exists():
        return logger_port
    payload = json.loads(preference_file.read_text(encoding="utf-8"))
    preferred = payload.get("default_remote_gateway")
    if preferred not in gateways:
        return logger_port
    return preferred


def set_default_remote_gateway(port: str, path: Path = CONFIG_FILE) -> str:
    """Persist a validated remote preference without modifying tracked gateways.json."""
    if not isinstance(port, str):
        raise ValueError("Gateway-Port fehlt")
    port = normalize_gateway_port(port)
    _, gateways = load_gateway_config(path)
    if port not in gateways:
        raise ValueError("Gateway ist nicht konfiguriert")
    preference_file = _preference_file(path)
    preference_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"default_remote_gateway": port}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=preference_file.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, preference_file)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return port
