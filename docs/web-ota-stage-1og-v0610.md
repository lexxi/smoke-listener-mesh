# Einfacher Web-OTA-Test: 1OG v0.6.9 nach v0.6.10

Stand: 04.11.2026. Dies ist ein **kontrollierter Staging-Test**, noch kein vollständiges unbeaufsichtigtes OTA-Update.

## Voraussetzungen

- Garage ist unter COM14 als USB-Logger bereits auf v0.6.10 getestet.
- 1OG läuft aktuell mit v0.6.9 in `app0`, Zustand VALID; der inaktive `app1` enthält noch v0.6.7.
- Kueche v0.6.1 als OTA-Gateway an **COM12** anschließen. 1OG zusätzlich über USB an **COM15** anschließen. Ohne beide seriellen Verbindungen kann diese Webversion den Zielknoten nicht lokal autorisieren, seinen Flash verifizieren oder den Status abfragen.
- Die anderen Arduino-Serial-Monitore / PowerShell-Logger auf COM12 und COM15 beenden. Garage COM14 kann weiter als eigenständiger Logger laufen.
- Signierter Release für exakt `000010637C6E27AC` und Version `0.6.10`; passendes Firmware-BIN aus dem Arduino-Build. Der private Signierschlüssel bleibt außerhalb des Repositories.

## Kurzer Ablauf

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
.\tools\ota\prepare-web-release.ps1 -Node 1OG -Version 0.6.10
.\myenv\Scripts\python.exe .\web\app.py
```

Vor `git pull` den bisher gestarteten Flask-Webserver regulär beenden. Falls das Signatur-Manifest bereits existiert, bricht der PowerShell-Helfer ab, statt es zu überschreiben. In diesem Fall das vorhandene Manifest verwenden, sofern es zur aktuellen BIN passt.

Im Browser `http://127.0.0.1:8088/ota`: 

1. **Release hinzufügen:** die Firmware-BIN und `C:\mesh-ota-keys\release-1og-0610.json` auswählen und auf **Prüfen und speichern** klicken.
2. **Release auswählen:** v0.6.10 / Ziel 1OG auswählen. Die Schaltfläche ist nur für dieses konkrete Versionspaar aktiv.
3. **Signierte Firmware übertragen:** nach der Sicherheitsabfrage startet der Webserver `ota_test.py` mit der bereits vorhandenen Prüfung von Identität, Firmwareversion, Slot, Signatur, Ziel-FLASH ARM, Flashstaging und SHA-256-Readback. Der Browser zeigt den Fortschritt und die Werkzeugausgabe.

Erfolg bedeutet **nur**: Die Firmware v0.6.10 wurde signiert in den **inaktiven Slot app1** von 1OG übertragen und dort geprüft. Der aktive Slot bleibt **app0 v0.6.9**. Keine Bootaktivierung, kein Reset, keine Bestätigung. Ein tatsächlicher Bootwechsel benötigt die bereits separat getesteten lokalen BOOT-Kommandos und einen sorgfältigen Bestätigungs-/Rollback-Test.

## Schutzmaßnahmen

- Nur `127.0.0.1` und lokale Browseraufrufe, nicht ins LAN/Internet freigeben.
- Nur signierte Releases werden angeboten. Zielknoten/Version werden sowohl vor Start als auch im OTA-Skript geprüft.
- Ein paralleler OTA-Webjob wird verhindert; alte OTA-Testbuttons wurden entfernt.
- Kein `--activate`, kein `BOOT ACTIVATE`, keine automatische `BOOT CONFIRM`-Ausführung.
- Benötigt weiter physisch angeschlossenes 1OG USB. Fern-OTA ohne Ziel-USB setzt neue, authentifizierte Fern-Arming- und Boot-Management-Kommandos in der ESP-Firmware voraus.
- Noch nicht am realen Gerät getestet. Erst mit einem Staging-/Readback-Durchlauf validieren; anschließend Bootwechsel separat.

## Warum Versionen vor v0.6.10 im Dashboard als Unbekannt erscheinen

Die ältere Firmware liefert keine authentifizierte Versions-Telemetrie. Ein Online-Status ist kein Beleg für die Firmwareversion. Der OTA-Sender überprüft die aktuelle Version über `BOOT STATUS` auf dem angeschlossenen Zielknoten.
