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
