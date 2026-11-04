"""Single source of truth for trusted USB gateways and the dashboard logger.

Edit web/gateways.json, then restart the Flask server to apply changes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CONFIG_FILE = Path(__file__).with_name("gateways.json")


def load_gateway_config(path: Path = CONFIG_FILE):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("gateways"), dict):
        raise ValueError("gateways.json: 'gateways' muss ein Objekt sein")
    gateways = {}
    nodes = set()
    for port, entry in payload["gateways"].items():
        if not isinstance(port, str) or not re.fullmatch(r"COM[1-9][0-9]*", port, re.I):
            raise ValueError("gateways.json: ungueltiger COM-Port")
        if not isinstance(entry, dict):
            raise ValueError("gateways.json: Gateway-Eintrag muss ein Objekt sein")
        name, node = entry.get("name"), entry.get("node")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("gateways.json: Gateway-Name fehlt")
        if not isinstance(node, str) or not re.fullmatch(r"[0-9A-F]{16}", node) or int(node, 16) == 0:
            raise ValueError("gateways.json: ungueltige Knoten-ID")
        port = port.upper()
        if port in gateways or node in nodes:
            raise ValueError("gateways.json: COM-Port oder Knoten-ID doppelt")
        gateways[port] = (name.strip(), node)
        nodes.add(node)
    logger_port = payload.get("logger_gateway")
    if not isinstance(logger_port, str) or logger_port.upper() not in gateways:
        raise ValueError("gateways.json: 'logger_gateway' muss ein registrierter COM-Port sein")
    return logger_port.upper(), gateways


LOGGER_PORT, TRUSTED_GATEWAYS = load_gateway_config()
LOGGER_NAME = TRUSTED_GATEWAYS[LOGGER_PORT][0]
