# Firmware v0.6.15 – INMP441 Audio-Diagnose (Entwicklungsstand)

## Status und Grenzen

Die v0.6.14 Mesh-/Remote-OTA-Firmware wurde als Ausgangsbasis übernommen.
Die bisher getrennte INMP441-Diagnose aus `firmware/smoke-listener/smoke-listener.ino` (v0.3.1)
wurde in `audio_monitor.h` als eigene FreeRTOS-Task aufgenommen.

**Kein produktives Rauchalarmsystem.** Audio-Ereignisse werden ausschließlich als
`[AUDIO]`-Diagnose auf USB-Serial ausgegeben. Es gibt **keinen** neuen Funkpakettyp,
**keine** Alarm-Weiterleitung und **keine** Änderung an den 92-Byte-Mesh-Paketen.
Insbesondere erkennt die Übernahme derzeit nur einen Kandidaten bei mindestens
drei gültigen Pieptönen; die gewünschte 2×2-Alarmfolge muss erst mit Messdaten und
Fehlalarmtests eindeutig spezifiziert und implementiert werden.

Noch **nicht** auf ESP32-C3 kompiliert, auf Hardware getestet oder auf Auswirkung auf
OTA-Übertragungszeit, Watchdog, Laufzeit und Funkpaketverluste untersucht.
**Nicht per OTA auf alle Knoten verteilen.**

## Unabhängige Firmware-Features

In `firmware/mesh-v0.6.15/feature_config.h` lassen sich die Funktionen
**vor dem Build** unabhängig ein- oder ausschalten:

```cpp
#define FEATURE_GATEWAY   0
#define FEATURE_AUDIO     1
#define FEATURE_CONFIG_AP 0
#define FEATURE_BATTERY   0
#define FEATURE_BUZZER    0
```

| Schalter | Stand in v0.6.15 |
| --- | --- |
| `FEATURE_GATEWAY` | USB-Serial-Befehle zum Starten von Remote-OTA, AUTH, IMG, MGMT und OTA-Tests |
| `FEATURE_AUDIO` | INMP441-Diagnose-Task (keine Funkalarme) |
| `FEATURE_CONFIG_AP` | BOOT-Taster-Konfigurations-AP |
| `FEATURE_BATTERY` | **Noch nicht implementiert; 1 löst Compilerfehler aus** |
| `FEATURE_BUZZER` | **Noch nicht implementiert; 1 löst Compilerfehler aus** |

**Immer in CORE:** ESP-NOW-Mesh und Relaying, Heartbeats, HMAC, OTA-Ziel-
und Relay-Protokoll, signierter OTA-Empfang, lokale Serial-Namenbefehle
sowie authentifizierte Remote-Namensverwaltung auf dem Zielknoten.
Deaktiviertes `FEATURE_GATEWAY` darf daher **nicht** den OTA-Empfang
eines Rauchmelder-Knotens deaktivieren.

Beispiel für Rauchmelder: AUDIO=1, GATEWAY=0, CONFIG_AP=0.
Beispiel für dedizierten USB-Gateway: AUDIO=0, GATEWAY=1, CONFIG_AP=0.
Keine Abhängigkeit zu einem fest vorgegebenen Profilnamen mehr.

## Arduino CLI unter Windows einrichten

Die zentrale Build-Matrix verwendet **Arduino CLI** (`arduino-cli`),
nicht den Compile-Knopf der Arduino IDE. Die Arduino IDE kann bereits
installiert und funktionsfähig sein, obwohl `arduino-cli` in PowerShell
noch nicht als Befehl gefunden wird.

**1. Installation über Windows Package Manager (PowerShell):**

```powershell
winget install --id ArduinoSA.CLI --exact
```

Danach **ein neues PowerShell-Fenster öffnen**, damit die aktualisierte
PATH-Umgebung übernommen wird.

**2. CLI und bestehende Boards überprüfen:**

```powershell
arduino-cli version
arduino-cli core list
```

In unserer Windows-Umgebung erkennt `arduino-cli core list` bereits
`esp32:esp32 3.3.12`. Die vorhandenen Boardpakete werden
weiterverwendet; eine zweite ESP32-Installation ist nicht erforderlich.
Das Build-Skript verwendet standardmäßig das Boardprofil
`esp32:esp32:XIAO_ESP32C3` mit den bisherigen Compiler-Einstellungen.

