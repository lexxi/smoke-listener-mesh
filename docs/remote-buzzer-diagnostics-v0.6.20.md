# v0.6.20: Remote-Buzzer-Diagnose (Entwicklungsstand)

Die experimentelle Web-Knotenverwaltung kann zwei neue, authentifizierte
Diagnosebefehle senden:

- `BUZZER_TEST` (MGMT 11): 2.000-Hz-Testton, 500 ms.
- `BUZZER_2X2` (MGMT 12): vier 2.000-Hz-Töne mit kurzem und langem Abstand.

Es werden **keine Rauchalarm-Pakete** ausgelöst. Die Remote-Antwort bestätigt
nur, dass die Wiedergabe gestartet wurde, **nicht**, dass der Ton akustisch
messbar war. Die Erkennung des INMP441 filtert 3.000–3.450 Hz: Der bestehende
2.000-Hz-Buzzer-Test prüft den Audiofilter nicht.

## Voraussetzungen

- Testknoten mit v0.6.20, `FEATURE_BUZZER=1`, Buzzer an GPIO5 (XIAO ESP32-C3).
- USB-Gateway muss ebenfalls mit v0.6.20 und `FEATURE_GATEWAY=1`
  aktualisiert werden; das bisherige v0.6.16.c-Gateway kann die neuen
  Aktionsnamen nicht über die serielle Schnittstelle interpretieren.
- Webapp mit den Änderungen aus dieser Branch; Fernsteuerung ausschließlich
  über den Admin-SSH-Tunnel, beispielsweise
  `ssh -N -L 18088:127.0.0.1:8088 tc@picore`.
- Die bisherige Konfiguration für authentifiziertes ESP-NOW-Mesh und
  vertrauenswürdige Gateways bleibt unverändert.

Die neuen Aktionen nutzen den vorhandenen Gateway-Vertrauensanker, den
HMAC-geschützten Managementframe und den einmaligen Node-Nonce. Befehle
werden bei laufendem oder gerade installierten OTA-Image sowie bei
fehlender Buzzer-Unterstützung abgewiesen.

## Testablauf (noch nicht ausgeführt)

1. Auf Windows die v0.6.20-Profile für **Audio+Buzzer-Ziel** und
   **USB-Gateway** kompilieren. Ohne erfolgreichen Build kein Flash.
2. Zuerst auf dem Testknoten `000020D37E6E27AC` die signierte v0.6.20
   über den bestehenden Gateway staged/aktivieren und `state=2` prüfen.
3. Den Gateway über USB auf das geprüfte Gateway-Profil aktualisieren.
   Der Logger muss dafür gestoppt und der Port freigegeben werden.
4. Auf piCore die Webapp aktualisieren. Vorher Daten/Umgebung sichern;
   die Webapp nach dem Git-Pull neu starten.
5. Auf `/nodes` Testknoten und Gateway wählen, ausschließlich im
   Admin-Tunnel „Buzzer: Testton“ und „Buzzer: 2×2“ auslösen.
6. Im Jobprotokoll `BUZZER START ACCEPTED` prüfen und das akustische
   Ergebnis separat protokollieren.

**Nicht mit Produktionsrauchmeldern testen.** Keine Überprüfung der
Brandalarmfunktion, der Audio-Gruppenerkennung oder des automatischen
Rollback durch diese Diagnose.

## Nächste Ausbaustufe

`AUDIO_STATUS` mit echten Mess-/Fehlerzählern, danach ein gesondertes,
passend zur Erkennungsfrequenz ausgelegtes Testmuster. Nicht Bestandteil
dieses ersten Buzzer-Patches.
