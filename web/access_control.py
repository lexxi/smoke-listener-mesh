"""Dashboard may be served on LAN; privileged actions remain loopback-only."""
from __future__ import annotations
import os
from flask import abort, request

LOOPBACK = ("127.0.0.1", "::1")

def lan_enabled() -> bool:
    return os.environ.get("SMOKE_WEB_LAN", "0") == "1"

def check_configuration() -> None:
    # LAN is intentionally monitoring-only. No password or browser session.
    return None

def authorized() -> bool:
    return request.remote_addr in LOOPBACK

def require_authorized() -> None:
    if not authorized():
        abort(403)
