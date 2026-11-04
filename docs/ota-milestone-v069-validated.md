# OTA-Meilenstein: signierte Updates und Rollback auf 1OG

Stand: 2026-11-04 · Hardwaretest erfolgreich · Node 1OG `000010637C6E27AC` (ESP32-C3, COM15)

## Testumgebung

| Knoten | Stand | Funktion |
| --- | --- | --- |
| Kueche | v0.6.1, COM12 | ESP-NOW-Gateway, authentifizierte HEARTBEATs |
| 1OG | **v0.6.9**, `app0`, `ESP_OTA_IMG_VALID` (2) | Testziel |
| 1OG Rückfallslot | v0.6.7, `app1`, `ESP_OTA_IMG_VALID` (2) | Vorherige bestätigte Firmware |

OTA-Partitionen auf 1OG: `app0` 0x10000, `app1` 0x150000, jeweils 1.310.720 Byte; `otadata` 0xE000 mit 8 KiB. Bootloader-Rollback wurde auf genau diesem Testgerät experimentell bestätigt.

## Erfolgreich nachgewiesen

1. **Signierte Firmware:** Offline ECDSA-P-256/SHA-256-Prüfung und geräteseitige Manifestprüfung. Images werden ausschließlich in den inaktiven OTA-Slot geschrieben.
2. **Flash-Readback:** Auf dem ESP32-C3 SHA-256-Vergleich gegen die signierten Metadaten; positiver `BOOT VERIFY PASS`.
3. **Bootauswahl:** `BOOT ARM` und `BOOT ACTIVATE` setzen `otadata` kontrolliert auf den vorher verifizierten inaktiven Slot, ohne automatischen Neustart.
4. **Negativer Rollback-Test – v0.6.8:** Nach OTA aus v0.6.7 nach `app0` erster Start mit `running_state=1` (`PENDING_VERIFY`); **kein** `BOOT CONFIRM`; erneuter Reset. Gerät bootete v0.6.7 aus `app1` (`running_state=2`), inaktives v0.6.8 war `inactive_state=4` (`ABORTED`).
5. **Positiver Bestätigungstest – v0.6.9:** Aus v0.6.7 nach `app0` übertragen, signiert und verifiziert. Erster Start als `PENDING_VERIFY` (`running_state=1`), authentifizierter HEARTBEAT von Kueche mit `AUTH=OK` und `mesh_peer_verified=1`, danach `BOOT CONFIRM` → `[BOOT] CONFIRM OK err=0`; Statuswechsel auf `running_state=2` (`VALID`).
6. **Persistenz:** Weiterer physischer Reset; 1OG startete erneut v0.6.9 aus `app0`, `boot=app0`, `running_state=2` (`VALID`), weiterhin `AUTH=OK` über Kueche.

## Relevante Implementierungsdetails

- In v0.6.8 und v0.6.9 unterdrückt `extern "C" bool verifyRollbackLater() { return true; }` die automatische Bootbestätigung durch den Arduino-ESP32-Core; dadurch bleibt der neue Slot bis zur bewussten Bestätigung in `PENDING_VERIFY`.
- `BOOT CONFIRM` ist ausschließlich ein **lokaler serieller Befehl**, der `PENDING_VERIFY` und einen authentifizierten Mesh-Empfang voraussetzt. Der Test eines authentifizierten HEARTBEATs ist **kein** vollständiger Ende-zu-Ende-Rauchalarmtest.
- Die lokale Freigabe für `BOOT ACTIVATE` benötigt eine während derselben Laufzeit erfolgreiche Prüfung der signierten Metadaten und des Flash-Images. Auth-/Staging-Status liegt derzeit nur **im RAM**: Nach Reset können für eine erneute Aktivierung neue signierte Metadaten bzw. erneutes Staging nötig sein.
- `ota_test.py` und die PowerShell-Launcher automatisieren Übertragung, Geräteprüfung, Flash-Readback und auf expliziten Wunsch Bootaktivierung. Die interaktive Freigabe wird während der Eingabe nicht mehr mit seriellen Statusmeldungen überlagert.
- Ein abgeschlossener OTA-Test ist kein automatischer Freigabenachweis für alle Mesh-Knoten oder andere Bootloader-Versionen.

## Bewusst offen

- **Remote-Aktivierung und Remote-Bestätigung ohne USB** sind noch nicht umgesetzt; aktuelle Sicherheitsgrenze ist der lokale serielle Bedienzugriff.
- Persistente, signiert gebundene OTA-Freigabemetadaten fehlen: unnötige Wiederholungstransfers können nach Neustart auftreten.
- End-to-End-Tests der Rauchalarm-Erkennung/Alarmweiterleitung, Fehlerfälle bei Stromverlust während Bootaktivierung und produktionsreife Remote-Recovery-Strategie müssen gesondert bewertet werden.

## Nächste Arbeit

Die funktionierende Version v0.6.9 auf 1OG nicht verändern. Als separate Entwicklung planen: über Mesh authorisierte Bootaktivierung, gesicherte Freigabe nach gezieltem Mesh-Selbsttest, persistente Signaturmetadaten und nachvollziehbare Recovery-Strategie.
