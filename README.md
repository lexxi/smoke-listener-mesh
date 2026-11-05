# Smoke Listener Mesh

Experimentelles Mesh-System auf **ESP32-C3 SuperMini** zur zusätzlichen
akustischen Erkennung der Pieptöne unveränderter Rauchwarnmelder. Das Projekt
kombiniert Mikrofon-Prototypen, authentifizierte ESP-NOW-Telemetrie,
Mesh-Weiterleitung, einen dedizierten USB-Gateway und eine lokale
**Windows-Webapp für Knotenverwaltung und signierte Remote-Firmwareupdates**.

> **Sicherheit:** Keine zertifizierte Brandmeldeanlage, kein Rauchwarnmelder
> und kein Ersatz für normgerechte Rauchwarnmelder. HEARTBEAT, OTA-Erfolg
> und ein „Online“-Status bestätigen weder die korrekte akustische
> Alarmerkennung noch einen Brandalarm. Rauchwarnmelder nicht verändern.
> Die Mikrofon-Alarmdetektion ist noch nicht als vollständiges
> sicherheitsrelevantes Gesamtsystem validiert.

## Aktueller Projektstand (05.11.2026)

| Bereich | Aktueller Stand |
| --- | --- |
| Geräte | ESP32-C3 SuperMini; ein dedizierter USB-Gateway sowie mehrere Mesh-Empfänger |
| Firmware | **v0.6.16**, Build-Profile `a`–`h`; Kombinationen aus Core, Audio, Gateway und Config-AP |
| Mesh | ESP-NOW, HMAC-geschützte Pakete, Heartbeats, Relay/TTL und Duplikatunterdrückung |
| Akustik | INMP441-basierte Ton-/Piepsdiagnostik erprobt; komplette Alarmkette noch nicht validiert |
| Remote-Verwaltung | STATUS, NAME GET/SET/RESET, RESTART und Remote-OTA über einen autorisierten Gateway |
| Dedizierter Gateway | **COM16**, Node-ID `00000CEC7E6E27AC`, vom Webserver verwalteter USB-Logger |
| Webapp | Flask-Dashboard: Discover, Inventar/Standort, OTA-Freigabe, Gateway-Einstellungen, Loggerstatus, Firmware-Releases |
| OTA | Zielgebundene, signierte Firmwaremanifeste; maximal **fünf** freigegebene Empfänger neben dem USB-Gateway |
| Nachgewiesen | Knotenregistrierung, Standortänderung, COM16-Verwaltung, Logger-Reconnect und die Webapp-Funktionen aus PR #4 in der Windows-Testinstallation |
| Noch offen | Automatische Übernahme des Inventarnamens per NAME SET, vollständige Alarm-/Mikrofonvalidierung, Batterie- und Buzzer-Integration |

**Die aktuellen Bedienanleitungen sind:**

- [Webapp / Windows – Schnellstart, Knoten und Gateway](web/README.md)
- [Knotenregistrierung, USB-Logger, Gateway-Verwaltung und Tests](docs/web-node-registration.md)
- [Hardware und INMP441-Verdrahtung](docs/hardware.md)
- [Signierte Releases und Sicherheitsgrundlagen](docs/ota-signing.md)

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
Der echte ESP32-Gerätename wird derzeit noch separat mit **NAME SET**
im NVS geändert. NAME GET, NAME RESET, Funkstatus und Neustart sind
ebenfalls über die Knotenverwaltung verfügbar. Automatisches NAME SET
beim Registrieren ist als nächste Funktion vorgesehen, aber **noch
nicht implementiert**.

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

Die neuen Webapp- und COM16-Funktionen wurden am **05.11.2026**
mit der Windows-Testinstallation geprüft und in
[PR #4](https://github.com/lexxi/smoke-listener-mesh/pull/4)
nach `main` übernommen.

## Sicherheitsgrenzen und offene Arbeiten

Die Webapp bindet standardmäßig nur an `127.0.0.1`.
**Keine Benutzeranmeldung vorhanden:** nicht ungeschützt ins
LAN oder Internet stellen. Für Schreibaktionen bestehen zusätzliche
lokale Zugriffs- und CSRF-Prüfungen, aber das ersetzt keine
Benutzerauthentisierung.

**Offen:** automatische Namensübernahme beim Registrieren;
Identitätsprüfung des angesteckten USB-Gateways; vollständige
End-to-End-Validierung der akustischen Erkennung und Alarmweiterleitung;
Stromversorgung/Batterielaufzeit, Buzzer und Gehäuse.

Historische Versuche und Quellstände bleiben unter `docs/` und
`firmware/` dokumentiert. Sie sind nützlich zur Fehlersuche, aber
nicht automatisch eine sichere Anleitung für die aktuelle Version.
