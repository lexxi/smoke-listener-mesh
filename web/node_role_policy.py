"""Explicit OTA target allowlist, independent of ESP32 feature selection.

Any registered ESP32-C3 may receive any signed variant. Registration is not a
hardware capability check: an AUDIO build still requires an INMP441 to detect.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

TARGETS_FILE = Path(__file__).resolve().parent / "data" / "node_targets.json"

def load_targets(path: Path = TARGETS_FILE) -> set[str]:
    if not path.is_file():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) > 4:
        raise ValueError("node_targets.json muss eine Liste mit maximal vier Zielknoten sein")
    result = set()
    for node in payload:
        if not isinstance(node, str) or not re.fullmatch(r"[0-9A-F]{16}", node) or int(node,16)==0:
            raise ValueError("Ungültige Knoten-ID in node_targets.json")
        if node in result:
            raise ValueError("Doppelte Knoten-ID in node_targets.json")
        result.add(node)
    return result

def check_release_target(plan: dict, targets: set[str]) -> None:
    version = tuple(map(int, plan["version"].split(".")[:3]))
    if version < (0, 6, 15):
        return
    if plan.get("features") is None:
        raise ValueError("Für v0.6.15+ sind signierte Features erforderlich")
    if plan["target"] not in targets:
        raise ValueError("Zielknoten nicht freigegeben: " + plan["target"])
