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
    """Match exact IPv4/IPv6 addresses or CIDR networks for node commands.

    Never trust forwarded headers; this permission does not authorize OTA.
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
        if not candidate:
            continue
        try:
            if "/" in candidate:
                if client in ipaddress.ip_network(candidate, strict=True):
                    return True
            elif client == ipaddress.ip_address(candidate):
                return True
        except ValueError:
            # Invalid entries never broaden the allowlist.
            continue
    return False


def require_authorized() -> None:
    if not authorized():
        abort(403)