**3. Reiner Compile-Test ohne Signatur und ohne OTA:**

```powershell
cd C:\pyprojects\smoke-listener-mesh
.\tools\ota\build-release-matrix.ps1 -BuildOnly
```

Falls `arduino-cli` weiterhin nicht erkannt wird, zuerst den
Installationspfad beziehungsweise die PATH-Variable prüfen.
Alternativ kann der vollständige Pfad zur ausführbaren Datei
über `-ArduinoCli "C:\Pfad\zu\arduino-cli.exe"` übergeben werden.

Wenn `arduino-cli core list` kein `esp32:esp32` zeigt, vor einer
Neuinstallation zuerst kontrollieren, ob Arduino CLI dasselbe
Arduino15-Datenverzeichnis wie die Arduino IDE verwendet
(typisch `%LOCALAPPDATA%\Arduino15`).

## Zentrale Build-Matrix und Variantenkennungen

Der vollständige Build läuft mit `tools/ota/build-release-matrix.ps1`.
**Standardmäßig werden alle acht** Kombinationen aus Audio,
Gateway und Konfigurations-AP erzeugt, jeweils aus einer
unveränderten lokalen Codebasis und mit eigenem Compiler-Verzeichnis.

| Anzeige | Profil | Gateway | Audio | AP | Interne OTA-Version |
| --- | --- | ---: | ---: | ---: | --- |
| `0.6.15a` | CORE | 0 | 0 | 0 | `0.6.150` |
| `0.6.15b` | AUDIO | 0 | 1 | 0 | `0.6.151` |
| `0.6.15c` | GATEWAY | 1 | 0 | 0 | `0.6.152` |
| `0.6.15d` | HYBRID | 1 | 1 | 0 | `0.6.153` |
| `0.6.15e` | CORE+AP | 0 | 0 | 1 | `0.6.154` |
| `0.6.15f` | AUDIO+AP | 0 | 1 | 1 | `0.6.155` |
| `0.6.15g` | GATEWAY+AP | 1 | 0 | 1 | `0.6.156` |
| `0.6.15h` | HYBRID+AP | 1 | 1 | 1 | `0.6.157` |

**Warum zwei Versionsangaben?** Der vorhandene ESP32-Firmwareverifier
und die Remote-OTA-Software verlangen numerische `X.Y.Z`-Versionen.
Der Buchstabe ist daher eine **zusätzlich signierte, menschenlesbare
Variantenkennung**. Der ESP32 meldet über das bisherige Protokoll die
numerische Version. Spätere Releases folgen demselben Schema,
z. B. `0.6.16a` mit `0.6.160`. Der verwendete dritte
Versionsbestandteil muss für die ESP-NOW-Status-Telemetrie <=255 sein;
das Schema ist daher bei einem künftigen Versionssprung zu prüfen.

Der signierte Feature-Satz und das signierte Label werden durch die
Server-Signaturprüfung an die exakten BIN-Bytes, Ziel-ID und numerische
Version gebunden. **Gleiche numerische OTA-Version für unterschiedliche
BINs ist ausgeschlossen.** Ein Wechsel von `0.6.15h` zurück zu
`0.6.15a` wird vom Downgrade-Schutz blockiert. Ein neueres Release
(z. B. `0.6.16a`) kann den Wechsel wieder ermöglichen.

### Ausführen

```powershell
git pull --ff-only

# Zuerst alle 8 Varianten bauen (ohne Signatur / OTA):
.\tools\ota\build-release-matrix.ps1 -BuildOnly

# Danach für alle ausdrücklich registrierten Knoten signieren:
Copy-Item .\web\node_targets.json.example .\web\data\node_targets.json
# Liste web/data/node_targets.json vor Verwendung überprüfen!
.\tools\ota\build-release-matrix.ps1
```

Arduino-CLI, Board-Core `esp32:esp32`, private Firmware-Header sowie
`myenv` mit `cryptography` müssen vorhanden sein. Zum Signieren
kommen privater und öffentlicher Schlüssel hinzu.

Ein Build erzeugt Unterordner je Kennung unter
`firmware/mesh-v0.6.15/build/release-matrix-8/`.
Bei erneutem Lauf nicht überschreiben: mit `-OutputRoot` einen
**neuen** Ausgabepfad angeben. Pro Variante werden BIN, SHA-256,
optional ein signiertes ZIP sowie ein gemeinsamer
`build-report.json` erzeugt.

