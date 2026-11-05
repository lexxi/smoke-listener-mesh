# Firmware v0.6.17 – Build- und Testvorbereitung

**Status:** Release-Kandidat im Feature-Branch, nicht signiert und nicht ausgerollt.
Die bisherige Firmware `0.6.16` und alle bestehenden Knoten bleiben unverändert.
Experimentelles Zusatzsystem, kein zertifizierter Rauchwarnmelder.

## Inhalt

- Neues, eigenständiges Arduino-Sketchverzeichnis
  `firmware/mesh-v0.6.17/mesh-v0.6.17.ino`.
- Identität `0.6.17` statt `0.6.16`, mit unverändertem Protokoll.
- Diagnose-Buzzer auf XIAO ESP32-C3 D3/GPIO5:
  `BUZZER TEST`, `BUZZER 2X2`, `BUZZER STOP`.
- Buzzer **default off**; kein automatischer Alarm, keine Weiterleitung
  von Audioereignissen als Mesh-Alarm.
- Vorhandene acht Releaseprofile `.a` bis `.h` bleiben erhalten.

## WICHTIG: private Header nicht ins Git-Repository einchecken

Die Dateien `mesh_secrets.h` und `ota_public_key.h` sind absichtlich
nicht im GitHub-Repository enthalten. Sie müssen aus der **bestehenden
lokalen Firmwareinstallation** in das neue Verzeichnis kopiert werden.
Es werden keine Schlüsselwerte neu erzeugt oder geändert:

```powershell
Copy-Item .\firmware\mesh-v0.6.16\mesh_secrets.h .\firmware\mesh-v0.6.17\
Copy-Item .\firmware\mesh-v0.6.16\ota_public_key.h .\firmware\mesh-v0.6.17\
```

Die Header dürfen nicht mit `git add -f` veröffentlicht werden.

## Vorgehen für den Testknoten

Zunächst **nur auf dem Testknoten** per USB testen.
In `firmware/mesh-v0.6.17/feature_config.h` lokal
`#define FEATURE_BUZZER 1` aktivieren, die Arduino-IDE öffnet
`mesh-v0.6.17.ino`, Board: `XIAO ESP32C3`.

Im seriellen Monitor mit 115200 Baud:

```text
BUZZER TEST
BUZZER 2X2
BUZZER STOP
```

Für den Build der **acht Standardprofile** (alle mit
`FEATURE_BUZZER=0`) aus dem Projektstamm:

```powershell
.\tools\ota\build-release-matrix.ps1 -Version 0.6.17 -BuildOnly
```

Der Skriptlauf verwendet die bestehende Arduino-CLI und erzeugt den
Build-Report im konfigurierten Ausgabeverzeichnis. Er benötigt die beiden
lokalen Header. Falls der Ausgabeordner bereits existiert,
`-OutputRoot` mit einem neuen Pfad angeben.

## Release-Sperre: signierte Buzzer-Variante

`tools/ota/sign_release.py` validiert die acht etablierten
Featureprofile mit den Merkmalen `gateway`, `audio`, `config_ap`.
Es gibt derzeit **keinen signierten Buzzer-spezifischen Variantencode**.
Die Standard-Build-Matrix setzt daher `FEATURE_BUZZER=0`.
Ein lokal mit `FEATURE_BUZZER=1` gebauter Test ist **nicht**
gleichbedeutend mit einem signierten Buzzer-Release.

Vor einem signierten Buzzer-OTA-Release müssen Feature-Schema,
Variantenzuordnung, Signierung, Verifikation und Web-Releaseanzeige
auf Konsistenz geprüft und getestet werden. Bestehende signierte
`0.6.16`-Artefakte niemals überschreiben oder als `0.6.17` ausgeben.

## Mindestprüfungen vor dem Merge

```powershell
python -m unittest discover -s tests -p "test_*.py"
.\tools\ota\build-release-matrix.ps1 -Version 0.6.17 -BuildOnly
```

Außerdem die bisherige serielle Mesh-Kommunikation, Audio-Diagnose,
Buzzer-Einzelsignal, 2×2-Muster und manuellen STOP auf dem Testknoten
erneut prüfen. Kein Flash auf Gateway oder andere produktive Knoten,
bevor diese Prüfungen erfolgreich sind.
