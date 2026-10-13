import unittest
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.test_logic import crear_manager
from views.tab_inventario import InventarioTab


class CargaInventarioTests(unittest.TestCase):
    def crear_tab(self):
        tab = SimpleNamespace(
            db=Mock(), label_estado=Mock(), tabla_inventario=Mock(),
            entry_busqueda=Mock(), after=Mock(), _cola_tareas_ui=Queue(),
            _carga_inventario_id=0, _cargando_inventario=False,
            _recarga_pendiente=False,
            producto_pertenece_a_vista=lambda _: True,
            decodificar_dimensiones=lambda _: {},
        )
        tab.entry_busqueda.get.return_value = ""
        tab.tabla_inventario.get_children.return_value = []
        for nombre in (
            'iniciar_carga_hilo', 'cargar_inventario_pesado',
            'actualizar_interfaz_tabla', '_mostrar_error_carga', '_avisar_carga_lenta',
        ):
            setattr(tab, nombre, getattr(InventarioTab, nombre).__get__(tab))
        return tab

    def test_no_duplica_hilos_ni_borra_datos_mientras_carga(self):
        tab = self.crear_tab()
        with patch('views.tab_inventario.threading.Thread') as hilo:
            tab.iniciar_carga_hilo()
            tab.iniciar_carga_hilo()
            tab.iniciar_carga_hilo()
        self.assertEqual(hilo.call_count, 1)
        tab.tabla_inventario.delete.assert_not_called()
        self.assertTrue(tab._recarga_pendiente)

    def test_error_en_hilo_se_encola_y_permite_reintentar(self):
        tab = self.crear_tab()
        tab._cargando_inventario = True
        tab.db.cargar_inventario_nube.side_effect = RuntimeError('Sin conexión')
        tab.cargar_inventario_pesado('', 0)
        tab.label_estado.configure.assert_not_called()
        callback, args, kwargs = tab._cola_tareas_ui.get_nowait()
        with patch('builtins.print'):
            callback(*args, **kwargs)
        self.assertFalse(tab._cargando_inventario)
        self.assertIn('Error al cargar', tab.label_estado.configure.call_args.kwargs['text'])
        tab.tabla_inventario.delete.assert_not_called()

    def test_resultado_y_error_antiguos_no_afectan_carga_actual(self):
        tab = self.crear_tab()
        tab._carga_inventario_id = 2
        tab._cargando_inventario = True
        tab.actualizar_interfaz_tabla([], 1)
        tab._mostrar_error_carga('anterior', 1)
        tab._avisar_carga_lenta(1)
        tab.label_estado.configure.assert_not_called()
        self.assertTrue(tab._cargando_inventario)

    def test_exito_procesa_una_recarga_pendiente_con_busqueda_actual(self):
        tab = self.crear_tab()
        tab._recarga_pendiente = True
        tab._cargando_inventario = True
        tab.entry_busqueda.get.return_value = 'tuercas'
        with patch('views.tab_inventario.threading.Thread') as hilo:
            tab.actualizar_interfaz_tabla([], 0)
        self.assertEqual(hilo.call_count, 1)
        self.assertEqual(hilo.call_args.kwargs['args'], ('tuercas', 1))
        self.assertFalse(tab._recarga_pendiente)

    def test_error_renderizado_sale_de_cargando(self):
        tab = self.crear_tab()
        tab._cargando_inventario = True
        tab.tabla_inventario.insert.side_effect = RuntimeError('Error tabla')
        with patch('builtins.print'):
            tab.actualizar_interfaz_tabla([{'values': (1,), 'tags': ()}], 0)
        self.assertFalse(tab._cargando_inventario)

    def test_aviso_lento_no_se_muestra_despues_de_terminar(self):
        tab = self.crear_tab()
        tab._cargando_inventario = True
        tab._avisar_carga_lenta(0)
        self.assertIn('conexión tarda', tab.label_estado.configure.call_args.kwargs['text'])
        tab.actualizar_interfaz_tabla([], 0)
        tab._avisar_carga_lenta(0)
        self.assertEqual(tab.label_estado.configure.call_args.kwargs['text'], '0 prod.')

    def test_error_bd_se_propaga_solo_si_se_solicita(self):
        db = crear_manager(None)
        db._ejecutar_con_reintentos = Mock(side_effect=RuntimeError('Sin conexión'))
        with patch('builtins.print'):
            self.assertEqual(db.cargar_inventario_nube(), [])
            with self.assertRaises(RuntimeError):
                db.cargar_inventario_nube(propagar_error=True)

    def test_no_existe_accion_eliminar_en_inventario(self):
        self.assertFalse(hasattr(InventarioTab, 'dar_de_baja'))


if __name__ == '__main__':
    unittest.main()
