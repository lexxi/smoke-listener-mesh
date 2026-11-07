# Gemeinsame Webapp für Windows und piCore (Raspberry Pi 2)

Status: **in `main` seit PR #10 (07.11.2026)**. Auf dem Raspberry Pi 2
(piCore 17.0.1, Hostname `picore`) im LAN in Betrieb; Windows bleibt
weiterhin unterstützt. Remote-OTA auf dem Pi ist noch **nicht** getestet.

## Prinzip

Eine gemeinsame Codebasis; Betriebssystemunterschiede ausschließlich
über Konfiguration. Windows-Standard `COM16` bleibt unverändert.
Firmware-Build und Signierung mit privatem Schlüssel bleiben auf Windows.
Der Pi betreibt Logger und Dashboard sowie die getestete Knotenverwaltung.
Signaturprüfung und Remote-OTA auf dem Pi bleiben gesondert zu prüfen.

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

Die Webapp hat keine Benutzeranmeldung. Für den laufenden Pi-Betrieb
ist direkter LAN-Zugriff bewusst aktiviert (`SMOKE_WEB_LAN=1`).
Auf keinem Fall eine Portweiterleitung ins Internet einrichten.
Ein SSH-Tunnel bleibt für administrative Tests möglich.

### Linux-USB-Gateway (in Betrieb)

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
Autostart, Web-/Rohlogrotation und SQLite-Tagesbackups sind inzwischen
in Betrieb. Externe Backups, Identitätsprüfung des USB-Geräts und
Überwachung eines unerwarteten Webserver-Absturzes sind noch offen.
Die bestehende Webapp schreibt standardmäßig Logdateien unter
`log/` und SQLite-Daten unter `web/data/` relativ zum Repository.

### Validierung

```sh
python -m unittest discover -s tests -p 'test_*.py'
```

Windows: **97 Tests OK**, Remote-STATUS über COM16 zur Garage bestätigt.
piCore: **96 Tests OK** vor den letzten Windows-Fixes, alle fünf
Knotenbefehle getestet; neue SQLite-Verbindungsfixes unter piCore noch
nicht erneut regressionsgetestet. Kein Firmware-Flash beim
plattformübergreifenden Test; Remote-OTA auf piCore weiter offen.


## Direkter LAN-Betrieb ohne Login

Ab diesem Stand ist der **Monitor** über das lokale Netz ohne Passwort erreichbar:
`http://192.168.98.39:8088/`. Dafür `SMOKE_WEB_LAN=1` in
`/mnt/mmcblk0p3/smoke-mesh/data/web.env` setzen.
`SMOKE_WEB_PASSWORD_HASH` und `SMOKE_WEB_SECRET_KEY` werden nicht
mehr benötigt. Alte Einträge in der lokalen Datei dürfen bestehen bleiben,
werden aber ignoriert.

**Aktuelle Sicherheitsgrenze:** Die Seiten `/`, `/nodes` und `/ota`
sind im LAN ohne Login lesbar. `STATUS` und `NAME_GET` sind als
Funkabfragen erlaubt (CSRF-Token und mindestens zehn Sekunden Abstand).
`NAME_SET`, `NAME_RESET` und `RESTART` funktionieren mit einer
expliziten IP- oder CIDR-Freigabe über `SMOKE_LAN_NODE_ADMIN_IPS`.
Firmware-OTA, Uploads, Inventar- und Gatewayänderungen bleiben im direkten LAN
gesperrt. Logger-Start/-Stop kann optional für ausdrücklich freigegebene
Client-IP-Adressen aktiviert werden (siehe unten). Zugriff über Loopback ist separat
möglich; ein CSRF-Token ist keine Authentisierung.

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
`0.0.0.0:8088`. Die aktive `/opt/bootlocal.sh` mountet zunächst P3 und
startet anschließend die Webapp **mit dem rotierenden Log-Stream**:

```sh
# SMOKEMESH_AUTO_MOUNT
mkdir -p /mnt/mmcblk0p3
mountpoint -q /mnt/mmcblk0p3 || mount -t ext4 /dev/mmcblk0p3 /mnt/mmcblk0p3

# SMOKEMESH_WEB_AUTOSTART
su tc -c '/bin/sh /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh/deploy/picore/start-web.sh' 2>&1 | /mnt/mmcblk0p3/smoke-mesh/venv/bin/python -u /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh/deploy/picore/rotate-web-stream.py --output /mnt/mmcblk0p3/smoke-mesh/logs/web-server.log --max-kb 1024 --keep 5 &
```

