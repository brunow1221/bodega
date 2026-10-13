"""Cálculos puros para el panel de estadísticas de movimientos."""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import unicodedata

from utils.fechas import fecha_hora_local
from utils.movimientos import TIPO_ENTREGA_HERRAMIENTA_PERSONAL


TODOS = "Todos"

_TIPOS_USO = {
    "entrega / consumo": "Entrega / Consumo",
    "entrega de herramienta personal": TIPO_ENTREGA_HERRAMIENTA_PERSONAL,
    "baja por dano / merma": "Baja por Daño / Merma",
    "corte / transformacion": "Corte / Transformación",
    "prestamo de herramienta": "Préstamo de Herramienta",
}

_TIPOS_SALIDA = {
    *_TIPOS_USO,
    "envio a calibracion / reparacion",
}

_TIPOS_ENTRADA = {
    "devolucion de herramienta",
    "devolucion pgp",
    "retorno de reparacion",
    "entrada / reposicion",
}

TIPOS_USO = tuple(dict.fromkeys(_TIPOS_USO.values()))

_MESES = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sept", "oct", "nov", "dic",
)


def normalizar_texto(valor):
    texto = unicodedata.normalize("NFD", str(valor or "").strip())
    return "".join(
        caracter for caracter in texto
        if not unicodedata.combining(caracter)
    ).casefold()


def tipo_uso_canonico(valor):
    return _TIPOS_USO.get(normalizar_texto(valor))


def clave_producto(movimiento):
    return movimiento.get("producto_id") or normalizar_texto(
        movimiento.get("producto") or "Producto desconocido"
    )


def convertir_fecha_filtro(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor).strip(), "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError("Las fechas deben usar el formato AAAA-MM-DD.") from error


