"""Ejemplo ejecutable del estilo visual y el zoom portable."""

from tkinter import ttk

import customtkinter as ctk

from tema import (
    PALETA,
    aplicar_tema_base,
    configurar_treeview_global,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)
from zoom import GestorZoom


class AplicacionEjemplo(ctk.CTk):
    def __init__(self):
        aplicar_tema_base()
        super().__init__()
        self.title("Plantilla visual")
        self.geometry("1120x720")
        self.minsize(900, 600)
        self.configure(fg_color=PALETA["fondo"])

        self.estilo_tablas = ttk.Style(self)
        self.zoom = GestorZoom(
            self,
            nombre_aplicacion="PlantillaEstiloBodega",
            al_cambiar=self.actualizar_tablas,
        )
        self.crear_interfaz()

    def actualizar_tablas(self, escala):
        configurar_treeview_global(self.estilo_tablas, escala)

    def crear_interfaz(self):
        barra = ctk.CTkFrame(self, **estilos_barra())
        barra.pack(fill="x", padx=20, pady=(16, 10))

        ctk.CTkLabel(
            barra,
            text="Sistema de Gestión",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETA["primario"],
        ).pack(side="left", padx=14, pady=12)

        ctk.CTkLabel(
            barra,
            text="Usuario: Bruno  |  Rol: Administrador",
            text_color=PALETA["texto_suave"],
        ).pack(side="left", padx=14)

        self.zoom.crear_controles(barra).pack(side="right", padx=10, pady=6)

        navegacion = ctk.CTkSegmentedButton(
            self,
            values=["Inicio", "Inventario", "Movimientos", "Configuración"],
            fg_color=PALETA["primario_suave"],
            selected_color=PALETA["primario"],
            selected_hover_color=PALETA["primario_hover"],
            unselected_color=PALETA["primario_suave"],
            unselected_hover_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        navegacion.pack(fill="x", padx=20, pady=(0, 10))
        navegacion.set("Inventario")

        panel = ctk.CTkFrame(self, **estilos_panel())
        panel.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        encabezado = ctk.CTkFrame(panel, fg_color="transparent")
        encabezado.pack(fill="x", padx=18, pady=(18, 10))
        ctk.CTkLabel(
            encabezado,
            text="Inventario general",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETA["texto"],
        ).pack(side="left")
        ctk.CTkButton(
            encabezado,
            text="+ Nuevo artículo",
            **estilos_boton("primario"),
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            encabezado,
            text="Editar seleccionado",
            **estilos_boton("secundario"),
        ).pack(side="right")

        filtros = ctk.CTkFrame(panel, fg_color=PALETA["panel_alt"], corner_radius=8)
        filtros.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkEntry(
            filtros,
            placeholder_text="Buscar por nombre, categoría o ubicación...",
            height=36,
            border_color=PALETA["borde"],
        ).pack(side="left", fill="x", expand=True, padx=12, pady=12)
        ctk.CTkOptionMenu(
            filtros,
            values=["Todos los sectores", "Bodega", "Afuera de bodega"],
            fg_color=PALETA["secundario"],
            button_color=PALETA["secundario_hover"],
        ).pack(side="left", padx=(0, 12), pady=12)

        contenedor_tabla = ctk.CTkFrame(panel, fg_color="transparent")
        contenedor_tabla.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        columnas = ("producto", "categoria", "ubicacion", "stock", "estado")
        tabla = ttk.Treeview(contenedor_tabla, columns=columnas, show="headings")
        for columna, titulo, ancho in (
            ("producto", "Producto", 280),
            ("categoria", "Categoría", 180),
            ("ubicacion", "Ubicación", 170),
            ("stock", "Stock", 90),
            ("estado", "Estado", 130),
        ):
            tabla.heading(columna, text=titulo)
            tabla.column(columna, width=ancho, anchor="center" if columna in {"stock", "estado"} else "w")

        tabla.insert("", "end", values=("Guante anticorte", "EPP", "Bodega · A-04", 42, "Disponible"), tags=("impar",))
        tabla.insert("", "end", values=("Paño de andamio", "Material", "Bodega · B-02", 8, "Stock bajo"), tags=("stock_bajo",))
        tabla.insert("", "end", values=("Argón industrial", "Gas", "Afuera · A-01", 2, "Crítico"), tags=("stock_critico",))
        tabla.insert("", "end", values=("Tóner impresora", "Librería", "Bodega · L-03", 15, "Disponible"), tags=("par",))
        estilizar_treeview(tabla)
        tabla.pack(fill="both", expand=True)


if __name__ == "__main__":
    AplicacionEjemplo().mainloop()
