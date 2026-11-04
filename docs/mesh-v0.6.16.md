# Firmware v0.6.16 – dedizierten USB-Gateway freigeben

Diese Version übernimmt die Funktionen von v0.6.15 und erweitert die **im
Empfänger fest einkompilierte Management-Vertrauensliste** um
`00000CEC7E6E27AC` (dedizierter Gateway an COM16).

Die bisherigen vertrauenswürdigen Gateway-IDs (Garage und Küche) bleiben
erhalten. Webserver-`web/gateways.json` steuert nur die Host-Seite; eine
neue Gateway-ID wird von bereits installierter Empfänger-Firmware erst
nach einem Update akzeptiert.

## Einmalige lokale Vorbereitung

Im Repository-Verzeichnis in PowerShell ausführen (die beiden lokalen,
**nicht eingecheckten**, sensiblen Header von v0.6.15 übernehmen):

```powershell
Copy-Item .\firmware\mesh-v0.6.15\mesh_secrets.h .\firmware\mesh-v0.6.16\mesh_secrets.h
Copy-Item .\firmware\mesh-v0.6.15\ota_public_key.h .\firmware\mesh-v0.6.16\ota_public_key.h
```

`feature_config.h` muss nicht manuell angepasst werden: Die Matrix setzt
alle Feature-Schalter im isolierten Build gezielt.

## Erst nur bauen, kein OTA

```powershell
.\tools\ota\build-release-matrix.ps1 -BuildOnly
```

Es entstehen acht voneinander unterscheidbare Versionen
`0.6.16.a` bis `0.6.16.h`. Das Script flasht keine Geräte.
Die Ausgabe landet in
`firmware/mesh-v0.6.16/build/release-matrix-4part`.

Für 1OG zum ersten Hardwaretest ist `0.6.16.h` vorgesehen (Gateway +
Audio + Konfigurations-AP). Vor dem USB-Flash zuerst den COM-Port prüfen,
und beachten, dass `merged.bin` NVS und OTA-Metadaten überschreiben kann.
Die normale Anwendungs-BIN alleine auf `0x10000` genügt nicht
zwangsläufig, wenn bereits `ota_1` aktiv ist.

## Testfolge

1. 1OG per USB mit `0.6.16.h` aktualisieren und serielle Version,
   gespeicherten Knotennamen und `BOOT STATUS` prüfen.
2. Über die Webapp **Gateway / COM16** und **1OG** auswählen,
   **Funkstatus** ausführen. Es muss eine authentifizierte
   `[MGMT] REPLY` erscheinen; `TIMEOUT no_reply` wäre ein Fehler.
3. Erst nach diesem Test andere Knoten aktualisieren. OTA-Staging,
   Signaturprüfung, Bootaktivierung und Rollback separat prüfen.
   Gleiche Version und identische Variante werden nicht als Upgrade gewertet.

**Noch experimentell:** Keine zertifizierte Brandmeldeanlage. Die
Audio-Diagnose ist keine produktiv validierte Alarmweiterleitung.
