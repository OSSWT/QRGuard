[CmdletBinding()]
param(
    [int]$Port = 8001,
    [switch]$Lan,
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$server = Join-Path $repoRoot 'scripts\run_server.py'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project virtual-environment Python was not found: $python"
}
if (-not (Test-Path -LiteralPath $server)) {
    throw "Backend launcher was not found: $server"
}

$serverArgs = @($server, '--port', $Port.ToString())
if ($Lan) {
    $serverArgs += '--lan'
}
if (-not $Reload) {
    $serverArgs += '--no-reload'
}

Write-Host "Using project Python: $python"
Write-Host "Starting QRGuard backend (preferred port $Port)..."
Write-Host 'Android Emulator URL: http://10.0.2.2:<printed-port>'
Write-Host 'Windows/Web URL:       http://127.0.0.1:<printed-port>'
Set-Location -LiteralPath $repoRoot
& $python @serverArgs
exit $LASTEXITCODE
