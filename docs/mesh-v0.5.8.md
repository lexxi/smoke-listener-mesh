# v0.5.8 – OTA-Partitionsprüfung vor echtem Flashen

**Status: Quellcode auf main, nicht kompiliert, nicht auf Hardware getestet. KEIN OTA-FLASHEN.**

Die v0.5.7 bleibt als getestete Grundlage unangetastet. v0.5.8 übernimmt den RAM-only-Test und erweitert ihn um den seriellen Befehl `OTA PREFLIGHT`. Er liest ausschließlich die Partitionstabelle und den OTA-Bootstatus. Es gibt **keinen** Aufruf von `esp_ota_begin`, `esp_ota_write` oder `esp_ota_set_boot_partition`. Keines dieser Geräte kann mit v0.5.8 über Funk eine neue Firmware installieren.

## Wozu der zusätzliche Schritt?

Das Arduino-Ergebnis `Maximum is 1310720 bytes` beweist alleine nicht, dass auf dem Gerät zur Laufzeit wirklich eine geeignete **inaktive OTA-App-Partition** verfügbar ist. Die neue Prüfung fragt direkt mit Espressif-APIs ab:

- `esp_ota_get_running_partition()` – tatsächlich laufende Anwendung
- `esp_ota_get_next_update_partition(nullptr)` – nächster OTA-App-Slot
- `esp_ota_get_boot_partition()` – im Bootloader ausgewählte Anwendung
- `esp_ota_get_state_partition()` – Zustand der laufenden Anwendung, sofern verfügbar

Bei fehlender oder offensichtlich zu kleiner/identischer Partition gibt es FAIL. Ein PASS bedeutet nur **geeignet erscheinender separater Slot** und keine vollständige Freigabe zum Flashen. Insbesondere prüft diese Version **keine** signierten Firmwaredateien.

## Kompilierung und Test (nur ein per USB erreichbarer C3)

```powershell
cd C:\pyprojects\smoke-listener-mesh
git pull origin main
Copy-Item .\firmware\mesh-v0.5.7\mesh_secrets.h .\firmware\mesh-v0.5.8\
```

`firmware/mesh-v0.5.8/mesh-v0.5.8.ino` in Arduino IDE öffnen. Die bisherigen Einstellungen beibehalten: XIAO_ESP32C3, ESP32 Arduino Core 3.3.12, 4 MB Flash, Default 4MB with SPIFFS (1.2MB APP/1.5MB SPIFFS), USB CDC On Boot an, Erase All Flash aus. **Zuerst nur kompilieren.**

Nach erfolgreichem Build kann man einen einzelnen, per USB rettbaren Testknoten aktualisieren, seriellen Monitor mit 115200 Baud öffnen und senden:

```text
OTA PREFLIGHT
```

Erwartete Ausgabe in etwa:

```text
[OTA] PREFLIGHT running=ota_0 size=... subtype=...
[OTA] PREFLIGHT next=ota_1 size=... subtype=...
[OTA] PREFLIGHT boot=ota_0
[OTA] PREFLIGHT image_state_result=... image_state=...
[OTA] PREFLIGHT PASS: separate OTA app slot exists; no flash operation attempted
```

Die tatsächlichen Partitionsnamen können abweichen. Bei FAIL **nicht** fortfahren, sondern die vollständige Ausgabe sichern.

## Für echten OTA-Transfer weiterhin erforderlich

1. Ein Wire-Format für signierte Release-Metadaten, das **auf dem ESP32 selbst** mit einem fest eingebauten öffentlichen Schlüssel geprüft wird (nicht nur auf dem PC).
2. Streaming der echten Firmwarebytes vom PC über den USB-Gatewayknoten durch ESP-NOW, inklusive Ziel/Session, Sequenz und wiederholbaren ACKs.
3. Hash des empfangenen Bildes mit signiertem Manifest vergleichen.
4. Inaktiven Slot erst nach erfolgreicher Signatur-/Zielprüfung öffnen und die geprüften Blöcke sequenziell schreiben; bei Unterbrechung abbrechen.
5. Endgültiges Image prüfen, Bootpartition aktivieren, Neustart mit Selbsttest/Rollback und USB-Rettungsmöglichkeit.

Siehe [Signaturwerkzeug](ota-signing.md) und [Gesamtplan](mesh-ota.md). Ein erfolgreicher RAM-only-Belastungstest kann diese Schritte nicht ersetzen.
