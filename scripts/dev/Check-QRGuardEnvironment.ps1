[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$flutterFallback = 'C:\src\flutter\bin\flutter.bat'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
$emulator = Join-Path $env:LOCALAPPDATA 'Android\Sdk\emulator\emulator.exe'

$flutterCommand = Get-Command flutter.bat -ErrorAction SilentlyContinue
$flutter = if ($flutterCommand) { $flutterCommand.Source } else { $flutterFallback }

$requiredFiles = [ordered]@{
    'Repository' = $repoRoot
    'Project Python' = $python
    'Flutter' = $flutter
    'ADB' = $adb
    'Android Emulator' = $emulator
    'Backend entry point' = (Join-Path $repoRoot 'scripts\run_server.py')
    'Flutter application' = (Join-Path $repoRoot 'app\pubspec.yaml')
}

$missing = @()
foreach ($item in $requiredFiles.GetEnumerator()) {
    $exists = Test-Path -LiteralPath $item.Value
    $status = if ($exists) { 'OK' } else { 'MISSING' }
    Write-Host ('[{0}] {1}: {2}' -f $status, $item.Key, $item.Value)
    if (-not $exists) {
        $missing += $item.Key
    }
}

if ($missing.Count -gt 0) {
    throw ('QRGuard environment is incomplete: {0}' -f ($missing -join ', '))
}

$pythonVersion = & $python -c "import sys; print(sys.version.split()[0])"
Write-Host "[OK] Project Python version: $pythonVersion"
Write-Host '[OK] Current Android application ID: com.osswt.qrguard'
Write-Host '[INFO] Retired Android application ID: my.qrguard.qrguard'
Write-Host '[READY] QRGuard development paths are available.'
