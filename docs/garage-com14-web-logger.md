# Garage über COM14 im Windows-Dashboard

Der C3 **Garage** ist an COM14 per USB am Windows-Laptop angeschlossen. Die bestehende Flask-Webapp kann den vorhandenen Logger `scripts/logging.py` gezielt starten und stoppen. Das Mesh-Dashboard liest die entstehenden `log/mesh_*.log` weiter wie bisher.

## Start

1. Den bisher separat in PowerShell laufenden Logger (`scripts/logging.py --port COM14`) mit Ctrl+C beenden. Auch Arduino Serial Monitor auf COM14 schließen.
2. Flask-Webapp in PowerShell mit Ctrl+C beenden und nach `git pull origin main` neu starten:

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
.\myenv\Scripts\python.exe .\web\app.py
```

3. Browser `http://127.0.0.1:8088/` neu laden.
4. Im Abschnitt **Garage · COM14** auf **Logger starten** klicken.

Die GUI zeigt den eigenen Prozessstatus an und lässt ihn über **Logger stoppen** beenden. Sie beendet niemals einen extern in PowerShell gestarteten Logger. Ein zweiter Logger auf demselben COM-Port verhindert die Verbindung; die andere Instanz muss vorher geschlossen werden. Bei COM-Port-Verbindungsfehlern versucht das bestehende Skript den Reconnect alle fünf Sekunden.

Die Live-Knoten- und RSSI-Anzeige beruht weiter auf den tatsächlich eingehenden seriellen Meldungen. Fehlende Knoten werden nicht als online fingiert.

**Grenzen:** Windows-Prototyp, nur Loopback; keine Authentifizierung für LAN-Zugriff. Webserver-Neustart beendet auch den von ihm gestarteten Logger. OTA benötigt separat COM12/COM15 und steuert bislang keine Bootaktivierung.
