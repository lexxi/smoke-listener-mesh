<#
.SYNOPSIS
Build and optionally sign all eight v0.6.15.a .. v0.6.15.h profiles.
USB flashing and remote OTA are deliberately not performed here.
#>
[CmdletBinding()]
param(
  [string]$Version = "0.6.15",
  [string]$Fqbn = "esp32:esp32:XIAO_ESP32C3:UploadSpeed=921600,CDCOnBoot=default,CPUFreq=160,FlashFreq=80,FlashMode=qio,FlashSize=4M,PartitionScheme=default,DebugLevel=none,EraseFlash=none",
  [string]$ArduinoCli = "arduino-cli",
  [string]$PrivateKey = "C:\mesh-ota-keys\signing-private.pem",
  [string]$PublicKey = "C:\mesh-ota-keys\signing-public.pem",
  [string]$TargetsFile = "",
  [string]$OutputRoot = "",
  [switch]$BuildOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version muss numerisch sein, z.B. 0.6.15" }
$sketchDir = Join-Path $repo ("firmware\mesh-v" + $Version)
$sketch = Join-Path $sketchDir ("mesh-v" + $Version + ".ino")
if (-not (Test-Path -LiteralPath $sketch)) { throw "Sketch fehlt: $sketch" }
foreach ($header in @("feature_config.h","mesh_secrets.h","ota_public_key.h")) {
  if (-not (Test-Path -LiteralPath (Join-Path $sketchDir $header))) {
    throw "Firmware-Header fehlt: $header"
  }
}
$cli = Get-Command $ArduinoCli -ErrorAction Stop
$python = Join-Path $repo "myenv\Scripts\python.exe"
if (-not $TargetsFile) { $TargetsFile = Join-Path $repo "web\data\node_targets.json" }
if (-not $OutputRoot) { $OutputRoot = Join-Path $repo ("firmware\mesh-v"+$Version+"\build\release-matrix-4part") }
if (Test-Path -LiteralPath $OutputRoot) {
  throw "Ausgabe existiert bereits: $OutputRoot. Neuen -OutputRoot angeben."
}
$targets = @()
if (-not $BuildOnly) {
  foreach ($required in @($PrivateKey,$PublicKey,$python,$TargetsFile)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Signatur-Voraussetzung fehlt: $required" }
  }
  $json = Get-Content -LiteralPath $TargetsFile -Raw
  if (-not $json.TrimStart().StartsWith("[")) { throw "node_targets.json muss ein JSON-Array sein" }
  $parsed = @(ConvertFrom-Json -InputObject $json)
  foreach ($target in $parsed) {
    if ($target -isnot [string] -or $target -cnotmatch '^[0-9A-F]{16}$' -or $target -eq '0000000000000000') {
      throw "Ungueltige Ziel-ID"
    }
    if ($targets -contains $target) { throw "Doppelte Ziel-ID: $target" }
    $targets += $target
  }
  if ($targets.Count -eq 0 -or $targets.Count -gt 4) { throw "Erwartet 1 bis 4 freigegebene Zielknoten" }
}
$profiles = @(
  @{Name="core";Gateway=0;Audio=0;Ap=0},
  @{Name="audio";Gateway=0;Audio=1;Ap=0},
  @{Name="gateway";Gateway=1;Audio=0;Ap=0},
  @{Name="hybrid";Gateway=1;Audio=1;Ap=0},
  @{Name="core_ap";Gateway=0;Audio=0;Ap=1},
  @{Name="audio_ap";Gateway=0;Audio=1;Ap=1},
  @{Name="gateway_ap";Gateway=1;Audio=0;Ap=1},
  @{Name="hybrid_ap";Gateway=1;Audio=1;Ap=1}
)
$original = Get-Content -LiteralPath $sketch -Raw
$versionLine = '#define SMOKE_FIRMWARE_VERSION "'+$Version+'"'
if (-not $original.Contains($versionLine)) { throw "Build-Versionsmarker fehlt" }
$signer = Join-Path $repo "tools\ota\sign_release.py"
$report = @()
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
foreach ($idx in 0..7) {
  $profile = $profiles[$idx]
  $letter = [char]([int][char]'a'+$idx)
  $release = $Version + "." + $letter
  $folder = Join-Path $OutputRoot $release
  $source = Join-Path $folder ("source\mesh-v"+$Version)
  $work = Join-Path $folder "compile"
  $export = Join-Path $folder "export"
  New-Item -ItemType Directory -Path $source,$work,$export -Force | Out-Null
  # Isolated copy retains local private headers; original source never modified.
  Get-ChildItem -LiteralPath $sketchDir -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $source $_.Name)
  }
  $variantSketch = Join-Path $source ("mesh-v"+$Version+".ino")
  $variantSource = $original.Replace($versionLine,('#define SMOKE_FIRMWARE_VERSION "'+$release+'"'))
  [System.IO.File]::WriteAllText($variantSketch,$variantSource,[System.Text.UTF8Encoding]::new($false))
  $flags = "-DFEATURE_GATEWAY=$($profile.Gateway) -DFEATURE_AUDIO=$($profile.Audio) -DFEATURE_CONFIG_AP=$($profile.Ap) -DFEATURE_BATTERY=0 -DFEATURE_BUZZER=0"
  Write-Host "[BUILD] $release $($profile.Name)" -ForegroundColor Cyan
  & $cli.Source compile --fqbn $Fqbn --build-path $work --output-dir $export --build-property ("compiler.cpp.extra_flags="+$flags) $source
  if ($LASTEXITCODE -ne 0) { throw "Compile fehlgeschlagen: $release" }
  $bin = Join-Path $export ("mesh-v"+$Version+".ino.bin")
  if (-not (Test-Path -LiteralPath $bin)) { throw "BIN fehlt: $bin" }
  $features = @()
  if ($profile.Gateway) { $features += "gateway" }
  if ($profile.Audio) { $features += "audio" }
  if ($profile.Ap) { $features += "config_ap" }
  $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $bin).Hash.ToLowerInvariant()
  $zip = $null
  if (-not $BuildOnly) {
    $package = Join-Path $folder "package"
    New-Item -ItemType Directory -Path $package -Force | Out-Null
    $pkgBin = Join-Path $package "firmware.bin"
    Copy-Item -LiteralPath $bin -Destination $pkgBin
    foreach ($target in $targets) {
      $manifest = Join-Path $package ("manifest_"+$target+".json")
      & $python $signer sign --image $pkgBin --private-key $PrivateKey --target $target --version $release --features ($features -join ",") --out $manifest
      if ($LASTEXITCODE -ne 0) { throw "Signieren fehlgeschlagen: $release $target" }
      & $python $signer verify --image $pkgBin --manifest $manifest --public-key $PublicKey
      if ($LASTEXITCODE -ne 0) { throw "Signaturpruefung fehlgeschlagen: $release $target" }
    }
    $zip = Join-Path $folder ("smoke-mesh-"+$release+"-ota.zip")
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($package,$zip)
  }
  $report += [pscustomobject]@{
    Version=$release; Profile=$profile.Name; Features=$features
    Bytes=(Get-Item -LiteralPath $bin).Length; Sha256=$digest
    Bin=$bin; Targets=$targets; Zip=$zip; Fqbn=$Fqbn; Flags=$flags
  }
}
$reportPath = Join-Path $OutputRoot "build-report.json"
ConvertTo-Json -InputObject $report -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Host "[DONE] $reportPath" -ForegroundColor Green
$report | Select-Object Version,Profile,Bytes,@{N="Targets";E={$_.Targets.Count}},Zip | Format-Table -AutoSize
