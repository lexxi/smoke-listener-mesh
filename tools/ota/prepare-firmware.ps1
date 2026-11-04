param(
    [ValidateSet("0.6.11","0.6.12","0.6.13")]
    [string]$Version = "0.6.11",
    [string]$From = "0.6.10"
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$source = Join-Path $repo ("firmware\mesh-v" + $From)
$destination = Join-Path $repo ("firmware\mesh-v" + $Version)
if (-not (Test-Path $destination)) { throw "Zielfirmware fehlt: $destination" }
foreach ($name in @("mesh_secrets.h", "ota_public_key.h")) {
    $src = Join-Path $source $name
    $dst = Join-Path $destination $name
    if (-not (Test-Path $src)) { throw "Privater Header fehlt in Quelle: $src" }
    if (Test-Path $dst) {
        Write-Host "Schon vorhanden (nicht überschrieben): $dst"
    } else {
        Copy-Item -LiteralPath $src -Destination $dst
        Write-Host "Lokal kopiert: $name"
    }
}
Write-Host "Bereit zum Arduino-Compile: $destination" -ForegroundColor Green
Write-Host "WICHTIG: Diese privaten Header niemals zu GitHub committen."
