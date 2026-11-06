"""Optional password gate for LAN operation; default remains localhost-only."""
from __future__ import annotations
import os
import secrets
from flask import abort, request, session
from werkzeug.security import check_password_hash

LOOPBACK = ("127.0.0.1", "::1")

def lan_enabled() -> bool:
    return os.environ.get("SMOKE_WEB_LAN", "0") == "1"

def check_configuration() -> None:
    if lan_enabled():
        if not os.environ.get("SMOKE_WEB_PASSWORD_HASH"):
            raise RuntimeError("SMOKE_WEB_PASSWORD_HASH required for LAN access")
        if len(os.environ.get("SMOKE_WEB_SECRET_KEY", "")) < 32:
            raise RuntimeError("SMOKE_WEB_SECRET_KEY must be at least 32 characters")

def authorized() -> bool:
    if not lan_enabled():
        return request.remote_addr in LOOPBACK
    return session.get("smoke_authenticated") is True

def require_authorized() -> None:
    if not authorized():
        abort(403)

def verify_password(password: str) -> bool:
    stored = os.environ.get("SMOKE_WEB_PASSWORD_HASH", "")
    return bool(stored) and check_password_hash(stored, password)

def new_login_csrf() -> str:
    token = secrets.token_urlsafe(32)
    session["smoke_login_csrf"] = token
    return token

def validate_login_csrf(token: str) -> bool:
    expected = session.get("smoke_login_csrf", "")
    return bool(expected) and secrets.compare_digest(expected, token)
