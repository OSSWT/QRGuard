[CmdletBinding()]
param([string]$Serial)

$ErrorActionPreference = 'Stop'
$checkRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$adb = 'C:\Users\OSSW\AppData\Local\Android\Sdk\platform-tools\adb.exe'
$apk = Join-Path $checkRoot 'app\build\app\outputs\flutter-apk\app-debug.apk'
if (-not (Test-Path -LiteralPath $apk)) {
    throw 'Build the 8014 USB candidate first; see docs/ATTENDANCE_QR_POLICY.md.'
}
$devices = @(& $adb devices | ForEach-Object {
    if ($_ -match '^(\S+)\s+device$') { $Matches[1] }
})
if (-not $Serial) {
    if ($devices.Count -ne 1) { throw 'Connect exactly one authorized USB-debugging phone, or specify -Serial.' }
    $Serial = $devices[0]
}
if ($Serial -notin $devices) { throw 'The selected phone is not authorized for USB debugging.' }
if (Get-NetTCPConnection -LocalPort 8014 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8014 is already occupied. Check the existing server before starting another.'
}
& $adb -s $Serial install -r $apk
if ($LASTEXITCODE -ne 0) { throw 'Candidate installation failed; no app data was cleared.' }
& $adb -s $Serial reverse tcp:8014 tcp:8014
if ($LASTEXITCODE -ne 0) { throw 'USB forwarding failed.' }

$previousDump = $env:QRGUARD_DUMP_SCANS
$previousModel = $env:QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS
try {
    $env:QRGUARD_DUMP_SCANS = Join-Path $checkRoot '.tmp\attendance-camera-8014'
    $env:QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS = Join-Path $checkRoot 'training\artifacts\structural'
    Write-Output 'Open QRGuard Capture. Its backend must be http://127.0.0.1:8014.'
    Write-Output "This local diagnostic session saves QR crops and per-frame checks under $env:QRGUARD_DUMP_SCANS. Keep those images private."
    & (Join-Path $checkRoot '.venv\Scripts\python.exe') -m uvicorn app.main:app --app-dir (Join-Path $checkRoot 'backend') --host 127.0.0.1 --port 8014
} finally {
    $env:QRGUARD_DUMP_SCANS = $previousDump
    $env:QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS = $previousModel
    & $adb -s $Serial reverse --remove tcp:8014
}
