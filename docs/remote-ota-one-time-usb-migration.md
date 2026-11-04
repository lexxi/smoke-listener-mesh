# Remote-OTA über die Webapp – einmalige USB-Migration

**Status 04.11.2026: Quellcode implementiert, noch NICHT auf ESP32-C3 kompiliert oder in Hardware getestet.** Die vorhandene v0.6.9-Rollbackprobe beweist NICHT die neue Fernaktivierung. Die Migration deshalb in Etappen durchführen.

## Ziel

Nach der einmaligen Installation der Remote-OTA-Basis **v0.6.11** auf allen C3 soll jeder weitere Firmwarewechsel ausschließlich in der Webapp erfolgen. Mindestens **ein** C3 bleibt als USB-Gateway dauerhaft am Host angeschlossen. Alle anderen Geräte benötigen nur ESP-NOW, keinen USB-Anschluss zum Server.

Verfügbare Gateway-Rollen: Garage/COM14 oder Kueche/COM12. Der USB-Gateway-Knoten kann nicht seine eigene Firmware über sich selbst aktualisieren: für ihn muss der jeweils andere C3 als USB-Gateway dienen. Der Webapp-Garage-Logger wird bei Nutzung von COM14 automatisch pausiert und anschließend wieder gestartet.

## Einmalige USB-Migration (nicht alle Geräte blind gleichzeitig flashen)

1. `git pull origin main`. Die private `mesh_secrets.h` und `ota_public_key.h` aus dem zuletzt verwendeten Sketch **lokal** in `firmware/mesh-v0.6.11/` kopieren. Diese Dateien sind absichtlich nicht in Git.
2. v0.6.11 in Arduino IDE mit ESP32 Core 3.3.12 / `XIAO_ESP32C3` und dem bisherigen Partition Scheme mit `app0`/`app1` kompilieren. `Erase All Flash` auf **Disabled** lassen. Compile-Warnungen und Größe notieren.
3. **Garage** zuerst über COM14 auf v0.6.11 aktualisieren. Danach mit dem bestehenden Logger TEST/HEARTBEAT zwischen Garage und 1OG/Kueche prüfen. Keine gleichzeitige Logger-/OTA-Nutzung von COM14.
4. **1OG** anschließend einmalig über USB auf v0.6.11 aktualisieren. Mit Garage als Gateway (COM14) im Browser den **Funkstatus** von 1OG prüfen. Noch kein OTA durchführen.
5. Erst wenn Statusübertragung funktioniert, v0.6.12 im Arduino IDE kompilieren (privaten Header ebenfalls lokal kopieren), auf dem vertrauenswürdigen Windows-PC ein signiertes Release-Paket erzeugen und in der Webapp hochladen.
6. **1OG v0.6.11 → v0.6.12** zunächst mit **Nur übertragen & prüfen** testen: Es darf sich kein Bootslot ändern. Danach für einen vollständigen Update-Test den Button **Vollständiges OTA-Update** verwenden. Achtung: Das führt derzeit eine erneute vollständige Übertragung durch; es nutzt den vorherigen Staging-Lauf nicht einfach wieder.
7. Bootbestätigung (`state=2`) und tatsächliche v0.6.12-Heartbeats prüfen. Für den negativen Test absichtlich keine Bestätigung senden, dann den 90-Sekunden-Watchdog und Rollback beobachten. Die autonome Alarmdetektion ist dadurch **nicht** validiert.
8. Erst nach positiven und negativen Tests **Kueche und FZRaum** einmalig über USB auf die geprüfte Remote-OTA-Basis aktualisieren. Zukünftige Releases dann nur über Webapp.

## Release-Paket für alle Knoten mit einem Befehl

Nach dem Kompilieren (für das v0.6.12-Testrelease):

```powershell
cd C:\pyprojects\smoke-listener-mesh
.\tools\ota\prepare-web-bundle.ps1 -Version 0.6.12
```

Das Skript benutzt **nur lokal** `C:\mesh-ota-keys\signing-private.pem` und erzeugt `C:\mesh-ota-keys\smoke-mesh-v0.6.12-ota.zip` mit einer `firmware.bin` und den **vier** individuell signierten Manifesten. Die Webapp benötigt nur den öffentlichen Prüfschlüssel und speichert nach der Prüfung die vier Releases im Verzeichnis `web/data/releases/`.

**Nie private Signierschlüssel, `mesh_secrets.h`, Klartext-Secrets oder vollständige private Header in ein ZIP packen oder auf den Webserver laden.**

