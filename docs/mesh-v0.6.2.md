# Smoke Listener Mesh v0.6.2 – signierter Upgrade-Kandidat

**Stand: Quellcode eingecheckt, noch nicht kompiliert oder auf Hardware getestet.**

v0.6.2 ist ein eigenständiger Test-Sketch, abgeleitet von v0.6.1. Der Versionswert `CURRENT_FW_VERSION` steht auf `0.6.2`; beim Start meldet die Firmware zusätzlich `[FW] version=0.6.2 release_candidate=1 ota_boot_activation=DISABLED`. Die bestehende ECDSA-Manifestprüfung, der Downgrade-Schutz und das nur lokal freizugebende Staging der inaktiven OTA-Partition bleiben erhalten.

**Kueche und 1OG vorerst auf v0.6.1 belassen.** v0.6.2 wird zunächst nur kompiliert, signiert und als neues Image von v0.6.1 aus geprüft. Der Test soll zunächst ausdrücklich *ohne* Flash-Schreiben erfolgen.

## 1. Quellcode holen und nur die benötigten lokalen Header kopieren

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main

Copy-Item .\firmware\mesh-v0.6.1\mesh_secrets.h .\firmware\mesh-v0.6.2\
Copy-Item .\firmware\mesh-v0.6.1\ota_public_key.h .\firmware\mesh-v0.6.2\
```

Die **privaten** Schlüssel dürfen nie ins Repository. Der öffentliche PEM-Schlüssel muss exakt zum vorhandenen privaten Signierschlüssel passen.

## 2. In der Arduino IDE kompilieren und Binary exportieren

Sketch `firmware/mesh-v0.6.2/mesh-v0.6.2.ino` öffnen. Einstellungen wie bisher:
- XIAO_ESP32C3 / Arduino-ESP32 3.3.12
- 4 MB Flash, **Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)**
- USB CDC On Boot aktiviert, Erase All Flash deaktiviert

Zunächst **Sketch → Überprüfen/Kompilieren**, dann **Sketch → Kompilierte Binärdatei exportieren**.

Die richtige Datei ist `mesh-v0.6.2.ino.bin`. **Nicht** die `merged.bin`, `bootloader.bin` oder `partitions.bin` verwenden.

## 3. Neues Manifest für 1OG signieren

Vorher den tatsächlichen Pfad des `.bin`-Exports überprüfen. Beim bisherigen Board-/Build-Profil dürfte er so lauten:

```powershell
py .\tools\ota\sign_release.py sign `
  --image ".\firmware\mesh-v0.6.2\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.6.2.ino.bin" `
  --private-key C:\mesh-ota-keys\signing-private.pem `
  --target 000010637C6E27AC `
  --version 0.6.2 `
  --out C:\mesh-ota-keys\release-1og-062.json
```

Bitte dafür das vorhandene **gleiche** Schlüsselpaar verwenden. `release-1og.json` von v0.5.9 nicht überschreiben.

## 4. Akzeptanzprüfung an v0.6.1 (zunächst nur Manifest)

Erst nach erfolgreichem Build und Signieren:

```powershell
py .\tools\ota\send_manifest.py `
  --port COM12 `
  --image ".\firmware\mesh-v0.6.2\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.6.2.ino.bin" `
  --manifest C:\mesh-ota-keys\release-1og-062.json `
  --public-key C:\mesh-ota-keys\signing-public.pem
```

Erwartet bei Erfolg: `[AUTH] PASS ... VERIFIED_ON_DEVICE NO_FLASH`.

Der v0.6.1-Zielknoten muss v0.6.2 als **neuere**, gültig signierte Version annehmen. Der erfolgreiche v0.5.9-Downgrade-Negativtest bleibt als Gegenprobe bestehen.

## 5. RAM-only-Transfer (separater Test)

```powershell
py .\tools\ota\send_image.py `
  --port COM12 `
  --image ".\firmware\mesh-v0.6.2\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.6.2.ino.bin" `
  --manifest C:\mesh-ota-keys\release-1og-062.json `
  --public-key C:\mesh-ota-keys\signing-public.pem `
  --timeout 1800
```

**Wichtig:** Die Signaturprüfung auf 1OG muss unmittelbar zuvor erfolgreich sein. Normalerweise ist das anschließende Image-Begin nur 120 Sekunden autorisiert. Keine `--flash-stage`-Option angeben und **kein** `FLASH ARM` verwenden. Ergebnis muss `SHA256_OK NO_FLASH` enthalten.

## Noch NICHT durchführen

Das echte Flash-Staging mit `--flash-stage`, lokaler ARM-Freigabe und den Boot-/Rollback-Tests erfolgt erst nach den erfolgreichen oben genannten Nachweisen und separater Kontrolle der Fehlerpfade. Bootumschaltung ist in der Firmware weiterhin nicht implementiert.

Dies ist keine zertifizierte Rauchwarnmelde-/Brandschutztechnik.
