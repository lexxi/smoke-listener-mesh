# v0.6.3 – Boot- und Rollback-Diagnose (SICHERHEITSZWISCHENSCHRITT)

**Noch nicht kompiliert und noch nicht auf Hardware getestet.** Der Hauptzweck von v0.6.3 ist, die tatsächliche Rollback-Konfiguration zu ermitteln, bevor wir eine signierte Firmware per OTA bootfähig schalten. Es gibt absichtlich **keinen** Befehl zum Umschalten der Bootpartition.

## Warum noch keine Bootaktivierung?

Beim bisherigen Test wurde v0.6.2 erfolgreich nach `app1` auf 1OG geschrieben, während **v0.6.1 in `app0`** weiterläuft. Es ist **nicht** nachgewiesen, dass der auf 1OG geflashte Bootloader Rollback unterstützt oder dass seine Bestätigung durch die App statt automatisch beim Start erfolgt.

Für einen automatischen Rollback benötigt ESP-IDF einen entsprechend konfigurierten Bootloader und eine passende Firmware. Der bloße Aufruf von `esp_ota_set_boot_partition()` und anschließendem `esp_restart()` ist kein sicherer Rollback-Nachweis. Auch eine automatisch früh bestätigte Firmware kann defekte Mesh-Funktionen haben. Für einen kontrollierten Test brauchen wir die Bestätigung explizit aus der App nach erfolgreicher Mesh-Initialisierung und später möglichst nach einem bestätigten Gateway-Handshake.

Die Build-Makros allein garantieren nicht, dass der **bereits geflashte** Bootloader exakt aus derselben Konfiguration stammt. Diese Übereinstimmung muss separat nachgewiesen werden.

## Sicherer nächster Schritt: nur Build

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main

Copy-Item .\firmware\mesh-v0.6.2\mesh_secrets.h .\firmware\mesh-v0.6.3\
Copy-Item .\firmware\mesh-v0.6.2\ota_public_key.h .\firmware\mesh-v0.6.3\
```

Öffnen: `firmware/mesh-v0.6.3/mesh-v0.6.3.ino`.

Board/Core/Partitionen wie bisher:
- `XIAO_ESP32C3`, Arduino-ESP32 **3.3.12**
- 4 MB Flash, `Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)`
- USB CDC On Boot aktiviert
- Erase All Flash deaktiviert

**Nur kompilieren. Noch keines der Geräte flashen!** Ein USB-Flash auf 1OG würde den bislang erfolgreichen Staging-Ausgangszustand verändern.

## Neuer serieller Diagnosebefehl

Auf einem Gerät mit v0.6.3 lautet der neue Befehl:

```text
BOOT STATUS
```

Er meldet:
- laufende, geplante und inaktive App-Partition;
- aktivierte oder deaktivierte `CONFIG_BOOTLOADER_APP_ROLLBACK[_ENABLE]`-Konfiguration;
- `confirmation_mode=BY_APP`, `ON_STARTUP` oder `UNSPECIFIED`;
- OTA-Imagezustände beider Slots;
- Image-Descriptor des inaktiven Slots, falls lesbar;
- `activation=LOCKED rollback_NOT_YET_PROVEN`.

**Bitte beachten:** Das Protokoll unterscheidet `BOOT STATUS` von `OTA PREFLIGHT`; nur bei der neuen Firmware ist `BOOT STATUS` implementiert.

## Nach erfolgreichem Build

Als nächstes den tatsächlich verwendeten Arduino-Core-/Bootloader-Build prüfen. Wenn Rollback nicht als `BY_APP` aktiv ist, wechseln wir für den echten Boot-/Rollback-Test auf eine eigens konfigurierte ESP-IDF- oder PlatformIO-ESP-IDF-Build-Kette samt Bootloader. Nicht einfach die vorhandene `app1` aktivieren.

Erst wenn diese Grundlage gesichert ist, entwickeln wir eine explizit lokal freizugebende Bootaktivierung und eine separate, neuere signierte Zielversion. Das aktuell gespeicherte `app1` enthält **v0.6.2**; ein Upgrade von der später per USB installierten **v0.6.3** zurück auf v0.6.2 wäre ein Downgrade. Deshalb darf die aktuelle `app1` nicht unbesehen aktiviert werden.

Referenzen:
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/ota.html
- https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/kconfig-reference.html

Dies ist keine zertifizierte Brandmelde- oder Rauchwarntechnik.
