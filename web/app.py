#!/usr/bin/env python3
"""Smoke Mesh dashboard: read existing serial log files; never open the serial port."""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from flask import Flask, jsonify, render_template, request, abort
from access_control import lan_enabled, authorized, check_configuration
from dashboard_version import DASHBOARD_VERSION

ROOT = Path(__file__).resolve().parents[1]
RX = re.compile(r"\[RX\]\s+(.*)")
TX = re.compile(r"\[TX\]\s+(.*)")
KV = re.compile(r"([A-Za-z_]+)=([^\s]+)")
TIME = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+")
LOCAL = dt.datetime.now().astimezone().tzinfo
app = Flask(__name__)
check_configuration()


@app.before_request
def authorize_request():
    # Direct LAN exposure is limited to the monitor and its read-only status.
    # Remote OTA, gateway controls, release uploads and inventory need loopback.
    if not lan_enabled() or authorized():
        return None
    if request.method == "GET" and request.path in (
        "/", "/nodes", "/ota", "/api/status", "/api/logger/status",
        "/api/releases", "/api/remote/config", "/api/remote/job",
        "/api/remote/gateway-settings", "/api/nodes/registry",
    ):
        return None
    if request.method == "POST" and request.path == "/api/remote/node-action":
        return None  # Endpoint separately enforces STATUS/NAME_GET and LAN-specific CSRF.
    abort(403)

from ota import bp as ota_blueprint
app.register_blueprint(ota_blueprint)
from logger_control import bp as logger_blueprint
app.register_blueprint(logger_blueprint)
from release_library import bp as releases_blueprint
app.register_blueprint(releases_blueprint)
from remote import bp as remote_blueprint
app.register_blueprint(remote_blueprint)
from node_registry import bp as node_registry_blueprint
app.register_blueprint(node_registry_blueprint)
lock = threading.RLock()
db_path = ROOT / "web" / "data" / "mesh.db"
log_dirs = [ROOT / "log", ROOT / "logs", ROOT / "scripts" / "log"]
offsets = {}

def database():
    conn = sqlite3.connect(db_path, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS receptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT NOT NULL,
        origin TEXT NOT NULL,
        name TEXT NOT NULL,
        via TEXT NOT NULL,
        boot TEXT NOT NULL,
        seq INTEGER NOT NULL,
        hops INTEGER NOT NULL,
        ttl INTEGER NOT NULL,
        rssi INTEGER,
        packet_type TEXT NOT NULL,
        firmware TEXT,
        source_file TEXT NOT NULL,
        source_offset INTEGER NOT NULL,
        UNIQUE(source_file, source_offset)
    )""")
    columns = {r[1] for r in conn.execute("PRAGMA table_info(receptions)")}
    if "firmware" not in columns:
        conn.execute("ALTER TABLE receptions ADD COLUMN firmware TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_origin_time ON receptions(origin, received_at DESC)")
    conn.execute("""CREATE TABLE IF NOT EXISTS transmissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sent_at TEXT NOT NULL, origin TEXT NOT NULL,
        boot TEXT NOT NULL, seq INTEGER NOT NULL,
        source_file TEXT NOT NULL, source_offset INTEGER NOT NULL,
        firmware TEXT,
        UNIQUE(source_file, source_offset)
    )""")
    txcols = {r[1] for r in conn.execute("PRAGMA table_info(transmissions)")}
    if "firmware" not in txcols:
        conn.execute("ALTER TABLE transmissions ADD COLUMN firmware TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_time ON transmissions(sent_at DESC)")
    return conn

def mac_from_origin(origin):
    # Firmware ID: 0000 + reversed 6 MAC bytes.
    if not re.fullmatch(r"[0-9A-Fa-f]{16}", origin):
        return ""
    tail = origin[4:]
    octets = [tail[i:i + 2] for i in range(0, 12, 2)]
    return ":".join(reversed(octets)).upper()

def nodes_config():
    path = ROOT / "config" / "nodes.csv"
    entries = {}
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                mac = (row.get("mac") or "").strip().upper()
                if mac:
                    entries[mac] = {"mac": mac, "configured_name": (row.get("name") or "").strip(),
                                    "location": (row.get("location") or "").strip()}
    return entries

def parse_line(line):
    m = RX.search(line)
    stamp = TIME.match(line)
    if not m or not stamp:
        return None
    values = dict(KV.findall(m.group(1)))
    if values.get("AUTH") != "OK":
        return None
    necessary = ("origin", "boot", "seq", "via", "ttl", "hops", "type")
    if any(k not in values for k in necessary):
        return None
    try:
        timestamp = dt.datetime.strptime(stamp.group(1), "%Y-%m-%d %H:%M:%S")
        return (timestamp.isoformat(), values["origin"].upper(), values.get("name", ""),
                values["via"].upper(), values["boot"].upper(), int(values["seq"]),
                int(values["hops"]), int(values["ttl"]),
                int(values["rssi"]) if "rssi" in values else None, values["type"],
                values.get("fw") if re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}(?:\.[a-h])?", values.get("fw", "")) else None)
    except (ValueError, OverflowError):
        return None

def parse_tx(line):
    match = TX.search(line)
    stamp = TIME.match(line)
    if not match or not stamp:
        return None
    values = dict(KV.findall(match.group(1)))
    if any(k not in values for k in ("origin", "boot", "seq")):
        return None
    try:
        timestamp = dt.datetime.strptime(stamp.group(1), "%Y-%m-%d %H:%M:%S")
        return (timestamp.isoformat(), values["origin"].upper(),
                values["boot"].upper(), int(values["seq"]),
                values.get("fw") if re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}(?:\.[a-h])?", values.get("fw", "")) else None)
    except (ValueError, OverflowError):
        return None

def log_files():
    found = {}
    for folder in log_dirs:
        if folder.is_dir():
            for path in folder.glob("mesh_*.log"):
                if path.is_file():
                    found[str(path.resolve())] = path
    return sorted(found.values(), key=lambda p: (p.stat().st_mtime, str(p)))

def ingest():
    """Incremental tail; handles appended data and restarted/rotated files."""
    with lock:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with closing(database()) as conn, conn:
            for path in log_files():
                key = str(path.resolve())
                stat = path.stat()
                state = offsets.get(key)
                if state is None or state[0] != (stat.st_dev, stat.st_ino) or stat.st_size < state[1]:
                    offset = 0
                else:
                    offset = state[1]
                with path.open("rb") as f:
                    f.seek(offset)
                    while True:
                        start = f.tell()
                        line = f.readline()
                        if not line:
                            break
                        # Do not consume an incompletely flushed line.
                        if not line.endswith(b"\n"):
                            f.seek(start)
                            break
                        parsed = parse_line(line.decode("utf-8", errors="replace"))
                        if parsed:
                            cursor = conn.execute(
                                """INSERT OR IGNORE INTO receptions
                                (received_at,origin,name,via,boot,seq,hops,ttl,rssi,packet_type,firmware,source_file,source_offset)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", parsed + (key, start))
                            count += cursor.rowcount
                        else:
                            sent = parse_tx(line.decode("utf-8", errors="replace"))
                            if sent:
                                conn.execute(
                                    """INSERT OR IGNORE INTO transmissions
                                    (sent_at,origin,boot,seq,firmware,source_file,source_offset)
                                    VALUES (?,?,?,?,?,?,?)""", sent + (key, start))
                    offsets[key] = ((stat.st_dev, stat.st_ino), f.tell())
        return count

