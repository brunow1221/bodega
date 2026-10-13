$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "preparar_configuracion.ps1")
Write-Host "Abre http://localhost:8080 en el navegador."

# Ejecutar desde esta carpeta evita que archivos como C:\Users\Bruno\socket.py
# oculten módulos internos de Python cuando el script se inicia desde otro lugar.
Push-Location -LiteralPath $PSScriptRoot
try {
    python -m http.server 8080
}
finally {
    Pop-Location
}
