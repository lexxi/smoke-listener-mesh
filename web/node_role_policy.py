"""Local explicit role policy for v0.6.15+ OTA; unknown targets fail closed.

This is a deployment policy, not cryptographic hardware attestation.
Never infer device roles from serial ports, names or firmware releases.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROLE_FILE = Path(__file__).resolve().parent / "data" / "node_roles.json"
ROLES = {"mesh", "listener", "gateway", "hybrid"}

def load_roles(path: Path = ROLE_FILE) -> dict[str, str]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("node_roles.json muss ein Objekt sein")
    result = {}
    for node, role in payload.items():
        if not isinstance(node, str) or not re.fullmatch(r"[0-9A-F]{16}", node):
            raise ValueError("Ungültige Knoten-ID in node_roles.json")
        if role not in ROLES:
            raise ValueError("Ungültige Knotenrolle: " + str(role))
        result[node] = role
    return result

def check_release_role(plan: dict, roles: dict[str,str]) -> str:
    """Return role or raise; only v0.6.15+ require a configured role."""
    version = tuple(map(int, plan["version"].split(".")))
    if version < (0, 6, 15):
        return "legacy"
    features = plan.get("features")
    if features is None:
        raise ValueError("Für v0.6.15+ sind signierte Features erforderlich")
    target = plan["target"]
    role = roles.get(target)
    if role is None:
        raise ValueError("Keine freigegebene Knotenrolle für " + target + " (node_roles.json)")
    feature_set = set(features)
    if "audio" in feature_set and "gateway" in feature_set:
        needed = "hybrid"
    elif "audio" in feature_set:
        needed = "listener"
    elif "gateway" in feature_set:
        needed = "gateway"
    else:
        needed = "mesh"
    if role != needed:
        raise ValueError(
            f"Firmware-Featureprofil {needed} nicht für Zielrolle {role} "
            f"({target}) freigegeben"
        )
    return role
