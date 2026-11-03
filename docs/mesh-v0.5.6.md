# Mesh v0.5.6: ESP-NOW-OTA-Transporttest (OHNE Flash-Schreibzugriff)

**Status:** Erster Implementierungsstand, noch **nicht in der Arduino IDE kompiliert oder auf Hardware getestet**. Bitte **nicht** alle Geräte damit flashen. Die funktionierende v0.5.5 bleibt im Repository. v0.5.6 dient ausschließlich zum Testen einer späteren Mesh-OTA-Datenübertragung und kann **keine echte Firmware installieren**.

## Was enthalten ist

- Die vorhandenen Heartbeat-/TEST-Pakete mit Protokoll 3 bleiben erhalten.
- Zusätzlich gibt es getrennte OTA-Testpakete mit **165 Bytes** (unter dem 250-Byte-Limit von ESP-NOW v1).
- Jedes OTA-Paket ist durch HMAC-SHA256 authentifiziert, inklusive Ziel-ID, Sitzung, Sequenz und Testnutzdaten.
- Eine Quelle schickt **16 synthetische Blöcke à 96 Bytes** (1.536 Byte). Das ist **keine .bin-Datei**.
- Der Zielknoten prüft die Testdaten **nur im RAM**, bestätigt jeden Block und bestätigt auch wiederholte Blöcke.
- Weiterleitung über Relays mit TTL=3, eigener Duplikaterkennung und kurzer zufälliger Verzögerung.
- Die Quelle sendet höchstens einen unbestätigten Block, wartet 1,25 s auf Ziel-ACK und versucht es höchstens fünfmal.
- Bei vollständiger Rückmeldung: `[OTA] DONE ... MODE=RAM_ONLY`. **Es wird weder eine Partition geschrieben noch neu gestartet.**

## Vorbereitung

1. Im bestehenden Projekt: `git pull origin main`.
2. `firmware/mesh-v0.5.6/mesh_secrets.h.example` als `mesh_secrets.h` im selben Verzeichnis anlegen oder die private Datei aus v0.5.5 dorthin kopieren. Geheimnisse nicht veröffentlichen.
3. In der Arduino IDE **XIAO_ESP32C3**, Flash 4 MB, **Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)**, USB CDC On Boot Enabled und Erase All Flash **Disabled** belassen.
4. `mesh-v0.5.6.ino` zuerst **nur kompilieren**. Die neue Firmware muss unter **1.310.720 Bytes** bleiben.
5. Bei erfolgreichem Build **nur zwei ausdrücklich ausgewählte Testgeräte** mit USB flashen. Andere Knoten können weiter v0.5.5 verwenden; sie ignorieren die neuen OTA-Pakete, können diese aber **nicht weiterleiten**. Für einen Relay-Test benötigt daher auch der Zwischenknoten v0.5.6.

## Zielknoten ermitteln

Der Befehl verwendet die 16-stellige Ursprungs-ID (`origin=`), **nicht** die MAC-Adresse mit Doppelpunkten. Bekannte Ziele:

| Knoten | origin |
| --- | --- |
| Kueche | `000094457F6E27AC` |
| Garage | `000058FE7D6E27AC` |
| Keller_Abgang | `0000A0E37E6E27AC` |
| 1OG | `000010637C6E27AC` |

## Test unter Windows

**COM15 darf nur von einem Programm geöffnet werden.** Den normalen `scripts/logging.py` mit Strg+C beenden; danach:

```powershell
cd C:\pyprojects\smoke-listener-mesh
py -m pip install pyserial
py .\scripts\ota_test.py --port COM15 --target 000094457F6E27AC
```

Dieser Befehl nutzt COM15 exklusiv, schickt über Serial `OTA TEST <origin>`, wartet auf die 16 bestätigten Blöcke und schreibt einen separaten Bericht nach `log/ota_test_*.log`.

Erwartete Gateway-Ausgaben:

```text
[OTA] START target=000094457F6E27AC ... TEST_NO_FLASH
[OTA] CHUNK ... index=1/16 attempt=1
[OTA] ACK ... index=1/16 hops=0
...
[OTA] DONE ... bytes=1536 MODE=RAM_ONLY
```

Auf dem Zielgerät erscheinen `[OTA] RX_DATA ... RAM_ONLY`-Meldungen. Bei Funkverlust können `attempt=2` bis `attempt=5` auftreten; nach erfolglosen Versuchen steht `[OTA] FAIL ... missing_ack`.

Anschließend kann der normale Logger wieder gestartet werden. **Keine COM15-Parallelöffnung versuchen.**

## Testreihenfolge

1. **Kompilierung** und Programmgröße prüfen.
2. Zwei Geräte auf dem Tisch: Ziel-ACK, 16/16 Blöcke, `DONE`.
3. Drittes Gerät mit v0.5.6 als Relay ergänzen.
4. Direktpfad zwischen Quelle und Ziel gezielt unterbrechen; Test über Relay durchführen. `hops>0` an ACKs und Quelle sowie verifizierter Ausfall ohne Relay sind für den Relay-only-Nachweis erforderlich.
5. Test bei schwachem Funk und absichtlich ausgeschaltetem Ziel: erwartetes `FAIL`, kein Absturz, Heartbeats laufen weiter.

## Bekannte Grenzen

- Dies ist **kein produktives Firmware-Update**: kein Datei-Upload, keine vollständige Firmware, keine digitale Firmware-Herausgebersignatur, kein OTA-Partition-Schreiben, kein Rollback.
- Die Testdaten sind deterministisch; der Empfänger hält keinen vollständigen 1.536-Byte-Puffer vor.
- Gemeinsames HMAC schützt den Transport vor fremden Paketen, ist **keine** Signatur eines Firmwareherstellers.
- Relay-Broadcasts können bei Netzüberlastung die regulären Heartbeats beeinträchtigen. Für spätere große Firmwarebilder brauchen wir eine robuste Übertragungssteuerung und ein separates Sicherheitskonzept.
- Ein erfolgreicher ESP-NOW-Sendeaufruf ist keine Ende-zu-Ende-Zustellbestätigung. Erst der vom Ziel erzeugte ACK zählt.

Weitere Roadmap: [docs/mesh-ota.md](mesh-ota.md).
