# Smoke Listener Mesh

Experimentelles Mesh-System auf **ESP32-C3 SuperMini** zur zusätzlichen
akustischen Erkennung der Pieptöne unveränderter Rauchwarnmelder. Das Projekt
kombiniert Mikrofon-Prototypen, authentifizierte ESP-NOW-Telemetrie,
Mesh-Weiterleitung, einen dedizierten USB-Gateway und eine lokale
**plattformübergreifende Webapp (Windows/piCore) für Knotenverwaltung und signierte Remote-Firmwareupdates**.

> **Sicherheit:** Keine zertifizierte Brandmeldeanlage, kein Rauchwarnmelder
> und kein Ersatz für normgerechte Rauchwarnmelder. HEARTBEAT, OTA-Erfolg
> und ein „Online“-Status bestätigen weder die korrekte akustische
> Alarmerkennung noch einen Brandalarm. Rauchwarnmelder nicht verändern.
> Die Mikrofon-Alarmdetektion ist noch nicht als vollständiges
> sicherheitsrelevantes Gesamtsystem validiert.

## Aktueller Projektstand (07.11.2026)

| Bereich | Aktueller Stand |
| --- | --- |
| Geräte | ESP32-C3 SuperMini; ein dedizierter USB-Gateway sowie mehrere Mesh-Empfänger |
| Firmware | Produktivknoten überwiegend **0.6.16.h**; Testknoten **0.6.20.b**, USB-Gateway **0.6.20.c**. **v0.6.21** für Remote-Audio-Diagnose implementiert, noch nicht gebaut/getestet |
| Mesh | ESP-NOW, HMAC-geschützte Pakete, Heartbeats, Relay/TTL und Duplikatunterdrückung |
| Akustik | INMP441-basierte Ton-/Piepsdiagnostik erprobt; komplette Alarmkette noch nicht validiert |
| Remote-Verwaltung | STATUS, NAME GET/SET/RESET, RESTART, signierte Remote-OTA; Buzzer-Test und 2×2 erfolgreich über LAN-Webapp; AUDIO_STATUS/RESET ab v0.6.21 vorbereitet |
| Dedizierter Gateway | Node-ID `00000CEC7E6E27AC`, auf piCore über `/dev/serial/by-id/...` angebunden, vom Webserver verwalteter USB-Logger |
| Webapp | **Dashboard v0.4.0** (Flask/Waitress): Windows und piCore, Discover, Inventar/Standort, Gateway/Logger, Releases |
| OTA | Zielgebundene, signierte Firmwaremanifeste; maximal **fünf** freigegebene Empfänger neben dem USB-Gateway |
| Nachgewiesen | piCore: signierte Remote-OTA auf Testknoten, Gateway-USB-Flash, Buzzer-Test und 2×2 über normale LAN-Webapp mit bestätigter ESP-NOW-Antwort |
| Noch offen | v0.6.21-Build/Signatur- und Hardwaretest für AUDIO_STATUS/RESET, Audiokette/Alarmweiterleitung, Batterie, externe Sicherung/Rotation unter Grenzwertbedingungen |

**Die aktuellen Bedienanleitungen sind:**

- [Webapp – Windows-Schnellstart, Knoten und Gateway](web/README.md)
- [piCore – Installation, Boot, LAN-Freigabe, Rotation und SQLite-Backup](docs/cross-platform-picore-web.md)
- [Knotenregistrierung, USB-Logger, Gateway-Verwaltung und Tests](docs/web-node-registration.md)
- [Hardware und INMP441-Verdrahtung](docs/hardware.md)
- [Signierte Releases und Sicherheitsgrundlagen](docs/ota-signing.md)
- [Remote-Buzzer-Diagnose v0.6.20 – erfolgreicher Hardwaretest](docs/remote-buzzer-diagnostics-v0.6.20.md)
- [Remote-Audio-Diagnose v0.6.21 – Umsetzung und Testplan](docs/remote-audio-diagnostics-v0.6.21.md)

Ältere Dokumente und Firmwarestände bleiben als **Entwicklungsarchiv**
im Repository. Frühere Texte zu v0.5.5 sowie zu den ersten Remote-OTA-
Tests v0.6.11/v0.6.12 sind keine aktuellen Rollout-Anweisungen.