## Bedienung

- `http://127.0.0.1:8088/ota` öffnen.
- ZIP unter **Release-Paket hochladen** auswählen und verifizieren.
- Release passend zum Zielknoten auswählen.
- USB-Gateway auswählen (Garage COM14 oder Kueche COM12, nicht identisch mit dem Ziel).
- **Funkstatus prüfen** fragt den Remote-Knoten über ESP-NOW ab: gemeldete Version, aktive/gewählte Partition und OTA-Zustand.
- **Nur übertragen & prüfen** sendet signiertes Manifest, aktiviert am Ziel einmalig die Flash-Freigabe, überträgt die BIN und verifiziert SHA-256 unmittelbar aus dem inaktiven Flashslot. Es wird nicht neu gestartet.
- **Vollständiges OTA-Update** führt zusätzlich Aktivierung des neuen Bootslots, Neustart, Status-/Heartbeat-Kontrolle und Bestätigung des PENDING_VERIFY-Zustands aus. Bei ausbleibender Bestätigung startet der neue C3 nach 90 Sekunden neu; ein korrekt konfigurierter ESP32-Bootloader sollte die vorherige VALID-Partition booten.

## Sicherheit und bekannte Grenzen

- Funksteuerung nutzt HMAC-SHA256 (bestehenden gemeinsamen Mesh-Schlüssel), gezielte Gateway-IDs **Kueche** und **Garage** sowie eine zufällige Challenge pro Zielboot, die nach jedem erfolgreichen Zustandswechsel gewechselt wird. Dies ist keine Public-Key-Signatur für Administrationsbefehle; ein kompromittierter Mesh-Schlüssel oder kompromittierter Knoten kann die Autorisierung unterlaufen.
- Firmware selbst wird weiterhin auf dem **Zielknoten** anhand des ECDSA-P256-signierten Manifests und ihres SHA-256 verifiziert; ein Downgrade wird verweigert.
- Keine Fernaktivierung ohne erfolgreiches Flash-Readback in der laufenden Sitzung. Status und Bestätigung berücksichtigen die neue Firmwareversion und ESP-IDF OTA-States.
- `BOOT CONFIRM` erfolgt nur bei `PENDING_VERIFY`, mindestens 15 Sekunden Laufzeit und zuvor empfangenem authentifiziertem Meshpaket. Das ist ein **Mesh-Selbsttest**, aber KEINE validierte Prüfung von Mikrofon, Rauchalarm-Erkennung oder sonstiger Sensorik.
- PENDING_VERIFY-Watchdog startet nach 90 Sekunden neu, wenn nicht bestätigt; der ESP-IDF-Bootloader übernimmt den Rollback. Ob das unter den gewählten ESP32-Arduino-Partitionseinstellungen tatsächlich zuverlässig funktioniert, muss auf Hardware noch getestet werden.
- Verbindungsabbruch, korrupte Signatur, fehlender Gateway-Heartbeat, fehlerhafte Aktivierung oder Geräteausfall dürfen niemals als erfolgreicher Updateabschluss angezeigt werden. Für den ersten Test Geräte mit USB-Rettungsmöglichkeit behalten.
- Webapp vorerst nur auf Loopback (`127.0.0.1`) und nicht im LAN/Internet betreiben. Der Webserver ist nicht authentifiziert. Später für Linux TLS/Auth/Rollen/Audit ergänzen.
- Laufende Flashjobs nicht durch Neustarten des Webservers unterbrechen; vor neuen Releases jeweils einen Testknoten aktualisieren.

## Firmwaredateien

- `firmware/mesh-v0.6.11/mesh-v0.6.11.ino` – erste einmalig per USB zu installierende Remote-OTA-Basis
- `firmware/mesh-v0.6.12/mesh-v0.6.12.ino` – erster geplanter Update-Test ohne USB am Ziel
- `tools/ota/remote_ota.py` – Desktop-/Webserver-Workflow über ein Gateway
- `tools/ota/prepare-web-bundle.ps1` – signiertes ZIP mit vier Manifesten
- `web/remote.py` – Web-OTA-Jobverwaltung
- `web/logger_control.py` – kontrollierte Garage-COM14-Freigabe

**Kein garantierter USB-freier Betrieb, bevor v0.6.11 kompiliert und die End-to-End-/Rollback-Tests erfolgreich abgeschlossen sind.**
