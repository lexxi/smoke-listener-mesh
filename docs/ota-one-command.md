# OTA-Staging und Flash-Readback mit einem Befehl

**Ziel:** Signierte v0.6.7 über Kueche nach 1OG übertragen, in `app1` schreiben, erneut aus dem Flash prüfen. **Keine Bootaktivierung und kein Neustart.**

**Voraussetzungen (Stand 2026-11-04):**
- Kueche: v0.6.1, COM12
- 1OG: v0.6.6, COM15; `app0` läuft und ist Bootziel
- v0.6.7 bereits lokal gebaut und als `C:\mesh-ota-keys\release-1og-067.json` für Node `000010637C6E27AC` signiert
- Python-venv `myenv` mit den bereits verwendeten `pyserial`-/`cryptography`-Bibliotheken
- Arduino Serial Monitor für **beide** COM-Ports schließen. Das Python-Skript besitzt COM15 durchgehend; Arduino darf COM15 nicht parallel öffnen.
- Beide Geräte zuverlässig per USB versorgen. Kueche COM12, 1OG COM15.

## Ausführen

Im Projektverzeichnis PowerShell:

```powershell
git pull origin main
.\tools\ota\ota-test.ps1
```

Optional nur lokale Vorprüfung ohne COM-Ports zu öffnen:

```powershell
.\tools\ota\ota-test.ps1 -DryRun
```

Bei anderen Ports:

```powershell
.\tools\ota\ota-test.ps1 -Gateway COM12 -TargetPort COM15
```

## Was das Skript automatisch erledigt

1. Prüft offline ECDSA-P-256-Signatur und SHA-256 der v0.6.7 gegen das Manifest.
2. Öffnet **COM15 durchgehend** mit deaktivierten DTR-/RTS-Steuersignalen, prüft per `NAME GET` Node-ID und per `BOOT STATUS` Version v0.6.6 / `app0`.
3. Sendet `FLASH ARM` lokal an 1OG.
4. Ruft die vorhandenen `send_manifest.py` und `send_image.py --flash-stage` auf Kueche (COM12) nacheinander auf.
5. Prüft auf 1OG: `FLASH STATUS` mit `staged_valid=1`, `BOOT VERIFY PASS signed=0.6.7` mit exakter Bytelänge und `BOOT STATUS` (`boot=app0`, `verified=1`, `arm_valid=0`).
6. Beendet erfolgreich nur bei allen Prüfungen. Detailliertes Log in `log/ota_test_YYYYMMDD_HHMMSS.log`.

**Das Skript sendet niemals `BOOT ARM`, `BOOT ACTIVATE`, `BOOT CONFIRM` oder einen Reboot-Befehl.** `FLASH ARM` ist hiervon verschieden und autorisiert ausschließlich das Schreiben in `app1`.

## Fehler und Grenzen

- Das Werkzeug ist neu; **noch nicht auf dem Windows-System/der Hardware ausgeführt**. Bei `STOP` oder `FAILED` Logs ansehen, nicht unkontrolliert neu starten oder erneut ausführen.
- Es automatisiert nur den **bereits mehrfach erprobten Flash-Staging-/Readback-Ablauf**, nicht das eigentliche Umschalten oder die praktische Rollback-Bestätigung.
- Öffnen eines USB-Ports kann je nach Board einen Reset verursachen. Das Skript prüft danach die laufende Firmware. Es hält COM15 danach durchgehend geöffnet, damit der auth-/arm-Status beim Wechsel zwischen Manifest- und Image-Transfer nicht verloren geht.
- Eine Übertragung von ~1 MB benötigt bei den letzten Tests weiterhin etwa 3–4 Minuten. Ein-Befehl-Automatisierung spart Bedienungsschritte, nicht Funkzeit.
- Der private Signierschlüssel wird **nicht** vom Skript gelesen; der signierte Release muss zuvor separat erstellt worden sein.
- Für den späteren echten Bootwechsel braucht es einen **eigenen** Test inklusive USB-Recovery und praktisch geprüfter Bootloader-Rollback-Funktion.

## Notfall

Wenn die Übertragung fehlschlägt: **kein** `BOOT ACTIVATE` ausführen. Der bisherige Bootslot bleibt normalerweise unverändert, solange kein anderes Werkzeug ihn verändert. Auf COM15 `OTA PREFLIGHT` / `BOOT STATUS` prüfen, bevor weitere Versuche starten.
