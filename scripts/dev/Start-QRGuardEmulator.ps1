[CmdletBinding()]
param(
    [string]$AvdName = 'Small_Phone',
    [string]$DeviceId = 'emulator-5554',
    [int]$BootTimeoutSeconds = 240
)

$ErrorActionPreference = 'Stop'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
$emulator = Join-Path $env:LOCALAPPDATA 'Android\Sdk\emulator\emulator.exe'

if (-not (Test-Path -LiteralPath $adb)) {
    throw "ADB was not found: $adb"
}
if (-not (Test-Path -LiteralPath $emulator)) {
    throw "Android Emulator was not found: $emulator"
}

$avds = @(& $emulator -list-avds)
if ($avds -notcontains $AvdName) {
    throw "Android Virtual Device '$AvdName' was not found. Available: $($avds -join ', ')"
}

function Test-DeviceReady {
    $devicePattern = '^{0}\s+device(?:\s|$)' -f [regex]::Escape($DeviceId)
    $connected = @(& $adb devices) | Where-Object { $_ -match $devicePattern }
    if (-not $connected) {
        return $false
    }
    $booted = (& $adb -s $DeviceId shell getprop sys.boot_completed 2>$null) -join ''
    return $booted.Trim() -eq '1'
}

if (-not (Test-DeviceReady)) {
    Write-Host "Starting $AvdName with the laptop webcam as its back camera..."
    Start-Process -FilePath $emulator -ArgumentList @(
        '-avd', $AvdName,
        '-no-snapshot',
        '-gpu', 'host',
        '-memory', '1024',
        '-no-boot-anim',
        '-camera-back', 'webcam0'
    )
}
else {
    Write-Host "$DeviceId is already booted; reusing it."
}

$deadline = [DateTime]::UtcNow.AddSeconds($BootTimeoutSeconds)
while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-DeviceReady) {
        Write-Host "[READY] $DeviceId is online and Android boot is complete."
        exit 0
    }
    Start-Sleep -Seconds 2
}

throw "Timed out waiting for $DeviceId after $BootTimeoutSeconds seconds."
