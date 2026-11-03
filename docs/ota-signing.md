# OTA-Firmwaredateien signieren – erster Baustein für echtes Mesh-OTA

**Stand: 03.11.2026 – Host-Werkzeug implementiert, noch nicht am ESP32-C3 getestet.**

Das Skript `tools/ota/sign_release.py` erstellt und prüft ein **ECDSA-P-256/SHA-256-signiertes Manifest** für eine kompilierte ESP32-C3-Anwendung. Der private Signaturschlüssel bleibt auf dem PC und darf **niemals** auf Mesh-Knoten oder ins Git-Repository kopiert werden.

**Der Stand ist ausdrücklich nur eine Offline-Vorbereitung.** v0.5.7 empfängt weiterhin ausschließlich synthetische RAM-Testblöcke. Es existieren noch kein OTA-Dateistream, keine Prüfung des Manifests auf dem ESP32 und kein Schreiben in eine OTA-Partition. Ein signiertes Manifest ist daher **noch keine installierbare OTA-Aktualisierung**.

## Voraussetzungen

```powershell
cd C:\pyprojects\smoke-listener-mesh
py -m pip install cryptography
```

Beim ersten Mal einen **privaten** Speicherort für Schlüssel außerhalb des Repository wählen:

```powershell
py .\tools\ota\sign_release.py keygen --private-key "C:\mesh-ota-keys\signing-private.pem" --public-key "C:\mesh-ota-keys\signing-public.pem"
```

Der private Schlüssel ist nicht mit einem Passwort verschlüsselt; deshalb nur in einem geschützten Benutzerverzeichnis aufbewahren, mit Betriebssystem-Zugriffsschutz versehen und sicher sichern. Bei einem kompromittierten Schlüssel ist eine spätere Schlüsselrotation auf den Knoten notwendig.

## Firmwarepaket vorbereiten

Die Arduino IDE erzeugt eine `.bin`-Datei, z. B. über **Sketch → Export Compiled Binary**. Das genaue Dateiverzeichnis hängt von der IDE ab.

```powershell
py .\tools\ota\sign_release.py sign --image "C:\Pfad\firmware.bin" --private-key "C:\mesh-ota-keys\signing-private.pem" --target 000010637C6E27AC --version 0.5.8 --out "C:\mesh-ota-keys\release-1og.json"
```

Prüfung unabhängig vom Signaturschritt mit dem öffentlichen Schlüssel:

```powershell
py .\tools\ota\sign_release.py verify --image "C:\Pfad\firmware.bin" --manifest "C:\mesh-ota-keys\release-1og.json" --public-key "C:\mesh-ota-keys\signing-public.pem"
```

Eine erfolgreiche Prüfung meldet `PASS`; ungültige Signaturen, veränderte Firmwaredateien, fehlerhafte Image-Header und abweichende Größen werden abgewiesen.

## Signierte Daten und Einschränkungen

Signiert wird die deterministische JSON-Kodierung des `signed`-Objekts: alphabetische Schlüsselsortierung, keine überflüssigen Leerzeichen, ASCII-Zeichen, UTF-8. Das Manifest enthält `schema`, `board`, `target`, `version`, `size` und `sha256`. Die Signatur wird als DER-kodiertes ECDSA-P-256-Hex im Feld `signature_der_hex` abgelegt.

Der Host prüft das Image-Magic-Byte und die ESP32-C3-Chip-ID sowie eine konservative Obergrenze von 1.310.720 Byte. Das **ersetzt nicht** die Prüfung des tatsächlich vorhandenen inaktiven OTA-Slots und der vollständigen Image-Struktur auf dem Ziel.

Der spätere Empfänger muss **dieselben exakten signierten Bytes** prüfen, die Signatur mit dem im Gerät fest eingebauten öffentlichen Schlüssel verifizieren und den Hash über die tatsächlich empfangenen Firmwarebytes bilden. Die Geräte-ID muss stimmen. Version und Rollback-Policy dürfen nicht nur unkritischer Anzeigetext bleiben.

**Noch offen vor einem echten OTA-Flashtest:** zuverlässiger Datei-/Blockstream aus dem PC, Manifest-Protokoll inklusive Signatur, signaturprüfender Empfänger, Inaktiv-Partition-/Größenprüfung, sequenzieller Flash-Schreibvorgang mit Abbruchbehandlung, Ende-zu-Ende-Hash-Prüfung, Aktivierung erst bei erfolgreicher Verifikation, Start-/Rollback-Tests und Relay-Fehlerbehandlung.

Auch mit diesen Funktionen bleibt das Mesh ein experimenteller Kommunikationsweg und kein Ersatz für Rauchwarnmelder.
