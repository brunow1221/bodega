TIPO_ENTREGA_HERRAMIENTA_PERSONAL = "Entrega de Herramienta Personal"


def validar_entrega_herramienta_personal(tipo_movimiento, producto, trabajador):
    """Retorna el mensaje de validación o una cadena vacía si es válida."""
    if tipo_movimiento != TIPO_ENTREGA_HERRAMIENTA_PERSONAL:
        return ""
    if not trabajador:
        return "Seleccione al trabajador que recibirá la herramienta personal."
    if str((producto or {}).get("categoria") or "").strip().casefold() != "herramientas":
        return (
            "La entrega personal solo admite productos de la categoría "
            "Herramientas."
        )
    return ""
