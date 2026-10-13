import unittest

from tests.test_logic import FakeTableSupabase, crear_manager
from utils.estadisticas import tipo_uso_canonico
from utils.movimientos import (
    TIPO_ENTREGA_HERRAMIENTA_PERSONAL,
    validar_entrega_herramienta_personal,
)
from views.tab_herramientas_personales import HerramientasPersonalesTab


class HerramientasPersonalesTests(unittest.TestCase):
    def setUp(self):
        self.movimientos = [
            {
                "id": 1,
                "producto_id": "h1",
                "trabajador_id": "t1",
                "proyecto_id": "p1",
                "tipo_movimiento": TIPO_ENTREGA_HERRAMIENTA_PERSONAL,
                "cantidad_movida": 2,
                "fecha_hora": "2026-09-24T12:00:00",
                "producto_nombre_snapshot": "Taladro histórico",
                "creado_por_usuario": "Bodega",
                "comentario": "Asignación personal",
            },
            {
                "id": 2,
                "producto_id": "h1",
                "trabajador_id": "t1",
                "proyecto_id": "p1",
                "tipo_movimiento": "Préstamo de Herramienta",
                "cantidad_movida": 1,
            },
        ]

    def crear_manager(self):
        manager = crear_manager(
            FakeTableSupabase({"transacciones": self.movimientos})
        )
        manager.cargar_inventario_nube = lambda: [
            {"id": "h1", "nombre": "Taladro", "categoria": "Herramientas"}
        ]
        manager.cargar_trabajadores_nube = lambda solo_activos=False: [
            {"id": "t1", "nombre": "Ana", "rut": "12.345.678-5"}
        ]
        manager.cargar_proyectos_completo = lambda: [
            {"id": "p1", "nombre": "Proyecto Norte"}
        ]
        return manager

    def test_registro_solo_incluye_entregas_personales(self):
        resultado = self.crear_manager().obtener_registro_herramientas_personales()
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["herramienta"], "Taladro histórico")
        self.assertEqual(resultado[0]["trabajador"], "Ana")
        self.assertEqual(resultado[0]["cantidad"], 2)

    def test_filtros_por_trabajador_herramienta_y_texto(self):
        entregas = self.crear_manager().obtener_registro_herramientas_personales()
        resultado = HerramientasPersonalesTab.filtrar_entregas(
            entregas,
            texto="asignacion taladro",
            trabajador="Ana",
            epp="Taladro histórico",
            proyecto="Proyecto Norte",
        )
        self.assertEqual(len(resultado), 1)

    def test_entrega_personal_exige_trabajador_y_categoria_herramientas(self):
        herramienta = {"categoria": "Herramientas"}
        self.assertIn(
            "trabajador",
            validar_entrega_herramienta_personal(
                TIPO_ENTREGA_HERRAMIENTA_PERSONAL, herramienta, None
            ),
        )
        self.assertIn(
            "Herramientas",
            validar_entrega_herramienta_personal(
                TIPO_ENTREGA_HERRAMIENTA_PERSONAL,
                {"categoria": "EPP"},
                {"id": 1},
            ),
        )
        self.assertEqual(
            validar_entrega_herramienta_personal(
                TIPO_ENTREGA_HERRAMIENTA_PERSONAL,
                herramienta,
                {"id": 1},
            ),
            "",
        )

    def test_estadisticas_la_reconocen_como_uso_distinto(self):
        self.assertEqual(
            tipo_uso_canonico(TIPO_ENTREGA_HERRAMIENTA_PERSONAL),
            TIPO_ENTREGA_HERRAMIENTA_PERSONAL,
        )


if __name__ == "__main__":
    unittest.main()
