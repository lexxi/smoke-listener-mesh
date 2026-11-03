# v0.6.6 / v0.6.7 – kontrollierte OTA-Bootaktivierung (Entwicklungsstand)

**Code im Repository, noch NICHT lokal kompiliert und NICHT auf Hardware getestet.**

## Ausgangslage

- Kueche: v0.6.1.
- 1OG: v0.6.4 auf app0, signierte und per Flash-Readback bestätigte v0.6.5 auf app1.
- v0.6.4 hat **keinen** `BOOT ACTIVATE`-Befehl. Der bisherige app1-Inhalt bleibt damit zunächst unangetastet.
- Die verfügbare ESP32-C3-Arduino-3.3.12-Konfiguration hat `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`, der tatsächlich geflashte Bootloader und der Hardware-Rollback sind noch nicht praktisch bewiesen.

## Versionspaar

- **v0.6.6**: Basis auf 1OG, enthält den Aktivierungsbefehl.
- **v0.6.7**: höhere, erst lokal zu bauende/signierende OTA-Zielversion; enthält explizite Bootbestätigung.

## Neue Befehle (nur lokale serielle Konsole)

- `BOOT STATUS`: zeigt laufenden Slot, Bootziel, Konfigurationshinweise und ob eine lokale Freigabe vorliegt.
- `BOOT VERIFY`: liest das gestagte Image aus dem inaktiven Flash zurück und prüft SHA-256 gegen die vorher auf 1OG überprüfte ECDSA-signierte Metadaten-Sitzung (nur in derselben Laufzeit).
- `BOOT ARM`: Einmal-Freigabe für 60 Sekunden, nur nach erfolgreichem `BOOT VERIFY`.
- `BOOT DISARM`: Freigabe zurückziehen.
- `BOOT ACTIVATE`: verbraucht die Freigabe, prüft Image nochmals und ruft erst dann `esp_ota_set_boot_partition(next)` auf. **Startet nicht neu.**
- `BOOT CONFIRM`: Nur wenn die laufende Firmware `ESP_OTA_IMG_PENDING_VERIFY` meldet, ESP-NOW initialisiert ist und mindestens eine authentifizierte fremde TEST/HEARTBEAT-Nachricht empfangen wurde, führt es `esp_ota_mark_app_valid_cancel_rollback()` aus. **Keine automatische Bestätigung** beim Boot.

## Sicherheitsgrenzen

- Das Prüfen einer authentifizierten TEST/HEARTBEAT-Nachricht belegt nur grundlegende Mesh-Empfangsfunktion, keinen vollständigen Rauchalarm-Ende-zu-Ende-Test.
- `BOOT VERIFY` bindet die Daten an die signierte Manifestprüfung, aber die Bindung bleibt **nur in RAM**. Nach Neustart muss der Vorgang wiederholt werden; eine vollwertige persistent geschützte OTA-Aktivierungsautorisierung steht noch aus.
- Bootloader-Rollback ist **noch nicht** auf Hardware nachgewiesen. Ein absichtlich nicht bestätigtes OTA-Image muss unter USB-Zugriff und vorbereitetem Recovery-Ablauf getestet werden.
- Ein Benutzer darf `BOOT ACTIVATE` nur auf dem physisch erreichbaren Testknoten ausführen. Der Befehl ändert `otadata`, daher ist der Schritt nicht rückgängig gemacht, indem man lediglich den seriellen Monitor schließt.
- Es gibt **keinen** automatischen Neustart nach `BOOT ACTIVATE`; ein physischer Neustart ist ein eigener, ausdrücklich kontrollierter Schritt.
- Der Arduino-ESP32-Build allein beweist nicht, dass der auf 1OG installierte Bootloader identisch ist. **Vor dem ersten Bootwechsel installierten Bootloader bzw. USB-Recovery überprüfen.**

## Vorläufiger Ablauf: NUR bauen, nicht flashen

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
Copy-Item .\firmware\mesh-v0.6.4\mesh_secrets.h .\firmware\mesh-v0.6.6\
Copy-Item .\firmware\mesh-v0.6.4\ota_public_key.h .\firmware\mesh-v0.6.6\
Copy-Item .\firmware\mesh-v0.6.4\mesh_secrets.h .\firmware\mesh-v0.6.7\
Copy-Item .\firmware\mesh-v0.6.4\ota_public_key.h .\firmware\mesh-v0.6.7\
```

Arduino IDE: Sketches `firmware/mesh-v0.6.6/mesh-v0.6.6.ino` und `firmware/mesh-v0.6.7/mesh-v0.6.7.ino` separat kompilieren. Gleiche Einstellungen wie bisher: `XIAO_ESP32C3`, Arduino-ESP32 3.3.12, 4MB Flash, `Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)`, QIO/80 MHz.

**Noch keines der Geräte flashen und keine Bootpartition umschalten.**

## Nach erfolgreichem Build

- v0.6.7 als ESP32-C3-bin exportieren, mit `tools/ota/sign_release.py` für Ziel `000010637C6E27AC` und Version `0.6.7` lokal signieren sowie verifizieren.
- Erst nach separater Bestätigung des Recovery-Setups v0.6.6 über COM15 installieren.
- Neue v0.6.7 mit vorhandenem Manifest-/Flash-Protokoll über Kueche transportieren, `BOOT VERIFY` kontrollieren und **vor `BOOT ARM` stoppen**. Die Boot-Umschaltung und der Rollback-Test erhalten einen eigenen Testplan samt protokollierter Abbruchbedingungen.

Vor dem ersten Bootversuch unbedingt prüfen, ob die v0.6.7-Build-Umgebung nach `ESP_OTA_IMG_PENDING_VERIFY` nicht automatisch bestätigt und welche `otadata`-Zustände nach dem Umschalten zu erwarten sind.
