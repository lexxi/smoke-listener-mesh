# Smoke Listener Mesh

Experimenteller ESP32-C3-basierter Mesh-Zusatz für die **akustische Erkennung unveränderter Rauchwarnmelder**. Derzeit sind Mikrofon-Prototypen, ESP-NOW-Heartbeats, authentifizierte Funkweiterleitung, ein serieller Dauerlogger und ein lokales Web-Dashboard vorhanden. **Die Audio-Alarmdetektion ist noch nicht mit der aktuellen Mesh-Firmware zu einem validierten Gesamtsystem integriert.**

> **Sicherheit:** Keine Brandmeldeanlage, kein zertifizierter Rauchwarnmelder und kein Ersatz für normgerechte Rauchwarnmelder. Ein `HEARTBEAT` sagt nur etwas über den beobachteten Funkkontakt aus, nicht über die Funktion des Mikrofons oder die Erkennung eines Brandalarms. Niemals als alleinigen Alarmweg verwenden. Rauchwarnmelder nicht öffnen oder verändern.

## Aktueller Stand (03.11.2026)

| Komponente | Version | Stand |
| --- | --- | --- |
| Mikrofon-/Ton-Diagnose | v0.3.1 | Pieptöne im Tisch- und Entfernungstest erkannt; keine vollständige produktive Alarmerkennung |
| ESP-NOW und Weiterleitung | v0.4.0–v0.5.x | Broadcasts, TTL, Duplikatunterdrückung, Heartbeats |
| Mesh-Firmware | **v0.5.5** | Protokoll 3, HMAC-SHA256, signierter Knotenname; zwei Knoten getestet und 03.11. im Gebäudelog beobachtet |
| Serieller Logger | `scripts/logging.py` | Fortlaufendes Mitschreiben ohne Zeitlimit, Reconnect |
| Web-Dashboard | **v0.3.0** | Knotenstatus, USB-Logger-Erkennung, Relay-Wege und getrennte Testläufe; auf Windows gestartet |
| Hardwaregehäuse | geplant | C3, INMP441, Buzzer, 18650-Akku, Antenne; mechanische Maße noch offen |

Frühere Implementierungen und Dokumente bleiben zur Nachvollziehbarkeit im Repository. Der **aktuelle Einstiegspunkt** ist `firmware/mesh-v0.5.5/mesh-v0.5.5.ino`, nicht v0.5.1.

## Firmwareversionen im Mesh (Entwicklung v0.6.10)

Die vorhandene Windows-Webapp zeigt unter **Knotenübersicht** nun pro Knoten eine Firmwareversion, sofern diese als authentifizierte Telemetrie gemeldet wurde. Alte Firmware meldet noch keine Version und erscheint korrekt als **Unbekannt**.

Die neue Firmware `firmware/mesh-v0.6.10/mesh-v0.6.10.ino` behält Protokoll 3 und das bestehende 92-Byte-Paket bei. Sie verwendet vier bisher ungenutzte, HMAC-geschützte Bytes im Namensfeld für Major/Minor/Patch. Ein v0.6.10-USB-Logger kann daher Versionen anderer aktualisierter Knoten ausgeben und seine eigene Version über `[TX]` anzeigen.

**Status:** v0.6.10 wurde in GitHub vorbereitet, **noch nicht kompiliert oder auf Hardware getestet**. 1OG bleibt auf der erfolgreich bestätigten v0.6.9; für den ersten Test eignet sich Garage (COM14).

Anleitung: [Firmware-Telemetrie v0.6.10](docs/mesh-firmware-version-telemetry-v0610.md).

## Fern-OTA per Webapp (experimentell: v0.6.11/v0.6.12)

**Ziel:** einmalig v0.6.11 über USB auf die C3 installieren, danach Firmwareversionen durch ein signiertes Release-Paket und die Weboberfläche verwalten. Ein C3 bleibt am Webserver als USB-zu-ESP-NOW-Gateway angeschlossen. Ein eigener USB-Anschluss an jedem Zielknoten ist dann für reguläre Updates nicht mehr nötig.

