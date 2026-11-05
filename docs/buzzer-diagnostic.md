# HW-508 Buzzer: lokaler Diagnosetest (Feature-Branch)

**Status:** Einfacher 500-ms-Buzzertest am XIAO wurde vom Anwender erfolgreich geprüft; 2×2-Piepsmuster am 05.11.2026 auf dem Testknoten mit XIAO ESP32-C3 praktisch geprüft. Die konkrete Pinbelegung des
**HW-508 v0.2.0** noch nicht anhand des Moduls verifiziert. Vor dem
Anschließen die Modulbeschriftung prüfen. **Nicht blind den mittleren
Pin an 3V3 oder 5V anschließen.**

## Hardware / Pinplanung

Der Knoten ist ein **Seeed Studio XIAO ESP32-C3** (nicht SuperMini).
Orientierung: Rückseite, USB oben, Antenne unten.

| Funktion | XIAO | ESP32-GPIO |
| --- | --- | --- |
| INMP441 SCK | D4 | 6 |
| INMP441 WS | D1 | 3 |
| INMP441 SD | D10 | 10 |
| INMP441 L/R | GND | – |
| INMP441 VDD | 3V3 | – |
| INMP441 GND | GND | – |
| Buzzer Signal, **geplant** | D3 | 5 |
| Buzzer GND | GND | – |
| Buzzer Versorgung | erst nach Abgleich mit realem Modul | – |

Das Mikrofon wurde am 05.11.2026 nach Umstecken auf D10/GPIO10
mit zwei gültigen 640-ms-Tönen bei 3360 und 3395 Hz getestet.
Diese erfolgreiche Audio-Diagnose löste keinen Mesh-Alarm aus.

## Diagnose in der Firmware

In `firmware/mesh-v0.6.16/feature_config.h` bleibt
`FEATURE_BUZZER` **standardmäßig 0**. Erst für einen bewusst
aufgebauten Buzzer-Test mit verifizierter Verdrahtung vor dem
Kompilieren auf `1` setzen oder ein äquivalentes Build-Flag benutzen.

Serieller Monitor: **115200 Baud**, Zeilenende `Newline` oder `Both NL & CR`.

| Befehl | Wirkung |
| --- | --- |
| `BUZZER TEST` | Ein 2000-Hz-PWM-Testton auf GPIO5 für **500 ms** |
| `BUZZER 2X2` | Vier Töne zu je 500 ms: Ton – 250 ms Pause – Ton – 1000 ms Pause – Ton – 250 ms Pause – Ton |
| `BUZZER STOP` | Ton sofort beenden |

Die Firmware meldet `[BUZZER] READY pin=GPIO5 mode=serial_diagnostic_only`
und bei Test `[BUZZER] TEST freq_hz=2000 duration_ms=500 pin=GPIO5`
sowie danach `[BUZZER] STOP`. Bei init-/PWM-Fehlern erfolgt
`[BUZZER] ERROR` bzw. `INIT_FAIL`.

Das PWM-Signal ist für einen **passiven, für 3,3 V geeigneten Buzzer
mit passender Treiberstufe** gedacht. Einige HW-508-Varianten können
abweichend beschaltet bzw. aktiv sein. Erst Modell prüfen; bei
hohem Betriebsstrom einen separaten Treiber einsetzen.

## Hardwaretest 05.11.2026 – Testknoten

Seriell gemeldet: `version=0.6.16`, `gateway=0 audio=1 config_ap=0 battery=0 buzzer=1`.
`BUZZER 2X2` startete die vier Töne, anschließend meldete die Firmware
`[BUZZER] STOP`. Die Mikrofon-Diagnose erkannte vier gültige Tonereignisse:

| Dauer | Frequenz | Ergebnis |
| --- | --- | --- |
| 512 ms | 4000 Hz | `valid=1` |
| 543 ms | 3941 Hz | `valid=1` |
| 545 ms | 3941 Hz | `valid=1` |
| 512 ms | 3938 Hz | `valid=1` |

Ausgabe zweimal `[AUDIO] GROUP beeps=2 diagnostic_only=1`.
ESP-NOW Heartbeat-Empfang und Relay-Meldungen liefen während des Tests weiter.
**Manuelles `BUZZER STOP` wurde anschließend separat getestet und bestätigt.**

**Wichtig:** Obwohl die PWM-Ansteuerung 2000 Hz vorgibt, erkennt das
Mikrofon ~4 kHz. Eine Oberwelle bzw. die akustische Charakteristik des
Buzzers ist eine plausible Ursache, aber noch nicht messtechnisch
bewiesen. Eigenbeschallung des Mikrofons muss vor künftiger
Alarmkopplung berücksichtigt werden; dieser Test bestätigt ausdrücklich
**keine** Rauchmelder-Alarmerkennung.

### Separater STOP-Test über COM11

Über `pyserial` wurde `BUZZER 2X2` gestartet und nach
**1,5 Sekunden** `BUZZER STOP` gesendet. Im Log standen zwei gültige
Audioerkennungen (513 ms bei 3150 Hz und 512 ms bei 3269 Hz), gefolgt von
`[BUZZER] STOP`. Danach waren keine weiteren Pieptöne im übermittelten
Testlog zu sehen. Das bestätigt das vorzeitige Abschalten im getesteten
Ablauf. Die STOP-Meldung unmittelbar *vor* `PATTERN 2X2` entsteht durch
das Zurücksetzen eines gegebenenfalls laufenden Musters beim Neustart.

### Sicherheitsgrenzen

- Kein Ton beim Booten.
- Keine automatische Buzzer-Auslösung durch Audio, Heartbeat, Mesh oder OTA.
- Keine Fernsteuerung der Buzzer-Funktion über das Funknetz.
- Maximal 500 ms Tondauer pro Einzelton; das Muster besteht aus genau vier Tönen.
- `BUZZER STOP` unterbricht auch ein laufendes 2×2-Muster sofort.
- Der gesamte Ablauf ist ohne blockierende `delay()`-Aufrufe umgesetzt; die Mesh-Verarbeitung bleibt aktiv.
- Kein zertifizierter Alarmgeber.
- Die Entwicklung verändert bislang den `v0.6.16`-Quellbaum
  **nur im Feature-Branch**. Vor einem offiziellen Release
  Versionsnummer erhöhen und neue signierte Firmwarepakete erzeugen;
  keine andere Binärdatei als vorhandenes `0.6.16.h` ausgeben.

## Python-Regressionstests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Zusätzlich auf dem Windows-PC mit eingebautem Arduino CLI kompilieren.
Der einzelne Buzzer-Test wurde am XIAO bereits erfolgreich ausgeführt; das 2×2-Muster wurde hardwareseitig bestätigt. Die Integration in ein neues signiertes Release ist noch offen.
