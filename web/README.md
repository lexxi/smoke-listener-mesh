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

## Aktiver Logger (automatisch)

Die Anwendung erkennt die MAC des im **ausgewählten Testlauf** sendenden Logger-C3 aus dessen jüngstem `[TX]`-Eintrag. Dieser Knoten erhält die Rolle `logger` und seinen Erreichbarkeitsstatus aus dem letzten TX-Zeitstempel. Andere Knoten behalten ihre aus `[RX]` ermittelten Statuswerte. Ein gestoppter Logger wird nach 120 Sekunden als offline geführt. Zum Umstellen auf einen anderen Logger sind keine Konfigurationsänderungen nötig; dessen neue `[TX]`-Meldungen werden automatisch erkannt.

Nach `git pull` den Webservice neu starten, da er ohne automatischen Code-Reload läuft. Die bereits vorhandenen Logs werden beim Start neu eingelesen, damit auch ältere TX-Zeilen in SQLite übernommen werden. Bei der Standardauswahl zählt für die Dashboard-Statistik jedoch nur die zuletzt geänderte Logdatei.

## Dashboard v0.3.0: Testläufe getrennt

Ein Logfile `mesh_*.log` entspricht einem Testlauf. Standardmäßig verwendet das Dashboard **nur die zuletzt geänderte Datei** für alle RX-Paketzahlen, Relay-Statistiken, Ereignisse und die automatische Logger-Erkennung aus `[TX]`. Die Auswahl **Testlauf** zeigt archivierte Logs separat, ohne die SQLite-Datenbank löschen zu müssen. Über **Aktuellen Log anzeigen** gelangst du zur automatischen Auswahl zurück. Archivierte Knoten werden nach ihrer heutigen Erreichbarkeit als offline dargestellt; das ist keine historische Online-Auswertung.

Wichtig: Die Lauftrennung erfolgt derzeit **pro Datei**, nicht anhand von Start-/Stop-Markierungen innerhalb derselben Datei. Den Logger für einen neuen Test am besten mit einem neuen Dateinamen starten. Ein einfacher Regressionstest steht in `tests/test_web_sessions.py` (`py -m unittest discover -s tests -p test_web_sessions.py`).