`web/data/node_targets.json` enthält ausschließlich eine Liste
freigegebener ESP32-C3-Knoten-IDs. **Jeder** registrierte Knoten
kann jedes der acht Firmware-Images bekommen; es gibt keine
fest verdrahtete AUDIO-/GATEWAY-Rolle mehr. Das Signierskript
generiert für jede Variante die passenden knotenspezifischen
Manifeste und prüft jede Signatur vor dem ZIP-Export.

Die Ausgabe von `-BuildOnly` enthält bei `Targets` bewusst 0,
weil nicht signiert wird. Die Build-Matrix sendet keine Daten per
Funk und flasht keine Geräte.

**Hardwaregrenze:** Kompilierbar bedeutet nicht, dass jede Funktion
auf jedem ESP tatsächlich verwendet werden kann. AUDIO benötigt
einen angeschlossenen INMP441, Batterie/Buzzer sind noch
nicht implementiert. Ein USB-Gateway muss physisch am
Server angeschlossen sein. OTA, Audio-Task und AP sind noch
nicht gemeinsam auf Hardware validiert.

## Signierte Feature-Metadaten für neue Releases

Der bestehende, vom ESP32-C3 geprüfte OTA-Payload (`signed` +
`signature_der_hex`) bleibt byteweise und strukturell unverändert.
Neue Manifeste können zusätzlich `feature_claim` und
`feature_signature_der_hex` enthalten. Die Feature-Angaben sind dabei
**separat mit ECDSA P-256 signiert** und an Ziel-ID, Version und
Firmware-SHA-256 gebunden. Das Firmware-Image wird weiterhin vollständig
über seinen signierten SHA-256 geprüft.

Die Remote-OTA-Webschnittstelle verweigert für **v0.6.15 und neuer**
ein Release ohne separat signierte Feature-Angaben; ältere Versionen
bleiben kompatibel. Ein Signatur- oder Metadatenfehler führt ebenfalls
zum Abbruch **vor** dem Flashen.

Die **Server-Seite** verifiziert beide Signaturen und zeigt die Features in
der Firmware-Auswahl sowie in den Releasedetails an. Ältere Releases ohne
diesen Zusatz erscheinen als `Features unbekannt`, nicht als CORE.

Beispiele für signierte v0.6.15-ZIPs nach dem Build:

```powershell
# Rauchmelder (FEATURE_AUDIO=1, alle anderen 0)
.\tools\ota\prepare-web-bundle.ps1 -Version 0.6.15 -Features @("audio") -Image "PFAD_ZUR_AUDIO_BIN"

# Schlanker Gateway (FEATURE_GATEWAY=1)
.\tools\ota\prepare-web-bundle.ps1 -Version 0.6.15 -Features @("gateway") -Image "PFAD_ZUR_GATEWAY_BIN"

# Reiner Mesh-Knoten
.\tools\ota\prepare-web-bundle.ps1 -Version 0.6.15 -Features @() -Image "PFAD_ZUR_CORE_BIN"
```

`-Features` ist für v0.6.15 explizit anzugeben. Für alle
Feature-Kombinationen sind **getrennte BIN-Dateien und ZIP-Pakete**
erforderlich. Die Anwendung muss außerdem die gewünschte Knotenrolle
prüfen; eine automatische Rolle/Hardware-Erkennung ist **noch nicht
implementiert**.

**Grenze:** Die zusätzliche Signatur beweist, dass der Herausgeber
diese Feature-Angaben für den konkreten Firmware-Hash signiert hat.
Sie beweist **nicht**, dass die beim Build verwendeten Schalter
tatsächlich dazu passen. Deshalb jede BIN mit den gewählten Schaltern
protokollieren und vor dem Signieren überprüfen. Auf dem Knoten selbst
wird die zusätzliche Feature-Signatur noch nicht überprüft; die
bestehende Gerätesignatur- und Hashprüfung bleibt erhalten.

Gleiche Firmwareversion mit anderer Feature-BIN ist **kein** normaler
Remote-OTA-Upgradepfad, da identische/ältere Versionen verweigert werden.
Die dauerhafte Node-Feature-Inventarisierung erfordert später
zusätzliche authentifizierte Telemetrie; die Webapp zeigt hier vorerst
die Eigenschaften des **ausgewählten Releases**, nicht automatisch
die Eigenschaften jeder bereits laufenden Firmware.

