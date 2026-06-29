@echo off
echo ============================================
echo Generando ejecutable Sistema Bodega...
echo ============================================

rmdir /s /q build
rmdir /s /q dist

pyinstaller ^
--noconfirm ^
--clean ^
--windowed ^
--name "SistemaBodega" ^
--icon "assets\icono.ico" ^
--version-file "version_info.txt" ^
--add-data "assets\icono.ico;assets" ^
--add-data "database\migrations;database\migrations" ^
--add-data "MIGRACION_SEGURIDAD.md;." ^
--collect-data barcode ^
main.py

echo.
echo ============================================
echo Ejecutable generado en dist\SistemaBodega
echo ============================================
pause