## Schnellstart: Webapp unter Windows

Im bestehenden Repository mit aktiver Python-Umgebung:

```powershell
cd C:\pyprojects\smoke-listener-mesh
git switch main
git pull --ff-only
python -m pip install -r .\web\requirements.txt
python .\web\app.py
```

Die Webapp läuft standardmäßig unter **http://127.0.0.1:8088**.

| Seite | Funktion |
| --- | --- |
| [Monitor](http://127.0.0.1:8088/) | Zustand des USB-Loggers, Mesh-Knoten, Logs und Relay-Statistik |
| [Knotenverwaltung](http://127.0.0.1:8088/nodes) | Discover, Name, Standort, OTA-Freigabe und Gateway-Einstellungen |
| [Firmware / OTA](http://127.0.0.1:8088/ota) | Signierte Releases hochladen, prüfen und verwalten |

**Neu seit PR #4:** Der Webserver startet den **COM16-Logger automatisch**.
Bitte **keinen zweiten Logger oder Arduino Serial Monitor parallel**
an COM16 öffnen. Während einer Remote-Aktion über COM16 pausiert die
Webapp ihren Logger kontrolliert und startet ihn anschließend wieder,
sofern er zuvor lief.

Die Anzeige unterscheidet:

- **Verbunden:** serieller COM-Port erfolgreich geöffnet.
- **Verbindung wird aufgebaut:** Prozess läuft, aber COM-Verbindung
  noch nicht bestätigt.
- **Nicht verbunden:** COM-Port fehlt/ist unterbrochen; der Logger
  versucht die Wiederverbindung automatisch.
- **Gestoppt:** kein laufender von der Webapp verwalteter Logger.

**PID bedeutet nicht automatisch USB-Verbindung.** Wenn der C3
ausgesteckt ist, bleibt der Python-Prozess im Reconnect-Modus aktiv.
Die Webapp warnt in diesem Fall, dass Knotenstatusdaten nicht aktuell
sind. Eine erfolgreiche COM-Verbindung bestätigt noch nicht
kryptografisch die Identität des angesteckten ESP32.

## piCore (Raspberry Pi 2) – Betrieb seit PR #10

Seit [PR #10](https://github.com/lexxi/smoke-listener-mesh/pull/10)
ist die gemeinsame Webapp in `main`. Der Raspberry Pi 2 mit piCore
17.0.1 betreibt den USB-Gateway unter dem Hostnamen `picore` und stellt
das Dashboard im vertrauenswürdigen LAN unter
`http://picore:8088` bzw. `http://192.168.98.39:8088` bereit.
`picore` muss dafür per DNS auflösbar sein.

Die Pi-Konfiguration liegt **außerhalb von Git** in
`/mnt/mmcblk0p3/smoke-mesh/data/web.env`. Die Gateway-JSON kann über
`SMOKE_GATEWAYS_FILE` auf den stabilen Linux-Gerätepfad unter
`/dev/serial/by-id/` verweisen. Unter Windows bleibt `COM16` der
unveränderte Standard.

Im LAN sind STATUS und NAME_GET möglich. `NAME_SET`, `NAME_RESET`
und `RESTART` erfordern eine explizite Freigabe über
`SMOKE_LAN_NODE_ADMIN_IPS`, wahlweise einzelne IPv4/IPv6-Adressen,
CIDR-Netze oder beides. Diese IP-basierte Erlaubnis ist **keine
Benutzeranmeldung**. Registry-Schreibzugriffe, Loggersteuerung, Uploads
und Remote-OTA werden dadurch nicht freigeschaltet.

Für piCore sind optional eingerichtet: Rohlog-Rotation (10 MiB),
Aufbewahrung (30 Tage/512 MiB), Webserver-Logrotation (1 MiB plus
fünf Generationen), tägliches konsistentes SQLite-Backup
(sieben Tagesstände). Die Backup-Dateien liegen aktuell auf derselben
SD-Karte und sind deshalb kein Ersatz für ein externes Backup.
Der Webserver wird mit Waitress über `/opt/bootlocal.sh` gestartet.
**Die Logrotation beim tatsächlichen Grenzwert und Remote-OTA unter
piCore sind noch nicht praktisch validiert.**

Siehe die [vollständige piCore-Betriebsanleitung](docs/cross-platform-picore-web.md).

## Knoten registrieren und Standort pflegen

1. `/nodes` öffnen und **Discover / Aktualisieren** wählen.
2. Den Knoten anhand seiner **Node-ID** auswählen.
3. **Name im Inventar** und **Standort** eintragen; optional
   **Für signierte OTA-Updates freigeben**.
4. **Knoten speichern**. Nach Neuladen der Seite die Werte prüfen.

**Discover zeigt bereits empfangene authentifizierte Mesh-Knoten**
und ist keine aktive Suche im Funknetz. Die Webapp speichert
Inventarname und Standort in `config/nodes.csv`, die Freigaben in
`web/data/node_targets.json`.

**Gerätename und Inventarname sind unterschiedliche Werte:**
Bei einer **neuen Registrierung** kann der Inventarname optional gleich per **NAME SET**
im NVS gespeichert werden. Die Webapp prüft die NAME-GET-Bestätigung; bei
bestehenden Knoten bleibt die Option standardmäßig aus, damit eine reine
Standortänderung keinen Gerätebefehl auslöst. NAME GET, NAME RESET, Funkstatus und Neustart sind
ebenfalls über die Knotenverwaltung verfügbar. Die kombinierte Registrierung mit NAME SET ist im Feature-Branch
`feature/web-registration-name-set` implementiert, aber noch **nicht
auf Hardware getestet oder nach main gemergt**.

Der Standort kann jederzeit ohne Flashen geändert werden – auch bei
**Küche** und **Garage**. Beide bleiben als reguläre Mesh-Knoten und
OTA-Empfänger erhalten.

## Gateway-Verwaltung

| Voreingestellter Gateway | Port | Node-ID |
| --- | --- | --- |
| Dedizierter USB-Logger und Management-Gateway | **COM16** | `00000CEC7E6E27AC` |

Die früheren USB-Gateway-Einträge **Küche/COM12** und
**Garage/COM14** wurden aus der Standardliste entfernt.
Das hat **keinen Einfluss auf deren Mesh- oder OTA-Rolle**.

Unter `/nodes` → **USB-Gateways verwalten** kannst du zusätzliche
USB-Gateways mit COM-Port, Name und Node-ID hinterlegen oder entfernen.
Die Konfiguration wird lokal in
`web/data/managed_gateways.json` gespeichert. **Zum Aktivieren dieser
Änderungen die Webapp vollständig neu starten.** Der dedizierte
COM16-Gateway ist gegen versehentliches Löschen geschützt.

Unter `/nodes` oder `/ota` lässt sich der **Standard-Gateway für
Remote-Verwaltung** mit **Als Standard-Gateway speichern** festlegen.
Die Präferenz wird in `web/data/gateway_preferences.json`
abgelegt und ist nach dem nächsten Seitenaufruf wirksam.
**Sie verändert nicht den Logger-Port COM16.**

Eine Gateway-Zuordnung in der Webapp stellt **keine**
Firmware-Vertrauensstellung her: Ziel-C3 müssen den jeweiligen
Management-Sender bereits akzeptieren. Daher kann ein älterer C3
(z. B. v0.6.15.h) auf Anfragen des neuen dedizierten Gateways mit
`TIMEOUT no_reply` reagieren; dies wurde durch Aktualisierung
auf `0.6.16.h` beim neuen Knoten behoben.

## Firmware, Feature-Matrix und Remote-OTA

Die **v0.6.16**-Buildmatrix enthält acht Profile:

| Suffix | Profil |
| --- | --- |
| `.a` | core |
| `.b` | audio |
| `.c` | gateway |
| `.d` | hybrid |
| `.e` | core + Config-AP |
| `.f` | audio + Config-AP |
| `.g` | gateway + Config-AP |
| `.h` | hybrid + Config-AP |

Build-/Signierwerkzeug (Windows/PowerShell):

```powershell
.\tools\ota\build-release-matrix.ps1 -Version 0.6.16
```

Das Skript setzt Arduino CLI, die erforderlichen **lokalen privaten
Firmware-Header** und für signierte Releases einen privaten
Signierschlüssel voraus. **Es flasht die Geräte nicht automatisch.**
Die Runtime-Liste der Empfänger steht in
`web/data/node_targets.json` (maximal fünf).
Ein zusätzlich freigegebener Knoten benötigt ein **neu signiertes**
Release-Bundle mit einem Manifest für seine Node-ID; die
Registrierung verändert ältere ZIP-Dateien nicht rückwirkend.

Die Webapp kann signierte Pakete prüfen, lokal ablegen sowie
Remote-STATUS, Staging, Aktivierung und OTA-Workflows durchführen.
Ein signiertes Update ersetzt **keinen** Test der Alarmdetektion.
Private Signierschlüssel, `mesh_secrets.h` und sonstige Geheimnisse
niemals auf GitHub hochladen.

Für technische Details und ältere Protokoll-/Migrationstests siehe
[OTA-Roadmap](docs/mesh-ota.md) und die
[historische Remote-OTA-Migration v0.6.11](docs/remote-ota-one-time-usb-migration.md).
Diese älteren Anleitungen können inzwischen überholte Port-,
Firmware- und Teststatusangaben enthalten.

## Hardware

Aktuelle Prototypen nutzen ESP32-C3 SuperMini und
**INMP441 (I²S)**. In der bestehenden Verdrahtung:

| INMP441 | ESP32-C3 |
| --- | --- |
| SCK | GPIO6 |
| WS | GPIO3 |
| SD | GPIO10 |
| L/R | GND |
| VDD | 3V3 |
| GND | GND |

Buzzer, 18650-Versorgung, geeigneter Spannungsregler,
Batteriemessung und Gehäuse sind weitere Hardwarearbeiten.
**Eine 18650-Zelle darf nicht direkt an den 3V3-Pin angeschlossen
werden.** Details: [Hardware-Dokumentation](docs/hardware.md).

## Logs, Status und Tests

Der automatisch verwaltete Logger schreibt in `log/mesh_*.log`;
die Webapp liest außerdem ältere Logs aus `logs/` und
`scripts/log/`. Die Datenbank befindet sich unter
`web/data/mesh.db`. `web/data/` ist von Git ausgeschlossen.

- **Online:** authentifiziertes Paket innerhalb von 45 Sekunden.
- **Überfällig:** letztes Paket vor 46–120 Sekunden.
- **Offline:** letztes Paket älter als 120 Sekunden.
- **RSSI:** der *letzten Funkstrecke*, nicht garantiert des Quellknotens.
- **Relay:** der letzte beobachtete Sender, kein vollständiger
  Ende-zu-Ende-Pfad.
- **Testlauf:** Statistiken beziehen sich auf die ausgewählte Logdatei.

Bei gestopptem oder getrenntem Logger dürfen diese Zeiten nicht als
zuverlässiger aktueller Knotenstatus interpretiert werden.

Regressionstests:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Windows/COM16-Funktionen wurden in [PR #4](https://github.com/lexxi/smoke-listener-mesh/pull/4)
übernommen. Die gemeinsame Windows/piCore-Codebasis wurde nach 97
Windows-Regressionstests und erfolgreichem Windows-Remote-STATUS
sowie den piCore-Funktionstests am 07.11.2026 mit
[PR #10](https://github.com/lexxi/smoke-listener-mesh/pull/10)
nach `main` übernommen.

## Sicherheitsgrenzen und offene Arbeiten

Die Webapp bindet standardmäßig nur an `127.0.0.1`.
**Keine Benutzeranmeldung vorhanden:** der Pi ist im vertrauenswürdigen
LAN ohne Login erreichbar. Einzelne Knotenbefehle sind dort nur per
IP-/CIDR-Freigabe erlaubt. Diese Prüfung und CSRF ersetzen keine
Benutzerauthentisierung. **Keine Portweiterleitung ins Internet.**

**Offen:** Hardwaretest und Merge der kombinierten Namensübernahme bei Registrierung;
Identitätsprüfung des angesteckten USB-Gateways; vollständige
End-to-End-Validierung der akustischen Erkennung und Alarmweiterleitung;
Stromversorgung/Batterielaufzeit, Buzzer und Gehäuse.

Historische Versuche und Quellstände bleiben unter `docs/` und
`firmware/` dokumentiert. Sie sind nützlich zur Fehlersuche, aber
nicht automatisch eine sichere Anleitung für die aktuelle Version.
