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

## Firmwareversion `Major.Minor.Patch.Variante`

Ab v0.6.15 verwenden wir **eine echte vierteilige Versionskennung**
in Firmware, Mesh-Telemetrie, signiertem OTA-Manifest, Remote-Status,
Webserver und Build-System. Einmalige **USB-Umstellung aller Knoten**
ist vorgesehen; installierte v0.6.14-Knoten können die neue
Versionssemantik nicht nutzen.

| Version | Profil | Gateway | Audio | AP |
| --- | --- | ---: | ---: | ---: |
| `0.6.15.a` | CORE | 0 | 0 | 0 |
| `0.6.15.b` | AUDIO | 0 | 1 | 0 |
| `0.6.15.c` | GATEWAY | 1 | 0 | 0 |
| `0.6.15.d` | HYBRID | 1 | 1 | 0 |
| `0.6.15.e` | CORE + AP | 0 | 0 | 1 |
| `0.6.15.f` | AUDIO + AP | 0 | 1 | 1 |
| `0.6.15.g` | GATEWAY + AP | 1 | 0 | 1 |
| `0.6.15.h` | HYBRID + AP | 1 | 1 | 1 |

Die ersten drei Zahlen bestimmen die **Code-Generation**.
Der vierte Bestandteil ist die **Feature-Variante**, kein
Release-Rang. Eine signierte Aktualisierung `0.6.15.h` →
`0.6.15.a` ist deshalb gestattet. Das gleiche Image nochmals
auf dieselbe Variante zu installieren wird verweigert.
Ein Code-Downgrade `0.6.16.a` → `0.6.15.h` bleibt gesperrt.

Die signierte Feature-Liste muss zur Variante passen.
Die bestehende ECDSA-Signatur, die SHA-256-Imageprüfung,
das Boot-Readback und die Boot-Bestätigung bleiben erhalten.

### Einheitliche Build-Matrix

```powershell
git pull --ff-only

# Alle acht Varianten ohne Signierung kompilieren:
.\tools\ota\build-release-matrix.ps1 -BuildOnly

# Erst nach erfolgreichem Test:
Copy-Item .\web\node_targets.json.example .\web\data\node_targets.json
# Freigegebene IDs in node_targets.json überprüfen
.\tools\ota\build-release-matrix.ps1
```

Die Build-Matrix kompiliert jede Kombination aus einem isolierten
Quellverzeichnis. Für jeden Build wird `SMOKE_FIRMWARE_VERSION`
auf die passende Version gesetzt. Firmware-Quellen und private
Header werden nicht verändert. Je Variante entstehen eine BIN
und – bei aktivierter Signierung – zielknotenspezifische
Manifeste und ein OTA-ZIP.

Ausgabeverzeichnis:
`firmware/mesh-v0.6.15/build/release-matrix-4part/`.
Bei einem zweiten Lauf mit `-OutputRoot` einen neuen Pfad
angeben; vorhandene Exporte werden nicht überschrieben.

Jeder in `web/data/node_targets.json` freigegebene ESP32-C3
kann alle acht Varianten erhalten. Die bisherige starre Rollenbindung
ist entfernt; die Wahl der Variante bleibt eine bewusste
Administrationsentscheidung.

### Übertragung und Migration

- Auf **allen Knoten einmalig per USB flashen**, damit jeder Empfänger
  den neuen Versionsvergleich beherrscht. Vorher ESP-NOW/OTA-Hardwaretests
  an einem Testknoten durchführen.
- Die Mesh-Heartbeat-Telemetrie transportiert die Variante in einem
  authentifizierten Versionsmarker; ältere Knoten erkennen den Marker
  nicht als vollständige vierteilige Version.
- Remote-Management über den USB-Gateway meldet `version=0.6.15.b`
  oder entsprechend andere Varianten.
- Die Webapp erkennt und sortiert die vierteilige Version und
  verwendet sie unverändert beim Upload und OTA.
- Nach dem Flashen mindestens Heartbeats, Namensverwaltung,
  Gateway-Kommandos, OTA-Stage/Verify sowie Rollback testen.
- Noch **kein produktiver Rauchalarm**: Die AUDIO-Integration
  erzeugt nur Diagnoseereignisse, keine Alarmweiterleitung.

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

Für neue Releases ausschließlich die zentrale
`build-release-matrix.ps1` verwenden. Das ältere
`prepare-web-bundle.ps1` ist nicht auf die neuen Variantenkennungen
und automatisch erzeugten OTA-Buildversionen abgestimmt.

**Grenze:** Die zusätzliche Signatur beweist, dass der Herausgeber
diese Feature-Angaben für den konkreten Firmware-Hash signiert hat.
Sie beweist **nicht**, dass die beim Build verwendeten Schalter
tatsächlich dazu passen. Deshalb jede BIN mit den gewählten Schaltern
protokollieren und vor dem Signieren überprüfen. Auf dem Knoten selbst
wird die zusätzliche Feature-Signatur noch nicht überprüft; die
bestehende Gerätesignatur- und Hashprüfung bleibt erhalten.

Wechsel zwischen Varianten derselben Codeversion sind per OTA zulässig,
nachdem die Knoten einmalig per USB auf die neue Firmware gebracht wurden.
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

## Zentrale USB-Gateway-Konfiguration

Die Webapp liest die zentrale Konfiguration aus `web/gateways.json` beim Start.
**Dies ist die einzige Stelle für COM-Port, Gateway-Namen und Gateway-Knoten-ID.**

