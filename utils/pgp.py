TIPO_ENTREGA_PGP = "Entrega / Consumo"
TIPO_PRESTAMO_PGP = "Préstamo de Herramienta"
TIPO_DEVOLUCION_PGP = "Devolución PGP"
TIPOS_MOVIMIENTO_PGP = (TIPO_ENTREGA_PGP, TIPO_PRESTAMO_PGP)


def preparar_items_pgp(items, rut_responsable=""):
    if not items:
        raise ValueError("Agregue al menos un artículo al PGP.")
    if len(items) > 100:
        raise ValueError("Un PGP puede contener como máximo 100 artículos.")

    resultado = []
    productos_vistos = set()
    contiene_prestamo = False

    for item in items:
        producto = item.get("producto") or {}
        producto_id = str(
            item.get("producto_id") or producto.get("id") or ""
        ).strip()
        nombre = str(
            item.get("producto_nombre") or producto.get("nombre") or "Artículo"
        ).strip()
        tipo = str(item.get("tipo_movimiento") or "").strip()

        if not producto_id:
            raise ValueError(f"{nombre}: falta identificar el artículo.")
        if producto_id in productos_vistos:
            raise ValueError(f"{nombre} ya está agregado al PGP.")
        if tipo not in TIPOS_MOVIMIENTO_PGP:
            raise ValueError(f"{nombre}: el tipo de movimiento no es válido.")

        try:
            cantidad = int(item.get("cantidad"))
        except (TypeError, ValueError) as error:
            raise ValueError(f"{nombre}: la cantidad debe ser un número entero.") from error
        if cantidad <= 0:
            raise ValueError(f"{nombre}: la cantidad debe ser mayor a cero.")

        stock_valor = item.get("stock_disponible", producto.get("stock"))
        if stock_valor not in (None, ""):
            try:
                stock = int(stock_valor)
            except (TypeError, ValueError):
                stock = 0
            if cantidad > stock:
                raise ValueError(
                    f"Stock insuficiente para {nombre}. Disponible: {stock}."
                )

        productos_vistos.add(producto_id)
        contiene_prestamo = contiene_prestamo or tipo == TIPO_PRESTAMO_PGP
        resultado.append({
            "producto_id": producto_id,
            "cantidad": cantidad,
            "tipo_movimiento": tipo,
        })

    if contiene_prestamo and not str(rut_responsable or "").strip():
        raise ValueError(
            "Los PGP con herramientas en préstamo requieren un responsable."
        )

    return resultado


def cantidad_pendiente_item_pgp(item):
    cantidad = max(0, int(item.get("cantidad") or 0))
    devuelta = max(0, int(item.get("cantidad_devuelta") or 0))
    return max(0, cantidad - devuelta)
