"""Presentación de fechas de movimientos en la zona horaria de la bodega."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


ZONA_HORARIA_BODEGA = "America/Santiago"


def fecha_actual_bodega():
    return datetime.now(ZoneInfo(ZONA_HORARIA_BODEGA)).date().isoformat()


def fecha_hora_local(valor):
    """Convierte un timestamp ISO de la base de datos a la hora de Santiago.

    Conserva el instante de timestamps con offset. Los timestamps antiguos sin
    zona se interpretan como UTC, igual que el origen de datos. No modifica el
    valor almacenado. Los valores vacíos o inválidos devuelven None.
    """
    if not valor:
        return None

    try:
        fecha = valor if isinstance(valor, datetime) else datetime.fromisoformat(
            str(valor).strip().replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None

    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)

    return fecha.astimezone(ZoneInfo(ZONA_HORARIA_BODEGA))


def formatear_fecha_hora(valor, formato="%Y-%m-%d %H:%M"):
    fecha = fecha_hora_local(valor)
    return fecha.strftime(formato) if fecha is not None else "-"
