# Migración requerida

La versión corregida necesita aplicar una migración antes de habilitar escrituras.

1. Abra el proyecto correcto en Supabase.
2. Entre a **SQL Editor**.
3. Si la base no tiene `bodegas`, `racks`, `ubicaciones` o
   `login_usuario_app`, ejecute primero
   `database/migrations/000_esquema_base.sql`.
4. Ejecute completo `database/migrations/001_integridad_seguridad.sql`.
5. Ejecute después `database/migrations/002_racks_configurables.sql`.
6. Ejecute `database/migrations/003_politicas_lectura_app.sql`.
7. Ejecute `database/migrations/004_corregir_ambiguedad_columna_racks.sql`.
8. Ejecute `database/migrations/005_racks_solo_niveles.sql`.
9. Ejecute `database/migrations/007_corregir_tipo_producto_origen.sql`.
10. Ejecute `database/migrations/008_crear_productos_compatible.sql`.
11. Ejecute `database/migrations/009_editar_cantidad_producto.sql`.
12. Ejecute `database/migrations/010_bodega_exterior_sectores_especiales.sql`.
13. Ejecute `database/migrations/011_separar_cafeteria_aseo.sql`.
14. Ejecute `database/migrations/012_historial_cambios_precio.sql`.
15. Cierre y vuelva a abrir la aplicación.

La migración:

- registra sesiones temporales por usuario;
- bloquea escrituras directas con la clave pública;
- hace atómicos e idempotentes los movimientos de stock;
- valida devoluciones y retornos;
- guarda precio, nombre, código y ubicación históricos;
- asocia auditoría al usuario autenticado.

La migración `012` registra cada cambio real del precio de un artículo, con
precio anterior, precio nuevo, fecha y usuario. También recupera desde la
auditoría los cambios anteriores que puedan comprobarse con ambos precios.

La migración `005` crea los sectores A y B y permite configurar sus módulos
físicos y la cantidad de estantes por módulo. Dentro de cada sector, los
estantes se numeran desde abajo hacia arriba y se continúa desde el módulo de
la derecha hacia los módulos de la izquierda. También evita reducciones que
dejen productos sin ubicación.

La versión actual de `005` no usa tablas temporales. Si una ejecución anterior
falló con `relation "rack_codigos_nuevos" does not exist`, vuelva a ejecutar el
archivo `005` completo desde el inicio.

Para crear o reparar el administrador `bruno`, abra
`database/migrations/006_crear_admin_bruno.sql`, reemplace el marcador por una
clave nueva y ejecute el contenido completo en SQL Editor. Este script también
comprueba el inicio de sesión y revierte el cambio si la comprobación falla.

## Scripts administrativos

`simulador.py` y `limpiar_base.py` ya no contienen credenciales. Para ejecutarlos:

```powershell
$env:SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "TU_SERVICE_ROLE_KEY"
python simulador.py
```

Para limpiar datos simulados antes de simular:

```powershell
$env:SIMULADOR_LIMPIAR_ANTES = "1"
python simulador.py
```

No distribuya la service role key junto con la aplicación.