**Implementiert (noch nicht auf Hardware getestet):**
- `firmware/mesh-v0.6.11/`: HMAC-authentifizierte, auf Garage/Kueche als Gateway begrenzte ESP-NOW-Steuerung für Status, Flash-Freigabe, Readback, Bootaktivierung, Neustart und Bestätigung; wechselnde Boot-Challenge gegen Wiederholungen.
- `firmware/mesh-v0.6.12/`: erster Test-Build für ein nachfolgendes Upgrade ohne USB am Ziel; Fernsteuerung bleibt enthalten.
- `tools/ota/remote_ota.py` und `web/remote.py`: gatewaybasierte Jobs für Funkstatus, nur Flashstaging oder vollständigen Updateversuch inklusive Rollback-Kontrolle.
- `web/logger_control.py`: Web-Garage-Logger auf COM14 wird bei OTA via Garage automatisch pausiert und wieder gestartet.
- `tools/ota/prepare-web-bundle.ps1`: ein ZIP-Paket mit EINER BIN und vier knotenspezifisch signierten Manifesten erstellen. Die Webapp verifiziert sämtliche Manifeste und bietet die einzelnen Ziel-Releases an.

**ACHTUNG:** Die frühere OTA-Hardwarevalidierung gilt nur für den lokalen Mechanismus, **nicht** für die hier neue Remote-Steuerung. **v0.6.11 noch nicht auf alle Geräte aufspielen**. Erst Garage und 1OG kompilieren, USB-testen, danach das echte Web-OTA auf v0.6.12 prüfen. Insbesondere muss die PENDING_VERIFY-/Rollback-Kette auf der Hardware validiert werden. Ein fehlgeschlagenes Image kann trotz Watchdog eine USB-Rettung nötig machen.

[Schrittweise Anleitung und Sicherheitsgrenzen](docs/remote-ota-one-time-usb-migration.md).

## OTA per Weboberfläche für 1OG v0.6.10 (Staging)

Die Seite **http://127.0.0.1:8088/ota** führt nun durch drei Schritte: **signiertes Release hochladen → Ziel/Version auswählen → Firmware übertragen und SHA-256 kontrollieren**. Für den ersten kontrollierten Hardwaretest ist nur **1OG: v0.6.9 (app0) → v0.6.10 (app1)** freigeschaltet.

**Beide Geräte müssen dabei weiterhin per USB am Windows-PC hängen:** Kueche als Gateway an COM12 und 1OG zur lokalen Autorisierung an COM15. Die Webapp startet **keinen Bootwechsel, Neustart oder BOOT CONFIRM**. Ein Web-OTA-Staging-Erfolg bedeutet nicht, dass die neue Firmware bereits läuft.

Zum Erstellen des signierten 1OG-Releases dient `tools/ota/prepare-web-release.ps1 -Node 1OG -Version 0.6.10`; der private Signierschlüssel bleibt lokal.

Die Funktion ist **implementiert, aber noch nicht auf der Hardware validiert**. [Windows-Testanleitung](docs/web-ota-stage-1og-v0610.md).

## Release-Verwaltung im Webinterface (Stand 04.11.2026)

Die bereits laufende Flask-Weboberfläche unter **http://127.0.0.1:8088/ota** kann nun eine kompilierte Firmware-BIN und das zugehörige signierte JSON-Manifest über den Browser entgegennehmen. Erst nach ECDSA-P256-Signaturprüfung, ESP32-C3-Imageprüfung und SHA-256-Abgleich wird das Release lokal unter `web/data/releases/` gespeichert (nicht auf GitHub). Der private Signierschlüssel bleibt auf dem Build-PC.

Die frühere fest verdrahtete Übertragung v0.6.9 für 1OG ist **deaktiviert**. Die Release-Verwaltung ist derzeit **nur Upload, Prüfung und Ablage**; OTA-Verteilung und Bootaktivierung folgen erst nach separatem Test.

[Windows-Anleitung zur Release-Verwaltung](docs/ota-release-library-windows.md).

## OTA-Entwicklung (Stand 03.11.2026)

