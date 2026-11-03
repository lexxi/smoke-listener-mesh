# v0.6.8 – Arduino OTA-Autobestätigung deaktivieren

## Warum?

Beim ersten OTA-Boot der v0.6.7 wurde `running_state=2` (`ESP_OTA_IMG_VALID`) gemeldet, obwohl der Sketch `BOOT CONFIRM` nicht ausgeführt hatte. Die Arduino-ESP32-Initialisierung ruft bei einem unbestätigten OTA-Image standardmäßig `verifyOta()` (Default: true) auf und markiert es unmittelbar als gültig. Dadurch war der gewünschte Rollback-Test nicht möglich.

## Änderung in v0.6.8

`firmware/mesh-v0.6.8/mesh-v0.6.8.ino` definiert:

```cpp
extern "C" bool verifyRollbackLater() {
  return true;
}
```

Das überschreibt die schwache Hook-Implementierung des Arduino-Cores und überspringt dessen sofortige Bestätigung. `BOOT CONFIRM` bleibt bewusst ein **manueller** serieller Befehl; die bereits vorhandene Prüfung verlangt `ESP_OTA_IMG_PENDING_VERIFY` plus einen authentifizierten Mesh-Empfang.

**Nicht** als Beweis werten, dass die C++-Datei kompiliert. Entscheidend ist, dass der laufende Sketch nach dem ersten OTA-Boot `running_state=1` meldet.

## Teststufen

1. **Nur kompilieren** mit genau den bisherigen Board-Optionen (ESP32-C3 / Arduino 3.3.12 / OTA-Partitionen), keine USB-Installation von v0.6.8 auf 1OG.
2. v0.6.8 als neues Image exportieren; signiertes Manifest für die Node-ID `000010637C6E27AC` erzeugen/verifizieren.
3. **Vor Übertragung** OTA-Sender-Skripte für die neue Ausgangsposition prüfen: 1OG läuft derzeit auf **v0.6.7 in app1**, Zielpartition ist nun **app0**. Der alte Automatiktest erwartet v0.6.6 in app0 und darf dafür nicht unverändert benutzt werden.
4. Nach verifizierter Übertragung und kontrollierter Aktivierung genau **einen** ersten Boot in v0.6.8 durchführen.
5. `BOOT STATUS` auslesen. Erwarteter Zustand bei funktionierender Verzögerung: `running=app0`, `boot=app0`, `version=0.6.8`, `running_state=1` (PENDING_VERIFY).
6. **Nicht** `BOOT CONFIRM` senden; der zweite Neustart ist der absichtliche Rückfalltest auf v0.6.7. Er braucht einen weiterhin funktionierenden USB-Recovery-Pfad.
7. Erst nach geprüftem Rückfall einen gesonderten positiven Test mit neuem OTA-Image und anschließender expliziter `BOOT CONFIRM` durchführen.

**Status:** Code für v0.6.8 auf GitHub; **noch nicht auf Zielhardware gebaut, signiert, übertragen oder getestet**.

Referenz: https://github.com/espressif/arduino-esp32/blob/master/cores/esp32/esp32-hal-misc.c (`verifyRollbackLater`, `initArduino`).
