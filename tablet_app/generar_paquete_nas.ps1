$ErrorActionPreference = "Stop"

$tabletPath = $PSScriptRoot
$projectPath = Split-Path $tabletPath -Parent
$distPath = Join-Path $projectPath "dist"
$targetPath = Join-Path $distPath "tablet_app_nas"
$zipPath = Join-Path $distPath "bodega-tablet-nas.zip"

& (Join-Path $tabletPath "preparar_configuracion.ps1")

$resolvedProject = [System.IO.Path]::GetFullPath($projectPath)
$resolvedTarget = [System.IO.Path]::GetFullPath($targetPath)
if (-not $resolvedTarget.StartsWith($resolvedProject, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "La carpeta de destino quedo fuera del proyecto."
}

New-Item -ItemType Directory -Path $distPath -Force | Out-Null
if (Test-Path -LiteralPath $targetPath) {
    Remove-Item -LiteralPath $targetPath -Recurse -Force
}
New-Item -ItemType Directory -Path $targetPath -Force | Out-Null

$publicFiles = @(
    "index.html",
    "styles.css",
    "app.js",
    "logic.js",
    "config.js",
    "manifest.webmanifest",
    "service-worker.js",
    "icon.svg",
    "icon-192.png",
    "icon-512.png"
)

foreach ($file in $publicFiles) {
    $source = Join-Path $tabletPath $file
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Falta el archivo requerido: $file"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $targetPath $file)
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $targetPath "*") -DestinationPath $zipPath

Write-Host "Paquete para NAS creado correctamente:"
Write-Host $zipPath
Write-Host "Descomprima su contenido en una carpeta publicada por HTTPS en el NAS."

