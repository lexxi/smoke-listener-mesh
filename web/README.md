# Smoke Mesh Webapp (Windows, Stand 05.11.2026)

Lokales Flask-Dashboard für das ESP32-C3 Smoke Listener Mesh mit
Knoten- und Gateway-Verwaltung, USB-Logger und signierter Remote-OTA-
Releaseverwaltung. **Experimentelles Projekt; kein Ersatz für eine
zertifizierte Rauchwarn- oder Brandmeldeanlage.**

## Schnellstart

Im Repository-Stammverzeichnis mit der bestehenden Python-Umgebung:

```powershell
git switch main
git pull --ff-only
python -m pip install -r .\web\requirements.txt
python .\web\app.py
```

Der Server ist unter **http://127.0.0.1:8088** erreichbar.

| Seite | Zweck |
| --- | --- |
| `/` | Monitor: Knoten, Verbindungsstatus, Empfang, Relay-Wege und Log-Testläufe |
| `/nodes` | Discover, Gerätebefehle, Inventar/Standort, OTA-Freigabe, Gateway-Verwaltung |
| `/ota` | Signierte Firmware-Releases hochladen, prüfen und kontrolliert verteilen |

**Der Logger auf COM16 wird von der Webapp automatisch gestartet.**
`scripts/logging.py` daher **nicht parallel** auf COM16 ausführen.
Auch Arduino Serial Monitor und andere Programme dürfen den Port nicht
gleichzeitig belegen. Wird der Logger bewusst gestoppt, kann er im
Dashboard manuell wieder gestartet werden.

## Logger- und Verbindungsstatus

Der Logger-Prozess führt bei Unterbrechung der USB-Verbindung selbstständig
Wiederholungsversuche aus (standardmäßig alle fünf Sekunden). Im Dashboard
werden die Zustände **Verbunden**, **Verbindung wird aufgebaut**,
**Nicht verbunden** und **Gestoppt** unterschieden.

Eine aktive PID allein bedeutet **nicht**, dass der C3 angeschlossen ist.
Bei fehlender Verbindung erscheint eine Warnung, dass die Knotenstatusdaten
nicht aktuell sind. Nach Wiederanstecken sollte die Verbindung ohne
manuellen Neustart zurückkehren. **Verbunden** bedeutet nur, dass COM16
geöffnet wurde, nicht, dass die C3-Identität geprüft ist.

Während Remote-STATUS, Gerätebefehlen oder OTA über den Logger-Gateway
pausiert die Webapp ihren eigenen Logger, reserviert den COM-Port und
startet den Logger nach Ende bei Bedarf neu. Fremde Prozesse werden nicht
beendet.

## Knotenverwaltung

1. Unter `/nodes` **Discover / Aktualisieren** wählen.
2. Knoten anhand der Node-ID markieren.
3. **Name im Inventar**, **Standort** und bei Bedarf **OTA-Freigabe**
   setzen und **Knoten speichern** wählen.
4. Falls auch der Gerätename geändert werden soll, separat **NAME SET**
   ausführen und die Rückmeldung prüfen.

**Discover zeigt zuvor empfangene authentifizierte Mesh-Knoten, keine
aktive Netzwerksuche.** Inventarname und Standort stehen in
`config/nodes.csv`. OTA-Freigaben stehen in
`web/data/node_targets.json`. Maximal fünf OTA-Empfänger sind zulässig.
Ein neuer Knoten benötigt ein neu signiertes Firmware-Bundle mit seinem
eigenen Manifest. Der Geräte-NVS-Name wird noch **nicht automatisch**
beim Speichern des Inventars gesetzt.

**Standort ändern:** Das funktioniert ohne Firmware-Update, auch bei
Küche und Garage; beide sind Mesh-Knoten und OTA-Empfänger.
Der dedizierte COM16-Gateway darf nicht als OTA-Empfänger registriert
werden.

## Gateway-Einstellungen

Die Standardkonfiguration verwendet nur den dedizierten
**Gateway COM16** (Node-ID `00000CEC7E6E27AC`). Küche/COM12 und
Garage/COM14 wurden als *USB-Gateways* entfernt, bleiben als
reguläre Mesh-Knoten erhalten.

