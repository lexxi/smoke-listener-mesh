param(
  [string]$Version = "0.6.14",
  [string]$Image = "",
  [string]$PrivateKey = "C:\mesh-ota-keys\signing-private.pem",
  [string]$Output = ""
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
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
    & $python $signer sign --image (Join-Path $temp "firmware.bin") --private-key $PrivateKey --target $target --version $Version --out $manifest
    if ($LASTEXITCODE -ne 0) { throw "Signatur fehlgeschlagen für $target" }
  }
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [System.IO.Compression.ZipFile]::CreateFromDirectory($temp,$Output)
  Write-Host "Signiertes Release-Paket erstellt: $Output" -ForegroundColor Green
  Write-Host "Enthält EINE BIN und $($nodes.Count) signierte Knotenmanifeste."
  Write-Host "In der Webapp nur dieses ZIP hochladen."
} finally {
  Remove-Item -LiteralPath $temp -Force -Recurse -ErrorAction SilentlyContinue
}
