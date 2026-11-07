<#
.SYNOPSIS
Build, sign and verify exactly two v0.6.21 ESP32-C3 releases: audio+buzzer (.b)
for Testknoten and gateway (.c) for dedicated USB gateway. No flashing.
.DESCRIPTION
Never copies signing private key into the build tree. Local device headers
(mesh_secrets.h, ota_public_key.h) are copied into temporary isolated sketches;
keep OutputRoot outside the Git repository and restrict its access.
#>
[CmdletBinding()]
param(
  [string]$OutputRoot = "C:\mesh-ota-test\release-0621-dual",
  [string]$ArduinoCli = "arduino-cli",
  [string]$Fqbn = "esp32:esp32:XIAO_ESP32C3",
  [string]$PrivateKey = "C:\mesh-ota-keys\signing-private.pem",
  [string]$PublicKey = "C:\mesh-ota-keys\signing-public.pem",
  [string]$Python = "",
  [switch]$BuildOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sketchDir = Join-Path $repo "firmware\mesh-v0.6.21"
$sketch = Join-Path $sketchDir "mesh-v0.6.21.ino"
$signer = Join-Path $repo "tools\ota\sign_release.py"
if (-not $Python) { $Python = Join-Path $repo "myenv\Scripts\python.exe" }
foreach ($file in @($sketch,$signer,(Join-Path $sketchDir "mesh_secrets.h"),
                   (Join-Path $sketchDir "ota_public_key.h"),$Python)) {
  if (-not (Test-Path -LiteralPath $file)) { throw "Fehlende Voraussetzung: $file" }
}
if (-not $BuildOnly) {
  foreach ($file in @($PrivateKey,$PublicKey)) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Signierschluessel fehlt: $file" }
  }
}
$cli = (Get-Command $ArduinoCli -ErrorAction Stop).Source
$OutputRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputRoot)
$repoPrefix = $repo.TrimEnd('\') + '\'
if ($OutputRoot.StartsWith($repoPrefix,[StringComparison]::OrdinalIgnoreCase)) {
  throw "OutputRoot muss AUSSERHALB des Git-Repositorys liegen (enthaelt lokale Hardware-Header)"
}
if (Test-Path -LiteralPath $OutputRoot) {
  throw "Ausgabeordner existiert bereits: $OutputRoot. Fuer reproduzierbaren Neubau anderen -OutputRoot angeben."
}
$original = [System.IO.File]::ReadAllText($sketch)
$marker = '#define SMOKE_FIRMWARE_VERSION "0.6.21"'
if (-not $original.Contains($marker)) { throw "Quellversion 0.6.21 nicht gefunden" }
$profiles = @(
  @{Name="testknoten"; Version="0.6.21.b"; Gateway=0; Audio=1; Buzzer=1; Features="audio,buzzer"; Target="000020D37E6E27AC"},
  @{Name="gateway"; Version="0.6.21.c"; Gateway=1; Audio=0; Buzzer=0; Features="gateway"; Target="00000CEC7E6E27AC"}
)
$report = @()
foreach ($profile in $profiles) {
  $folder = Join-Path $OutputRoot $profile.Name
  $source = Join-Path $folder "source\mesh-v0.6.21"
  $work = Join-Path $folder "compile"
  $export = Join-Path $folder "export"
  $package = Join-Path $folder "package"
  New-Item -ItemType Directory -Force -Path $source,$work,$export,$package | Out-Null
  foreach ($header in @("audio_monitor.h","buzzer_diagnostic.h","feature_config.h",
                         "ota_auth.h","ota_version.h","mesh_secrets.h","ota_public_key.h")) {
    Copy-Item -LiteralPath (Join-Path $sketchDir $header) -Destination (Join-Path $source $header)
  }
  $builtSource = $original.Replace($marker,('#define SMOKE_FIRMWARE_VERSION "'+$profile.Version+'"'))
  $isolatedSketch = Join-Path $source "mesh-v0.6.21.ino"
  [System.IO.File]::WriteAllText($isolatedSketch,$builtSource,[System.Text.UTF8Encoding]::new($false))
  $flags = "-DFEATURE_GATEWAY=$($profile.Gateway) -DFEATURE_AUDIO=$($profile.Audio) -DFEATURE_CONFIG_AP=0 -DFEATURE_BATTERY=0 -DFEATURE_BUZZER=$($profile.Buzzer)"
  Write-Host "[BUILD] $($profile.Name): $($profile.Version) -> $($profile.Target)" -ForegroundColor Cyan
  & $cli compile --fqbn $Fqbn --build-path $work --output-dir $export --build-property ("compiler.cpp.extra_flags="+$flags) $source
  if ($LASTEXITCODE -ne 0) { throw "Build fehlgeschlagen: $($profile.Name)" }
  $bin = Join-Path $export "mesh-v0.6.21.ino.bin"
  if (-not (Test-Path -LiteralPath $bin)) { throw "OTA-Anwendungs-BIN fehlt: $bin" }
  $pkgBin = Join-Path $package "firmware.bin"
  Copy-Item -LiteralPath $bin -Destination $pkgBin
  $manifest = Join-Path $package ("manifest_"+$profile.Target+".json")
  $zip = Join-Path $folder ("smoke-mesh-"+$profile.Version+"-"+$profile.Name+".zip")
  if (-not $BuildOnly) {
    & $Python $signer sign --image $pkgBin --private-key $PrivateKey --target $profile.Target --version $profile.Version --features $profile.Features --out $manifest
    if ($LASTEXITCODE -ne 0) { throw "Signatur fehlgeschlagen: $($profile.Name)" }
    & $Python $signer verify --image $pkgBin --manifest $manifest --public-key $PublicKey
    if ($LASTEXITCODE -ne 0) { throw "Signaturpruefung fehlgeschlagen: $($profile.Name)" }
    Compress-Archive -LiteralPath $pkgBin,$manifest -DestinationPath $zip -ErrorAction Stop
  }
  $report += [pscustomobject]@{
    Profile=$profile.Name; Version=$profile.Version; Target=$profile.Target
    Features=$profile.Features; Bytes=(Get-Item -LiteralPath $pkgBin).Length
    Sha256=(Get-FileHash -LiteralPath $pkgBin -Algorithm SHA256).Hash.ToLowerInvariant()
    Bin=$pkgBin; Manifest= $(if ($BuildOnly) {$null} else {$manifest})
    Zip= $(if ($BuildOnly) {$null} else {$zip})
  }
}
$reportPath = Join-Path $OutputRoot "build-report.json"
[System.IO.File]::WriteAllText($reportPath,(ConvertTo-Json -InputObject $report -Depth 4),[System.Text.UTF8Encoding]::new($false))
$report | Format-Table Profile,Version,Target,Features,Bytes,Zip -AutoSize
Write-Host "[DONE] $reportPath" -ForegroundColor Green
Write-Host "No firmware flashed. Private signing key stayed at configured path." -ForegroundColor Yellow
