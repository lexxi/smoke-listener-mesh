# Mess- und Entwicklungsprotokoll

## Testobjekt

Smartwares RM149, optischer Rauchmelder, EN 14604, hergestellt 2016-08, vorgesehenes Austauschjahr 2026. **Nur als akustisches Testobjekt; nicht als regulärer Rauchmelder weiterverwenden.** Testtaste kann sich vom tatsächlichen Brandalarm unterscheiden.

## v0.3.1 – Tischtest

Drei Zungenschnalzer, anschließend zweimal zwei Pieptöne vom Melder; Geräusche beim Weglegen. Ergebnis: **4/4 bewusst ausgelöste Pieptöne** als gültig erkannt, **zwei Gruppen zu je 2**. Insgesamt 7 verworfene kurze Ereignisse (nicht alle einzeln zugeordnet). Beispiele: Piepdauer 640–704 ms, Pause 384–416 ms.

## v0.3.1 – Entfernungsversuch

ESP32/Mikrofon blieb am selben Platz. Rauchmelder in ca. 1, 2, 4 und 5 m Entfernung, zuletzt hinter geschlossener Tür. Laut Nutzer tatsächlich 7 Pieptöne in den Folgen **2, 1, 2, 2**. Im Log: 7 gültige Pieptöne, vier Gruppen mit **2, 1, 2, 2**, zusätzlich 7 verworfene Ereignisse. Keine exakte zeitliche Zuordnung einzelner Gruppen zu Messentfernungen aufgezeichnet. Keine belastbare Aussage zur Empfindlichkeit hinter Türen oder mit unterschiedlichen Rauchmeldern.

## v0.4.0 – ESP-NOW-Funktest (2026-10-20)

Zwei ESP32-C3 SuperMini mit identischer Broadcast-Testfirmware auf Funkkanal 6. Beobachteter Knoten: MAC `90:DA:72:91:4E:5C`. Serielle Ausgabe: `ESP-NOW initialized`, abwechselnd `[RX]` und `[TX]` im 5-Sekunden-Rhythmus. Sichtbar waren Empfangspakete mit Sequenznummern **1–11** ohne Lücken. Die jeweilige `[TX]`-Ausgabe bezeichnet nur erfolgreichen Aufruf der Sende-API, keine Zustellgarantie. Beide Geräte kommunizieren direkt; keine Relais-Weiterleitung implementiert, keine Reichweitenmessung durchgeführt.

## Bekannte Grenzen und TODO

- Der ausgegebene Goertzel-`freq-match`-Prozentsatz ist kein Nachweis einer stabilen Grundfrequenz. Messfenster suchen 3,0–4,4 kHz, die Ergebnisse variieren.
- Naher lauter Rauchmelder erzeugt Spitzen nahe 24-Bit-Sättigung; Verzerrung kann Frequenzanalyse verschlechtern.
- Gegenprobe mit anderen Geräuschen, anderen Meldern, abweichenden Räumen und realen Alarmmustern fehlt.
- Audio-C3 läuft durchgehend: erheblicher Strombedarf, 18650-Laufzeit ungeprüft.
- Für sicherheitskritischen Betrieb nicht geeignet; keine garantierte Zustellung durch ESP-NOW.
- v0.4.0 ESP-NOW erfolgreich mit zwei ESP32-C3 getestet; Broadcast ist **noch kein Mesh**. Aussagekraft auf kurzen Funktionstest begrenzt.

## v0.5.0 – Mesh-Protokoll in Entwicklung

Ein gemeinsamer Sketch mit Chip-ID als Ursprung, Sequenznummer, TTL=3, Duplikat-Cache (48 Einträge), zufällig verzögerter Weiterleitung (30–119 ms) und Heartbeats alle 15 Sekunden ist im Repository. **Nicht auf Hardware oder über drei Hops verifiziert.** Broadcasts sind unverschlüsselt, nicht authentifiziert und nicht zustellgarantiert. TTL zählt Übertragungsstufen; die Prüfanordnung mit nur zwei Knoten beweist kein Relay. Es gibt noch keine Paket-ACKs, Heartbeat-Ausfallwertung, dauerhafte Sequenznummern, ausfallsichere Stromversorgung oder Integration mit der Audioerkennung. Nur Labortests.


## v0.5.5 – Test mit zwei Geräten (03.11.2026)

ESP32-C3 mit etwa 1 m Abstand. Im seriellen Log von `1OG` waren sechs empfangene Heartbeats von `Kueche` (`seq=1–6` nach Zählerstand) sichtbar, davon fünf im vorliegenden Logausschnitt (`seq=2–6`). Die Pakete zeigten `AUTH=OK`, `hops=0`, `ttl=3` und RSSI zwischen −31 und −44 dBm. Der Empfänger protokollierte für diese Pakete `[RELAY] ... status=0`. Das belegt Empfang, Namensübertragung und Auslösen der Weiterleitung, **nicht** die Zustellung an einen dritten Knoten.

## v0.5.5 – Gebäude-Log und Dashboard (03.11.2026)

USB-Logger aktuell `1OG` (MAC-Endung `7C:63:10`), früherer PC-Logger `7E:D3:20` außer Betrieb. Im bereitgestellten Ausschnitt des Logs `mesh_20261103_101709.log` sind authentifizierte Heartbeats von `Kueche`, `Garage` und `Keller_Abgang` zu sehen. Es treten direkte Empfänge (`hops=0`), Ein-Hop-Relays (`hops=1`) und Zwei-Hop-Relays (`hops=2`) auf. Der `via`-Wert ist die letzte sendende MAC-Adresse vor dem Logger. Die Zuordnung `FZRaum` in `config/nodes.csv` und der Funkname `Keller_Abgang` bezeichnen denselben Knoten mit MAC-Endung `7E:E3:A0`; das sind unterschiedliche Beschriftungsfelder.

Das lokale Dashboard **v0.3.0** liest die Logdateien ohne Zugriff auf den seriellen Port ein, ermittelt den aktiven USB-Logger aus `[TX]` und begrenzt Statistiken auf einen ausgewählten Testlauf (eine Logdatei). Der Nutzer hat den Start und die Anzeige des Dashboards unter Windows bestätigt; dies ist kein formaler Softwaretest.

**Offen:** Ein *ausschließlich über Relay* erreichbarer Knoten wurde noch nicht belastbar nachgewiesen. Dazu muss der Direktpfad nachweislich ausfallen, während die Verbindung mit aktivem Zwischenknoten wieder funktioniert. Die gemessene RSSI-Zahl bei Relay-Empfang ist nur die Signalstärke der letzten Funkstrecke.
