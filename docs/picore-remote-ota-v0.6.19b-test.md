# piCore Remote-OTA: Hardwaretest v0.6.19.b (07.11.2026)

## Ergebnis

**Erfolgreich auf genau einem Testknoten nachgewiesen.** ESP-NOW-Stage-only,
separate Aktivierung, Bootbestätigung und ein zusätzlicher Remote-Neustart
wurden über die piCore-Webapp durchgeführt. Andere Knoten wurden nicht
aktualisiert. Ein automatischer Rollback wurde **nicht** getestet.

| Komponente | Teststand |
| --- | --- |
| Host | piCore 17.0.1, Webapp + USB-Gateway, Repo `main` |
| Windows | Firmware-Build und ECDSA-P-256-Signierung, privater Schlüssel bleibt auf Windows |
| Testknoten | `000020D37E6E27AC` (Testknoten) |
| Bisherige Version | `0.6.18` |
| Neue Version | `0.6.19.b` |
| Signierte Features | `audio,buzzer` |
| Firmware-BIN | 1.019.904 Bytes |
| SHA-256 | `d49367c2302dd0c9656beeed2c5dc9b9b155c0b8a4b8eff26f0a37f64fdda7db` |
| Gateway-Port | `/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_AC:27:6E:7E:EC:0C-if00` |

## Vorprüfung

- Signiertes Release auf Windows mit `sign_release.py verify` geprüft: PASS.
- Nach SCP-Übertragung auf piCore erneut mit `sign_release.py verify` geprüft: PASS.
- `prepare_transfer.py` meldete: `PASS: publisher signature verified; 10624 blocks, 1019904 bytes`.
- `web/data/node_targets.json` auf piCore für diesen Test **ausschließlich**
  mit `000020D37E6E27AC` angelegt.
- Öffentlicher Schlüssel auf piCore über `SMOKE_OTA_PUBLIC_KEY` konfiguriert.
  **Kein privater Schlüssel auf piCore.**
- Webapp-Release-Bibliothek: Image + Manifest signaturgeprüft übernommen.
  OTA-Verwaltung über SSH-Tunnel zu `127.0.0.1:8088`, nicht über den
  direkt erreichbaren LAN-Monitor.
- Funkstatus vor Transfer: `version=0.6.18`, `peer=True`,
  `staged=False`, `verified=False`.

## Stage-only: Übertragen und prüfen, kein Bootwechsel

Abschlussmeldungen:

```text
[IMAGE] DONE target=000020D37E6E27AC bytes=1019904 blocks=10624 retries=64 duration_ms=391047 SHA256_OK STAGED_INACTIVE BOOT_UNCHANGED
PASS: image written and verified in inactive OTA slot; BOOT PARTITION NOT CHANGED.
[REMOTE] STATUS ... action=VERIFY result=0 ... staged=True verified=True ... version=0.6.18
[REMOTE] STAGED_AND_VERIFIED; inactive firmware ready, old boot still selected
[REMOTE] DONE STAGE_ONLY BOOT_UNCHANGED
```

Die Übertragung dauerte 391.047 ms (ca. 6 min 31 s), 64 Retries
wurden berichtet. Die laufende Firmware blieb `0.6.18`. Der Logger
wurde automatisch pausiert und danach wieder freigegeben.

## Getrennte Aktivierung des staged Images

`ACTIVATE_STAGED` führte ohne erneuten Image-Upload eine neue
Signaturprüfung auf dem Gerät und `VERIFY` aus. Danach wurde der
Bootslot umgeschaltet und das Ziel neu gestartet:

```text
[AUTH] PASS ... VERIFIED_ON_DEVICE NO_FLASH
[REMOTE] STAGED_AND_VERIFIED; inactive firmware ready, old boot still selected
[REMOTE] STATUS ... action=ACTIVATE result=0 ... boot=1 ... version=0.6.18
[REMOTE] STATUS ... action=STATUS result=0 running=1 boot=1 state=1 peer=True version=0.6.19.b
[REMOTE] STATUS ... action=CONFIRM result=1 running=1 boot=1 state=1 ... version=0.6.19.b
[REMOTE] STATUS ... action=CONFIRM result=0 running=1 boot=1 state=2 ... version=0.6.19.b
[REMOTE] SUCCESS: signed image booted and VALID; rollback not needed
```

**Auffälligkeit:** Der erste `CONFIRM`-Versuch wurde mit `result=1`
abgewiesen; der zweite war erfolgreich (`result=0`, `state=2`).
Die Ursache ist noch nicht geklärt. Aus dem erfolgreichen zweiten
Versuch folgt **nicht**, dass der Ablauf ohne diesen Retry robust
funktioniert oder dass Rollback getestet wurde.

## Neustart nach erfolgreicher Bestätigung

`RESTART` wurde mit `result=0` angenommen. Eine anschließende
separate `STATUS`-Abfrage meldete:

```text
[REMOTE] STATUS ... action=STATUS result=0 running=1 boot=1 state=2 staged=False verified=False peer=True version=0.6.19.b name=Testknoten
```

Damit wurde bestätigt, dass `0.6.19.b` nach einem weiteren Neustart
weiterläuft und `state=2` (VALID) behält. Der Gateway-Logger wurde
anschließend wieder freigegeben.

## Nicht nachgewiesen / offene Prüfungen

1. Audio-/Buzzer-Funktion unter **der neu installierten** `0.6.19.b`
   separat testen. Für `0.6.18` ist ein früherer USB-Diagnosetest
   dokumentiert, das ersetzt keinen Test der neuen Version.
2. Die erste abgelehnte `CONFIRM`-Anfrage gezielt untersuchen.
3. Rollback-/Stromausfallverhalten, Fehler während des OTA-Transfers und
   Langzeitstabilität sind durch diesen Lauf nicht validiert.
4. Die OTA-Prüfung ist keine Validierung einer sicherheitskritischen
   Rauchalarm-Erkennung oder Alarmweiterleitung.

## Betriebshinweise

- Die lokalen Schlüsseldateien und Knoten-Whitelist nicht ins Git einchecken.
- Logger/OTA verwenden denselben seriellen USB-Port; die Webapp reserviert
  den Port für OTA und stellt den Logger danach wieder her.
- Das auf piCore geprüfte Release lag zusätzlich unter
  `/mnt/mmcblk0p3/smoke-mesh/releases/0.6.19.b/`. Die Webapp
  verwendet ihre eigene geprüfte Release-Bibliothek unter
  `web/data/releases/`.
