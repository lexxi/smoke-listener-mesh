"""Dashboard may be served on LAN; privileged actions remain loopback-only."""
from __future__ import annotations
import os
import ipaddress
from flask import abort, request

LOOPBACK = ("127.0.0.1", "::1")

def lan_enabled() -> bool:
    return os.environ.get("SMOKE_WEB_LAN", "0") == "1"

def check_configuration() -> None:
    # LAN is intentionally monitoring-only. No password or browser session.
    return None

def authorized() -> bool:
    return request.remote_addr in LOOPBACK

def lan_node_write_allowed() -> bool:
    """Explicit IPv4/IPv6 literal allowlist for name changes and node reboot.

    No CIDRs, wildcards, or forwarded headers. Never authorizes OTA endpoints.
    """
    peer = request.remote_addr
    if not lan_enabled() or not peer:
        return False
    allowed = os.environ.get("SMOKE_LAN_NODE_ADMIN_IPS", "").split(",")
    try:
        client = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for candidate in allowed:
        candidate = candidate.strip()
        try:
            if client == ipaddress.ip_address(candidate):
                return True
        except ValueError:
            continue
    return False


def require_authorized() -> None:
    if not authorized():
        abort(403)
