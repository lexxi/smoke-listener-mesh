# Echter Firmwaredatei-Transfer: Vorbereitung und Sicherheitsgrenzen

**Stand 03.11.2026: Offline-Datei-/Signaturprüfung und Blockaufbereitung implementiert. Funkempfänger und Flash-Installation folgen.**

Die Live-Tests auf `Kueche` mit v0.5.8 haben gezeigt:
`running=app0`, `next=app1`, beide 1.310.720 Byte; `PREFLIGHT PASS`.
v0.5.7 hat 4096 synthetische 96-Byte-Blöcke mit 0 Retries in 42.566 ms direkt übertragen.

**Diese Ergebnisse beweisen nicht**, dass echte Firmwaredateien bereits drahtlos übertragen oder installiert werden können. Der Code von v0.5.8 bleibt unverändert.

## Was jetzt tatsächlich verfügbar ist

`tools/ota/sign_release.py` erzeugt ein per P-256-Signatur geschütztes Manifest mit Ziel-ID, Firmwareversion, Bildgröße und SHA-256. `tools/ota/prepare_transfer.py` validiert das vollständige Manifest, den öffentlichen Signaturschlüssel und die tatsächlich vorhandenen Firmwarebytes **erneut**, bevor es einen Transportplan und optional 96-Byte-Blöcke erzeugt.

Sicherheitsprinzip: Bei abweichendem Image oder manipulierter Signatur **kein** Transferplan. Der private Schlüssel verlässt den PC nicht. Die Blockdatei ist lediglich ein Zwischenformat und hat selbst noch keine unabhängige Vertrauensgarantie.

## Auf Windows benutzen

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
py -m pip install cryptography
```

Signierte Version mit `tools/ota/sign_release.py sign` vorbereiten; das genaue Verfahren steht in [ota-signing.md](ota-signing.md).

Anschließend:

```powershell
py .\tools\ota\prepare_transfer.py `
    --image "C:\Pfad\firmware.bin" `
    --manifest "C:\mesh-ota-keys\release-kueche.json" `
    --public-key "C:\mesh-ota-keys\signing-public.pem" `
    --out "C:\mesh-ota-keys\transfer-kueche.json" `
    --chunks-out "C:\mesh-ota-keys\chunks-kueche.txt"
```

Das Resultat enthält Blockzahl, Größe, Ziel-ID, Hash und die Anzahl gültiger Bytes im letzten Block. Die Blöcke enthalten pro Zeile einen 0-basierten Index und exakt 96 Byte hexadezimal; die letzte Zeile ist mit Nullen aufgefüllt. **Die Hashprüfung später auf dem ESP32 muss ausschließlich die tatsächliche Bildgröße berücksichtigen, ohne Padding.**

`tests/test_ota_prepare.py` testet die Offline-Verarbeitung mit einem synthetischen Image-Header, gültiger Signatur, manipulierten Bytes und einem manipulierten Manifest:

```powershell
py -m unittest discover -s tests -p test_ota_prepare.py -v
```

**Testhinweis:** Das künstliche Image aus dem Unittest ist nicht bootfähig; der Test validiert Transportplan, Signatur und Block-Reassemblierung, nicht die ESP32-Bootfähigkeit.

## Was noch gebaut werden muss

1. Serielle Gateway-Schnittstelle, die reale Dateiblöcke statt der deterministischen v0.5.7-Testblöcke annimmt; mit Backpressure und ACK.
2. Neue Mesh-Pakettypen für Manifest/BEGIN, DATA, ACK/NACK, COMPLETE/ABORT; **eigenes Versionskennzeichen** und Replay-Behandlung. Mehrhop-Relay muss diese Pakettypen unterstützen.
3. Auf dem Ziel P-256-Signatur **vor jeglichem Flash-Zugriff** prüfen und verifizierte Metadaten an eine einzige Session binden.
4. Hash während des Schreibens über die echte Image-Länge bilden, im **inaktiven** OTA-Slot schreiben und bei Übertragungsfehlern abbrechen.
5. Schreibende und Boot-Auswahl nur bei erfolgreicher Signatur-, Ziel-, Versions-, Größen-, Image- und SHA-256-Prüfung, danach kontrollierter Neustart und Rollback-Test.

**Noch keine Flash-Schreibfunktion und noch keine automatisch anwendbare OTA-Firmware.** Bis zur erfolgreichen Signaturprüfung auf dem Knoten bleiben ausschließlich USB-Updates möglich. Auch die Offline-Datei-Aufbereitung ist kein Ersatz für diesen Schritt.
