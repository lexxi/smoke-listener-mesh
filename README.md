# Smoke Listener Mesh

Experimentelles, akustisches Zusatz-Benachrichtigungssystem für **unveränderte, eigenständig funktionierende Rauchwarnmelder** mit ESP32-C3, INMP441 und perspektivisch ESP-NOW-Weiterleitung.

> **Sicherheitsgrenze:** Dieses Hobbyprojekt ist **keine Brandmeldeanlage**, kein zertifizierter Rauchwarnmelder und kein Ersatz für normgerechte Rauchwarnmelder. Alarm-Erkennung, Funkübertragung und Energieversorgung können ausfallen. Original-Rauchmelder niemals öffnen, elektrisch anzapfen oder verändern. Keine sicherheitsrelevante Alarmierung von diesem Prototyp abhängig machen.

## Entwicklungsstand

| Version | Funktion | Status |
| --- | --- | --- |
| v0.3.1 | I²S-Mikrofon, Ton-/Gruppen-Diagnose | Auf Tischaufbau erprobt |
| v0.4.0 | Zwei ESP32-C3 senden/empfangen ESP-NOW-Testbroadcasts | Erfolgreich getestet |\n| v0.5.0 | Paketweiterleitung, TTL, Duplikaterkennung, Heartbeats | Auf drei ESP32 beobachtet |\n| v0.5.1 | Vollständige Herkunfts-ID, direkte Sender-MAC, HMAC-SHA256 für TEST/HEARTBEAT | Eingecheckt, **noch nicht auf Hardware getestet** |

## Hardware (Prototyp)

- ESP32-C3 SuperMini, Arduino IDE: **ESP32C3 Dev Module**, USB CDC On Boot enabled
- Rundes INMP441-kompatibles I²S-Mikrofon (6 Pins)
- 18650 Li-Ion und HW-373/TC4056-Lademodul mit Schutzschaltung (geplant; aktuell **USB-Versorgung**)
- HW-187 Mini360 ist **nicht** als 3,3-V-Versorgung aus einer einzelnen 18650 geeignet
- Ein passender stromsparender **3,3-V-Buck-Boost-Regler** ist noch offen
- Optional aktiver Buzzer, später Funk-Weiterleitung

## Mikrofon-Verdrahtung

| Mikrofon | ESP32-C3 |
| --- | --- |
| SCK | GPIO6 |
| WS | GPIO3 |
| SD | GPIO10 |
| L/R | GND |
| VDD | 3V3 |
| GND | GND |

Nur mit USB und Mikrofon testen, **keinen Akku parallel anschließen**.

## Firmware

- [Audio-Diagnose v0.3.1](firmware/smoke-listener/smoke-listener.ino)
- [ESP-NOW-Funktest v0.4.0](firmware/mesh-test/mesh-test.ino)\n- [Experimentelle ESP-NOW-Weiterleitung v0.5.0](firmware/mesh-v0.5.0/mesh-v0.5.0.ino)\n- [Authentifizierter Labortest v0.5.1](firmware/mesh-v0.5.1/mesh-v0.5.1.ino) – [Setup-Anleitung](docs/mesh-v0.5.1.md)

Beide Sketche sind unabhängig und können in der Arduino IDE mit Espressif-Arduino-Core betrieben werden. Zusätzliche Libraries sind nicht nötig; der Core stellt I²S und ESP-NOW bereit. Die Funk-Testpakete sind unverschlüsselt und dürfen **keine Sicherheitsalarme auslösen**.

## Ergebnisse und Planung

Siehe [Testprotokoll](docs/test-results.md) und [Hardwarehinweise](docs/hardware.md).

Als nächstes: v0.5.1 auf drei Geräten testen, danach den Relay-Weg eindeutig nachweisen; robuste Audioerkennung mit tatsächlichen späteren Rauchmeldern validieren; Versorgung und Laufzeit messen; danach Weiterleitungsprotokoll mit Duplikatunterdrückung, TTL und Ausfallanzeige entwerfen.


## Passiver Funklogger

Für den vierten ESP32-C3: [Logger-Firmware](firmware/mesh-logger-v0.1.0/mesh-logger-v0.1.0.ino), [Windows-CSV-Recorder](scripts/mesh_serial_logger.py), [Anleitung](docs/mesh-logger.md). Noch nicht auf Hardware getestet; der private Netzwerkschlüssel bleibt lokal.

## XIAO ESP32-C3: WLAN-Konfiguration (v0.5.4)

Die Firmware [mesh-v0.5.4](firmware/mesh-v0.5.4/mesh-v0.5.4.ino) unterstützt einen temporären WLAN-Access-Point zum Ändern des Knotennamens ohne erneutes Flashen. **Vor dem ersten Flashen** die lokale Datei `firmware/mesh-v0.5.4/mesh_secrets.h` aus der Beispielkonfiguration erstellen bzw. die vorhandene private Datei aus v0.5.3 übernehmen und um folgende Konstante ergänzen:

```cpp
static constexpr char MESH_CONFIG_AP_PASSWORD[] = "HIER_EIGENES_STARKES_PASSWORT";
```

**Passwortanforderung der aktuellen Implementierung: mindestens 12 Zeichen** (WPA2-AP technisch: maximal 63 Zeichen). Das Beispielpasswort `CHANGE-TO-PRIVATE-LONG-PASSWORD` wird von v0.5.4 ausdrücklich abgelehnt. Der Passwortwert wird beim Kompilieren in die Firmware eingebaut; eine nachträgliche Änderung erfordert derzeit erneutes Flashen. Den realen Schlüssel und das AP-Passwort **niemals committen**.

Zum Konfigurieren den bereits laufenden XIAO **ohne RESET** mit dem BOOT-Taster ca. 5 Sekunden gedrückt halten. Das Gerät startet einen AP `SmokeListener-XXXXXX` (die letzten sechs Hex-Zeichen der stabilen Hardware-Node-ID, unabhängig von der WLAN-MAC-Anzeige im AP-Modus) auf Kanal 6; nach Verbindung `http://192.168.4.1` im Browser öffnen und einen Namen aus 1–24 ASCII-Zeichen (Buchstaben, Ziffern, Minuszeichen, Unterstrich) speichern. Der Name bleibt in NVS erhalten. Während des AP-Modus ist ESP-NOW pausiert; nach 5 Minuten ohne Webzugriff erfolgt ein Neustart zurück ins Mesh. Nach einem Speichervorgang bei Bedarf den AP auslaufen lassen oder die Stromversorgung neu starten.

**Fehlersuche:** `[CONFIG] ERROR: set private AP password first` bedeutet, dass das Passwort fehlt, das unveränderte Beispielpasswort eingetragen ist oder weniger als 12 Zeichen umfasst. Lokale `mesh_secrets.h` im **v0.5.4-Verzeichnis** prüfen, korrigieren und neu flashen. Die Firmware ist experimentell und muss vor einem flächendeckenden Update an einem einzelnen XIAO getestet werden.
