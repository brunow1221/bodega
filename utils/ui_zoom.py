import json
import os
from pathlib import Path


ZOOM_PREDETERMINADO = 100
ZOOM_MINIMO = 80
ZOOM_MAXIMO = 160
PASO_ZOOM = 10


def normalizar_zoom(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return ZOOM_PREDETERMINADO

    ajustado = int(round(numero / PASO_ZOOM) * PASO_ZOOM)
    return max(ZOOM_MINIMO, min(ZOOM_MAXIMO, ajustado))


def obtener_ruta_preferencias():
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "SistemaBodega" / "preferencias.json"

    return Path.home() / ".sistema_bodega" / "preferencias.json"


def cargar_zoom():
    try:
        datos = json.loads(
            obtener_ruta_preferencias().read_text(encoding="utf-8")
        )
        return normalizar_zoom(datos.get("zoom", ZOOM_PREDETERMINADO))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return ZOOM_PREDETERMINADO


def guardar_zoom(valor):
    zoom = normalizar_zoom(valor)
    try:
        ruta = obtener_ruta_preferencias()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps({"zoom": zoom}, indent=2),
            encoding="utf-8"
        )
        return True
    except OSError:
        return False