```json
{
  "logger_gateway": "COM16",
  "gateways": {
    "COM16": {"name": "Gateway", "node": "00000CEC7E6E27AC"},
    "COM14": {"name": "Garage", "node": "000058FE7D6E27AC"},
    "COM12": {"name": "Kueche", "node": "000094457F6E27AC"}
  }
}
```

- `logger_gateway`: welcher registrierte USB-Gateway für den Dashboard-Dauerlogger benutzt wird.
- `gateways`: für Remote-OTA und Knotenverwaltung freigegebene COM-Ports samt
  Namen und **16-stelliger Hardware-Knoten-ID**. Die übrigen Einträge sind Fallback-Gateways.
- `web/gateway_config.py` validiert die Datei und stellt Werte für
  `web/logger_control.py` und `web/remote.py` bereit.
- Das Dashboard liest Name und Port aus `/api/logger/status`; es enthält keine
  eigene COM-Port-Konstante.
- Wenn ein Remote-OTA- oder Verwaltungsbefehl über den Logger-Gateway läuft,
  wird dessen Web-Logger pausiert und danach bei Bedarf wieder gestartet.
  Bei einem anderen Gateway bleibt der Logger unberührt.
- **Nach jeder Änderung von `web/gateways.json` die Webapp neu starten.**
  COM-Ports können sich nach Neuanschluss der Hardware ändern.
- Der Web-Logger wird weiterhin **nur nach Klick auf „Logger starten“**
  gestartet. Vorher alle externen Serial-Monitore/Logger auf diesem Port schließen.
**Wichtig: Vertrauensliste im Empfänger:** Die Firmware enthält zusätzlich eine
kompilierte Remote-Management-Allowlist (`MGMT_TRUST_*` in
`firmware/mesh-v0.6.15/mesh-v0.6.15.ino`). Seit der Gateway-Erweiterung
ist auch `00000CEC7E6E27AC` (Gateway/COM16) enthalten. Die JSON-Datei
konfiguriert nur die Webapp. Bereits geflashte Empfänger vertrauen dem
neuen Gateway **erst nach einem Firmwareupdate**; andernfalls erscheint
`[MGMT] TIMEOUT no_reply`, obwohl Heartbeats empfangen werden.
Vor dem Aktualisieren aller Empfänger einen Management-STATUS über einen
bereits vertrauenswürdigen Gateway (Garage oder Kueche) testen. Ein neuer
Build mit derselben Versionskennung ist dabei nicht eindeutig von einem
alten Build zu unterscheiden; Versionierung beim Rollout beachten.

- `web/data/node_targets.json` ist eine **separate OTA-Zielknoten-Allowlist**;
  die Gateway-Konfiguration ersetzt sie nicht.

## Webserver mit migrieren

Die Webserver-Umstellung gehört zur einmaligen USB-Migration.
Folgende Komponenten sind an vierteilige Versionskennungen angepasst:

- `web/release_library.py`: signierte Releases `0.6.15.a` bis
  `0.6.15.h` prüfen, speichern und auflisten;
- `web/remote.py`: Remote-OTA-Start erst nach Prüfung der
  Vier-Komponenten-Version, Feature-Signatur und freigegebenen Ziel-ID;
- `web/templates/ota.html`: die echte Versionskennung bei Release-Auswahl,
  Details und Start-Bestätigung anzeigen;
- `web/app.py`: `fw=0.6.15.b` aus authentifizierten Mesh-Logs
  in der Datenbank erhalten;
- `tools/ota/remote_ota.py`: Remote-MGMT-Status mit optionalem
  vierten Bestandteil einlesen, Code-Downgrade sperren und signierte
  Feature-Wechsel bei gleichem Code-Stand erlauben.

Den Webserver nach `git pull --ff-only` neu starten, damit die
neuen Python-Module und die Webvorlage geladen werden.
Vor dem ersten Remote-OTA die Statusabfrage für Gateway und Ziel
prüfen. Falls ein noch nicht aktualisierter Gateway in der alten
Firmware läuft, liefert er die neue Variantenkennung nicht vollständig.

Bestehende historische Log-Datensätze behalten ihren bisherigen
Versionswert; neue Empfangsdaten enthalten die vollständige
vierstellige Version.

## Zielknoten-Freigabe statt fester Hardware-Rollen

Ab v0.6.15 prüft der Webserver vor Stage, Aktivierung und OTA,
ob das Ziel in `web/data/node_targets.json` eingetragen ist.
Die Funktionswahl ist **nicht** an einen festen Knotentyp gebunden.
Damit kann ein bisheriger Rauchmelder auch Gateway-Funktionen
bekommen oder ein Gateway eine AUDIO-Variante erhalten,
sofern die benötigten Bauteile vorhanden sind.

```powershell
Copy-Item .\web\node_targets.json.example .\web\data\node_targets.json
```

Die Beispiel-IDs vor dem produktiven Signieren prüfen. Jeder
registrierte Knoten darf jede der acht Varianten erhalten.
Fehlende oder beschädigte Freigabelisten sperren OTA ab v0.6.15;
alte Releases bis v0.6.14 sind davon ausgenommen.
Die Statusabfrage wird weiterhin zugelassen.

Diese Freigabe ist eine **serverseitige Auswahlkontrolle** und
keine Geräte-Attestation. Der Empfänger überprüft unverändert
die bereits bestehende Signatur der Firmware und ihren Hash.
Die tatsächlich angeschlossenen Peripheriegeräte werden nicht erkannt.

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
