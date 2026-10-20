# Smoke Listener Mesh

Experimentelles, akustisches Zusatz-Benachrichtigungssystem für **unveränderte, eigenständig funktionierende Rauchwarnmelder** mit ESP32-C3, INMP441 und perspektivisch ESP-NOW-Weiterleitung.

> **Sicherheitsgrenze:** Dieses Hobbyprojekt ist **keine Brandmeldeanlage**, kein zertifizierter Rauchwarnmelder und kein Ersatz für normgerechte Rauchwarnmelder. Alarm-Erkennung, Funkübertragung und Energieversorgung können ausfallen. Original-Rauchmelder niemals öffnen, elektrisch anzapfen oder verändern. Keine sicherheitsrelevante Alarmierung von diesem Prototyp abhängig machen.

## Entwicklungsstand

| Version | Funktion | Status |
| --- | --- | --- |
| v0.3.1 | I²S-Mikrofon, Ton-/Gruppen-Diagnose | Auf Tischaufbau erprobt |
| v0.4.0 | Zwei ESP32-C3 senden/empfangen ESP-NOW-Testbroadcasts | Erfolgreich getestet |\n| v0.5.0 | Paketweiterleitung, TTL, Duplikaterkennung, Heartbeats | Implementiert, noch nicht getestet |

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
- [ESP-NOW-Funktest v0.4.0](firmware/mesh-test/mesh-test.ino)\n- [Experimentelle ESP-NOW-Weiterleitung v0.5.0](firmware/mesh-v0.5.0/mesh-v0.5.0.ino)

Beide Sketche sind unabhängig und können in der Arduino IDE mit Espressif-Arduino-Core betrieben werden. Zusätzliche Libraries sind nicht nötig; der Core stellt I²S und ESP-NOW bereit. Die Funk-Testpakete sind unverschlüsselt und dürfen **keine Sicherheitsalarme auslösen**.

## Ergebnisse und Planung

Siehe [Testprotokoll](docs/test-results.md) und [Hardwarehinweise](docs/hardware.md).

Als nächstes: v0.5.0 auf zwei Geräten testen, danach mit einem dritten Gerät die Weiterleitung nachweisen; robuste Audioerkennung mit tatsächlichen späteren Rauchmeldern validieren; Versorgung und Laufzeit messen; danach Weiterleitungsprotokoll mit Duplikatunterdrückung, TTL und Ausfallanzeige entwerfen.
