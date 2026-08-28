[CmdletBinding()]
param(
    [string]$BackendUrl = "https://qrguard-api.onrender.com",
    [string]$WebUrl = "https://qrguard-app.onrender.com"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$appRoot = Join-Path $repoRoot "app"
$publicRoot = Join-Path $PSScriptRoot "web\public"
$expectedParent = Join-Path (Resolve-Path -LiteralPath $PSScriptRoot).Path "web"

if (-not $BackendUrl.StartsWith("https://", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackendUrl must use HTTPS."
}
if (-not $WebUrl.StartsWith("https://", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "WebUrl must use HTTPS."
}

$flutter = "C:\src\flutter\bin\flutter.bat"
if (-not (Test-Path -LiteralPath $flutter)) {
    throw "Flutter was not found at $flutter"
}

Push-Location $appRoot
try {
    & $flutter build web --release --no-version-check `
        --dart-define="QRGUARD_BACKEND_URL=$BackendUrl"
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter web build failed with exit code $LASTEXITCODE."
    }

    & $flutter build apk --release --no-version-check `
        --dart-define="QRGUARD_BACKEND_URL=$BackendUrl"
    if ($LASTEXITCODE -ne 0) {
        throw "Signed Android APK build failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}

if (Test-Path -LiteralPath $publicRoot) {
    $resolvedPublic = (Resolve-Path -LiteralPath $publicRoot).Path
    if ((Split-Path -Parent $resolvedPublic) -ne $expectedParent) {
        throw "Refusing to replace unexpected directory: $resolvedPublic"
    }
    Remove-Item -LiteralPath $resolvedPublic -Recurse -Force
}

New-Item -ItemType Directory -Path $publicRoot -Force | Out-Null
Copy-Item -Path (Join-Path $appRoot "build\web\*") -Destination $publicRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "deploy\web\privacy.html") `
    -Destination (Join-Path $publicRoot "privacy.html") -Force

$downloads = New-Item -ItemType Directory -Path (Join-Path $publicRoot "downloads") -Force
$apkName = "qrguard-1.0.0+8006.apk"
$apkTarget = Join-Path $downloads.FullName $apkName
Copy-Item -LiteralPath (Join-Path $appRoot "build\app\outputs\flutter-apk\app-release.apk") `
    -Destination $apkTarget -Force

$downloadPage = @"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Download QRGuard</title>
  <style>body{font:16px system-ui;max-width:720px;margin:3rem auto;padding:0 1rem;color:#172033}a.button{display:inline-block;padding:.8rem 1.1rem;border-radius:.6rem;background:#1263dd;color:#fff;text-decoration:none}</style>
</head>
<body>
  <h1>Download QRGuard for Android</h1>
  <p>This is the signed FYP test build. Android may ask you to allow installation from this browser.</p>
  <p><a class="button" href="/downloads/$apkName">Download APK</a></p>
  <p>Web application: <a href="$WebUrl">$WebUrl</a></p>
  <p><a href="/privacy.html">Privacy policy</a></p>
</body>
</html>
"@
Set-Content -LiteralPath (Join-Path $publicRoot "download.html") `
    -Value $downloadPage -Encoding UTF8

$apk = Get-Item -LiteralPath $apkTarget
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $apkTarget).Hash
Write-Output "Prepared Render static site: $publicRoot"
Write-Output "Backend URL: $BackendUrl"
Write-Output "Web URL: $WebUrl"
Write-Output "Signed APK: $($apk.FullName)"
Write-Output "APK bytes: $($apk.Length)"
Write-Output "APK SHA256: $hash"
