"""Tema visual portable basado en el Sistema de Gestión de Bodega."""

from tkinter import ttk

import customtkinter as ctk


PALETA = {
    "fondo": "#edf5fb",
    "panel": "#ffffff",
    "panel_alt": "#f7fbff",
    "borde": "#bfdbfe",
    "borde_suave": "#1659af",
    "texto": "#0f172a",
    "texto_suave": "#64748b",
    "primario": "#1d4ed8",
    "primario_hover": "#1e40af",
    "primario_suave": "#e0f2fe",
    "secundario": "#475569",
    "secundario_hover": "#334155",
    "exito": "#0f766e",
    "exito_hover": "#115e59",
    "peligro": "#b91c1c",
    "peligro_hover": "#7f1d1d",
    "alerta": "#b7791f",
    "alerta_hover": "#8a5a12",
    "seleccion": "#2563eb",
    "fila_par": "#f8fbff",
    "fila_impar": "#ffffff",
    "fila_inactiva": "#e5e7eb",
    "stock_bajo": "#fef3c7",
    "stock_critico": "#fee2e2",
}


def aplicar_tema_base():
    """Activa el modo claro y el tema azul de CustomTkinter."""
    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")


def estilos_boton(tipo="primario"):
    """Devuelve colores listos para expandir con ** en un CTkButton."""
    estilos = {
        "primario": {
            "fg_color": PALETA["primario"],
            "hover_color": PALETA["primario_hover"],
            "text_color": "white",
        },
        "secundario": {
            "fg_color": PALETA["secundario"],
            "hover_color": PALETA["secundario_hover"],
            "text_color": "white",
        },
        "exito": {
            "fg_color": PALETA["exito"],
            "hover_color": PALETA["exito_hover"],
            "text_color": "white",
        },
        "peligro": {
            "fg_color": PALETA["peligro"],
            "hover_color": PALETA["peligro_hover"],
            "text_color": "white",
        },
        "alerta": {
            "fg_color": PALETA["alerta"],
            "hover_color": PALETA["alerta_hover"],
            "text_color": "white",
        },
        "fantasma": {
            "fg_color": PALETA["primario_suave"],
            "hover_color": PALETA["borde"],
            "text_color": PALETA["primario"],
        },
    }
    return estilos.get(tipo, estilos["primario"]).copy()


def estilos_panel():
    return {
        "fg_color": PALETA["panel"],
        "border_color": PALETA["borde_suave"],
        "border_width": 1,
        "corner_radius": 10,
    }


def estilos_barra():
    return estilos_panel()


def configurar_treeview_global(estilo: ttk.Style, escala=1.0):
    """Aplica el mismo estilo y adapta fuente/filas al zoom activo."""
    tamano_fuente = max(8, round(10 * escala))
    alto_fila = max(24, round(30 * escala))

    estilo.theme_use("clam")
    estilo.configure(
        "Treeview",
        background=PALETA["fila_impar"],
        foreground=PALETA["texto"],
        rowheight=alto_fila,
        fieldbackground=PALETA["fila_impar"],
        bordercolor=PALETA["borde_suave"],
        borderwidth=1,
        font=("Segoe UI", tamano_fuente),
    )
    estilo.configure(
        "Treeview.Heading",
        font=("Segoe UI", tamano_fuente, "bold"),
        background=PALETA["primario_suave"],
        foreground=PALETA["texto"],
        relief="flat",
        bordercolor=PALETA["borde"],
    )
    estilo.map(
        "Treeview",
        background=[("selected", PALETA["seleccion"])],
        foreground=[("selected", "white")],
    )


def estilizar_treeview(tabla):
    """Crea etiquetas opcionales para estados y filas alternadas."""
    tabla.tag_configure("par", background=PALETA["fila_par"])
    tabla.tag_configure("impar", background=PALETA["fila_impar"])
    tabla.tag_configure("inactivo", background=PALETA["fila_inactiva"], foreground=PALETA["texto_suave"])
    tabla.tag_configure("stock_bajo", background=PALETA["stock_bajo"], foreground=PALETA["texto"])
    tabla.tag_configure("stock_critico", background=PALETA["stock_critico"], foreground=PALETA["peligro"])
