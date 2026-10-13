$ErrorActionPreference = "Stop"

$tabletPath = $PSScriptRoot
$projectPath = Split-Path $tabletPath -Parent
$envPath = Join-Path $projectPath ".env"
$distPath = Join-Path $projectPath "dist"
$targetPath = Join-Path $distPath "bodega-tablet-docker"
$zipPath = Join-Path $distPath "bodega-tablet-docker.zip"
$tarPath = Join-Path $distPath "bodega-tablet-docker.tar.gz"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "No se encontro el archivo .env principal."
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $envPath -Encoding UTF8) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
        continue
    }
    $parts = $trimmed.Split("=", 2)
    $settings[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
}

$url = $settings["SUPABASE_URL"]
$key = $settings["SUPABASE_PUBLISHABLE_KEY"]
if (-not $url -or -not $key) {
    throw "Faltan SUPABASE_URL o SUPABASE_PUBLISHABLE_KEY en .env."
}

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
New-Item -ItemType Directory -Path (Join-Path $targetPath "docker-entrypoint.d") -Force | Out-Null

$publicFiles = @(
    "index.html",
    "styles.css",
    "app.js",
    "logic.js",
    "manifest.webmanifest",
    "service-worker.js",
    "icon.svg",
    "icon-192.png",
    "icon-512.png",
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    "config.template.js",
    "nginx.conf",
    "instalar_nas.sh",
    "README.md"
)

foreach ($file in $publicFiles) {
    $source = Join-Path $tabletPath $file
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Falta el archivo requerido: $file"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $targetPath $file)
}

$entrypointSource = Join-Path $tabletPath "docker-entrypoint.d\40-bodega-config.sh"
$entrypointTarget = Join-Path $targetPath "docker-entrypoint.d\40-bodega-config.sh"
Copy-Item -LiteralPath $entrypointSource -Destination $entrypointTarget

$shellFiles = @(
    (Join-Path $targetPath "instalar_nas.sh"),
    $entrypointTarget
)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
foreach ($shellFile in $shellFiles) {
    $shellContent = [System.IO.File]::ReadAllText($shellFile).Replace("`r`n", "`n")
    [System.IO.File]::WriteAllText($shellFile, $shellContent, $utf8NoBom)
}

$dockerEnv = @"
SUPABASE_URL=$url
SUPABASE_PUBLISHABLE_KEY=$key
BODEGA_TABLET_PORT=8080
"@
$dockerEnvPath = Join-Path $targetPath ".env"
[System.IO.File]::WriteAllText($dockerEnvPath, $dockerEnv, $utf8NoBom)

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $targetPath "*") -DestinationPath $zipPath

if (Test-Path -LiteralPath $tarPath) {
    Remove-Item -LiteralPath $tarPath -Force
}
& tar -czf $tarPath -C $targetPath .
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo crear el paquete TAR.GZ."
}

Write-Host "Paquetes Docker creados correctamente:"
Write-Host $zipPath
Write-Host $tarPath
Write-Host "Para NAS sin unzip, suba el TAR.GZ y extraigalo con tar -xzf."
