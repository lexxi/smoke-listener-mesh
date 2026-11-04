# Firmware v0.6.14 – Heartbeat-Versionskorrektur

## Änderung

v0.6.13 meldet in der authentifizierten Remote-OTA-Statusantwort korrekt `version=0.6.13`, überträgt im normalen TEST/HEARTBEAT jedoch versehentlich die fest codierte Version `0.6.12`. Daher zeigt der Webmonitor bei einer korrekt gestarteten v0.6.13 weiterhin 0.6.12 an.

v0.6.14 ersetzt in `sendLocal()` die fest codierten Versionsbytes durch die aus `CURRENT_FW_VERSION` abgeleiteten Werte. Das Protokoll bleibt bei Version 3, Paketgröße und OTA-/Managementablauf bleiben unverändert. Keine Audioerkennung hinzugefügt.

## Vorbereitung (PowerShell, Repository-Stamm)

```powershell
git fetch origin
git switch fix/firmware-v0.6.14-telemetry
git pull --ff-only
.\tools\ota\prepare-firmware.ps1 -Version 0.6.14 -From 0.6.13
py -m unittest discover -s tests -p test_firmware_telemetry.py
```

Dabei `mesh_secrets.h` und `ota_public_key.h` **immer aus dem zuletzt funktionierenden Versionsverzeichnis** in `firmware/mesh-v0.6.14/` übernehmen. Die Vorlagen auf neue Felder prüfen; keine echten Secrets committen.

Anschließend den Sketch `firmware/mesh-v0.6.14/mesh-v0.6.14.ino` mit demselben XIAO_ESP32C3-/OTA-Partitionsprofil wie v0.6.13 in Arduino IDE kompilieren und die BIN exportieren. Das ZIP wird danach mit `.\tools\ota\prepare-web-bundle.ps1 -Version 0.6.14` lokal signiert; der private Signierschlüssel bleibt lokal.

## Validierung

1. Bis zum Hardwaretest gilt diese Version als **Quellcode-Kandidat, nicht als validiertes Release**.
2. Offline-Regressionstest und Arduino-Compile durchführen.
3. Nur einen erreichbaren Testknoten auf 0.6.14 aktualisieren (zuerst STAGE_ONLY, verifizieren, danach aktivieren).
4. Remote STATUS muss `version=0.6.14` und nach CONFIRM `state=2` melden.
5. Im Garage-Logger muss danach eine authentifizierte `[RX] ... fw=0.6.14 AUTH=OK`-Zeile erscheinen. Webmonitor soll ebenfalls v0.6.14 anzeigen.
6. Vor dem Rollout die bestehenden ESP-NOW-, Relay- und Remote-OTA-Funktionen prüfen.

**Sicherheit:** Dieses experimentelle System ersetzt keine zertifizierten Rauchwarnmelder oder deren Alarmierung.