Änderungen an `/opt/bootlocal.sh` mit `sudo filetool.sh -b`
persistieren und danach Webserver, Logger, Zeit und Datenbankbackup
prüfen. `/opt/bootsync.sh` setzt den lokalen Hostnamen über
`/usr/bin/sethostname picore`; diese Datei ebenfalls mit
`filetool.sh -b` sichern, falls geändert.


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

### Logger-Start/-Stop im LAN (opt-in)

Die Logger-Buttons werden bei direktem LAN-Zugriff standardmäßig
absichtlich deaktiviert. Für einen einzelnen vertrauenswürdigen
Administrationsrechner in `/mnt/mmcblk0p3/smoke-mesh/data/web.env` setzen:

```sh
SMOKE_LAN_LOGGER_IPS='192.168.98.50'
```

Adresse durch die tatsächliche Client-IP ersetzen; mehrere IPs und
kanonische CIDR-Netze werden kommasepariert unterstützt. Ohne diese
Variable bleibt die Funktion gesperrt. Nach Änderung den Webserver
neu starten, anschließend die Monitorseite neu laden. Der Loggerstatus
ist weiterhin für alle LAN-Clients lesbar; den CSRF-Token erhalten nur
Loopback und freigegebene Client-IP-Adressen. Start/Stop ist bei
OTA-Portreservierung gesperrt (HTTP 409); nur der von der Webapp gestartete
Logger wird beendet. Diese Freigabe gibt **keinen** Zugriff auf OTA,
Release-Uploads oder andere Verwaltungsoperationen.

Die IP-Freigabe plus CSRF-Token ist keine echte Authentisierung. Im
unvertrauenswürdigen Netz stattdessen ausschließlich über einen
SSH-Tunnel auf `127.0.0.1:8088` administrieren.
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


## Tägliches SQLite-Backup (piCore, opt-in)

Die Monitoring-Datenbank liegt unter `web/data/mesh.db` und
verwendet SQLite WAL. Eine laufende Datenbank nicht mit `cp` sichern:
`web/db_backup.py` verwendet stattdessen die SQLite-Online-Backup-API.

Auf dem Pi in der lokalen
`/mnt/mmcblk0p3/smoke-mesh/data/web.env` ergaenzen:

```sh
SMOKE_DB_BACKUP_DIR='/mnt/mmcblk0p3/smoke-mesh/backups/sqlite'
SMOKE_DB_BACKUP_KEEP='7'
```

Mit Neustart des Webservers ist die Sicherung aktiv. Beim Start und
anschliessend stuendlich prueft der Webserver, ob fuer den aktuellen
UTC-Tag bereits `mesh_YYYYMMDD.db` vorhanden ist. Pro UTC-Tag
wird maximal ein konsistentes Backup erstellt. Fehler werden ins
`web-server.log` geschrieben und beim naechsten Lauf erneut versucht.
Bei noch fehlender Quelldatenbank wird die Sicherung nach deren
Erstellung nachgeholt. Backups werden vor Veroeffentlichung mittels
`PRAGMA integrity_check` ueberprueft. Erst nach erfolgreicher
Sicherung werden ueberzaehlige alte Backups geloescht.
Das Backup-Verzeichnis befindet sich ausserhalb des Git-Repos.

Manuelle einmalige Sicherung ohne aktivierten Hintergrundjob:

```sh
cd /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh
. /mnt/mmcblk0p3/smoke-mesh/venv/bin/activate
python - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, 'web')
from db_backup import backup_database
print(backup_database(
    Path('web/data/mesh.db'),
    Path('/mnt/mmcblk0p3/smoke-mesh/backups/sqlite'), keep=7))
PY
```

Pruefung nach Webserver-Neustart:

```sh
ls -lh /mnt/mmcblk0p3/smoke-mesh/backups/sqlite/
grep 'SQLite backup' /mnt/mmcblk0p3/smoke-mesh/logs/web-server.log | tail -5
```

