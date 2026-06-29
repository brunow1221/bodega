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

VERSION_APP = "1.0.0"

URL_SUPABASE = os.environ.get("SUPABASE_URL", "").strip()
KEY_SUPABASE = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()

VERIFICAR_ACTUALIZACIONES = (
    os.environ.get("VERIFICAR_ACTUALIZACIONES", "0").strip().lower()
    in {"1", "true", "yes", "si"}
)
