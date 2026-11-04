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

## Konfigurations-AP entfernt

Der bislang über den BOOT-Taster (GPIO9) gestartete WLAN-Konfigurations-AP und
sein HTTP-Webserver sind in v0.6.15 entfernt. Die Namensverwaltung bleibt
über die bereits vorhandenen lokalen Serial-Befehle `NAME GET`,
`NAME SET <name>`, `NAME RESET` und über das authentifizierte
Remote-Management (Gateway und Ziel mindestens v0.6.13) verfügbar.
Das NVS mit dem gespeicherten Knotennamen wird bei normalem OTA nicht gelöscht.

**Folge:** Bei Funk-/Gatewayausfall ist die Namensänderung nicht mehr per
Konfigurations-WLAN möglich. Ein lokaler USB-Serial-Zugang bleibt als
Wiederherstellungsweg erforderlich. GPIO9/BOOT ist dadurch für den
Konfigurations-AP nicht mehr belegt; seine physische Boot-Funktion
des ESP32-C3 ist davon nicht betroffen.

Diese Code-Änderung wurde noch nicht auf Hardware validiert.
Die tatsächliche Flash-Einsparung muss nach dem Kompilieren gemessen werden.

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
