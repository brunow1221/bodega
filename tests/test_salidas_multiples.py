import unittest
from unittest.mock import Mock, call, patch

from views.tab_salidas import SalidasTab


class SalidasMultiplesTests(unittest.TestCase):
    def setUp(self):
        self.pernos = {
            "id": "p1",
            "codigo_barras": "PER-1",
            "nombre": "Pernos",
            "categoria": "Materiales",
            "stock": 10,
        }
        self.guantes = {
            "id": "p2",
            "codigo_barras": "GUA-1",
            "nombre": "Guantes",
            "categoria": "EPP",
            "stock": 4,
        }

    def test_prepara_articulos_en_orden_y_sin_repetidos(self):
        resultado = SalidasTab.preparar_lista_productos_entrega(
            [self.pernos, self.guantes],
            self.pernos,
        )

        self.assertEqual(resultado, [self.pernos, self.guantes])

    def test_pregunta_cantidad_de_cada_articulo_en_orden(self):
        respuestas = iter(["3", "2"])
        titulos = []

        class DialogoFalso:
            def __init__(self, *, title, text):
                titulos.append(title)

            def get_input(self):
                return next(respuestas)

        tab = SalidasTab.__new__(SalidasTab)
        with patch("views.tab_salidas.ctk.CTkInputDialog", DialogoFalso):
            cantidades = tab.solicitar_cantidades_entrega(
                [self.pernos, self.guantes]
            )

        self.assertEqual(cantidades, [3, 2])
        self.assertEqual(titulos, ["Cantidad 1 de 2", "Cantidad 2 de 2"])

    def test_registra_todos_los_articulos_con_la_misma_entrega(self):
        tab = SalidasTab.__new__(SalidasTab)
        tab.productos_entrega = [self.pernos, self.guantes]
        tab.db = Mock()
        tab.db.buscar_producto_por_codigo.side_effect = lambda codigo: {
            "PER-1": self.pernos,
            "GUA-1": self.guantes,
        }[codigo]
        tab.db.registrar_movimiento_camara.return_value = (True, "OK")
        tab.solicitar_cantidades_entrega = Mock(return_value=[3, 2])
        tab.on_epp_registrado = Mock()
        tab.cargar_ultimos_movimientos = Mock()
        tab.limpiar_formulario = Mock()
        tab.iniciar_carga_selectores = Mock()
        trabajador = {"rut": "1-9", "nombre": "Ana"}

        with patch("views.tab_salidas.messagebox.showinfo"):
            tab.registrar_entrega_multiple(
                None,
                trabajador,
                "Obra Norte",
                "Entrega semanal",
            )

        self.assertEqual(
            tab.db.registrar_movimiento_camara.call_args_list,
            [
                call(
                    "1-9", "PER-1", SalidasTab.TIPO_ENTREGA,
                    "p1", 10, 3, "Obra Norte", "Entrega semanal",
                ),
                call(
                    "1-9", "GUA-1", SalidasTab.TIPO_ENTREGA,
                    "p2", 4, 2, "Obra Norte", "Entrega semanal",
                ),
            ],
        )
        tab.on_epp_registrado.assert_called_once_with()
        tab.limpiar_formulario.assert_called_once_with()

    def test_un_fallo_deja_en_la_lista_solo_los_articulos_pendientes(self):
        tab = SalidasTab.__new__(SalidasTab)
        tab.productos_entrega = [self.pernos, self.guantes]
        tab.db = Mock()
        tab.db.buscar_producto_por_codigo.side_effect = lambda codigo: {
            "PER-1": self.pernos,
            "GUA-1": self.guantes,
        }[codigo]
        tab.db.registrar_movimiento_camara.side_effect = [
            (True, "OK"),
            (False, "Stock insuficiente"),
        ]
        tab.solicitar_cantidades_entrega = Mock(return_value=[3, 2])
        tab.on_epp_registrado = Mock()
        tab.actualizar_tabla_productos_entrega = Mock()
        tab.cargar_ultimos_movimientos = Mock()
        tab.iniciar_carga_selectores = Mock()

        with patch("views.tab_salidas.messagebox.showerror") as mostrar_error:
            tab.registrar_entrega_multiple(
                None,
                {"rut": "1-9", "nombre": "Ana"},
                "Obra Norte",
                "",
            )

        self.assertEqual(tab.productos_entrega, [self.guantes])
        mostrar_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
