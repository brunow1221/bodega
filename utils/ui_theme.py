import customtkinter as ctk


PALETA = {
    "fondo": ("#edf5fb", "#0b1220"),
    "panel": ("#ffffff", "#111827"),
    "panel_alt": ("#f7fbff", "#172033"),
    "borde": ("#bfdbfe", "#334155"),
    "borde_suave": ("#1659af", "#475569"),
    "texto": ("#0f172a", "#e5edf7"),
    "texto_suave": ("#64748b", "#9fb0c4"),
    "primario": ("#1d4ed8", "#3b82f6"),
    "primario_hover": ("#1e40af", "#2563eb"),
    "primario_suave": ("#e0f2fe", "#1e3a5f"),
    "secundario": ("#475569", "#475569"),
    "secundario_hover": ("#334155", "#64748b"),
    "exito": ("#0f766e", "#0f766e"),
    "exito_hover": ("#115e59", "#14b8a6"),
    "peligro": ("#b91c1c", "#dc2626"),
    "peligro_hover": ("#7f1d1d", "#b91c1c"),
    "alerta": ("#b7791f", "#d97706"),
    "alerta_hover": ("#8a5a12", "#b45309"),
    "seleccion": ("#2563eb", "#1d4ed8"),
    "fila_par": ("#f8fbff", "#172033"),
    "fila_impar": ("#ffffff", "#111827"),
    "fila_inactiva": ("#e5e7eb", "#293548"),
    "stock_bajo": ("#fef3c7", "#4a3513"),
    "stock_critico": ("#fee2e2", "#4b1d24"),
}


def color_actual(color):
    if isinstance(color, (tuple, list)) and len(color) >= 2:
        return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
    return color


def aplicar_tema_base(modo="Light"):
    ctk.set_appearance_mode(modo)
    ctk.set_default_color_theme("blue")


def estilos_boton(tipo="primario"):
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
    return estilos.get(tipo, estilos["primario"])


def estilos_panel():
    return {
        "fg_color": PALETA["panel"],
        "border_color": PALETA["borde_suave"],
        "border_width": 1,
        "corner_radius": 10,
    }


def estilos_barra():
    return {
        "fg_color": PALETA["panel"],
        "border_color": PALETA["borde_suave"],
        "border_width": 1,
        "corner_radius": 10,
    }


def configurar_treeview_global(estilo, escala=1.0):
    tamano_fuente = max(8, round(10 * escala))
    alto_fila = max(24, round(30 * escala))

    estilo.theme_use("clam")
    estilo.configure(
        "TFrame",
        background=color_actual(PALETA["panel"]),
    )
    estilo.configure(
        "TEntry",
        fieldbackground=color_actual(PALETA["panel_alt"]),
        foreground=color_actual(PALETA["texto"]),
        bordercolor=color_actual(PALETA["borde"]),
        lightcolor=color_actual(PALETA["borde"]),
        darkcolor=color_actual(PALETA["borde"]),
    )
    estilo.configure(
        "TButton",
        background=color_actual(PALETA["primario_suave"]),
        foreground=color_actual(PALETA["texto"]),
        bordercolor=color_actual(PALETA["borde"]),
    )
    estilo.map(
        "TButton",
        background=[("active", color_actual(PALETA["borde"]))],
    )
    estilo.configure(
        "TScrollbar",
        background=color_actual(PALETA["borde"]),
        troughcolor=color_actual(PALETA["panel_alt"]),
        bordercolor=color_actual(PALETA["panel"]),
        arrowcolor=color_actual(PALETA["texto"]),
    )
    estilo.configure(
        "Treeview",
        background=color_actual(PALETA["fila_impar"]),
        foreground=color_actual(PALETA["texto"]),
        rowheight=alto_fila,
        fieldbackground=color_actual(PALETA["fila_impar"]),
        bordercolor=color_actual(PALETA["borde_suave"]),
        lightcolor=color_actual(PALETA["borde_suave"]),
        darkcolor=color_actual(PALETA["borde_suave"]),
        borderwidth=1,
        relief="flat",
        font=("Segoe UI", tamano_fuente),
    )
    estilo.configure(
        "Treeview.Heading",
        font=("Segoe UI", tamano_fuente, "bold"),
        background=color_actual(PALETA["primario_suave"]),
        foreground=color_actual(PALETA["texto"]),
        relief="flat",
        bordercolor=color_actual(PALETA["borde"]),
        lightcolor=color_actual(PALETA["borde"]),
        darkcolor=color_actual(PALETA["borde"]),
    )
    estilo.map(
        "Treeview",
        background=[("selected", color_actual(PALETA["seleccion"]))],
        foreground=[("selected", "white")],
        bordercolor=[("focus", color_actual(PALETA["borde_suave"]))],
        lightcolor=[("focus", color_actual(PALETA["borde_suave"]))],
        darkcolor=[("focus", color_actual(PALETA["borde_suave"]))],
    )


def estilizar_treeview(tabla):
    tabla.tag_configure("par", background=color_actual(PALETA["fila_par"]))
    tabla.tag_configure("impar", background=color_actual(PALETA["fila_impar"]))
    tabla.tag_configure("activo", background=color_actual(PALETA["fila_impar"]))
    tabla.tag_configure("inactivo", background=color_actual(PALETA["fila_inactiva"]), foreground=color_actual(PALETA["texto_suave"]))
    tabla.tag_configure("finalizado", background=color_actual(PALETA["primario_suave"]), foreground=color_actual(PALETA["texto"]))
    tabla.tag_configure("stock_bajo", background=color_actual(PALETA["stock_bajo"]), foreground=color_actual(PALETA["texto"]))
    tabla.tag_configure("stock_critico", background=color_actual(PALETA["stock_critico"]), foreground=color_actual(PALETA["peligro"]))


def color_estado(tipo):
    colores = {
        "cargando": PALETA["alerta"],
        "ok": PALETA["exito"],
        "error": PALETA["peligro"],
        "info": PALETA["primario"],
        "suave": PALETA["texto_suave"],
    }
    return colores.get(tipo, PALETA["texto_suave"])
