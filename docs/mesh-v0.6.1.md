# Smoke Listener Mesh v0.6.1 — signiertes Flash-Staging (Entwicklungsstand)

**Noch nicht kompiliert oder auf Hardware getestet.** v0.6.0 ist der nachgewiesen funktionierende Referenzstand für gültige und ungültige Signaturen. Diese Version schreibt erstmals auf ausdrückliche Freigabe Firmware in die **inaktive** OTA-App-Partition. **Sie ändert die Bootpartition NICHT und startet die neue Firmware NICHT.**

## Sicherheitsgrenzen

1. Auf dem Ziel muss die mit dem öffentlichen Schlüssel überprüfte ECDSA-P-256-Signatur vorliegen.
2. Die signierte Ziel-ID, Firmwaregröße und SHA-256 müssen passen.
3. Das signierte Versionsfeld muss **streng größer** sein als die fest einkompilierte Version `CURRENT_FW_VERSION = "0.6.1"`. Akzeptiert wird nur `MAJOR.MINOR.PATCH` (drei nichtnegative dezimale Komponenten). Ein signiertes `0.5.9`, `0.6.0` oder `0.6.1` wird abgelehnt.
4. Für Flash-Staging muss der Zielknoten **lokal am eigenen USB-Seriellport** den Befehl `FLASH ARM` erhalten. Die Freigabe gilt einmalig und höchstens 300 Sekunden, wird beim Start verbraucht. Ohne Freigabe bleibt der normale `IMG BEGIN`-Transfer RAM-only. Das opt-in `STAGE`-Kennzeichen im HMAC-authentifizierten `IMG BEGIN` muss ausdrücklich gesetzt sein.
5. `esp_ota_begin`/`esp_ota_write`/`esp_ota_end` schreiben und prüfen ausschließlich die von `esp_ota_get_next_update_partition()` gelieferte inaktive App-Partition. Schreiben und Bootaktivierung bleiben getrennt. **`esp_ota_set_boot_partition` wird nicht aufgerufen.**
6. Bei Timeout oder Hash-Fehler wird `esp_ota_abort` aufgerufen; die aktuell gebootete App wird nicht überschrieben. Ein beschädigtes inaktives Image wird nicht gebootet.

**Einschränkungen:** Kein automatischer Installationsabschluss, kein OTA-Boot, keine Bootbestätigung und noch kein getesteter Rollback. Der Versionsvergleich schützt nur gegenüber der einkompilierten Version, nicht dauerhaft gegenüber USB-/Flash-Reprogrammierung oder einer eFuse-basierten Anti-Rollback-Sicherung. Secure Boot und Flash Encryption sind ebenfalls nicht eingerichtet.

## Warum wir v0.6.2 als Test-Image brauchen

Kueche und 1OG führen aktuell v0.6.0 aus. Nach einem einmaligen Flash von v0.6.1 per USB kann der neue Empfänger ältere oder gleiche Versionen nicht mehr annehmen. Eine *neue* v0.6.2 ist daher die erste sinnvolle OTA-Testdatei. **Das bisherige signierte Manifest für v0.5.9 muss unter v0.6.1 abgelehnt werden.** Für den nächsten Test wird eine echte v0.6.2-Binärdatei erstellt und für 1OG neu signiert.

## Vorbereitung: nur kompilieren

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main

Copy-Item .\firmware\mesh-v0.6.0\mesh_secrets.h .\firmware\mesh-v0.6.1\
Copy-Item .\firmware\mesh-v0.6.0\ota_public_key.h .\firmware\mesh-v0.6.1\
```

Anschließend `firmware/mesh-v0.6.1/mesh-v0.6.1.ino` in der Arduino IDE **nur überprüfen/kompilieren**. Board: `XIAO_ESP32C3`; Arduino-ESP32 3.3.12; 4-MB-Flash; `Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)`; USB CDC On Boot aktiviert; Erase All Flash deaktiviert.

**Bis der Build, Versionsvergleiche und Flash-Fehlerpfade geprüft sind: nicht flashen und kein `--flash-stage` starten.**

## Geplante Hardwaretests, erst nach gesonderter Freigabe

- Beide Entwicklungsgeräte per USB auf v0.6.1 bringen, Heartbeats mit `AUTH=OK` kontrollieren.
- Das signierte v0.5.9-Manifest senden: muss als Downgrade abgelehnt werden.
- Ein neues, für 1OG signiertes v0.6.2-Manifest senden: muss angenommen werden.
- Mit `send_image.py` ohne `--flash-stage` unverändert den RAM-only-Transfer prüfen.
- Für den späteren Staging-Test 1OG per USB verbinden, **an 1OG** `FLASH ARM` eingeben, lokalen Monitor schließen. Per PC-Tool über **Kueche** mit ausdrücklichem `--flash-stage` den Transfer auslösen. Bei Erfolg: `STAGED_INACTIVE BOOT_UNCHANGED`. Über `FLASH STATUS` auf 1OG kann die Zwischenablage geprüft werden. Der serielle Monitor von Kueche muss beim Gateway-Script geschlossen sein.
- Stromverlust-/Fehler- und Recovery-Szenarien auf einem separat per USB rettbaren Testgerät prüfen; erst danach Bootaktivierung und Rollback implementieren.

Das Staging kann die vorhandene *inaktive* Firmware überschreiben. Auch ohne Bootumschaltung ist dies eine **echte Flash-Operation**. Erst ausführen, wenn der Testknoten per USB wiederhergestellt werden kann.

Keine zertifizierte Rauchwarnmelde- oder Brandmeldetechnik.
