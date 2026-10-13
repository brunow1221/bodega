import unittest

from database.db_manager import DatabaseManager
from tests.test_logic import FakeTableSupabase, crear_manager
from utils.estadisticas import (
    TODOS,
    calcular_estadisticas,
    calcular_historial_articulo,
    calcular_historial_precios,
    tipo_uso_canonico,
)


class CalculoEstadisticasTests(unittest.TestCase):
    def setUp(self):
        self.movimientos = [
            {
                "producto_id": "p1",
                "producto": "Guantes",
                "proyecto": "Proyecto A",
                "tipo_movimiento": "Entrega / Consumo",
                "cantidad_movida": 2,
                "precio_unitario": "100.50",
                "fecha_hora": "2026-08-31T12:45:00Z",
            },
            {
                "producto_id": "p1",
                "producto": "Guantes",
                "proyecto": "Proyecto B",
                "tipo_movimiento": "Prestamo de Herramienta",
                "cantidad_movida": 3,
                "precio_unitario": 100,
                "fecha_hora": "2026-09-01T12:00:00Z",
            },
            {
                "producto_id": "p2",
                "producto": "Disco de corte",
                "proyecto": "Proyecto A",
                "tipo_movimiento": "Baja por Daño / Merma",
                "cantidad_movida": 1,
                "precio_unitario": 250,
                "fecha_hora": "2026-09-02T12:00:00Z",
            },
            {
                "producto_id": "p3",
                "producto": "Taladro",
                "proyecto": "Proyecto A",
                "tipo_movimiento": "Devolución de Herramienta",
                "cantidad_movida": 20,
                "fecha_hora": "2026-09-02T13:00:00Z",
            },
            {
                "producto_id": "p1",
                "producto": "Guantes",
                "proyecto": "Proyecto B",
                "tipo_movimiento": "Devolución de Herramienta",
                "cantidad_movida": 1,
                "fecha_hora": "2026-09-03T12:00:00Z",
                "trabajador": "Ana Soto",
                "registrado_por": "Bruno",
                "stock_anterior": 4,
                "stock_nuevo": 5,
            },
            {
                "producto_id": "p4",
                "producto": "Resma",
                "proyecto": "Proyecto A",
                "tipo_movimiento": "Entrada / Reposición",
                "cantidad_movida": 50,
                "fecha_hora": "2026-09-02T14:00:00Z",
            },
        ]

    def test_reconoce_variantes_sin_tilde(self):
        self.assertEqual(
            tipo_uso_canonico("Prestamo de Herramienta"),
            "Préstamo de Herramienta",
        )

    def test_ranking_excluye_entradas_y_devoluciones(self):
        resultado = calcular_estadisticas(self.movimientos)
        self.assertEqual(resultado["cantidad_total"], 6)
        self.assertEqual(resultado["total_movimientos"], 3)
        self.assertEqual(resultado["productos_distintos"], 2)
        self.assertEqual(resultado["proyectos_distintos"], 2)
        self.assertEqual(resultado["productos"][0], {"etiqueta": "Guantes", "cantidad": 5})
        self.assertEqual(resultado["proyectos"][0], {"etiqueta": "Proyecto A", "cantidad": 3})
        self.assertEqual(
            resultado["tendencia"],
            [
                {"etiqueta": "ago 2026", "cantidad": 2},
                {"etiqueta": "sept 2026", "cantidad": 4},
            ],
        )

    def test_filtra_proyecto_tipo_y_fecha_local(self):
        resultado = calcular_estadisticas(
            self.movimientos,
            proyecto="Proyecto A",
            tipo_movimiento="Entrega / Consumo",
            desde="2026-08-31",
            hasta="2026-08-31",
        )
        self.assertEqual(resultado["cantidad_total"], 2)
        self.assertEqual(resultado["productos"][0]["etiqueta"], "Guantes")

    def test_fecha_utc_se_filtra_por_el_dia_chileno(self):
        movimientos = [{
            "producto_id": "p1",
            "producto": "Guantes",
            "proyecto": "Proyecto A",
            "tipo_movimiento": "Entrega / Consumo",
            "cantidad_movida": 1,
            "fecha_hora": "2026-09-01T02:00:00Z",
        }]
        self.assertEqual(
            calcular_estadisticas(movimientos, desde="2026-08-31", hasta="2026-08-31")["cantidad_total"],
            1,
        )
        self.assertEqual(
            calcular_estadisticas(movimientos, desde="2026-09-01")["cantidad_total"],
            0,
        )

    def test_valida_fechas_y_limita_ranking(self):
        with self.assertRaises(ValueError):
            calcular_estadisticas(self.movimientos, desde="2026-09-03", hasta="2026-09-01")
        self.assertEqual(len(calcular_estadisticas(self.movimientos, limite=3)["productos"]), 2)
        self.assertEqual(calcular_estadisticas([], proyecto=TODOS)["productos"], [])

    def test_historial_articulo_informa_cantidades_persona_y_fecha(self):
        resultado = calcular_historial_articulo(self.movimientos, "p1")
        self.assertEqual(resultado["movimientos"], 3)
        self.assertEqual(resultado["total_retirado"], 5)
        self.assertEqual(resultado["total_devuelto"], 1)
        self.assertEqual(resultado["saldo_movimientos"], -4)
        self.assertEqual(resultado["filas"][0]["trabajador"], "Ana Soto")
        self.assertEqual(resultado["filas"][0]["fecha_texto"], "03/09/2026 08:00")
        self.assertEqual(resultado["filas"][0]["stock_nuevo"], 5)

    def test_historial_articulo_reconoce_devolucion_pgp(self):
        movimientos = [{
            "producto_id": "p1",
            "tipo_movimiento": "Devolución PGP",
            "cantidad_movida": 2,
            "fecha_hora": "2026-09-03T12:00:00Z",
        }]
        resultado = calcular_historial_articulo(movimientos, "p1")
        self.assertEqual(resultado["total_devuelto"], 2)
        self.assertEqual(resultado["saldo_movimientos"], 2)

    def test_historial_articulo_admite_filtros(self):
        resultado = calcular_historial_articulo(
            self.movimientos,
            "p1",
            proyecto="Proyecto A",
            tipo_movimiento="Entrega / Consumo",
            desde="2026-08-31",
            hasta="2026-08-31",
        )
        self.assertEqual(resultado["movimientos"], 1)
        self.assertEqual(resultado["total_retirado"], 2)