**Wichtig:** Die Sicherungen liegen auf derselben SD-Karte und schuetzen
nur gegen versehentliche Datenbankbeschaedigung bzw. Datenverlust durch
Softwarefehler, nicht gegen einen Defekt der SD-Karte. Ein regelmaessiges
externes Backup ist weiterhin sinnvoll. Keine automatische Datenloeschung
aus `receptions` oder `transmissions`; alte Backup-Dateien werden auf
sieben Generationen begrenzt. Windows bleibt ohne explizite
Konfiguration unveraendert.


## Begrenztes piCore-Webserver-Log

`web-server.log` wird bisher durch `/opt/bootlocal.sh` dauerhaft
als offene Datei beschrieben. Umbenennen/Loeschen der laufenden Datei
mit einem externen Rotator ist deshalb ungeeignet. Unter piCore wird
stattdessen der stdout/stderr-Strom durch
`deploy/picore/rotate-web-stream.py` geleitet. Der kleine Python-Prozess
rotiert die Ausgabedatei bei 1024 KiB und bewahrt die letzten fuenf
abgeschlossenen Generationen auf:
`web-server.log.1` bis `web-server.log.5`.

**Aktiv auf dem Pi:** In
`/opt/bootlocal.sh` ausschliesslich die bestehende Zeile fuer
`SMOKEMESH_WEB_AUTOSTART` ersetzen (Mount und andere Zeilen bleiben):

```sh
su tc -c '/bin/sh /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh/deploy/picore/start-web.sh' 2>&1 | /mnt/mmcblk0p3/smoke-mesh/venv/bin/python -u /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh/deploy/picore/rotate-web-stream.py --output /mnt/mmcblk0p3/smoke-mesh/logs/web-server.log --max-kb 1024 --keep 5 &
```

Die Pipe muss komplett im Hintergrund laufen (abschließendes `&`).
Vor späteren Änderungen `/opt/bootlocal.sh` sichern; danach mit
`sudo filetool.sh -b` dauerhaft speichern und neu starten.
Das alte Log bleibt erhalten und wird beim Erreichen der Größengrenze
rotiert. **Dieser Grenzwert wurde im Dauerbetrieb bisher nicht erreicht;
die Rotation wurde in automatisierten Tests geprüft.** Der Log-Schreiber beendet sich, wenn die Webapp den
Ausgabestrom schliesst.

Nach Reboot kontrollieren:
```sh
ps | grep -E 'rotate-web-stream|web/app.py'
tail -n 15 /mnt/mmcblk0p3/smoke-mesh/logs/web-server.log
ls -lh /mnt/mmcblk0p3/smoke-mesh/logs/web-server.log*
```

Diese Loesung rotiert ausschliesslich den Webserver-Ausgabestrom,
nicht die SQLite-Datenbank oder die separaten Mesh-Rohlogs.


## Nach PR #10: Stand und sichere Updates

[PR #10](https://github.com/lexxi/smoke-listener-mesh/pull/10)
wurde mit Merge-Commit `960ecbefae147ecab04be113adb4b3e8601cf0a4`
nach `main` übernommen. Der Pi-Checkout kann nach einem Statuscheck
vom bisherigen Feature-Branch auf `main` umgestellt werden:

```sh
cd /mnt/mmcblk0p3/smoke-mesh/app/smoke-listener-mesh
git status -sb
git fetch origin
# Nur wenn keine lokalen Änderungen vorhanden sind:
git switch main
git pull --ff-only origin main
. /mnt/mmcblk0p3/smoke-mesh/venv/bin/activate
python -m unittest discover -s tests -p 'test_*.py'
```

Die lokalen Pi-Dateien `web/data/gateways.pi.json` und `web.env`
bleiben außerhalb der versionierten Konfiguration. Windows-Arbeitsstände
mit lokal geänderten Firmware-Headern oder `config/nodes.csv` nicht
blind mit `git pull` überschreiben.

**Noch nicht abgeschlossen:** Pi-Remote-OTA/Signaturprüfung in Hardware,
externe SQLite-Sicherung, Rotation beim echten Größenlimit und
vollständige Sicherheitsvalidierung der Rauchalarmkette.
