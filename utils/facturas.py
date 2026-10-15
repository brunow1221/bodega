import os
import shutil
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4


EXTENSIONES_FACTURA = {".pdf", ".jpg", ".jpeg", ".png"}
TAMANO_MAXIMO_FACTURA = 25 * 1024 * 1024


def _fecha_desde_valor(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor).strip())
    except (TypeError, ValueError) as error:
        raise ValueError("La fecha de la factura no es válida.") from error


def _numero_positivo(valor, nombre, permite_cero=False):
    texto = str(valor or "").strip().replace(",", ".")
    try:
        numero = Decimal(texto)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{nombre} debe ser un número válido.") from error

    limite_valido = numero >= 0 if permite_cero else numero > 0
    if not limite_valido:
        condicion = "mayor o igual a cero" if permite_cero else "mayor que cero"
        raise ValueError(f"{nombre} debe ser {condicion}.")
    return format(numero, "f")


def preparar_registro_factura(
    *,
    proveedor,
    numero_factura,
    fecha_factura,
    ruta_archivo,
    archivo_original,
    observacion,
    items,
):
    proveedor = str(proveedor or "").strip()
    numero_factura = str(numero_factura or "").strip()
    ruta_archivo = str(ruta_archivo or "").strip()

    if not proveedor:
        raise ValueError("El proveedor es obligatorio.")
    if not numero_factura:
        raise ValueError("El número de factura es obligatorio.")
    if not ruta_archivo:
        raise ValueError("Debe seleccionar el archivo de la factura.")
    if not items:
        raise ValueError("Debe asociar al menos un producto a la factura.")

    fecha = _fecha_desde_valor(fecha_factura)
    items_normalizados = []
    ids_vistos = set()
    for item in items:
        producto = (item or {}).get("producto") or item or {}
        producto_id = str(producto.get("id") or "").strip()
        producto_nombre = str(producto.get("nombre") or "").strip()
        if not producto_id or not producto_nombre:
            raise ValueError("Debe seleccionar productos válidos.")
        if producto_id in ids_vistos:
            raise ValueError("Un producto no puede repetirse en la misma factura.")
        ids_vistos.add(producto_id)

        items_normalizados.append({
            "producto_id": producto_id,
            "producto_nombre": producto_nombre,
            "cantidad": _numero_positivo(item.get("cantidad"), "La cantidad"),
            "precio_unitario": _numero_positivo(
                item.get("precio_unitario"),
                "El precio unitario",
                permite_cero=True,
            ),
        })

    factura = {
        "proveedor": proveedor,
        "numero_factura": numero_factura,
        "fecha_factura": fecha.isoformat(),
        "ruta_archivo": ruta_archivo,
        "archivo_original": str(archivo_original or "").strip(),
        "observacion": str(observacion or "").strip(),
    }
    return factura, items_normalizados


class AlmacenFacturasNAS:
    """Guarda facturas en una carpeta compartida y expone referencias relativas."""

    def __init__(self, directorio_base):
        valor = str(directorio_base or "").strip()
        if not valor:
            raise ValueError(
                "Falta configurar FACTURAS_NAS_DIR con la carpeta compartida del NAS."
            )
        self.directorio_base = Path(valor).expanduser()

    def guardar(self, archivo_origen, *, fecha_factura):
        origen = Path(archivo_origen)
        if not origen.is_file():
            raise ValueError("No se encontró el archivo de la factura.")

        extension = origen.suffix.lower()
        if extension not in EXTENSIONES_FACTURA:
            raise ValueError("La factura debe ser un archivo PDF, JPG, JPEG o PNG.")

        tamano = origen.stat().st_size
        if tamano <= 0:
            raise ValueError("El archivo de la factura está vacío.")
        if tamano > TAMANO_MAXIMO_FACTURA:
            raise ValueError("El archivo de la factura no puede superar 25 MB.")

        fecha = _fecha_desde_valor(fecha_factura)
        carpeta = self.directorio_base / f"{fecha.year:04d}" / f"{fecha.month:02d}"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"{uuid4().hex}{extension}"
        temporal = destino.with_suffix(destino.suffix + ".part")

        try:
            shutil.copy2(origen, temporal)
            os.replace(temporal, destino)
        except Exception:
            if temporal.exists():
                temporal.unlink()
            raise

        return destino.relative_to(self.directorio_base).as_posix()

    def resolver(self, referencia):
        raiz = self.directorio_base.resolve(strict=False)
        candidato = (raiz / str(referencia or "")).resolve(strict=False)
        try:
            candidato.relative_to(raiz)
        except ValueError as error:
            raise ValueError(
                "La referencia apunta fuera de la carpeta configurada para facturas."
            ) from error
        return candidato

    def eliminar(self, referencia):
        archivo = self.resolver(referencia)
        if archivo.is_file():
            archivo.unlink()


class RegistroFacturaDocumental:
    """Coordina archivo y metadatos sin producir movimientos de inventario."""

    def __init__(self, db_manager, almacen):
        self.db = db_manager
        self.almacen = almacen

    def registrar(
        self,
        *,
        archivo_origen,
        proveedor,
        numero_factura,
        fecha_factura,
        observacion,
        items,
    ):
        # Validar los datos antes de escribir en la carpeta compartida.
        preparar_registro_factura(
            proveedor=proveedor,
            numero_factura=numero_factura,
            fecha_factura=fecha_factura,
            ruta_archivo="pendiente",
            archivo_original=Path(archivo_origen).name,
            observacion=observacion,
            items=items,
        )

        referencia = self.almacen.guardar(
            archivo_origen,
            fecha_factura=_fecha_desde_valor(fecha_factura),
        )
        try:
            factura, items = preparar_registro_factura(
                proveedor=proveedor,
                numero_factura=numero_factura,
                fecha_factura=fecha_factura,
                ruta_archivo=referencia,
                archivo_original=Path(archivo_origen).name,
                observacion=observacion,
                items=items,
            )
            exito, mensaje, datos = self.db.registrar_factura_compra(
                factura,
                items,
            )
        except Exception:
            self.almacen.eliminar(referencia)
            raise

        if not exito:
            self.almacen.eliminar(referencia)
        return exito, mensaje, datos
