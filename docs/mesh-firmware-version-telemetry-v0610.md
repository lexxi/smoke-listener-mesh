# Mesh-Knoten und Firmwareversionen – v0.6.10

## Zweck

Das Dashboard zeigt seit dieser Änderung pro bekanntem Knoten `Firmware: vX.Y.Z` oder ausdrücklich `Unbekannt (noch nicht gemeldet)`.
Die Information stammt **nicht** aus einer manuell gepflegten Versionsliste: eine v0.6.10-Firmware veröffentlicht sie im authentifizierten ESP-NOW-Heartbeat bzw. TEST-Paket.

## Protokoll

- Bestehendes Mesh-Protokoll **3**, Paketgröße weiterhin **92 Byte**. Kein neues Paketformat und kein Firmware-Downgrade nötig.
- Das gepackte `Packet.name[24]` verwendet nun für lokale Namen maximal 19 Zeichen. Byte 19 bleibt NUL, Byte 20 enthält die Markierung `0xA5`, Bytes 21–23 enthalten Major/Minor/Patch als `uint8_t`.
- Diese vier Bytes liegen im bereits von HMAC-SHA256 authentifizierten Nachrichtenanteil. Eine weitergeleitete Meldung behält die Versionskennung des *Ursprungsknotens*, nicht die Version des Relays.
- Firmware vor v0.6.10 nutzt diese Bytes nicht, bleibt kompatibel und wird als **Unbekannt** dargestellt. Eine längere, in NVS gespeicherte Alt-Konfiguration wird nur für die Funkübertragung auf 19 Zeichen gekürzt.
- Neue v0.6.10 empfängt ältere Protokoll-3-TEST- und HEARTBEAT-Pakete weiter und schreibt `fw=unknown` oder `fw=0.6.10` in `[RX]`-Zeilen.
- Eigene `[TX]`-Zeilen der v0.6.10 enthalten `fw=0.6.10`, damit der direkt über USB angeschlossene Logger-Knoten im Dashboard seine eigene Version anzeigen kann.

## Windows-Test

1. In `C:\pyprojects\smoke-listener-mesh` zunächst `git pull origin main` ausführen.
2. Flask-Webapp und Web-Logger normal stoppen; den alten `web/data/mesh.db` **nicht löschen**. Die SQLite-Spalten werden beim nächsten Start automatisch ergänzt.
3. Flask-Webapp mit `myenv\Scripts\python.exe .\web\app.py` neu starten und die Knotenübersicht kontrollieren. Bis eine Meldung mit Versionsfeld eingeht, muss bei allen alten Knoten `Unbekannt` stehen.
4. Nur zum Testen: v0.6.10 in Arduino IDE mit bisherigen Board-/Partitionseinstellungen **kompilieren**, privaten `mesh_secrets.h` und `ota_public_key.h` aus dem vorherigen Sketch lokal übernehmen. Kein Erase All Flash.
5. **Erst nach erfolgreichem Compile** einen gut erreichbaren Testknoten (z. B. Garage am USB-COM14) aktualisieren. 1OG v0.6.9 als bereits validierten OTA-/Rollback-Stand vorerst unverändert lassen.
6. Garage-Logger im Browser wieder starten. Nach dem nächsten `[TX] ... fw=0.6.10` muss die eigene Garage als `Firmware: v0.6.10` erscheinen.
7. Andere Knoten mit älterer Firmware zeigen weiterhin `Unbekannt`. Eine reale Fernauslesung ihrer alten Versionskennung ist nicht möglich, weil die ältere Firmware sie nicht sendet.

**Wichtig:** Die Webapp **allein** kann Versionsdaten von bestehenden alten Knoten nicht erfinden. Damit auch Kueche/1OG/FZRaum ihre Firmwareversion melden, benötigen sie künftig ebenfalls eine Firmware mit dieser Erweiterung. Die v0.6.10 ist aktuell noch nicht auf Hardware kompiliert oder getestet.

## Einschränkungen

- Dies ist Diagnose-Telemetrie, **kein unabhängiger Firmware-Attest**. Die Versionsangabe ist durch den Netzwerkschlüssel gegen Fremdpakete authentifiziert, aber jeder Knoten mit dem gemeinsamen Schlüssel kann prinzipiell Daten anderer Knoten imitieren.
- Der Dashboard-Zustand stammt weiterhin aus Logdateien und bezeichnet keine garantierte Ende-zu-Ende-Alarmfunktion.
- Eine OTA-Automatisierung für v0.6.10 oder Remote-Aktivierung ist noch nicht Teil dieser Änderung.
