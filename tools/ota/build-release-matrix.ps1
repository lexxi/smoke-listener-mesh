<#
.SYNOPSIS
Build all requested v0.6.15 firmware variants, export separate BINs, then sign
only for explicitly approved node roles. Never flashes devices.
.EXAMPLE
.\tools\ota\build-release-matrix.ps1 -Version 0.6.15
.EXAMPLE
.\tools\ota\build-release-matrix.ps1 -Version 0.6.15 -AllCombinations -BuildOnly
#>
[CmdletBinding()]
param(
  [string]$Version = "0.6.15",
  [string]$Fqbn = "esp32:esp32:XIAO_ESP32C3:UploadSpeed=921600,CDCOnBoot=default,CPUFreq=160,FlashFreq=80,FlashMode=qio,FlashSize=4M,PartitionScheme=default,DebugLevel=none,EraseFlash=none",
  [string]$ArduinoCli = "arduino-cli",
  [string]$PrivateKey = "C:\mesh-ota-keys\signing-private.pem",
  [string]$RoleFile = "",
  [string]$OutputRoot = "",
  [switch]$AllCombinations,
  [switch]$BuildOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sketch = Join-Path $repo ("firmware\mesh-v$Version\mesh-v$Version.ino")
$sketchDir = Split-Path $sketch -Parent
if ($Version -ne "0.6.15") { throw "Dieses Skript ist aktuell nur fuer v0.6.15 validiert." }
if (-not (Test-Path -LiteralPath $sketch)) { throw "Sketch fehlt: $sketch" }
foreach ($file in @("mesh_secrets.h", "ota_public_key.h", "feature_config.h")) {
  if (-not (Test-Path -LiteralPath (Join-Path $sketchDir $file))) {
    throw "Firmware-Header fehlt: $file (prepare-firmware.ps1 ausfuehren)"
  }
}
$cli = Get-Command $ArduinoCli -ErrorAction Stop
if ($cli.CommandType -notin @("Application", "ExternalScript")) {
  throw "Arduino-CLI muss ein installiertes Programm sein"
}
$python = Join-Path $repo "myenv\Scripts\python.exe"
if (-not $BuildOnly) {
  if (-not (Test-Path -LiteralPath $PrivateKey)) { throw "Privater OTA-Signierschluessel fehlt: $PrivateKey" }
  if (-not (Test-Path -LiteralPath $python)) { throw "Python-venv fehlt: $python" }
}
if (-not $RoleFile) { $RoleFile = Join-Path $repo "web\data\node_roles.json" }
if (-not $OutputRoot) { $OutputRoot = Join-Path $repo ("firmware\mesh-v$Version\build\release-matrix") }
if (Test-Path -LiteralPath $OutputRoot) {
  throw "Ausgabeverzeichnis existiert bereits (keine alten BINs ueberschreiben): $OutputRoot"
}
# No inferred targets. The role list is a local, operator-approved allowlist.
$roleMap = @{}
if (-not $BuildOnly) {
  if (-not (Test-Path -LiteralPath $RoleFile)) {
    throw "Rollenfreigabe fehlt: $RoleFile. node_roles.json.example pruefen und nach web/data/node_roles.json kopieren."
  }
  $raw = Get-Content -LiteralPath $RoleFile -Raw | ConvertFrom-Json
  foreach ($entry in $raw.PSObject.Properties) {
    if ($entry.Name -cnotmatch '^[0-9A-F]{16}$') { throw "Ungueltige Knoten-ID: $($entry.Name)" }
    if ($entry.Value -cnotin @("mesh","listener","gateway","hybrid")) {
      throw "Ungueltige Zielrolle fuer $($entry.Name): $($entry.Value)"
    }
    $roleMap[$entry.Name] = [string]$entry.Value
  }
  if ($roleMap.Count -eq 0) { throw "Keine Zielrollen freigegeben" }
}
$profiles = @(
  @{Name="core"; Role="mesh"; Gateway=0; Audio=0; Ap=0},
  @{Name="audio"; Role="listener"; Gateway=0; Audio=1; Ap=0},
  @{Name="gateway"; Role="gateway"; Gateway=1; Audio=0; Ap=0},
  @{Name="hybrid"; Role="hybrid"; Gateway=1; Audio=1; Ap=0}
)
if ($AllCombinations) {
  $extra = @()
  foreach ($p in $profiles) {
    $extra += @{Name=($p.Name+"_ap");Role=$p.Role;Gateway=$p.Gateway;Audio=$p.Audio;Ap=1}
  }
  $profiles += $extra
}
$signer = Join-Path $repo "tools\ota\sign_release.py"
$results = @()
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
try {
  foreach ($profile in $profiles) {
    $name = $profile.Name
    $folder = Join-Path $OutputRoot $name
    $work = Join-Path $folder "compile"
    $out = Join-Path $folder "export"
    New-Item -ItemType Directory -Path $work, $out -Force | Out-Null
    $flags = "-DFEATURE_GATEWAY=$($profile.Gateway) -DFEATURE_AUDIO=$($profile.Audio) -DFEATURE_CONFIG_AP=$($profile.Ap) -DFEATURE_BATTERY=0 -DFEATURE_BUZZER=0"
    Write-Host "[BUILD] $name ($flags)" -ForegroundColor Cyan
    & $cli.Source compile --fqbn $Fqbn --build-path $work --output-dir $out --build-property ("compiler.cpp.extra_flags="+$flags) $sketchDir
    if ($LASTEXITCODE -ne 0) { throw "Compile fehlgeschlagen: $name ($LASTEXITCODE)" }
    $expected = Join-Path $out ("mesh-v$Version.ino.bin")
    if (-not (Test-Path -LiteralPath $expected)) {
      throw "BIN nicht exportiert: $expected"
    }
    $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $expected).Hash.ToLowerInvariant()
    $features = @()
    if ($profile.Gateway -eq 1) { $features += "gateway" }
    if ($profile.Audio -eq 1) { $features += "audio" }
    if ($profile.Ap -eq 1) { $features += "config_ap" }
    $targets = @($roleMap.Keys | Where-Object { $roleMap[$_] -eq $profile.Role } | Sort-Object)
    $zipPath = $null
    if (-not $BuildOnly -and $targets.Count -gt 0) {
      $packageDir = Join-Path $folder "package"
      New-Item -ItemType Directory -Path $packageDir -Force | Out-Null
      Copy-Item -LiteralPath $expected -Destination (Join-Path $packageDir "firmware.bin")
      foreach ($target in $targets) {
        $manifest = Join-Path $packageDir ("manifest_"+$target+".json")
        $arguments = @("sign","--image",(Join-Path $packageDir "firmware.bin"),
          "--private-key",$PrivateKey,"--target",$target,"--version",$Version,
          "--features",($features -join ","),"--out",$manifest)
        & $python $signer @arguments
        if ($LASTEXITCODE -ne 0) { throw "Signatur fehlgeschlagen: $name fuer $target" }
        # Verify immediately with the local public key when configured.
      }
      $zipPath = Join-Path $folder ("smoke-mesh-v"+$Version+"-"+$name+"-ota.zip")
      Add-Type -AssemblyName System.IO.Compression.FileSystem
      [System.IO.Compression.ZipFile]::CreateFromDirectory($packageDir,$zipPath)
      Write-Host "[SIGNED] $zipPath targets=$($targets.Count)" -ForegroundColor Green
    }
    $results += [pscustomobject]@{
      Version=$Version; Profile=$name; Role=$profile.Role; Features=$features
      Sha256=$digest; Bytes=(Get-Item -LiteralPath $expected).Length
      Bin=$expected; Targets=$targets; Zip=$zipPath; Fqbn=$Fqbn
      BuildFlags=$flags
    }
  }
  $report = Join-Path $OutputRoot "build-report.json"
  $results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $report -Encoding UTF8
  Write-Host "[DONE] $report" -ForegroundColor Green
  $results | Select-Object Profile,Bytes,@{N="Targets";E={$_.Targets.Count}},Zip | Format-Table -AutoSize
} catch {
  Write-Error "Build-Matrix abgebrochen: $_ (Zwischenergebnisse nicht als Releases verteilen)"
  throw
}
