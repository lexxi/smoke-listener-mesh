# Mess- und Entwicklungsprotokoll

## Testobjekt

Smartwares RM149, optischer Rauchmelder, EN 14604, hergestellt 2016-08, vorgesehenes Austauschjahr 2026. **Nur als akustisches Testobjekt; nicht als regulärer Rauchmelder weiterverwenden.** Testtaste kann sich vom tatsächlichen Brandalarm unterscheiden.

## v0.3.1 – Tischtest

Drei Zungenschnalzer, anschließend zweimal zwei Pieptöne vom Melder; Geräusche beim Weglegen. Ergebnis: **4/4 bewusst ausgelöste Pieptöne** als gültig erkannt, **zwei Gruppen zu je 2**. Insgesamt 7 verworfene kurze Ereignisse (nicht alle einzeln zugeordnet). Beispiele: Piepdauer 640–704 ms, Pause 384–416 ms.

## v0.3.1 – Entfernungsversuch

ESP32/Mikrofon blieb am selben Platz. Rauchmelder in ca. 1, 2, 4 und 5 m Entfernung, zuletzt hinter geschlossener Tür. Laut Nutzer tatsächlich 7 Pieptöne in den Folgen **2, 1, 2, 2**. Im Log: 7 gültige Pieptöne, vier Gruppen mit **2, 1, 2, 2**, zusätzlich 7 verworfene Ereignisse. Keine exakte zeitliche Zuordnung einzelner Gruppen zu Messentfernungen aufgezeichnet. Keine belastbare Aussage zur Empfindlichkeit hinter Türen oder mit unterschiedlichen Rauchmeldern.

## Bekannte Grenzen und TODO

- Der ausgegebene Goertzel-`freq-match`-Prozentsatz ist kein Nachweis einer stabilen Grundfrequenz. Messfenster suchen 3,0–4,4 kHz, die Ergebnisse variieren.
- Naher lauter Rauchmelder erzeugt Spitzen nahe 24-Bit-Sättigung; Verzerrung kann Frequenzanalyse verschlechtern.
- Gegenprobe mit anderen Geräuschen, anderen Meldern, abweichenden Räumen und realen Alarmmustern fehlt.
- Audio-C3 läuft durchgehend: erheblicher Strombedarf, 18650-Laufzeit ungeprüft.
- Für sicherheitskritischen Betrieb nicht geeignet; keine garantierte Zustellung durch ESP-NOW.
- v0.4.0 ESP-NOW bisher **nicht getestet**; Broadcast ist nicht automatisch Mesh.
