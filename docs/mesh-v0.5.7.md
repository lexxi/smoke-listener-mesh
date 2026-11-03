# Mesh v0.5.7 – OTA-RAM-Belastungstest

**Status: Quellcode im Repository, noch NICHT auf ESP32-C3 kompiliert oder getestet.**
Diese Version kann **keine Firmwaredateien installieren** und führt **keine OTA-Flash-Schreibzugriffe** durch. Die bewährte v0.5.6 bleibt verfügbar.

## Warum v0.5.7?

Die Tests vom 03.11.2026 haben auf dem Pfad **Keller_Abgang (COM13) → Garage (Relay) → 1OG** gezeigt:

| Zeitpunkt | Relay Garage | Ergebnis | Hinweis |
| --- | --- | --- | --- |
| 18:21 | an | 7/16 ACKs | Abbruch bei Block 8 |
| 18:23 | an | 16/16 ACKs | 9 Wiederholungen, alle ACKs `hops=1` |
| 18:26 | aus | 0/16 ACKs | Abbruch bei Block 1 |
| 18:27 | wieder an | 0/16 ACKs | erster Test nach Einschalten fehlgeschlagen |
| 18:28 | an | 16/16 ACKs | 2 Wiederholungen, alle ACKs `hops=1` |

Die Gegenprobe zeigt eine funktionierende **bestätigte Übertragung über Relay**; der erste fehlgeschlagene Lauf nach dem Neustart unterstreicht die unzureichende Robustheit. Ohne separate Empfangslogs aller Knoten ist die Ursache einzelner Paketverluste unbekannt.

## Änderungen gegenüber v0.5.6

- `OTA TEST <16-hex-origin> [blocks]` unterstützt **1 bis 4096 synthetische Testblöcke** à 96 Bytes. Standard: 16.
- Maximale Testmenge: **393.216 Bytes**, nur generierte/validierte RAM-Testdaten; kein zusammenhängender Empfangspuffer und **kein Firmware-Image**.
- Stop-and-wait bleibt: ein offener Block, ACK-Timeout **1750 ms**, bis zu **8 Versuche** je Block. Diese Werte sind Experimentparameter, keine belegte Optimierung.
- `OTA STATS` zeigt separate Zähler für OTA-Daten und ACK-Empfang, geplante Relay-Weiterleitungen, Relay-Queue-Überlauf, ungültige OTA-Pakete und TX-Fehler.
- `OTA DEBUG ON` protokolliert zusätzlich jedes zur Weiterleitung eingeplante OTA-Paket (Standard OFF). `OTA DEBUG OFF` beendet die Detailausgabe.
- `[OTA] DONE` enthält Blockzahl, Bytes, Wiederholungen, Zeit und kumulierte ACK-Hopzahl; `[OTA] PROGRESS` alle 32 Blöcke.
- ACK-Prüfung vergleicht nun auch `total` und begrenzt `attempt`.
- Das Python-Skript `scripts/ota_test.py` unterstützt `--blocks`. Ohne `--blocks` bleibt es auch mit v0.5.6 kompatibel.

## Arduino IDE: zuerst nur kompilieren

1. `git pull origin main`
2. Private `mesh_secrets.h` aus dem bestehenden v0.5.6-Ordner nach `firmware/mesh-v0.5.7/` kopieren. **Nie committen.**
3. `firmware/mesh-v0.5.7/mesh-v0.5.7.ino` in Arduino IDE öffnen.
4. Unveränderte, bereits funktionierende Board-/Partition-Einstellungen verwenden: **XIAO_ESP32C3**, 4 MB Flash, `Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)`, USB CDC On Boot ein, Erase All Flash aus.
5. Build-Größe notieren (max. 1.310.720 Byte App). **Kein Remote-Update möglich.** v0.5.7 müsste zum Test weiterhin per USB installiert werden.

## Tests nach erfolgreicher Kompilierung und bewusstem USB-Flash

Zuerst zwei Knoten direkt und erst danach mit Relay testen. Für Relay-Weiterleitung müssen **alle drei** Geräte v0.5.7 besitzen. Bestehende v0.5.6-Knoten können die veränderte Test-Blockzahl nicht verarbeiten; deshalb nicht mit großen Tests mischen.

```powershell
cd C:\pyprojects\smoke-listener-mesh
py .\scripts\ota_test.py --port COM13 --target 000010637C6E27AC --blocks 16
py .\scripts\ota_test.py --port COM13 --target 000010637C6E27AC --blocks 256 --timeout 1200
```

`--blocks 256` entspricht 24.576 Bytes Testdaten. Für einen 4096-Block-Lauf braucht es eine entsprechend längere `--timeout`-Einstellung; mehr Blocks bedeuten **nicht** weniger Funkprobleme.

Auf dem Relay über USB-Monitor einmal `OTA STATS` abfragen; nur bei Bedarf `OTA DEBUG ON` aktivieren (viel serielle Ausgabe, kann die Leistung beeinflussen). Niemals Logger und OTA-Testprogramm auf demselben COM-Port gleichzeitig öffnen.

## Wichtige Grenzen

- **Noch keine übertragene .bin-Datei, keine Flash-Partition, keine Hersteller-Signatur, kein Rollback und kein Resume.**
- Bestehende v0.5.6-Knoten erhalten durch GitHub-Commits **keine drahtlose Updatefähigkeit**.
- 4096 Blöcke testen den Transport nur in einer Sitzung; bei einem Abbruch muss der gesamte Test erneut starten.
- OTA-Relay-Statistik zählt eingeplante Weiterleitungen, keine bestätigte Funkzustellung.
- Das System ist kein zertifizierter oder zuverlässiger Rauchwarnmelder/Alarmweg.

Die nächste Stufe ist ein **authentifizierter Firmware-Update-Workflow** mit signiertem Manifest, verifizierter Zielpartition, SHA-256, Stromausfalltests und Rollback. Erst nach Tests auf einem per USB rettbaren Knoten sollte eine solche Funktion für entfernte Geräte freigegeben werden.
