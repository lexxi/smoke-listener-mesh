# Passive ESP-NOW Logger v0.1.0

For the **4th ESP32-C3 SuperMini**, operating as a receive-only logging point. Works alongside v0.5.1 nodes; does not transmit or relay. A single logger can only record packets it actually receives.

## Arduino IDE

- Open `firmware/mesh-logger-v0.1.0/mesh-logger-v0.1.0.ino`.
- Copy the **existing local** `firmware/mesh-v0.5.1/mesh_secrets.h` to the logger sketch directory. Do NOT generate a different key and do NOT commit/upload the secret file.
- Board: ESP32C3 Dev Module, USB CDC On Boot: Enabled; monitor 115200; radio channel 6.
- Example output (illustrative):
  `uptime_ms,origin,via,boot,seq,ttl,hops,type,rssi_dbm,channel,auth`
  `30235,0000A4289172DA90,90:DA:72:91:28:A4,75E2C67893603841,5,3,0,HEARTBEAT,-73,6,OK`
- Logs `# STATS` every 30s. `invalid` counts invalid packets of correct packet size; nonmatching lengths are silently ignored. It does not observe traffic beyond ESP-NOW matching this struct.

## Windows capture

Install once:
```powershell
py -m pip install pyserial
```

From repo root:
```powershell
py scripts/mesh_serial_logger.py --port COM7
```
Use your actual COM port (run with no `--port` to list). Writes timestamped CSV to `logs/`. The serial capture PC time is **receipt time**, not a synchronized source timestamp.

## Interpreting measurements

RSSI of directly received packets applies to the **immediate RF sender** identified by `via`, not necessarily the packet's `origin`. HMAC authenticates immutable origin payload, not `via` or `ttl`; an attacker can replay authentic messages or alter TTL. Duplicate relays count multiple times. Accurate packet delivery ratios require logs from sending and receiving nodes and knowledge of their up/down periods. ESP-NOW broadcasts offer no confirmation of delivery.

This is **not a smoke alarm, certified alert system or life-safety communication channel**. Independent certified smoke alarms must remain operational.
