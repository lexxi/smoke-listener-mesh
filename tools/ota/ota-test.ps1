param(
    [string]$Gateway = "COM12",
    [string]$TargetPort = "COM15",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repo "myenv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "py"
}
$script = Join-Path $PSScriptRoot "ota_test.py"

Push-Location $repo
try {
    $arguments = @($script, "--gateway", $Gateway, "--target-port", $TargetPort)
    if ($DryRun) {
        $arguments += "--dry-run"
    }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "OTA staging/readback FAILED (exit code $LASTEXITCODE). See the log directory."
    }
} finally {
    Pop-Location
}
