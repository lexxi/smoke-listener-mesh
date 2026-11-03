param(
    [string]$Gateway = "COM12",
    [string]$TargetPort = "COM15",
    [switch]$DryRun
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
    else { $arguments += "--activate" }

    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "OTA activation FAILED or state uncertain (exit code $LASTEXITCODE). Inspect log/ and BOOT STATUS before reboot."
    }
} finally {
    Pop-Location
}