- **v0.5.6 auf Hardware getestet:** Direkter Test 1OG → Garage: 16/16 Blöcke. Relay-Pfad Keller_Abgang → Garage → 1OG: erfolgreich 16/16 ACKs mit `hops=1`; ohne Garage 0/16; nach Wiedereinschalten erst im zweiten Anlauf 16/16. Paketverluste treten auf. Das ist ein **RAM-Transporttest, kein Firmware-Update**.
- **v0.5.7 im Repository, Build/Hardwaretest offen:** längere RAM-only-Tests mit 1–4096 Blöcken, mehr Diagnose und Wiederholungen. Anleitung: [v0.5.7](docs/mesh-v0.5.7.md).
- **v0.5.8 (Quellcode, Build noch offen):** [OTA-Partitionsprüfung](docs/mesh-v0.5.8.md) mit `OTA PREFLIGHT`; noch kein Flash-Schreibzugriff und kein drahtloses Firmwareupdate.
- **Vorbereitung echter OTA-Updates:** [Firmware-Signaturwerkzeug](docs/ota-signing.md) für zielgebundene, mit ECDSA-P-256 signierte Firmwaremanifeste hinzugefügt. Der Empfänger und der eigentliche Flash-Workflow fehlen noch.
- **Echte Image-Datei (Offline-Vorbereitung):** [signierte Firmware in 96-Byte-Transferblöcke aufbereiten](docs/ota-real-image-preparation.md), inklusive Signatur- und SHA-256-Prüfung am PC und manipulationsbezogener Unittests. **Noch keine Übertragung der Datei über Funk und kein OTA-Flashen.**
- **v0.5.9 (Quellcode, Build/Hardwaretest noch offen):** [Echte Firmwaredateien über USB und ESP-NOW streamen](docs/mesh-v0.5.9.md), inklusive SHA-256-Prüfung auf dem Empfänger. **Keine Flash-Schreibzugriffe, Signaturprüfung noch nicht auf dem ESP32.**
- **v0.6.0 (auf Kueche und 1OG getestet):** [Signaturprüfung direkt am Zielgerät](docs/mesh-v0.6.0.md): ein gültiges ECDSA-P-256-Manifest wurde akzeptiert, eine absichtlich manipulierte Signatur abgelehnt. **Kein Flash-Schreiben.**
- **v0.6.1 (neu, noch NICHT kompiliert oder hardwaregetestet):** [Downgrade-Prüfung und ausdrücklich freizugebendes Schreiben in den inaktiven OTA-App-Slot](docs/mesh-v0.6.1.md). **Keine Bootumschaltung und kein automatischer Rollback.** Nicht ohne die dokumentierten Tests produktiv verwenden.
- **v0.6.2 (Upgrade-Kandidat, noch nicht kompiliert):** [Signiertes Image für den positiven v0.6.1→v0.6.2-Test](docs/mesh-v0.6.2.md). Kueche und 1OG bleiben zunächst auf v0.6.1. Erst Signatur und RAM-only-Transfer prüfen; Flash-Staging noch nicht starten.
- **v0.6.3 (Rollback-Diagnostik, noch nicht kompiliert):** [Boot-/Rollback-Fähigkeiten prüfen](docs/mesh-v0.6.3.md), ohne die Bootpartition zu wechseln. Zunächst nur kompilieren; auf 1OG liegt derzeit die getestete v0.6.2 in der inaktiven Partition.
- **Vollständige automatische OTA-Installation ist noch nicht fertig.** Es fehlen kontrollierte Bootaktivierung, Bootbestätigung, Recovery und Rollback. Details: [OTA-Roadmap](docs/mesh-ota.md).

## Hardware

Aktueller Testaufbau: ESP32-C3 SuperMini mit INMP441 (I²S), USB-Stromversorgung. Für den späteren Knoten vorgesehen: **Buzzer, 18650-Li-Ion-Akku, Lade-/Schutzelektronik, geregelte 3,3-V-Versorgung und geeignete 2,4-GHz-Antenne**. Antennenanschluss und Buzzer-Treiber sind abhängig von der konkreten Hardware noch zu prüfen.

| INMP441 | ESP32-C3 |
| --- | --- |
| SCK | GPIO6 |
| WS | GPIO3 |
| SD | GPIO10 |
| L/R | GND |
| VDD | 3V3 |
| GND | GND |

**Akku nicht ungeprüft an den 3V3-Pin anschließen.** Ein TP4056-artiges Lademodul allein stellt keine geregelten 3,3 V bereit. Der vorhandene HW-187 MINI360 eignet sich nicht als 3,3-V-Regler für den gesamten Spannungsbereich einer einzelnen 18650. Details unter [Hardware und Verdrahtung](docs/hardware.md).

## Firmware v0.5.5 flashen