def convertir_decimal(valor):
    try:
        return Decimal(str(valor or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def calcular_estadisticas(
    movimientos,
    proyecto=TODOS,
    tipo_movimiento=TODOS,
    desde=None,
    hasta=None,
    limite=10,
):
    """Filtra movimientos de uso y devuelve agrupaciones listas para graficar."""
    fecha_desde = convertir_fecha_filtro(desde)
    fecha_hasta = convertir_fecha_filtro(hasta)
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise ValueError("La fecha desde no puede ser posterior a la fecha hasta.")

    try:
        limite = max(3, min(20, int(limite)))
    except (TypeError, ValueError):
        limite = 10

    por_producto = {}
    por_proyecto = defaultdict(int)
    por_mes = defaultdict(int)
    por_tipo = defaultdict(int)
    total_cantidad = 0
    total_valor = Decimal("0")
    total_movimientos = 0

    for movimiento in movimientos or []:
        tipo = tipo_uso_canonico(movimiento.get("tipo_movimiento"))
        if not tipo:
            continue
        if tipo_movimiento != TODOS and tipo != tipo_movimiento:
            continue

        nombre_proyecto = str(
            movimiento.get("proyecto") or "Sin proyecto"
        ).strip() or "Sin proyecto"
        if proyecto != TODOS and nombre_proyecto != proyecto:
            continue

        fecha = fecha_hora_local(movimiento.get("fecha_hora"))
        if fecha_desde and (fecha is None or fecha.date() < fecha_desde):
            continue
        if fecha_hasta and (fecha is None or fecha.date() > fecha_hasta):
            continue

        try:
            cantidad = int(movimiento.get("cantidad_movida") or 0)
        except (TypeError, ValueError):
            continue
        if cantidad <= 0:
            continue

        producto_id = movimiento.get("producto_id")
        nombre_producto = str(
            movimiento.get("producto") or "Producto desconocido"
        ).strip() or "Producto desconocido"
        clave_producto = producto_id or normalizar_texto(nombre_producto)
        if clave_producto not in por_producto:
            por_producto[clave_producto] = {
                "etiqueta": nombre_producto,
                "cantidad": 0,
            }
        por_producto[clave_producto]["cantidad"] += cantidad

        precio = convertir_decimal(movimiento.get("precio_unitario"))
        total_cantidad += cantidad
        total_valor += precio * cantidad
        total_movimientos += 1
        por_proyecto[nombre_proyecto] += cantidad
        por_tipo[tipo] += cantidad
        if fecha is not None:
            por_mes[(fecha.year, fecha.month)] += cantidad

    productos = sorted(
        por_producto.values(),
        key=lambda item: (-item["cantidad"], normalizar_texto(item["etiqueta"])),
    )
    proyectos = sorted(
        (
            {"etiqueta": etiqueta, "cantidad": cantidad}
            for etiqueta, cantidad in por_proyecto.items()
        ),
        key=lambda item: (-item["cantidad"], normalizar_texto(item["etiqueta"])),
    )
    tipos = sorted(
        (
            {"etiqueta": etiqueta, "cantidad": cantidad}
            for etiqueta, cantidad in por_tipo.items()
        ),
        key=lambda item: (-item["cantidad"], normalizar_texto(item["etiqueta"])),
    )
    meses = []
    if por_mes:
        primer_ano, primer_mes = min(por_mes)
        ultimo_ano, ultimo_mes = max(por_mes)
        diferencia = (ultimo_ano - primer_ano) * 12 + ultimo_mes - primer_mes
        cantidad_meses = min(12, diferencia + 1)
        indice_ultimo = ultimo_ano * 12 + ultimo_mes - 1
        for desplazamiento in range(cantidad_meses - 1, -1, -1):
            indice = indice_ultimo - desplazamiento
            meses.append((indice // 12, indice % 12 + 1))
    tendencia = [
        {
            "etiqueta": f"{_MESES[mes - 1]} {ano}",
            "cantidad": por_mes[(ano, mes)],
        }
        for ano, mes in meses
    ]

    return {
        "total_movimientos": total_movimientos,
        "cantidad_total": total_cantidad,
        "valor_total": total_valor,
        "productos_distintos": len(por_producto),
        "proyectos_distintos": len([
            nombre for nombre in por_proyecto if nombre != "Sin proyecto"
        ]),
        "productos": productos[:limite],
        "proyectos": proyectos[:limite],
        "tipos": tipos,
        "tendencia": tendencia,
    }


def calcular_historial_articulo(
    movimientos,
    producto_clave,
    proyecto=TODOS,
    tipo_movimiento=TODOS,
    desde=None,
    hasta=None,
):
    """Devuelve movimientos y totales de un artículo específico."""
    fecha_desde = convertir_fecha_filtro(desde)
    fecha_hasta = convertir_fecha_filtro(hasta)
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise ValueError("La fecha desde no puede ser posterior a la fecha hasta.")

    filas = []
    total_retirado = 0
    total_devuelto = 0

    for movimiento in movimientos or []:
        if clave_producto(movimiento) != producto_clave:
            continue

        nombre_proyecto = str(
            movimiento.get("proyecto") or "Sin proyecto"
        ).strip() or "Sin proyecto"
        if proyecto != TODOS and nombre_proyecto != proyecto:
            continue

        tipo = str(movimiento.get("tipo_movimiento") or "Sin movimiento").strip()
        if (
            tipo_movimiento != TODOS
            and normalizar_texto(tipo) != normalizar_texto(tipo_movimiento)
        ):
            continue

        fecha = fecha_hora_local(movimiento.get("fecha_hora"))
        if fecha_desde and (fecha is None or fecha.date() < fecha_desde):
            continue
        if fecha_hasta and (fecha is None or fecha.date() > fecha_hasta):
            continue

        try:
            cantidad = max(0, int(movimiento.get("cantidad_movida") or 0))
        except (TypeError, ValueError):
            cantidad = 0

        tipo_normalizado = normalizar_texto(tipo)
        if tipo_normalizado in _TIPOS_SALIDA:
            total_retirado += cantidad
        elif tipo_normalizado in _TIPOS_ENTRADA:
            total_devuelto += cantidad

        filas.append({
            "fecha": fecha,
            "fecha_texto": (
                fecha.strftime("%d/%m/%Y %H:%M") if fecha is not None else "-"
            ),
            "tipo_movimiento": tipo,
            "cantidad": cantidad,
            "trabajador": movimiento.get("trabajador") or "Sin responsable",
            "proyecto": nombre_proyecto,
            "registrado_por": movimiento.get("registrado_por") or "-",
            "stock_anterior": movimiento.get("stock_anterior"),
            "stock_nuevo": movimiento.get("stock_nuevo"),
            "comentario": movimiento.get("comentario") or "-",
        })

    filas.sort(
        key=lambda fila: (
            fila["fecha"] is not None,
            fila["fecha"].timestamp() if fila["fecha"] is not None else 0,
        ),
        reverse=True,
    )
    return {
        "filas": filas,
        "movimientos": len(filas),
        "total_retirado": total_retirado,
        "total_devuelto": total_devuelto,
        "saldo_movimientos": total_devuelto - total_retirado,
    }


def calcular_historial_precios(
    cambios,
    producto_clave=None,
    direccion=TODOS,
    desde=None,
    hasta=None,
):
    """Filtra y resume cambios de precio registrados por la base de datos."""
    fecha_desde = convertir_fecha_filtro(desde)
    fecha_hasta = convertir_fecha_filtro(hasta)
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise ValueError("La fecha desde no puede ser posterior a la fecha hasta.")

    filas = []
    productos = set()
    aumentos = 0
    disminuciones = 0

    for cambio in cambios or []:
        clave = cambio.get("producto_id") or normalizar_texto(
            cambio.get("producto_nombre")
        )
        if producto_clave is not None and clave != producto_clave:
            continue

        anterior = convertir_decimal(cambio.get("precio_anterior"))
        nuevo = convertir_decimal(cambio.get("precio_nuevo"))
        diferencia = nuevo - anterior
        if direccion == "Aumentos" and diferencia <= 0:
            continue
        if direccion == "Disminuciones" and diferencia >= 0:
            continue

        fecha = fecha_hora_local(cambio.get("fecha_hora"))
        if fecha_desde and (fecha is None or fecha.date() < fecha_desde):
            continue
        if fecha_hasta and (fecha is None or fecha.date() > fecha_hasta):
            continue

        if diferencia > 0:
            aumentos += 1
        elif diferencia < 0:
            disminuciones += 1
        productos.add(clave)
        porcentaje = (
            diferencia * Decimal("100") / anterior
            if anterior != 0 else None
        )
        filas.append({
            "fecha": fecha,
            "fecha_texto": (
                fecha.strftime("%d/%m/%Y %H:%M") if fecha is not None else "-"
            ),
            "producto_id": cambio.get("producto_id"),
            "producto": cambio.get("producto_nombre") or "Producto eliminado",
            "precio_anterior": anterior,
            "precio_nuevo": nuevo,
            "diferencia": diferencia,
            "porcentaje": porcentaje,
            "usuario": cambio.get("usuario_app") or "Usuario no identificado",
        })

    filas.sort(
        key=lambda fila: (
            fila["fecha"] is not None,
            fila["fecha"].timestamp() if fila["fecha"] is not None else 0,
        ),
        reverse=True,
    )
    return {
        "filas": filas,
        "cambios": len(filas),
        "productos": len(productos),
        "aumentos": aumentos,
        "disminuciones": disminuciones,
    }
