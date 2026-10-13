$ErrorActionPreference = "Stop"

$envPath = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
$outputPath = Join-Path $PSScriptRoot "config.js"

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

$urlJson = ConvertTo-Json $url -Compress
$keyJson = ConvertTo-Json $key -Compress
$content = @"
window.BODEGA_CONFIG = {
  supabaseUrl: $urlJson,
  supabaseKey: $keyJson,
};
"@

Set-Content -LiteralPath $outputPath -Value $content -Encoding UTF8
Write-Host "Configuracion creada correctamente en tablet_app/config.js"
