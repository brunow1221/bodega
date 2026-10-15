"""Ventanas centradas y limitadas al área útil del monitor, incluso con zoom."""

import re
import sys
from tkinter import Toplevel

import customtkinter as ctk


def area_disponible(ventana):
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class MonitorInfo(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD),
                            ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

            user32 = ctypes.windll.user32
            user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            user32.MonitorFromWindow.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
            padre = ventana.master.winfo_toplevel() if ventana.master else ventana
            monitor = user32.MonitorFromWindow(padre.winfo_id(), 2)
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(info)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                r = info.rcWork
                return r.left, r.top, r.right - r.left, r.bottom - r.top
        except (OSError, AttributeError):
            pass
    return 0, 0, ventana.winfo_screenwidth(), ventana.winfo_screenheight() - 60


def dimensiones_ajustadas(ancho, alto, escala, area_ancho, area_alto):
    max_ancho = max(1, int((area_ancho - 40) / escala))
    max_alto = max(1, int((area_alto - 80) / escala))
    return min(ancho, max_ancho), min(alto, max_alto)


def dimensiones_ventana_principal(area_ancho, area_alto, escala=1.0):
    ancho, alto = dimensiones_ajustadas(
        1200, 800, escala, area_ancho, area_alto
    )
    minimo_ancho, minimo_alto = dimensiones_ajustadas(
        900, 600, escala, area_ancho, area_alto
    )
    return ancho, alto, minimo_ancho, minimo_alto


def adaptar_campos_en_fila(frame, cantidad, pie=None):
    """Apila pares etiqueta/campo cuando el formulario tiene poco ancho."""
    grupos = [(frame.grid_slaves(row=0, column=i)[0],
               frame.grid_slaves(row=1, column=i)[0]) for i in range(cantidad)]
    ultimo = [None]

    def distribuir(event):
        if event.widget != frame:
            return
        ancho = event.width / frame._get_widget_scaling()
        compacto = ancho < 480
        if compacto != ultimo[0]:
            ultimo[0] = compacto
            for i, (etiqueta, campo) in enumerate(grupos):
                frame.grid_columnconfigure(i, weight=1 if not compacto or i == 0 else 0)
                etiqueta.grid_configure(row=2*i if compacto else 0, column=0 if compacto else i)
                campo.grid_configure(row=2*i+1 if compacto else 1, column=0 if compacto else i)
            if pie is not None:
                pie.grid_configure(row=2*cantidad if compacto else 2, columnspan=1 if compacto else cantidad)
        if pie is not None:
            pie.configure(wraplength=max(100, ancho - 30))

    frame.bind("<Configure>", distribuir, add="+")


class VentanaAdaptable(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        self._tamano_solicitado = None
        super().__init__(*args, **kwargs)

    def geometry(self, geometry_string=None):
        if geometry_string:
            medidas = re.match(r"^(\d+)x(\d+)", geometry_string)
            if medidas:
                self._tamano_solicitado = tuple(map(int, medidas.groups()))
                self.ajustar_pantalla()
                return
        return super().geometry(geometry_string)

    def minsize(self, width=None, height=None):
        if width is None or height is None:
            return Toplevel.minsize(self)
        _, _, aw, ah = area_disponible(self)
        width, height = dimensiones_ajustadas(width, height, self._get_window_scaling(), aw, ah)
        # Permite reducir el formulario; los formularios largos tienen desplazamiento.
        return super().minsize(min(width, 320), min(height, 240))

    def _set_scaling(self, new_widget_scaling, new_window_scaling):
        super()._set_scaling(new_widget_scaling, new_window_scaling)
        if self._tamano_solicitado:
            self.after_idle(self.ajustar_pantalla)

    def ajustar_pantalla(self):
        if not self._tamano_solicitado or not self.winfo_exists():
            return
        left, top, aw, ah = area_disponible(self)
        escala = self._get_window_scaling()
        ancho, alto = dimensiones_ajustadas(*self._tamano_solicitado, escala, aw, ah)
        max_ancho, max_alto = dimensiones_ajustadas(100000, 100000, escala, aw, ah)
        super().minsize(min(320, ancho), min(240, alto))
        super().maxsize(max_ancho, max_alto)
        x = left + max(0, int((aw - ancho * escala) / 2))
        y = top + max(30, int((ah - alto * escala) / 2) - 15)
        super().geometry(f"{ancho}x{alto}{x:+d}{y:+d}")
