# ESP-NOW OTA – Entwicklungsplan und Sicherheitsgrenzen

Status: **Entwurf, noch keine OTA-fähige Firmware veröffentlicht** (03.11.2026).
Die aktuell laufende Firmware v0.5.5 kann keine drahtlosen Firmwaredateien empfangen.
Ziel: Ein einziges Gateway (z. B. 1OG per USB) verteilt gezielt Firmware an
einen Knoten über ESP-NOW, gegebenenfalls über weitere Relays. Kein Tastendruck
auf dem Zielknoten nach einmaliger Installation der neuen OTA-Firmware.

## Geprüfte Grundlagen

- Mesh v0.5.5: Protokoll 3, 92-Byte-Heartbeat-Pakete, TTL=3 und HMAC-SHA256.
- Der serielle Logger beansprucht bereits COM15. **Nie parallel denselben COM-Port**
  aus einer zweiten Python-Anwendung öffnen.
- Der ESP-NOW-v1-Datenrahmen ist auf maximal 250 Bytes beschränkt; Firmware
  benötigt Fragmentierung, Flusskontrolle und Wiederholungen.
- OTA braucht ein Partitionierungsschema mit inaktivem OTA-Slot. Die Arduino
  Update-Library verwendet dafür `esp_ota_get_next_update_partition()`.
- Der bestehende HMAC-Schlüssel authentifiziert Mesh-Pakete, ist aber **keine
  belastbare Firmware-Herausgebersignatur**, da er auf allen Knoten liegt.

## Stufenplan mit überprüfbaren Abnahmekriterien

### Phase A – Flash/Bootloader prüfen (vor dem nächsten Flash)

1. Exaktes ESP32-C3-Board, Flash-Größe und Arduino-ESP32-Core-Version notieren.
2. In der Arduino IDE das gewählte Partitionsschema ablesen. Zwei OTA-App-Slots
   müssen existieren. Für die Firmwaredatei Größe gegen den kleineren OTA-Slot prüfen.
3. Vor der Installation prüfen, dass `esp_ota_get_next_update_partition()` einen
   anderen, ausreichend großen Bereich als die laufende Partition liefert.
4. Vorhandene private `mesh_secrets.h` niemals ins Repository committen.
5. Einen Knoten als USB-Rettungsgerät verfügbar halten.

Hilfsmittel zur Prüfung einer kompilierten .bin-Datei: `tools/ota/check_image.py`.

### Phase B – Mesh-OTA-Transport (ohne Flash-Schreibzugriffe)

- Eigene OTA-Frame-Typen mit HMAC, Ursprung, Ziel-MAC/-ID, Sitzungskennung,
  Blockindex, TTL und begrenzter Nutzlast.
- Ausschließlich **ein Zielgerät gleichzeitig**. BEGIN, CHUNK, ACK/NACK,
  COMPLETE/ABORT; eigener Kanal für Fortschrittsausgaben.
- Relay-Weiterleitung über die vorhandene Mesh-Logik, mit separater
  OTA-Duplikaterkennung und zufälliger Weiterleitungsverzögerung.
- Ende-zu-Ende-Bestätigung der **Zielnode**, nicht nur ESP-NOW-Sendestatus;
  fehlende ACKs nach Timeout erneut versuchen.
- Zweimaliger Test: direkter Knoten; anschließend nur via Relay erreichbarer
  Knoten. Paketverlust künstlich erzeugen; Timeout und Abbruch prüfen.
- Heartbeats priorisieren oder Datenrate begrenzen, damit das Monitoring nicht
  durch Update-Traffic verdrängt wird.

### Phase C – Sicheres Flashen

- Firmwareabbild vor Übertragung lokal auf plausibles Format, Größe, Zielchip,
  Version und signierten Herausgeber prüfen.
- Vor Beginn verbindliche Ziel-ID und signiertes Manifest mit SHA-256,
  Bildgröße, Firmwareversion, Hardware-ID und Anti-Rollback-Information.
- **Signaturprüfung auf dem Zielknoten mit fest eingebautem öffentlichem
  Schlüssel**. Der gemeinsame Mesh-HMAC-Key alleine reicht dafür nicht.
- Nur in die *inaktive* App-Partition schreiben; Längen, Hash und Signatur
  vor Aktivierung prüfen. Bei Fehler abbrechen, bisherige Firmware behalten.
- Nach Boot Gesundheitsprüfung und Bestätigung/Rollback; unterbrochenen Upload
  nicht starten. NVS-Namen und Geheimnisse erhalten.
- Stromversorgung / Spannungsabfall während des Schreibens testen.

### Phase D – Webmonitor

- Webmonitor stellt Firmwaredatei und **explizite Zielnode** bereit.
- Ein exklusiver Gateway-Prozess besitzt den seriellen Port und stellt eine
  lokale, geschützte Steuer-API bereit; der Dashboard-Prozess öffnet COM nicht.
- Uploadstatus und Abschlussbestätigung im Monitor. Kein autonomes Ausrollen
  auf alle Knoten. HTTPS/Authentifizierung vor Zugriff aus fremden Netzen.
- Version + OTA-Fähigkeit der Knoten sichtbar und nachvollziehbar.

## Was wir ausdrücklich nicht behaupten

- `[TX] status=0` bestätigt keine Zustellung an die Zielnode.
- `hops=1` alleine beweist keine fehlende Direktverbindung.
- Eine erfolgreich übertragene .bin-Datei ist nicht automatisch gültig oder
  vertrauenswürdig.
- ESP-NOW-OTA darf nicht als zuverlässiger Alarmkanal gelten.
- **v0.5.5 ist nicht OTA-fähig** und muss mindestens einmal per USB durch
  eine spätere freigegebene Version ersetzt werden.

## Referenzen

- Espressif ESP-NOW Component: https://github.com/espressif/esp-now
- Espressif ESP-NOW OTA API: https://docs.espressif.com/projects/esp-now/en/latest/esp32/api-reference/ota/espnow_ota.html
- Arduino ESP32 Update API: https://github.com/espressif/arduino-esp32/blob/master/libraries/Update/README.md
