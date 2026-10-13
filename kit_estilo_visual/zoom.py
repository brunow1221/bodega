"""Zoom global reutilizable para aplicaciones CustomTkinter."""

import json
import os
from pathlib import Path

import customtkinter as ctk

try:
    from .tema import PALETA, estilos_boton
except ImportError:  # Permite ejecutar ejemplo.py directamente.
    from tema import PALETA, estilos_boton


class GestorZoom:
    def __init__(
        self,
        ventana,
        nombre_aplicacion="MiAplicacion",
        zoom_predeterminado=100,
        zoom_minimo=80,
        zoom_maximo=160,
        paso=10,
        al_cambiar=None,
    ):
        self.ventana = ventana
        self.nombre_aplicacion = nombre_aplicacion
        self.zoom_predeterminado = zoom_predeterminado
        self.zoom_minimo = zoom_minimo
        self.zoom_maximo = zoom_maximo
        self.paso = paso
        self.al_cambiar = al_cambiar
        self.boton_porcentaje = None
        self.porcentaje = self.cargar()

        self.aplicar(self.porcentaje, guardar=False)
        self.configurar_atajos()

    def normalizar(self, valor):
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return self.zoom_predeterminado

        ajustado = int(round(numero / self.paso) * self.paso)
        return max(self.zoom_minimo, min(self.zoom_maximo, ajustado))

    def ruta_preferencias(self):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / self.nombre_aplicacion / "preferencias.json"
        return Path.home() / f".{self.nombre_aplicacion.lower()}" / "preferencias.json"

    def cargar(self):
        try:
            datos = json.loads(self.ruta_preferencias().read_text(encoding="utf-8"))
            return self.normalizar(datos.get("zoom", self.zoom_predeterminado))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return self.zoom_predeterminado

    def guardar(self):
        try:
            ruta = self.ruta_preferencias()
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(
                json.dumps({"zoom": self.porcentaje}, indent=2),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False

    def aplicar(self, porcentaje, guardar=True):
        self.porcentaje = self.normalizar(porcentaje)
        escala = self.porcentaje / 100

        ctk.set_widget_scaling(escala)
        ctk.set_window_scaling(escala)

        if self.al_cambiar:
            self.al_cambiar(escala)

        if self.boton_porcentaje is not None:
            self.boton_porcentaje.configure(text=f"{self.porcentaje}%")

        if guardar:
            self.guardar()

    def aumentar(self, event=None):
        self.aplicar(self.porcentaje + self.paso)
        return "break" if event is not None else None

    def disminuir(self, event=None):
        self.aplicar(self.porcentaje - self.paso)
        return "break" if event is not None else None

    def restablecer(self, event=None):
        self.aplicar(self.zoom_predeterminado)
        return "break" if event is not None else None

    def configurar_atajos(self):
        for secuencia in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.ventana.bind_all(secuencia, self.aumentar, add="+")
        for secuencia in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.ventana.bind_all(secuencia, self.disminuir, add="+")
        for secuencia in ("<Control-0>", "<Control-KP_0>"):
            self.ventana.bind_all(secuencia, self.restablecer, add="+")

    def crear_controles(self, padre):
        contenedor = ctk.CTkFrame(padre, fg_color="transparent")
        ctk.CTkLabel(
            contenedor,
            text="Zoom:",
            text_color=PALETA["texto_suave"],
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            contenedor,
            text="−",
            width=34,
            height=30,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.disminuir,
            **estilos_boton("fantasma"),
        ).pack(side="left", padx=2)

        self.boton_porcentaje = ctk.CTkButton(
            contenedor,
            text=f"{self.porcentaje}%",
            width=62,
            height=30,
            command=self.restablecer,
            **estilos_boton("fantasma"),
        )
        self.boton_porcentaje.pack(side="left", padx=2)

        ctk.CTkButton(
            contenedor,
            text="+",
            width=34,
            height=30,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.aumentar,
            **estilos_boton("fantasma"),
        ).pack(side="left", padx=2)
        return contenedor