def available_sessions():
    """One log file is one test session; choose latest modified file as default."""
    return sorted(log_files(), key=lambda p: (p.stat().st_mtime, str(p)), reverse=True)

def snapshot(selected_file=None):
    ingest()
    sessions = available_sessions()
    allowed = {str(p.resolve()): p for p in sessions}
    if selected_file and selected_file not in allowed:
        raise ValueError("Unknown log file")
    chosen = selected_file or (str(sessions[0].resolve()) if sessions else None)
    session_info = [
        {"id": str(p.resolve()), "label": p.name, "active": str(p.resolve()) == chosen}
        for p in sessions
    ]
    now = dt.datetime.now().astimezone().replace(tzinfo=None)
    settings = nodes_config()
    nodes = {mac: {**entry, "name": entry["configured_name"] or entry["location"] or mac,
                   "last_seen": None, "age_seconds": None, "status": "unknown",
                   "packets": 0, "direct": 0, "relayed": 0, "rssi": None,
                   "hops": None, "via": None, "last_type": None, "firmware": None}
             for mac, entry in settings.items()}
    with closing(database()) as conn, conn:
        if chosen is None:
            latest, sums, paths, recent, total, active_logger, logger_tx = [], {}, [], [], 0, None, None
        else:
            latest = conn.execute("""SELECT * FROM (
                SELECT r.*, ROW_NUMBER() OVER
                    (PARTITION BY origin ORDER BY received_at DESC, id DESC) AS rn
                FROM receptions r WHERE source_file=?
            ) WHERE rn=1""", (chosen,)).fetchall()
            sums = {r["origin"]: r for r in conn.execute(
                """SELECT origin, COUNT(*) packets, SUM(hops=0) direct,
                   SUM(hops>0) relayed FROM receptions WHERE source_file=? GROUP BY origin""",
                (chosen,))}
            paths = [dict(row) for row in conn.execute(
                """SELECT origin,via,hops,COUNT(*) AS packets FROM receptions
                   WHERE source_file=? AND hops>0 GROUP BY origin,via,hops
                   ORDER BY packets DESC LIMIT 100""", (chosen,))]
            recent = [dict(row) for row in conn.execute(
                """SELECT received_at,origin,name,via,seq,hops,rssi,packet_type
                   FROM receptions WHERE source_file=?
                   ORDER BY received_at DESC,id DESC LIMIT 40""", (chosen,))]
            total = conn.execute(
                "SELECT COUNT(*) FROM receptions WHERE source_file=?", (chosen,)
            ).fetchone()[0]
            active_logger = conn.execute(
                """SELECT * FROM transmissions WHERE source_file=?
                   ORDER BY sent_at DESC,id DESC LIMIT 1""", (chosen,)
            ).fetchone()
            logger_tx = conn.execute(
                "SELECT COUNT(*) FROM transmissions WHERE source_file=? AND origin=?",
                (chosen, active_logger["origin"])
            ).fetchone()[0] if active_logger else None
    for last in latest:
        mac = mac_from_origin(last["origin"])
        if not mac:
            continue
        if mac not in nodes:
            nodes[mac] = {"mac": mac, "configured_name": "", "location": "",
                          "name": last["name"] or mac, "status": "unknown"}
        node = nodes[mac]
        stamp = dt.datetime.fromisoformat(last["received_at"])
        age = max(0, int((now - stamp).total_seconds()))
        counters = sums[last["origin"]]
        node.update(name=last["name"] or node["configured_name"] or node["location"] or mac,
                    last_seen=last["received_at"], age_seconds=age,
                    status="online" if age <= 45 else "stale" if age <= 120 else "offline",
                    packets=counters["packets"], direct=counters["direct"] or 0,
                    relayed=counters["relayed"] or 0, rssi=last["rssi"],
                    hops=last["hops"], via=last["via"], last_type=last["packet_type"],
                    firmware=last["firmware"])
    logger_mac = None
    if active_logger:
        logger_mac = mac_from_origin(active_logger["origin"])
        if logger_mac:
            if logger_mac not in nodes:
                nodes[logger_mac] = {
                    "mac": logger_mac, "configured_name": "", "location": "",
                    "name": logger_mac, "packets": 0, "direct": 0, "relayed": 0
                }
            logger_node = nodes[logger_mac]
            sent_at = active_logger["sent_at"]
            age = max(0, int((now - dt.datetime.fromisoformat(sent_at)).total_seconds()))
            logger_node.update(
                role="logger", last_seen=sent_at, age_seconds=age,
                status="online" if age <= 45 else "stale" if age <= 120 else "offline",
                tx_packets=logger_tx, last_type="TX",
                firmware=active_logger["firmware"],
                hops=None, via=None, rssi=None,
            )
    for node in nodes.values():
        node.setdefault("role", "remote")
    for path in paths:
        path["source_mac"] = mac_from_origin(path["origin"])
        path["source"] = nodes.get(path["source_mac"], {}).get("name", path["source_mac"])
        path["relay"] = nodes.get(path["via"], {}).get("name", path["via"])
    for event in recent:
        mac = mac_from_origin(event["origin"])
        event["source"] = nodes.get(mac, {}).get("name", event["name"] or mac)
        event["relay"] = nodes.get(event["via"], {}).get("name", event["via"])
    return {"nodes": list(nodes.values()), "logger_mac": logger_mac,
            "selected_file": chosen, "sessions": session_info,
            "routes": paths, "events": recent,
            "total": total, "generated_at": now.isoformat(), "log_files": len(sessions),
            "note": "RSSI measures the last radio hop, not necessarily origin-to-logger signal strength."}

