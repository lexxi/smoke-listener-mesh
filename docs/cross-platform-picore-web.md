# Gemeinsame Webapp für Windows und piCore (Raspberry Pi 2)

Status: Entwicklungsbranch, **noch keine Produktivmigration**.

## Prinzip

Eine gemeinsame Codebasis; Betriebssystemunterschiede ausschließlich
über Konfiguration. Windows-Standard `COM16` bleibt unverändert.
Firmware-Build und Signierung mit privatem Schlüssel bleiben auf Windows.
Der Pi übernimmt später nur Logger, Dashboard, Signaturprüfung und Remote-OTA.

### Neue Optionen

- `SMOKE_GATEWAYS_FILE`: Lokale Gateway-JSON statt versioniertem
  `web/gateways.json`. Unter Linux bevorzugt
  `/dev/serial/by-id/usb-...`, alternativ `/dev/ttyACM0`.
- `SMOKE_MANAGED_GATEWAYS_FILE`: Optionaler Pfad für lokal verwaltete
  zusätzliche Gateways; Windows-Standard bleibt `web/data/managed_gateways.json`.
- `SMOKE_LOGGER_AUTOSTART=0`: Webapp ohne angeschlossenen Gateway
  starten; Default auf Windows bleibt Autostart.
- `SMOKE_OTA_PUBLIC_KEY`: Bereits unterstützter Pfad zum **öffentlichen**
  Signaturprüfschlüssel; kein privater Schlüssel auf dem Pi.

### PiCore: Test ohne angeschlossenen Gateway

Repository unter `/mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh`,
virtuelle Umgebung unter `/mnt/mmcblk0p3/smoke-mesh/venv`.

```sh
cd /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh
. /mnt/mmcblk0p3/smoke-mesh/venv/bin/activate
python -m pip check
SMOKE_LOGGER_AUTOSTART=0 python web/app.py
```

Der Entwicklungsserver lauscht ausschließlich auf `127.0.0.1:8088`.
Vom Windows-Laptop aus einen SSH-Tunnel öffnen:

```powershell
ssh -L 8088:127.0.0.1:8088 tc@192.168.98.39
```

Im Laptop-Browser `http://127.0.0.1:8088` öffnen. Der lokale
Windows-Webserver muss dafür auf Port 8088 gestoppt sein, oder
für den SSH-Tunnel einen anderen **lokalen** Port, z. B.
`ssh -L 18088:127.0.0.1:8088 ...` verwenden und dann
`http://127.0.0.1:18088` öffnen.

Die Webapp und ihre Verwaltungs-APIs haben keine normale
Benutzeranmeldung. **Nicht** mit `--host 0.0.0.0` öffentlich im
LAN starten. SSH-Tunnel ist nur für den administrativen Test;
später gehört ein abgesicherter Reverse Proxy mit Authentifizierung
und TLS davor.

### Mit Linux-USB-Gateway (nach erstem Test)

Ein lokales, nicht versioniertes `web/data/gateways.pi.json`
mit der **tatsächlichen** `/dev/serial/by-id/`-Gerätekennung anlegen:

```json
{
  "logger_gateway": "/dev/serial/by-id/usb-GATEWAY_ECHTE_ID",
  "gateways": {
    "/dev/serial/by-id/usb-GATEWAY_ECHTE_ID": {
      "name": "Gateway",
      "node": "00000CEC7E6E27AC"
    }
  }
}
```

Anschließend `SMOKE_GATEWAYS_FILE` auf den absoluten Pfad setzen
und ohne `SMOKE_LOGGER_AUTOSTART=0` starten. Das Beispiel ist
nur eine Vorlage; die echte Gerätekennung mit
`ls -l /dev/serial/by-id/` bestimmen.

### Persistenz

piCore lädt das Root-Dateisystem in den RAM. Das Repository und
`web/data` liegen hier auf der dauerhaft eingehängten Partition P3.
Für späteren Dauerbetrieb sollten eine externe Logrotation,
Dateiberechtigungen, Service-Start und Backups ergänzt werden.
Die bestehende Webapp schreibt standardmäßig Logdateien unter
`log/` und SQLite-Daten unter `web/data/` relativ zum Repository.

### Validierung

