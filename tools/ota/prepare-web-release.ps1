param(
    [ValidateSet("1OG","Garage","Kueche","FZRaum")]
    [string]$Node = "1OG",
    [string]$Version = "0.6.10",
    [string]$Image = "",
    [string]$PrivateKey = "C:\mesh-ota-keys\signing-private.pem",
    [string]$Output = ""
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repo "myenv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python-Umgebung fehlt: $python" }
$nodes = @{
    "1OG"    = "000010637C6E27AC"
    "Garage" = "000058FE7D6E27AC"
    "Kueche" = "000094457F6E27AC"
    "FZRaum" = "0000A0E37E6E27AC"
}
if (-not $Image) {
    $Image = Join-Path $repo ("firmware\mesh-v$Version\build\esp32.esp32.XIAO_ESP32C3\mesh-v$Version.ino.bin")
}
if (-not $Output) {
    $Output = "C:\mesh-ota-keys\release-$($Node.ToLower())-$($Version.Replace('.','')).json"
}
if (-not (Test-Path $Image)) { throw "Firmware-BIN fehlt: $Image" }
if (-not (Test-Path $PrivateKey)) { throw "Private Signing-Key fehlt: $PrivateKey" }
if (Test-Path $Output) { throw "Manifest existiert bereits: $Output (kein Überschreiben)" }
$signer = Join-Path $repo "tools\ota\sign_release.py"
Write-Host "Erstelle signiertes Manifest fuer $Node v$Version; Target=$($nodes[$Node])"
& $python $signer sign --image $Image --private-key $PrivateKey --target $nodes[$Node] --version $Version --out $Output
if ($LASTEXITCODE -ne 0) { throw "Signierung fehlgeschlagen" }
Write-Host "Fertig. In der Webapp diese Dateien hochladen:" -ForegroundColor Green
Write-Host "BIN:      $Image"
Write-Host "Manifest: $Output"
