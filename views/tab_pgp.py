import threading
import unicodedata

import customtkinter as ctk
from utils.ui_windows import VentanaAdaptable
from tkinter import messagebox, ttk

from utils.pgp import (
    TIPO_ENTREGA_PGP,
    TIPO_PRESTAMO_PGP,
    TIPOS_MOVIMIENTO_PGP,
    cantidad_pendiente_item_pgp,
    preparar_items_pgp,
)
from utils.searchable_combobox import SearchableCombobox
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.ui_theme import (
    PALETA,
    color_estado,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)


class PgpTab(ctk.CTkFrame):
    TODOS = "Todos"
    ESTADOS = (
        TODOS,
        "Despachado",
        "Entregado",
        "Devolución parcial",
        "Cerrado",
    )

    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        iniciar_despachador_ui(self)

        self.productos = []
        self.trabajadores = []
        self.items_carga = []
        self.contenedores = []
        self.pgp_por_id = {}
        self.item_pgp_por_id = {}
        self._carga_selectores_id = 0
        self._carga_historial_id = 0
        self._guardando = False
        self._pgp_a_reseleccionar = None

        self.crear_interfaz()
        self.after(500, self.iniciar_carga_selectores)
        self.after(700, self.iniciar_carga_historial)

    @staticmethod
    def normalizar(valor):
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        return "".join(
            caracter for caracter in texto
            if not unicodedata.combining(caracter)
        ).casefold()

    @staticmethod
    def etiqueta_producto(producto):
        nombre = producto.get("nombre") or "Artículo sin nombre"
        categoria = producto.get("categoria") or "Sin categoría"
        stock = int(producto.get("stock") or 0)
        return f"{nombre} · {categoria} · Stock {stock}"

    @staticmethod
    def texto_busqueda_producto(producto):
        return " ".join(str(producto.get(campo) or "") for campo in (
            "nombre", "categoria", "ubicacion_codigo"
        ))

    @staticmethod
    def etiqueta_trabajador(trabajador):
        nombre = trabajador.get("nombre") or "Trabajador sin nombre"
        rut = trabajador.get("rut") or "Sin RUT"
        return f"{nombre} · {rut}"

    @staticmethod
    def texto_busqueda_trabajador(trabajador):
        return " ".join(str(trabajador.get(campo) or "") for campo in (
            "nombre", "rut", "cargo"
        ))

    def crear_interfaz(self):
        self.pack_propagate(False)
        self.tabview = ctk.CTkTabview(
            self,
            fg_color="transparent",
            segmented_button_fg_color=PALETA["primario_suave"],
            segmented_button_selected_color=PALETA["primario"],
            segmented_button_selected_hover_color=PALETA["primario_hover"],
            segmented_button_unselected_color=PALETA["primario_suave"],
            segmented_button_unselected_hover_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_nuevo = self.tabview.add("Nuevo PGP")
        self.tab_historial = self.tabview.add("Historial PGP")
        self.crear_tab_nuevo()
        self.crear_tab_historial()

    def crear_tab_nuevo(self):
        self.tab_nuevo.grid_columnconfigure(0, weight=1)
        self.tab_nuevo.grid_rowconfigure(1, weight=1)

        encabezado = ctk.CTkFrame(self.tab_nuevo, **estilos_barra())
        encabezado.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        encabezado.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            encabezado,
            text="Preparar contenedor para proyecto",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETA["primario"],
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            encabezado,
            text=(
                "Agrupe entregas y préstamos en un solo despacho. "
                "El stock se actualizará al registrar el PGP."
            ),
            text_color=PALETA["texto_suave"],
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))
        self.label_estado_nuevo = ctk.CTkLabel(
            encabezado,
            text="Cargando datos...",
            text_color=color_estado("cargando"),
        )
        self.label_estado_nuevo.grid(
            row=0, column=1, rowspan=2, sticky="e", padx=14
        )

        contenido = ctk.CTkFrame(self.tab_nuevo, fg_color="transparent")
        contenido.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        contenido.grid_columnconfigure(0, weight=0, minsize=390)
        contenido.grid_columnconfigure(1, weight=1)
        contenido.grid_rowconfigure(0, weight=1)

        formulario = ctk.CTkScrollableFrame(
            contenido,
            width=370,
            **estilos_panel(),
        )
        formulario.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(
            formulario,
            text="Datos del despacho",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 8))

        ctk.CTkLabel(formulario, text="Proyecto / destino (escriba para buscar):").pack(
            anchor="w", padx=12
        )
        self.combo_proyecto = SearchableCombobox(
            formulario,
            label_getter=str,
            width=42,
            font=("Segoe UI", 11),
        )
        self.combo_proyecto.pack(fill="x", padx=12, pady=(3, 10))
        self.combo_proyecto.set("")

        ctk.CTkLabel(
            formulario,
            text="Responsable (obligatorio si hay préstamos):",
        ).pack(anchor="w", padx=12)
        self.combo_trabajador = SearchableCombobox(
            formulario,
            label_getter=self.etiqueta_trabajador,
            search_getter=self.texto_busqueda_trabajador,
            width=42,
            font=("Segoe UI", 11),
        )
        self.combo_trabajador.pack(fill="x", padx=12, pady=(3, 5), ipady=5)
        ctk.CTkButton(
            formulario,
            text="Sin responsable",
            height=30,
            **estilos_boton("secundario"),
            command=self.combo_trabajador.clear,
        ).pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(formulario, text="Observación general (opcional):").pack(
            anchor="w", padx=12
        )
        self.texto_observacion = ctk.CTkTextbox(
            formulario,
            height=72,
            wrap="word",
            fg_color=PALETA["panel_alt"],
            border_color=PALETA["borde"],
            border_width=1,
        )
        self.texto_observacion.pack(fill="x", padx=12, pady=(3, 14))

        ctk.CTkLabel(
            formulario,
            text="Agregar artículo",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(6, 8))
        ctk.CTkLabel(formulario, text="Artículo:").pack(anchor="w", padx=12)
        self.combo_producto = SearchableCombobox(
            formulario,
            label_getter=self.etiqueta_producto,
            search_getter=self.texto_busqueda_producto,
            width=42,
            font=("Segoe UI", 11),
        )
        self.combo_producto.pack(fill="x", padx=12, pady=(3, 10), ipady=5)

        ctk.CTkLabel(formulario, text="Tipo de salida:").pack(
            anchor="w", padx=12
        )
        self.combo_tipo = ctk.CTkComboBox(
            formulario,
            values=list(TIPOS_MOVIMIENTO_PGP),
            state="readonly",
            height=38,
        )
        self.combo_tipo.set(TIPO_ENTREGA_PGP)
        self.combo_tipo.pack(fill="x", padx=12, pady=(3, 10))

        ctk.CTkLabel(formulario, text="Cantidad:").pack(anchor="w", padx=12)
        self.entry_cantidad = ctk.CTkEntry(
            formulario,
            placeholder_text="Ej: 1",
            height=38,
        )
        self.entry_cantidad.insert(0, "1")
        self.entry_cantidad.pack(fill="x", padx=12, pady=(3, 10))

        ctk.CTkButton(
            formulario,
            text="Agregar al contenedor",
            height=42,
            **estilos_boton("primario"),
            command=self.agregar_item,
        ).pack(fill="x", padx=12, pady=(4, 14))

        panel_carga = ctk.CTkFrame(contenido, **estilos_panel())
        panel_carga.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        panel_carga.grid_columnconfigure(0, weight=1)
        panel_carga.grid_rowconfigure(1, weight=1)

        cabecera_carga = ctk.CTkFrame(panel_carga, fg_color="transparent")
        cabecera_carga.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        ctk.CTkLabel(
            cabecera_carga,
            text="Contenido del PGP",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")
        self.label_resumen_carga = ctk.CTkLabel(
            cabecera_carga,
            text="0 artículos · 0 unidades",
            text_color=PALETA["texto_suave"],
        )
        self.label_resumen_carga.pack(side="right")

        frame_tabla = ctk.CTkFrame(panel_carga, fg_color="transparent")
        frame_tabla.grid(row=1, column=0, sticky="nsew", padx=12)
        frame_tabla.grid_columnconfigure(0, weight=1)
        frame_tabla.grid_rowconfigure(0, weight=1)
        columnas = ("ID", "Artículo", "Tipo", "Cantidad", "Stock")
        self.tabla_carga = ttk.Treeview(
            frame_tabla,
            columns=columnas,
            displaycolumns=columnas[1:],
            show="headings",
        )
        estilizar_treeview(self.tabla_carga)
        anchos = {
            "Artículo": 280,
            "Tipo": 190,
            "Cantidad": 85,
            "Stock": 85,
        }
        for columna in columnas:
            self.tabla_carga.heading(columna, text=columna)
        for columna in columnas[1:]:
            self.tabla_carga.column(
                columna, width=anchos[columna], anchor="center"
            )
        barra = ctk.CTkScrollbar(
            frame_tabla,
            orientation="vertical",
            command=self.tabla_carga.yview,
        )
        self.tabla_carga.configure(yscrollcommand=barra.set)
        self.tabla_carga.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns", padx=(4, 0))

        acciones = ctk.CTkFrame(panel_carga, fg_color="transparent")
        acciones.grid(row=2, column=0, sticky="ew", padx=12, pady=12)
        ctk.CTkButton(
            acciones,
            text="Quitar seleccionado",
            **estilos_boton("peligro"),
            command=self.quitar_item,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            acciones,
            text="Vaciar",
            **estilos_boton("secundario"),
            command=self.vaciar_carga,
        ).pack(side="left", padx=6)
        self.btn_despachar = ctk.CTkButton(
            acciones,
            text="Registrar y despachar PGP",
            height=42,
            **estilos_boton("exito"),
            command=self.registrar_pgp,
        )
        self.btn_despachar.pack(side="right", padx=(6, 0))

    def crear_tab_historial(self):
        self.tab_historial.grid_columnconfigure(0, weight=1)
        self.tab_historial.grid_rowconfigure(1, weight=1)

        filtros = ctk.CTkFrame(self.tab_historial, **estilos_barra())
        filtros.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        filtros.grid_columnconfigure(0, weight=1)

        self.entry_busqueda = ctk.CTkEntry(
            filtros,
            placeholder_text="Buscar PGP, proyecto, responsable o artículo...",
            height=38,
        )
        self.entry_busqueda.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.entry_busqueda.bind("<KeyRelease>", self.aplicar_filtros)
        self.combo_estado = ctk.CTkComboBox(
            filtros,
            values=list(self.ESTADOS),
            state="readonly",
            width=180,
            command=lambda _=None: self.aplicar_filtros(),
        )
        self.combo_estado.set(self.TODOS)
        self.combo_estado.grid(row=0, column=1, padx=6, pady=10)
        ctk.CTkButton(
            filtros,
            text="Actualizar",
            **estilos_boton("primario"),
            command=self.iniciar_carga_historial,
        ).grid(row=0, column=2, padx=(6, 10), pady=10)

        self.label_estado_historial = ctk.CTkLabel(
            filtros,
            text="",
            text_color=PALETA["texto_suave"],
        )
        self.label_estado_historial.grid(
            row=1, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 8)
        )

        contenido = ctk.CTkFrame(self.tab_historial, fg_color="transparent")
        contenido.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        contenido.grid_columnconfigure(0, weight=1)
        contenido.grid_rowconfigure(0, weight=3)
        contenido.grid_rowconfigure(1, weight=2)

        frame_pgp = ctk.CTkFrame(contenido, **estilos_panel())
        frame_pgp.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        frame_pgp.grid_columnconfigure(0, weight=1)
        frame_pgp.grid_rowconfigure(0, weight=1)
        columnas = (
            "ID", "PGP", "Fecha", "Proyecto", "Responsable",
            "Estado", "Artículos", "Unidades", "Pendientes", "Observación"
        )
        self.tabla_pgp = ttk.Treeview(
            frame_pgp,
            columns=columnas,
            displaycolumns=columnas[1:],
            show="headings",
        )
        estilizar_treeview(self.tabla_pgp)
        anchos = {
            "PGP": 135,
            "Fecha": 135,
            "Proyecto": 180,
            "Responsable": 180,
            "Estado": 125,
            "Artículos": 75,
            "Unidades": 75,
            "Pendientes": 85,
            "Observación": 240,
        }
        for columna in columnas:
            self.tabla_pgp.heading(columna, text=columna)
        for columna in columnas[1:]:
            self.tabla_pgp.column(
                columna, width=anchos[columna], anchor="center"
            )
        barra_y = ctk.CTkScrollbar(
            frame_pgp, orientation="vertical", command=self.tabla_pgp.yview
        )
        barra_x = ctk.CTkScrollbar(
            frame_pgp, orientation="horizontal", command=self.tabla_pgp.xview
        )
        self.tabla_pgp.configure(
            yscrollcommand=barra_y.set,
            xscrollcommand=barra_x.set,
        )
        self.tabla_pgp.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0))
        barra_y.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=(8, 0))
        barra_x.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(4, 8))
        self.tabla_pgp.bind("<<TreeviewSelect>>", self.mostrar_detalle_seleccionado)

        frame_detalle = ctk.CTkFrame(contenido, **estilos_panel())
        frame_detalle.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        frame_detalle.grid_columnconfigure(0, weight=1)
        frame_detalle.grid_rowconfigure(1, weight=1)
        cabecera = ctk.CTkFrame(frame_detalle, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        self.label_detalle = ctk.CTkLabel(
            cabecera,
            text="Seleccione un PGP para ver su contenido",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.label_detalle.pack(side="left")
        self.btn_devolver = ctk.CTkButton(
            cabecera,
            text="Registrar devolución",
            **estilos_boton("exito"),
            command=self.abrir_devolucion,
        )
        self.btn_devolver.pack(side="right")
        self.btn_devolver_todo = ctk.CTkButton(
            cabecera,
            text="Devolver todo",
            **estilos_boton("alerta"),
            command=self.abrir_devolucion_total,
        )
        self.btn_devolver_todo.pack(side="right", padx=(0, 8))
        self.btn_agregar_items = ctk.CTkButton(
            cabecera,
            text="Agregar artículos al PGP",
            **estilos_boton("primario"),
            command=self.abrir_agregar_articulos,
        )
        self.btn_agregar_items.pack(side="right", padx=(0, 8))

        columnas_detalle = (
            "ID", "Artículo", "Tipo", "Fecha salida",
            "Enviado", "Devuelto", "Pendiente"
        )
        self.tabla_detalle = ttk.Treeview(
            frame_detalle,
            columns=columnas_detalle,
            displaycolumns=columnas_detalle[1:],
            show="headings",
            height=6,
        )
        estilizar_treeview(self.tabla_detalle)
        anchos_detalle = {
            "Artículo": 300,
            "Tipo": 190,
            "Fecha salida": 135,
            "Enviado": 85,
            "Devuelto": 85,
            "Pendiente": 85,
        }
        for columna in columnas_detalle:
            self.tabla_detalle.heading(columna, text=columna)
        for columna in columnas_detalle[1:]:
            self.tabla_detalle.column(
                columna,
                width=anchos_detalle[columna],
                anchor="center",
            )
        self.tabla_detalle.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=(0, 10)
        )

    def iniciar_carga_selectores(self):
        self._carga_selectores_id += 1
        carga_id = self._carga_selectores_id
        self.label_estado_nuevo.configure(
            text="Actualizando datos...",
            text_color=color_estado("cargando"),
        )
        threading.Thread(
            target=self._cargar_selectores_pesado,
            args=(carga_id,),
            daemon=True,
        ).start()

    def _cargar_selectores_pesado(self, carga_id):
        productos = self.db.cargar_productos_activos_selector()
        trabajadores = self.db.cargar_trabajadores_nube()
        proyectos = self.db.cargar_proyectos()
        ejecutar_en_ui(
            self,
            self._actualizar_selectores,
            productos,
            trabajadores,
            proyectos,
            carga_id,
        )

    def _actualizar_selectores(
        self, productos, trabajadores, proyectos, carga_id
    ):
        if carga_id != self._carga_selectores_id:
            return
        self.productos = list(productos or [])
        self.trabajadores = list(trabajadores or [])
        self.combo_producto.set_items(self.productos)
        self.combo_trabajador.set_items(self.trabajadores)
        proyectos = list(proyectos or [])
        self.combo_proyecto.set_items(proyectos)
        self.label_estado_nuevo.configure(
            text=f"{len(self.productos)} artículos disponibles",
            text_color=color_estado("ok"),
        )

    def agregar_item(self):
        producto = self.combo_producto.get_selected()
        if not producto:
            return messagebox.showwarning(
                "Artículo requerido",
                "Busque un artículo y selecciónelo desde la lista.",
                parent=self,
            )
        try:
            cantidad = int(self.entry_cantidad.get().strip())
        except ValueError:
            cantidad = 0

        item = {
            "producto": producto,
            "tipo_movimiento": self.combo_tipo.get(),
            "cantidad": cantidad,
        }
        try:
            preparar_items_pgp(self.items_carga + [item], "responsable-temporal")
        except ValueError as error:
            return messagebox.showwarning("No se puede agregar", str(error), parent=self)

        self.items_carga.append(item)
        self.combo_producto.clear()
        self.entry_cantidad.delete(0, "end")
        self.entry_cantidad.insert(0, "1")
        self.actualizar_tabla_carga()

    def actualizar_tabla_carga(self):
        for fila in self.tabla_carga.get_children():
            self.tabla_carga.delete(fila)
        for indice, item in enumerate(self.items_carga):
            producto = item["producto"]
            self.tabla_carga.insert(
                "",
                "end",
                values=(
                    producto.get("id"),
                    producto.get("nombre", "Artículo"),
                    item.get("tipo_movimiento"),
                    item.get("cantidad"),
                    int(producto.get("stock") or 0),
                ),
                tags=("par" if indice % 2 == 0 else "impar",),
            )
        unidades = sum(int(item.get("cantidad") or 0) for item in self.items_carga)
        self.label_resumen_carga.configure(
            text=(
                f"{len(self.items_carga)} "
                f"{'artículo' if len(self.items_carga) == 1 else 'artículos'} · "
                f"{unidades} unidades"
            )
        )

    def quitar_item(self):
        seleccion = self.tabla_carga.selection()
        if not seleccion:
            return messagebox.showwarning(
                "Aviso", "Seleccione un artículo de la carga.", parent=self
            )
        producto_id = str(self.tabla_carga.item(seleccion[0])["values"][0])
        self.items_carga = [
            item for item in self.items_carga
            if str(item["producto"].get("id")) != producto_id
        ]
        self.actualizar_tabla_carga()

    def vaciar_carga(self):
        self.items_carga.clear()
        self.actualizar_tabla_carga()

    def registrar_pgp(self):
        if self._guardando:
            return
        trabajador = self.combo_trabajador.get_selected()
        if self.combo_trabajador.get().strip() and not trabajador:
            return messagebox.showwarning(
                "Responsable inválido",
                "Seleccione al responsable desde la lista desplegable.",
                parent=self,
            )
        rut = trabajador.get("rut", "") if trabajador else ""
        try:
            preparar_items_pgp(self.items_carga, rut)
        except ValueError as error:
            return messagebox.showwarning("PGP incompleto", str(error), parent=self)

        proyecto = self.combo_proyecto.get_selected()
        if not proyecto:
            return messagebox.showwarning(
                "Proyecto requerido", "Busque un proyecto y selecciónelo desde la lista.", parent=self
            )

        observacion = self.texto_observacion.get("1.0", "end").strip()
        if len(observacion) > 1000:
            return messagebox.showwarning(
                "Observación extensa",
                "La observación puede tener como máximo 1.000 caracteres.",
                parent=self,
            )
        if not messagebox.askyesno(
            "Confirmar despacho",
            (
                f"Se registrarán {len(self.items_carga)} artículos para "
                f"{proyecto} y se descontará su stock.\n\n¿Continuar?"
            ),
            parent=self,
        ):
            return

        self._guardando = True
        self.btn_despachar.configure(state="disabled", text="Registrando PGP...")
        threading.Thread(
            target=self._registrar_pgp_pesado,
            args=(proyecto, rut, observacion, list(self.items_carga)),
            daemon=True,
        ).start()

    def _registrar_pgp_pesado(self, proyecto, rut, observacion, items):
        resultado = self.db.crear_pgp(proyecto, rut, observacion, items)
        ejecutar_en_ui(self, self._finalizar_registro_pgp, resultado)

    def _finalizar_registro_pgp(self, resultado):
        self._guardando = False
        self.btn_despachar.configure(
            state="normal", text="Registrar y despachar PGP"
        )
        exito, mensaje, _ = resultado
        if not exito:
            return messagebox.showerror("No se pudo registrar", mensaje, parent=self)

        messagebox.showinfo("PGP registrado", mensaje, parent=self)
        self.vaciar_carga()
        self.combo_proyecto.clear()
        self.combo_trabajador.clear()
        self.texto_observacion.delete("1.0", "end")
        self.iniciar_carga_selectores()
        self.iniciar_carga_historial()
        self.notificar_movimientos()
        self.tabview.set("Historial PGP")

    def iniciar_carga_historial(self):
        self._carga_historial_id += 1
        carga_id = self._carga_historial_id
        self.label_estado_historial.configure(
            text="Cargando PGP...",
            text_color=color_estado("cargando"),
        )
        threading.Thread(
            target=self._cargar_historial_pesado,
            args=(carga_id,),
            daemon=True,
        ).start()

    def _cargar_historial_pesado(self, carga_id):
        resultado = self.db.cargar_pgp_contenedores()
        ejecutar_en_ui(
            self, self._actualizar_historial, resultado, carga_id
        )

    def _actualizar_historial(self, resultado, carga_id):
        if carga_id != self._carga_historial_id:
            return
        if not resultado.get("disponible"):
            self.contenedores = []
            self.pgp_por_id = {}
            self.aplicar_filtros()
            self.label_estado_historial.configure(
                text=resultado.get("error") or "No se pudo cargar PGP.",
                text_color=color_estado("error"),
            )
            return

        self.contenedores = list(resultado.get("contenedores") or [])
        self.pgp_por_id = {
            str(pgp.get("id")): pgp for pgp in self.contenedores
        }
        self.aplicar_filtros()
        if self._pgp_a_reseleccionar:
            self._seleccionar_pgp_por_id(self._pgp_a_reseleccionar)
            self._pgp_a_reseleccionar = None
        self.label_estado_historial.configure(
            text=f"{len(self.contenedores)} PGP registrados.",
            text_color=color_estado("ok"),
        )

    def aplicar_filtros(self, event=None):
        texto = self.normalizar(self.entry_busqueda.get()).strip()
        palabras = texto.split()
        estado = self.combo_estado.get()
        filtrados = []
        for pgp in self.contenedores:
            if estado != self.TODOS and pgp.get("estado") != estado:
                continue
            buscable = self.normalizar(" ".join([
                str(pgp.get("codigo_pgp") or ""),
                str(pgp.get("proyecto_nombre") or ""),
                str(pgp.get("trabajador_nombre") or ""),
                str(pgp.get("observacion") or ""),
                " ".join(
                    str(item.get("producto_nombre") or "")
                    for item in pgp.get("items", [])
                ),
            ]))
            if palabras and not all(palabra in buscable for palabra in palabras):
                continue
            filtrados.append(pgp)

        for fila in self.tabla_pgp.get_children():
            self.tabla_pgp.delete(fila)
        for indice, pgp in enumerate(filtrados):
            self.tabla_pgp.insert(
                "",
                "end",
                values=(
                    pgp.get("id"),
                    pgp.get("codigo_pgp", "-"),
                    pgp.get("fecha", "-"),
                    pgp.get("proyecto_nombre", "-"),
                    pgp.get("trabajador_nombre") or "Sin responsable",
                    pgp.get("estado", "-"),
                    pgp.get("cantidad_items", 0),
                    pgp.get("cantidad_unidades", 0),
                    pgp.get("unidades_pendientes", 0),
                    pgp.get("observacion") or "-",
                ),
                tags=("par" if indice % 2 == 0 else "impar",),
            )
        self.mostrar_detalle(None)

    def _seleccionar_pgp_por_id(self, pgp_id):
        pgp_id = str(pgp_id)
        for fila in self.tabla_pgp.get_children():
            valores = self.tabla_pgp.item(fila)["values"]
            if valores and str(valores[0]) == pgp_id:
                self.tabla_pgp.selection_set(fila)
                self.tabla_pgp.focus(fila)
                self.tabla_pgp.see(fila)
                self.mostrar_detalle(self.pgp_por_id.get(pgp_id))
                return

    def mostrar_detalle_seleccionado(self, event=None):
        seleccion = self.tabla_pgp.selection()
        if not seleccion:
            return self.mostrar_detalle(None)
        pgp_id = str(self.tabla_pgp.item(seleccion[0])["values"][0])
        self.mostrar_detalle(self.pgp_por_id.get(pgp_id))

    def mostrar_detalle(self, pgp):
        for fila in self.tabla_detalle.get_children():
            self.tabla_detalle.delete(fila)
        self.item_pgp_por_id = {}
        if not pgp:
            self.label_detalle.configure(
                text="Seleccione un PGP para ver su contenido"
            )
            return
        self.label_detalle.configure(
            text=f"Contenido de {pgp.get('codigo_pgp', 'PGP')}"
        )
        for indice, item in enumerate(pgp.get("items", [])):
            item_id = str(item.get("id"))
            self.item_pgp_por_id[item_id] = item
            pendiente = cantidad_pendiente_item_pgp(item)
            devuelta = int(item.get("cantidad_devuelta") or 0)
            self.tabla_detalle.insert(
                "",
                "end",
                values=(
                    item_id,
                    item.get("producto_nombre", "Artículo"),
                    item.get("tipo_movimiento", "-"),
                    item.get("fecha_salida", "-"),
                    item.get("cantidad", 0),
                    devuelta,
                    pendiente,
                ),
                tags=("par" if indice % 2 == 0 else "impar",),
            )

    def abrir_agregar_articulos(self):
        seleccion = self.tabla_pgp.selection()
        if not seleccion:
            return messagebox.showwarning(
                "Selección requerida",
                "Seleccione el PGP al que desea agregar artículos.",
                parent=self,
            )

        pgp_id = str(self.tabla_pgp.item(seleccion[0])["values"][0])
        pgp = self.pgp_por_id.get(pgp_id)
        if not pgp:
            return

        ventana = VentanaAdaptable(self)
        ventana.title(f"Agregar artículos a {pgp.get('codigo_pgp', 'PGP')}")
        ventana.geometry("760x680")
        ventana.minsize(620, 560)
        ventana.grab_set()

        panel = ctk.CTkScrollableFrame(ventana, **estilos_panel())
        panel.pack(fill="both", expand=True, padx=12, pady=12)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel,
            text=f"Ampliar {pgp.get('codigo_pgp', 'PGP')}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETA["primario"],
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 3))
        ctk.CTkLabel(
            panel,
            text=(
                f"Proyecto: {pgp.get('proyecto_nombre', '-')}  ·  "
                f"Responsable: {pgp.get('trabajador_nombre') or 'Sin responsable'}"
            ),
            text_color=PALETA["texto_suave"],
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))

        combo_responsable = None
        if not pgp.get("trabajador_rut"):
            ctk.CTkLabel(
                panel,
                text="Responsable (requerido si agrega préstamos):",
            ).grid(row=2, column=0, sticky="w", padx=12)
            combo_responsable = SearchableCombobox(
                panel,
                label_getter=self.etiqueta_trabajador,
                search_getter=self.texto_busqueda_trabajador,
                width=55,
                font=("Segoe UI", 11),
            )
            combo_responsable.set_items(self.trabajadores)
            combo_responsable.grid(
                row=3, column=0, sticky="ew", padx=12, pady=(3, 10), ipady=5
            )
            fila_producto = 4
        else:
            fila_producto = 2

        ctk.CTkLabel(panel, text="Artículo:").grid(
            row=fila_producto, column=0, sticky="w", padx=12
        )
        combo_producto = SearchableCombobox(
            panel,
            label_getter=self.etiqueta_producto,
            search_getter=self.texto_busqueda_producto,
            width=55,
            font=("Segoe UI", 11),
        )
        combo_producto.set_items(self.productos)
        combo_producto.grid(
            row=fila_producto + 1,
            column=0,
            sticky="ew",
            padx=12,
            pady=(3, 10),
            ipady=5,
        )

        fila_datos = ctk.CTkFrame(panel, fg_color="transparent")
        fila_datos.grid(
            row=fila_producto + 2, column=0, sticky="ew", padx=12, pady=4
        )
        fila_datos.grid_columnconfigure((0, 1), weight=1)
        combo_tipo = ctk.CTkComboBox(
            fila_datos,
            values=list(TIPOS_MOVIMIENTO_PGP),
            state="readonly",
            height=38,
        )
        combo_tipo.set(TIPO_ENTREGA_PGP)
        combo_tipo.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        entry_cantidad = ctk.CTkEntry(
            fila_datos, placeholder_text="Cantidad", height=38
        )
        entry_cantidad.insert(0, "1")
        entry_cantidad.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        items_nuevos = []
        columnas = ("ID", "Artículo", "Tipo", "Cantidad", "Stock")
        tabla = ttk.Treeview(
            panel,
            columns=columnas,
            displaycolumns=columnas[1:],
            show="headings",
            height=7,
        )
        estilizar_treeview(tabla)
        for columna in columnas:
            tabla.heading(columna, text=columna)
        for columna, ancho in {
            "Artículo": 270,
            "Tipo": 190,
            "Cantidad": 80,
            "Stock": 80,
        }.items():
            tabla.column(columna, width=ancho, anchor="center")
        tabla.grid(
            row=fila_producto + 4,
            column=0,
            sticky="nsew",
            padx=12,
            pady=(6, 8),
        )

        def actualizar_tabla():
            for fila in tabla.get_children():
                tabla.delete(fila)
            for indice, item in enumerate(items_nuevos):
                producto = item["producto"]
                tabla.insert(
                    "",
                    "end",
                    values=(
                        producto.get("id"),
                        producto.get("nombre", "Artículo"),
                        item["tipo_movimiento"],
                        item["cantidad"],
                        int(producto.get("stock") or 0),
                    ),
                    tags=("par" if indice % 2 == 0 else "impar",),
                )

        def agregar():
            producto = combo_producto.get_selected()
            if not producto:
                return messagebox.showwarning(
                    "Artículo requerido",
                    "Busque y seleccione el artículo.",
                    parent=ventana,
                )
            try:
                cantidad = int(entry_cantidad.get().strip())
            except ValueError:
                cantidad = 0
            item = {
                "producto": producto,
                "tipo_movimiento": combo_tipo.get(),
                "cantidad": cantidad,
            }
            try:
                preparar_items_pgp(
                    items_nuevos + [item], "responsable-temporal"
                )
            except ValueError as error:
                return messagebox.showwarning(
                    "No se puede agregar", str(error), parent=ventana
                )
            items_nuevos.append(item)
            combo_producto.clear()
            entry_cantidad.delete(0, "end")
            entry_cantidad.insert(0, "1")
            actualizar_tabla()

        ctk.CTkButton(
            panel,
            text="Agregar a esta salida",
            **estilos_boton("primario"),
            command=agregar,
        ).grid(
            row=fila_producto + 3, column=0, sticky="ew", padx=12, pady=(2, 4)
        )

        def quitar():
            seleccion_item = tabla.selection()
            if not seleccion_item:
                return
            producto_id = str(tabla.item(seleccion_item[0])["values"][0])
            items_nuevos[:] = [
                item for item in items_nuevos
                if str(item["producto"].get("id")) != producto_id
            ]
            actualizar_tabla()

        ctk.CTkButton(
            panel,
            text="Quitar seleccionado",
            **estilos_boton("secundario"),
            command=quitar,
        ).grid(
            row=fila_producto + 5, column=0, sticky="w", padx=12, pady=(0, 10)
        )

        ctk.CTkLabel(panel, text="Observación de esta salida (opcional):").grid(
            row=fila_producto + 6, column=0, sticky="w", padx=12
        )
        texto_observacion = ctk.CTkTextbox(
            panel,
            height=70,
            fg_color=PALETA["panel_alt"],
            border_color=PALETA["borde"],
            border_width=1,
        )
        texto_observacion.grid(
            row=fila_producto + 7, column=0, sticky="ew", padx=12, pady=(3, 10)
        )

        def confirmar():
            trabajador = (
                combo_responsable.get_selected()
                if combo_responsable is not None else None
            )
            if (
                combo_responsable is not None
                and combo_responsable.get().strip()
                and not trabajador
            ):
                return messagebox.showwarning(
                    "Responsable inválido",
                    "Seleccione al trabajador desde la lista.",
                    parent=ventana,
                )
            rut = (
                pgp.get("trabajador_rut")
                or (trabajador.get("rut") if trabajador else "")
            )
            try:
                preparar_items_pgp(items_nuevos, rut)
            except ValueError as error:
                return messagebox.showwarning(
                    "Salida incompleta", str(error), parent=ventana
                )
            observacion = texto_observacion.get("1.0", "end").strip()
            if len(observacion) > 1000:
                return messagebox.showwarning(
                    "Observación extensa",
                    "La observación puede tener como máximo 1.000 caracteres.",
                    parent=ventana,
                )
            unidades = sum(int(item["cantidad"]) for item in items_nuevos)
            if not messagebox.askyesno(
                "Confirmar nueva salida",
                (
                    f"Se agregarán {unidades} unidades a "
                    f"{pgp.get('codigo_pgp', 'PGP')} y se descontará su stock.\n\n"
                    "¿Continuar?"
                ),
                parent=ventana,
            ):
                return
            boton_confirmar.configure(state="disabled", text="Registrando...")
            threading.Thread(
                target=self._agregar_items_pgp_pesado,
                args=(
                    pgp,
                    rut,
                    observacion,
                    list(items_nuevos),
                    ventana,
                    boton_confirmar,
                ),
                daemon=True,
            ).start()

        boton_confirmar = ctk.CTkButton(
            panel,
            text="Confirmar salida adicional",
            height=44,
            **estilos_boton("exito"),
            command=confirmar,
        )
        boton_confirmar.grid(
            row=fila_producto + 8, column=0, sticky="ew", padx=12, pady=(4, 14)
        )

    def _agregar_items_pgp_pesado(
        self, pgp, rut, observacion, items, ventana, boton
    ):
        resultado = self.db.agregar_items_pgp(
            pgp.get("id"), rut, observacion, items
        )
        ejecutar_en_ui(
            self,
            self._finalizar_agregado_pgp,
            resultado,
            pgp.get("id"),
            ventana,
            boton,
        )

    def _finalizar_agregado_pgp(
        self, resultado, pgp_id, ventana, boton
    ):
        exito, mensaje, _ = resultado
        if not exito:
            if boton.winfo_exists():
                boton.configure(
                    state="normal", text="Confirmar salida adicional"
                )
            return messagebox.showerror("Error", mensaje, parent=ventana)
        if ventana.winfo_exists():
            ventana.destroy()
        self._pgp_a_reseleccionar = str(pgp_id)
        messagebox.showinfo("PGP actualizado", mensaje, parent=self)
        self.iniciar_carga_historial()
        self.iniciar_carga_selectores()
        self.notificar_movimientos()

    def abrir_devolucion(self):
        seleccion_pgp = self.tabla_pgp.selection()
        seleccion_item = self.tabla_detalle.selection()
        if not seleccion_pgp or not seleccion_item:
            return messagebox.showwarning(
                "Selección requerida",
                "Seleccione un PGP y luego el artículo que desea devolver.",
                parent=self,
            )
        pgp_id = str(self.tabla_pgp.item(seleccion_pgp[0])["values"][0])
        item_id = str(self.tabla_detalle.item(seleccion_item[0])["values"][0])
        item = self.item_pgp_por_id.get(item_id)
        if not item:
            return
        pendiente = cantidad_pendiente_item_pgp(item)
        if pendiente <= 0:
            return messagebox.showinfo(
                "Artículo cerrado",
                "Este artículo ya fue devuelto completamente.",
                parent=self,
            )

        ventana = VentanaAdaptable(self)
        ventana.title("Registrar devolución PGP")
        ventana.geometry("460x360")
        ventana.resizable(False, False)
        ventana.grab_set()
        panel = ctk.CTkScrollableFrame(ventana, **estilos_panel())
        panel.pack(fill="both", expand=True, padx=14, pady=14)
        ctk.CTkLabel(
            panel,
            text=item.get("producto_nombre", "Artículo"),
            font=ctk.CTkFont(size=18, weight="bold"),
            wraplength=390,
        ).pack(pady=(18, 4))
        ctk.CTkLabel(
            panel,
            text=f"Cantidad pendiente: {pendiente}",
            text_color=PALETA["texto_suave"],
        ).pack(pady=(0, 14))
        entry_cantidad = ctk.CTkEntry(
            panel, placeholder_text="Cantidad devuelta", height=38
        )
        entry_cantidad.insert(0, str(pendiente))
        entry_cantidad.pack(fill="x", padx=35, pady=5)
        texto_comentario = ctk.CTkTextbox(
            panel,
            height=75,
            fg_color=PALETA["panel_alt"],
            border_color=PALETA["borde"],
            border_width=1,
        )
        texto_comentario.pack(fill="x", padx=35, pady=8)

        def guardar():
            comentario = texto_comentario.get("1.0", "end").strip()
            try:
                cantidad = int(entry_cantidad.get().strip())
            except ValueError:
                cantidad = 0
            if cantidad <= 0 or cantidad > pendiente:
                return messagebox.showwarning(
                    "Cantidad inválida",
                    f"Ingrese una cantidad entre 1 y {pendiente}.",
                    parent=ventana,
                )
            boton.configure(state="disabled", text="Guardando...")
            threading.Thread(
                target=self._devolver_pesado,
                args=(pgp_id, item_id, cantidad, comentario, ventana, boton),
                daemon=True,
            ).start()

        boton = ctk.CTkButton(
            panel,
            text="Registrar devolución",
            height=42,
            **estilos_boton("exito"),
            command=guardar,
        )
        boton.pack(fill="x", padx=35, pady=(5, 18))

    def _devolver_pesado(
        self, pgp_id, item_id, cantidad, comentario, ventana, boton
    ):
        resultado = self.db.devolver_item_pgp(
            pgp_id, item_id, cantidad, comentario
        )
        ejecutar_en_ui(
            self, self._finalizar_devolucion, resultado, ventana, boton
        )

    def abrir_devolucion_total(self):
        seleccion = self.tabla_pgp.selection()
        if not seleccion:
            return messagebox.showwarning(
                "Selección requerida",
                "Seleccione el PGP que desea devolver completamente.",
                parent=self,
            )
        pgp_id = str(self.tabla_pgp.item(seleccion[0])["values"][0])
        pgp = self.pgp_por_id.get(pgp_id)
        if not pgp:
            return
        items_pendientes = [
            item for item in pgp.get("items", [])
            if cantidad_pendiente_item_pgp(item) > 0
        ]
        unidades = sum(
            cantidad_pendiente_item_pgp(item) for item in items_pendientes
        )
        if unidades <= 0:
            return messagebox.showinfo(
                "PGP cerrado",
                "Este PGP ya fue devuelto completamente.",
                parent=self,
            )

        ventana = VentanaAdaptable(self)
        ventana.title("Devolver PGP completo")
        ventana.geometry("480x360")
        ventana.resizable(False, False)
        ventana.grab_set()
        panel = ctk.CTkScrollableFrame(ventana, **estilos_panel())
        panel.pack(fill="both", expand=True, padx=14, pady=14)
        ctk.CTkLabel(
            panel,
            text=f"Devolver {pgp.get('codigo_pgp', 'PGP')} completo",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(20, 6))
        ctk.CTkLabel(
            panel,
            text=(
                f"Se devolverán {unidades} unidades correspondientes a "
                f"{len(items_pendientes)} artículos."
            ),
            text_color=PALETA["texto_suave"],
            wraplength=410,
        ).pack(pady=(0, 14))
        ctk.CTkLabel(
            panel, text="Comentario (opcional):", anchor="w"
        ).pack(fill="x", padx=35)
        texto_comentario = ctk.CTkTextbox(
            panel,
            height=85,
            fg_color=PALETA["panel_alt"],
            border_color=PALETA["borde"],
            border_width=1,
        )
        texto_comentario.pack(fill="x", padx=35, pady=(5, 12))

        def guardar_todo():
            comentario = texto_comentario.get("1.0", "end").strip()
            boton.configure(state="disabled", text="Devolviendo...")
            threading.Thread(
                target=self._devolver_todo_pesado,
                args=(pgp_id, comentario, ventana, boton),
                daemon=True,
            ).start()

        boton = ctk.CTkButton(
            panel,
            text="Confirmar devolución completa",
            height=42,
            **estilos_boton("alerta"),
            command=guardar_todo,
        )
        boton.pack(fill="x", padx=35, pady=(0, 18))

    def _devolver_todo_pesado(self, pgp_id, comentario, ventana, boton):
        resultado = self.db.devolver_pgp_completo(pgp_id, comentario)
        ejecutar_en_ui(
            self, self._finalizar_devolucion, resultado, ventana, boton
        )

    def _finalizar_devolucion(self, resultado, ventana, boton=None):
        exito, mensaje = resultado
        if not exito:
            if boton is not None and boton.winfo_exists():
                boton.configure(state="normal", text="Intentar nuevamente")
            return messagebox.showerror("Error", mensaje, parent=ventana)
        if ventana.winfo_exists():
            ventana.destroy()
        messagebox.showinfo("Devolución registrada", mensaje, parent=self)
        self.iniciar_carga_historial()
        self.iniciar_carga_selectores()
        self.notificar_movimientos()

    def notificar_movimientos(self):
        app = self.winfo_toplevel()
        for nombre, metodo in (
            ("vista_inventario", "iniciar_carga_hilo"),
            ("vista_salidas", "iniciar_carga_selectores"),
            ("vista_terreno", "iniciar_carga_hilo"),
            ("vista_consumo_proyecto", "iniciar_carga"),
        ):
            vista = getattr(app, nombre, None)
            funcion = getattr(vista, metodo, None) if vista is not None else None
            if callable(funcion):
                try:
                    funcion()
                except Exception:
                    pass
