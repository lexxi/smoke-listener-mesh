# v0.6.9 – positiver OTA-Bestätigungstest

Ausgangszustand (nach bestandenem negativem Rollback-Test):
- 1OG: `v0.6.7` läuft aus `app1`, `running_state=2` (VALID).
- `app0` enthält v0.6.8 mit `inactive_state=4` (ABORTED); wird beim neuen Staging überschrieben.
- Kueche: v0.6.1, COM12. 1OG: COM15.

## Änderung

Firmware `mesh-v0.6.9.ino` basiert auf v0.6.8, einschließlich `extern "C" bool verifyRollbackLater() { return true; }`. Dadurch bleibt das neu gestartete OTA-Image zunächst bei `PENDING_VERIFY` (`running_state=1`). Es wird **nur** mit lokalem seriellen `BOOT CONFIRM` und erst nach authentifiziertem Mesh-RX bestätigt.

## Bauen und signieren

```powershell
git pull origin main
Copy-Item .\firmware\mesh-v0.6.8\mesh_secrets.h .\firmware\mesh-v0.6.9\
Copy-Item .\firmware\mesh-v0.6.8\ota_public_key.h .\firmware\mesh-v0.6.9\
```

Arduino IDE: `firmware/mesh-v0.6.9/mesh-v0.6.9.ino` kompilieren und Binärdatei exportieren. Danach:

```powershell
$image = ".\firmware\mesh-v0.6.9\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.6.9.ino.bin"
py .\tools\ota\sign_release.py sign --image $image --private-key C:\mesh-ota-keys\signing-private.pem --target 000010637C6E27AC --version 0.6.9 --out C:\mesh-ota-keys\release-1og-069.json
py .\tools\ota\sign_release.py verify --image $image --manifest C:\mesh-ota-keys\release-1og-069.json --public-key C:\mesh-ota-keys\signing-public.pem
```

## Übertragen und aktivieren

Nur nach erfolgreicher Signaturprüfung. Beide Arduino Serial Monitore schließen. 1OG bleibt per USB zugänglich. Einmaliger OTA-Durchlauf:

```powershell
.\tools\ota\ota-v069.ps1 -Activate
```

Das Skript kontrolliert `v0.6.7` auf `app1` und setzt v0.6.9 in `app0`. Es verlangt die explizite Eingabe `ACTIVATE 1OG 0.6.9` vor der Änderung von `otadata`. Es führt **keinen** automatischen Reset aus.

## Positiver Rollback-Test

1. Nach `ACTIVATE SUCCESS next_boot=app0 running=app1` nur **einmal** 1OG physisch resetten.
2. Über COM15 `BOOT STATUS` ausführen: Erwartet `running=app0 boot=app0 version=0.6.9` und `running_state=1` (`PENDING_VERIFY`).
3. Prüfen, dass Kueche mit `AUTH=OK` empfangen wurde und `mesh_peer_verified=1` gilt.
4. Lokal auf 1OG einmal `BOOT CONFIRM` ausführen. Erwartet `[BOOT] CONFIRM OK err=0`.
5. Wieder `BOOT STATUS`: Erwartet `running_state=2` (`VALID`).
6. Optional separater **nachgelagerter** Reset-Test zur Persistenz der Bestätigung; `v0.6.9` muss auf `app0` bleiben.

Wenn `PENDING_VERIFY` nicht angezeigt wird, **nicht** bestätigen und keinen weiteren Reset auslösen, bis die Ursache geklärt ist. Bei fehlendem authentifizierten Mesh-RX `BOOT CONFIRM` nicht erzwingen.

**Status:** Quellcode und Testskript im Repository; v0.6.9 noch nicht lokal gebaut oder auf Hardware geprüft. Der vorherige negative Rollback-Test mit v0.6.8 war erfolgreich.
