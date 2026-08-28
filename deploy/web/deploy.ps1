[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [Parameter(Mandatory = $true)]
    [string]$BackendUrl,
    [string]$Region = "asia-southeast1",
    [string]$ServiceName = "qrguard-web",
    [string]$BackendServiceName = "qrguard-api"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$flutter = "C:\src\flutter\bin\flutter.bat"
$gcloudCommand = Get-Command "gcloud" -ErrorAction SilentlyContinue
$gcloud = if ($gcloudCommand) {
    $gcloudCommand.Source
} else {
    "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
}
$build = Join-Path $repo "app\build\web"
$public = Join-Path $PSScriptRoot "public"

if (-not $BackendUrl.StartsWith("https://")) {
    throw "BackendUrl must be the production HTTPS endpoint."
}
if (-not (Test-Path -LiteralPath $gcloud -PathType Leaf)) {
    throw "Google Cloud CLI is not installed."
}

Push-Location (Join-Path $repo "app")
try {
    & $flutter build web --release --no-version-check `
        "--dart-define=QRGUARD_BACKEND_URL=$BackendUrl"
    if ($LASTEXITCODE -ne 0) { throw "Flutter web build failed." }
}
finally {
    Pop-Location
}

$resolvedDeploy = (Resolve-Path -LiteralPath $PSScriptRoot).Path
if ((Split-Path -Parent $public) -ne $resolvedDeploy) {
    throw "Refusing to clean unexpected web output path: $public"
}
if (Test-Path -LiteralPath $public) {
    Remove-Item -LiteralPath $public -Recurse -Force
}
[void](New-Item -ItemType Directory -Path $public)
Copy-Item -Path (Join-Path $build "*") -Destination $public -Recurse
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "privacy.html") `
    -Destination (Join-Path $public "privacy.html")

& $gcloud run deploy $ServiceName `
    --source $PSScriptRoot `
    --project $ProjectId `
    --region $Region `
    --allow-unauthenticated `
    --port 8080 `
    --cpu 1 `
    --memory 512Mi `
    --concurrency 80 `
    --min-instances 0 `
    --max-instances 2 `
    --quiet
if ($LASTEXITCODE -ne 0) { throw "QRGuard web deployment failed." }

$webUrl = (& $gcloud run services describe $ServiceName `
    --project $ProjectId `
    --region $Region `
    --format "value(status.url)").Trim()
if (-not $webUrl.StartsWith("https://")) {
    throw "Cloud Run did not return an HTTPS web URL."
}

& $gcloud run services update $BackendServiceName `
    --project $ProjectId `
    --region $Region `
    --set-env-vars "QRGUARD_CORS_ORIGINS=$webUrl" `
    --quiet
if ($LASTEXITCODE -ne 0) { throw "Could not restrict backend CORS to $webUrl" }

[void](Invoke-WebRequest -Uri $webUrl -TimeoutSec 60 -UseBasicParsing)
[void](Invoke-WebRequest -Uri "$webUrl/privacy.html" -TimeoutSec 60 -UseBasicParsing)

$record = [ordered]@{
    service = $ServiceName
    project = $ProjectId
    region = $Region
    url = $webUrl
    backend_url = $BackendUrl
    privacy_url = "$webUrl/privacy.html"
    deployed_at = (Get-Date).ToUniversalTime().ToString("o")
}
$record | ConvertTo-Json | Set-Content `
    -LiteralPath (Join-Path $PSScriptRoot "last_deployment.json") `
    -Encoding UTF8
Write-Output "QRGuard web deployed: $webUrl"
Write-Output "Privacy policy: $webUrl/privacy.html"
