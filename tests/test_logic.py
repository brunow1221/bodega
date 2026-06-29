import unittest

from database.db_manager import DatabaseManager
from views.tab_mapa_bodega import MapaBodegaTab
from views.tab_salidas import SalidasTab
from views.tab_trabajadores import validar_rut_chileno


class FakeResponse:
    def __init__(self, data=None):
        self.data = data


class FakeRpcRequest:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class FakeSupabase:
    def __init__(self, rpc_data=None):
        self.rpc_data = rpc_data
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return FakeRpcRequest(FakeResponse(self.rpc_data))


class FlakyRpcRequest:
    def __init__(self, owner):
        self.owner = owner

    def execute(self):
        if self.owner.attempts == 1:
            raise RuntimeError("Server disconnected")
        return FakeResponse({"ok": True})


class FlakySupabase:
    def __init__(self):
        self.attempts = 0
        self.request_ids = []

    def rpc(self, name, params):
        self.attempts += 1
        self.request_ids.append(params.get("p_request_id"))
        return FlakyRpcRequest(self)


class FakeQuery:
    def __init__(self, data):
        self.data = data

    def select(self, *args, **kwargs):
        return self

    def in_(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        return FakeResponse(self.data)


class FakeTableSupabase:
    def __init__(self, table_data):
        self.table_data = table_data

    def table(self, name):
        return FakeQuery(self.table_data[name])


def crear_manager(supabase, token="token-prueba"):
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.supabase = supabase
    manager.session_token = token
    manager.usuario_actual = {
        "usuario": "admin",
        "nombre": "Administrador",
        "rol": "Administrador"
    }
    manager.migracion_seguridad_disponible = bool(token)
    return manager


class ValidacionRutTests(unittest.TestCase):
    def test_rut_valido(self):
        self.assertTrue(validar_rut_chileno("12.345.678-5"))

    def test_rut_invalido(self):
        self.assertFalse(validar_rut_chileno("12.345.678-9"))


class RackValidationTests(unittest.TestCase):
    def setUp(self):
        self.tab = MapaBodegaTab.__new__(MapaBodegaTab)

    def test_decimal_opcional(self):
        self.assertEqual(
            self.tab.leer_decimal_opcional("200,5", "ancho"),
            200.5
        )
        self.assertIsNone(self.tab.leer_decimal_opcional("", "ancho"))

    def test_dimension_no_positiva(self):
        with self.assertRaises(ValueError):
            self.tab.leer_decimal_opcional("0", "alto")


class RetazoTests(unittest.TestCase):
    def setUp(self):
        self.tab = SalidasTab.__new__(SalidasTab)

    def test_calculo_por_largo(self):
        producto = {
            "precio_unitario": 30000,
            "tipo_medicion": "Largo",
            "medida_largo": 6,
            "medida_ancho": None
        }
        precio, porcentaje = self.tab.calcular_precio_retazo(
            producto,
            cantidad_cortada=1,
            largo_retazo=1.5
        )
        self.assertEqual(precio, 7500)
        self.assertEqual(porcentaje, 25.0)

    def test_retazo_no_puede_superar_material(self):
        producto = {
            "precio_unitario": 30000,
            "tipo_medicion": "Largo",
            "medida_largo": 6,
            "medida_ancho": None
        }
        with self.assertRaises(ValueError):
            self.tab.calcular_precio_retazo(
                producto,
                cantidad_cortada=1,
                largo_retazo=7
            )


class DatabaseManagerTests(unittest.TestCase):
    def test_mutacion_bloqueada_sin_sesion(self):
        manager = crear_manager(FakeSupabase(), token=None)
        exito, mensaje, respuesta = manager._mutar("crear_producto", {})
        self.assertFalse(exito)
        self.assertIsNone(respuesta)
        self.assertIn("migración", mensaje.lower())

    def test_movimiento_usa_rpc_atomica(self):
        supabase = FakeSupabase({"ok": True, "stock_nuevo": 4})
        manager = crear_manager(supabase)
        exito, _ = manager.registrar_movimiento_camara(
            "12345678-5",
            "PRD1",
            "Entrega / Consumo",
            "producto-1",
            999,
            2,
            "Taller Interno"
        )
        self.assertTrue(exito)
        self.assertEqual(supabase.calls[0][0], "registrar_movimiento_app")
        self.assertEqual(supabase.calls[0][1]["p_cantidad"], 2)
        self.assertNotIn("stock_actual", supabase.calls[0][1])

    def test_movimiento_rechaza_cantidad_no_positiva(self):
        manager = crear_manager(FakeSupabase())
        exito, mensaje = manager.registrar_movimiento_camara(
            "",
            "PRD1",
            "Entrada / Reposición",
            "producto-1",
            0,
            0,
            "Taller Interno"
        )
        self.assertFalse(exito)
        self.assertIn("mayor a cero", mensaje)

    def test_reintento_conserva_request_id(self):
        supabase = FlakySupabase()
        manager = crear_manager(supabase)
        exito, _, _ = manager._mutar("crear_producto", {"nombre": "Prueba"})
        self.assertTrue(exito)
        self.assertEqual(supabase.attempts, 2)
        self.assertEqual(supabase.request_ids[0], supabase.request_ids[1])

    def test_gestionar_rack_usa_rpc_segura(self):
        supabase = FakeSupabase({"ok": True, "id": 8})
        manager = crear_manager(supabase)
        exito, _ = manager.gestionar_rack(
            "crear",
            {
                "bodega_id": 1,
                "codigo_rack": "R08",
                "niveles": 4,
                "columnas": 5
            }
        )
        self.assertTrue(exito)
        nombre, parametros = supabase.calls[0]
        self.assertEqual(nombre, "gestionar_rack_app")
        self.assertEqual(parametros["p_accion"], "crear")
        self.assertEqual(parametros["p_datos"]["columnas"], 5)
        self.assertTrue(parametros["p_request_id"])

    def test_herramientas_mantiene_cantidad_pendiente(self):
        movimientos = [
            {
                "producto_id": "p1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Préstamo de Herramienta",
                "cantidad_movida": 3,
                "fecha_hora": "2026-01-01T10:00:00"
            },
            {
                "producto_id": "p1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Devolución de Herramienta",
                "cantidad_movida": 1,
                "fecha_hora": "2026-01-02T10:00:00"
            }
        ]
        manager = crear_manager(
            FakeTableSupabase({"transacciones": movimientos})
        )
        manager.cargar_inventario_nube = lambda: [
            {"id": "p1", "nombre": "Taladro"}
        ]
        manager.cargar_trabajadores_nube = lambda solo_activos=False: [
            {"id": "t1", "nombre": "Ana"}
        ]
        manager.cargar_proyectos_completo = lambda: [
            {"id": "pr1", "nombre": "Proyecto A"}
        ]

        resultado = manager.obtener_herramientas_en_terreno()
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["nombre_producto"], "Taladro")
        self.assertEqual(resultado[0]["cantidad_pendiente"], 2)
        self.assertEqual(resultado[0]["nombre_proyecto"], "Proyecto A")


if __name__ == "__main__":
    unittest.main()
