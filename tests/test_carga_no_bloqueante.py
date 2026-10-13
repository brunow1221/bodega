import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from queue import Queue

from views.tab_salidas import SalidasTab
from views.tab_consumo_proyecto import ConsumoProyectoTab


class CargaNoBloqueanteTests(unittest.TestCase):
    def test_consultas_lentas_no_bloquean_y_resultados_se_encolan(self):
        for clase, iniciar, pesado, actualizar, contador, consulta, resultado in (
            (SalidasTab, 'cargar_proyectos', '_cargar_proyectos_pesado', '_actualizar_proyectos_ui', '_carga_proyectos_id', 'cargar_proyectos', ['Obra']),
            (SalidasTab, 'cargar_ultimos_movimientos', '_cargar_ultimos_pesado', '_actualizar_ultimos_ui', '_carga_ultimos_id', 'obtener_ultimos_movimientos', [('fecha', 'producto')]),
            (ConsumoProyectoTab, 'cargar_proyectos', '_cargar_proyectos_pesado', '_actualizar_proyectos_ui', '_carga_proyectos_id', 'cargar_proyectos', ['Obra']),
        ):
            with self.subTest(vista=clase.__name__, consulta=consulta):
                empezo = threading.Event()
                liberar = threading.Event()
                db = Mock()
                def consulta_lenta(*_):
                    self.assertIsNot(threading.current_thread(), threading.main_thread())
                    empezo.set()
                    liberar.wait(2)
                    return resultado
                getattr(db, consulta).side_effect = consulta_lenta
                tab = SimpleNamespace(db=db, _cola_tareas_ui=Queue(), label_estado=Mock())
                setattr(tab, contador, 0)
                setattr(tab, actualizar, Mock())
                setattr(tab, pesado, lambda carga_id: getattr(clase, pesado)(tab, carga_id))
                try:
                    getattr(clase, iniciar)(tab)
                    self.assertTrue(empezo.wait(1))
                    getattr(tab, actualizar).assert_not_called()
                    self.assertTrue(tab._cola_tareas_ui.empty())
                finally:
                    liberar.set()
                callback, args, kwargs = tab._cola_tareas_ui.get(timeout=2)
                self.assertEqual(args, (resultado, 1))
                callback(*args, **kwargs)
                getattr(tab, actualizar).assert_called_once_with(resultado, 1)

    def test_descarta_historial_de_carga_antigua(self):
        tab = SimpleNamespace(_carga_ultimos_id=2, tabla_ultimos=Mock())
        SalidasTab._actualizar_ultimos_ui(tab, [('viejo',)], 1)
        tab.tabla_ultimos.get_children.assert_not_called()

    def test_error_historial_se_encola_sin_tocar_widgets(self):
        tab = SimpleNamespace(db=Mock(), _actualizar_ultimos_ui=Mock(), _cola_tareas_ui=Queue())
        tab.db.obtener_ultimos_movimientos.side_effect = RuntimeError('Conexion interrumpida')
        with patch('builtins.print'):
            SalidasTab._cargar_ultimos_pesado(tab, 1)
        tab._actualizar_ultimos_ui.assert_not_called()
        _, args, _ = tab._cola_tareas_ui.get_nowait()
        self.assertEqual(args, (None, 1))
