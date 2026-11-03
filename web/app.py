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
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).resolve().parents[1]
RX = re.compile(r"\[RX\]\s+(.*)")
KV = re.compile(r"([A-Za-z_]+)=([^\s]+)")
TIME = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+")
LOCAL = dt.datetime.now().astimezone().tzinfo
app = Flask(__name__)
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
        source_file TEXT NOT NULL,
        source_offset INTEGER NOT NULL,
        UNIQUE(source_file, source_offset)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_origin_time ON receptions(origin, received_at DESC)")
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
                int(values["rssi"]) if "rssi" in values else None, values["type"])
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
        with database() as conn:
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
                                (received_at,origin,name,via,boot,seq,hops,ttl,rssi,packet_type,source_file,source_offset)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", parsed + (key, start))
                            count += cursor.rowcount
                    offsets[key] = ((stat.st_dev, stat.st_ino), f.tell())
        return count

def snapshot():
    ingest()
    now = dt.datetime.now().astimezone().replace(tzinfo=None)
    settings = nodes_config()
    nodes = {mac: {**entry, "name": entry["configured_name"] or entry["location"] or mac,
                   "last_seen": None, "age_seconds": None, "status": "unknown",
                   "packets": 0, "direct": 0, "relayed": 0, "rssi": None,
                   "hops": None, "via": None, "last_type": None}
             for mac, entry in settings.items()}
    with database() as conn:
        latest = conn.execute("""SELECT r.* FROM receptions r JOIN
          (SELECT origin, MAX(id) AS last_id FROM receptions GROUP BY origin) x
          ON x.last_id=r.id""").fetchall()
        sums = {r["origin"]: r for r in conn.execute(
            "SELECT origin,COUNT(*) packets,SUM(hops=0) direct,SUM(hops>0) relayed FROM receptions GROUP BY origin")}
        paths = [dict(row) for row in conn.execute(
            """SELECT origin,via,hops,COUNT(*) AS packets FROM receptions
            WHERE hops>0 GROUP BY origin,via,hops ORDER BY packets DESC LIMIT 100""")]
        recent = [dict(row) for row in conn.execute(
            """SELECT received_at,origin,name,via,seq,hops,rssi,packet_type
               FROM receptions ORDER BY id DESC LIMIT 40""")]
        total = conn.execute("SELECT COUNT(*) FROM receptions").fetchone()[0]
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
                    hops=last["hops"], via=last["via"], last_type=last["packet_type"])
    for path in paths:
        path["source_mac"] = mac_from_origin(path["origin"])
        path["source"] = nodes.get(path["source_mac"], {}).get("name", path["source_mac"])
        path["relay"] = nodes.get(path["via"], {}).get("name", path["via"])
    for event in recent:
        mac = mac_from_origin(event["origin"])
        event["source"] = nodes.get(mac, {}).get("name", event["name"] or mac)
        event["relay"] = nodes.get(event["via"], {}).get("name", event["via"])
    return {"nodes": list(nodes.values()), "routes": paths, "events": recent,
            "total": total, "generated_at": now.isoformat(), "log_files": len(log_files()),
            "note": "RSSI measures the last radio hop, not necessarily origin-to-logger signal strength."}

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/status")
def status():
    return jsonify(snapshot())

def main():
    parser = argparse.ArgumentParser(description="Local Smoke Mesh web dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--log-dir", action="append", type=Path,
                        help="Additional directory with mesh_*.log (repeatable)")
    args = parser.parse_args()
    if args.log_dir:
        log_dirs.extend(args.log_dir)
    print("Monitoring:", ", ".join(map(str, log_dirs)), flush=True)
    print("Dashboard: http://%s:%s" % (args.host, args.port), flush=True)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
