#!/usr/bin/env python3
"""Summarize smoke-mesh raw log by origin; optionally resolve MAC/name/site."""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

RX = re.compile(r"\[RX\] (.*)")
PAIR = re.compile(r"([A-Za-z_]+)=([^ ]+)")
TIME = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ")


def origin_from_mac(mac):
    return "0000" + "".join(reversed(mac.upper().split(":")))


def main():
    p=argparse.ArgumentParser(description="Smoke Mesh RX summary")
    p.add_argument("log",type=Path)
    p.add_argument("--nodes",type=Path,default=Path("config/nodes.csv"))
    args=p.parse_args()
    mapping={}
    if args.nodes.is_file():
        with args.nodes.open(encoding="utf-8-sig",newline="") as file:
            for item in csv.DictReader(file):
                mac=(item.get("mac") or "").strip().upper()
                if mac:
                    mapping[origin_from_mac(mac)]=item
    info=defaultdict(lambda:{"rx":0,"direct":0,"relay":0,"rssi":[],"boots":set(),"seqs":set(),"first":None,"last":None,"packet_name":""})
    with args.log.open(encoding="utf-8",errors="replace") as file:
        for line in file:
            match=RX.search(line)
            if not match: continue
            values=dict(PAIR.findall(match.group(1)))
            origin=values.get("origin","").upper()
            if not origin:continue
            row=info[origin]
            row["rx"]+=1
            hops=int(values.get("hops","0"))
            row["direct" if hops==0 else "relay"]+=1
            if hops==0 and "rssi" in values:
                row["rssi"].append(int(values["rssi"]))
            if values.get("boot"): row["boots"].add(values["boot"])
            if values.get("seq"): row["seqs"].add(int(values["seq"]))
            name=values.get("name","")
            if name and name!="(unset)":row["packet_name"]=name
            time=TIME.match(line)
            if time:
                if row["first"] is None: row["first"]=time.group(1)
                row["last"]=time.group(1)
    print(f"{'MAC':<18} {'Name':<24} {'Standort':<20} {'RX':>6} {'direkt':>7} {'Relay':>6} {'RSSI':>7} {'Luecken':>7} {'Boots':>5}")
    for origin,row in sorted(info.items()):
        item=mapping.get(origin,{})
        mac=item.get("mac","?") or "?"
        name=row["packet_name"] or item.get("name","") or "-"
        place=item.get("location","") or "-"
        rssi=f"{sum(row['rssi'])/len(row['rssi']):.1f}" if row["rssi"] else "-"
        seqs=row["seqs"]
        missing=(max(seqs)-min(seqs)+1-len(seqs)) if seqs else 0
        print(f"{mac:<18} {name:<24} {place:<20} {row['rx']:>6} {row['direct']:>7} {row['relay']:>6} {rssi:>7} {missing:>7} {len(row['boots']):>5}")
        print(f"  origin={origin}, {row['first'] or '?'} - {row['last'] or '?'}")
    print("Note: gaps only within observed sequence ranges; relay RSSI belongs to last hop.")


if __name__=="__main__":
    main()
