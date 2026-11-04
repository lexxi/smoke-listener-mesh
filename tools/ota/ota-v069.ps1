param(
    [string]$Gateway = "COM12",
    [string]$TargetPort = "COM15",
    [switch]$Activate,
    [switch]$ActivateOnly,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repo "myenv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python venv missing: $python" }
$script = Join-Path $PSScriptRoot "ota_test.py"
$image = Join-Path $repo "firmware\mesh-v0.6.9\build\esp32.esp32.XIAO_ESP32C3\mesh-v0.6.9.ino.bin"
$manifest = "C:\mesh-ota-keys\release-1og-069.json"
$publicKey = "C:\mesh-ota-keys\signing-public.pem"
if (-not (Test-Path $image)) { throw "Image missing: $image" }
if (-not (Test-Path $manifest)) { throw "Signed manifest missing: $manifest" }
Push-Location $repo
try {
    $argList = @($script, "--gateway", $Gateway, "--target-port", $TargetPort,
        "--from-version", "0.6.7", "--to-version", "0.6.9",
        "--image", $image, "--manifest", $manifest, "--public-key", $publicKey)
    if ($DryRun) { $argList += "--dry-run" }
    if ($Activate -or $ActivateOnly) { $argList += "--activate" }
    if ($ActivateOnly) { $argList += "--activate-only" }
    & $python @argList
    if ($LASTEXITCODE -ne 0) {
        throw "v0.6.9 OTA stopped/failed; inspect log before reset."
    }
} finally { Pop-Location }
