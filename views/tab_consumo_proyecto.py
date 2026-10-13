import customtkinter as ctk
from tkinter import ttk, messagebox
import threading
import unicodedata
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from decimal import Decimal, InvalidOperation
from utils.ui_theme import (
    PALETA,
    color_estado,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)


class ConsumoProyectoTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")

        self.db = db_manager
        iniciar_despachador_ui(self)
        self.proyectos = []
        self._carga_consumo_id = 0
        self._carga_proyectos_id = 0

        self.crear_interfaz()
        self.after(2500, self.cargar_proyectos)

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # =====================================================
        # BARRA SUPERIOR
        # =====================================================
        frame_top = ctk.CTkFrame(self, **estilos_barra())
        frame_top.grid(row=0, column=0, sticky="ew", padx=15, pady=10)

        fila_titulo = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_titulo.pack(fill="x", padx=12, pady=(10, 4))

        fila_controles = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_controles.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(
            fila_titulo,
            text="Consumo por Proyecto",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETA["primario"]
        ).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(
            fila_controles,
            text="Proyecto:"
        ).pack(side="left", padx=(5, 5))

        self.combo_proyecto = ctk.CTkComboBox(
            fila_controles,
            values=[],
            width=260,
            state="readonly"
        )
        self.combo_proyecto.pack(side="left", padx=5)

        ctk.CTkButton(
            fila_controles,
            text="Actualizar",
            width=110,
            **estilos_boton("primario"),
            command=self.cargar_consumo
        ).pack(side="left", padx=10)

        self.label_estado = ctk.CTkLabel(
            fila_titulo,
            text="",
            text_color=color_estado("suave")
        )
        self.label_estado.pack(side="right", padx=10)

        # =====================================================
        # TARJETAS RESUMEN
        # =====================================================
        frame_resumen = ctk.CTkFrame(self, **estilos_panel())
        frame_resumen.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        frame_resumen.grid_columnconfigure((0, 1, 2), weight=1)

        self.card_productos = self.crear_card_resumen(
            frame_resumen,
            "Productos distintos",
            "0",
            0
        )

        self.card_cantidad = self.crear_card_resumen(
            frame_resumen,
            "Cantidad consumida",
            "0",
            1
        )

        self.card_valor = self.crear_card_resumen(
            frame_resumen,
            "Valor estimado",
            "$0",
            2
        )

        # =====================================================
        # ARTICULOS UTILIZADOS
        # =====================================================
        frame_articulos = ctk.CTkFrame(self, **estilos_panel())
        frame_articulos.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=15,
            pady=(0, 10)
        )

        ctk.CTkLabel(
            frame_articulos,
            text="Artículos utilizados",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETA["texto"]
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.texto_articulos = ctk.CTkTextbox(
            frame_articulos,
            height=84,
            wrap="word",
            fg_color=PALETA["panel_alt"],
            border_color=PALETA["borde"],
            border_width=1,
            text_color=PALETA["texto"],
            font=ctk.CTkFont(size=14)
        )
        self.texto_articulos.pack(fill="x", padx=14, pady=(0, 10))
        self.texto_articulos.insert(
            "1.0",
            "Sin consumos registrados para este proyecto."
        )
        self.texto_articulos.configure(state="disabled")

        # =====================================================
        # TABLAS
        # =====================================================
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=PALETA["panel"],
            segmented_button_fg_color=PALETA["primario_suave"],
            segmented_button_selected_color=PALETA["primario"],
            segmented_button_selected_hover_color=PALETA["primario_hover"],
            segmented_button_unselected_color=PALETA["primario_suave"],
            segmented_button_unselected_hover_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self.tabview.grid(row=3, column=0, sticky="nsew", padx=15, pady=(0, 15))

        self.tab_resumen = self.tabview.add("Resumen por Producto")
        self.tab_historial = self.tabview.add("Historial Detallado")

        self.crear_tabla_resumen()
        self.crear_tabla_historial()

    def crear_card_resumen(self, parent, titulo, valor, columna):
        frame = ctk.CTkFrame(parent, **estilos_panel())
        frame.grid(row=0, column=columna, padx=8, pady=10, sticky="ew")

        label_titulo = ctk.CTkLabel(
            frame,
            text=titulo,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETA["texto_suave"]
        )
        label_titulo.pack(pady=(12, 3))

        label_valor = ctk.CTkLabel(
            frame,
            text=valor,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=PALETA["primario"]
        )
        label_valor.pack(pady=(0, 12))

        return label_valor

    def crear_tabla_resumen(self):
        frame = ctk.CTkFrame(self.tab_resumen, **estilos_panel())
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ctk.CTkScrollbar(frame, orientation="vertical")
        scrollbar.pack(side="right", fill="y")

        columnas = (
            "Producto",
            "Código",
            "Categoría",
            "Ubicación",
            "Cantidad",
            "Precio Unit. Prom.",
            "Valor Total"
        )

        self.tabla_resumen = ttk.Treeview(
            frame,
            columns=columnas,
            show="headings",
            yscrollcommand=scrollbar.set
        )
        estilizar_treeview(self.tabla_resumen)

        scrollbar.configure(command=self.tabla_resumen.yview)

        anchos = {
            "Producto": 240,
            "Código": 130,
            "Categoría": 130,
            "Ubicación": 160,
            "Cantidad": 90,
            "Precio Unit. Prom.": 130,
            "Valor Total": 130
        }

        for col in columnas:
            self.tabla_resumen.heading(col, text=col)
            self.tabla_resumen.column(col, width=anchos[col], anchor="center")

        self.tabla_resumen.pack(fill="both", expand=True)

    def crear_tabla_historial(self):
        frame = ctk.CTkFrame(self.tab_historial, **estilos_panel())
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ctk.CTkScrollbar(frame, orientation="vertical")
        scrollbar.pack(side="right", fill="y")

        columnas = (
            "Fecha",
            "Producto",
            "Código",
            "Movimiento",
            "Cantidad",
            "Precio Unitario",
            "Valor Total",
            "Responsable",
            "Ubicación"
        )

        self.tabla_historial = ttk.Treeview(
            frame,
            columns=columnas,
            show="headings",
            yscrollcommand=scrollbar.set
        )
        estilizar_treeview(self.tabla_historial)

        scrollbar.configure(command=self.tabla_historial.yview)

        anchos = {
            "Fecha": 130,
            "Producto": 220,
            "Código": 120,
            "Movimiento": 170,
            "Cantidad": 80,
            "Precio Unitario": 120,
            "Valor Total": 110,
            "Responsable": 160,
            "Ubicación": 160
        }

        for col in columnas:
            self.tabla_historial.heading(col, text=col)
            self.tabla_historial.column(col, width=anchos[col], anchor="center")

        self.tabla_historial.pack(fill="both", expand=True)

    # ============================================================
    # CARGA DE PROYECTOS
    # ============================================================
    def cargar_proyectos(self):
        self._carga_proyectos_id += 1
        self.label_estado.configure(text="Cargando proyectos...", text_color=color_estado("cargando"))
        threading.Thread(
            target=self._cargar_proyectos_pesado,
            args=(self._carga_proyectos_id,),
            daemon=True,
        ).start()
        return True

    def _cargar_proyectos_pesado(self, carga_id):
        try:
            proyectos = self.db.cargar_proyectos()
            ejecutar_en_ui(self, self._actualizar_proyectos_ui, proyectos, carga_id)
        except Exception as e:
            print(f"Error cargando proyectos en consumo: {e}")
            ejecutar_en_ui(self, self._actualizar_proyectos_ui, None, carga_id)

    def _actualizar_proyectos_ui(self, proyectos, carga_id):
        if carga_id != self._carga_proyectos_id:
            return
        if proyectos is None:
            self.label_estado.configure(
                text="Error cargando proyectos.",
                text_color=color_estado("error")
            )
            return
        actual = self.combo_proyecto.get()
        self.proyectos = list(proyectos or [])
        self.combo_proyecto.configure(values=self.proyectos)
        self.combo_proyecto.set(actual if actual in self.proyectos else next(iter(self.proyectos), ""))
        if self.proyectos:
            self.cargar_consumo()
        else:
            self.label_estado.configure(text="Sin proyectos disponibles.", text_color=color_estado("info"))

    # ============================================================
    # CARGA DE CONSUMO
    # ============================================================
    def cargar_consumo(self):
        proyecto = self.combo_proyecto.get()

        if not proyecto:
            return messagebox.showwarning(
                "Aviso",
                "Seleccione un proyecto."
            )

        self.label_estado.configure(
            text="Cargando consumo...",
            text_color=color_estado("cargando")
        )
        self._carga_consumo_id += 1
        carga_id = self._carga_consumo_id

        threading.Thread(
            target=self.cargar_consumo_pesado,
            args=(proyecto, carga_id),
            daemon=True
        ).start()

    def cargar_consumo_pesado(self, proyecto, carga_id):
        try:
            resumen = self.db.obtener_resumen_consumo_proyecto(proyecto)
            historial = self.db.obtener_historial_consumo_proyecto(proyecto)
            articulos = self.agrupar_articulos(resumen)
            totales = {
                "productos_distintos": len(articulos),
                "cantidad_total": sum(int(fila[4] or 0) for fila in resumen),
                "valor_total": sum(
                    self.convertir_importe(fila[6])
                    for fila in resumen
                )
            }

            ejecutar_en_ui(
                self,
                self.actualizar_interfaz,
                resumen,
                historial,
                totales,
                proyecto,
                carga_id
            )

        except Exception as e:
            print(f"Error cargando consumo pesado: {e}")
            try:
                ejecutar_en_ui(
                    self,
                    self.label_estado.configure,
                    text="Error cargando consumo.",
                    text_color=color_estado("error")
                )
            except Exception:
                pass

    def actualizar_interfaz(
        self,
        resumen,
        historial,
        totales,
        proyecto,
        carga_id
    ):
        try:
            if (
                carga_id != self._carga_consumo_id
                or proyecto != self.combo_proyecto.get()
            ):
                return

            for item in self.tabla_resumen.get_children():
                self.tabla_resumen.delete(item)

            for item in self.tabla_historial.get_children():
                self.tabla_historial.delete(item)

            for fila in resumen:
                fila_formateada = (
                    fila[0],
                    fila[1],
                    fila[2],
                    fila[3],
                    fila[4],
                    self.formatear_pesos(fila[5]),
                    self.formatear_pesos(fila[6])
                )

                self.tabla_resumen.insert("", "end", values=fila_formateada)

            for fila in historial:
                fila_formateada = (
                    fila[0],
                    fila[1],
                    fila[2],
                    fila[3],
                    fila[4],
                    self.formatear_pesos(fila[5]),
                    self.formatear_pesos(fila[6]),
                    fila[7],
                    fila[8]
                )

                self.tabla_historial.insert("", "end", values=fila_formateada)

            self.card_productos.configure(
                text=str(totales.get("productos_distintos", 0))
            )

            self.card_cantidad.configure(
                text=str(totales.get("cantidad_total", 0))
            )

            self.card_valor.configure(
                text=self.formatear_pesos(totales.get("valor_total", 0))
            )

            self.actualizar_articulos_utilizados(resumen)

            self.label_estado.configure(
                text="Consumo actualizado.",
                text_color=color_estado("ok")
            )

        except Exception as e:
            print(f"Error actualizando consumo: {e}")
            self.label_estado.configure(
                text="Error actualizando vista.",
                text_color=color_estado("error")
            )

    def formatear_pesos(self, valor):
        try:
            importe = self.convertir_importe(valor)
            if importe == importe.to_integral_value():
                return "$" + f"{int(importe):,}".replace(",", ".")

            texto = f"{importe:,.2f}"
            texto = texto.replace(",", "#").replace(".", ",").replace("#", ".")
            return "$" + texto
        except (InvalidOperation, TypeError, ValueError):
            return "$0"

    @staticmethod
    def convertir_importe(valor):
        if valor is None or valor == "":
            return Decimal("0")
        return Decimal(str(valor))

    @staticmethod
    def agrupar_articulos(resumen):
        agrupados = {}

        for fila in resumen:
            nombre = str(fila[0] or "Artículo sin nombre").strip()
            clave = unicodedata.normalize("NFKD", nombre)
            clave = "".join(
                caracter for caracter in clave
                if not unicodedata.combining(caracter)
            ).casefold()

            if clave not in agrupados:
                agrupados[clave] = [nombre, 0]

            agrupados[clave][1] += int(fila[4] or 0)

        return sorted(
            (tuple(datos) for datos in agrupados.values()),
            key=lambda articulo: (-articulo[1], articulo[0].casefold())
        )

    @classmethod
    def formatear_articulos_utilizados(cls, resumen):
        articulos = cls.agrupar_articulos(resumen)
        if not articulos:
            return "Sin consumos registrados para este proyecto."

        return "\n".join(
            f"{nombre} × {cantidad}"
            for nombre, cantidad in articulos
        )

    def actualizar_articulos_utilizados(self, resumen):
        texto = self.formatear_articulos_utilizados(resumen)
        self.texto_articulos.configure(state="normal")
        self.texto_articulos.delete("1.0", "end")
        self.texto_articulos.insert("1.0", texto)
        self.texto_articulos.configure(state="disabled")
        
    def actualizar_proyectos(self):
        return self.cargar_proyectos()
