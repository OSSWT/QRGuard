[CmdletBinding()]
param(
    [string]$DeviceId = 'emulator-5554',
    [int]$BackendPort = 8001
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$checkScript = Join-Path $PSScriptRoot 'Check-QRGuardEnvironment.ps1'
$emulatorScript = Join-Path $PSScriptRoot 'Start-QRGuardEmulator.ps1'
$backendScript = Join-Path $PSScriptRoot 'Start-QRGuardBackend.ps1'
$appScript = Join-Path $PSScriptRoot 'Run-QRGuardApp.ps1'

& $checkScript
& $emulatorScript -DeviceId $DeviceId

Write-Host 'Opening the backend in a separate PowerShell window...'
Start-Process -FilePath 'powershell.exe' -WorkingDirectory $repoRoot -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy', 'Bypass',
    '-File', $backendScript,
    '-Port', $BackendPort
)

$healthUrl = "http://127.0.0.1:$BackendPort/health"
$deadline = [DateTime]::UtcNow.AddSeconds(45)
$healthy = $false
while ([DateTime]::UtcNow -lt $deadline) {
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($response.status -eq 'ok') {
            $healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if ($healthy) {
    Write-Host "[READY] Backend health check passed at $healthUrl"
}
else {
    Write-Warning "Port $BackendPort did not answer. Read the backend window: run_server.py may have selected another free port. Update the app Backend URL to http://10.0.2.2:<printed-port>."
}

& $appScript -DeviceId $DeviceId -SkipEmulatorCheck
exit $LASTEXITCODE
