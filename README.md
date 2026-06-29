# Sistema de Gestion de Bodega

Aplicacion de escritorio para gestionar inventario, salidas, proyectos,
trabajadores, herramientas en terreno y mapa de bodega con racks configurables.

Version publica inicial: `v1.0.0`.

## Requisitos

- Python 3.12 o compatible.
- Cuenta/proyecto de Supabase.
- En Windows, Inno Setup solo si se quiere generar instalador.

## Configuracion

1. Instalar dependencias:

```powershell
python -m pip install -r requirements.txt
```

2. Crear variables de entorno tomando como base `.env.example`:

```powershell
$env:SUPABASE_URL = "https://tu-proyecto.supabase.co"
$env:SUPABASE_PUBLISHABLE_KEY = "sb_publishable_tu_clave_publica"
```

Tambien se puede crear un archivo `.env` local en la raiz del proyecto o junto
al EXE instalado. Ese archivo queda ignorado por Git.

3. Ejecutar las migraciones en Supabase SQL Editor, en este orden:

```text
database/migrations/001_integridad_seguridad.sql
database/migrations/002_racks_configurables.sql
```

La llave `SUPABASE_SERVICE_ROLE_KEY` solo se usa para scripts administrativos
locales. No debe guardarse en GitHub.

## Ejecutar

```powershell
python main.py
```

## Pruebas

```powershell
python -m unittest discover -q
```

## Generar EXE

```powershell
.\build_exe.bat
```

El ejecutable queda en `dist/SistemaBodega/`.

## Generar instalador

Despues de generar el EXE, compilar `installer.iss` con Inno Setup.

El instalador queda en `installer_output/`.

## Publicar en GitHub

El repositorio debe incluir codigo fuente, migraciones y documentacion. No subir:

- `.env`
- `dist/`
- `build/`
- `installer_output/`
- codigos QR o codigos de barra generados
- llaves reales de Supabase

Para publicar una version instalable, subir el instalador como asset de un
GitHub Release, por ejemplo `v1.0.0`.

El build solo empaqueta `assets/icono.ico`; los codigos generados por la app se
guardan localmente en Documentos del usuario.
