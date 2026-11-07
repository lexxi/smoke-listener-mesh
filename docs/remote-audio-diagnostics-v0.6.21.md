# Remote-Audio-Diagnose v0.6.21 – Hardwaretest erfolgreich

Stand: 07.11.2026. Beide Firmwareprofile wurden gebaut und signiert.
Testknoten `0.6.21.b` wurde über signierte Stage-only-OTA, VERIFY und
Aktivierung erfolgreich auf `state=2` (VALID) gebracht; USB-Gateway
`0.6.21.c` wurde per USB aktualisiert. Beide Geräte sind im Mesh online.
Die alten Firmwarestände v0.6.20.b/.c kennen die Audio-Befehle nicht.

## Bestätigter Hardwaretest (07.11.2026)

Testziel: `000020D37E6E27AC` (Testknoten), Gateway:
`00000CEC7E6E27AC` (piCore USB-Logger). Alle drei Aktionen liefen über
die normale LAN-Knotenverwaltung mit authentifizierten ESP-NOW-Antworten.

| Aktion | Messwerte | Ergebnis |
| --- | --- | --- |
| Erstes `AUDIO_STATUS` | `ready=1 beeps=1 rejected=5 groups=1 candidates=0 errors=0` | Erfolgreich |
| `AUDIO_RESET` | `ready=1 beeps=0 rejected=0 groups=0 candidates=0 errors=0` | Erfolgreich |
| Zweites `AUDIO_STATUS` | `ready=1 beeps=0 rejected=2 groups=0 candidates=0 errors=0` | Erfolgreich |

`rejected=2` bei der Kontrollabfrage belegt neue Diagnoseaktivität
**nach** der Rücksetzung. Ein einzelner Ereigniszähler allein beweist
allerdings nicht die korrekte Erkennung eines realen Rauchalarms.
In allen Fällen `result=0`, Firmware `0.6.21.b`,
`running=boot=1`, `state=2`, `peer=True`.
Der Gateway-Logger wurde nach den Befehlen wieder freigegeben.

Das v0.6.21-Dual-Build erzeugte: Testknoten `1.020.608` Bytes,
Gateway `991.600` Bytes, Release-Verzeichnis
`C:\\mesh-ota-test\\release-0621-dual-v2`.
Der Testknoten wurde erfolgreich staged übertragen (`SHA256_OK`),
verifiziert, aktiviert und nach Mesh-Check bestätigt.

Noch **nicht** nachgewiesen: 3.200-Hz-Testmuster, kompletter Alarmweg,
Audio-Erkennung eines realen Rauchmeldermusters und erneuter
Buzzer-Regressionstest nach dem v0.6.21-Update.

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
ausführen. Signierte Release-Uploads und Remote-OTA sind für das Node-Admin-Netz\nfreigegeben. Die Logger-Admin-Liste allein reicht dafür nicht. Die Uploads\nwerden weiterhin serverseitig signatur- und zielgebunden geprüft.\n\n**Sicherheit:** Eine CIDR-Freigabe ist keine Anmeldung: Jeder Rechner\nim freigegebenen Netz könnte Updates anstoßen. Deshalb nur für ein\nvertrauenswürdiges, isoliertes Admin-Netz verwenden. Der HTTP-Zugang\nist ohne zusätzliche Absicherung nicht verschlüsselt.
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

## Reproduzierbarer Hardwaretest (bereits durchgeführt; weitere Prüfungen offen)

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