class DatosEstadisticasTests(unittest.TestCase):
    def test_enriquece_movimientos_con_producto_proyecto_y_precio(self):
        movimiento = {
            "producto_id": "p1",
            "proyecto_id": "pr1",
            "trabajador_id": "t1",
            "tipo_movimiento": "Entrega / Consumo",
            "cantidad_movida": 2,
            "fecha_hora": "2026-09-01T12:00:00Z",
            "precio_unitario_movimiento": None,
            "producto_nombre_snapshot": "Nombre histórico",
        }
        manager = crear_manager(FakeTableSupabase({"transacciones": [movimiento]}))
        manager.cargar_inventario_nube = lambda: [
            {"id": "p1", "nombre": "Nombre actual", "precio_unitario": "500"}
        ]
        manager.cargar_proyectos_completo = lambda: [
            {"id": "pr1", "nombre": "Proyecto Norte"}
        ]
        manager.cargar_trabajadores_nube = lambda solo_activos=False: [
            {"id": "t1", "nombre": "Ana Soto"}
        ]

        resultado = DatabaseManager.obtener_movimientos_estadisticas(manager)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["producto"], "Nombre histórico")
        self.assertEqual(resultado[0]["proyecto"], "Proyecto Norte")
        self.assertEqual(resultado[0]["trabajador"], "Ana Soto")
        self.assertEqual(resultado[0]["precio_unitario"], "500")

    def test_obtiene_historial_precios(self):
        cambio = {
            "id": 1,
            "producto_id": 8,
            "producto_nombre": "Guantes",
            "precio_anterior": "1000",
            "precio_nuevo": "1200",
            "fecha_hora": "2026-09-03T12:00:00Z",
            "usuario_app": "Bruno",
        }
        manager = crear_manager(
            FakeTableSupabase({"historial_precios": [cambio]})
        )
        resultado = manager.obtener_historial_precios()
        self.assertTrue(resultado["disponible"])
        self.assertEqual(resultado["filas"], [cambio])


class HistorialPreciosTests(unittest.TestCase):
    def setUp(self):
        self.cambios = [
            {
                "producto_id": 1,
                "producto_nombre": "Guantes",
                "precio_anterior": "1000",
                "precio_nuevo": "1250",
                "fecha_hora": "2026-09-03T12:45:00Z",
                "usuario_app": "Bruno",
            },
            {
                "producto_id": 1,
                "producto_nombre": "Guantes",
                "precio_anterior": "1250",
                "precio_nuevo": "1100",
                "fecha_hora": "2026-09-04T12:45:00Z",
                "usuario_app": "Bodega",
            },
            {
                "producto_id": 2,
                "producto_nombre": "Casco",
                "precio_anterior": "0",
                "precio_nuevo": "5000",
                "fecha_hora": "2026-09-05T12:45:00Z",
                "usuario_app": "Bruno",
            },
        ]

    def test_resume_cambios_y_porcentaje(self):
        resultado = calcular_historial_precios(self.cambios)
        self.assertEqual(resultado["productos"], 2)
        self.assertEqual(resultado["cambios"], 3)
        self.assertEqual(resultado["aumentos"], 2)
        self.assertEqual(resultado["disminuciones"], 1)
        self.assertIsNone(resultado["filas"][0]["porcentaje"])
        self.assertEqual(resultado["filas"][1]["porcentaje"], -12)

    def test_filtra_articulo_direccion_y_fecha(self):
        resultado = calcular_historial_precios(
            self.cambios,
            producto_clave=1,
            direccion="Aumentos",
            desde="2026-09-03",
            hasta="2026-09-03",
        )
        self.assertEqual(resultado["cambios"], 1)
        self.assertEqual(resultado["filas"][0]["precio_nuevo"], 1250)
        self.assertEqual(resultado["filas"][0]["fecha_texto"], "03/09/2026 08:45")


if __name__ == "__main__":
    unittest.main()
