# v0.6.5 – signierter OTA-Testkandidat für v0.6.4

**Stand: Quellcode erstellt, noch nicht lokal kompiliert oder signiert. Auf keiner Hardware installiert.**

## Zweck

v0.6.5 ist ein eigenständiger Sketch mit `CURRENT_FW_VERSION="0.6.5"` und deutlich erkennbarer Startmeldung. Er dient als **höhere signierte Zielversion** für den kontrollierten OTA-Test mit v0.6.4 auf 1OG. Der vorhandene Upgrade-/Downgrade-Schutz verlangt eine **neuere Version** als die gerade laufende Firmware.

v0.6.5 enthält weiterhin den `BOOT VERIFY`-Diagnosecode und keinen Bootaktivierungsbefehl; keine `esp_ota_set_boot_partition()`-Aufrufe und keinen automatischen Neustart. Der erste Test endet nach dem Flash-Readback von v0.6.4. **Weder ein erfolgreiches Staging noch ein `BOOT VERIFY PASS` bedeutet, dass Rollback bereits getestet ist.**

## Vorbereiten: Nur bauen und signieren, noch nicht flashen

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main

Copy-Item .\firmware\mesh-v0.6.4\mesh_secrets.h .\firmware\mesh-v0.6.5\
Copy-Item .\firmware\mesh-v0.6.4\ota_public_key.h .\firmware\mesh-v0.6.5\
```

Arduino IDE: `firmware/mesh-v0.6.5/mesh-v0.6.5.ino` öffnen, Board `XIAO_ESP32C3`, Core 3.3.12, Flash 4 MB, `Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)`. **Überprüfen/kompilieren**, anschließend über **Sketch > Kompilierte Binärdatei exportieren** das gebaute Image exportieren.

Bei Verwendung des bisherigen lokalen Build-Verzeichnisses ist der erwartete Pfad (vor Ausführung Dateiexistenz prüfen):

```powershell
$image = ".\firmware\mesh-v0.6.5\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.6.5.ino.bin"
Test-Path $image
```

Nur wenn `Test-Path` `True` liefert:

```powershell
py .\tools\ota\sign_release.py sign `
  --image $image `
  --private-key C:\mesh-ota-keys\signing-private.pem `
  --target 000010637C6E27AC `
  --version 0.6.5 `
  --out C:\mesh-ota-keys\release-1og-065.json

py .\tools\ota\sign_release.py verify `
  --image $image `
  --manifest C:\mesh-ota-keys\release-1og-065.json `
  --public-key C:\mesh-ota-keys\signing-public.pem
```

**Den privaten Schlüssel und `mesh_secrets.h` nicht in GitHub oder einen Chat kopieren.** Signieren und Verifizieren finden lokal statt; der Manifestdateipfad liegt ebenfalls außerhalb des Repositories.

## Späterer kontrollierter Hardwaretest (noch NICHT ausführen)

1. Backup und Recovery per USB überprüfen; 1OG ist derzeit v0.6.1 mit in `app1` gestagter v0.6.2. Eine lokale USB-Installation von v0.6.4 **verändert diesen Testzustand**.
2. v0.6.4 lokal auf **1OG**, Kueche weiterhin v0.6.1. Danach `BOOT STATUS` und `OTA PREFLIGHT` prüfen und Boot-/Partitionsergebnis dokumentieren. Kueche nicht umflashen.
3. 1OG lokal über COM15 `FLASH ARM` ausführen; Monitor auf 1OG offen lassen. Signed-manifest zuerst auf Kueche über COM12 übertragen, dann unmittelbar OTA-Image mit `--flash-stage` senden (siehe vorherige v0.6.2-Testprotokolle).
4. Auf 1OG ohne Neustart `FLASH STATUS`, `BOOT VERIFY`, `OTA PREFLIGHT` ausführen. Erwartet `SHA256_OK BOOT_UNCHANGED`.
5. **Keine Bootaktivierung, kein `BOOT ACTIVATE`** – eine sicher bestätigte und getestete Rollback-Stufe wird separat entwickelt.

## Sicherheitsgrenzen

Der Signiercode prüft vor Erstellung eines Manifests die ESP32-C3-Imagekennung, den Image-Hash und die Größe von maximal 1.310.720 Bytes. Das ist ein Integritäts-/Signaturtest, kein vollständiger Boot-/Hardwaretest. Das Mesh-Projekt ist ein experimenteller Kommunikationsprototyp, kein zugelassenes Rauchwarnsystem.
