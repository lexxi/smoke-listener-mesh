"""OTA page. Legacy target-USB staging endpoints are explicitly retired.

Active remote OTA endpoints are defined in web/remote.py.
"""
from __future__ import annotations

import secrets
from access_control import require_authorized
from flask import Blueprint, abort, jsonify, render_template, request

bp = Blueprint("ota", __name__)
csrf_token = secrets.token_urlsafe(32)


def local():
    require_authorized()


@bp.get("/ota")
def page():
    local()
    return render_template("ota.html", csrf_token=csrf_token)


@bp.route("/api/ota/start", methods=["POST"])
def legacy_start():
    local()
    return jsonify({"error": "Die alte USB-OTA-Schnittstelle ist deaktiviert. Verwende /api/remote/start."}), 410


@bp.get("/api/ota/releases")
def legacy_releases():
    local()
    return jsonify({"error": "Alte Release-Liste deaktiviert. Verwende /api/releases."}), 410


@bp.get("/api/ota/job")
def legacy_job():
    local()
    return jsonify({"error": "Alte OTA-Jobliste deaktiviert. Verwende /api/remote/job."}), 410
