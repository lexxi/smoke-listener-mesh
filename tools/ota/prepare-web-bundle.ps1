param(
  [string]$Version = "0.6.15",
  [string]$Image = "",
  [string]$PrivateKey = "C:\mesh-ota-keys\signing-private.pem",
  [string]$Output = "",
  [string[]]$Features = @()
)
$ErrorActionPreference = "Stop"
if ($Version -eq "0.6.15") {
  throw "Dieses alte Bundle-Skript ist fuer die vierteilige Version nicht geeignet. Bitte tools/ota/build-release-matrix.ps1 verwenden."
}
$allowedFeatures = @("gateway", "audio", "config_ap")
foreach ($feature in $Features) {
  if ($feature -cnotin $allowedFeatures) { throw "Unbekanntes Feature: $feature" }
}
if (($Features | Select-Object -Unique).Count -ne $Features.Count) {
  throw "Doppelte Feature-Angabe"
}
if ($Version -eq "0.6.15" -and -not $PSBoundParameters.ContainsKey("Features")) {
  throw "Fuer v0.6.15 -Features explizit angeben: @() fuer CORE oder @('audio') / @('gateway')"
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ($Version -eq "0.6.15") {
  $header = Join-Path $repo "firmware\mesh-v0.6.15\feature_config.h"
  if (-not (Test-Path $header)) { throw "Feature-Konfiguration fehlt: $header" }
  $source = Get-Content -LiteralPath $header -Raw
  $flags = @{"gateway"="FEATURE_GATEWAY";"audio"="FEATURE_AUDIO";"config_ap"="FEATURE_CONFIG_AP"}
  foreach ($item in $flags.GetEnumerator()) {
    $match = [regex]::Match($source, "(?m)^\s*#define\s+" + $item.Value + "\s+([01])\s*$")
    if (-not $match.Success) { throw "Feature-Schalter nicht lesbar: $($item.Value)" }
    $enabled = $match.Groups[1].Value -eq "1"
    $declared = $Features -contains $item.Key
    if ($enabled -ne $declared) {
      throw "Feature-Abweichung: $($item.Value)=$([int]$enabled), signiert=$([int]$declared). Erst konfigurieren und dieselbe BIN neu kompilieren."
    }
  }
}
$python = Join-Path $repo "myenv\Scripts\python.exe"
$nodes = @("000010637C6E27AC","000058FE7D6E27AC","000094457F6E27AC","0000A0E37E6E27AC")
if (-not $Image) { $Image = Join-Path $repo ("firmware\mesh-v$Version\build\esp32.esp32.XIAO_ESP32C3\mesh-v$Version.ino.bin") }
if (-not $Output) { $Output = "C:\mesh-ota-keys\smoke-mesh-v$Version-ota.zip" }
if (-not (Test-Path $python)) { throw "Python-venv fehlt: $python" }
if (-not (Test-Path $Image)) { throw "Firmware-BIN fehlt: $Image" }
if (-not (Test-Path $PrivateKey)) { throw "Private Signing-Key fehlt: $PrivateKey" }
if (Test-Path $Output) { throw "Release-ZIP existiert bereits: $Output" }
$signer = Join-Path $repo "tools\ota\sign_release.py"
$temp = Join-Path $env:TEMP ([guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temp -Force | Out-Null
try {
  Copy-Item -LiteralPath $Image -Destination (Join-Path $temp "firmware.bin")
  foreach ($target in $nodes) {
    $manifest = Join-Path $temp ("manifest_" + $target + ".json")
    $signArgs = @("sign", "--image", (Join-Path $temp "firmware.bin"), "--private-key", $PrivateKey,
      "--target", $target, "--version", $Version, "--out", $manifest)
    if ($PSBoundParameters.ContainsKey("Features")) {
      $signArgs += @("--features", ($Features -join ","))
    }
    & $python $signer @signArgs
    if ($LASTEXITCODE -ne 0) { throw "Signatur fehlgeschlagen für $target" }
  }
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [System.IO.Compression.ZipFile]::CreateFromDirectory($temp,$Output)
  Write-Host "Signiertes Release-Paket erstellt: $Output" -ForegroundColor Green
  Write-Host "Enthält EINE BIN und $($nodes.Count) signierte Knotenmanifeste."
  Write-Host "In der Webapp nur dieses ZIP hochladen."
  if ($PSBoundParameters.ContainsKey("Features")) {
    Write-Host "Signierte Feature-Angabe: $(if ($Features.Count) { $Features -join ', ' } else { 'CORE' })"
    Write-Warning "Feature-Angabe gegen tatsaechlich kompilierte Schalter pruefen; die Signatur beweist nicht deren Aktivierung."
  }
} finally {
  Remove-Item -LiteralPath $temp -Force -Recurse -ErrorAction SilentlyContinue
}
