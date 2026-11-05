# Webapp: Knotenregistrierung und Gateway-Start

Diese Funktionen liegen im Branch `feature/web-node-registration` und müssen vor dem
Merge auf Windows getestet werden.

## Neu geflashten C3 registrieren

1. Über `Knotenverwaltung / Discover` warten, bis der Knoten nach einem
   authentifizierten Funkpaket erscheint.
2. Knoten auswählen, Inventarname und Standort eingeben und bei Bedarf
   `Für signierte OTA-Updates freigeben` wählen.
3. `Knoten speichern` schreibt in die vorhandene `config/nodes.csv` und
   die lokale `web/data/node_targets.json`. Die Freigabe ist keine Signatur.
   Für einen neuen Empfänger muss ein neues signiertes Paket mit dessen
   Manifest erstellt werden.
4. `NAME SET` separat ausführen, damit der Gerätename im NVS gespeichert
   wird. Firmware vor v0.6.16 akzeptiert den neuen dedizierten
   COM16-Gateway eventuell noch nicht als Management-Sender.

Maximal fünf OTA-Empfänger werden unterstützt. Der dedizierte USB-Gateway
bleibt ein separates Gerät. Die eingetragenen Ports in `web/gateways.json`
sind bislang eine Betreiberkonfiguration.

## Standard-Gateway per Web wählen

In `Knotenverwaltung` oder `Firmware / OTA` gewünschten Gateway auswählen und
`Als Standard-Gateway speichern` anklicken. Ab dem nächsten Seitenaufruf
wird diese Auswahl vorausgewählt. Die Präferenz liegt in
`web/data/gateway_preferences.json` und erfordert keinen Neustart.

**Unterscheidung:** Das ändert nur den vorausgewählten Sender für
Remote-Management und OTA. Der **physische USB-Logger** bleibt auf dem
`logger_gateway` aus `web/gateways.json`.

Im Abschnitt **USB-Gateways verwalten** können weitere USB-Gateways per
COM-Port, Name und Node-ID hinzugefügt und entfernt werden. Neue
Einstellungen werden in `web/data/managed_gateways.json` gespeichert und
**erst nach einem vollständigen Neustart der Webapp aktiv**. COM16 als
dedizierter Logger ist vor dem Löschen geschützt. COM12 (Küche) und
COM14 (Garage) sind standardmäßig nicht mehr als USB-Gateways eingetragen,
bleiben aber Mesh-Knoten und OTA-Empfänger. Die Firmware-Vertrauensanker
werden dadurch **nicht** geändert: Ein neuer USB-Gateway muss von den
Ziel-Firmwares bereits für Management-Befehle zugelassen sein.

## Logger-Start

Ein Start über `python web/app.py` startet den konfigurierten USB-Logger
einmalig. Während einer Remote-Aktion wird der Logger reserviert und
nach Bedarf wieder gestartet. Auf dem Dashboard steht ein Warnhinweis,
wenn kein Web-Logger läuft; dann sind Online/Offline-Anzeigen nicht aktuell.

Wenn COM16 durch einen fremden seriellen Prozess belegt ist, darf die
Webapp diesen Prozess nicht beenden. Ein Loggerfehler ist am angezeigten
Status und im Diagnose-Log zu prüfen.

## Prüfschritte

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Nach dem Neustart der Webapp überprüfen: Logger-Autostart, Auswahl des
Standard-Gateways, Persistenz nach Browserreload, node registration, OTA
Freigabe und korrekte Pausierung des Loggers bei Remote-STATUS.
