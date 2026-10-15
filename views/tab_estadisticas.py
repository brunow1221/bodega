import threading
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from utils.estadisticas import (
    TODOS,
    TIPOS_USO,
    calcular_estadisticas,
    calcular_historial_articulo,
    calcular_historial_precios,
    clave_producto,
)
from utils.searchable_combobox import SearchableCombobox
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.ui_theme import (
    PALETA,
    color_actual,
    color_estado,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)


class GraficoBarras(ctk.CTkFrame):
    def __init__(self, master, titulo, color, **kwargs):
        super().__init__(master, **estilos_panel(), **kwargs)
        self.color = color
        self.datos = []
        self.escala = 1.0

        ctk.CTkLabel(
            self,
            text=titulo,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETA["texto"],
        ).pack(anchor="w", padx=16, pady=(12, 2))
        self.canvas = tk.Canvas(
            self,
            height=280,
            background=color_actual(PALETA["panel"]),
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas.bind("<Configure>", lambda _evento: self.redibujar())

    def actualizar(self, datos):
        self.datos = list(datos or [])
        alto = max(230, 34 * max(1, len(self.datos)) + 35)
        self.canvas.configure(height=round(alto * self.escala))
        self.after_idle(self.redibujar)

    def aplicar_zoom(self, escala):
        self.escala = escala
        self.actualizar(self.datos)

    def aplicar_tema(self):
        self.canvas.configure(background=color_actual(PALETA["panel"]))
        self.redibujar()

    def redibujar(self):
        self.canvas.delete("all")
        ancho = max(self.canvas.winfo_width(), 420)
        alto = max(self.canvas.winfo_height(), 220)
        escala = self.escala
        if not self.datos:
            self.canvas.create_text(
                ancho / 2,
                alto / 2,
                text="Sin datos para los filtros seleccionados",
                fill=color_actual(PALETA["texto_suave"]),
                font=("Segoe UI", max(9, round(11 * escala))),
            )
            return

        margen_etiqueta = min(round(185 * escala), round(ancho * 0.42))
        margen_derecho = round(52 * escala)
        ancho_barras = max(40, ancho - margen_etiqueta - margen_derecho - 18)
        alto_fila = (alto - 22) / len(self.datos)
        maximo = max(item["cantidad"] for item in self.datos) or 1

        for indice, item in enumerate(self.datos):
            centro_y = 12 + alto_fila * (indice + 0.5)
            alto_barra = min(round(20 * escala), alto_fila * 0.62)
            ancho_barra = ancho_barras * item["cantidad"] / maximo
            etiqueta = str(item["etiqueta"])
            limite = max(12, round(margen_etiqueta / max(5, 7 * escala)))
            if len(etiqueta) > limite:
                etiqueta = etiqueta[: limite - 1] + "…"

            self.canvas.create_text(
                margen_etiqueta - 8,
                centro_y,
                text=etiqueta,
                anchor="e",
                fill=color_actual(PALETA["texto"]),
                font=("Segoe UI", max(8, round(10 * escala))),
            )
            self.canvas.create_rectangle(
                margen_etiqueta,
                centro_y - alto_barra / 2,
                margen_etiqueta + ancho_barra,
                centro_y + alto_barra / 2,
                fill=color_actual(self.color),
                outline="",
            )
            self.canvas.create_text(
                margen_etiqueta + ancho_barra + 7,
                centro_y,
                text=str(item["cantidad"]),
                anchor="w",
                fill=color_actual(PALETA["texto"]),
                font=("Segoe UI", max(8, round(10 * escala)), "bold"),
            )


class GraficoTendencia(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **estilos_panel(), **kwargs)
        self.datos = []
        self.escala = 1.0
        ctk.CTkLabel(
            self,
            text="Evolución mensual del uso",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETA["texto"],
        ).pack(anchor="w", padx=16, pady=(12, 2))
        self.canvas = tk.Canvas(
            self,
            height=260,
            background=color_actual(PALETA["panel"]),
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas.bind("<Configure>", lambda _evento: self.redibujar())

    def actualizar(self, datos):
        self.datos = list(datos or [])
        self.canvas.configure(height=round(260 * self.escala))
        self.after_idle(self.redibujar)

    def aplicar_zoom(self, escala):
        self.escala = escala
        self.actualizar(self.datos)

    def aplicar_tema(self):
        self.canvas.configure(background=color_actual(PALETA["panel"]))
        self.redibujar()

    def redibujar(self):
        self.canvas.delete("all")
        ancho = max(self.canvas.winfo_width(), 500)
        alto = max(self.canvas.winfo_height(), 220)
        escala = self.escala
        if not self.datos:
            self.canvas.create_text(
                ancho / 2,
                alto / 2,
                text="Sin fechas válidas para construir la tendencia",
                fill=color_actual(PALETA["texto_suave"]),
                font=("Segoe UI", max(9, round(11 * escala))),
            )
            return

        izquierda = round(58 * escala)
        derecha = round(25 * escala)
        superior = round(20 * escala)
        inferior = round(50 * escala)
        x0, y0 = izquierda, alto - inferior
        x1, y1 = ancho - derecha, superior
        maximo = max(item["cantidad"] for item in self.datos) or 1

        for paso in range(5):
            y = y0 - (y0 - y1) * paso / 4
            valor = round(maximo * paso / 4)
            self.canvas.create_line(
                x0, y, x1, y, fill=color_actual(PALETA["borde"])
            )
            self.canvas.create_text(
                x0 - 8, y, text=str(valor), anchor="e",
                fill=color_actual(PALETA["texto_suave"]),
                font=("Segoe UI", max(8, round(9 * escala))),
            )

        cantidad_puntos = len(self.datos)
        puntos = []
        for indice, item in enumerate(self.datos):
            x = (
                (x0 + x1) / 2
                if cantidad_puntos == 1
                else x0 + (x1 - x0) * indice / (cantidad_puntos - 1)
            )
            y = y0 - (y0 - y1) * item["cantidad"] / maximo
            puntos.extend((x, y))
            self.canvas.create_text(
                x, y0 + round(20 * escala), text=item["etiqueta"],
                anchor="n", fill=color_actual(PALETA["texto_suave"]),
                font=("Segoe UI", max(7, round(9 * escala))),
            )
            self.canvas.create_text(
                x, y - round(11 * escala), text=str(item["cantidad"]),
                fill=color_actual(PALETA["texto"]),
                font=("Segoe UI", max(8, round(9 * escala)), "bold"),
            )

        if len(puntos) >= 4:
            self.canvas.create_line(
                *puntos,
                fill=color_actual(PALETA["primario"]),
                width=max(2, round(3 * escala)),
            )
        for indice in range(0, len(puntos), 2):
            x, y = puntos[indice], puntos[indice + 1]
            radio = max(3, round(4 * escala))
            self.canvas.create_oval(
                x - radio, y - radio, x + radio, y + radio,
                fill=color_actual(PALETA["primario"]),
                outline=color_actual(PALETA["panel"]),
                width=2,
            )


class EstadisticasTab(ctk.CTkFrame):
    def __init__(self, master, db_manager, escala_zoom=1.0):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.movimientos = []
        self.historial_precios = {
            "disponible": False,
            "filas": [],
            "error": "Cargando historial de precios...",
        }
        self._carga_id = 0
        self.escala_zoom = escala_zoom
        iniciar_despachador_ui(self)
        self.crear_interfaz()
        self.after(800, self.actualizar_datos)

    def crear_interfaz(self):
        self.pack_propagate(False)
        barra = ctk.CTkFrame(self, **estilos_barra())
        barra.pack(fill="x", padx=12, pady=(10, 5))
        barra.grid_columnconfigure(0, weight=1)

        self.titulo_estadisticas = ctk.CTkLabel(
            barra,
            text="Estadísticas de artículos y proyectos",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETA["primario"],
            anchor="w",
            justify="left",
        )
        self.titulo_estadisticas.grid(
            row=0, column=0, sticky="ew", padx=14, pady=(10, 4)
        )
        fila_actualizacion = ctk.CTkFrame(barra, fg_color="transparent")
        fila_actualizacion.grid(
            row=1, column=0, sticky="ew", padx=14, pady=(4, 10)
        )
        fila_actualizacion.grid_columnconfigure(0, weight=1)
        self.label_estado = ctk.CTkLabel(
            fila_actualizacion,
            text="",
            text_color=color_estado("suave"),
            anchor="w",
            justify="left",
        )
        self.label_estado.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.boton_actualizar = ctk.CTkButton(
            fila_actualizacion,
            text="Actualizar datos",
            command=self.actualizar_datos,
            **estilos_boton("primario"),
        )
        self.boton_actualizar.grid(row=0, column=1, sticky="e")
        barra.bind(
            "<Configure>",
            lambda evento: self.titulo_estadisticas.configure(
                wraplength=max(220, evento.width - 36)
            ),
        )

        self.secciones = ctk.CTkTabview(
            self,
            fg_color=PALETA["panel"],
            segmented_button_fg_color=PALETA["primario_suave"],
            segmented_button_selected_color=PALETA["primario"],
            segmented_button_selected_hover_color=PALETA["primario_hover"],
            segmented_button_unselected_color=PALETA["primario_suave"],
            segmented_button_unselected_hover_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self.secciones.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.tab_graficos = self.secciones.add("Gráficos")
        self.tab_historial_articulo = self.secciones.add("Historial por artículo")
        self.tab_precios = self.secciones.add("Cambios de precio")

        self.contenido = ctk.CTkScrollableFrame(
            self.tab_graficos, fg_color="transparent", corner_radius=0
        )
        self.contenido.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self.contenido.grid_columnconfigure((0, 1), weight=1, uniform="graficos")

        filtros = ctk.CTkFrame(self.contenido, **estilos_panel())
        filtros.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=5)
        for columna in range(3):
            filtros.grid_columnconfigure(columna, weight=1)

        self.combo_proyecto = self.crear_filtro_combo(
            filtros, "Proyecto", [TODOS], 0
        )
        self.combo_tipo = self.crear_filtro_combo(
            filtros, "Tipo de uso", [TODOS, *TIPOS_USO], 1
        )
        self.combo_limite = self.crear_filtro_combo(
            filtros, "Mostrar", ["5", "10", "15", "20"], 2
        )
        self.combo_limite.set("10")

        ctk.CTkLabel(filtros, text="Desde").grid(
            row=2, column=0, sticky="w", padx=8, pady=(2, 2)
        )
        self.entry_desde = ctk.CTkEntry(filtros, placeholder_text="AAAA-MM-DD")
        self.entry_desde.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 10))
        ctk.CTkLabel(filtros, text="Hasta").grid(
            row=2, column=1, sticky="w", padx=8, pady=(2, 2)
        )
        self.entry_hasta = ctk.CTkEntry(filtros, placeholder_text="AAAA-MM-DD")
        self.entry_hasta.grid(row=3, column=1, sticky="ew", padx=8, pady=(0, 10))
        for entrada in (self.entry_desde, self.entry_hasta):
            entrada.bind("<Return>", self.aplicar_filtros)

        acciones = ctk.CTkFrame(filtros, fg_color="transparent")
        acciones.grid(row=3, column=2, sticky="ew", padx=8, pady=(0, 10))
        acciones.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            acciones, text="Aplicar",
            command=self.aplicar_filtros, **estilos_boton("exito")
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            acciones, text="Limpiar",
            command=self.limpiar_filtros, **estilos_boton("fantasma")
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        tarjetas = ctk.CTkFrame(self.contenido, fg_color="transparent")
        tarjetas.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=3)
        tarjetas.grid_columnconfigure((0, 1), weight=1, uniform="tarjetas")
        self.card_cantidad = self.crear_tarjeta(tarjetas, "Unidades utilizadas", 0, 0)
        self.card_productos = self.crear_tarjeta(tarjetas, "Artículos distintos", 1, 0)
        self.card_proyectos = self.crear_tarjeta(tarjetas, "Proyectos involucrados", 0, 1)
        self.card_valor = self.crear_tarjeta(tarjetas, "Valor estimado", 1, 1)

        self.grafico_productos = GraficoBarras(
            self.contenido, "Artículos más utilizados", PALETA["primario"]
        )
        self.grafico_productos.grid(
            row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=5
        )
        self.grafico_tendencia = GraficoTendencia(self.contenido)
        self.grafico_tendencia.grid(
            row=3, column=0, columnspan=2, sticky="nsew", padx=8, pady=5
        )
        self.label_desglose = ctk.CTkLabel(
            self.contenido,
            text="",
            justify="left",
            anchor="w",
            text_color=PALETA["texto_suave"],
        )
        self.label_desglose.grid(
            row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 12)
        )
        self.crear_historial_articulo()
        self.crear_historial_precios()
        self.aplicar_zoom(self.escala_zoom)

    def crear_historial_articulo(self):
        filtros = ctk.CTkFrame(self.tab_historial_articulo, **estilos_panel())
        filtros.pack(fill="x", padx=10, pady=10)
        filtros.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(filtros, text="Artículo").grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 2)
        )
        self.selector_articulo = SearchableCombobox(
            filtros,
            label_getter=lambda item: item["etiqueta"],
            search_getter=lambda item: item["producto"],
            on_selected=lambda _item: self.aplicar_filtros_historial(),
            width=42,
        )
        self.selector_articulo.grid(
            row=1, column=0, sticky="ew", padx=8, pady=(0, 10)
        )

        self.combo_proyecto_historial = self.crear_filtro_combo_historial(
            filtros, "Proyecto", [TODOS], 1
        )
        self.combo_tipo_historial = self.crear_filtro_combo_historial(
            filtros, "Movimiento", [TODOS], 2
        )

        ctk.CTkLabel(filtros, text="Desde").grid(
            row=2, column=0, sticky="w", padx=8, pady=(2, 2)
        )
        self.entry_desde_historial = ctk.CTkEntry(
            filtros, placeholder_text="AAAA-MM-DD"
        )
        self.entry_desde_historial.grid(
            row=3, column=0, sticky="ew", padx=8, pady=(0, 10)
        )
        ctk.CTkLabel(filtros, text="Hasta").grid(
            row=2, column=1, sticky="w", padx=8, pady=(2, 2)
        )
        self.entry_hasta_historial = ctk.CTkEntry(
            filtros, placeholder_text="AAAA-MM-DD"
        )
        self.entry_hasta_historial.grid(
            row=3, column=1, sticky="ew", padx=8, pady=(0, 10)
        )
        for entrada in (self.entry_desde_historial, self.entry_hasta_historial):
            entrada.bind("<Return>", self.aplicar_filtros_historial)

        acciones = ctk.CTkFrame(filtros, fg_color="transparent")
        acciones.grid(row=3, column=2, sticky="ew", padx=8, pady=(0, 10))
        acciones.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            acciones,
            text="Aplicar filtros",
            command=self.aplicar_filtros_historial,
            **estilos_boton("exito"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            acciones,
            text="Limpiar filtros",
            command=self.limpiar_filtros_historial,
            **estilos_boton("fantasma"),
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.label_estado_historial = ctk.CTkLabel(
            filtros,
            text="Seleccione un artículo para revisar sus movimientos.",
            text_color=color_estado("suave"),
            anchor="w",
            justify="left",
        )
        self.label_estado_historial.grid(
            row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8)
        )

        tarjetas = ctk.CTkFrame(
            self.tab_historial_articulo, fg_color="transparent"
        )
        tarjetas.pack(fill="x", padx=6, pady=(0, 5))
        tarjetas.grid_columnconfigure((0, 1), weight=1, uniform="historial")
        self.card_movimientos_articulo = self.crear_tarjeta(
            tarjetas, "Movimientos", 0, 0
        )
        self.card_retirado_articulo = self.crear_tarjeta(
            tarjetas, "Cantidad retirada", 1, 0
        )
        self.card_devuelto_articulo = self.crear_tarjeta(
            tarjetas, "Cantidad devuelta/ingresada", 0, 1
        )
        self.card_saldo_articulo = self.crear_tarjeta(
            tarjetas, "Balance de movimientos", 1, 1
        )

        frame_tabla = ctk.CTkFrame(
            self.tab_historial_articulo, **estilos_panel()
        )
        frame_tabla.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        scroll_y = ttk.Scrollbar(frame_tabla, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(frame_tabla, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")
        columnas = (
            "Fecha/Hora",
            "Movimiento",
            "Cantidad",
            "Trabajador",
            "Proyecto",
            "Registrado por",
            "Stock",
            "Comentario",
        )
        self.tabla_historial_articulo = ttk.Treeview(
            frame_tabla,
            columns=columnas,
            show="headings",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )
        anchos = {
            "Fecha/Hora": 145,
            "Movimiento": 190,
            "Cantidad": 80,
            "Trabajador": 180,
            "Proyecto": 170,
            "Registrado por": 170,
            "Stock": 100,
            "Comentario": 230,
        }
        for columna in columnas:
            self.tabla_historial_articulo.heading(columna, text=columna)
            self.tabla_historial_articulo.column(
                columna,
                width=anchos[columna],
                anchor="center" if columna in {"Fecha/Hora", "Cantidad", "Stock"} else "w",
            )
        estilizar_treeview(self.tabla_historial_articulo)
        self.tabla_historial_articulo.pack(fill="both", expand=True)
        scroll_y.configure(command=self.tabla_historial_articulo.yview)
        scroll_x.configure(command=self.tabla_historial_articulo.xview)

    def crear_filtro_combo_historial(self, padre, titulo, valores, columna):
        ctk.CTkLabel(padre, text=titulo).grid(
            row=0, column=columna, sticky="w", padx=8, pady=(8, 2)
        )
        combo = ctk.CTkComboBox(
            padre,
            values=valores,
            state="readonly",
            command=lambda _valor: self.aplicar_filtros_historial(),
        )
        combo.grid(row=1, column=columna, sticky="ew", padx=8, pady=(0, 10))
        combo.set(valores[0])
        return combo

    def crear_historial_precios(self):
        filtros = ctk.CTkFrame(self.tab_precios, **estilos_panel())
        filtros.pack(fill="x", padx=10, pady=10)
        filtros.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(filtros, text="Artículo").grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 2)
        )
        self.selector_precio_articulo = SearchableCombobox(
            filtros,
            label_getter=lambda item: item["etiqueta"],
            search_getter=lambda item: item["producto"],
            on_selected=lambda _item: self.aplicar_filtros_precios(),
            width=42,
        )
        self.selector_precio_articulo.grid(
            row=1, column=0, sticky="ew", padx=8, pady=(0, 10)
        )
        self.combo_direccion_precio = self.crear_filtro_combo_precios(
            filtros, "Tipo de cambio", [TODOS, "Aumentos", "Disminuciones"], 1
        )
        ctk.CTkLabel(filtros, text="Desde").grid(
            row=2, column=0, sticky="w", padx=8, pady=(2, 2)
        )
        self.entry_desde_precio = ctk.CTkEntry(
            filtros, placeholder_text="AAAA-MM-DD"
        )
        self.entry_desde_precio.grid(
            row=3, column=0, sticky="ew", padx=8, pady=(0, 10)
        )
        ctk.CTkLabel(filtros, text="Hasta").grid(
            row=2, column=1, sticky="w", padx=8, pady=(2, 2)
        )
        self.entry_hasta_precio = ctk.CTkEntry(
            filtros, placeholder_text="AAAA-MM-DD"
        )
        self.entry_hasta_precio.grid(
            row=3, column=1, sticky="ew", padx=8, pady=(0, 10)
        )
        for entrada in (self.entry_desde_precio, self.entry_hasta_precio):
            entrada.bind("<Return>", self.aplicar_filtros_precios)

        acciones = ctk.CTkFrame(filtros, fg_color="transparent")
        acciones.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 4))
        acciones.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            acciones, text="Aplicar filtros", command=self.aplicar_filtros_precios,
            **estilos_boton("exito")
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            acciones, text="Limpiar filtros", command=self.limpiar_filtros_precios,
            **estilos_boton("fantasma")
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.label_estado_precios = ctk.CTkLabel(
            filtros,
            text="Cargando historial...",
            text_color=color_estado("suave"),
            anchor="w",
            justify="left",
        )
        self.label_estado_precios.grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8)
        )

        tarjetas = ctk.CTkFrame(self.tab_precios, fg_color="transparent")
        tarjetas.pack(fill="x", padx=6, pady=(0, 5))
        tarjetas.grid_columnconfigure((0, 1), weight=1, uniform="precios")
        self.card_productos_precio = self.crear_tarjeta(tarjetas, "Artículos modificados", 0, 0)
        self.card_cambios_precio = self.crear_tarjeta(tarjetas, "Cambios registrados", 1, 0)
        self.card_aumentos_precio = self.crear_tarjeta(tarjetas, "Aumentos", 0, 1)
        self.card_disminuciones_precio = self.crear_tarjeta(tarjetas, "Disminuciones", 1, 1)

        frame_tabla = ctk.CTkFrame(self.tab_precios, **estilos_panel())
        frame_tabla.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        scroll_y = ttk.Scrollbar(frame_tabla, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(frame_tabla, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")
        columnas = (
            "Fecha/Hora", "Artículo", "Precio anterior", "Precio nuevo",
            "Diferencia", "Variación", "Modificado por",
        )
        self.tabla_precios = ttk.Treeview(
            frame_tabla, columns=columnas, show="headings",
            yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set,
        )
        anchos = {
            "Fecha/Hora": 145, "Artículo": 260, "Precio anterior": 130,
            "Precio nuevo": 130, "Diferencia": 125, "Variación": 100,
            "Modificado por": 190,
        }
        for columna in columnas:
            self.tabla_precios.heading(columna, text=columna)
            self.tabla_precios.column(
                columna, width=anchos[columna],
                anchor="w" if columna in {"Artículo", "Modificado por"} else "center",
            )
        estilizar_treeview(self.tabla_precios)
        self.tabla_precios.tag_configure(
            "aumento", background=color_actual(PALETA["stock_bajo"])
        )
        self.tabla_precios.tag_configure(
            "disminucion",
            background=color_actual(PALETA["stock_critico"]),
            foreground=color_actual(PALETA["peligro"]),
        )
        self.tabla_precios.pack(fill="both", expand=True)
        scroll_y.configure(command=self.tabla_precios.yview)
        scroll_x.configure(command=self.tabla_precios.xview)

    def crear_filtro_combo_precios(self, padre, titulo, valores, columna):
        ctk.CTkLabel(padre, text=titulo).grid(
            row=0, column=columna, sticky="w", padx=8, pady=(8, 2)
        )
        combo = ctk.CTkComboBox(
            padre, values=valores, state="readonly",
            command=lambda _valor: self.aplicar_filtros_precios(),
        )
        combo.grid(row=1, column=columna, sticky="ew", padx=8, pady=(0, 10))
        combo.set(valores[0])
        return combo

    def crear_filtro_combo(self, padre, titulo, valores, columna):
        ctk.CTkLabel(padre, text=titulo).grid(
            row=0, column=columna, sticky="w", padx=8, pady=(8, 2)
        )
        combo = ctk.CTkComboBox(
            padre,
            values=valores,
            state="readonly",
            command=lambda _valor: self.aplicar_filtros(),
        )
        combo.grid(row=1, column=columna, sticky="ew", padx=8, pady=(0, 10))
        combo.set(valores[0])
        return combo

    def crear_tarjeta(self, padre, titulo, columna, fila=0):
        tarjeta = ctk.CTkFrame(padre, **estilos_panel())
        tarjeta.grid(row=fila, column=columna, sticky="ew", padx=4, pady=5)
        etiqueta = ctk.CTkLabel(
            tarjeta,
            text=titulo,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PALETA["texto_suave"],
            justify="center",
        )
        etiqueta.pack(fill="x", padx=8, pady=(10, 2))
        tarjeta.bind(
            "<Configure>",
            lambda evento, label=etiqueta: label.configure(
                wraplength=max(100, evento.width - 24)
            ),
        )
        valor = ctk.CTkLabel(
            tarjeta,
            text="0",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETA["primario"],
        )
        valor.pack(pady=(0, 10))
        return valor

    def actualizar_datos(self):
        self._carga_id += 1
        carga_id = self._carga_id
        self.boton_actualizar.configure(state="disabled", text="Cargando...")
        self.label_estado.configure(
            text="Consultando movimientos...", text_color=color_estado("cargando")
        )
        threading.Thread(
            target=self._cargar_datos_pesado, args=(carga_id,), daemon=True
        ).start()

    def _cargar_datos_pesado(self, carga_id):
        movimientos = self.db.obtener_movimientos_estadisticas()
        historial_precios = self.db.obtener_historial_precios()
        ejecutar_en_ui(
            self, self._recibir_datos, movimientos, carga_id, historial_precios
        )

    def _recibir_datos(self, movimientos, carga_id, historial_precios=None):
        if carga_id != self._carga_id:
            return
        self.movimientos = movimientos
        if historial_precios is not None:
            self.historial_precios = historial_precios
        seleccion = self.combo_proyecto.get()
        proyectos = sorted({
            str(movimiento.get("proyecto") or "Sin proyecto")
            for movimiento in movimientos
        }, key=str.casefold)
        valores = [TODOS, *proyectos]
        self.combo_proyecto.configure(values=valores)
        self.combo_proyecto.set(seleccion if seleccion in valores else TODOS)
        self.actualizar_selectores_historial(valores)
        self.actualizar_selector_precios()
        self.boton_actualizar.configure(state="normal", text="Actualizar datos")
        self.aplicar_filtros()

    def actualizar_selectores_historial(self, proyectos):
        seleccionado = self.selector_articulo.get_selected()
        clave_seleccionada = (
            seleccionado.get("clave") if seleccionado is not None else None
        )
        articulos_por_clave = {}
        for movimiento in self.movimientos:
            clave = clave_producto(movimiento)
            articulos_por_clave.setdefault(clave, {
                "clave": clave,
                "producto": movimiento.get("producto") or "Producto desconocido",
            })
        articulos = sorted(
            articulos_por_clave.values(), key=lambda item: item["producto"].casefold()
        )
        repeticiones = {}
        for item in articulos:
            nombre = item["producto"].casefold()
            repeticiones[nombre] = repeticiones.get(nombre, 0) + 1
        for item in articulos:
            item["etiqueta"] = item["producto"]
            if repeticiones[item["producto"].casefold()] > 1:
                item["etiqueta"] = f"{item['producto']} · ID {item['clave']}"
        self.selector_articulo.set_items(articulos)

        articulo_a_mostrar = next(
            (item for item in articulos if item["clave"] == clave_seleccionada),
            articulos[0] if articulos else None,
        )
        if articulo_a_mostrar is not None:
            self.selector_articulo.set(articulo_a_mostrar["etiqueta"])

        proyecto_actual = self.combo_proyecto_historial.get()
        self.combo_proyecto_historial.configure(values=proyectos)
        self.combo_proyecto_historial.set(
            proyecto_actual if proyecto_actual in proyectos else TODOS
        )

        tipos = sorted({
            str(movimiento.get("tipo_movimiento") or "Sin movimiento")
            for movimiento in self.movimientos
        }, key=str.casefold)
        valores_tipos = [TODOS, *tipos]
        tipo_actual = self.combo_tipo_historial.get()
        self.combo_tipo_historial.configure(values=valores_tipos)
        self.combo_tipo_historial.set(
            tipo_actual if tipo_actual in valores_tipos else TODOS
        )
        self.aplicar_filtros_historial()

    def aplicar_filtros(self, _evento=None):
        try:
            resultado = calcular_estadisticas(
                self.movimientos,
                proyecto=self.combo_proyecto.get() or TODOS,
                tipo_movimiento=self.combo_tipo.get() or TODOS,
                desde=self.entry_desde.get().strip(),
                hasta=self.entry_hasta.get().strip(),
                limite=self.combo_limite.get(),
            )
        except ValueError as error:
            messagebox.showwarning("Filtros inválidos", str(error), parent=self.winfo_toplevel())
            return

        self.card_cantidad.configure(text=f"{resultado['cantidad_total']:,}".replace(",", "."))
        self.card_productos.configure(text=str(resultado["productos_distintos"]))
        self.card_proyectos.configure(text=str(resultado["proyectos_distintos"]))
        self.card_valor.configure(text=self.formatear_pesos(resultado["valor_total"]))
        self.grafico_productos.actualizar(resultado["productos"])
        self.grafico_tendencia.actualizar(resultado["tendencia"])
        desglose = " · ".join(
            f"{item['etiqueta']}: {item['cantidad']}" for item in resultado["tipos"]
        ) or "Sin movimientos de uso para los filtros seleccionados."
        self.label_desglose.configure(text=f"Desglose: {desglose}")
        self.label_estado.configure(
            text=f"{resultado['total_movimientos']} movimientos considerados",
            text_color=color_estado("ok" if resultado["total_movimientos"] else "suave"),
        )

    def limpiar_filtros(self):
        self.combo_proyecto.set(TODOS)
        self.combo_tipo.set(TODOS)
        self.combo_limite.set("10")
        for entrada in (self.entry_desde, self.entry_hasta):
            entrada.delete(0, "end")
        self.aplicar_filtros()

    def aplicar_filtros_historial(self, _evento=None):
        articulo = self.selector_articulo.get_selected()
        if articulo is None:
            self.limpiar_resultados_historial()
            self.label_estado_historial.configure(
                text="Seleccione un artículo de la lista.",
                text_color=color_estado("suave"),
            )
            return

        try:
            resultado = calcular_historial_articulo(
                self.movimientos,
                articulo["clave"],
                proyecto=self.combo_proyecto_historial.get() or TODOS,
                tipo_movimiento=self.combo_tipo_historial.get() or TODOS,
                desde=self.entry_desde_historial.get().strip(),
                hasta=self.entry_hasta_historial.get().strip(),
            )
        except ValueError as error:
            messagebox.showwarning(
                "Filtros inválidos", str(error), parent=self.winfo_toplevel()
            )
            return

        self.limpiar_resultados_historial()
        for indice, fila in enumerate(resultado["filas"]):
            anterior = fila["stock_anterior"]
            nuevo = fila["stock_nuevo"]
            if anterior is not None and nuevo is not None:
                stock = f"{anterior} → {nuevo}"
            elif nuevo is not None:
                stock = str(nuevo)
            else:
                stock = "-"
            self.tabla_historial_articulo.insert(
                "",
                "end",
                values=(
                    fila["fecha_texto"],
                    fila["tipo_movimiento"],
                    fila["cantidad"],
                    fila["trabajador"],
                    fila["proyecto"],
                    fila["registrado_por"],
                    stock,
                    fila["comentario"],
                ),
                tags=("par" if indice % 2 == 0 else "impar",),
            )

        self.card_movimientos_articulo.configure(text=str(resultado["movimientos"]))
        self.card_retirado_articulo.configure(text=str(resultado["total_retirado"]))
        self.card_devuelto_articulo.configure(text=str(resultado["total_devuelto"]))
        balance = resultado["saldo_movimientos"]
        self.card_saldo_articulo.configure(
            text=f"{balance:+d}" if balance else "0"
        )
        self.label_estado_historial.configure(
            text=f"{resultado['movimientos']} movimientos encontrados.",
            text_color=color_estado("ok" if resultado["movimientos"] else "suave"),
        )

    def limpiar_resultados_historial(self):
        for item in self.tabla_historial_articulo.get_children():
            self.tabla_historial_articulo.delete(item)
        for tarjeta in (
            self.card_movimientos_articulo,
            self.card_retirado_articulo,
            self.card_devuelto_articulo,
            self.card_saldo_articulo,
        ):
            tarjeta.configure(text="0")

    def limpiar_filtros_historial(self):
        self.combo_proyecto_historial.set(TODOS)
        self.combo_tipo_historial.set(TODOS)
        for entrada in (
            self.entry_desde_historial,
            self.entry_hasta_historial,
        ):
            entrada.delete(0, "end")
        self.aplicar_filtros_historial()

    def actualizar_selector_precios(self):
        filas = self.historial_precios.get("filas", [])
        seleccionado = self.selector_precio_articulo.get_selected()
        clave_actual = seleccionado.get("clave") if seleccionado else None
        articulos_por_clave = {}
        for cambio in filas:
            clave = cambio.get("producto_id") or str(
                cambio.get("producto_nombre") or "Producto eliminado"
            ).casefold()
            articulos_por_clave.setdefault(clave, {
                "clave": clave,
                "producto": cambio.get("producto_nombre") or "Producto eliminado",
            })
        articulos = sorted(
            articulos_por_clave.values(), key=lambda item: item["producto"].casefold()
        )
        opciones = [{
            "clave": None,
            "producto": "Todos los artículos",
            "etiqueta": "Todos los artículos",
        }]
        repeticiones = {}
        for item in articulos:
            nombre = item["producto"].casefold()
            repeticiones[nombre] = repeticiones.get(nombre, 0) + 1
        for item in articulos:
            item["etiqueta"] = item["producto"]
            if repeticiones[item["producto"].casefold()] > 1:
                item["etiqueta"] = f"{item['producto']} · ID {item['clave']}"
            opciones.append(item)
        self.selector_precio_articulo.set_items(opciones)
        opcion = next(
            (item for item in opciones if item["clave"] == clave_actual), opciones[0]
        )
        self.selector_precio_articulo.set(opcion["etiqueta"])
        self.aplicar_filtros_precios()

    def aplicar_filtros_precios(self, _evento=None):
        if not self.historial_precios.get("disponible"):
            self.limpiar_resultados_precios()
            self.label_estado_precios.configure(
                text=self.historial_precios.get("error") or "Historial no disponible.",
                text_color=color_estado("error"),
            )
            return

        seleccion = self.selector_precio_articulo.get_selected()
        if seleccion is None:
            self.label_estado_precios.configure(
                text="Seleccione un artículo de la lista.",
                text_color=color_estado("alerta"),
            )
            return
        clave = seleccion.get("clave") if seleccion else None
        try:
            resultado = calcular_historial_precios(
                self.historial_precios.get("filas", []),
                producto_clave=clave,
                direccion=self.combo_direccion_precio.get() or TODOS,
                desde=self.entry_desde_precio.get().strip(),
                hasta=self.entry_hasta_precio.get().strip(),
            )
        except ValueError as error:
            messagebox.showwarning(
                "Filtros inválidos", str(error), parent=self.winfo_toplevel()
            )
            return

        self.limpiar_resultados_precios()
        for fila in resultado["filas"]:
            diferencia = fila["diferencia"]
            porcentaje = fila["porcentaje"]
            self.tabla_precios.insert(
                "", "end",
                values=(
                    fila["fecha_texto"],
                    fila["producto"],
                    self.formatear_pesos(fila["precio_anterior"]),
                    self.formatear_pesos(fila["precio_nuevo"]),
                    self.formatear_diferencia(diferencia),
                    f"{porcentaje:+.1f}%" if porcentaje is not None else "-",
                    fila["usuario"],
                ),
                tags=("aumento" if diferencia > 0 else "disminucion",),
            )
        self.card_productos_precio.configure(text=str(resultado["productos"]))
        self.card_cambios_precio.configure(text=str(resultado["cambios"]))
        self.card_aumentos_precio.configure(text=str(resultado["aumentos"]))
        self.card_disminuciones_precio.configure(text=str(resultado["disminuciones"]))
        self.label_estado_precios.configure(
            text=f"{resultado['cambios']} cambios de precio encontrados.",
            text_color=color_estado("ok" if resultado["cambios"] else "suave"),
        )

    def limpiar_resultados_precios(self):
        for item in self.tabla_precios.get_children():
            self.tabla_precios.delete(item)
        for tarjeta in (
            self.card_productos_precio,
            self.card_cambios_precio,
            self.card_aumentos_precio,
            self.card_disminuciones_precio,
        ):
            tarjeta.configure(text="0")

    def limpiar_filtros_precios(self):
        self.selector_precio_articulo.set("Todos los artículos")
        self.combo_direccion_precio.set(TODOS)
        for entrada in (self.entry_desde_precio, self.entry_hasta_precio):
            entrada.delete(0, "end")
        self.aplicar_filtros_precios()

    @classmethod
    def formatear_diferencia(cls, valor):
        prefijo = "+" if valor > 0 else ""
        return prefijo + cls.formatear_pesos(valor)

    def aplicar_zoom(self, escala):
        self.escala_zoom = escala
        for grafico in (
            self.grafico_productos,
            self.grafico_tendencia,
        ):
            grafico.aplicar_zoom(escala)

    def aplicar_tema(self):
        for grafico in (
            self.grafico_productos,
            self.grafico_tendencia,
        ):
            grafico.aplicar_tema()
        estilizar_treeview(self.tabla_historial_articulo)
        estilizar_treeview(self.tabla_precios)
        self.tabla_precios.tag_configure(
            "aumento", background=color_actual(PALETA["stock_bajo"])
        )
        self.tabla_precios.tag_configure(
            "disminucion",
            background=color_actual(PALETA["stock_critico"]),
            foreground=color_actual(PALETA["peligro"]),
        )

    @staticmethod
    def formatear_pesos(valor):
        return f"${float(valor or 0):,.0f}".replace(",", ".")
