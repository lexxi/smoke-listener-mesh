# Webapp: Knotenverwaltung, Gateway und Logger (Stand 07.11.2026)

Die Windows-Grundfunktionen sind seit **PR #4** in `main`.
Die gemeinsame Windows-/piCore-Webapp wurde mit
[PR #10](https://github.com/lexxi/smoke-listener-mesh/pull/10)
gemergt; Windows-Regression: 97 Tests OK und STATUS über COM16 geprüft.
Die piCore-spezifischen Schritte stehen in der
[piCore-Anleitung](cross-platform-picore-web.md). Die aktuellen Seiten:

- [Monitor](http://127.0.0.1:8088/) – Knotenstatus, USB-Logger und Empfangslogs
- [Knotenverwaltung](http://127.0.0.1:8088/nodes) – Discover, Gerätebefehle, Stammdaten und Gateways
- [Firmware / OTA](http://127.0.0.1:8088/ota) – signierte Releases und Remote-OTA

> **Sicherheit:** Entwicklungs- und Testsystem, keine zertifizierte Brandmelde-
> oder Alarmierungsanlage. Funk-HEARTBEATs beweisen nicht die Funktion des
> Rauchwarnmelders oder der akustischen Detektion.

## 1. Windows-Start

Im Repository-Stammverzeichnis und in der bestehenden Python-Umgebung:

```powershell
git switch main
git pull --ff-only
python -m pip install -r .\web\requirements.txt
python .\web\app.py
```

Standardadresse: `http://127.0.0.1:8088`. Der Webserver startet den
konfigurierten **COM16-Logger automatisch**; keinen zweiten Logger oder
Arduino Serial Monitor parallel an COM16 öffnen. Der manuelle Logger
`python scripts/logging.py --port COM16` ist nur für unabhängige
Diagnoseläufe gedacht, **wenn die Webapp den Port nicht nutzt**.

Beim Start wird der Logger-Prozess mit eigener PID erzeugt. Die Oberfläche
unterscheidet zusätzlich den **seriellen Verbindungszustand**:

| Anzeige | Bedeutung |
| --- | --- |
| **Verbunden** | Der Logger hat den COM-Port erfolgreich geöffnet |
| **Verbindung wird aufgebaut** | Logger-Prozess läuft; die serielle Verbindung ist noch nicht bestätigt |
| **Nicht verbunden** | Verbindung fehlgeschlagen oder unterbrochen; automatischer Wiederholungsversuch |
| **Gestoppt** | Kein von der Webapp verwalteter Logger-Prozess |
| **Für OTA reserviert** | COM16 ist vorübergehend für einen Remote-Management-/OTA-Vorgang reserviert |

Eine **PID allein ist kein Verbindungsnachweis**. Der Logger versucht bei
USB-Unterbrechung standardmäßig alle fünf Sekunden die Verbindung wieder
aufzubauen. Beim Wiederanstecken des C3 ist normalerweise kein Webapp-
Neustart nötig. „Verbunden“ beweist lediglich, dass der COM-Port geöffnet
werden konnte, nicht, dass die Geräteidentität kryptografisch geprüft wurde.

Solange die serielle Verbindung fehlt, sind Online-/Überfällig-/Offline-
Anzeigen nicht als **aktueller Mesh-Zustand** belastbar. Das Dashboard zeigt
dafür eine Warnung; Empfangs- und historische Logs bleiben verfügbar.

## 2. Knoten erkennen und registrieren

1. In der Knotenverwaltung **Discover / Aktualisieren** anklicken.
2. Den neuen Knoten anhand seiner **Node-ID** auswählen.
3. Unter **Knoten registrieren** den **Inventarnamen** und **Standort**
   eintragen und, falls gewünscht, **Für signierte OTA-Updates freigeben**.
4. **Knoten speichern** anklicken. Danach Seite neu laden und gespeicherte
   Werte prüfen.

**Discover ist keine aktive Funksuche.** Es zeigt Knoten, die bereits in
authentifizierten Mesh-Logs vorkommen. Ein frisch geflashter C3 muss zunächst
empfangen werden.

| Feld | Speicherort | Auswirkung |
| --- | --- | --- |
| Name im Inventar | `config/nodes.csv` | Bezeichnung im Dashboard |
| Standort | `config/nodes.csv` | Standort-/Raumzuordnung; ohne Firmwareänderung editierbar |
| OTA-Freigabe | `web/data/node_targets.json` | Aufnahme in die lokale Liste der signierbaren OTA-Empfänger |
| Gerätename | NVS im ESP32-C3 | Separat per **NAME SET** setzen; über authentifizierte Meldungen übertragener Name |

Die **Inventarbezeichnung ist nicht automatisch der Firmware-Gerätename**.
Im neuen Feature-Branch wird bei einer Registrierung mit gesetzter NAME-SET-
Option zusätzlich der Gerätename übertragen. Bei existierenden Einträgen
bleibt die Option standardmäßig aus, damit eine Standortkorrektur keinen
Fernbefehl auslöst. **Scheitert NAME SET, bleiben die gespeicherten
Inventardaten unverändert.** In `main` ist NAME SET bis zum Merge des
Feature-Branches noch separat auszuführen. **NAME GET**, **NAME
RESET**, **Funkstatus** und **Neustart** sind eigene Remote-Befehle.
Eine automatische Namensübernahme bei Registrierung ist noch offen.

**Standort ändern:** Knoten (z. B. Küche) in Discover auswählen, nur
`Standort` ändern, die bestehende OTA-Freigabe unverändert lassen und
speichern. Das funktioniert auch bei Knoten, die früher zusätzlich als
USB-Gateway eingetragen waren.

Maximal **fünf OTA-Empfänger**, zusätzlich zum dedizierten Gateway.
Die OTA-Liste ist eine **Freigabeliste**, kein Ersatz für
signierte Manifeste. Nach Registrierung eines neuen Empfängers enthalten
bereits signierte ZIP-Pakete **noch kein Manifest für diesen Knoten**;
ein neues signiertes Bundle muss erstellt werden.

`config/nodes.csv` gehört aktuell zum Repository: Änderungen über die
Webapp können deshalb `git status` als geänderte Datei erscheinen lassen.
`web/data/` ist dagegen von Git ausgeschlossen. Vor `git pull` lokale
Änderungen prüfen und nicht blind verwerfen.

## 3. USB-Gateways verwalten

Aktuelle Standardkonfiguration:

| Gateway | Node-ID | Verwendung |
| --- | --- | --- |
| **COM16 – Gateway** | `00000CEC7E6E27AC` | Dedizierter USB-Logger und Management-/OTA-Gateway |

**COM12/Küche** und **COM14/Garage** sind standardmäßig **nicht mehr**
als USB-Gateways konfiguriert. Küche und Garage bleiben aber normale
Mesh-Knoten und OTA-Ziele; ihre Standortverwaltung wird nicht gesperrt.

Unter **Knotenverwaltung → USB-Gateways verwalten** können zusätzliche
USB-Gateways mit **COM-Port**, **Name** und **16-stelliger Node-ID** angelegt
oder entfernt werden. Der dedizierte COM16-Logger ist vor dem Löschen
geschützt. Die Webapp speichert diese Konfiguration in:

```text
web/data/managed_gateways.json
```

**Nach Änderungen muss die gesamte Webapp neu gestartet werden.**
Die laufende Konfiguration wechselt nicht mitten in einem OTA-Job. Die
Ausgangskonfiguration steht in `web/gateways.json`.

Den **Standard-Gateway für Remote-Aktionen** unter **Knotenverwaltung**
oder **Firmware / OTA** auswählen und **Als Standard-Gateway speichern**
anklicken. Diese Auswahl wird separat in
`web/data/gateway_preferences.json` abgelegt, ist ohne Neustart wirksam
und ändert **nicht** den physischen USB-Logger-Port.

**Wichtig:** Eine Webapp-Zuordnung autorisiert einen Gateway nicht in
der Firmware anderer C3. Der Zielknoten muss dessen Management-Identität
bereits als vertrauenswürdig akzeptieren. Für den dedizierten COM16-
Gateway wurde dies mit Firmware `0.6.16.h` praktisch getestet. Ein
älterer Knoten mit `0.6.15.h` kann deshalb trotz erfolgreichem Discover
auf Remote-STATUS mit `TIMEOUT no_reply` reagieren; dann ist der
Firmware-Vertrauensstand zu prüfen.

## 4. Remote-Management und OTA

Bei Remote-STATUS, NAME-Befehlen oder einem OTA-Vorgang über COM16 wird
der von der Webapp verwaltete Logger pausiert und der Port für den Job
reserviert. Anschließend wird der zuvor laufende Logger wieder gestartet.
Die Webapp beendet dabei **keine fremden seriellen Programme**.

Unter `/ota` werden signierte Releases lokal geprüft und in
`web/data/releases/` abgelegt. Für `0.6.16` existieren
Build-Profile `a` bis `h` (`core`, `audio`, `gateway`,
`hybrid` jeweils mit/ohne Config-AP). Build- und Signiermatrix:

```powershell
.\tools\ota\build-release-matrix.ps1 -Version 0.6.16
```

Dazu werden Arduino CLI, lokale private Header und private
Signierschlüssel benötigt. Das Skript flasht **keine** Hardware.
Freigeschaltete OTA-Ziele stammen aus
`web/data/node_targets.json`. Release-Bundles für neue Empfänger
müssen neu signiert werden. Die eigentliche Alarmdetektion ist durch
ein erfolgreiches OTA **nicht validiert**.

## 5. Funktionstest nach Änderungen

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Zusätzlich in der Windows-Webapp prüfen:

1. COM16 angesteckt: **Verbunden**, neue authentifizierte Heartbeats.
2. COM16 ausgesteckt: **Nicht verbunden** trotz laufender Logger-PID;
   nach Wiedereinstecken automatische Verbindung.
3. Standort von Küche ändern und nach Browser-Refresh prüfen.
4. Standard-Gateway speichern und auf beiden Verwaltungsseiten prüfen.
5. Über COM16 Remote-STATUS durchführen; Logger-Pausierung und
   Wiederanlauf nach Jobende kontrollieren.
6. Gateway-Eintrag ergänzen/entfernen: Speichern und Neustart der Webapp
   kontrollieren; COM16 muss als dedizierter Logger erhalten bleiben.

Die Windows-Schritte wurden für PR #4 praktisch geprüft;
STATUS über COM16 wurde auch nach PR #10 bestätigt.
Auf piCore wurden STATUS, NAME GET/SET/RESET und RESTART erfolgreich
getestet. Remote-OTA auf dem Pi bleibt ungeprüft.
Diese Schritte ersetzen keinen End-to-End-Test der Rauchalarm-Erkennung.

## Noch offen

- Remote-OTA auf piCore inklusive Signaturprüfung praktisch validieren.
- Externes Backup der Pi-Daten einrichten; derzeit liegen die
  sieben SQLite-Tagesstände auf derselben SD-Karte.

- Kombinierte Registrierung / `NAME SET` auf Hardware testen und den
  Feature-Branch danach mergen.
- Gateway-Identität über den geöffneten seriellen COM-Port zusätzlich
  bestätigen; bislang werden Verbindungsereignisse ausgewertet.
- Optional später: Laufzeit-Inventar aus der Git-verfolgten
  `config/nodes.csv` in eine ausschließlich lokale Datenhaltung migrieren.