1. In `firmware/mesh-v0.5.5/` die private Datei `mesh_secrets.h` aus der vorhandenen v0.5.4-Konfiguration übernehmen. [Beispiel](firmware/mesh-v0.5.5/mesh_secrets.h.example). Geheimschlüssel und AP-Passwort **nicht committen**.
2. `firmware/mesh-v0.5.5/mesh-v0.5.5.ino` mit der Arduino IDE öffnen. Board: **ESP32C3 Dev Module**, USB CDC On Boot einschalten.
3. Alle miteinander kommunizierenden Mesh-Geräte auf v0.5.5 aktualisieren. **Protokoll 3 ist nicht kompatibel mit v0.5.4 (Protokoll 2)**.
4. Serielle Ausgabe prüfen: `[RX] name=... origin=... via=... hops=... AUTH=OK`, `[TX]`, `[RELAY]`, `[STATS]`.

**Namen einstellen:** Bei laufendem Knoten BOOT ungefähr 5 Sekunden halten, mit dem Konfigurations-WLAN `SmokeListener-XXXXXX` verbinden, dann `http://192.168.4.1` öffnen. Namen mit 1–24 ASCII-Zeichen (Buchstaben, Ziffern, `-`, `_`) speichern. Das WLAN-AP-Passwort muss privat gesetzt sein und mindestens 12 Zeichen haben. Der AP unterbricht ESP-NOW vorübergehend; nach ungefähr fünf Minuten ohne Webzugriff erfolgt ein Neustart. Namen bleiben bei normalem Flashen üblicherweise in NVS, **nicht** bei vollständigem Flash-Erase. Der übertragene Knotenname ist **authentifiziert, aber nicht verschlüsselt**.

## Knoten und Standorte

Die bekannte Zuordnung steht in [`config/nodes.csv`](config/nodes.csv):

| MAC-Endung | Standort in CSV | Zuletzt im Log beobachteter Name / Funktion |
| --- | --- | --- |
| `7E:E3:A0` | FZRaum | `Keller_Abgang` |
| `7F:45:94` | Kueche | `Kueche` |
| `7C:63:10` | 1OG | **aktuell USB-Logger** |
| `7D:FE:58` | Garage | `Garage` |
| `7E:D3:20` | PC-Logger | früherer Logger, aktuell nicht im Mesh aktiv |

Ein Standort aus `nodes.csv` und ein vom Gerät gesendeter Name sind **unterschiedliche Daten**. Der Webservice zeigt beides an. Die Rolle des USB-Loggers wird dynamisch aus dessen `[TX]`-Zeilen ermittelt.

## Seriellen Dauerlogger starten (Windows)

Im **Repository-Stammverzeichnis**:

```powershell
py -m pip install pyserial
py .\scripts\logging.py --port COM15
```

COM-Port entsprechend dem eigenen System anpassen. Ausgabe standardmäßig nach `log/mesh_YYYYMMDD_HHMMSS.log`. Ohne `--hours` läuft der Logger unbegrenzt und wird mit `Strg+C` beendet. Mit `--hours 6` ist ein begrenzter Test möglich, mit `--out PFAD` ein frei gewählter Dateiname. Bei USB-Unterbrechung wird die Verbindung standardmäßig alle fünf Sekunden erneut versucht. Für einen **neuen Testlauf** einen **neuen Logdateinamen** verwenden. Der Arduino Serial Monitor darf den Port nicht parallel öffnen.

Wenn der Logger aus `scripts/` heraus gestartet wird, kann die Datei in `scripts/log/` liegen. Der Webservice erkennt beide Orte.

## Smoke Mesh Monitor v0.3.0

