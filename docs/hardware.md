# Hardware und Verdrahtung

## ESP32-C3 SuperMini + I²S MEMS Mikrofon

| Mikrofon | ESP32-C3 |
| --- | --- |
| SCK | GPIO6 |
| WS | GPIO3 |
| SD | GPIO10 |
| L/R | GND |
| VDD | 3V3 |
| GND | GND |

Bisheriger Tischaufbau auf Breadboard, Versorgung ausschließlich über USB. Beim Erstanschluss der C3-Boards war es erforderlich, **BOOT beim Einstecken** gedrückt zu halten, um die Programmierung zu ermöglichen.

## Ladeelektronik

HW-373 V1.2 / TP4056-artiges 1S-USB-C-Lademodul mit Schutz-ICs: B+/B- für Akku, OUT+/OUT- für Verbraucher. **Der Ausgang ist keine geregelte 3,3-V-Spannung.** Genaue Schutzfunktionen und Ladestrom am konkreten Board verifizieren. Ein TP4056-Ladeboard ist nicht automatisch für gleichzeitigen Lade- und Lastbetrieb mit Power-Path-Management geeignet.

## Spannungsregler

Vorhanden: HW-187 MINI360 (Step-Down, nicht geeignet für 3,0–4,2 V Einzelzelle), zusätzlich ein AP63203-basiertes Abwärtswandlermodul. **Noch kein geeignetes geregeltes 3,3-V-Netzteil für den vollen 18650-Entladebereich vorhanden.** Gesucht: stromsparender 3,3-V-Buck-Boost mit ausreichenden ESP32-Sendespitzen, geprüftem Startverhalten und niedrigem Ruhestrom. 18650 nie direkt auf 3V3-Pin legen.

## Nächste Hardwareaufgaben

Akkuschutz und Abschaltung testen; Ladestrom an die Zelle anpassen; sauber geregelte Versorgung beschaffen; Mikrofon und Buzzer messen; Ruheleistung / reale Akkulaufzeit messen. Bei unbeaufsichtigtem Li-Ion-Betrieb sind zusätzliche Sicherheits- und Temperaturprüfungen erforderlich.
