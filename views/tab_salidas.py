import customtkinter as ctk
from utils.ui_windows import VentanaAdaptable
from tkinter import messagebox, ttk
from datetime import datetime
from uuid import uuid4
import threading
from utils.searchable_combobox import SearchableCombobox
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.movimientos import (
    TIPO_ENTREGA_HERRAMIENTA_PERSONAL,
    validar_entrega_herramienta_personal,
)
from views.tab_inventario import InventarioTab
from utils.ui_theme import (
    PALETA,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)


class SalidasTab(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        db_manager,
        on_epp_registrado=None,
        on_herramienta_personal_registrada=None,
    ):
        super().__init__(
            master,
            fg_color="transparent",
            orientation="vertical",
            scrollbar_button_color=PALETA["primario"],
            scrollbar_button_hover_color=PALETA["primario_hover"]
        )

        self.db = db_manager
        iniciar_despachador_ui(self)
        self.on_epp_registrado = on_epp_registrado
        self.on_herramienta_personal_registrada = (
            on_herramienta_personal_registrada
        )
        self._carga_selectores_id = 0
        self._carga_proyectos_id = 0
        self._carga_ultimos_id = 0
        self.productos_selector = []
        self.trabajadores_selector = []

        self.crear_interfaz()

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # =========================
        # CONTENEDOR PRINCIPAL
        # =========================
        self.frame_contenedor = ctk.CTkFrame(self, **estilos_panel())
        self.frame_contenedor.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")

        self.frame_contenedor.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.frame_contenedor,
            text="Registro de Movimientos por Proyecto",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=PALETA["primario"]
        ).grid(row=0, column=0, pady=(25, 8))

        ctk.CTkLabel(
            self.frame_contenedor,
            text=(
                "Busque y seleccione el producto y, opcionalmente, "
                "el trabajador responsable."
            ),
            font=ctk.CTkFont(size=14),
            text_color=PALETA["texto_suave"]
        ).grid(row=1, column=0, pady=(0, 18))

        # =========================
        # TIPO DE MOVIMIENTO
        # =========================
        opciones_movimiento = [
            "Entrega / Consumo",
            "Baja por Daño / Merma",
            "Préstamo de Herramienta",
            TIPO_ENTREGA_HERRAMIENTA_PERSONAL,
            "Devolución de Herramienta",
            "Envío a Calibración / Reparación",
            "Retorno de Reparación",
            "Corte / Transformación",
            "Entrada / Reposición"
        ]

        ctk.CTkLabel(
            self.frame_contenedor,
            text="Tipo de Movimiento:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=2, column=0, pady=(5, 5))

        self.combo_movimiento = ctk.CTkComboBox(
            self.frame_contenedor,
            values=opciones_movimiento,
            width=340,
            height=40,
            font=ctk.CTkFont(weight="bold"),
            state="readonly"
        )
        self.combo_movimiento.grid(row=3, column=0, pady=(0, 12))
        self.combo_movimiento.set("Entrega / Consumo")

        # =========================
        # PROYECTO
        # =========================
        ctk.CTkLabel(
            self.frame_contenedor,
            text="Proyecto / Destino (escriba para buscar):",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=4, column=0, pady=(5, 5))

        opciones_proyectos = []

        self.combo_proyecto = SearchableCombobox(
            self.frame_contenedor,
            label_getter=str,
            width=52,
            font=("Segoe UI", 12),
        )
        self.combo_proyecto.grid(row=5, column=0, pady=(0, 12), ipady=6)
        self.combo_proyecto.set_items(opciones_proyectos)

        self.combo_proyecto.set("")

        # =========================
        # PRODUCTO BUSCABLE
        # =========================
        ctk.CTkLabel(
            self.frame_contenedor,
            text="Producto (escriba para buscar o abra la lista):",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=6, column=0, pady=(5, 5))

        self.combo_producto = SearchableCombobox(
            self.frame_contenedor,
            label_getter=self.etiqueta_producto,
            search_getter=self.texto_busqueda_producto,
            on_selected=self.al_seleccionar_producto,
            width=52,
            font=("Segoe UI", 12)
        )
        self.combo_producto.grid(row=7, column=0, pady=(0, 12), ipady=6)

        # =========================
        # RESPONSABLE OPCIONAL
        # =========================
        ctk.CTkLabel(
            self.frame_contenedor,
            text=(
                "Responsable / Trabajador "
                "(escriba para buscar o abra la lista):"
            ),
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=8, column=0, pady=(5, 5))

        self.combo_trabajador = SearchableCombobox(
            self.frame_contenedor,
            label_getter=self.etiqueta_trabajador,
            search_getter=self.texto_busqueda_trabajador,
            on_selected=self.al_seleccionar_trabajador,
            width=52,
            font=("Segoe UI", 12)
        )
        self.combo_trabajador.grid(row=9, column=0, pady=(0, 8), ipady=6)

        self.btn_sin_responsable = ctk.CTkButton(
            self.frame_contenedor,
            text="Continuar sin responsable",
            height=34,
            width=340,
            **estilos_boton("secundario"),
            command=self.continuar_sin_responsable
        )
        self.btn_sin_responsable.grid(row=10, column=0, pady=(0, 8))

        # =========================
        # COMENTARIO OPCIONAL
        # =========================
        ctk.CTkLabel(
            self.frame_contenedor,
            text="Comentario / Observación (opcional):",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=11, column=0, pady=(8, 5))

        self.texto_comentario = ctk.CTkTextbox(
            self.frame_contenedor,
            width=520,
            height=72,
            wrap="word",
            fg_color=PALETA["panel_alt"],
            border_color=PALETA["borde"],
            border_width=1,
            text_color=PALETA["texto"]
        )
        self.texto_comentario.grid(row=12, column=0, pady=(0, 8))

        # =========================
        # MENSAJE DE ESTADO
        # =========================
        self.label_estado = ctk.CTkLabel(
            self.frame_contenedor,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=520
        )
        self.label_estado.grid(row=13, column=0, pady=(5, 12))

        # =========================
        # BOTONES
        # =========================
        self.btn_registrar = ctk.CTkButton(
            self.frame_contenedor,
            text="Registrar Movimiento",
            height=48,
            width=340,
            **estilos_boton("primario"),
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.registrar_salida
        )
        self.btn_registrar.grid(row=14, column=0, pady=(8, 8))

        self.btn_limpiar = ctk.CTkButton(
            self.frame_contenedor,
            text="Limpiar formulario",
            height=36,
            width=340,
            **estilos_boton("secundario"),
            command=self.limpiar_formulario
        )
        self.btn_limpiar.grid(row=15, column=0, pady=(0, 15))

        # =========================
        # ÚLTIMOS MOVIMIENTOS
        # =========================
        ctk.CTkLabel(
            self.frame_contenedor,
            text="Últimos 5 movimientos registrados",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=16, column=0, pady=(5, 5))

        frame_ultimos = ctk.CTkFrame(self.frame_contenedor, **estilos_panel())
        frame_ultimos.grid(row=17, column=0, padx=20, pady=(0, 25), sticky="ew")

        columnas = ("Fecha", "Producto", "Responsable", "Movimiento / Proyecto", "Cant.")

        self.tabla_ultimos = ttk.Treeview(
            frame_ultimos,
            columns=columnas,
            show="headings",
            height=5
        )
        estilizar_treeview(self.tabla_ultimos)

        anchos = {
            "Fecha": 120,
            "Producto": 220,
            "Responsable": 180,
            "Movimiento / Proyecto": 280,
            "Cant.": 60
        }

        for col in columnas:
            self.tabla_ultimos.heading(col, text=col)
            self.tabla_ultimos.column(col, width=anchos[col], anchor="center")

        self.tabla_ultimos.pack(fill="x", expand=True, padx=8, pady=8)

        self.after(100, self.cargar_proyectos)
        self.after(150, self.cargar_ultimos_movimientos)
        self.after(200, self.iniciar_carga_selectores)
        self.after(300, self.combo_producto.focus_set)

    # ============================================================
    # PROYECTOS
    # ============================================================
    def cargar_proyectos(self):
        self._carga_proyectos_id += 1
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
            print(f"Error actualizando combo de proyectos: {e}")
            ejecutar_en_ui(self, self._actualizar_proyectos_ui, None, carga_id)

    def _actualizar_proyectos_ui(self, proyectos, carga_id):
        if carga_id != self._carga_proyectos_id:
            return
        if proyectos is None:
            self.label_estado.configure(text="No se pudieron cargar los proyectos. Revise la conexión.", text_color=PALETA["alerta"])
            return
        self.combo_proyecto.set_items(proyectos)

    def actualizar_proyectos(self):
        return self.cargar_proyectos()

    # ============================================================
    # SELECTORES BUSCABLES
    # ============================================================
    @staticmethod
    def etiqueta_producto(producto):
        nombre = producto.get("nombre") or "Producto sin nombre"
        categoria = producto.get("categoria") or "Sin categoría"
        stock = int(producto.get("stock") or 0)
        return f"{nombre} · {categoria} · Stock {stock}"

    @staticmethod
    def texto_busqueda_producto(producto):
        return " ".join(str(producto.get(campo) or "") for campo in (
            "nombre", "categoria"
        ))

    @staticmethod
    def etiqueta_trabajador(trabajador):
        nombre = trabajador.get("nombre") or "Trabajador sin nombre"
        rut = trabajador.get("rut") or "Sin RUT"
        cargo = trabajador.get("cargo") or "Sin cargo"
        return f"{nombre} · {rut} · {cargo}"

    @staticmethod
    def texto_busqueda_trabajador(trabajador):
        return " ".join(str(trabajador.get(campo) or "") for campo in (
            "nombre", "rut", "cargo"
        ))

    def iniciar_carga_selectores(self):
        self._carga_selectores_id += 1
        carga_id = self._carga_selectores_id
        self.label_estado.configure(
            text="Actualizando productos y trabajadores...",
            text_color=PALETA["texto_suave"]
        )
        threading.Thread(
            target=self._cargar_selectores_pesado,
            args=(carga_id,),
            daemon=True
        ).start()

    def _cargar_selectores_pesado(self, carga_id):
        try:
            productos = self.db.cargar_productos_activos_selector()
            trabajadores = self.db.cargar_trabajadores_nube()
        except Exception as error:
            print(f"Error cargando selectores: {error}")
            ejecutar_en_ui(self, self._error_selectores_ui, carga_id)
            return
        ejecutar_en_ui(
            self,
            self._actualizar_selectores_ui,
            productos,
            trabajadores,
            carga_id
        )

    def _error_selectores_ui(self, carga_id):
        if carga_id == self._carga_selectores_id:
            self.label_estado.configure(text="No se pudieron cargar los datos. Revise la conexión.", text_color=PALETA["alerta"])

    def _actualizar_selectores_ui(
        self,
        productos,
        trabajadores,
        carga_id
    ):
        if carga_id != self._carga_selectores_id:
            return
        self.productos_selector = list(productos or [])
        self.trabajadores_selector = list(trabajadores or [])
        self.combo_producto.set_items(self.productos_selector)
        self.combo_trabajador.set_items(self.trabajadores_selector)
        self.label_estado.configure(
            text=(
                f"{len(self.productos_selector)} productos y "
                f"{len(self.trabajadores_selector)} trabajadores disponibles."
            ),
            text_color=PALETA["texto_suave"]
        )

    def al_seleccionar_producto(self, producto):
        self.label_estado.configure(
            text=(
                f"Producto seleccionado: {producto.get('nombre', '-')} · "
                f"Stock: {int(producto.get('stock') or 0)}"
            ),
            text_color=PALETA["primario"]
        )
        self.combo_trabajador.focus_set()

    def al_seleccionar_trabajador(self, trabajador):
        self.label_estado.configure(
            text=f"Responsable seleccionado: {trabajador.get('nombre', '-')}",
            text_color=PALETA["exito"]
        )

    # ============================================================
    # ÚLTIMOS MOVIMIENTOS
    # ============================================================
    def cargar_ultimos_movimientos(self):
        self._carga_ultimos_id += 1
        threading.Thread(
            target=self._cargar_ultimos_pesado,
            args=(self._carga_ultimos_id,),
            daemon=True,
        ).start()

    def _cargar_ultimos_pesado(self, carga_id):
        try:
            movimientos = self.db.obtener_ultimos_movimientos(5)
            ejecutar_en_ui(self, self._actualizar_ultimos_ui, movimientos, carga_id)
        except Exception as e:
            print(f"Error cargando últimos movimientos: {e}")
            ejecutar_en_ui(self, self._actualizar_ultimos_ui, None, carga_id)

    def _actualizar_ultimos_ui(self, movimientos, carga_id):
        if carga_id != self._carga_ultimos_id:
            return
        if movimientos is None:
            self.label_estado.configure(text="No se pudo cargar el historial reciente. Revise la conexión.", text_color=PALETA["alerta"])
            return
        for item in self.tabla_ultimos.get_children():
            self.tabla_ultimos.delete(item)
        for mov in movimientos:
            self.tabla_ultimos.insert("", "end", values=mov)

    def continuar_sin_responsable(self):
        self.combo_trabajador.clear()
        producto = self.combo_producto.get_selected()
        proyecto = self.combo_proyecto.get_selected()

        if producto and proyecto:
            self.label_estado.configure(
                text=(
                    "Movimiento sin responsable asociado.\n"
                    f"Proyecto seleccionado: {proyecto}\n"
                    "Listo para registrar."
                ),
                text_color=PALETA["exito"]
            )
        else:
            self.label_estado.configure(
                text="Seleccione un producto y un proyecto desde sus listas.",
                text_color=PALETA["alerta"]
            )
            self.combo_producto.focus_set()

    # ============================================================
    # REGISTRAR MOVIMIENTO
    # ============================================================
    def registrar_salida(self):
        producto_seleccionado = self.combo_producto.get_selected()
        trabajador_seleccionado = self.combo_trabajador.get_selected()
        tipo_movimiento = self.combo_movimiento.get()
        proyecto = self.combo_proyecto.get_selected()
        comentario = self.texto_comentario.get("1.0", "end").strip()

        if len(comentario) > 1000:
            return messagebox.showwarning(
                "Comentario demasiado largo",
                "El comentario puede tener como máximo 1.000 caracteres."
            )

        if not proyecto:
            return messagebox.showwarning(
                "Aviso",
                "Busque un proyecto y selecciónelo desde la lista antes de registrar el movimiento."
            )

        if not producto_seleccionado:
            return messagebox.showwarning(
                "Aviso",
                "Busque un producto y selecciónelo desde la lista."
            )

        codigo_producto = producto_seleccionado.get("codigo_barras")
        producto = self.db.buscar_producto_por_codigo(codigo_producto)

        if not producto:
            return messagebox.showerror(
                "Error",
                "El producto no existe en la base de datos o está inactivo."
            )

        if self.combo_trabajador.get().strip() and not trabajador_seleccionado:
            return messagebox.showwarning(
                "Aviso",
                "Seleccione al trabajador desde la lista o use "
                "'Continuar sin responsable'."
            )

        es_entrega_epp = (
            tipo_movimiento == "Entrega / Consumo"
            and str(producto.get("categoria") or "").strip().casefold() == "epp"
        )
        if es_entrega_epp and not trabajador_seleccionado:
            return messagebox.showwarning(
                "Responsable requerido",
                "Para entregar un EPP debe seleccionar al trabajador que lo recibe."
            )

        es_entrega_herramienta_personal = (
            tipo_movimiento == TIPO_ENTREGA_HERRAMIENTA_PERSONAL
        )
        error_entrega_personal = validar_entrega_herramienta_personal(
            tipo_movimiento,
            producto,
            trabajador_seleccionado,
        )
        if error_entrega_personal:
            return messagebox.showwarning(
                "Entrega personal inválida",
                error_entrega_personal,
            )

        rut_trabajador = (
            trabajador_seleccionado.get("rut", "")
            if trabajador_seleccionado
            else ""
        )

        cantidad = 1

        texto_dialogo = f"¿Cuántas unidades de '{producto['nombre']}' desea registrar?"

        dialog = ctk.CTkInputDialog(
            text=texto_dialogo,
            title="Cantidad"
        )

        try:
            respuesta = dialog.get_input()

            if respuesta is None:
                return

            cantidad = int(respuesta)

            if cantidad < 1:
                raise ValueError

        except Exception:
            return messagebox.showerror(
                "Error",
                "Debe ingresar un número entero mayor a 0."
            )

        stock_actual = int(producto.get("stock", 0) or 0)

        exito, msg = self.db.registrar_movimiento_camara(
            rut_trabajador,
            codigo_producto,
            tipo_movimiento,
            producto["id"],
            stock_actual,
            cantidad,
            proyecto,
            comentario
        )

        if exito:
            if es_entrega_epp and callable(self.on_epp_registrado):
                self.on_epp_registrado()
            if (
                es_entrega_herramienta_personal
                and callable(self.on_herramienta_personal_registrada)
            ):
                self.on_herramienta_personal_registrada()

            if tipo_movimiento == "Corte / Transformación":
                crear_retazo = messagebox.askyesno(
                    "Generar Retazo",
                    "Se ha registrado el corte.\n¿Sobró material útil que deba ingresar como retazo?",
                    parent=self
                )

                if crear_retazo:
                    self.cargar_ultimos_movimientos()

                    self.crear_dialogo_retazo(
                        prod_original=producto,
                        cantidad_cortada=cantidad,
                        proyecto=proyecto,
                        rut_trabajador=rut_trabajador
                    )

                    # Importante:
                    # No limpiar aquí, porque si limpiamos/focuseamos la pantalla principal,
                    # la ventana del retazo puede quedar atrás o minimizarse.
                    return

                messagebox.showinfo(
                    "Éxito",
                    f"{tipo_movimiento} registrado correctamente.\n\n"
                    f"Proyecto: {proyecto}",
                    parent=self
                )

                self.cargar_ultimos_movimientos()
                self.limpiar_formulario()
                self.iniciar_carga_selectores()
                return

            responsable_txt = (
                trabajador_seleccionado.get("nombre", "-")
                if trabajador_seleccionado
                else "Sin responsable"
            )

            messagebox.showinfo(
                "Éxito",
                f"{tipo_movimiento} registrado correctamente.\n\n"
                f"Proyecto: {proyecto}\n"
                f"Responsable: {responsable_txt}",
                parent=self
            )

            self.cargar_ultimos_movimientos()
            self.limpiar_formulario()
            self.iniciar_carga_selectores()

        else:
            messagebox.showerror("Error", f"Fallo al registrar: {msg}", parent=self)
    # ============================================================
    # RETAZOS CON CÁLCULO REAL
    # ============================================================
    def formatear_pesos(self, valor):
        try:
            return "$" + f"{int(valor):,}".replace(",", ".")
        except Exception:
            return "$0"

    def convertir_decimal(self, texto):
        texto = str(texto).strip().replace(",", ".")

        if texto == "":
            return None

        return float(texto)

    def calcular_precio_retazo(
        self,
        prod_original,
        cantidad_cortada,
        largo_retazo=None,
        ancho_retazo=None,
        porcentaje_manual=None
    ):
        precio_unitario = int(prod_original.get("precio_unitario") or 0)
        precio_original_total = precio_unitario * int(cantidad_cortada or 1)

        tipo_medicion = prod_original.get("tipo_medicion") or "No aplica"
        largo_original = float(prod_original.get("medida_largo") or 0)
        ancho_original = float(prod_original.get("medida_ancho") or 0)

        proporcion = 0

        if tipo_medicion == "Largo":
            largo_total = largo_original * int(cantidad_cortada or 1)

            if largo_total <= 0 or largo_retazo is None:
                raise ValueError("El producto original no tiene un largo válido.")

            proporcion = float(largo_retazo) / largo_total

        elif tipo_medicion == "Área":
            area_original_unitaria = largo_original * ancho_original
            area_original_total = area_original_unitaria * int(cantidad_cortada or 1)

            if area_original_total <= 0 or largo_retazo is None or ancho_retazo is None:
                raise ValueError("El producto original no tiene medidas de área válidas.")

            area_retazo = float(largo_retazo) * float(ancho_retazo)
            proporcion = area_retazo / area_original_total

        elif tipo_medicion == "Porcentaje":
            if porcentaje_manual is None:
                raise ValueError("Debe ingresar un porcentaje útil para el retazo.")

            proporcion = float(porcentaje_manual) / 100

        else:
            if porcentaje_manual is None:
                raise ValueError(
                    "Este producto no tiene medición estructurada. "
                    "Ingrese un porcentaje útil manual."
                )

            proporcion = float(porcentaje_manual) / 100

        if proporcion <= 0:
            raise ValueError("La proporción del retazo debe ser mayor a 0.")

        if proporcion > 1:
            raise ValueError(
                "El retazo no puede valer más que el material original cortado. "
                "Revise las medidas ingresadas."
            )

        precio_retazo = int(precio_original_total * proporcion)
        porcentaje_valor = round(proporcion * 100, 2)

        return precio_retazo, porcentaje_valor

    def crear_dialogo_retazo(
        self,
        prod_original,
        cantidad_cortada=1,
        proyecto="Taller Interno",
        rut_trabajador=""
    ):
        tipo_medicion = prod_original.get("tipo_medicion") or "No aplica"
        unidad = prod_original.get("unidad_medida") or "unidad"

        self.win_retazo = VentanaAdaptable(self)
        self.win_retazo.title("Crear Retazo")
        self.win_retazo.geometry("520x680")
        self.win_retazo.minsize(520, 680)

        self.win_retazo.transient(self.winfo_toplevel())
        self.win_retazo.lift()
        self.win_retazo.focus_force()
        self.win_retazo.grab_set()
        self.win_retazo.protocol(
            "WM_DELETE_WINDOW",
            self.cancelar_dialogo_retazo
        )

        self.win_retazo.after(150, self.win_retazo.lift)
        self.win_retazo.after(200, self.win_retazo.focus_force)

        scroll = ctk.CTkScrollableFrame(self.win_retazo)
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            scroll,
            text="Crear retazo desde corte",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(10, 5))

        precio_unitario = int(prod_original.get("precio_unitario") or 0)
        precio_total_corte = precio_unitario * int(cantidad_cortada or 1)

        info = (
            f"Producto original:\n{prod_original.get('nombre', '-')}\n\n"
            f"Tipo medición: {tipo_medicion}\n"
            f"Cantidad cortada: {cantidad_cortada}\n"
            f"Precio unitario: {self.formatear_pesos(precio_unitario)}\n"
            f"Valor total del corte: {self.formatear_pesos(precio_total_corte)}"
        )

        if tipo_medicion == "Largo":
            largo_unitario = float(prod_original.get("medida_largo") or 0)
            largo_total = largo_unitario * int(cantidad_cortada or 1)

            info += (
                f"\nLargo por unidad: {largo_unitario} {unidad}"
                f"\nLargo total cortado: {largo_total} {unidad}"
            )

        elif tipo_medicion == "Área":
            info += (
                f"\nMedida por unidad: "
                f"{prod_original.get('medida_largo', '-')} x "
                f"{prod_original.get('medida_ancho', '-')} {unidad}"
            )

        ctk.CTkLabel(
            scroll,
            text=info,
            justify="left",
            text_color=PALETA["texto_suave"],
            wraplength=440
        ).pack(pady=(5, 15))

        frame = ctk.CTkFrame(scroll)
        frame.pack(fill="x", padx=10, pady=10)
        frame.grid_columnconfigure((0, 1), weight=1)

        self.retazo_largo = None
        self.retazo_ancho = None
        self.retazo_porcentaje = None

        if tipo_medicion == "Largo":
            ctk.CTkLabel(
                frame,
                text=f"Largo del retazo ({unidad}):",
                font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))

            self.retazo_largo = ctk.CTkEntry(
                frame,
                placeholder_text=f"Ej: 1.5 en {unidad}"
            )
            self.retazo_largo.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=8)

        elif tipo_medicion == "Área":
            ctk.CTkLabel(
                frame,
                text=f"Largo retazo ({unidad}):",
                font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))

            ctk.CTkLabel(
                frame,
                text=f"Ancho retazo ({unidad}):",
                font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=1, sticky="w", padx=10, pady=(10, 0))

            self.retazo_largo = ctk.CTkEntry(frame, placeholder_text="Ej: 50")
            self.retazo_largo.grid(row=1, column=0, sticky="ew", padx=10, pady=8)

            self.retazo_ancho = ctk.CTkEntry(frame, placeholder_text="Ej: 50")
            self.retazo_ancho.grid(row=1, column=1, sticky="ew", padx=10, pady=8)

        else:
            ctk.CTkLabel(
                frame,
                text="Porcentaje útil del retazo:",
                font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))

            self.retazo_porcentaje = ctk.CTkEntry(
                frame,
                placeholder_text="Ej: 25 para 25%"
            )
            self.retazo_porcentaje.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=8)

        ctk.CTkLabel(
            scroll,
            text="Nombre del retazo:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=20, pady=(10, 0))

        nombre_base = prod_original.get("nombre", "Material")

        if nombre_base.startswith("Retazo de "):
            nombre_base = nombre_base.replace("Retazo de ", "")

        self.retazo_nombre = ctk.CTkEntry(
            scroll,
            width=430,
            placeholder_text="Nombre del retazo"
        )
        self.retazo_nombre.pack(pady=6)

        self.retazo_nombre.insert(0, f"Retazo de {nombre_base}")

        ctk.CTkLabel(
            scroll,
            text="Precio sugerido:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=20, pady=(10, 0))

        self.retazo_precio = ctk.CTkEntry(
            scroll,
            width=430,
            placeholder_text="Se calculará automáticamente"
        )
        self.retazo_precio.pack(pady=6)

        self.retazo_label_resultado = ctk.CTkLabel(
            scroll,
            text="Ingrese las medidas para calcular el precio.",
            text_color=PALETA["texto_suave"],
            wraplength=430
        )
        self.retazo_label_resultado.pack(pady=8)

        def calcular_y_mostrar():
            try:
                largo = None
                ancho = None
                porcentaje = None

                if tipo_medicion == "Largo":
                    largo = self.convertir_decimal(self.retazo_largo.get())

                elif tipo_medicion == "Área":
                    largo = self.convertir_decimal(self.retazo_largo.get())
                    ancho = self.convertir_decimal(self.retazo_ancho.get())

                else:
                    porcentaje = self.convertir_decimal(self.retazo_porcentaje.get())

                precio_retazo, porcentaje_valor = self.calcular_precio_retazo(
                    prod_original=prod_original,
                    cantidad_cortada=cantidad_cortada,
                    largo_retazo=largo,
                    ancho_retazo=ancho,
                    porcentaje_manual=porcentaje
                )

                self.retazo_precio.delete(0, "end")
                self.retazo_precio.insert(0, str(precio_retazo))

                self.retazo_label_resultado.configure(
                    text=(
                        f"Precio sugerido: {self.formatear_pesos(precio_retazo)}\n"
                        f"Equivale al {porcentaje_valor}% del valor cortado."
                    ),
                    text_color=PALETA["exito"]
                )

            except Exception as e:
                self.retazo_label_resultado.configure(
                    text=str(e),
                    text_color=PALETA["peligro"]
                )

        ctk.CTkButton(
            scroll,
            text="Calcular precio sugerido",
            **estilos_boton("fantasma"),
            command=calcular_y_mostrar
        ).pack(fill="x", padx=35, pady=(10, 6))

        ctk.CTkButton(
            scroll,
            text="Guardar retazo",
            **estilos_boton("primario"),
            height=42,
            command=lambda: self.guardar_retazo_calculado(
                prod_original=prod_original,
                cantidad_cortada=cantidad_cortada,
                proyecto=proyecto,
                rut_trabajador=rut_trabajador,
                tipo_medicion=tipo_medicion,
                unidad=unidad
            )
        ).pack(fill="x", padx=35, pady=(6, 15))

    def guardar_retazo_calculado(
        self,
        prod_original,
        cantidad_cortada,
        proyecto,
        rut_trabajador,
        tipo_medicion,
        unidad
    ):
        try:
            nombre_retazo = self.retazo_nombre.get().strip()

            if not nombre_retazo:
                return messagebox.showwarning(
                    "Aviso",
                    "Debe ingresar un nombre para el retazo.",
                    parent=self.win_retazo
                )

            largo = None
            ancho = None
            porcentaje_manual = None

            if tipo_medicion == "Largo":
                largo = self.convertir_decimal(self.retazo_largo.get())

                if largo is None or largo <= 0:
                    raise ValueError("Debe ingresar un largo válido para el retazo.")

                tamano_retazo = f"{largo} {unidad}"

            elif tipo_medicion == "Área":
                largo = self.convertir_decimal(self.retazo_largo.get())
                ancho = self.convertir_decimal(self.retazo_ancho.get())

                if largo is None or largo <= 0 or ancho is None or ancho <= 0:
                    raise ValueError("Debe ingresar largo y ancho válidos para el retazo.")

                tamano_retazo = f"{largo}x{ancho} {unidad}"

            else:
                porcentaje_manual = self.convertir_decimal(self.retazo_porcentaje.get())

                if porcentaje_manual is None or porcentaje_manual <= 0:
                    raise ValueError("Debe ingresar un porcentaje válido para el retazo.")

                tamano_retazo = f"{porcentaje_manual}% útil"

            precio_sugerido, porcentaje_valor = self.calcular_precio_retazo(
                prod_original=prod_original,
                cantidad_cortada=cantidad_cortada,
                largo_retazo=largo,
                ancho_retazo=ancho,
                porcentaje_manual=porcentaje_manual
            )

            precio_final_txt = self.retazo_precio.get().strip()

            if precio_final_txt:
                precio_final = int(float(precio_final_txt.replace(".", "").replace(",", ".")))
            else:
                precio_final = precio_sugerido

            if precio_final < 0:
                raise ValueError("El precio del retazo no puede ser negativo.")

            valor_total_corte = (
                int(prod_original.get("precio_unitario") or 0)
                * int(cantidad_cortada or 1)
            )
            if precio_final > valor_total_corte:
                raise ValueError(
                    "El precio del retazo no puede superar el valor total del corte."
                )

            nuevo_codigo = (
                f"RET{datetime.now().strftime('%y%m%d')}"
                f"{uuid4().hex[:10].upper()}"
            )

            if tipo_medicion == "Porcentaje" or tipo_medicion == "No aplica":
                tipo_retazo = "Porcentaje"
                medida_largo = None
                medida_ancho = None
                unidad_retazo = "%"
            else:
                tipo_retazo = tipo_medicion
                medida_largo = largo
                medida_ancho = ancho if tipo_medicion == "Área" else None
                unidad_retazo = unidad

            dimensiones_originales = str(
                prod_original.get("tamaño_dimensiones") or ""
            )
            if dimensiones_originales.startswith(
                InventarioTab.PREFIJO_DIMENSIONES
            ):
                configuracion_retazo = InventarioTab.decodificar_dimensiones(
                    prod_original
                )
                configuracion_retazo["principal"] = medida_largo
                if tipo_medicion == "Área":
                    configuracion_retazo["secundaria"] = medida_ancho
                    configuracion_retazo["unidad_secundaria"] = unidad
                configuracion_retazo["unidad_principal"] = unidad_retazo
                tamano_retazo = InventarioTab.codificar_dimensiones(
                    configuracion_retazo
                )

            datos_retazo = {
                "codigo_barras": nuevo_codigo,
                "nombre": nombre_retazo,
                "categoria": prod_original.get("categoria", "Materiales"),
                "tamaño_dimensiones": tamano_retazo,
                "precio_unitario": precio_final,
                "ubicacion_id": prod_original.get("ubicacion_id"),
                "tipo_medicion": tipo_retazo,
                "medida_largo": medida_largo,
                "medida_ancho": medida_ancho,
                "unidad_medida": unidad_retazo,
                "producto_origen_id": prod_original.get("id"),
                "porcentaje_valor_origen": porcentaje_valor,
                "observacion_retazo": (
                    f"Retazo generado desde corte de {prod_original.get('nombre', '-')}. "
                    f"Cantidad cortada: {cantidad_cortada}. Proyecto: {proyecto}."
                )
            }
            exito, msg, _ = self.db.crear_retazo_con_entrada(
                datos_retazo,
                proyecto,
                rut_trabajador
            )

            if not exito:
                return messagebox.showerror(
                    "Error",
                    f"No se pudo guardar el retazo: {msg}",
                    parent=self.win_retazo
                )

            messagebox.showinfo(
                "Retazo creado",
                (
                    f"Se creó el retazo correctamente.\n\n"
                    f"Nombre: {nombre_retazo}\n"
                    f"Medida: {tamano_retazo}\n"
                    f"Precio: {self.formatear_pesos(precio_final)}\n"
                    f"Valor equivalente: {porcentaje_valor}% del corte."
                ),
                parent=self.win_retazo
            )

            self.win_retazo.destroy()
            self.cargar_ultimos_movimientos()
            self.limpiar_formulario()
            self.iniciar_carga_selectores()

        except ValueError as e:
            messagebox.showerror(
                "Error",
                str(e),
                parent=self.win_retazo
            )

        except Exception as e:
            messagebox.showerror(
                "Error",
                f"No se pudo crear el retazo: {e}",
                parent=self.win_retazo
            )

    # ============================================================
    # LIMPIAR
    # ============================================================
    def cancelar_dialogo_retazo(self):
        if hasattr(self, "win_retazo") and self.win_retazo.winfo_exists():
            self.win_retazo.destroy()
        self.cargar_ultimos_movimientos()
        self.limpiar_formulario()

    def limpiar_formulario(self):
        self.combo_proyecto.clear()
        self.combo_producto.clear()
        self.combo_trabajador.clear()
        self.texto_comentario.delete("1.0", "end")
        self.label_estado.configure(text="")
        self.after(200, self.combo_producto.focus_set)
