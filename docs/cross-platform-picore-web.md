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


## Direkter LAN-Betrieb und persistenter Bootstart

Für direkten Browserzugriff (kein SSH-Tunnel) hat der Entwicklungsbranch
eine optionale Passwortsperre. Der Default unter Windows bleibt
`127.0.0.1` ohne LAN-Modus. Für den Pi wird Waitress verwendet.
Im lokalen LAN ist HTTP **nicht verschlüsselt**; keine Portweiterleitung
zum Internet, kein untrusted WLAN. Für dauerhaften administrativen
Betrieb ist zusätzlich HTTPS einzuplanen.

Auf dem Pi einmalig:

```sh
cd /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh
. /mnt/mmcblk0p3/smoke-mesh/venv/bin/activate
python -m pip install 'waitress>=3,<4'
mkdir -p /mnt/mmcblk0p3/smoke-mesh/data /mnt/mmcblk0p3/smoke-mesh/logs
```

Die Datei `/mnt/mmcblk0p3/smoke-mesh/data/web.env` wird **nur lokal**
angelegt, Modus `0600`, z. B.:

```sh
SMOKE_WEB_LAN=1
SMOKE_WEB_PASSWORD_HASH='scrypt:...'
SMOKE_WEB_SECRET_KEY='...'
SMOKE_GATEWAYS_FILE='/mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh/web/data/gateways.pi.json'
```

Passworthash mit
`werkzeug.security.generate_password_hash(getpass(...))` und
Cookie-Secret mit `secrets.token_urlsafe(48)` erzeugen. Niemals
ein Klartextpasswort oder den privaten OTA-Signierschlüssel speichern.

Der versionierte Startbefehl liegt unter
`deploy/picore/start-web.sh`; dieser muss als `tc` laufen und P3
muss vorher gemountet sein. Den Start in `/opt/bootlocal.sh`
**nach** dem vorhandenen P3-Mount ergänzen:

```sh
su tc -c '/bin/sh /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh/deploy/picore/start-web.sh' >> /mnt/mmcblk0p3/smoke-mesh/logs/web-server.log 2>&1 &
```

Anschließend `sudo filetool.sh -b` und Reboot-Prüfung.
Die Konfigurationsdatei auf P3 bleibt ohne `filetool` bestehen.
Vermeide einen zweiten gleichzeitig laufenden Flask-Prozess:
der USB-Port darf nur vom einen gestarteten Logger geöffnet werden.
