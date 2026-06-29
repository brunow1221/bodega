# Migración requerida

La versión corregida necesita aplicar una migración antes de habilitar escrituras.

1. Abra el proyecto correcto en Supabase.
2. Entre a **SQL Editor**.
3. Ejecute completo `database/migrations/001_integridad_seguridad.sql`.
4. Ejecute después `database/migrations/002_racks_configurables.sql`.
5. Cierre y vuelva a abrir la aplicación.

La migración:

- registra sesiones temporales por usuario;
- bloquea escrituras directas con la clave pública;
- hace atómicos e idempotentes los movimientos de stock;
- valida devoluciones y retornos;
- guarda precio, nombre, código y ubicación históricos;
- asocia auditoría al usuario autenticado.

La segunda migración permite crear, editar, retirar y reactivar racks,
configurar su matriz entre 1 y 8 niveles/columnas, guardar sus dimensiones
físicas y evitar reducciones que dejen productos sin ubicación.

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
