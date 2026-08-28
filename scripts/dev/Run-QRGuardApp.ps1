[CmdletBinding()]
param(
    [string]$DeviceId = 'emulator-5554',
    [switch]$SkipEmulatorCheck
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$appRoot = Join-Path $repoRoot 'app'
$flutterFallback = 'C:\src\flutter\bin\flutter.bat'
$flutterCommand = Get-Command flutter.bat -ErrorAction SilentlyContinue
$flutter = if ($flutterCommand) { $flutterCommand.Source } else { $flutterFallback }

if (-not (Test-Path -LiteralPath $flutter)) {
    throw "Flutter was not found: $flutter"
}

if (-not $SkipEmulatorCheck) {
    & (Join-Path $PSScriptRoot 'Start-QRGuardEmulator.ps1') -DeviceId $DeviceId
}

Write-Host "Running QRGuard on $DeviceId in Flutter debug mode."
Write-Host 'The first run installs the debug APK; later runs replace the same package and keep one icon.'
Write-Host 'Use r for hot reload, R for hot restart, and q to stop.'
Set-Location -LiteralPath $appRoot
& $flutter run -d $DeviceId
exit $LASTEXITCODE
