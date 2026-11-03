# v0.6.4 – signiertes OTA-Image aus dem Flash zurücklesen

**Entwicklungsstand: Code auf GitHub, noch nicht lokal kompiliert oder auf Hardware getestet.**

## Umfang

Zusätzlich zu v0.6.3 ist der lokale serielle Befehl `BOOT VERIFY` vorhanden. Er prüft eine frisch signierte Manifest-/Image-Session, die **in derselben Laufzeit** in die inaktive Partition gestaged wurde, durch einen erneuten vollständigen Flash-Readback:

1. Die Firmware verlangt, dass die ECDSA-signierte Manifestprüfung erfolgreich war.
2. Die Manifest-Version muss höher als `CURRENT_FW_VERSION=0.6.4` sein (kein Downgrade).
3. Das SHA-256 der empfangenen Imagedaten und die signierte SHA-256-Angabe müssen übereinstimmen.
4. Das Image muss im selben Bootvorgang vollständig und erfolgreich mit `esp_ota_end()` in den inaktiven Slot geschrieben worden sein.
5. `BOOT VERIFY` liest exakt die signierte Bytelänge mit `esp_partition_read()` zurück, berechnet SHA-256 erneut und kontrolliert anschließend, dass der Slot einen lesbaren App-Descriptor hat.

Bei Erfolg: `[BOOT] VERIFY PASS signed=... bytes=... slot=... SHA256_OK BOOT_UNCHANGED`.

**Bewusste Grenzen:**
- Kein `esp_ota_set_boot_partition()`, keine Änderung von `otadata`, kein automatischer Neustart.
- Noch **keine** dauerhafte signierte Manifest-/Hash-Bindung über einen Neustart hinweg.
- Keine erfolgreiche Hardwareprüfung des Bootloaders oder Rollback-Ablaufs.
- Kein `BOOT ACTIVATE` und keine automatische App-Bestätigung.
- Ein erfolgreicher Readback belegt noch nicht, dass das Image startet oder die Funkfunktion nach einem Neustart korrekt ist.
- Das alte `app1`-Image v0.6.2 ist **kein Upgrade** gegenüber der neuen v0.6.4-Basis.

## Nächster Arbeitsschritt: **nur kompilieren**

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main

Copy-Item .\firmware\mesh-v0.6.3\mesh_secrets.h .\firmware\mesh-v0.6.4\
Copy-Item .\firmware\mesh-v0.6.3\ota_public_key.h .\firmware\mesh-v0.6.4\
```

Arduino-IDE: `firmware/mesh-v0.6.4/mesh-v0.6.4.ino`, Board `XIAO_ESP32C3`, Arduino-ESP32 3.3.12, 4 MB Flash, `Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)`.

**Noch nicht auf 1OG oder Kueche flashen.** Das würde den derzeit erfolgreich dokumentierten Staging-Ausgangszustand verändern. Nach erfolgreichem Build müssen wir das Basis-Upgrade und ein neueres signiertes v0.6.5-Testimage kontrolliert vorbereiten und die Bootaktivierung separat absichern.
