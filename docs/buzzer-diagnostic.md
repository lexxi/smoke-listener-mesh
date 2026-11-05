# HW-508 Buzzer: lokaler Diagnosetest (Feature-Branch)

**Status:** Code vorbereitet; Hardwaretyp und konkrete Pinbelegung des
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
| `BUZZER TEST` | 2000-Hz-PWM-Testton auf GPIO5, **max. 500 ms** |
| `BUZZER STOP` | Ton sofort beenden |

Die Firmware meldet `[BUZZER] READY pin=GPIO5 mode=serial_diagnostic_only`
und bei Test `[BUZZER] TEST freq_hz=2000 duration_ms=500 pin=GPIO5`
sowie danach `[BUZZER] STOP`. Bei init-/PWM-Fehlern erfolgt
`[BUZZER] ERROR` bzw. `INIT_FAIL`.

Das PWM-Signal ist für einen **passiven, für 3,3 V geeigneten Buzzer
mit passender Treiberstufe** gedacht. Einige HW-508-Varianten können
abweichend beschaltet bzw. aktiv sein. Erst Modell prüfen; bei
hohem Betriebsstrom einen separaten Treiber einsetzen.

### Sicherheitsgrenzen

- Kein Ton beim Booten.
- Keine automatische Buzzer-Auslösung durch Audio, Heartbeat, Mesh oder OTA.
- Keine Fernsteuerung der Buzzer-Funktion über das Funknetz.
- Maximal 500 ms Tondauer je bewusstem lokalem Testbefehl.
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
Die Hardwarefunktion bleibt bis zum tatsächlichen Test unbestätigt.
