# OTA-Weboberfläche – erster Windows-Test

Das bestehende Flask-Dashboard `web/app.py` wurde um `/ota` erweitert. Kein zweiter Webserver nötig.

## Start

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
.\myenv\Scripts\python.exe -m pip install -r .\web\requirements.txt
.\myenv\Scripts\python.exe .\web\app.py
```

Im Browser: http://127.0.0.1:8088/ota

## Funktionen

- Release-Prüfung v0.6.9 inklusive P-256-Signatur, SHA-256 und exakter Imagegröße.
- OTA-Staging und Readback durch das bestehende `tools/ota/ota_test.py` für fest konfiguriertes Gerät und Versionspaar.
- Live-Log, Status, Ergebnis; kein paralleler Transfer im selben Webprozess.
- Bootaktivierung, Neustart und `BOOT CONFIRM` sind bewusst **nicht** über Web erreichbar.
- Nur Loopback-Zugriff (`127.0.0.1`) erlaubt; nicht nach außen veröffentlichen.

## Derzeitiger Gerätestand

1OG ist bereits auf v0.6.9 (`app0`, VALID). Das in der Seite hinterlegte signierte v0.6.9 ist daher **nur ein Prüfbeispiel**. Eine echte Übertragung erfordert ein neues signiertes Release (v0.6.10 oder höher) und eine bewusst aktualisierte Versionspaar-Konfiguration. Der bisherige Sender wird eine erneute Installation von v0.6.9 auf dem aktuellen Gerät ablehnen.

Vor einem echten Test Arduino Serial Monitor für COM12 und COM15 schließen. Bei fehlenden Paketen `cryptography` und `pyserial` in derselben venv wie den bisherigen OTA-Tools installieren.

## Grenzen

- Der Webservice ist ein lokaler Prototyp, kein LAN-Managementdienst. Weder Login noch TLS sind bisher implementiert.
- Jobstatus bleibt nur im RAM; der OTA-Prozess darf während einer laufenden Übertragung nicht durch Webserver-Neustart unterbrochen werden.
- Remote-Aktivierung/-Bestätigung und automatischer Recovery-Ablauf fehlen noch.
- Für akustische Rauchalarm-Erkennung liegt kein durchgehender produktiver Sicherheitsnachweis vor.
