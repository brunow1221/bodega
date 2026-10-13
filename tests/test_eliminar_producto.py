import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.test_logic import FakeTableSupabase, crear_manager
from views.tab_inventario import InventarioTab


class EliminarProductoTests(unittest.TestCase):
    def test_eliminar_solo_cambia_estado_y_audita(self):
        manager = crear_manager(None)
        manager._mutar = Mock(return_value=(True, "ok", {}))
        self.assertTrue(manager.dar_de_baja_producto(7)[0])
        operacion, datos = manager._mutar.call_args.args
        self.assertEqual(operacion, "actualizar_producto")
        self.assertEqual({k: v for k, v in datos.items() if not k.startswith('_')},
                         {"id": 7, "estado": "Inactivo"})

    def test_proyecto_conserva_cantidades_y_costo_de_producto_inactivo(self):
        manager = crear_manager(FakeTableSupabase({"transacciones": [{
            "producto_id": 7, "cantidad_movida": 3,
            "precio_unitario_movimiento": "1250.50",
            "producto_nombre_snapshot": "Disco de corte",
        }]}))
        manager.obtener_proyecto_por_nombre = lambda _: {"id": 1}
        manager.cargar_inventario_nube = lambda: [{
            "id": 7, "nombre": "Disco actual", "estado": "Inactivo",
            "precio_unitario": 9999,
        }]
        fila = manager.obtener_resumen_consumo_proyecto("Obra")[0]
        self.assertEqual(fila[0], "Disco de corte")
        self.assertEqual(fila[4], 3)
        self.assertEqual(fila[6], Decimal("3751.50"))

    def test_inactivos_visibles_para_restaurar_sin_filtro(self):
        tab = SimpleNamespace(
            db=SimpleNamespace(cargar_inventario_nube=lambda **_: [
                {"id": 1, "nombre": "Activo", "estado": "Activo"},
                {"id": 2, "nombre": "Eliminado", "estado": "Inactivo"},
            ]),
            producto_pertenece_a_vista=lambda _: True,
            decodificar_dimensiones=lambda _: {},
            actualizar_interfaz_tabla=Mock(),
        )
        with patch('views.tab_inventario.ejecutar_en_ui') as dispatch:
            InventarioTab.cargar_inventario_pesado(tab, "", 1)
            self.assertEqual([f['values'][0] for f in dispatch.call_args.args[2]], [1, 2])

    def test_restaurar_usa_columna_estado_correcta(self):
        tabla = Mock()
        tabla.selection.return_value = ["fila"]
        tabla.item.return_value = {"values": (7, "PRD7", "Disco", "Insumos", 3, 1, 100, "B1", "Inactivo")}
        tab = SimpleNamespace(tabla_inventario=tabla, db=Mock(), iniciar_carga_hilo=Mock(), notificar_cambio_selectores=Mock())
        tab.db.restaurar_producto_nube.return_value = (True, "ok")
        with patch('views.tab_inventario.messagebox.askyesno', return_value=True), patch('views.tab_inventario.messagebox.showinfo'):
            InventarioTab.restaurar_producto(tab)
        tab.db.restaurar_producto_nube.assert_called_once_with(7)


if __name__ == '__main__':
    unittest.main()
