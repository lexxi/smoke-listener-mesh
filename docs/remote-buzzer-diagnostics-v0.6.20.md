# v0.6.20: Remote-Buzzer-Diagnose – Hardwaretest bestanden (07.11.2026)

## Ergebnis

Die Remote-Buzzer-Steuerung wurde auf dem Testknoten **erfolgreich**
über die normale piCore-LAN-Webapp getestet.

| Komponente | Getesteter Stand |
| --- | --- |
| Testknoten | `000020D37E6E27AC`, Firmware `0.6.20.b`, Audio + Buzzer |
| USB-Gateway | `00000CEC7E6E27AC`, Firmware `0.6.20.c`, per USB aktualisiert |
| Host | Raspberry Pi 2 / piCore 17.0.1, Webapp Port 8088 |
| Admin-Netz | `192.168.98.0/24`, konfigurierbar über `SMOKE_LAN_NODE_ADMIN_IPS` |
| Browser | Normale LAN-Oberfläche `/nodes`, kein SSH-Tunnel |
| `BUZZER_TEST` | Einzelton hörbar, Test erfolgreich |
| `BUZZER_2X2` | Vier Pieptöne hörbar, Empfangsbestätigung `result=0` |

Die 2×2-Wiedergabe wurde erst akustisch bestätigt und danach nach einem
Parser-Fix auch im Managementprotokoll sauber bestätigt:

```text
[REMOTE] STATUS ... version=0.6.20.b name=Testknoten
[REMOTE] STATUS ... action=BUZZER_2X2 result=0 ... state=2 peer=True version=0.6.20.b
[REMOTE] BUZZER START ACCEPTED target=000020D37E6E27AC action=BUZZER_2X2; audible output not verified
[WEB] Gateway-Logger wieder freigegeben.
```

Die Ausgabe `audible output not verified` ist korrekt: Das Protokoll
bestätigt den Start, nicht den akustischen Nachweis. Die tatsächliche
Hörbarkeit wurde beim manuellen Test separat festgestellt.

## Fehleranalyse und Korrektur

Beim ersten 2×2-Test waren die vier Pieptöne hörbar, aber die Webapp
meldete einen Timeout. Ursache war der Python-Parser
`tools/ota/remote_ota.py`: Die Regex `[A-Z_]+` akzeptierte keine
Ziffern und verwarf die gültige Antwortaktion `BUZZER_2X2`.

Korrektur in `main`:
- Aktionsmuster auf `[A-Z0-9_]+` erweitert (Commit `7175c86`).
- Regressionstest `tests/test_remote_mgmt_reply_digits.py`
  ergänzt (Commit `e0d1150`).
- Auf piCore aktualisiert und neu gestartet. Die Wiederholung bestätigte
  `BUZZER_2X2 result=0`.

**Kein erneuter Firmware-Flash für diesen Parser-Fix erforderlich.**

## Befehle und Grenzen

- `BUZZER_TEST` (Management-Aktion 11): 2.000 Hz, 500 ms.
- `BUZZER_2X2` (Aktion 12): vier 2.000-Hz-Töne als zwei Gruppen.
- Befehle laufen über das bestehende HMAC-authentifizierte ESP-NOW-
  Management mit vertrauenswürdigem Gateway und einmaligem Nonce.
- Bei `FEATURE_BUZZER=0`, während ungeeigneter OTA-Zustände oder
  bei bereits laufendem Test wird der neue Test nicht gestartet.
- **Keine** echten Rauchalarm-Pakete durch diese Diagnose.

Der Audiofilter arbeitet im Bereich **3.000–3.450 Hz**. Die hier
verwendeten **2.000 Hz** sind nur ein Buzzer-Funktionstest und
bestätigen **nicht** die INMP441-Audioerkennung.

## Bedienung in der normalen Webapp

1. `SMOKE_WEB_LAN=1` und Admin-Freigabe setzen, z. B.
   `SMOKE_LAN_NODE_ADMIN_IPS='192.168.98.0/24'` in
   `/mnt/mmcblk0p3/smoke-mesh/data/web.env`.
2. Webapp nach einer Konfigurationsänderung neu starten.
3. `http://192.168.98.39:8088/nodes` vom freigegebenen LAN-Client öffnen.
4. Gateway und Testknoten `000020D37E6E27AC` auswählen.
5. „Buzzer: Testton“ beziehungsweise „Buzzer: 2×2“ auslösen.
6. Ergebnisprotokoll prüfen. Der Logger wird bei Benutzung des
   USB-Gateways automatisch pausiert und danach freigegeben.

Alternativ können die Diagnoseaktionen auch bei bestehender
`SMOKE_LAN_LOGGER_IPS`-Freigabe für den betreffenden Client zugelassen
sein. Die CIDR-Freigabe ist eine **IP-basierte Zugriffsbeschränkung,
keine Benutzeranmeldung**. Nur in einem vertrauenswürdigen LAN verwenden.
OTA-Upload und -Aktivierung werden dadurch nicht freigegeben.

## Build und signierte Releases

Ein einziger reproduzierbarer Aufruf über
`tools/ota/build-0620-dual.ps1` erzeugte zwei getrennte signierte
Firmware-Releases. Beide wurden danach separat erfolgreich auf Signatur
und Image geprüft:

| Profil | Version | Größe | Signiertes Ziel |
| --- | --- | ---: | --- |
| Audio+Buzzer | `0.6.20.b` | 1.019.952 Bytes | `000020D37E6E27AC` |
| Gateway | `0.6.20.c` | 991.312 Bytes | `00000CEC7E6E27AC` |

Die Aktualisierung des Testknotens über piCore Remote-OTA wurde mit
`state=2` (VALID), `peer=True`, `running=boot=0` bestätigt.
Der Gateway wurde anschließend per USB aktualisiert und meldete
`0.6.20.c` im Mesh-Monitor.

## Noch offen

- `AUDIO_STATUS`: Mikrofonbereitschaft, Mess-/Fehlerzähler über Mesh abrufen.
- `AUDIO_RESET`: Diagnosezähler gezielt zurücksetzen.
- Passendes 3.200-Hz-Testmuster für die Audio-Gruppenerkennung.
- Audio-Erkennung, Alarmweiterleitung und Rollback unter Fehlerbedingungen
  sind mit dem Buzzer-Test **nicht** validiert.

Diese experimentelle Testinstallation ist **keine zertifizierte
Brandmeldeanlage**.
