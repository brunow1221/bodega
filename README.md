# Sistema de Gestion de Bodega

Aplicacion de escritorio para gestionar inventario, salidas, proyectos,
trabajadores, herramientas en terreno y mapa de bodega por sectores y estantes.

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
database/migrations/000_esquema_base.sql
database/migrations/001_integridad_seguridad.sql
database/migrations/002_racks_configurables.sql
database/migrations/003_politicas_lectura_app.sql
database/migrations/004_corregir_ambiguedad_columna_racks.sql
database/migrations/005_racks_solo_niveles.sql
database/migrations/007_corregir_tipo_producto_origen.sql
database/migrations/008_crear_productos_compatible.sql
database/migrations/009_editar_cantidad_producto.sql
database/migrations/010_bodega_exterior_sectores_especiales.sql
database/migrations/011_separar_cafeteria_aseo.sql
database/migrations/012_historial_cambios_precio.sql
database/migrations/013_pgp_contenedores.sql
database/migrations/014_fecha_termino_proyecto.sql
database/migrations/015_herramientas_personales.sql
database/migrations/016_ampliar_pgp.sql
database/migrations/017_facturas_documentales.sql
```

Para usar el archivo documental de facturas, configure además una carpeta
compartida del NAS accesible desde todos los equipos que ejecuten la aplicación:

```powershell
$env:FACTURAS_NAS_DIR = "\\NOMBRE-NAS\Bodega\Facturas"
```

La aplicación organiza los archivos por año y mes. Registrar una factura no
modifica el stock ni el precio vigente del producto.

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
- llaves reales de Supabase

Para publicar una version instalable, subir el instalador como asset de un
GitHub Release, por ejemplo `v1.0.0`.

El build empaqueta `assets/icono.ico` y las migraciones requeridas por la app.
