<#
.SYNOPSIS
Build all eight Gateway/Audio/AP combinations for every explicitly allowed node.
Letters are RELEASE LABELS; numeric OTA version remains monotone.
Example v0.6.15a = OTA 0.6.150; v0.6.15h = OTA 0.6.157.
Never flashes a device.
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
  [switch]$BuildOnly,
  [switch]$AllCombinations
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sketchDir = Join-Path $repo ("firmware\mesh-v" + $Version)
$sketch = Join-Path $sketchDir ("mesh-v" + $Version + ".ino")
if ($Version -notmatch '^0\.6\.(\d+)
if (-not (Test-Path -LiteralPath $sketch)) { throw "Sketch fehlt: $sketch" }
foreach ($file in @("mesh_secrets.h", "ota_public_key.h", "feature_config.h")) {
  if (-not (Test-Path -LiteralPath (Join-Path $sketchDir $file))) { throw "Header fehlt: $file" }
}
$cli = Get-Command $ArduinoCli -ErrorAction Stop
$python = Join-Path $repo "myenv\Scripts\python.exe"
if (-not $TargetsFile) { $TargetsFile = Join-Path $repo "web\data\node_targets.json" }
if (-not $OutputRoot) { $OutputRoot = Join-Path $repo ("firmware\mesh-v" + $Version + "\build\release-matrix-8") }
if (Test-Path -LiteralPath $OutputRoot) { throw "Output already exists: $OutputRoot. Supply a fresh -OutputRoot." }
$targets = @()
if (-not $BuildOnly) {
  foreach ($file in @($PrivateKey,$PublicKey,$python,$TargetsFile)) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing signing prerequisite: $file" }
  }
  $list = @(Get-Content -LiteralPath $TargetsFile -Raw | ConvertFrom-Json)
  foreach ($entry in $list) {
    if ($entry -isnot [string] -or $entry -cnotmatch '^[0-9A-F]{16}$') {
      throw "node_targets.json must contain an array of uppercase 16-digit IDs"
    }
    if ($targets -contains $entry) { throw "Duplicate target: $entry" }
    $targets += $entry
  }
  if ($targets.Count -eq 0 -or $targets.Count -gt 4) { throw "Expected 1..4 explicitly approved targets" }
}
$profiles = @(
  @{Name="core"; Gateway=0; Audio=0; Ap=0},
  @{Name="audio"; Gateway=0; Audio=1; Ap=0},
  @{Name="gateway"; Gateway=1; Audio=0; Ap=0},
  @{Name="hybrid"; Gateway=1; Audio=1; Ap=0},
  @{Name="core_ap"; Gateway=0; Audio=0; Ap=1},
  @{Name="audio_ap"; Gateway=0; Audio=1; Ap=1},
  @{Name="gateway_ap"; Gateway=1; Audio=0; Ap=1},
  @{Name="hybrid_ap"; Gateway=1; Audio=1; Ap=1}
)
$baseSource = Get-Content -LiteralPath $sketch -Raw
$needle = '#define SMOKE_FIRMWARE_VERSION "' + $Version + '"'
if (-not $baseSource.Contains($needle)) { throw "Version override hook is missing in source" }
$signer = Join-Path $repo "tools\ota\sign_release.py"
$results = @()
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
for ($i = 0; $i -lt $profiles.Count; $i++) {
  $profile = $profiles[$i]
  $letter = [char]([int][char]'a' + $i)
  $label = "$Version$letter"
  $otaVersion = "0.6." + ($basePatch * 10 + $i)
  $folder = Join-Path $OutputRoot $label
  $src = Join-Path $folder ("source\mesh-v" + $Version)
  $work = Join-Path $folder "compile"
  $out = Join-Path $folder "export"
  New-Item -ItemType Directory -Path $src,$work,$out -Force | Out-Null
  # Isolate each sketch, including ignored local private headers. No repo edits.
  Get-ChildItem -LiteralPath $sketchDir -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $src $_.Name)
  }
  $variantSketch = Join-Path $src ("mesh-v" + $Version + ".ino")
  $variantSource = $baseSource.Replace($needle, ('#define SMOKE_FIRMWARE_VERSION "' + $otaVersion + '"'))
  [System.IO.File]::WriteAllText($variantSketch,$variantSource,[System.Text.UTF8Encoding]::new($false))
  $flags = "-DFEATURE_GATEWAY=$($profile.Gateway) -DFEATURE_AUDIO=$($profile.Audio) -DFEATURE_CONFIG_AP=$($profile.Ap) -DFEATURE_BATTERY=0 -DFEATURE_BUZZER=0"
  Write-Host "[BUILD] $label OTA=$otaVersion $($profile.Name)" -ForegroundColor Cyan
  & $cli.Source compile --fqbn $Fqbn --build-path $work --output-dir $out --build-property ("compiler.cpp.extra_flags="+$flags) $src
  if ($LASTEXITCODE -ne 0) { throw "Compile failed: $label" }
  $image = Join-Path $out ("mesh-v" + $Version + ".ino.bin")
  if (-not (Test-Path -LiteralPath $image)) { throw "No BIN: $image" }
  $features = @()
  if ($profile.Gateway) { $features += "gateway" }
  if ($profile.Audio) { $features += "audio" }
  if ($profile.Ap) { $features += "config_ap" }
  $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $image).Hash.ToLowerInvariant()
  $zip = $null
  if (-not $BuildOnly) {
    $pkg = Join-Path $folder "package"
    New-Item -ItemType Directory -Path $pkg -Force | Out-Null
    Copy-Item -LiteralPath $image -Destination (Join-Path $pkg "firmware.bin")
    foreach ($target in $targets) {
      $manifest = Join-Path $pkg ("manifest_" + $target + ".json")
      & $python $signer sign --image (Join-Path $pkg "firmware.bin") --private-key $PrivateKey --target $target --version $otaVersion --features ($features -join ",") --label $label --out $manifest
      if ($LASTEXITCODE -ne 0) { throw "Sign failed $label $target" }
      & $python $signer verify --image (Join-Path $pkg "firmware.bin") --manifest $manifest --public-key $PublicKey
      if ($LASTEXITCODE -ne 0) { throw "Verify failed $label $target" }
    }
    $zip = Join-Path $folder ("smoke-mesh-" + $label + "-ota.zip")
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($pkg,$zip)
    Write-Host "[SIGNED] $label for $($targets.Count) node(s)" -ForegroundColor Green
  }
  $results += [pscustomobject]@{
    Label=$label; OtaVersion=$otaVersion; Profile=$profile.Name
    Features=$features; Sha256=$digest; Bytes=(Get-Item -LiteralPath $image).Length
    Bin=$image; Targets=$targets; Zip=$zip; Fqbn=$Fqbn; BuildFlags=$flags
  }
}
$report = Join-Path $OutputRoot "build-report.json"
$results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $report -Encoding UTF8
Write-Host "[DONE] $report" -ForegroundColor Green
$results | Select-Object Label,OtaVersion,Profile,Bytes,@{N="Targets";E={$_.Targets.Count}},Zip | Format-Table -AutoSize
) { throw "Expected firmware version 0.6.N" }
$basePatch = [int]$Matches[1]
if ($basePatch -lt 15 -or $basePatch -gt 24) {
  throw "For 8 variants and 8-bit telemetry, supported release patches: 15..24"
}
if (-not (Test-Path -LiteralPath $sketch)) { throw "Sketch fehlt: $sketch" }
foreach ($file in @("mesh_secrets.h", "ota_public_key.h", "feature_config.h")) {
  if (-not (Test-Path -LiteralPath (Join-Path $sketchDir $file))) { throw "Header fehlt: $file" }
}
$cli = Get-Command $ArduinoCli -ErrorAction Stop
$python = Join-Path $repo "myenv\Scripts\python.exe"
if (-not $TargetsFile) { $TargetsFile = Join-Path $repo "web\data\node_targets.json" }
if (-not $OutputRoot) { $OutputRoot = Join-Path $repo ("firmware\mesh-v" + $Version + "\build\release-matrix-8") }
if (Test-Path -LiteralPath $OutputRoot) { throw "Output already exists: $OutputRoot. Supply a fresh -OutputRoot." }
$targets = @()
if (-not $BuildOnly) {
  foreach ($file in @($PrivateKey,$PublicKey,$python,$TargetsFile)) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing signing prerequisite: $file" }
  }
  $list = @(Get-Content -LiteralPath $TargetsFile -Raw | ConvertFrom-Json)
  foreach ($entry in $list) {
    if ($entry -isnot [string] -or $entry -cnotmatch '^[0-9A-F]{16}$') {
      throw "node_targets.json must contain an array of uppercase 16-digit IDs"
    }
    if ($targets -contains $entry) { throw "Duplicate target: $entry" }
    $targets += $entry
  }
  if ($targets.Count -eq 0 -or $targets.Count -gt 4) { throw "Expected 1..4 explicitly approved targets" }
}
$profiles = @(
  @{Name="core"; Gateway=0; Audio=0; Ap=0},
  @{Name="audio"; Gateway=0; Audio=1; Ap=0},
  @{Name="gateway"; Gateway=1; Audio=0; Ap=0},
  @{Name="hybrid"; Gateway=1; Audio=1; Ap=0},
  @{Name="core_ap"; Gateway=0; Audio=0; Ap=1},
  @{Name="audio_ap"; Gateway=0; Audio=1; Ap=1},
  @{Name="gateway_ap"; Gateway=1; Audio=0; Ap=1},
  @{Name="hybrid_ap"; Gateway=1; Audio=1; Ap=1}
)
$baseSource = Get-Content -LiteralPath $sketch -Raw
$needle = '#define SMOKE_FIRMWARE_VERSION "0.6.15"'
if (-not $baseSource.Contains($needle)) { throw "Version override hook is missing in source" }
$signer = Join-Path $repo "tools\ota\sign_release.py"
$results = @()
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
for ($i = 0; $i -lt $profiles.Count; $i++) {
  $profile = $profiles[$i]
  $letter = [char]([int][char]'a' + $i)
  $label = "$Version$letter"
  $otaVersion = "0.6." + (150 + $i)
  $folder = Join-Path $OutputRoot $label
  $src = Join-Path $folder ("source\mesh-v" + $Version)
  $work = Join-Path $folder "compile"
  $out = Join-Path $folder "export"
  New-Item -ItemType Directory -Path $src,$work,$out -Force | Out-Null
  # Isolate each sketch, including ignored local private headers. No repo edits.
  Get-ChildItem -LiteralPath $sketchDir -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $src $_.Name)
  }
  $variantSketch = Join-Path $src ("mesh-v" + $Version + ".ino")
  $variantSource = $baseSource.Replace($needle, ('#define SMOKE_FIRMWARE_VERSION "' + $otaVersion + '"'))
  [System.IO.File]::WriteAllText($variantSketch,$variantSource,[System.Text.UTF8Encoding]::new($false))
  $flags = "-DFEATURE_GATEWAY=$($profile.Gateway) -DFEATURE_AUDIO=$($profile.Audio) -DFEATURE_CONFIG_AP=$($profile.Ap) -DFEATURE_BATTERY=0 -DFEATURE_BUZZER=0"
  Write-Host "[BUILD] $label OTA=$otaVersion $($profile.Name)" -ForegroundColor Cyan
  & $cli.Source compile --fqbn $Fqbn --build-path $work --output-dir $out --build-property ("compiler.cpp.extra_flags="+$flags) $src
  if ($LASTEXITCODE -ne 0) { throw "Compile failed: $label" }
  $image = Join-Path $out ("mesh-v" + $Version + ".ino.bin")
  if (-not (Test-Path -LiteralPath $image)) { throw "No BIN: $image" }
  $features = @()
  if ($profile.Gateway) { $features += "gateway" }
  if ($profile.Audio) { $features += "audio" }
  if ($profile.Ap) { $features += "config_ap" }
  $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $image).Hash.ToLowerInvariant()
  $zip = $null
  if (-not $BuildOnly) {
    $pkg = Join-Path $folder "package"
    New-Item -ItemType Directory -Path $pkg -Force | Out-Null
    Copy-Item -LiteralPath $image -Destination (Join-Path $pkg "firmware.bin")
    foreach ($target in $targets) {
      $manifest = Join-Path $pkg ("manifest_" + $target + ".json")
      & $python $signer sign --image (Join-Path $pkg "firmware.bin") --private-key $PrivateKey --target $target --version $otaVersion --features ($features -join ",") --label $label --out $manifest
      if ($LASTEXITCODE -ne 0) { throw "Sign failed $label $target" }
      & $python $signer verify --image (Join-Path $pkg "firmware.bin") --manifest $manifest --public-key $PublicKey
      if ($LASTEXITCODE -ne 0) { throw "Verify failed $label $target" }
    }
    $zip = Join-Path $folder ("smoke-mesh-" + $label + "-ota.zip")
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($pkg,$zip)
    Write-Host "[SIGNED] $label for $($targets.Count) node(s)" -ForegroundColor Green
  }
  $results += [pscustomobject]@{
    Label=$label; OtaVersion=$otaVersion; Profile=$profile.Name
    Features=$features; Sha256=$digest; Bytes=(Get-Item -LiteralPath $image).Length
    Bin=$image; Targets=$targets; Zip=$zip; Fqbn=$Fqbn; BuildFlags=$flags
  }
}
$report = Join-Path $OutputRoot "build-report.json"
$results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $report -Encoding UTF8
Write-Host "[DONE] $report" -ForegroundColor Green
$results | Select-Object Label,OtaVersion,Profile,Bytes,@{N="Targets";E={$_.Targets.Count}},Zip | Format-Table -AutoSize
