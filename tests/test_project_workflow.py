import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.test_logic import FakeTableSupabase, FakeSupabase, crear_manager
from views.tab_salidas import SalidasTab
from views.tab_pgp import PgpTab
from utils.ui_windows import dimensiones_ajustadas
from utils.searchable_combobox import SearchableCombobox


def selector_proyectos():
    combo = SearchableCombobox.__new__(SearchableCombobox)
    texto = [""]
    combo.entry = Mock()
    combo.entry.get.side_effect = lambda: texto[0]
    combo.entry.delete.side_effect = lambda *_: texto.__setitem__(0, "")
    combo.entry.insert.side_effect = lambda _, valor: texto.__setitem__(0, valor)
    combo.label_getter = str
    combo.search_getter = str
    combo.on_selected = None
    combo._popup = None
    combo._listbox = None
    combo.mostrar_lista = Mock()
    combo.set_items([])
    return combo


class ProyectoWorkflowTests(unittest.TestCase):
    def manager(self, estado="Activo", fecha_fin=None):
        manager = crear_manager(FakeTableSupabase({"proyectos": [{
            "estado": estado, "fecha_fin": fecha_fin,
            "fecha_inicio": "2026-01-01",
        }]}))
        manager._mutar = Mock(return_value=(True, "ok", {}))
        return manager

    @patch("database.db_manager.fecha_actual_bodega", return_value="2026-09-24")
    def test_finalizar_registra_fecha_real(self, _hoy):
        manager = self.manager()
        self.assertTrue(manager.actualizar_proyecto(1, {"estado": "Finalizado"})[0])
        self.assertEqual(manager._mutar.call_args.args[1]["fecha_fin"], "2026-09-24")

    def test_editar_finalizado_no_cambia_fecha(self):
        manager = self.manager("Finalizado", "2026-09-01")
        manager.actualizar_proyecto(1, {"estado": "Finalizado", "nombre": "Obra", "fecha_fin": "2099-01-01"})
        self.assertNotIn("fecha_fin", manager._mutar.call_args.args[1])

    def test_reactivar_limpia_fecha(self):
        manager = self.manager("Finalizado", "2026-09-01")
        manager.actualizar_proyecto(1, {"estado": "Activo"})
        self.assertIsNone(manager._mutar.call_args.args[1]["fecha_fin"])

    def test_nuevo_proyecto_sin_fecha_termino(self):
        manager = self.manager()
        manager.crear_proyecto("Obra", fecha_fin="2099-01-01")
        self.assertIsNone(manager._mutar.call_args.args[1]["fecha_fin"])

    def test_movimiento_sin_proyecto_no_llega_a_base(self):
        supabase = FakeSupabase()
        manager = crear_manager(supabase)
        exito, mensaje = manager.registrar_movimiento_camara("", "PRD1", "Entrega / Consumo", 1, 10)
        self.assertFalse(exito)
        self.assertIn("proyecto", mensaje)
        self.assertEqual(supabase.calls, [])

    def test_recarga_salidas_no_elige_primer_proyecto(self):
        combo = selector_proyectos()
        tab = SimpleNamespace(_carga_proyectos_id=1, combo_proyecto=combo)
        SalidasTab._actualizar_proyectos_ui(tab, ["Taller Interno", "Obra"], 1)
        self.assertEqual(combo.get(), "")
        self.assertIsNone(combo.get_selected())

    def test_movimiento_limpia_proyecto(self):
        tab = SimpleNamespace(combo_proyecto=Mock(), combo_producto=Mock(), combo_trabajador=Mock(), texto_comentario=Mock(), label_estado=Mock(), after=Mock())
        SalidasTab.limpiar_formulario(tab)
        tab.combo_proyecto.clear.assert_called_once_with()

    def test_recarga_pgp_no_selecciona_proyecto(self):
        combo = selector_proyectos()
        tab = SimpleNamespace(_carga_selectores_id=1, combo_proyecto=combo, combo_producto=Mock(), combo_trabajador=Mock(), label_estado_nuevo=Mock())
        PgpTab._actualizar_selectores(tab, [], [], ["Taller Interno", "Obra"], 1)
        self.assertEqual(combo.get(), "")
        self.assertIsNone(combo.get_selected())

    def test_proyectos_filtran_cada_tecla_y_enter_selecciona(self):
        combo = selector_proyectos()
        combo.set_items(["Taller Interno", "Obra Norte", "Obra Sur"])
        for texto, coincidencias in [
            ("o", ["Taller Interno", "Obra Norte", "Obra Sur"]),
            ("ob", ["Obra Norte", "Obra Sur"]),
            ("obra n", ["Obra Norte"]),
        ]:
            combo.set(texto)
            combo._on_key_release(SimpleNamespace(keysym=texto[-1]))
            self.assertEqual(combo._filtered_labels, coincidencias)
            self.assertIsNone(combo.get_selected())
        self.assertEqual(combo.entry.focus_set.call_count, 3)
        self.assertEqual(combo.mostrar_lista.call_count, 3)
        combo._on_return()
        self.assertEqual(combo.get_selected(), "Obra Norte")

    def test_texto_sin_coincidencias_no_es_proyecto_valido(self):
        combo = selector_proyectos()
        combo.set_items(["Obra Norte"])
        combo.set("Proyecto inexistente")
        combo._on_key_release()
        combo._on_return()
        self.assertIsNone(combo.get_selected())
        self.assertEqual(combo._filtered_labels, [])


class DimensionesVentanaTests(unittest.TestCase):
    def test_formulario_cabe_con_zoom_y_dpi_combinados(self):
        for pantalla in [(1024, 768), (1366, 728), (1920, 1040)]:
            for escala in [1, 1.4, 1.75, 2, 2.4]:
                with self.subTest(pantalla=pantalla, escala=escala):
                    ancho, alto = dimensiones_ajustadas(560, 760, escala, *pantalla)
                    self.assertLessEqual(ancho * escala, pantalla[0] - 40)
                    self.assertLessEqual(alto * escala, pantalla[1] - 80)


if __name__ == "__main__":
    unittest.main()
