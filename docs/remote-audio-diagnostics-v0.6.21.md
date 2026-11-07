# Remote-Audio-Diagnose v0.6.21 – Implementiert, Hardwaretest ausständig

Stand: 07.11.2026. Implementierung in `main`; **noch keine erfolgreiche
Kompilierung, Signierung oder Prüfung am ESP32-C3 für v0.6.21 bestätigt**.
Die bestehende v0.6.20.b/.c-Firmware kennt diese beiden Befehle nicht.

## Ziel und Funktionen

Zwei neue authentifizierte ESP-NOW-Managementaktionen:

| Aktion | Nummer | Wirkung |
| --- | ---: | --- |
| `AUDIO_STATUS` | 13 | Status des I²S-Audio-Tasks und aktuelle Diagnosezähler abfragen |
| `AUDIO_RESET` | 14 | Nur Diagnosezähler zurücksetzen; I²S und die laufende Tonerkennung bleiben aktiv |

Die Antwort enthält `audio_ready`, `beeps` (gültige Pieptöne),
`rejected`, `groups`, `candidates` und `errors` (I²S-Lesefehler).
Diese Werte stammen aus den bereits vorhandenen Audio-Zählern, nicht
aus synthetischen Beispieldaten. Die Zähler werden mittels FreeRTOS-
Critical-Section konsistent gelesen und zurückgesetzt.

Die Antwort nutzt die bestehende HMAC-authentifizierte Managementantwort:
`data[40..59]` enthält fünf Little-Endian-`uint32`-Zähler;
`data[60]` zeigt die Audio-Bereitschaft. Alte Managementantworten sind
unverändert; die Erweiterung erscheint ausschließlich bei
`AUDIO_STATUS`/`AUDIO_RESET` mit `result=0`.
Wenn Audio fehlt, verweigert die Firmware mit `result=3`; bei noch
nicht initialisiertem Mikrofon mit `result=1`. Der Parser verlangt
explizit die sechs Audiofelder; fehlende Felder gelten als Fehler.

`AUDIO_RESET` löscht keine OTA-Daten, setzt den ESP nicht zurück und
erzeugt weder Testtöne noch Alarmmeldungen. Es werden ausschließlich
die fünf Diagnosezähler zurückgesetzt – ein laufender Piepton oder
die aktuelle Gruppenbildung werden nicht abgebrochen.

## Zugriff über die normale LAN-Webapp

Auf `http://192.168.98.39:8088/nodes` befinden sich die neuen
Schaltflächen „Audio: Status“ und „Audio: Zähler zurücksetzen“ direkt
im Bereich **Hardware-Diagnose** neben den funktionierenden
Buzzer-Diagnosen. Für den Zähler-Reset gibt es eine Rückfrage.

Die vorhandene IP/CIDR-Freigabe wird weiterverwendet:

```ini
SMOKE_LAN_NODE_ADMIN_IPS='192.168.98.0/24'
```

Berechtigte Logger-Admin-IPs können wie bisher auch Diagnoseaktionen
ausführen. Firmware-Upload und Remote-OTA bleiben gesondert geschützt.
Keine neue Branch-/SSH-Tunnel-Infrastruktur notwendig.

## Benötigte Firmware und Upgrade-Reihenfolge

Die Funkaktionen sind neu. Beide Geräte benötigen **v0.6.21**:

- Testknoten `000020D37E6E27AC`: `0.6.21.b`, Featureprofil
  `audio,buzzer` (über die vorhandene signierte Remote-OTA).
- USB-Gateway `00000CEC7E6E27AC`: `0.6.21.c`, Feature `gateway`
  (per USB flashen, USB-Logger vorher stoppen).

Windows-Build und Signierung mit lokalem Schlüssel:

```powershell
cd C:\pyprojects\smoke-listener-mesh
git switch main
git pull --ff-only origin main
.\tools\ota\build-0621-dual.ps1
```

Das Skript verwendet neue v0.6.21-Quellen, zwei voneinander getrennte
Builds und eine separate Signaturprüfung. Nicht versionierte
`mesh_secrets.h` und `ota_public_key.h` werden aus der v0.6.20-
Installation verwendet, wenn sie noch nicht in v0.6.21 liegen.
Der private Signaturschlüssel wird nicht in ein Buildverzeichnis
kopiert. Das Skript flasht **keine** Hardware.

Ausgabe standardmäßig in
`C:\mesh-ota-test\release-0621-dual\{testknoten,gateway}`.

**Erst nach erfolgreichem Build, Signaturprüfung, OTA und USB-Flash**
werden die Audio-Buttons aktiviert (Firmware-Erkennung ab 0.6.21).

## Hardwaretest (noch offen)

1. Python-Regressionstests ausführen, v. a.
   `tests/test_remote_audio_management.py`.
2. Beide v0.6.21-Images bauen und signierte ZIPs verifizieren.
3. Testknoten staged aktualisieren, VERIFY/ACTIVATE/CONFIRM sowie
   `state=2` und `peer=True` prüfen.
4. Gateway per USB aktualisieren und Logger wieder starten.
5. In der normalen Knotenverwaltung Testknoten auswählen und
   **Audio: Status** klicken. Beispielzeile (kein gemessener Wert):
   `[REMOTE] AUDIO ready=1 beeps=0 rejected=0 groups=0 candidates=0 errors=0`.
6. Geeigneten echten Testton in Mikrofonnähe auslösen und Status erneut
   abrufen; dann **Audio: Zähler zurücksetzen** auslösen und verifizieren,
   dass die fünf Zähler zurückgesetzt wurden.
7. Buzzer-Fernbefehle nach dem Update auf Regression prüfen.

## Grenzen

Kein neuer Audio-Detektionsalgorithmus und keine Rauchalarm-Auslösung.
Die vorhandene v0.6.20-Audiofrequenzsuche prüft **3.000–4.400 Hz**;
die 2.000-Hz-Buzzer-Diagnose liegt weiterhin außerhalb dieses Bereichs.
Das gezielte 3.200-Hz-Testmuster und ein End-to-End-Alarmtest sind
nicht Bestandteil dieser Änderung.

Experimenteller Aufbau, **kein zertifiziertes Brandmeldesystem**.
