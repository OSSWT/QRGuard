[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$DeviceId = 'emulator-5554'
)

$ErrorActionPreference = 'Stop'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
$currentPackage = 'com.osswt.qrguard'
$retiredPackage = 'my.qrguard.qrguard'

if (-not (Test-Path -LiteralPath $adb)) {
    throw "ADB was not found: $adb"
}

$devicePattern = '^{0}\s+device(?:\s|$)' -f [regex]::Escape($DeviceId)
$connected = @(& $adb devices) | Where-Object { $_ -match $devicePattern }
if (-not $connected) {
    throw "$DeviceId is not online. Run Start-QRGuardEmulator.ps1 first."
}

$packages = @(& $adb -s $DeviceId shell pm list packages)
$hasCurrent = $packages -contains "package:$currentPackage"
$hasRetired = $packages -contains "package:$retiredPackage"

Write-Host "Current package ($currentPackage): $(if ($hasCurrent) { 'installed' } else { 'not installed yet' })"
Write-Host "Retired package ($retiredPackage): $(if ($hasRetired) { 'installed' } else { 'not installed' })"

if (-not $hasRetired) {
    Write-Host '[OK] No retired QRGuard package needs removal.'
    exit 0
}

if ($PSCmdlet.ShouldProcess("$DeviceId / $retiredPackage", 'Uninstall retired QRGuard package and its old local data')) {
    $result = (& $adb -s $DeviceId uninstall $retiredPackage) -join "`n"
    Write-Host $result
    if ($result.Trim() -ne 'Success') {
        throw "ADB could not uninstall $retiredPackage."
    }
}

$remaining = @(& $adb -s $DeviceId shell pm list packages)
if ($remaining -contains "package:$retiredPackage") {
    throw "Retired package is still installed: $retiredPackage"
}
if ($hasCurrent -and $remaining -notcontains "package:$currentPackage") {
    throw "Safety check failed: current QRGuard package disappeared unexpectedly."
}

Write-Host '[DONE] The retired QRGuard icon/package was removed.'
Write-Host '[PRESERVED] The current com.osswt.qrguard package and its data were not cleared.'
