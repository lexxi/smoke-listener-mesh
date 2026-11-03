# Smoke Listener Mesh v0.5.9 – echter .bin-Datenstrom, SHA-256 auf Ziel

**Status: Quellcode bereitgestellt; Arduino-Build und Hardwaretests stehen aus.**
**WICHTIG: KEINE FLASH-SCHREIBZUGRIFFE, KEIN OTA-INSTALLATIONSVORGANG.**
Die funktionierende v0.5.7 und die bereits auf Kueche geprüfte v0.5.8 bleiben erhalten.

## Was v0.5.9 erstmals tut

- Ein PC-Programm `tools/ota/send_image.py` liest eine echte `.bin`-Datei und überprüft **vor der Übertragung** deren signiertes Manifest mit dem bekannten öffentlichen P-256-Schlüssel.
- Über den seriellen USB-Port gehen `IMG BEGIN <target> <size> <sha256>` und danach einzelne `IMG DATA <192 hex>`-Zeilen an den Gateway-ESP32-C3.
- Gateway sendet pro Block einen HMAC-authentifizierten ESP-NOW-Rahmen (96 Byte Nutzdaten) und wartet auf Endgeräte-ACK. Retries und TTL-Relay bleiben vorhanden.
- Der Empfänger prüft seine inaktive OTA-Partition nur auf **Existenz und Größe**, schreibt aber NICHT hinein. Stattdessen werden empfangene Bytes inkrementell mit SHA-256 verarbeitet. Der letzte 96-Byte-Block kann gepaddet sein; Padding geht nicht in die Prüfsumme ein.
- Nach Hashvergleich sendet das Ziel `IMG_RESULT`. Nur bei `SHA256_OK` meldet der Gateway `[IMAGE] DONE ... NO_FLASH`.
- Maximal 1.310.720 Byte / 13.654 Blöcke; der ESP32 hält nur SHA-256-Zustand und den aktuellen Datenblock.

**Sicherheitsgrenze:** Die eigentliche P-256-Signatur wird weiterhin ausschließlich am PC verifiziert. Der Zielknoten sieht nur die SHA-256-Angabe aus einem HMAC-authentifizierten `IMG BEGIN`. Daher ist der Empfänger ausdrücklich **NICHT** zum Flashen freigegeben. Ein kompromittierter gemeinsamer Mesh-HMAC-Schlüssel würde nicht als Herausgebersignatur reichen.

## Testhardware (bereits vorbereitet)

| Gerät | Funktion | Kennung |
| --- | --- | --- |
| Kueche | USB-Gateway am Laptop | `000094457F6E27AC` |
| 1OG | Funkempfänger, nur Strom im Normalbetrieb | `000010637C6E27AC` |

Bisheriger Empfang 1OG → Kueche: `AUTH=OK`, `hops=0`, RSSI −40 bis −42 dBm.

**Beide Geräte müssen zunächst einmal per USB mit v0.5.9 installiert werden.** Die v0.5.8 auf Kueche und eine ältere Firmware auf 1OG können die neuen `IMG_*`-Pakete nicht interpretieren. Zum Flashen von 1OG also einmal temporär per USB anschließen. Danach kann 1OG wieder rein über Strom versorgt werden. Nicht am endgültigen Installationsort einsetzen.

## 1. Code holen und kompilieren

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
Copy-Item .\firmware\mesh-v0.5.8\mesh_secrets.h .\firmware\mesh-v0.5.9\
```

`firmware/mesh-v0.5.9/mesh-v0.5.9.ino` in Arduino IDE öffnen. Bestehendes Board `XIAO_ESP32C3`, Arduino-Core 3.3.12, 4-MB-Flash und `Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS)`, USB CDC On Boot ein, Erase All Flash aus. **Zuerst nur kompilieren, Speicherverbrauch und Warnungen prüfen.** Nur bei erfolgreicher Kompilierung die beiden ausdrücklich ausgewählten Tischtest-Geräte flashen.

## 2. Release am PC signieren

```powershell
py -m pip install cryptography pyserial
```

Private Schlüssel grundsätzlich **außerhalb** des Repository verwahren. Falls noch kein Schlüssel vorhanden ist, einmalig erzeugen:

```powershell
py .\tools\ota\sign_release.py keygen --private-key "C:\mesh-ota-keys\signing-private.pem" --public-key "C:\mesh-ota-keys\signing-public.pem"
```

Mit Arduino IDE unter **Sketch → Export Compiled Binary** eine reale v0.5.9- oder spätere `.bin`-Datei erzeugen. Für den Dateiübertragungstest darf es eine gültige ESP32-C3-App-Datei sein; sie wird **nicht installiert**.

```powershell
py .\tools\ota\sign_release.py sign --image "C:\Pfad\mesh-v0.5.9.ino.bin" --private-key "C:\mesh-ota-keys\signing-private.pem" --target 000010637C6E27AC --version 0.5.9 --out "C:\mesh-ota-keys\release-1og.json"
```

## 3. Echte Datei über Funk übertragen

Den seriellen Monitor auf Kueche schließen. Der Gateway-COM-Port darf nicht gleichzeitig von Logger und Testprogramm belegt sein.

```powershell
py .\tools\ota\send_image.py --port COM13 --image "C:\Pfad\mesh-v0.5.9.ino.bin" --manifest "C:\mesh-ota-keys\release-1og.json" --public-key "C:\mesh-ota-keys\signing-public.pem" --timeout 1800
```

**COM13 nur verwenden, wenn Kueche wirklich an COM13 hängt.** Die früheren COM-Nummern können sich beim Umstecken ändern.

Erwartete Meldungen (erst nach erfolgreichem Hardwaretest bestätigt):

```text
[IMAGE] START target=000010637C6E27AC size=... blocks=... NO_FLASH
[IMAGE] NEXT index=0/...
...
[IMAGE] DONE target=000010637C6E27AC bytes=... blocks=... retries=... SHA256_OK NO_FLASH
PASS: complete real-image transport + target SHA256; nothing flashed.
```

Die Übertragung einer ~1-MB-Datei umfasst mehr als 10.000 Blöcke. Das kann wesentlich länger dauern als der 4096-Block-Test. Zunächst **kleine, gültige** ESP32-C3-App-Datei verwenden oder ersten Test auf einen einzelnen 1-MB-Transfer beschränken; im Fehlerfall Logs sichern und nicht blind erneut flashen.

## 4. Was unbedingt noch fehlt

- Signaturprüfung direkt auf 1OG (P-256-Public-Key fest in der Firmware) vor einem späteren Flashbeginn.
- Anti-Rollback-/Version-Policy und verbindliche Zielidentität.
- Zustandsbehafteter Flash-Schreibpfad in `app1` samt Abbruch-, Stromausfall- und Wiederanlaufstrategie.
- Bootpartition erst nach vollständiger Validierung umschalten, Boot-Selbsttest und Rollback prüfen.
- Fehlerbehandlung, Recovery und Belastungstest über schwache Funkverbindung / Relay.

Eine `SHA256_OK`-Meldung bedeutet **nur**, dass die echte Datei korrekt zum Ziel übertragen wurde. Sie bestätigt weder die Echtheit des Herausgebers aus Sicht des Geräts noch ein installiertes Update.

Dieses System ist kein zertifizierter Rauchmelder oder Alarmweg.
