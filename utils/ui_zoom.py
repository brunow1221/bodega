import json
import os
from pathlib import Path


ZOOM_PREDETERMINADO = 100
ZOOM_MINIMO = 80
ZOOM_MAXIMO = 160
PASO_ZOOM = 10
TEMA_PREDETERMINADO = "Light"


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


def normalizar_tema(valor):
    texto = str(valor or "").strip().casefold()
    if texto in {"dark", "oscuro"}:
        return "Dark"
    if texto in {"light", "claro"}:
        return "Light"
    return TEMA_PREDETERMINADO


def _cargar_preferencias():
    try:
        datos = json.loads(
            obtener_ruta_preferencias().read_text(encoding="utf-8")
        )
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _guardar_preferencias(cambios):
    try:
        ruta = obtener_ruta_preferencias()
        datos = _cargar_preferencias()
        datos.update(cambios)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(datos, indent=2),
            encoding="utf-8"
        )
        return True
    except OSError:
        return False


def cargar_zoom():
    datos = _cargar_preferencias()
    return normalizar_zoom(datos.get("zoom", ZOOM_PREDETERMINADO))


def guardar_zoom(valor):
    zoom = normalizar_zoom(valor)
    return _guardar_preferencias({"zoom": zoom})


def cargar_tema():
    datos = _cargar_preferencias()
    return normalizar_tema(datos.get("tema", TEMA_PREDETERMINADO))


def guardar_tema(valor):
    tema = normalizar_tema(valor)
    return _guardar_preferencias({"tema": tema})
