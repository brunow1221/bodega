import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from database.db_manager import DatabaseManager
from utils.facturas import (
    AlmacenFacturasNAS,
    RegistroFacturaDocumental,
    preparar_registro_factura,
)


class AlmacenFacturasNASTests(unittest.TestCase):
    def test_guarda_una_copia_organizada_por_fecha_y_devuelve_ruta_relativa(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal) / "nas"
            origen = Path(temporal) / "factura original.pdf"
            origen.write_bytes(b"%PDF-1.4 factura")
            almacen = AlmacenFacturasNAS(raiz)

            referencia = almacen.guardar(
                origen,
                fecha_factura=date(2026, 10, 15),
            )

            self.assertEqual(Path(referencia).parts[:2], ("2026", "10"))
            self.assertEqual(almacen.resolver(referencia).read_bytes(), origen.read_bytes())
            self.assertNotEqual(almacen.resolver(referencia), origen)

    def test_rechaza_formatos_que_no_son_documentos_de_factura(self):
        with tempfile.TemporaryDirectory() as temporal:
            origen = Path(temporal) / "programa.exe"
            origen.write_bytes(b"contenido")
            almacen = AlmacenFacturasNAS(Path(temporal) / "nas")

            with self.assertRaisesRegex(ValueError, "PDF, JPG, JPEG o PNG"):
                almacen.guardar(origen, fecha_factura=date(2026, 10, 15))

    def test_no_resuelve_rutas_fuera_de_la_carpeta_configurada(self):
        with tempfile.TemporaryDirectory() as temporal:
            almacen = AlmacenFacturasNAS(Path(temporal) / "nas")

            with self.assertRaisesRegex(ValueError, "fuera de la carpeta"):
                almacen.resolver("../secreto.pdf")


class PrepararRegistroFacturaTests(unittest.TestCase):
    def test_prepara_factura_documental_sin_datos_de_stock(self):
        factura, items = preparar_registro_factura(
            proveedor="Proveedor Uno",
            numero_factura="F-125",
            fecha_factura="2026-10-15",
            ruta_archivo="2026/10/archivo.pdf",
            archivo_original="factura.pdf",
            observacion="Compra histórica",
            items=[
                {
                    "producto": {"id": 7, "nombre": "Disco de corte"},
                    "cantidad": "15",
                    "precio_unitario": "4500.50",
                },
                {
                    "producto": {"id": 8, "nombre": "Guante"},
                    "cantidad": "4",
                    "precio_unitario": "2100",
                },
            ],
        )

        self.assertEqual(factura["numero_factura"], "F-125")
        self.assertEqual(items, [
            {
                "producto_id": "7",
                "producto_nombre": "Disco de corte",
                "cantidad": "15",
                "precio_unitario": "4500.50",
            },
            {
                "producto_id": "8",
                "producto_nombre": "Guante",
                "cantidad": "4",
                "precio_unitario": "2100",
            },
        ])
        self.assertNotIn("stock", factura)
        self.assertNotIn("stock", items[0])


class DatabaseFacturasTests(unittest.TestCase):
    def crear_manager(self):
        manager = DatabaseManager.__new__(DatabaseManager)
        manager.session_token = "token-sesion"
        manager._ejecutar_con_reintentos = lambda operacion: operacion()
        manager.supabase = Mock()
        return manager

    def test_registrar_factura_usa_rpc_documental_y_no_mutacion_de_inventario(self):
        manager = self.crear_manager()
        respuesta = SimpleNamespace(data={"ok": True, "factura_id": "abc"})
        manager.supabase.rpc.return_value.execute.return_value = respuesta

        exito, _, datos = manager.registrar_factura_compra(
            {"proveedor": "Proveedor", "numero_factura": "1"},
            [{"producto_id": "7", "cantidad": "2", "precio_unitario": "100"}],
        )

        self.assertTrue(exito)
        self.assertEqual(datos["factura_id"], "abc")
        nombre_rpc, parametros = manager.supabase.rpc.call_args.args
        self.assertEqual(nombre_rpc, "registrar_factura_compra_app")
        self.assertEqual(parametros["p_factura"]["numero_factura"], "1")
        self.assertNotIn("stock", str(parametros).lower())

    def test_listar_facturas_exige_sesion_y_filtra_por_producto(self):
        manager = self.crear_manager()
        manager.supabase.rpc.return_value.execute.return_value = SimpleNamespace(
            data=[{"factura_id": "abc", "numero_factura": "1"}]
        )

        facturas = manager.listar_facturas_producto(7)

        self.assertEqual(facturas[0]["factura_id"], "abc")
        nombre_rpc, parametros = manager.supabase.rpc.call_args.args
        self.assertEqual(nombre_rpc, "listar_facturas_producto_app")
        self.assertEqual(parametros["p_producto_id"], "7")
        self.assertEqual(parametros["p_token"], "token-sesion")


class MigracionFacturasTests(unittest.TestCase):
    def test_migracion_documental_no_contiene_mutaciones_de_stock(self):
        ruta = Path(__file__).resolve().parents[1] / "database" / "migrations" / "017_facturas_documentales.sql"
        sql = ruta.read_text(encoding="utf-8").lower()

        self.assertNotIn("update public.productos", sql)
        self.assertNotIn("insert into public.transacciones", sql)
        self.assertIn("registrar_factura_compra_app", sql)


class RegistroFacturaDocumentalTests(unittest.TestCase):
    def test_revierte_archivo_si_la_base_rechaza_la_factura(self):
        almacen = Mock()
        almacen.guardar.return_value = "2026/10/factura.pdf"
        db = Mock()
        db.registrar_factura_compra.return_value = (False, "Factura duplicada", None)
        registro = RegistroFacturaDocumental(db, almacen)

        exito, mensaje, _ = registro.registrar(
            archivo_origen="origen.pdf",
            proveedor="Proveedor",
            numero_factura="10",
            fecha_factura="2026-10-15",
            observacion="",
            items=[{
                "producto": {"id": 7, "nombre": "Disco"},
                "cantidad": "2",
                "precio_unitario": "100",
            }],
        )

        self.assertFalse(exito)
        self.assertEqual(mensaje, "Factura duplicada")
        almacen.eliminar.assert_called_once_with("2026/10/factura.pdf")

    def test_registro_exitoso_conserva_archivo_y_no_invoca_operaciones_de_stock(self):
        almacen = Mock()
        almacen.guardar.return_value = "2026/10/factura.pdf"
        db = Mock()
        db.registrar_factura_compra.return_value = (
            True,
            "Factura registrada correctamente.",
            {"factura_id": "abc"},
        )
        registro = RegistroFacturaDocumental(db, almacen)

        exito, _, datos = registro.registrar(
            archivo_origen="factura.pdf",
            proveedor="Proveedor",
            numero_factura="10",
            fecha_factura="2026-10-15",
            observacion="",
            items=[{
                "producto": {"id": 7, "nombre": "Disco"},
                "cantidad": "2",
                "precio_unitario": "100",
            }],
        )

        self.assertTrue(exito)
        self.assertEqual(datos["factura_id"], "abc")
        almacen.eliminar.assert_not_called()
        self.assertEqual(
            [llamada[0] for llamada in db.method_calls],
            ["registrar_factura_compra"],
        )


if __name__ == "__main__":
    unittest.main()
