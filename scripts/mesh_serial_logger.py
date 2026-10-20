#!/usr/bin/env python3
"""Record passive smoke-mesh ESP-NOW logger serial output to CSV. No third-party libraries except pyserial."""
import argparse
import csv
import datetime as dt
from pathlib import Path
import serial
from serial.tools import list_ports

FIELDS = ["pc_time", "uptime_ms", "origin", "via", "boot", "seq", "ttl", "hops", "type", "rssi_dbm", "channel", "auth"]

def main():
    p=argparse.ArgumentParser(description="Smoke Mesh serial logger")
    p.add_argument("--port", help="COM port, e.g. COM7")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--out", type=Path, default=None)
    args=p.parse_args()
    if not args.port:
        print("Available serial ports:")
        for item in list_ports.comports():
            print(f"  {item.device}: {item.description}")
        p.error("Specify --port COMx")
    outfile=args.out or Path("logs") / ("mesh_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv")
    outfile.parent.mkdir(parents=True,exist_ok=True)
    print("Writing", outfile)
    print("Stop with Ctrl+C")
    with serial.Serial(args.port,args.baud,timeout=1) as port, outfile.open("w",newline="",encoding="utf-8") as f:
        wr=csv.DictWriter(f,fieldnames=FIELDS);wr.writeheader()
        try:
            while True:
                line=port.readline().decode("utf-8",errors="replace").strip()
                if not line: continue
                now=dt.datetime.now().astimezone().isoformat(timespec="milliseconds")
                if line.startswith("#"):
                    print(now,line);continue
                if line.startswith("uptime_ms,"):continue
                cols=next(csv.reader([line]))
                if len(cols)!=len(FIELDS)-1:
                    print(now,"[UNKNOWN]",line);continue
                record=dict(zip(FIELDS[1:],cols))
                record["pc_time"]=now
                wr.writerow(record);f.flush()
                print(now, f"src={record['origin']} via={record['via']} ttl={record['ttl']} RSSI={record['rssi_dbm']}dBm")
        except KeyboardInterrupt:
            print("\nStopped.")
if __name__=="__main__":
    main()
