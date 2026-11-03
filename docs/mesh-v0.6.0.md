# Mesh v0.6.0 – Manifest-Signatur direkt auf dem ESP32 prüfen

**Status: Entwicklungsstand, noch NICHT kompiliert oder auf Hardware getestet.**
**Die echte Flash-Installation ist noch SPERRT:** keine Aufrufe von `esp_ota_begin`, `esp_ota_write`, `esp_ota_end` oder `esp_ota_set_boot_partition`. v0.5.9 bleibt unser erfolgreich getesteter Referenzstand.

## Ziel und implementierte Prüfung

Die PC-Seite validiert weiterhin die Firmwaredatei mit `build_plan()` sowie den öffentlichen P-256-Schlüssel. Neu sendet `send_manifest.py` das signierte Manifest in bis zu sechs HMAC-geschützten 96-Byte-Paketen an den Zielknoten. Der Zielknoten besitzt den **fest einprogrammierten öffentlichen** Herausgeberschlüssel (aus `ota_public_key.h`). Er überprüft:

- die **ECDSA-P-256/SHA-256-Signatur direkt auf dem ESP32**;
- das exakte kanonische JSON-Format, das `sign_release.py` signiert;
- Board `esp32c3`, Schema, Ziel-ID und gültige Größe;
- die Größe der vorhandenen inaktiven OTA-Partition.

Erst nach `[AUTH] RESULT ... SIGNATURE_OK` darf derselbe Absender innerhalb von 120 Sekunden `IMG BEGIN` starten, und zwar ausschließlich mit der im signierten Manifest enthaltenen Größe und SHA-256. Der eigentliche Bildtransfer bleibt wie in v0.5.9 **RAM-only** und prüft am Ende den SHA-256 auf dem Ziel. Es gibt **keine Flash-Schreibzugriffe**.

**Vorsicht:** Es gibt noch keine Anti-Rollback-Versionsverwaltung, keine persistente Recovery-Session und keinen geprüften Boot-/Rollback-Mechanismus. Bis diese Punkte umgesetzt und getestet sind, dürfen wir den Flashpfad nicht aktivieren.

## 1. Quellcode holen und öffentlichen Schlüssel erzeugen

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
Copy-Item .\firmware\mesh-v0.5.9\mesh_secrets.h .\firmware\mesh-v0.6.0\

py .\tools\ota\export_public_header.py `
  --public-key C:\mesh-ota-keys\signing-public.pem `
  --out .\firmware\mesh-v0.6.0\ota_public_key.h
```

Wichtig: Das muss **derselbe öffentliche Schlüssel** sein, der zum privaten Schlüssel für `release-1og.json` gehört. Die private PEM-Datei **niemals** auf einen ESP32 oder in GitHub übertragen. Der generierte Header wird von `.gitignore` ignoriert.

## 2. Arduino IDE – ZUERST NUR KOMPILIEREN

Öffne `firmware/mesh-v0.6.0/mesh-v0.6.0.ino`. Die bisherigen Einstellungen beibehalten: `XIAO_ESP32C3`, Arduino-ESP32 3.3.12, 4-MB-Flash, **Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)**, USB CDC On Boot aktiviert, Erase All Flash deaktiviert.

Erst nach erfolgreichem Build und Codeprüfung zwei per USB rettbare Tischknoten auf v0.6.0 bringen:
- **Kueche:** USB-Gateway am Laptop, ID `000094457F6E27AC`.
- **1OG:** Signaturprüfender Empfänger, ID `000010637C6E27AC`.

**v0.5.9 und v0.6.0 sind für die signierte AUTH-Phase nicht kompatibel.** Ein Knoten mit v0.5.9 kann noch keine `IMG_AUTH`-Pakete verstehen.

## 3. Offline-Tests auf dem PC

```powershell
py -m pip install cryptography pyserial
py -m unittest discover -s tests -p test_ota_signed_wire.py -v
```

Das sind **nur Offline-Tests**, keine Gerätesignaturtests.

## 4. Signatur auf dem Ziel prüfen

Bei beiden Geräten v0.6.0, den Serial Monitor von Kueche schließen. Die signierte Manifestdatei und das passende `.bin` aus dem v0.5.9-Test dürfen wiederverwendet werden. Den tatsächlichen COM-Port von **Kueche** angeben:

```powershell
py .\tools\ota\send_manifest.py `
  --port COM13 `
  --image ".\firmware\mesh-v0.5.9\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.5.9.ino.bin" `
  --manifest C:\mesh-ota-keys\release-1og.json `
  --public-key C:\mesh-ota-keys\signing-public.pem
```

Erwartetes Ergebnis bei gültigem Schlüssel und unveränderter Signatur:

```text
[AUTH] PASS ... VERIFIED_ON_DEVICE NO_FLASH
PASS: ECDSA P-256 signature verified by target (no flash).
```

Auf 1OG sollte `[AUTH] RESULT ... SIGNATURE_OK NO_FLASH` erscheinen. Manipulierte Metadaten müssen mit `SIGNATURE_FAIL` abgelehnt werden.

**Wichtig:** Nach erfolgreicher Manifestprüfung innerhalb von 120 Sekunden die `.bin` senden; andernfalls die Manifestprüfung erneut ausführen.

```powershell
py .\tools\ota\send_image.py `
  --port COM13 `
  --image ".\firmware\mesh-v0.5.9\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.5.9.ino.bin" `
  --manifest C:\mesh-ota-keys\release-1og.json `
  --public-key C:\mesh-ota-keys\signing-public.pem `
  --timeout 1800
```

Ein erfolgreicher Lauf endet mit `[IMAGE] DONE ... SHA256_OK NO_FLASH` – **keine Firmware wurde installiert**.

## Nächster Schritt für echtes Flashen

Nach erfolgreichen Signatur- und End-to-End-Tests auf dem ESP32 bauen wir einen getrennten, kontrollierten `esp_ota_begin/write/end`-Pfad für `app1` ein. Es fehlen unter anderem Anti-Rollback/Versionsschutz, Persistenz und Recovery bei Stromverlust, Firmware-Image-Validierung und Boot-Bestätigung samt Rollback.

Diesen Code nicht als Ersatz für zertifizierte Brandmeldetechnik verwenden.
