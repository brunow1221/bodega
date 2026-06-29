import customtkinter as ctk
from tkinter import messagebox, ttk
from datetime import datetime
from uuid import uuid4


class SalidasTab(ctk.CTkFrame):
    def __init__(self, master, db_manager, barcode_gen):
        super().__init__(master, fg_color="transparent")

        self.db = db_manager
        self.barcode = barcode_gen

        self.crear_interfaz()

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # =========================
        # CONTENEDOR PRINCIPAL
        # =========================
        self.frame_contenedor = ctk.CTkFrame(self, corner_radius=15)
        self.frame_contenedor.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")

        self.frame_contenedor.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.frame_contenedor,
            text="Registro de Movimientos por Proyecto",
            font=ctk.CTkFont(size=26, weight="bold")
        ).grid(row=0, column=0, pady=(25, 8))

        ctk.CTkLabel(
            self.frame_contenedor,
            text="Seleccione el proyecto, escanee el producto y registre la cantidad. El responsable es opcional.",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).grid(row=1, column=0, pady=(0, 18))

        # =========================
        # TIPO DE MOVIMIENTO
        # =========================
        opciones_movimiento = [
            "Entrega / Consumo",
            "Baja por Daño / Merma",
            "Préstamo de Herramienta",
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
            text="Proyecto / Destino:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=4, column=0, pady=(5, 5))

        opciones_proyectos = self.db.cargar_proyectos()

        self.combo_proyecto = ctk.CTkComboBox(
            self.frame_contenedor,
            values=opciones_proyectos,
            width=340,
            height=40,
            state="readonly"
        )
        self.combo_proyecto.grid(row=5, column=0, pady=(0, 12))

        if opciones_proyectos:
            self.combo_proyecto.set(opciones_proyectos[0])

        # =========================
        # CÓDIGO PRODUCTO
        # =========================
        ctk.CTkLabel(
            self.frame_contenedor,
            text="Código del Producto:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=6, column=0, pady=(5, 5))

        self.entrada_producto_salida = ctk.CTkEntry(
            self.frame_contenedor,
            placeholder_text="Escanee el código de barras del producto",
            width=340,
            height=45,
            font=ctk.CTkFont(size=15)
        )
        self.entrada_producto_salida.grid(row=7, column=0, pady=(0, 12))
        self.entrada_producto_salida.bind("<Return>", self.procesar_producto_pistola)

        # =========================
        # RESPONSABLE OPCIONAL
        # =========================
        ctk.CTkLabel(
            self.frame_contenedor,
            text="Responsable / Trabajador (opcional):",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=8, column=0, pady=(5, 5))

        self.entrada_trabajador = ctk.CTkEntry(
            self.frame_contenedor,
            placeholder_text="Escanee QR/RUT si desea asociar responsable",
            width=340,
            height=45,
            font=ctk.CTkFont(size=15)
        )
        self.entrada_trabajador.grid(row=9, column=0, pady=(0, 8))
        self.entrada_trabajador.configure(state="disabled")
        self.entrada_trabajador.bind("<Return>", self.procesar_trabajador_pistola)

        self.btn_sin_responsable = ctk.CTkButton(
            self.frame_contenedor,
            text="Continuar sin responsable",
            height=34,
            width=340,
            fg_color="#555555",
            hover_color="#333333",
            command=self.continuar_sin_responsable
        )
        self.btn_sin_responsable.grid(row=10, column=0, pady=(0, 8))

        # =========================
        # MENSAJE DE ESTADO
        # =========================
        self.label_estado = ctk.CTkLabel(
            self.frame_contenedor,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=520
        )
        self.label_estado.grid(row=11, column=0, pady=(5, 12))

        # =========================
        # BOTONES
        # =========================
        self.btn_registrar = ctk.CTkButton(
            self.frame_contenedor,
            text="Registrar Movimiento",
            height=48,
            width=340,
            fg_color="#1f538d",
            hover_color="#163c65",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.registrar_salida
        )
        self.btn_registrar.grid(row=12, column=0, pady=(8, 8))

        self.btn_limpiar = ctk.CTkButton(
            self.frame_contenedor,
            text="Limpiar Escaneo",
            height=36,
            width=340,
            fg_color="#555555",
            hover_color="#333333",
            command=self.limpiar_escaneo
        )
        self.btn_limpiar.grid(row=13, column=0, pady=(0, 15))

        # =========================
        # ÚLTIMOS MOVIMIENTOS
        # =========================
        ctk.CTkLabel(
            self.frame_contenedor,
            text="Últimos 5 movimientos registrados",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=14, column=0, pady=(5, 5))

        frame_ultimos = ctk.CTkFrame(self.frame_contenedor)
        frame_ultimos.grid(row=15, column=0, padx=20, pady=(0, 25), sticky="ew")

        columnas = ("Fecha", "Producto", "Responsable", "Movimiento / Proyecto", "Cant.")

        self.tabla_ultimos = ttk.Treeview(
            frame_ultimos,
            columns=columnas,
            show="headings",
            height=5
        )

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

        self.cargar_ultimos_movimientos()

        self.after(300, self.entrada_producto_salida.focus_set)

    # ============================================================
    # PROYECTOS
    # ============================================================
    def cargar_proyectos(self):
        try:
            proyectos = self.db.cargar_proyectos()

            if not proyectos:
                proyectos = ["Taller Interno"]

            proyecto_actual = self.combo_proyecto.get()

            self.combo_proyecto.configure(values=proyectos)

            if proyecto_actual in proyectos:
                self.combo_proyecto.set(proyecto_actual)
            else:
                self.combo_proyecto.set(proyectos[0])

            return True

        except Exception as e:
            print(f"Error actualizando combo de proyectos: {e}")
            return False

    def actualizar_proyectos(self):
        return self.cargar_proyectos()

    # ============================================================
    # FOCO PARA PISTOLA LECTORA
    # ============================================================
    def mantener_foco_pistola(self):
        try:
            producto = self.entrada_producto_salida.get().strip()

            if not producto:
                self.entrada_producto_salida.focus_set()

        except Exception:
            pass

    # ============================================================
    # ÚLTIMOS MOVIMIENTOS
    # ============================================================
    def cargar_ultimos_movimientos(self):
        try:
            for item in self.tabla_ultimos.get_children():
                self.tabla_ultimos.delete(item)

            movimientos = self.db.obtener_ultimos_movimientos(5)

            for mov in movimientos:
                self.tabla_ultimos.insert("", "end", values=mov)

        except Exception as e:
            print(f"Error cargando últimos movimientos: {e}")

    # ============================================================
    # PROCESAR PRODUCTO
    # ============================================================
    def procesar_producto_pistola(self, event=None):
        codigo = self.entrada_producto_salida.get().strip()

        if not codigo:
            return

        producto = self.db.buscar_producto_por_codigo(codigo)

        if producto:
            self.entrada_trabajador.configure(state="normal")
            self.entrada_trabajador.delete(0, "end")

            proyecto = self.combo_proyecto.get()

            self.label_estado.configure(
                text=(
                    f"✅ Producto: {producto['nombre']}\n"
                    f"Proyecto seleccionado: {proyecto}\n"
                    "Puede escanear un responsable o registrar sin responsable."
                ),
                text_color="#1f538d"
            )

            self.entrada_trabajador.focus_set()

        else:
            self.label_estado.configure(
                text="❌ Producto no encontrado o inactivo.",
                text_color="red"
            )
            self.entrada_producto_salida.delete(0, "end")
            self.entrada_producto_salida.focus_set()

    # ============================================================
    # PROCESAR RESPONSABLE
    # ============================================================
    def procesar_trabajador_pistola(self, event=None):
        rut = self.entrada_trabajador.get().strip()

        if not rut:
            self.continuar_sin_responsable()
            return

        trabajador = self.db.buscar_trabajador_por_rut(rut)

        if trabajador:
            self.label_estado.configure(
                text=f"✅ Responsable: {trabajador['nombre']}\nListo para registrar movimiento.",
                text_color="green"
            )

        else:
            self.label_estado.configure(
                text="❌ QR/RUT no reconocido. Puede corregirlo o continuar sin responsable.",
                text_color="red"
            )
            self.entrada_trabajador.delete(0, "end")
            self.entrada_trabajador.focus_set()

    def continuar_sin_responsable(self):
        self.entrada_trabajador.configure(state="normal")
        self.entrada_trabajador.delete(0, "end")

        producto = self.entrada_producto_salida.get().strip()
        proyecto = self.combo_proyecto.get()

        if producto:
            self.label_estado.configure(
                text=(
                    f"✅ Movimiento sin responsable asociado.\n"
                    f"Proyecto seleccionado: {proyecto}\n"
                    "Listo para registrar."
                ),
                text_color="green"
            )
        else:
            self.label_estado.configure(
                text="Escanee primero un producto.",
                text_color="orange"
            )
            self.entrada_producto_salida.focus_set()

    # ============================================================
    # REGISTRAR MOVIMIENTO
    # ============================================================
    def registrar_salida(self):
        codigo_producto = self.entrada_producto_salida.get().strip()
        rut_trabajador = self.entrada_trabajador.get().strip()
        tipo_movimiento = self.combo_movimiento.get()
        proyecto = self.combo_proyecto.get()

        if not proyecto:
            return messagebox.showwarning(
                "Aviso",
                "Debe seleccionar un proyecto antes de registrar el movimiento."
            )

        if not codigo_producto:
            return messagebox.showwarning(
                "Aviso",
                "Debe escanear o ingresar el código del producto."
            )

        producto = self.db.buscar_producto_por_codigo(codigo_producto)

        if not producto:
            return messagebox.showerror(
                "Error",
                "El producto no existe en la base de datos o está inactivo."
            )

        if rut_trabajador:
            trabajador = self.db.buscar_trabajador_por_rut(rut_trabajador)

            if not trabajador:
                return messagebox.showerror(
                    "Error",
                    "El responsable ingresado no existe o está inactivo. "
                    "Corrija el RUT o deje el campo vacío para continuar sin responsable."
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
            proyecto
        )

        if exito:
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
                self.limpiar_escaneo()
                return

            responsable_txt = rut_trabajador if rut_trabajador else "Sin responsable"

            messagebox.showinfo(
                "Éxito",
                f"{tipo_movimiento} registrado correctamente.\n\n"
                f"Proyecto: {proyecto}\n"
                f"Responsable: {responsable_txt}",
                parent=self
            )

            self.cargar_ultimos_movimientos()
            self.limpiar_escaneo()

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

        self.win_retazo = ctk.CTkToplevel(self)
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
            text_color="gray",
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
            text_color="gray",
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
                    text_color="green"
                )

            except Exception as e:
                self.retazo_label_resultado.configure(
                    text=str(e),
                    text_color="red"
                )

        ctk.CTkButton(
            scroll,
            text="Calcular precio sugerido",
            fg_color="#1f538d",
            hover_color="#163c65",
            command=calcular_y_mostrar
        ).pack(fill="x", padx=35, pady=(10, 6))

        ctk.CTkButton(
            scroll,
            text="Guardar retazo",
            fg_color="green",
            hover_color="darkgreen",
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

            datos_retazo = {
                "codigo_barras": nuevo_codigo,
                "nombre": nombre_retazo,
                "categoria": prod_original.get("categoria", "Materiales"),
                "subcategoria": prod_original.get("subcategoria", ""),
                "marca": prod_original.get("marca", ""),
                "tamaño_dimensiones": tamano_retazo,
                "talla": prod_original.get("talla", ""),
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

            self.barcode.generar_codigo_barras(nuevo_codigo, nombre_retazo)

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
            self.limpiar_escaneo()

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
        self.limpiar_escaneo()

    def limpiar_escaneo(self):
        self.entrada_producto_salida.configure(state="normal")
        self.entrada_producto_salida.delete(0, "end")

        self.entrada_trabajador.configure(state="normal")
        self.entrada_trabajador.delete(0, "end")
        self.entrada_trabajador.configure(state="disabled")

        self.label_estado.configure(text="")

        self.after(200, self.entrada_producto_salida.focus_set)