@app.get("/nodes")
def node_admin():
    return render_template("nodes.html")

@app.get("/")
def index():
    return render_template("index.html", dashboard_version=DASHBOARD_VERSION)

@app.get("/api/status")
def status():
    try:
        return jsonify(snapshot(request.args.get("file") or None))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

def main():
    parser = argparse.ArgumentParser(description="Local Smoke Mesh web dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--server", choices=("flask", "waitress"), default="flask")
    parser.add_argument("--log-dir", action="append", type=Path,
                        help="Additional directory with mesh_*.log (repeatable)")
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "::1", "localhost") and not lan_enabled():
        parser.error("LAN binding requires SMOKE_WEB_LAN=1 (monitoring-only, privileged APIs localhost-only)")
    if args.log_dir:
        log_dirs.extend(args.log_dir)
    from logger_control import autostart
    if os.environ.get("SMOKE_LOGGER_AUTOSTART", "1") == "0":
        print("Logger: Autostart disabled (SMOKE_LOGGER_AUTOSTART=0)", flush=True)
    else:
        logger_state = autostart()
        print("Logger:", logger_state["note"], flush=True)
    print("Monitoring:", ", ".join(map(str, log_dirs)), flush=True)
    print("Dashboard: http://%s:%s" % (args.host, args.port), flush=True)
    if args.server == "waitress":
        from waitress import serve
        serve(app, host=args.host, port=args.port, threads=4)
    else:
        app.run(host=args.host, port=args.port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
