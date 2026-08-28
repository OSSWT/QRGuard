[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "asia-southeast1",
    [string]$ServiceName = "qrguard-api",
    [string]$CorsOrigins = ""
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$gcloudCommand = Get-Command "gcloud" -ErrorAction SilentlyContinue
$gcloud = if ($gcloudCommand) {
    $gcloudCommand.Source
} else {
    "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
}
if (-not (Test-Path -LiteralPath $gcloud -PathType Leaf)) {
    throw "Google Cloud CLI is not installed."
}

Push-Location $repo
try {
    & $gcloud config set project $ProjectId
    if ($LASTEXITCODE -ne 0) { throw "Could not select Google Cloud project." }

    $arguments = @(
        "run", "deploy", $ServiceName,
        "--source", ".",
        "--project", $ProjectId,
        "--region", $Region,
        "--allow-unauthenticated",
        "--port", "8080",
        "--cpu", "2",
        "--memory", "2Gi",
        "--concurrency", "8",
        "--min-instances", "0",
        "--max-instances", "2",
        "--timeout", "60",
        "--set-env-vars", "QRGUARD_CORS_ORIGINS=$CorsOrigins",
        "--quiet"
    )
    & $gcloud @arguments
    if ($LASTEXITCODE -ne 0) { throw "Cloud Run deployment failed." }

    $url = (& $gcloud run services describe $ServiceName `
        --project $ProjectId `
        --region $Region `
        --format "value(status.url)").Trim()
    if (-not $url.StartsWith("https://")) {
        throw "Cloud Run did not return an HTTPS service URL."
    }

    $health = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 60
    if ($health.status -ne "ok") {
        throw "Online health check is $($health.status): $($health | ConvertTo-Json -Depth 8)"
    }

    $record = [ordered]@{
        service = $ServiceName
        project = $ProjectId
        region = $Region
        url = $url
        deployed_at = (Get-Date).ToUniversalTime().ToString("o")
        health = $health
    }
    $record | ConvertTo-Json -Depth 8 | Set-Content `
        -LiteralPath (Join-Path $PSScriptRoot "last_deployment.json") `
        -Encoding UTF8
    Write-Output "QRGuard backend deployed: $url"
}
finally {
    Pop-Location
}
