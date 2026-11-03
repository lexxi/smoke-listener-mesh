# Smoke Mesh Monitor (Prototyp)

Lokales Web-Dashboard für ESP32-C3-Logs. Kein Zugriff auf COM: der vorhandene Logger läuft unverändert weiter.
Die Anwendung liest `mesh_*.log` aus `log/`, `logs/` und `scripts/log/` relativ zum Repository.

## Schnellstart unter Windows

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
py -m pip install -r .\web\requirements.txt
py .\web\app.py
```

Browser: http://127.0.0.1:8088

Den vorhandenen Logger parallel weiterlaufen lassen. Beispiel:

```powershell
py .\scripts\logging.py --port COM15 --out .\log\mesh_live.log
```

Der Log aus `scripts\log` (Logger aus dem scripts-Verzeichnis gestartet) wird ebenfalls erkannt.
Andere Log-Verzeichnisse lassen sich mit `--log-dir PFAD` ergänzen.

## Enthalten

- Knotenname aus v0.5.5, MAC-Adresse und Standort aus `config/nodes.csv`
- Online bis 45 s, überfällig bis 120 s, danach offline (Zeitstempel der Logdatei)
- letzte Meldung, direkt/Relay, RSSI, letzte Sender-MAC, Hops
- schematische Etagenübersicht, Relay-Zählung, letzte RX-Ereignisse
- SQLite-Datenbank unter `web/data/mesh.db`

## Grenzen

- Nur authentifizierte RX-Zeilen (`AUTH=OK`); lokale TX-Meldungen zählen nicht als RX.
- RSSI gehört zum letzten Hop, nicht zwangsläufig zur Quellverbindung.
- Via-MAC ist nur der letzte Relay-Sender, keine vollständige Funkroute.
- Empfangenes HEARTBEAT beweist weder Rauchmeldererkennung noch vollständige Netzfunktion.
- Mehrfach vorhandene identische Logläufe können doppelt gezählt werden.
- Node `7E:E3:A0` kann als `Keller_Abgang` auftreten, auch wenn Standort `FZRaum` konfiguriert ist.
- Keine Authentifizierung: standardmäßig nur `127.0.0.1`; für vertrauenswürdiges LAN `--host 0.0.0.0` und Firewall prüfen.
- Keine sicherheitskritische Rauch-/Brandmeldung; nur experimentelle Beobachtung.
