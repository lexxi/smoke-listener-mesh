# Release-Verwaltung im Webinterface (Windows)

Die bestehende Flask-Webapp unter `http://127.0.0.1:8088/ota` besitzt eine Release-Verwaltung zum lokalen Hochladen, Prüfen und Speichern einer **kompilierten** Firmwaredatei und eines **signierten** Manifests.

## Installation und Test

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
.\myenv\Scripts\python.exe -m pip install -r .\web\requirements.txt
.\myenv\Scripts\python.exe .\web\app.py
```

Im Browser `http://127.0.0.1:8088/ota` öffnen. Im Abschnitt **Release-Verwaltung** zwei Dateien auswählen:

- **Firmware-BIN**: z. B. die fertige `mesh-v0.6.10.ino.bin` aus dem Arduino-Build.
- **Signiertes Manifest**: das exakt zu dieser BIN gehörende JSON aus `sign_release.py sign`. Ein Manifest für v0.6.9 kann **nicht** für die v0.6.10-BIN verwendet werden.

Auf **Release prüfen & speichern** klicken. Der Server prüft mit `C:\mesh-ota-keys\signing-public.pem` die ECDSA-P256-Signatur, Zielknoten-ID, ESP32-C3-Image-Header, Chip-ID, Imagegröße und SHA-256 der exakten BIN-Datei. Nur gültige Kombinationen werden abgelegt. Ein identisches Release wird nicht doppelt angelegt.

Die verifizierten Dateien werden als `web/data/releases/<target>_<version>_<sha-prefix>/firmware.bin` und `manifest.json` gespeichert. `web/data/` ist per `.gitignore` von GitHub ausgeschlossen. Ein Serverumzug benötigt ein Backup dieses Verzeichnisses **und** die korrekte öffentliche Verifikationsdatei.

### Signiertes Manifest für die neue Firmware erstellen

**Nur auf dem vertrauenswürdigen Build-PC** – den privaten Schlüssel niemals zur Webapp hochladen oder ins Repository kopieren:

```powershell
cd C:\pyprojects\smoke-listener-mesh
.\myenv\Scripts\python.exe .\tools\ota\sign_release.py sign `
  --image .\firmware\mesh-v0.6.10\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.6.10.ino.bin `
  --private-key C:\mesh-ota-keys\signing-private.pem `
  --target 000010637C6E27AC `
  --version 0.6.10 `
  --out C:\mesh-ota-keys\release-1og-0610.json
```

Das Beispiel signiert die BIN **für 1OG**. Garage oder andere Knoten brauchen ein **jeweils auf ihre Knoten-ID signiertes Manifest**. Das BIN kann bei gleicher Hardware/Firmware gleich bleiben.

## Sicherheitsgrenzen

- **Nur lokales Loopback**, keine LAN-Freigabe, kein Login/TLS oder Mehrbenutzerbetrieb. Nicht auf `0.0.0.0` binden.
- Maximal 1.310.720 Byte BIN + 8192 Byte Manifest; die Serveranwendung verwertet keine hochgeladenen Dateinamen als Pfad.
- Es werden keine privaten Schlüssel oder Arduino-Header auf den Server geladen.
- **Upload ist kein Flashen.** Die bestehenden v0.6.9-Stagingbefehle für 1OG sind bewusst deaktiviert. Geräteselektion, Übertragung, Bootaktivierung, Rollback-Bestätigung und Wiederaufnahme müssen separat integriert und getestet werden.
- Ein syntaktisch gültiges und signiertes BIN sagt nichts über die Funktion der Rauchalarm-Erkennung aus.

## Problemlösung

- Bei Signaturfehler: passendes Manifest zur Binärdatei erstellen und den hinterlegten **richtigen öffentlichen Schlüssel** prüfen.
- Bei `already present`: Upload wurde schon gespeichert; verifizierte Release-Liste prüfen.
- Bei fehlendem Build-BIN: Arduino IDE muss `Export compiled Binary` ausgeführt haben bzw. der Build-Pfad muss stimmen.
- Bei neuem Webcode: Flask normal stoppen, `git pull origin main`, Flask wieder starten, Browser mit `Strg+F5` aktualisieren.