Das NVS mit dem Namen bleibt bei normalem OTA erhalten;
`NAME GET`, `NAME SET` und `NAME RESET` bleiben auch ohne AP erreichbar.
Die Remote-Management-Befehle benötigen eine vertrauenswürdige
Gateway-Identität und die bisherige Authentifizierung.

Der Code wurde noch **nicht** in allen Feature-Kombinationen kompiliert
und ist auf Hardware nicht validiert. Jede geplante Kombination einzeln
bauen, Funktion und ESP-NOW/OTA-Grenzen testen. Nicht auf installierte
Alarm-Knoten verteilen.

## Explizite Zielrollen für Remote-OTA

Ab v0.6.15 sperrt der Webserver **Stage, Aktivierung und vollständige OTA**
für jeden Knoten ohne lokal freigegebene Zielrolle oder mit
unpassenden signierten Features. Die reine Statusabfrage bleibt möglich.

Einmalige lokale Konfiguration auf dem Webserver:

```powershell
Copy-Item .\web\node_roles.json.example .\web\data\node_roles.json
```

Vor Verwendung **Inhalt prüfen und anpassen**. Die Beispielzuordnungen
sind Vorschläge, keine automatische Erkennung. Nicht eingetragene
Knoten dürfen keine neuen Images per Webapp erhalten.

Erlaubte Werte:

| Rolle | Erforderliche signierte Features |
| --- | --- |
| `mesh` | weder `audio` noch `gateway` |
| `listener` | `audio`, aber kein `gateway` |
| `gateway` | `gateway`, aber kein `audio` |
| `hybrid` | `gateway` und `audio` |

`config_ap` ist für jede Rolle optional. Damit werden Fehlverteilungen
verhindert, ohne eine bestimmte Knotenhistorie als Wahrheit anzunehmen.
`web/data/node_roles.json` ist in `.gitignore` ausgeschlossen und
wird nicht ins Repository eingecheckt.

**Sicherheitsgrenze:** Die Rollenprüfung ist eine serverseitige
Freigabeliste. Sie verhindert falsche Auswahl über diese Webapp,
ist aber **keine Geräte- oder Hardware-Attestation**. Die aktuell
laufenden Features werden noch nicht vom ESP32 gemeldet.
Ein anderes OTA-Werkzeug kann diese Webapp-Prüfung umgehen.
Fehlerhafte manuelle Freigabelisten bleiben möglich.

Bestandsreleases bis v0.6.14 werden von der neuen Rollensperre
nicht betroffen; die bisherige signierte OTA-Prüfung bleibt bestehen.

## Anschlüsse

INMP441: SCK=GPIO6, WS=GPIO3, SD=GPIO10, L/R=GND, VDD=3V3, GND=GND.
Vor dem Test Pinbelegung des tatsächlich verwendeten C3-Boards und
I2S-Treiberkompatibilität der installierten Arduino-ESP32-Version überprüfen.

## Vorbereitung

```powershell
git fetch origin
git switch feature/firmware-v0.6.15-audio-diagnostics
.\tools\ota\prepare-firmware.ps1 -Version 0.6.15 -From 0.6.14
py -m unittest discover -s tests -p test_audio_integration.py
```

`mesh_secrets.h` und `ota_public_key.h` wie bei **jedem** Firmwarewechsel
aus der letzten funktionierenden Version übernehmen. Niemals committen.

## Validierung vor einem OTA-Versuch

1. Arduino-Compile mit bisherigem XIAO_ESP32C3-OTA-/Rollback-Partitionsprofil.
2. Audio zunächst an einem **per USB rettbaren Testgerät** prüfen.
3. Im seriellen Log `[AUDIO] READY`, `[AUDIO] BEEP`,
   `[AUDIO] STATS` und gegebenenfalls `ALARM_CANDIDATE DIAGNOSTIC_ONLY` prüfen.
4. Parallel `[RX]`, `[TX]`, `[RELAY]` und OTA-Status auf Aussetzer prüfen.
5. Boot-/Rollback-Tests und längere Laufzeitmessung; die Audio-Task darf die
   Mesh-/Managementfunktion nicht verschlechtern.
6. Anschließend exakte 2×2-Sequenz, Fehlalarme und Mikrofonfehlererkennung entwickeln.

Es wurde noch kein Hardwaretest für diesen Branch durchgeführt.
