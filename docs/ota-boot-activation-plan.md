# Bootaktivierung: gesicherter Übergang nach OTA-Flash-Staging

## Stand vom 2026-11-03

- 1OG läuft **v0.6.1** auf `app0` (Offset `0x10000`, 1280 KiB).
- Per ESP-NOW signierte **v0.6.2** wurde nach `app1` (Offset `0x150000`, 1280 KiB) übertragen, SHA-256 geprüft und mit `esp_ota_end()` abgeschlossen; **Bootauswahl blieb app0**.
- `otadata` (Offset `0xe000`, 8192 B) wurde lokal in `backups/1OG/otadata-before-activation.bin` gesichert, SHA-256 `4187E23640DDB4D9E00A91376D2DF4AEC3B0316E51B2F8F784BD43DF49CE8BA9`.
- Der gesicherte Eintrag 0 hat `ota_seq=1`, `state=UNDEFINED`, **gültige CRC**; Eintrag 1 ist gelöscht (nur `0xff`). Bootauswahl damit `app0`.
- Arduino-ESP32 3.3.12 für ESP32-C3 hat in `sdkconfig` `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`; der mitgelieferte QIO-80-MHz-Bootloader enthält OTA-Auswahlsymbole. **Der tatsächlich auf 1OG installierte Bootloader ist noch nicht binär verifiziert und Rollback nicht auf Hardware getestet.**

## Wiederholbar und schreibgeschützt prüfen

```powershell
py .\tools\ota\inspect_otadata.py .\backups\1OG\otadata-before-activation.bin
```

Das Skript verwendet die ESP-IDF-CRC-Initialisierung `0xffffffff` und erkennt einen vollständig gelöschten zweiten Eintrag ausdrücklich. Es schreibt keine Flash-Daten.

## Wichtiger Entwicklungsengpass

**v0.6.1 implementiert keinen `BOOT ACTIVATE`-Befehl.** Ein neuer lokaler Aktivierungsbefehl in einem künftigen Sketch kann nicht über den seriellen Monitor der momentan laufenden v0.6.1 ausgeführt werden. Ein USB-Flash von v0.6.3 auf 1OG würde den Ausgangszustand verändern und die bislang verifizierte, niedrigere Version v0.6.2 wäre danach kein zulässiges Upgrade. Ein `esptool write-flash`-Eingriff in `otadata` ist keine geeignete Abkürzung: Das würde die Anwendungskontrollen, Signaturbindung, atomare Auswahl und Rollback-Voraussetzungen umgehen.

## Anforderungen vor dem ersten Aktivierungstest

1. Eine neue **Basis-Firmware mit Aktivierungscode und expliziter Anwendungsbestätigung** separat bauen, lokal per USB auf 1OG testen, Version/Reboot prüfen. Geeignete Nummerierung z. B. v0.6.4 als Basis und v0.6.5 als signiertes OTA-Ziel.
2. Signaturprüfung und **dauerhafte Zuordnung** zu exakt den in der inaktiven Partition gespeicherten Bytes vor dem `esp_ota_set_boot_partition()` erneut durchführen; der bisherige RAM-only `staged_valid` reicht nicht.
3. Bootloader-/Partitionstabellenkonfiguration prüfen und Rollback-Verhalten mit lokal zugänglichem 1OG **kontrolliert praktisch nachweisen**, nicht nur anhand von Symbolen.
4. Bootumschaltung ausschließlich nach lokaler, zeitlich begrenzter Bestätigung. **Kein automatischer Reboot** im ersten Test.
5. Die erste Startbestätigung darf nicht unmittelbar am Anfang von `setup()` erfolgen. Sie braucht eine begrenzte Startprüfung und explizite Kriterien für Netzwerk-/Mesh-Funktion; erst danach `esp_ota_mark_app_valid_cancel_rollback()`. Ausfalltest auf absichtlich nicht bestätigtem Image mit USB-Rettungsmöglichkeit durchführen.
6. Kein persistentes Zurücksetzen von `otadata` oder `app0` während dieser Prüfung.

`v0.6.3` ist derzeit eine kompilierte Diagnoseversion ohne Aktivierungsbefehl; **noch nicht flashen**. Die aktuelle gestagte v0.6.2 bleibt als nachgewiesener Transport-/Schreibtest erhalten, aber ist ohne Vorbereitung kein sicherer nächster Start.

## Sicherheit

Testplattform für Mesh-Kommunikation, **kein zertifiziertes Rauchwarnsystem**.
