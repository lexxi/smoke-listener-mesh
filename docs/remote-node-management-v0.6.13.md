# Remote-Knotenverwaltung ab Firmware v0.6.13

## Funktionsumfang

- Webapp: http://127.0.0.1:8088/nodes (Link im Monitor).
- **Discover** liest die jüngsten authentifizierten Mesh-Meldungen aus der Monitor-Datenbank. Es ist keine Funk-Broadcast-Abfrage. Noch nie empfangene Knoten erscheinen erst nach ihrer ersten Mesh-Meldung.
- Für einen bekannten Knoten: `STATUS`, `NAME_GET`, `NAME_SET <name>`, `NAME_RESET`, `RESTART`.
- Ein Name hat 1–19 ASCII-Zeichen: `A-Z a-z 0-9 - _`. Speichern erfolgt im NVS, ohne Neustart; `NAME_RESET` löscht den gespeicherten Namen.
- Ziel- und Gateway-Firmware **beide v0.6.13 oder neuer**. Ältere Zielknoten können wie bisher OTA-Updates empfangen, solange sie mindestens v0.6.11 ausführen.
- Die Node-ID (hardwarebasiert) bleibt unabhängig vom Namen gleich.
- Remote-Aktionen verwenden die vorhandenen HMAC-authentifizierten Mesh-MGMT-Frames plus einmalige, vom Ziel ausgegebene Nonces. Nicht bestätigte Befehle nicht blind wiederholen.
- Ein eigenständiger `RESTART` wird nur akzeptiert, wenn Bootpartition und laufende Partition gleich sind und keine aktive Flash-Übertragung läuft. Der bestehende `REBOOT` bleibt für OTA-Bootwechsel reserviert.
- Webapp serialisiert OTA und Knotenverwaltung über denselben Job-Lock; der COM14-Logger wird vor jeder Aktion pausiert und danach fortgesetzt.

## Firmware bauen

```powershell
git pull origin main
.\tools\ota\prepare-firmware.ps1 -Version 0.6.13 -From 0.6.12
```

In Arduino IDE `firmware/mesh-v0.6.13/mesh-v0.6.13.ino` mit demselben Board-/Partitionsprofil wie v0.6.12 kompilieren, kompilierte BIN exportieren, signiertes ZIP erzeugen:

```powershell
.\tools\ota\prepare-web-bundle.ps1 -Version 0.6.13
```

**Nicht blind alle Knoten auf einmal umstellen.** Zuerst einen Nicht-Gateway-Testknoten mit OTA **STAGE_ONLY** aktualisieren, Bootwechsel und `state=2` prüfen, dann die übrigen Knoten. Garage/COM14 kann sich nicht selbst flashen: Einen anderen bereits v0.6.13-fähigen, per USB angeschlossenen Gateway-Knoten verwenden oder Garage kontrolliert per USB aktualisieren. Erst nach dem Gateway-Update funktionieren `NAME_*` und `RESTART` remote.

## Tests vor realem Einsatz

1. Python-Tests: `python -m unittest discover -s tests -p test_remote_ota_protocol.py`.
2. Firmware-Compile für XIAO_ESP32C3, OTA-Partition und aktiviertes Rollback.
3. `STATUS` / `NAME_GET` auf v0.6.13-Knoten, dann `NAME_SET TestNode` und erneutes `NAME_GET`; NVS-Persistenz nach Reboot überprüfen.
4. `NAME_RESET` und erneute Abfrage. Testen, dass ungültige Namen abgelehnt werden.
5. Unveränderte Alarmweiterleitung nach Umbenennen und Neustart prüfen.

Das GitHub-Commit ersetzt keinen Hardwaretest. Vor Tests die vorhandene Alarmfunktion nicht als alleinige Sicherheitsmaßnahme verwenden.
