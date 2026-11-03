param(
    [string]$Gateway = "COM12",
    [string]$TargetPort = "COM15",
    [switch]$DryRun,
    [switch]$Restage
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repo "myenv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Missing Python environment: $python" }
$script = Join-Path $PSScriptRoot "ota_test.py"

Push-Location $repo
try {
    $arguments = @($script, "--gateway", $Gateway, "--target-port", $TargetPort)
    if ($DryRun) { $arguments += "--dry-run" }
    else {
        $arguments += "--activate"
        if (-not $Restage) { $arguments += "--activate-only" }
    }

    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "OTA activation STOPPED/FAILED (exit code $LASTEXITCODE). If RAM authorization was lost, new staging is necessary on v0.6.6. No automatic retransfer. Inspect BOOT STATUS before reboot."
    }
} finally {
    Pop-Location
}