Ein zweites PowerShell-Fenster öffnen; den seriellen Logger **weiterlaufen lassen**:

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
py -m pip install -r .\web\requirements.txt
py .\web\app.py
```

Im Browser: **http://127.0.0.1:8088**

Der Webservice öffnet den COM-Port **nicht** selbst. Er liest die vorhandenen `mesh_*.log`-Dateien aus `log/`, `logs/` oder `scripts/log/` und speichert ausgewertete Einträge lokal in `web/data/mesh.db` (in `.gitignore` ausgeschlossen).

Funktionen:
- Automatisch erkannte Logger-Rolle aus `[TX]`; externe Knoten aus authentifizierten `[RX]`-Einträgen.
- Erreichbarkeit: **Online** bis 45 Sekunden, **überfällig** bis 120 Sekunden, danach **Offline**. Bei historischen Tests ist das kein historischer Erreichbarkeitsstatus.
- Angezeigter Name, MAC, Standort, letzter Empfang, Hops, RSSI der **letzten Funkstrecke**, direkte und über Relay empfangene Pakete.
- Schematische Bereichsübersicht, Relay-Tabelle, letzte Meldungen.
- **Testlauf-Auswahl:** standardmäßig zuletzt geänderte Logdatei; ältere Dateien separat auswählbar. Statistiken werden pro ausgewählter Datei berechnet, nicht aus allen historischen Logs gemischt.

Die Webanwendung läuft standardmäßig nur auf `127.0.0.1` und **hat keine Anmeldung**. `--host 0.0.0.0` nur in einem geschützten lokalen Netz verwenden. Für den Prototyp ist kein öffentlicher Internetzugang vorgesehen.

Ausführliche Anleitung und Grenzen: [`web/README.md`](web/README.md).

### Log auswerten ohne Weboberfläche

```powershell
py .\scripts\analyze_mesh_log.py .\log\mesh_YYYYMMDD_HHMMSS.log --nodes .\config\nodes.csv
```

Die Auswertung kann empfangene Pakete, direkt/Relay, beobachtete Sequenzlücken und RSSI bei **Direktempfang** zusammenfassen. Aus den Paketen allein lässt sich keine Ende-zu-Ende-Zustellgarantie ableiten.

## Firmware drahtlos aktualisieren: ESP-NOW-OTA (in Entwicklung)

Ziel: Firmware vom PC über den angeschlossenen Logger-C3 an ausgewählte
Mesh-Knoten schicken, **ohne an den Zielknoten den BOOT-Taster zu drücken**.
Dabei sollen auch Relay-Verbindungen funktionieren.

**Stand 03.11.2026: OTA-Transport-Prototyp v0.5.6 eingecheckt, noch nicht kompiliert oder auf Hardware getestet.** v0.5.5 enthält keinen
OTA-Empfänger. Für die spätere OTA-fähige Firmware ist mindestens **ein**
USB-Flash pro Gerät erforderlich. Die Flash-Partitionierung, eine
authentifizierte und verlusttolerante Übertragung mit Ziel-Bestätigung,
Firmware-Signaturprüfung und Rückfallverhalten sind vor dem ersten
drahtlosen Firmware-Flash zu implementieren und mit einem Testgerät zu prüfen.

Die technische Checkliste und die Meilensteine stehen in
[docs/mesh-ota.md](docs/mesh-ota.md). Der erste **RAM-only-Transporttest**
steht in [Firmware v0.5.6](firmware/mesh-v0.5.6/mesh-v0.5.6.ino)
mit [Testanleitung](docs/mesh-v0.5.6.md) und
[Windows-Testskript](scripts/ota_test.py). Er überträgt nur 16 synthetische
Datenblöcke, nicht eine echte Firmware; **kein Flash-Schreibzugriff**.
Ein **rein lokales Prüftool**, das keine Firmware schreibt, steht unter
[tools/ota/check_image.py](tools/ota/check_image.py). Beispiel (OTA-Slotgröße
**nur als Beispiel**, den tatsächlich eingestellten Wert einsetzen):

```powershell
py .\tools\ota\check_image.py .\firmware.bin --ota-slot-bytes 0x140000
```

## Testergebnisse und offene Aufgaben

- **03.11.2026:** Zwei-Knoten-Test mit Abstand rund 1 m: Knotenname `Kueche`, `AUTH=OK`, `hops=0` und erfolgreiche `[RELAY]`-Ausgaben sichtbar.
- **03.11.2026:** Mehrknoten-Log: `Keller_Abgang`, `Garage` und `Kueche` wurden von `1OG` als Logger empfangen; sowohl direkte (`hops=0`) als auch weitergeleitete (`hops=1` und `hops=2`) Pakete beobachtet.
- **Noch nicht nachgewiesen:** Ein Quellknoten ist ausschließlich über Relay erreichbar. Dazu Relay aus-/einschalten und Direktpfad separat ausschließen.
- **Noch offen:** Audio-Erkennung in die aktuelle Mesh-Firmware integrieren und mit unterschiedlichen Alarmmustern prüfen; Energieverbrauch und 18650-Laufzeit messen; Buzzer, Antenne, Ladeelektronik und 3D-Gehäuse fertig entwickeln; Langzeittest je Testlauf systematisch dokumentieren.

Weitere historische Messergebnisse: [`docs/test-results.md`](docs/test-results.md). Ältere Unterlagen zu [v0.5.1](docs/mesh-v0.5.1.md) und zum [passiven Logger](docs/mesh-logger.md) beschreiben frühere Entwicklungsstände.
