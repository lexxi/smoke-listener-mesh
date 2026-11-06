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


### Schreibende Knotenbefehle: einzelne IPs und CIDR-Netze

`NAME_SET`, `NAME_RESET` und `RESTART` bleiben standardmäßig
gesperrt. Freigaben werden auf dem Pi lokal unter
`/mnt/mmcblk0p3/smoke-mesh/data/web.env` mit der Einstellung
`SMOKE_LAN_NODE_ADMIN_IPS` konfiguriert. Beispiele:

```sh
# Nur ein Rechner
SMOKE_LAN_NODE_ADMIN_IPS='192.168.98.50'

# Ganzes Netzwerk
SMOKE_LAN_NODE_ADMIN_IPS='192.168.98.0/24'

# Gemischt, kommasepariert (IPv4 und optional IPv6)
SMOKE_LAN_NODE_ADMIN_IPS='192.168.98.50,192.168.99.0/24,2001:db8:1::/64'
```

CIDR-Adressen müssen kanonische Netzadressen sein (z. B.
`192.168.98.0/24`, nicht `192.168.98.50/24`).
Ungültige Einträge werden ignoriert, nicht freigegeben.
Keine Wildcards, keine Auswertung von `X-Forwarded-For`.
Ohne Variable ist keine schreibende LAN-Knotenverwaltung erlaubt.
Nach Konfigurationsänderungen die Webapp neu starten.
`STATUS` und `NAME_GET` sind auch ohne diese Freigabe erlaubt.

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


## Logrotation und Aufbewahrung (piCore, opt-in)

Der USB-Logger schreibt seine aktuelle Datei fortlaufend. Externes
Umbenennen/Abschneiden der offenen Datei ist nicht sicher. Deshalb kann
der Logger selbst nach jeweils 10 MiB eine neue `mesh_*.log`-Datei
mit Suffix `_part0001`, `_part0002` usw. öffnen.

In der **lokalen** `/mnt/mmcblk0p3/smoke-mesh/data/web.env`
für piCore ergänzen:

```sh
SMOKE_LOG_ROTATE_MB='10'
SMOKE_LOG_RETENTION_DAYS='30'
SMOKE_LOG_MAX_MB='512'
```

- Jeder Raw-Log-Teil erhält eine Größenbegrenzung von 10 MiB.
- Ein Hintergrundlauf prüft stündlich `<repo>/log/` auf abgeschlossene
  `mesh_*.log`- und `logger_control_*.log`-Dateien.
- Abgeschlossene Logs älter als 30 Tage werden gelöscht; bei mehr
  als 512 MiB werden die ältesten abgeschlossenen Logs zuerst gelöscht.
- Die jeweils neuesten Dateien beider Typen und erkennbare offene
  Prozessdateien bleiben geschützt. Bei nur aktiven Dateien kann das
  Limit vorübergehend überschritten werden.
- Mit aktivierter Rotation werden die empfangenen Rohdaten nicht
  zusätzlich zeilenweise ins Diagnoseprotokoll kopiert.
- Die SQLite-Datenbank `web/data/mesh.db`, `web-server.log`
  und `web/data/ota_jobs/` werden **nicht** bereinigt. Für deren
  Wachstum/Backup braucht es eine separate Strategie.
- Ohne diese Variablen bleiben die bisherigen Windows-Defaults
  vollständig unverändert.

Vor der Aktivierung trockene Vorschau (löscht nichts):

```sh
cd /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh
. /mnt/mmcblk0p3/smoke-mesh/venv/bin/activate
python web/log_retention.py --dir log --days 30 --max-mb 512
```

Der Dienst verwendet später dieselben Regeln mit aktivem Löschen.
Beim Übergang zu einem neuen Chunk zeigt die Log-Auswahl des Dashboards
die Teile als einzelne Sessions. Ein Backup der Rohlogs ist bei Bedarf
vor der Aktivierung anzulegen.

Für Windows weiterhin Standard: kein automatisches Löschen, kein
Rotieren, solange die Optionen nicht explizit gesetzt sind.
