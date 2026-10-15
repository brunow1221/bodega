import os
import sys
from pathlib import Path


def _cargar_env_local():
    rutas = []

    if getattr(sys, "frozen", False):
        rutas.append(Path(sys.executable).resolve().parent / ".env")

    rutas.extend([
        Path(__file__).resolve().parent / ".env",
        Path.cwd() / ".env",
    ])

    vistas = set()
    for ruta in rutas:
        if ruta in vistas or not ruta.exists():
            continue
        vistas.add(ruta)

        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(
                clave.strip(),
                valor.strip().strip('"').strip("'")
            )


_cargar_env_local()

VERSION_APP = "1.1.2"

SUPABASE_URL_PREDETERMINADA = "https://vqxvuwepzzexnmhenitt.supabase.co"
SUPABASE_PUBLISHABLE_KEY_PREDETERMINADA = (
    "sb_publishable_SZvlgGCY-HB22e5vjslWHA_u55DOdSe"
)


def _obtener_configuracion(nombre, valor_predeterminado):
    return os.environ.get(nombre, valor_predeterminado).strip()


URL_SUPABASE = _obtener_configuracion(
    "SUPABASE_URL",
    SUPABASE_URL_PREDETERMINADA,
)
KEY_SUPABASE = _obtener_configuracion(
    "SUPABASE_PUBLISHABLE_KEY",
    SUPABASE_PUBLISHABLE_KEY_PREDETERMINADA,
)

# Carpeta compartida donde se guardan los PDF e imágenes de facturas.
# Puede ser una ruta UNC (\\NAS\Bodega\Facturas) o una unidad de red.
DIRECTORIO_FACTURAS_NAS = os.environ.get("FACTURAS_NAS_DIR", "").strip()

VERIFICAR_ACTUALIZACIONES = (
    os.environ.get("VERIFICAR_ACTUALIZACIONES", "0").strip().lower()
    in {"1", "true", "yes", "si"}
)