Unter `/nodes` → **USB-Gateways verwalten** lassen sich weitere
USB-Gateways (Port, Name, Node-ID) hinzufügen und entfernen.
Einstellungen werden in `web/data/managed_gateways.json` geschrieben.
**Erst nach einem vollständigen Webapp-Neustart werden sie aktiv.**
Der dedizierte COM16-Logger bleibt geschützt.

Der Standard-Gateway für Remote-Management und OTA kann auf `/nodes`
oder `/ota` ausgewählt und mit **Als Standard-Gateway speichern**
dauerhaft unter `web/data/gateway_preferences.json` gespeichert werden.
Diese Auswahl ändert **nicht** den physischen Logger-Port.

Ein neu konfigurierter Gateway muss von der Firmware der Zielknoten
bereits als Management-Sender akzeptiert werden. Webapp-Einstellungen
ändern keine auf dem ESP32 gespeicherten Vertrauensanker.

## Releases und OTA

Signierte Releases werden über `/ota` geprüft und in
`web/data/releases/` gespeichert. Der Upload prüft u. a.
Signatur, Firmwareformat, SHA-256 und das Manifest.
Neue signierte Bundles können bis zu fünf individuell berechtigte
Empfänger enthalten. Die Firmware-Profile `0.6.16.a` bis
`0.6.16.h` werden über
`tools/ota/build-release-matrix.ps1` erstellt.

Eine OTA-Freigabe allein erzeugt noch kein Manifest. Nach dem
Hinzufügen eines neuen Knotens ein passendes Paket **neu signieren**.
Bei jedem Update Ziel, Gateway, Firmwareversion sowie Boot- und
Mesh-Bestätigung kontrollieren. Ein OTA-Erfolg beweist **nicht**,
dass Mikrofon oder Alarmdetektion funktionieren.

## Monitor und Log-Dateien

- Logger schreibt in `log/mesh_*.log`; ältere Dateien aus `logs/`
  und `scripts/log/` werden ebenfalls gelesen.
- **Online**: letztes empfangenes Paket ≤45 s,
  **Überfällig**: ≤120 s, danach **Offline**.
  Bei gestopptem/nicht verbundenem Logger sind diese Anzeigen nicht
  als aktueller Gesundheitsstatus belastbar.
- Firmware, authentifizierter Knotenname, MAC, Inventarstandort,
  Paketanzahlen, Relay-Hops und RSSI des **letzten Funk-Hops**.
- Getrennte Testläufe je Logdatei; über die Auswahl lassen sich alte
  Logs ansehen. Archivdaten sind kein historischer Live-Status.
- Auswertung in `web/data/mesh.db` (lokale SQLite-Datenbank).
  Laufzeitdaten unter `web/data/` werden nicht in Git versioniert.

Weitere Verzeichnisse als Logquelle:
```powershell
python .\web\app.py --log-dir C:\Pfad\Zu\Logs
```

## Tests und Sicherheitsgrenzen

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Der Webserver bindet standardmäßig an `127.0.0.1` und hat **keine
Benutzeranmeldung**. Nicht ungeschützt ins Internet stellen.
API-Aufrufe für Änderungen setzen zusätzlich lokalen Zugriff und
CSRF-Token voraus; das ersetzt keine Benutzeranmeldung.

Ein Mesh-HEARTBEAT bestätigt nur empfangene Funktelemetrie. RSSI gehört
zum letzten Funk-Hop und Via-MAC ist kein vollständiger Routenverlauf.
Das System ist keine zertifizierte Sicherheitsanlage.

**Ausführliche Schritt-für-Schritt-Anleitung:**
[Webapp – Knotenregistrierung und Gateway-Start](../docs/web-node-registration.md).

**Historische OTA-Migration:** [Remote-OTA v0.6.11/0.6.12](../docs/remote-ota-one-time-usb-migration.md)
beschreibt frühere Entwicklungsstände und ist keine aktuelle
Schritt-für-Schritt-Installationsanleitung.
