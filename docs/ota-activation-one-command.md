# Ein-Befehl-OTA-Aktivierung (v0.6.6 → v0.6.7)

**Entwicklungsstand:** Skript im GitHub-Repository; automatische Kombination aus Staging und Bootaktivierung **noch nicht auf Hardware getestet**. Ein fehlgeschlagener Boot-/Rollback-Test kann USB-Recovery erfordern.

## Voraussetzungen

- 1OG: Firmware **v0.6.6** in `app0` auf **COM15**.
- Kueche: v0.6.1 auf **COM12**.
- Signiertes v0.6.7-Image und Manifest müssen unverändert vorhanden sein.
- Beide Arduino Serial Monitor schließen.
- USB-Verbindung zu 1OG für Recovery verfügbar halten.

## Zuerst: Signatur/Dateien ohne COM-Zugriff kontrollieren

```powershell
git pull origin main
.\tools\ota\ota-activate.ps1 -DryRun
```

## Aktivierung (ÄNDERT `otadata`)

```powershell
.\tools\ota\ota-activate.ps1
```

Der Launcher nutzt `tools/ota/ota_test.py --activate` und erledigt:
1. Offline-Validierung von Signatur, Ziel-ID, Image und SHA-256.
2. Durchgängige Verbindung COM15; `NAME GET` und `BOOT STATUS` prüfen v0.6.6 und `app0`.
3. Lokales `FLASH ARM`, Signaturmanifest-Transfer über COM12, Flash-Staging von v0.6.7.
4. `BOOT VERIFY` mit erneutem Flash-Readback, Abbruch bei jedem Fehler.
5. **Expliziter Halt vor der Bootauswahl.** Nur die **exakte interaktive Eingabe** `ACTIVATE 1OG 0.6.7` autorisiert die nächsten Schritte.
6. `BOOT ARM` (60 s), `BOOT ACTIVATE`, `BOOT STATUS` kontrollieren `running=app0 boot=app1`.
7. **Kein Neustart, keine automatische Firmwarebestätigung.** Abschluss- und Fehlerlogs unter `log/ota_test_....log`.

Die Skriptausführung kann etwa 3–4 Minuten dauern, weil das bereits gespeicherte Image **noch einmal übertragen und verifiziert** wird. Grund: Das signierte Manifest und die Freigabe liegen in der laufenden Firmware nur im RAM; nach dem früheren Lesen der `otadata` erfolgte ein Reset.

## Entscheidend

- Der normale `ota-test.ps1` bleibt ein reiner Staging-/Readback-Test und ändert **nie** die Bootauswahl.
- Die Aktivierung ist ein gesonderter, expliziter Vorgang. **Nicht ausführen**, solange der getestete Rückfall-/Recovery-Ablauf nicht bereitsteht.
- Der bestätigte neue Bootslot bedeutet **noch nicht**, dass v0.6.7 bereits gebootet hat.
- Erst in einem separaten Test mit USB-Zugriff: Neustart → `PENDING_VERIFY` auslesen → authentifizierte Mesh-Verbindung prüfen → kontrolliert `BOOT CONFIRM` oder absichtlich unbestätigt erneut starten und Rückfall auf `app0` prüfen.
- ESP-IDF-Rollback ist im bereitgestellten Core konfiguriert, aber der tatsächlich installierte Bootloader und der Rückfallmechanismus sind **nicht auf Hardware bewiesen**.
- Vor jedem Neustart nach aktivierter `app1` muss ein funktionierender USB-Recovery-Weg feststehen.
