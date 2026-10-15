import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from main import AplicacionBodega
from utils.ui_theme import configurar_treeview_global
from utils.ui_windows import dimensiones_ventana_principal
from utils.ui_zoom import (
    cargar_tema,
    cargar_zoom,
    guardar_tema,
    guardar_zoom,
    normalizar_tema,
)
from views.tab_terreno import TerrenoTab


class EstiloGrabado:
    def __init__(self):
        self.configuraciones = {}
        self.mapas = {}

    def theme_use(self, nombre):
        self.tema = nombre

    def configure(self, nombre, **opciones):
        self.configuraciones[nombre] = opciones

    def map(self, nombre, **opciones):
        self.mapas[nombre] = opciones


class PreferenciasInterfazTests(unittest.TestCase):
    def test_normaliza_nombres_de_tema(self):
        self.assertEqual(normalizar_tema("oscuro"), "Dark")
        self.assertEqual(normalizar_tema("Light"), "Light")
        self.assertEqual(normalizar_tema("desconocido"), "Light")

    def test_tema_y_zoom_se_guardan_sin_borrarse(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "preferencias.json"
            with patch(
                "utils.ui_zoom.obtener_ruta_preferencias",
                return_value=ruta,
            ):
                self.assertTrue(guardar_zoom(120))
                self.assertTrue(guardar_tema("Dark"))
                self.assertEqual(cargar_zoom(), 120)
                self.assertEqual(cargar_tema(), "Dark")
                datos = json.loads(ruta.read_text(encoding="utf-8"))

        self.assertEqual(datos, {"zoom": 120, "tema": "Dark"})

    def test_boton_alterna_y_guarda_tema(self):
        aplicacion = SimpleNamespace(
            tema_actual="Light",
            configurar_estilo_tablas=lambda: None,
            actualizar_treeviews=lambda _widget: None,
        )
        with (
            patch("main.ctk.set_appearance_mode") as aplicar,
            patch("main.guardar_tema") as guardar,
        ):
            AplicacionBodega.alternar_tema(aplicacion)

        self.assertEqual(aplicacion.tema_actual, "Dark")
        aplicar.assert_called_once_with("Dark")
        guardar.assert_called_once_with("Dark")


class ResolucionInterfazTests(unittest.TestCase):
    def test_ventana_principal_no_supera_area_disponible(self):
        for area in ((800, 600), (1024, 728), (1366, 728), (1920, 1040)):
            for escala in (1.0, 1.25, 1.5):
                with self.subTest(area=area, escala=escala):
                    ancho, alto, minimo_ancho, minimo_alto = (
                        dimensiones_ventana_principal(*area, escala)
                    )
                    self.assertLessEqual(ancho * escala, area[0] - 40)
                    self.assertLessEqual(alto * escala, area[1] - 80)
                    self.assertLessEqual(minimo_ancho, ancho)
                    self.assertLessEqual(minimo_alto, alto)

    def test_treeview_oscuro_no_conserva_contorno_claro(self):
        estilo = EstiloGrabado()
        with patch("utils.ui_theme.ctk.get_appearance_mode", return_value="Dark"):
            configurar_treeview_global(estilo)

        tabla = estilo.configuraciones["Treeview"]
        self.assertEqual(tabla["bordercolor"], "#475569")
        self.assertEqual(tabla["lightcolor"], "#475569")
        self.assertEqual(tabla["darkcolor"], "#475569")

    def test_encabezado_terreno_calcula_espacio_para_ambos_textos(self):
        titulo = SimpleNamespace(configure=lambda **opciones: setattr(titulo, "opciones", opciones))
        estado = SimpleNamespace(configure=lambda **opciones: setattr(estado, "opciones", opciones))
        boton = SimpleNamespace(winfo_reqwidth=lambda: 180)
        tab = SimpleNamespace(
            titulo_terreno=titulo,
            label_estado=estado,
            boton_refrescar=boton,
        )

        TerrenoTab._ajustar_textos_encabezado(tab, SimpleNamespace(width=600))

        self.assertEqual(titulo.opciones["wraplength"], 568)
        self.assertEqual(estado.opciones["wraplength"], 368)


if __name__ == "__main__":
    unittest.main()