```sh
python -m unittest discover -s tests -p 'test_*.py'
```

Für Windows zusätzlich die bestehenden Tests und Logger/Remote-OTA
gegen `COM16` durchführen. Kein Flash/OTA im Cross-Platform-Test.


## Direkter LAN-Betrieb ohne Login

Ab diesem Stand ist der **Monitor** über das lokale Netz ohne Passwort erreichbar:
`http://192.168.98.39:8088/`. Dafür `SMOKE_WEB_LAN=1` in
`/mnt/mmcblk0p3/smoke-mesh/data/web.env` setzen.
`SMOKE_WEB_PASSWORD_HASH` und `SMOKE_WEB_SECRET_KEY` werden nicht
mehr benötigt. Alte Einträge in der lokalen Datei dürfen bestehen bleiben,
werden aber ignoriert.

**Sicherheitsgrenze:** Im LAN sind nur `GET /` und `GET /api/status`
zugänglich. Die Seiten `/ota` und `/nodes` sind lesbar. Die Funkabfragen `STATUS` und `NAME_GET` sind im LAN erlaubt (separater CSRF-Token, mindestens 10 Sekunden Abstand). Schreibende APIs wie `NAME_SET`, `NAME_RESET`, `RESTART`, Gateway-Konfiguration, Logger-Steuerung und OTA bleiben auf Loopback beschränkt.
Für administrative Arbeiten
kann weiterhin ein SSH-Tunnel verwendet werden.

Keine Portweiterleitung ins Internet; auch die Monitoring-Daten werden
ohne TLS übertragen. Später kann HTTPS plus Authentifizierung ergänzt werden.

### Dauerbetrieb mit Waitress

```sh
cd /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh
. /mnt/mmcblk0p3/smoke-mesh/venv/bin/activate
python -m pip install 'waitress>=3,<4'
```

Die Startdatei `deploy/picore/start-web.sh` liest
`/mnt/mmcblk0p3/smoke-mesh/data/web.env` und startet Waitress auf
`0.0.0.0:8088`. Für piCore den folgenden Befehl **nach dem Mount von P3**
in `/opt/bootlocal.sh` eintragen:

```sh
su tc -c '/bin/sh /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh/deploy/picore/start-web.sh' >> /mnt/mmcblk0p3/smoke-mesh/logs/web-server.log 2>&1 &
```

Anschließend `sudo filetool.sh -b` und nach einem Reboot Webserver,
Logger, und Uhrzeit prüfen.


### Schreibende Knotenbefehle für einen einzelnen LAN-Admin-PC

`NAME_SET`, `NAME_RESET` und `RESTART` sind im direkten LAN
standardmäßig gesperrt. Eine explizite Rechnerfreigabe ist möglich:

```sh
SMOKE_LAN_NODE_ADMIN_IPS='192.168.98.50'
```

**Beispiel-IP ersetzen** durch die tatsächliche LAN-IPv4-Adresse
des Windows-Admin-PCs (z. B. `ipconfig`). In
`/mnt/mmcblk0p3/smoke-mesh/data/web.env` eintragen, Webapp neu
starten. Es sind nur exakte IP-Adressen erlaubt, kein CIDR/Wildcard,
keine Auswertung von `X-Forwarded-For`. Mehrere exakte IPs
lassen sich komma-separiert eintragen. Ohne Variable ist die Freigabe
deaktiviert. `STATUS` und `NAME_GET` bleiben für das LAN möglich.

Diese Ausnahme gilt **nur** für Funk-Knotenbefehle, nicht für
OTA, Upload, Logger-Steuerung oder die Registrierung von OTA-Zielen.
Der API-Request hat weiterhin einen CSRF-Token, eine 10-Sekunden-
Sperrfrist und läuft jeweils nur als ein Job.

Wichtig: IP-Freigabe ist **keine Benutzeranmeldung**. In einem
unvertrauenswürdigen Netz ist sie unzureichend. HTTP überträgt
Daten unverschlüsselt. Verwende die Freigabe nur in einem
abgeschotteten vertrauenswürdigen Administrations-LAN und
keinesfalls über eine Internet-Portweiterleitung. Für
vollständige Verwaltung später TLS und echte Authentifizierung
einführen.
