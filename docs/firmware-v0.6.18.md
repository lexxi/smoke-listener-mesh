# Firmware v0.6.18 – signierte Buzzer-Profile (Release-Kandidat)

**Status: Noch nicht gebaut, signiert oder per OTA ausgerollt.**
Nur der Testknoten wird zunächst verwendet. Die bisherigen
`0.6.16`-/`0.6.17`-Quellen und signierten Releases bleiben erhalten.

## Umfang

- Neues Verzeichnis `firmware/mesh-v0.6.18` auf Basis der erfolgreichen
  v0.6.17-Hardwaretests.
- `BUZZER TEST`, `BUZZER 2X2`, `BUZZER STOP` bleiben lokale
  serielle Diagnosen auf XIAO ESP32-C3 D3/GPIO5.
- Kein automatischer Rauchalarm und kein zusätzlicher Funkpakettyp.
- `0.6.18.a-h` sind **ausschließlich** für die mit
  `-Buzzer` gebauten und mit `buzzer` signierten Varianten reserviert.
  Der Signierer verweigert `0.6.18.a-h` ohne `buzzer`.
- Variantenbuchstaben `.a-h` behalten ihre alte
  Gateway/Audio/AP-Zuordnung; `buzzer` wird zusätzlich signiert.

## Lokale Installation

Aus der bisherigen lokalen Firmwareinstallation nur die
benötigten privaten, ignorierten Header kopieren:

```powershell
Copy-Item .\firmware\mesh-v0.6.17\mesh_secrets.h .\firmware\mesh-v0.6.18\
Copy-Item .\firmware\mesh-v0.6.17\ota_public_key.h .\firmware\mesh-v0.6.18\
```

**Schlüsseldateien nicht committen und nicht hochladen.**

## 1. Tests (kein Flash, keine Signatur)

```powershell
python -m unittest discover -s tests -p "test_*.py"
.\tools\ota\build-release-matrix.ps1 -Version 0.6.18 -Buzzer -BuildOnly
```

Die acht Builds sind alle mit aktiviertem Buzzer versehen. Die
Build-Matrix schlägt für `0.6.18` ohne `-Buzzer` absichtlich fehl.

## 2. USB-Testknoten

Arduino IDE: `firmware/mesh-v0.6.18/mesh-v0.6.18.ino`.
`feature_config.h` nur lokal für den Testknoten anpassen:
`FEATURE_GATEWAY=0`, `FEATURE_AUDIO=1`,
`FEATURE_CONFIG_AP=0`, `FEATURE_BUZZER=1`.

Die `0.6.18`-USB-Testfirmware hat **keinen** Variantenbuchstaben.
Per USB auf Testknoten `000020D37E6E27AC` flashen;
Seriell 115200 Baud `BUZZER 2X2` prüfen,
vier gültige Beeps und zwei `GROUP beeps=2`-Meldungen abwarten,
ESP-NOW RX/TX/Relay kontrollieren. In der Firmware bleibt
`diagnostic_only=1`.

## 3. Signierung erst nach USB-Prüfung

Offline die bereits lokal vorhandenen privaten Schlüssel verwenden.
`-Buzzer` ist Pflicht; das Ergebnis muss mit
`sign_release.py verify` bzw. `prepare_transfer.py` geprüft
werden. Die Build-Matrix signiert standardmäßig für die in
`web/data/node_targets.json` eingetragenen maximal fünf
freigegebenen Empfänger. **Vor einem echten OTA ausdrücklich
sicherstellen, dass nur der Testknoten als Ziel verwendet wird.**
Für den Test kann eine eigene, separate Ziel-Datei über
`-TargetsFile` angegeben werden. Der Gateway ist kein OTA-Empfänger.

Ziel: den Audio+Buzzer-Build `0.6.18.b` zunächst auf
`Testknoten` testen, OTA-Staging und BOOT-Verifikation kontrollieren.
Keine anderen Knoten anfassen, bevor der Test erfolgreich war.

**Hinweis:** Wegen des Versionsvergleichs darf dieselbe Kennung
`0.6.18.b` nicht für einen zweiten, abweichenden Build wiederverwendet
werden. Ein weiterer Funktionsstand benötigt eine neue Version.

## Hardwaretestergebnis – Testknoten (USB)

Der lokale USB-Test auf `000020D37E6E27AC` war erfolgreich:

- Boot meldet `version=0.6.18`, `gateway=0 audio=1 config_ap=0 battery=0 buzzer=1`.
- `BUZZER 2X2` lief auf GPIO5 mit 2000 Hz, nominell viermal 500 ms.
- Vier gültige `[AUDIO] BEEP`-Ereignisse: 512 ms/3562 Hz,
  512 ms/3750 Hz, 544 ms/3647 Hz, 512 ms/3750 Hz;
  `match_pct=100 valid=1`.
- Zwei `[AUDIO] GROUP beeps=2 diagnostic_only=1`,
  automatischer `[BUZZER] STOP`.
- Empfang und Relay von `1OG`, `Garage`, `FZRaum` und
  dem USB-Gateway; jeweils `AUTH=OK` in den empfangenen Paketen
  und ältere Versionen `0.6.16.h`/`0.6.16.c` kompatibel.
- Ein anfängliches ungültiges BEEP-Ereignis (448 ms, 0 Hz,
  `valid=0`) wurde erkannt und korrekt nicht als gültiger Beep gezählt.

**Einschränkung:** Der 2000-Hz-PWM-Buzzer wird akustisch im
Bereich 3562–3750 Hz erkannt. Die Frequenzdiskrepanz wurde nicht
vermessen oder aufgeklärt; dieser Test bestätigt nur die
Diagnosefunktion, keine Rauchalarm-Sicherheit. Es liegt noch **kein**
positiver Bericht für signiertes OTA-Staging, Boot-Aktivierung oder
Rollback vor. Ebenso ist ein kompletter Python-Testlauf für diesen
PR noch separat zu bestätigen.

## Release-Gate: Tests bestätigt

Der lokale vollständige Python-Unittest-Lauf wurde vom Anwender als **OK** bestätigt.
Alle acht BuildOnly-Profile mit `-Version 0.6.18 -Buzzer` wurden erfolgreich gebaut:

| Variante | Profil | BIN-Bytes |
| --- | --- | ---: |
| `.a` | core | 992864 |
| `.b` | audio | 1019904 |
| `.c` | gateway | 1002608 |
| `.d` | hybrid | 1029648 |
| `.e` | core_ap | 1044016 |
| `.f` | audio_ap | 1071056 |
| `.g` | gateway_ap | 1053376 |
| `.h` | hybrid_ap | 1080416 |

Diese Bestätigung betrifft Build und USB-Diagnose; ein signiertes Paket und Remote-OTA sind **noch nicht getestet**.
