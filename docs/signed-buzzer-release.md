# Signierte Buzzer-Firmware – Erweiterung des Release-Vertrags

Status: **Vorbereitung / noch nicht ausrollbar**. Dieser Branch stellt
die Signierungs- und Build-Unterstützung bereit, **nicht** die neue
Firmware `0.6.18`. Bestehende `0.6.16`/`0.6.17`-Releases
und die acht Profile `.a` bis `.h` bleiben gültig.

## Kompatibilitätsentscheidung

- Die acht Variantenbuchstaben `.a` bis `.h` bezeichnen weiterhin
  ausschließlich die Kombinationen aus `gateway`, `audio` und
  `config_ap`.
- Der Buzzer ist ab **0.6.18** ein zusätzliches signiertes Feature
  `buzzer` (in `feature_claim.features`).
- Es gibt **keine** neuen Variantenbuchstaben `.i` bis `.p`.
  Die älteren Empfänger und die Webapp kennen nur `.a` bis `.h`.
- Signierte Buzzer-Claims für `0.6.17` oder älter werden
  abgewiesen. Diese Versionsnummern dürfen nicht für eine geänderte
  Kombination erneut verwendet werden.

## Build-Matrix (zukünftige Firmware 0.6.18)

Ohne Schalter bleibt das Verhalten unverändert:

```powershell
.\tools\ota\build-release-matrix.ps1 -Version 0.6.17 -BuildOnly -OutputRoot .\firmware\mesh-v0.6.17\build\matrix-check
```

Mit der **erst noch bereitzustellenden** Firmwareversion 0.6.18
kann eine Buzzer-Variante ausdrücklich angewählt werden:

```powershell
.\tools\ota\build-release-matrix.ps1 -Version 0.6.18 -Buzzer -BuildOnly
```

Ohne `-BuildOnly` signiert das Skript lokal für die freigegebenen
Zielknoten und prüft die Manifeste gegen den öffentlichen Schlüssel.
Die privaten Schlüssel dürfen niemals ins Repository gelangen.

**Wichtig:** Die optionale Buzzer-Kombination ist *kein neuer*
Variantenbuchstabe. Für eine bestimmte Firmwareversion plus Buchstabe
darf daher nur **eine eindeutig definierte Featurekombination**
veröffentlicht werden. Nicht gleichzeitig beispielsweise
`0.6.18.b` als `audio` und als `audio+buzzer` anbieten:
Dieselbe Versionsidentität kann auf dem Zielgerät nicht zwischen
beiden unterscheiden. Wähle die Zielkonfiguration vor dem Build
und erhöhe die Firmwareversion bei späteren Änderungen.

## Vor dem ersten echten Buzzer-OTA-Release

1. Eigenständige Firmware `0.6.18` anlegen und lokal mit dem
   Buzzer-Feature auf dem Testknoten prüfen.
2. Gesamte Python-Testreihe und acht Buildprofile laufen lassen.
3. Prüfen, dass `sign_release.py`, `prepare_transfer.py`,
   die Web-Releasebibliothek und Remote-OTA die zusätzliche signierte
   `buzzer`-Angabe korrekt verarbeiten.
4. Mindestens ein neu signiertes Paket offline mit dem
   vorhandenen öffentlichen Schlüssel verifizieren.
5. Ein echtes OTA nur zum freigegebenen Testknoten durchführen,
   mit Boot-Verifikation und möglichem Rollback.
6. Erst danach weitere Knoten freigeben.

`FEATURE_BUZZER=1` bedeutet derzeit lediglich eine **lokale
serielle Diagnosefunktion** – es existiert weiterhin **keine
automatische akustische Rauchalarmweiterleitung**. Der selbst erzeugte
Buzzer-Ton wird vom INMP441 erfasst; diese Rückkopplung ist vor
einer Alarmfunktion explizit zu behandeln.
