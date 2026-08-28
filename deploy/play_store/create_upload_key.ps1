[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$android = Join-Path $repo "app\android"
$desktop = [Environment]::GetFolderPath("Desktop")
$secretDirectory = Join-Path $desktop "QRGuard_Release_Secrets"
$keystore = Join-Path $secretDirectory "qrguard-upload.jks"
$protectedCredential = Join-Path $secretDirectory "qrguard-upload-password.clixml"
$properties = Join-Path $android "key.properties"
$keytool = "C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe"

if (-not (Test-Path -LiteralPath $keytool -PathType Leaf)) {
    throw "Android Studio keytool was not found at $keytool"
}
foreach ($target in @($keystore, $protectedCredential, $properties)) {
    if (Test-Path -LiteralPath $target) {
        throw "Refusing to overwrite existing release credential: $target"
    }
}

[void](New-Item -ItemType Directory -Path $secretDirectory -Force)
$bytes = New-Object byte[] 32
$random = [Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $random.GetBytes($bytes)
}
finally {
    $random.Dispose()
}
$password = [Convert]::ToBase64String($bytes).Replace("+", "A").Replace("/", "B")
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force

& $keytool -genkeypair -v `
    -keystore $keystore `
    -storetype JKS `
    -storepass $password `
    -alias "qrguard-upload" `
    -keypass $password `
    -keyalg RSA `
    -keysize 4096 `
    -validity 10000 `
    -dname "CN=QRGuard, OU=OSSWT, O=OSSWT, L=Kampar, ST=Perak, C=MY"
if ($LASTEXITCODE -ne 0) { throw "keytool failed to create the upload key." }

[pscredential]::new("qrguard-upload", $securePassword) |
    Export-Clixml -LiteralPath $protectedCredential
$javaStorePath = $keystore.Replace("\", "/")
$content = @(
    "storePassword=$password",
    "keyPassword=$password",
    "keyAlias=qrguard-upload",
    "storeFile=$javaStorePath"
) -join [Environment]::NewLine
[IO.File]::WriteAllText($properties, $content, [Text.UTF8Encoding]::new($false))

$password = $null
$securePassword.Dispose()
Write-Output "Upload keystore: $keystore"
Write-Output "DPAPI-protected credential: $protectedCredential"
Write-Output "Gradle signing properties: $properties"
Write-Output "Back up QRGuard_Release_Secrets before the first Play upload."
