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

**Wichtig zum Release-Prozess:** Unterschiedliche Feature-Kombinationen
erzeugen unterschiedliche Firmware-BINs. Die vorhandene Signatur bindet
die **konkreten BIN-Bytes über SHA-256**, aber der Feature-Satz steht noch
nicht ausdrücklich im signierten Manifest oder im Dashboard. Für jede
Kombination eine eigene BIN, ihren SHA-256 und die Schalterstellung
protokollieren. Dieselbe Versionsnummer lässt sich wegen der
Monotonieprüfung nicht ohne Weiteres per OTA gegen eine andere Variante
austauschen. Ein künftiger OTA-/Webapp-Schritt muss Feature-Metadaten
verifizieren und anzeigen, bevor Varianten massenhaft verteilt werden.

Das NVS mit dem Namen bleibt bei normalem OTA erhalten;
`NAME GET`, `NAME SET` und `NAME RESET` bleiben auch ohne AP erreichbar.
Die Remote-Management-Befehle benötigen eine vertrauenswürdige
Gateway-Identität und die bisherige Authentifizierung.

Der Code wurde noch **nicht** in allen Feature-Kombinationen kompiliert
und ist auf Hardware nicht validiert. Jede geplante Kombination einzeln
bauen, Funktion und ESP-NOW/OTA-Grenzen testen. Nicht auf installierte
Alarm-Knoten verteilen.

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
