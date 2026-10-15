import sys
import unittest
from unittest.mock import patch

import customtkinter as ctk

from views.tab_estadisticas import EstadisticasTab
from views.tab_historial import HistorialTab
from views.tab_inventario import InventarioTab
from views.tab_mapa_bodega import MapaBodegaTab
from views.tab_pgp import PgpTab
from views.tab_trabajadores import TrabajadoresTab


class BaseDatosVacia:
    def __getattr__(self, _nombre):
        return lambda *args, **kwargs: []


@unittest.skipUnless(sys.platform == "win32", "La auditoría usa geometría Tk de Windows")
class DistribucionVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctk.set_appearance_mode("Dark")
        ctk.set_widget_scaling(1.5)
        ctk.set_window_scaling(1.5)
        cls.parche_hilos = patch("threading.Thread.start", return_value=None)
        cls.parche_hilos.start()
        cls.raiz = ctk.CTk()
        cls.raiz.geometry("656x432-10000-10000")
        cls.raiz.update()

    @classmethod
    def tearDownClass(cls):
        cls.destruir_raiz(cls.raiz)
        cls.parche_hilos.stop()

    def crear_raiz(self):
        return self.raiz

    def crear_vista(self, raiz, clase, *extra):
        vista = clase(raiz, BaseDatosVacia(), *extra)
        vista.pack(fill="both", expand=True)
        raiz.update()
        return vista

    @staticmethod
    def destruir_raiz(raiz):
        try:
            raiz.destroy()
        except Exception:
            pass

    def test_encabezados_no_tocan_el_contorno(self):
        raiz = self.crear_raiz()
        for clase in (TrabajadoresTab, HistorialTab):
            with self.subTest(clase=clase.__name__):
                vista = self.crear_vista(raiz, clase)
                barra = vista.winfo_children()[0]
                for control in barra.winfo_children():
                    self.assertGreater(control.winfo_y(), 1)
                    self.assertLess(
                        control.winfo_y() + control.winfo_height(),
                        barra.winfo_height() - 1,
                    )
                vista.pack_forget()

    def test_botones_no_recortan_su_texto_en_1024_a_150(self):
        raiz = self.crear_raiz()
        casos = (
            (EstadisticasTab, (1.5,)),
            (InventarioTab, ()),
            (MapaBodegaTab, ()),
            (PgpTab, ()),
        )
        for clase, extra in casos:
            with self.subTest(clase=clase.__name__):
                vista = self.crear_vista(raiz, clase, *extra)
                pendientes = [vista]
                while pendientes:
                    widget = pendientes.pop()
                    pendientes.extend(widget.winfo_children())
                    if not isinstance(widget, ctk.CTkButton):
                        continue
                    if not widget.winfo_ismapped():
                        continue
                    etiqueta = getattr(widget, "_text_label", None)
                    if etiqueta is None or not etiqueta.winfo_exists():
                        continue
                    self.assertLessEqual(
                        etiqueta.winfo_reqwidth(),
                        etiqueta.winfo_width() + 2,
                        msg=f"Texto recortado: {getattr(widget, '_text', '')}",
                    )
                vista.pack_forget()


if __name__ == "__main__":
    unittest.main()
