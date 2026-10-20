# Mesh v0.5.1 – Inbetriebnahme

**Nur experimentelles Funkprotokoll. Keine Brandalarmfunktion oder sicherheitskritische Nutzung.**

## Schlüssel

Die drei Boards verwenden einen **identischen zufälligen 256-Bit-Schlüssel**. Die `mesh_secrets.h.example` in `mesh_secrets.h` kopieren und im selben Sketch-Ordner ablegen. Die 32 Nullbytes **unbedingt ersetzen**, bevor du die Firmware flashst. Unter PowerShell:

```powershell
$b = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($b)
($b | ForEach-Object { '0x{0:X2}' -f $_ }) -join ', '
```

Die Ausgabe zwischen die geschweiften Klammern einfügen. Den identischen Header lokal in allen drei Sketch-Verzeichnissen verwenden, **niemals auf GitHub pushen oder im Chat posten**. Für private Änderungen nach Möglichkeit identischen Sketch auf alle Boards flashen und nur eine lokale Schlüsseldatei verwenden.

`MESH_NETWORK_ID` ist eine öffentliche Kennung, kein Geheimnis. Der HMAC muss für authentifizierte Pakete stimmen. Alte v0.5.0-Broadcasts werden verworfen.

## Test

1. Alle drei Boards auf v0.5.1 flashen; die Arduino IDE muss `mesh_secrets.h` im selben Sketch-Ordner finden.
2. Serial Monitor auf 115200. Überprüfen, dass `Node=` für alle unterschiedlich ist.
3. `[RX] origin=... via=... ttl=... hops=... AUTH=OK` zeigt ursprünglichen Sender und direkten Funk-Nachbarn.
4. `ttl=3 hops=0` ist direkter Empfang; `ttl=2 hops=1` ist nach einer Weiterleitung.
5. Mit **nur zwei** Knoten ist keine echte A→B→C-Strecke bewiesen. Drei Geräte so aufstellen, dass A und C keinen direkten Link haben; mit Vergleichstest bei ausgeschaltetem B prüfen.
6. Nach 30–60 Sekunden Logs aller Knoten sichern. Kein Rauchmelderpiepsen nötig.

## Sicherheitsgrenzen

HMAC-SHA256 authentifiziert nur den unveränderlichen Paketinhalt (bis vor `ttl`). Die TTL ist bewusst **nicht** kryptografisch geschützt und darf nicht als vertrauenswürdige Hop-Bescheinigung betrachtet werden; `via` bezeichnet nur die direkte Funk-MAC, diese ist ebenfalls kein Authentizitätsnachweis. Broadcast-Payload bleibt lesbar. Gültige alte Pakete könnten wieder eingespielt werden: Der Cache blockiert Duplikate nur innerhalb eines begrenzten Zeit-/Speicherfensters, ein dauerhafter Replay-Schutz fehlt. Boot-Nonce und Sequenz reduzieren versehentliche Kollisionen, ersetzen aber keinen persistenten Replay-Schutz. Schlüsselinhaber können Pakete fälschen. Funkblockierung und Paketverlust bleiben möglich.

Es werden ausschließlich `TEST` und `HEARTBEAT` verarbeitet, **keine ALARM-Nachrichten**. Statuswerte `TX status=0` bedeuten nicht nachgewiesene Auslieferung. Das System bleibt eine experimentelle Erweiterung neben unveränderten zertifizierten Rauchmeldern.
