import customtkinter as ctk
from tkinter import ttk, messagebox
from PIL import Image
import os
from datetime import datetime
from uuid import uuid4
from utils import obtener_ruta_icono
import threading


class InventarioTab(ctk.CTkFrame):
    def __init__(self, master, db_manager, barcode_gen):
        super().__init__(master, fg_color="transparent")

        self.db = db_manager
        self.barcode = barcode_gen

        self.racks_cache = []
        self.ubicaciones_cache = []

        self.rack_codigo_a_id = {}
        self.rack_id_a_codigo = {}
        self.rack_por_id = {}
        self.ubicacion_por_id = {}
        self.bloques_por_posicion = {}
        self.subdivisiones_por_padre = {}
        self._carga_inventario_id = 0

        self.crear_interfaz()

    # ============================================================
    # INTERFAZ PRINCIPAL
    # ============================================================
    def crear_interfaz(self):
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.pack(fill="x", pady=10, padx=10)

        self.entry_busqueda = ctk.CTkEntry(
            frame_top,
            placeholder_text="🔍 Buscar nombre, código, categoría o ubicación...",
            width=280
        )
        self.entry_busqueda.pack(side="left", padx=5)
        self.entry_busqueda.bind("<Return>", lambda e: self.iniciar_carga_hilo())

        ctk.CTkButton(
            frame_top,
            text="Buscar",
            width=70,
            command=self.iniciar_carga_hilo
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="Limpiar",
            width=70,
            fg_color="#555555",
            hover_color="#333333",
            command=self.limpiar_filtros
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="Actualizar Lista",
            fg_color="#1f538d",
            hover_color="#163c65",
            command=self.iniciar_carga_hilo
        ).pack(side="left", padx=5)

        self.label_estado = ctk.CTkLabel(frame_top, text="", text_color="blue")
        self.label_estado.pack(side="left", padx=10)

        self.btn_excel = ctk.CTkButton(
            frame_top,
            text="Exportar a Excel",
            fg_color="#1D6F42",
            hover_color="#145A32",
            width=140,
            command=self.exportar_a_excel
        )
        self.btn_excel.pack(side="right", padx=5)

        self.btn_editar = ctk.CTkButton(
            frame_top,
            text="Editar Seleccionado",
            fg_color="#24608a",
            width=140,
            command=self.abrir_formulario_edicion
        )
        self.btn_editar.pack(side="right", padx=5)

        self.btn_nuevo = ctk.CTkButton(
            frame_top,
            text="+ Nuevo Producto",
            fg_color="green",
            hover_color="darkgreen",
            command=self.abrir_formulario_producto
        )
        self.btn_nuevo.pack(side="right", padx=(5, 0))

        self.btn_baja = ctk.CTkButton(
            frame_top,
            text="Dar de Baja",
            fg_color="#8B0000",
            hover_color="#5C0000",
            command=self.dar_de_baja
        )
        self.btn_baja.pack(side="right", padx=5)

        self.btn_restaurar = ctk.CTkButton(
            frame_top,
            text="Restaurar",
            fg_color="#B8860B",
            hover_color="#8B6508",
            command=self.restaurar_producto
        )
        self.btn_restaurar.pack(side="right", padx=5)

        self.btn_ver_codigo = ctk.CTkButton(
            frame_top,
            text="Ver Código de Barras",
            fg_color="#1f538d",
            command=self.ver_codigo_barras
        )
        self.btn_ver_codigo.pack(side="right", padx=5)

        # =========================
        # TABLA
        # =========================
        frame_tabla = ctk.CTkFrame(self)
        frame_tabla.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar_inv = ctk.CTkScrollbar(frame_tabla, orientation="vertical")
        scrollbar_inv.pack(side="right", fill="y")

        columnas = (
            "ID",
            "Código",
            "Nombre",
            "Categoría",
            "Marca/Subcategoría",
            "Stock",
            "Stock Mín.",
            "Precio",
            "Ubicación",
            "Estado"
        )

        columnas_visibles = (
            "Código",
            "Nombre",
            "Categoría",
            "Marca/Subcategoría",
            "Stock",
            "Stock Mín.",
            "Precio",
            "Ubicación",
            "Estado"
        )

        self.tabla_inventario = ttk.Treeview(
            frame_tabla,
            columns=columnas,
            displaycolumns=columnas_visibles,
            show="headings",
            height=15,
            yscrollcommand=scrollbar_inv.set
        )

        scrollbar_inv.configure(command=self.tabla_inventario.yview)

        self.tabla_inventario.tag_configure(
            "stock_bajo",
            background="#FFCCCC",
            foreground="black"
        )
        self.tabla_inventario.tag_configure(
            "stock_critico",
            background="#FF6666",
            foreground="white"
        )
        self.tabla_inventario.tag_configure(
            "inactivo",
            background="#D3D3D3",
            foreground="gray"
        )
        self.tabla_inventario.tag_configure("par", background="#F5F5F5")
        self.tabla_inventario.tag_configure("impar", background="#FFFFFF")

        anchos = {
            "Código": 120,
            "Nombre": 220,
            "Categoría": 120,
            "Marca/Subcategoría": 150,
            "Stock": 70,
            "Stock Mín.": 90,
            "Precio": 90,
            "Ubicación": 180,
            "Estado": 80
        }

        for col in columnas:
            self.tabla_inventario.heading(col, text=col)

        for col in columnas_visibles:
            self.tabla_inventario.heading(
                col,
                text=col,
                command=lambda c=col: self.ordenar_columna(c, False)
            )
            self.tabla_inventario.column(col, width=anchos[col], anchor="center")

        self.tabla_inventario.pack(side="left", fill="both", expand=True)

        # Retraso pequeño para evitar error de threading al abrir la app.
        self.after(500, self.iniciar_carga_hilo)

    # ============================================================
    # CARGA DE DATOS
    # ============================================================
    def limpiar_filtros(self):
        self.entry_busqueda.delete(0, "end")
        self.iniciar_carga_hilo()

    def iniciar_carga_hilo(self, *args):
        try:
            self.label_estado.configure(text="Cargando datos...", text_color="orange")

            for item in self.tabla_inventario.get_children():
                self.tabla_inventario.delete(item)

            texto_busqueda = self.entry_busqueda.get().strip().lower()
            self._carga_inventario_id += 1
            carga_id = self._carga_inventario_id

            hilo = threading.Thread(
                target=self.cargar_inventario_pesado,
                args=(texto_busqueda, carga_id),
                daemon=True
            )
            hilo.start()

        except Exception as e:
            print(f"Error iniciando carga inventario: {e}")

    def cargar_inventario_pesado(self, texto_busqueda, carga_id):
        try:
            productos = self.db.cargar_inventario_nube()
            filas_a_insertar = []

            for p in productos:
                nombre_prod = str(p.get("nombre", "")).lower()
                codigo_prod = str(p.get("codigo_barras", "")).lower()
                cat_prod = str(p.get("categoria", "")).lower()
                marca_prod = str(
                    p.get("subcategoria", "") or p.get("marca", "")
                ).lower()
                ubicacion_prod = str(p.get("ubicacion_codigo", "")).lower()

                if texto_busqueda and not (
                    texto_busqueda in nombre_prod
                    or texto_busqueda in codigo_prod
                    or texto_busqueda in cat_prod
                    or texto_busqueda in marca_prod
                    or texto_busqueda in ubicacion_prod
                ):
                    continue

                stock = int(p.get("stock") or 0)
                stock_minimo = int(p.get("stock_minimo") or 0)

                tag = ""

                if stock <= 0:
                    tag = "stock_critico"
                elif stock_minimo > 0 and stock <= stock_minimo:
                    tag = "stock_bajo"

                estado_actual = p.get("estado", "Activo")

                if estado_actual == "Inactivo":
                    tag = "inactivo"

                fila = (
                    p.get("id", ""),
                    p.get("codigo_barras", ""),
                    p.get("nombre", ""),
                    p.get("categoria", "") or "-",
                    p.get("subcategoria", "") or p.get("marca", "") or "-",
                    stock,
                    stock_minimo,
                    p.get("precio_unitario", 0),
                    p.get("ubicacion_codigo", "-"),
                    estado_actual
                )

                filas_a_insertar.append({
                    "values": fila,
                    "tags": (tag,) if tag else ()
                })

            try:
                if self.winfo_exists():
                    self.after(
                        0,
                        self.actualizar_interfaz_tabla,
                        filas_a_insertar,
                        carga_id
                    )
            except RuntimeError as e:
                print(f"No se pudo actualizar la tabla de inventario: {e}")
            except Exception as e:
                print(f"Error actualizando interfaz de inventario: {e}")

        except Exception as e:
            print(f"Error cargando inventario pesado: {e}")

    def actualizar_interfaz_tabla(self, filas, carga_id):
        try:
            if carga_id != self._carga_inventario_id:
                return

            for item in self.tabla_inventario.get_children():
                self.tabla_inventario.delete(item)

            for i, f in enumerate(filas):
                etiquetas = f["tags"]

                if not etiquetas:
                    etiquetas = ("par",) if i % 2 == 0 else ("impar",)

                self.tabla_inventario.insert(
                    "",
                    "end",
                    values=f["values"],
                    tags=etiquetas
                )

            self.label_estado.configure(
                text=f"{len(filas)} prod.",
                text_color="green"
            )

        except Exception as e:
            print(f"Error actualizando tabla inventario: {e}")

    def ordenar_columna(self, col, reverse):
        lista_items = [
            (self.tabla_inventario.set(k, col), k)
            for k in self.tabla_inventario.get_children("")
        ]

        try:
            lista_items.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            lista_items.sort(reverse=reverse)

        for index, (val, k) in enumerate(lista_items):
            self.tabla_inventario.move(k, "", index)

        self.tabla_inventario.heading(
            col,
            command=lambda: self.ordenar_columna(col, not reverse)
        )

    # ============================================================
    # EXPORTAR
    # ============================================================
    def exportar_a_excel(self):
        try:
            import pandas as pd
            from tkinter import filedialog

            columnas = [
                "ID",
                "Código",
                "Nombre",
                "Categoría",
                "Marca/Subcategoría",
                "Stock",
                "Stock Mín.",
                "Precio",
                "Ubicación",
                "Estado"
            ]

            data = []

            for child in self.tabla_inventario.get_children():
                data.append(self.tabla_inventario.item(child)["values"])

            if not data:
                return messagebox.showwarning(
                    "Aviso",
                    "No hay datos para exportar."
                )

            df = pd.DataFrame(data, columns=columnas)

            ruta = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")]
            )

            if ruta:
                df.to_excel(ruta, index=False)
                messagebox.showinfo(
                    "Éxito",
                    "Archivo Excel generado correctamente."
                )

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar: {e}")

    # ============================================================
    # UBICACIONES - SELECTOR AMIGABLE
    # ============================================================
    def cargar_datos_ubicaciones_selector(self):
        self.racks_cache = self.db.cargar_racks()
        self.ubicaciones_cache = self.db.cargar_ubicaciones(solo_activas=True)

        self.rack_codigo_a_id = {}
        self.rack_id_a_codigo = {}
        self.rack_por_id = {}

        for r in self.racks_cache:
            codigo = r.get("codigo_rack")
            rack_id = r.get("id")

            if codigo and rack_id:
                self.rack_codigo_a_id[codigo] = rack_id
                self.rack_id_a_codigo[rack_id] = codigo
                self.rack_por_id[rack_id] = r

        self.ubicacion_por_id = {}
        self.bloques_por_posicion = {}
        self.subdivisiones_por_padre = {}

        for u in self.ubicaciones_cache:
            ubicacion_id = u.get("id")
            self.ubicacion_por_id[ubicacion_id] = u

            if u.get("tipo") == "Bloque":
                llave = (
                    u.get("rack_id"),
                    u.get("nivel"),
                    u.get("columna")
                )
                self.bloques_por_posicion[llave] = u

            elif u.get("tipo") == "Subdivision":
                padre_id = u.get("ubicacion_padre_id")

                if padre_id not in self.subdivisiones_por_padre:
                    self.subdivisiones_por_padre[padre_id] = []

                self.subdivisiones_por_padre[padre_id].append(u)

    def crear_selector_ubicacion(self, parent, prefijo, ubicacion_id_actual=None):
        self.cargar_datos_ubicaciones_selector()

        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=0, pady=(5, 12))
        frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            frame,
            text="Rack:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            frame,
            text="Nivel:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=1, sticky="w", padx=10, pady=(10, 0))

        rack_values = ["Sin ubicación"] + sorted(
            list(self.rack_codigo_a_id.keys())
        )

        combo_rack = ctk.CTkComboBox(
            frame,
            values=rack_values,
            width=170,
            state="readonly"
        )
        combo_rack.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        combo_nivel = ctk.CTkComboBox(
            frame,
            values=["N01", "N02", "N03"],
            width=170,
            state="readonly"
        )
        combo_nivel.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(
            frame,
            text="Columna:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(8, 0))

        ctk.CTkLabel(
            frame,
            text="Subdivisión:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=2, column=1, sticky="w", padx=10, pady=(8, 0))

        combo_columna = ctk.CTkComboBox(
            frame,
            values=["C01", "C02", "C03"],
            width=170,
            state="readonly"
        )
        combo_columna.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        combo_subdivision = ctk.CTkComboBox(
            frame,
            values=["Sin subdivisión"],
            width=170,
            state="readonly"
        )
        combo_subdivision.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        label_resultado = ctk.CTkLabel(
            frame,
            text="Ubicación seleccionada: Sin ubicación",
            text_color="gray",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_resultado.grid(
            row=4,
            column=0,
            columnspan=2,
            padx=10,
            pady=(8, 10),
            sticky="ew"
        )

        setattr(self, f"{prefijo}_combo_rack", combo_rack)
        setattr(self, f"{prefijo}_combo_nivel", combo_nivel)
        setattr(self, f"{prefijo}_combo_columna", combo_columna)
        setattr(self, f"{prefijo}_combo_subdivision", combo_subdivision)
        setattr(self, f"{prefijo}_label_ubicacion", label_resultado)

        combo_rack.configure(
            command=lambda value=None: self.actualizar_selector_ubicacion(prefijo)
        )
        combo_nivel.configure(
            command=lambda value=None: self.actualizar_selector_ubicacion(prefijo)
        )
        combo_columna.configure(
            command=lambda value=None: self.actualizar_selector_ubicacion(prefijo)
        )
        combo_subdivision.configure(
            command=lambda value=None: self.actualizar_selector_ubicacion(prefijo)
        )

        combo_rack.set("Sin ubicación")
        combo_nivel.set("N01")
        combo_columna.set("C01")
        combo_subdivision.set("Sin subdivisión")

        if ubicacion_id_actual:
            self.seleccionar_ubicacion_en_selector(
                prefijo,
                ubicacion_id_actual
            )
        else:
            self.actualizar_selector_ubicacion(prefijo)

        return frame

    def actualizar_selector_ubicacion(self, prefijo):
        combo_rack = getattr(self, f"{prefijo}_combo_rack")
        combo_nivel = getattr(self, f"{prefijo}_combo_nivel")
        combo_columna = getattr(self, f"{prefijo}_combo_columna")
        combo_subdivision = getattr(self, f"{prefijo}_combo_subdivision")
        label_resultado = getattr(self, f"{prefijo}_label_ubicacion")

        rack_codigo = combo_rack.get()

        if rack_codigo == "Sin ubicación":
            combo_nivel.configure(state="disabled")
            combo_columna.configure(state="disabled")
            combo_subdivision.configure(state="disabled")
            label_resultado.configure(
                text="Ubicación seleccionada: Sin ubicación",
                text_color="gray"
            )
            return

        combo_nivel.configure(state="readonly")
        combo_columna.configure(state="readonly")
        combo_subdivision.configure(state="readonly")

        rack_id = self.rack_codigo_a_id.get(rack_codigo)
        rack = self.rack_por_id.get(rack_id, {})

        niveles_disponibles = [
            f"N{i:02d}"
            for i in range(1, int(rack.get("niveles") or 3) + 1)
        ]
        columnas_disponibles = [
            f"C{i:02d}"
            for i in range(1, int(rack.get("columnas") or 3) + 1)
        ]
        nivel_actual = combo_nivel.get()
        columna_actual = combo_columna.get()
        combo_nivel.configure(values=niveles_disponibles)
        combo_columna.configure(values=columnas_disponibles)
        combo_nivel.set(
            nivel_actual
            if nivel_actual in niveles_disponibles
            else niveles_disponibles[0]
        )
        combo_columna.set(
            columna_actual
            if columna_actual in columnas_disponibles
            else columnas_disponibles[0]
        )

        nivel = combo_nivel.get()
        columna = combo_columna.get()

        bloque = self.bloques_por_posicion.get((rack_id, nivel, columna))

        if not bloque:
            combo_subdivision.configure(values=["Sin subdivisión"])
            combo_subdivision.set("Sin subdivisión")
            label_resultado.configure(
                text=(
                    f"Ubicación seleccionada: "
                    f"{rack_codigo}-{nivel}-{columna} no existe"
                ),
                text_color="orange"
            )
            return

        subdivisiones = self.subdivisiones_por_padre.get(bloque.get("id"), [])
        valores_sub = ["Sin subdivisión"]

        for sub in subdivisiones:
            if sub.get("subdivision"):
                valores_sub.append(sub.get("subdivision"))

        subdivision_actual = combo_subdivision.get()
        combo_subdivision.configure(values=valores_sub)

        if subdivision_actual in valores_sub:
            combo_subdivision.set(subdivision_actual)
        else:
            combo_subdivision.set("Sin subdivisión")

        ubicacion_id = self.obtener_ubicacion_id_selector(prefijo)
        ubicacion = self.ubicacion_por_id.get(ubicacion_id)

        if ubicacion:
            label_resultado.configure(
                text=(
                    f"Ubicación seleccionada: "
                    f"{ubicacion.get('codigo_ubicacion')}"
                ),
                text_color="#1f538d"
            )
        else:
            label_resultado.configure(
                text="Ubicación seleccionada: Sin ubicación",
                text_color="gray"
            )

    def obtener_ubicacion_id_selector(self, prefijo):
        combo_rack = getattr(self, f"{prefijo}_combo_rack")
        combo_nivel = getattr(self, f"{prefijo}_combo_nivel")
        combo_columna = getattr(self, f"{prefijo}_combo_columna")
        combo_subdivision = getattr(self, f"{prefijo}_combo_subdivision")

        rack_codigo = combo_rack.get()

        if rack_codigo == "Sin ubicación":
            return None

        rack_id = self.rack_codigo_a_id.get(rack_codigo)
        nivel = combo_nivel.get()
        columna = combo_columna.get()
        subdivision = combo_subdivision.get()

        bloque = self.bloques_por_posicion.get((rack_id, nivel, columna))

        if not bloque:
            return None

        if subdivision == "Sin subdivisión":
            return bloque.get("id")

        subdivisiones = self.subdivisiones_por_padre.get(bloque.get("id"), [])

        for sub in subdivisiones:
            if sub.get("subdivision") == subdivision:
                return sub.get("id")

        return bloque.get("id")

    def seleccionar_ubicacion_en_selector(self, prefijo, ubicacion_id_actual):
        ubicacion = self.ubicacion_por_id.get(ubicacion_id_actual)

        combo_rack = getattr(self, f"{prefijo}_combo_rack")
        combo_nivel = getattr(self, f"{prefijo}_combo_nivel")
        combo_columna = getattr(self, f"{prefijo}_combo_columna")
        combo_subdivision = getattr(self, f"{prefijo}_combo_subdivision")

        if not ubicacion:
            combo_rack.set("Sin ubicación")
            self.actualizar_selector_ubicacion(prefijo)
            return

        if ubicacion.get("tipo") == "Subdivision":
            padre = self.ubicacion_por_id.get(
                ubicacion.get("ubicacion_padre_id")
            )

            if padre:
                rack_codigo = self.rack_id_a_codigo.get(
                    padre.get("rack_id"),
                    "Sin ubicación"
                )
                combo_rack.set(rack_codigo)
                combo_nivel.set(padre.get("nivel", "N01"))
                combo_columna.set(padre.get("columna", "C01"))

                self.actualizar_selector_ubicacion(prefijo)

                combo_subdivision.set(
                    ubicacion.get("subdivision", "Sin subdivisión")
                )
                self.actualizar_selector_ubicacion(prefijo)
                return

        rack_codigo = self.rack_id_a_codigo.get(
            ubicacion.get("rack_id"),
            "Sin ubicación"
        )
        combo_rack.set(rack_codigo)
        combo_nivel.set(ubicacion.get("nivel", "N01"))
        combo_columna.set(ubicacion.get("columna", "C01"))
        combo_subdivision.set("Sin subdivisión")

        self.actualizar_selector_ubicacion(prefijo)

    # ============================================================
    # MEDICIÓN ESTRUCTURADA PARA RETAZOS
    # ============================================================
    def crear_selector_medicion(self, parent, prefijo, producto_actual=None):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=0, pady=(5, 12))
        frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            frame,
            text="Tipo medición:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            frame,
            text="Unidad:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=1, sticky="w", padx=10, pady=(10, 0))

        combo_tipo = ctk.CTkComboBox(
            frame,
            values=["No aplica", "Largo", "Área", "Porcentaje"],
            state="readonly",
            width=170,
            command=lambda value=None: self.actualizar_estado_medicion(prefijo)
        )
        combo_tipo.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        combo_unidad = ctk.CTkComboBox(
            frame,
            values=["mm", "cm", "m", "unidad", "%"],
            state="readonly",
            width=170
        )
        combo_unidad.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(
            frame,
            text="Largo / medida principal:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(8, 0))

        ctk.CTkLabel(
            frame,
            text="Ancho:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=2, column=1, sticky="w", padx=10, pady=(8, 0))

        entry_largo = ctk.CTkEntry(
            frame,
            placeholder_text="Ej: 6, 200, 50",
            width=170
        )
        entry_largo.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        entry_ancho = ctk.CTkEntry(
            frame,
            placeholder_text="Solo si es área",
            width=170
        )
        entry_ancho.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        label_ayuda = ctk.CTkLabel(
            frame,
            text=(
                "Para retazos: Largo = perfiles/tubos/barras. "
                "Área = planchas/mallas."
            ),
            text_color="gray",
            font=ctk.CTkFont(size=11),
            wraplength=390
        )
        label_ayuda.grid(
            row=4,
            column=0,
            columnspan=2,
            padx=10,
            pady=(5, 10),
            sticky="ew"
        )

        setattr(self, f"{prefijo}_combo_tipo_medicion", combo_tipo)
        setattr(self, f"{prefijo}_combo_unidad_medida", combo_unidad)
        setattr(self, f"{prefijo}_entry_medida_largo", entry_largo)
        setattr(self, f"{prefijo}_entry_medida_ancho", entry_ancho)

        tipo = "No aplica"
        unidad = "unidad"
        largo = ""
        ancho = ""

        if producto_actual:
            tipo = producto_actual.get("tipo_medicion") or "No aplica"
            unidad = producto_actual.get("unidad_medida") or "unidad"

            if producto_actual.get("medida_largo") is not None:
                largo = str(producto_actual.get("medida_largo"))

            if producto_actual.get("medida_ancho") is not None:
                ancho = str(producto_actual.get("medida_ancho"))

        combo_tipo.set(tipo)
        combo_unidad.set(unidad)

        entry_largo.insert(0, largo)
        entry_ancho.insert(0, ancho)

        self.actualizar_estado_medicion(prefijo)

        return frame

    def actualizar_estado_medicion(self, prefijo):
        combo_tipo = getattr(self, f"{prefijo}_combo_tipo_medicion")
        combo_unidad = getattr(self, f"{prefijo}_combo_unidad_medida")
        entry_largo = getattr(self, f"{prefijo}_entry_medida_largo")
        entry_ancho = getattr(self, f"{prefijo}_entry_medida_ancho")

        tipo = combo_tipo.get()

        if tipo == "No aplica":
            combo_unidad.configure(state="disabled")
            entry_largo.configure(state="disabled")
            entry_ancho.configure(state="disabled")

        elif tipo == "Largo":
            combo_unidad.configure(state="readonly")
            entry_largo.configure(state="normal")
            entry_ancho.configure(state="disabled")
            entry_ancho.delete(0, "end")

            if combo_unidad.get() == "%":
                combo_unidad.set("m")

        elif tipo == "Área":
            combo_unidad.configure(state="readonly")
            entry_largo.configure(state="normal")
            entry_ancho.configure(state="normal")

            if combo_unidad.get() == "%":
                combo_unidad.set("cm")

        elif tipo == "Porcentaje":
            combo_unidad.configure(state="readonly")
            combo_unidad.set("%")
            combo_unidad.configure(state="disabled")

            entry_largo.configure(state="disabled")
            entry_ancho.configure(state="disabled")
            entry_largo.delete(0, "end")
            entry_ancho.delete(0, "end")

    def convertir_numero_decimal(self, texto):
        texto = str(texto).strip().replace(",", ".")

        if texto == "":
            return None

        return float(texto)

    def obtener_datos_medicion(self, prefijo):
        combo_tipo = getattr(self, f"{prefijo}_combo_tipo_medicion")
        combo_unidad = getattr(self, f"{prefijo}_combo_unidad_medida")
        entry_largo = getattr(self, f"{prefijo}_entry_medida_largo")
        entry_ancho = getattr(self, f"{prefijo}_entry_medida_ancho")

        tipo = combo_tipo.get()
        unidad = combo_unidad.get()

        if tipo == "No aplica":
            return {
                "tipo_medicion": "No aplica",
                "medida_largo": None,
                "medida_ancho": None,
                "unidad_medida": None
            }

        if tipo == "Porcentaje":
            return {
                "tipo_medicion": "Porcentaje",
                "medida_largo": None,
                "medida_ancho": None,
                "unidad_medida": "%"
            }

        try:
            largo = self.convertir_numero_decimal(entry_largo.get())

            if largo is None or largo <= 0:
                raise ValueError

        except Exception:
            raise ValueError(
                "Debe ingresar una medida principal válida mayor a 0."
            )

        ancho = None

        if tipo == "Área":
            try:
                ancho = self.convertir_numero_decimal(entry_ancho.get())

                if ancho is None or ancho <= 0:
                    raise ValueError

            except Exception:
                raise ValueError(
                    "Debe ingresar un ancho válido mayor a 0 "
                    "para productos por área."
                )

        return {
            "tipo_medicion": tipo,
            "medida_largo": largo,
            "medida_ancho": ancho,
            "unidad_medida": unidad
        }

    # ============================================================
    # CÓDIGO DE BARRAS
    # ============================================================
    def ver_codigo_barras(self):
        seleccion = self.tabla_inventario.selection()

        if not seleccion:
            return messagebox.showwarning("Aviso", "Seleccione un producto.")

        item = self.tabla_inventario.item(seleccion[0])
        cod = str(item["values"][1])
        nom = str(item["values"][2])

        ruta = self.barcode.obtener_ruta_codigo_barras(cod, nom)

        if not os.path.exists(ruta):
            respuesta = messagebox.askyesno(
                "Código no encontrado",
                "No se encontró la imagen del código de barras.\n\n"
                "¿Desea generarla nuevamente?"
            )

            if respuesta:
                creado = self.barcode.generar_codigo_barras(cod, nom)

                if not creado:
                    return messagebox.showerror(
                        "Error",
                        "No se pudo generar el código de barras."
                    )
            else:
                return

        win = ctk.CTkToplevel(self)
        win.title("Código de Barras")
        win.geometry("420x300")
        win.grab_set()

        try:
            win.after(
                200,
                lambda: win.iconbitmap(obtener_ruta_icono("icono.ico"))
            )
        except Exception:
            pass

        imagen_pil = Image.open(ruta)
        img = ctk.CTkImage(
            light_image=imagen_pil,
            dark_image=imagen_pil,
            size=(300, 120)
        )

        ctk.CTkLabel(win, image=img, text="").pack(pady=20)

        ctk.CTkLabel(
            win,
            text=f"Código: {cod}",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=(0, 10))

        ctk.CTkButton(
            win,
            text="Descargar",
            command=lambda: self.barcode.exportar_archivo(
                ruta,
                f"{cod}.png",
                win
            )
        ).pack()

    # ============================================================
    # BAJA / RESTAURAR
    # ============================================================
    def dar_de_baja(self):
        seleccion = self.tabla_inventario.selection()

        if not seleccion:
            return messagebox.showwarning(
                "Aviso",
                "Seleccione un producto para dar de baja."
            )

        item = self.tabla_inventario.item(seleccion[0])
        id_producto = item["values"][0]
        nombre_producto = item["values"][2]

        if messagebox.askyesno(
            "Confirmar Baja",
            f"¿Seguro que desea dar de baja y desactivar: {nombre_producto}?"
        ):
            exito, msg = self.db.dar_de_baja_producto(id_producto)

            if exito:
                messagebox.showinfo("Éxito", msg)
                self.iniciar_carga_hilo()
            else:
                messagebox.showerror("Error", msg)

    def restaurar_producto(self):
        seleccion = self.tabla_inventario.selection()

        if not seleccion:
            return messagebox.showwarning(
                "Aviso",
                "Seleccione un producto para restaurar."
            )

        item = self.tabla_inventario.item(seleccion[0])

        id_producto = item["values"][0]
        nombre_producto = item["values"][2]
        estado = item["values"][9]

        if estado == "Activo":
            return messagebox.showinfo(
                "Aviso",
                "Este producto ya se encuentra activo."
            )

        if messagebox.askyesno(
            "Restaurar",
            f"¿Desea volver a activar: {nombre_producto}?"
        ):
            exito, msg = self.db.restaurar_producto_nube(id_producto)

            if exito:
                messagebox.showinfo("Éxito", msg)
                self.iniciar_carga_hilo()
            else:
                messagebox.showerror("Error", msg)

    # ============================================================
    # NUEVO PRODUCTO
    # ============================================================
    def abrir_formulario_producto(self):
        self.ventana_nuevo = ctk.CTkToplevel(self)
        self.ventana_nuevo.title("Agregar Nuevo Producto")
        self.ventana_nuevo.geometry("560x760")
        self.ventana_nuevo.minsize(560, 760)
        self.ventana_nuevo.grab_set()

        try:
            self.ventana_nuevo.after(
                200,
                lambda: self.ventana_nuevo.iconbitmap(
                    obtener_ruta_icono("icono.ico")
                )
            )
        except Exception:
            pass

        scroll = ctk.CTkScrollableFrame(self.ventana_nuevo)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            scroll,
            text="Registro Manual de Producto",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=15)

        categorias = [
            "Herramientas",
            "Insumos",
            "EPP",
            "Equipos",
            "Materiales",
            "Otros"
        ]

        self.entry_nombre = ctk.CTkEntry(
            scroll,
            placeholder_text="Nombre del Producto",
            width=390
        )
        self.entry_nombre.pack(pady=5)

        ctk.CTkLabel(
            scroll,
            text="Seleccione Categoría:",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(10, 0))

        self.combo_categoria = ctk.CTkComboBox(
            scroll,
            values=categorias,
            width=390,
            state="readonly"
        )
        self.combo_categoria.pack(pady=5)
        self.combo_categoria.set(categorias[0])

        self.entry_subcategoria = ctk.CTkEntry(
            scroll,
            placeholder_text="Subcategoría",
            width=390
        )
        self.entry_subcategoria.pack(pady=5)

        self.entry_marca = ctk.CTkEntry(
            scroll,
            placeholder_text="Marca",
            width=390
        )
        self.entry_marca.pack(pady=5)

        self.entry_tamano = ctk.CTkEntry(
            scroll,
            placeholder_text="Tamaño / Dimensiones",
            width=390
        )
        self.entry_tamano.pack(pady=5)

        self.entry_talla = ctk.CTkEntry(
            scroll,
            placeholder_text="Talla (Si aplica)",
            width=390
        )
        self.entry_talla.pack(pady=5)

        self.entry_stock = ctk.CTkEntry(
            scroll,
            placeholder_text="Stock Inicial",
            width=390
        )
        self.entry_stock.pack(pady=5)

        self.entry_stock_minimo = ctk.CTkEntry(
            scroll,
            placeholder_text="Stock Mínimo",
            width=390
        )
        self.entry_stock_minimo.pack(pady=5)

        self.entry_precio = ctk.CTkEntry(
            scroll,
            placeholder_text="Precio Unitario Neto",
            width=390
        )
        self.entry_precio.pack(pady=5)

        ctk.CTkLabel(
            scroll,
            text="Medición para retazos:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=(10, 0))

        self.crear_selector_medicion(
            scroll,
            prefijo="nuevo",
            producto_actual=None
        )

        ctk.CTkLabel(
            scroll,
            text="Ubicación física:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=(10, 0))

        self.crear_selector_ubicacion(
            scroll,
            prefijo="nuevo",
            ubicacion_id_actual=None
        )

        ctk.CTkButton(
            scroll,
            text="Guardar Producto",
            fg_color="green",
            hover_color="darkgreen",
            height=45,
            width=390,
            command=self.guardar_producto
        ).pack(pady=15)

    def guardar_producto(self):
        nombre = self.entry_nombre.get().strip()
        cat = self.combo_categoria.get().strip()
        subcat = self.entry_subcategoria.get().strip()
        marca = self.entry_marca.get().strip()
        tam = self.entry_tamano.get().strip()
        talla = self.entry_talla.get().strip()
        stock = self.entry_stock.get().strip()
        stock_minimo = self.entry_stock_minimo.get().strip()
        precio = self.entry_precio.get().strip()

        if not all([nombre, stock]):
            return messagebox.showwarning(
                "Error",
                "Nombre y Stock son obligatorios.",
                parent=self.ventana_nuevo
            )

        try:
            stock_int = int(stock)
            if stock_int < 0:
                raise ValueError
        except Exception:
            return messagebox.showwarning(
                "Error",
                "El stock debe ser un número entero mayor o igual a 0.",
                parent=self.ventana_nuevo
            )

        try:
            stock_minimo_int = int(stock_minimo) if stock_minimo else 0
            if stock_minimo_int < 0:
                raise ValueError
        except Exception:
            return messagebox.showwarning(
                "Error",
                "El stock mínimo debe ser un número entero mayor o igual a 0.",
                parent=self.ventana_nuevo
            )

        try:
            precio_int = int(precio) if precio else 0
            if precio_int < 0:
                raise ValueError
        except Exception:
            return messagebox.showwarning(
                "Error",
                "El precio debe ser un número entero mayor o igual a 0.",
                parent=self.ventana_nuevo
            )

        ubicacion_id = self.obtener_ubicacion_id_selector("nuevo")

        try:
            datos_medicion = self.obtener_datos_medicion("nuevo")
        except ValueError as e:
            return messagebox.showwarning(
                "Error en medición",
                str(e),
                parent=self.ventana_nuevo
            )

        cod = f"PRD{datetime.now().strftime('%y%m%d')}{uuid4().hex[:10].upper()}"

        exito, msg = self.db.guardar_producto_nube(
            cod,
            "",
            nombre,
            cat,
            subcat,
            tam,
            talla,
            stock_int,
            precio_int,
            ubicacion_id=ubicacion_id,
            stock_minimo=stock_minimo_int,
            marca=marca,
            tipo_medicion=datos_medicion["tipo_medicion"],
            medida_largo=datos_medicion["medida_largo"],
            medida_ancho=datos_medicion["medida_ancho"],
            unidad_medida=datos_medicion["unidad_medida"]
        )

        if exito:
            codigo_creado = self.barcode.generar_codigo_barras(cod, nombre)

            if codigo_creado:
                messagebox.showinfo(
                    "Éxito",
                    "Producto registrado correctamente.\n\n"
                    "El código de barras fue creado en:\n"
                    f"{self.barcode.products_dir}",
                    parent=self.ventana_nuevo
                )
            else:
                messagebox.showwarning(
                    "Producto guardado",
                    "El producto fue guardado en la base de datos, "
                    "pero no se pudo crear el código de barras.",
                    parent=self.ventana_nuevo
                )

            self.ventana_nuevo.destroy()
            self.iniciar_carga_hilo()

        else:
            messagebox.showerror("Error", msg, parent=self.ventana_nuevo)

    # ============================================================
    # EDITAR PRODUCTO
    # ============================================================
    def abrir_formulario_edicion(self):
        seleccion = self.tabla_inventario.selection()

        if not seleccion:
            return messagebox.showwarning(
                "Aviso",
                "Por favor, selecciona un producto de la tabla."
            )

        item = self.tabla_inventario.item(seleccion[0])
        codigo_barras = str(item["values"][1])

        prod_db = self.db.buscar_producto_por_codigo(codigo_barras)

        if not prod_db:
            return messagebox.showerror(
                "Error",
                "No se encontró la información completa en la base de datos."
            )

        self.ventana_editar = ctk.CTkToplevel(self)
        self.ventana_editar.title("Editar Producto")
        self.ventana_editar.geometry("560x760")
        self.ventana_editar.minsize(560, 760)
        self.ventana_editar.grab_set()

        try:
            self.ventana_editar.after(
                200,
                lambda: self.ventana_editar.iconbitmap(
                    obtener_ruta_icono("icono.ico")
                )
            )
        except Exception:
            pass

        scroll = ctk.CTkScrollableFrame(self.ventana_editar)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            scroll,
            text="EDITAR PRODUCTO",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            scroll,
            text=f"Código: {prod_db.get('codigo_barras', '')}",
            text_color="gray"
        ).pack(pady=(0, 20))

        frame_form = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_form.pack(fill="both", expand=True, padx=40)

        ctk.CTkLabel(
            frame_form,
            text="Nombre:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")

        self.ed_nombre = ctk.CTkEntry(frame_form, height=35)
        self.ed_nombre.insert(0, prod_db.get("nombre", ""))
        self.ed_nombre.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            frame_form,
            text="Categoría:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")

        categorias = [
            "Herramientas",
            "Insumos",
            "EPP",
            "Equipos",
            "Materiales",
            "Otros"
        ]

        self.ed_cat = ctk.CTkComboBox(
            frame_form,
            values=categorias,
            height=35,
            state="readonly"
        )
        self.ed_cat.set(
            prod_db.get("categoria")
            if prod_db.get("categoria") in categorias
            else categorias[0]
        )
        self.ed_cat.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            frame_form,
            text="Subcategoría:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")

        self.ed_subcat = ctk.CTkEntry(frame_form, height=35)
        self.ed_subcat.insert(0, prod_db.get("subcategoria", "") or "")
        self.ed_subcat.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            frame_form,
            text="Marca:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")

        self.ed_marca = ctk.CTkEntry(frame_form, height=35)
        self.ed_marca.insert(0, prod_db.get("marca", "") or "")
        self.ed_marca.pack(fill="x", pady=(0, 10))

        frame_num = ctk.CTkFrame(frame_form, fg_color="transparent")
        frame_num.pack(fill="x", pady=(0, 15))
        frame_num.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            frame_num,
            text="Precio:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self.ed_precio = ctk.CTkEntry(frame_num, height=35)
        self.ed_precio.insert(0, prod_db.get("precio_unitario", 0))
        self.ed_precio.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkLabel(
            frame_num,
            text="Stock (solo movimientos):",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=1, sticky="w")

        self.ed_stock = ctk.CTkEntry(frame_num, height=35)
        self.ed_stock.insert(0, prod_db.get("stock", 0))
        self.ed_stock.configure(state="disabled")
        self.ed_stock.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkLabel(
            frame_num,
            text="Stock mín.:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=2, sticky="w")

        self.ed_stock_min = ctk.CTkEntry(frame_num, height=35)
        self.ed_stock_min.insert(0, prod_db.get("stock_minimo", 0))
        self.ed_stock_min.grid(row=1, column=2, sticky="ew")

        ctk.CTkLabel(
            frame_form,
            text="Medición para retazos:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")

        self.crear_selector_medicion(
            frame_form,
            prefijo="editar",
            producto_actual=prod_db
        )

        ctk.CTkLabel(
            frame_form,
            text="Ubicación:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")

        self.crear_selector_ubicacion(
            frame_form,
            prefijo="editar",
            ubicacion_id_actual=prod_db.get("ubicacion_id")
        )

        self.guardando_edicion = False

        self.btn_guardar_edicion = ctk.CTkButton(
    scroll,
    text="GUARDAR CAMBIOS",
    height=45,
    fg_color="#24608a",
    font=ctk.CTkFont(weight="bold", size=14),
    command=lambda: self.guardar_edicion(prod_db.get("id"))
)
        self.btn_guardar_edicion.pack(fill="x", padx=40, pady=15)

    def guardar_edicion(self, id_prod):
        try:
            # Evita doble clic o doble ejecución del botón
            if getattr(self, "guardando_edicion", False):
                return

            self.guardando_edicion = True

            if hasattr(self, "btn_guardar_edicion"):
                try:
                    self.btn_guardar_edicion.configure(
                        state="disabled",
                        text="Guardando..."
                    )
                except Exception:
                    pass

            # Si la ventana ya fue cerrada, no intentar leer campos destruidos
            if not hasattr(self, "ventana_editar") or not self.ventana_editar.winfo_exists():
                self.guardando_edicion = False
                return

            widgets = [
                self.ed_precio,
                self.ed_stock,
                self.ed_stock_min,
                self.ed_nombre,
                self.ed_cat,
                self.ed_subcat,
                self.ed_marca
            ]

            for w in widgets:
                if not w.winfo_exists():
                    self.guardando_edicion = False
                    return

            precio_txt = self.ed_precio.get().strip()
            stock_min_txt = self.ed_stock_min.get().strip()

            precio = int(precio_txt) if precio_txt else 0
            stock_min = int(stock_min_txt) if stock_min_txt else 0

            if precio < 0 or stock_min < 0:
                raise ValueError(
                    "El precio y el stock mínimo deben ser mayores o iguales a 0."
                )

            nombre = self.ed_nombre.get().strip()
            if not nombre:
                raise ValueError("El nombre del producto es obligatorio.")

            ubicacion_id = self.obtener_ubicacion_id_selector("editar")
            datos_medicion = self.obtener_datos_medicion("editar")

            datos = {
                "nombre": nombre,
                "categoria": self.ed_cat.get(),
                "subcategoria": self.ed_subcat.get().strip(),
                "marca": self.ed_marca.get().strip(),
                "precio_unitario": precio,
                "stock_minimo": stock_min,
                "ubicacion_id": ubicacion_id,
                "tipo_medicion": datos_medicion["tipo_medicion"],
                "medida_largo": datos_medicion["medida_largo"],
                "medida_ancho": datos_medicion["medida_ancho"],
                "unidad_medida": datos_medicion["unidad_medida"]
            }

            exito, msg = self.db.actualizar_producto_nube(id_prod, datos)

            if exito:
                messagebox.showinfo("Éxito", msg, parent=self.ventana_editar)

                if self.ventana_editar.winfo_exists():
                    self.ventana_editar.destroy()

                self.iniciar_carga_hilo()
                self.guardando_edicion = False

            else:
                self.guardando_edicion = False

                if hasattr(self, "btn_guardar_edicion"):
                    try:
                        self.btn_guardar_edicion.configure(
                            state="normal",
                            text="GUARDAR CAMBIOS"
                        )
                    except Exception:
                        pass

                messagebox.showerror("Error", msg, parent=self.ventana_editar)

        except ValueError as e:
            self.guardando_edicion = False

            if hasattr(self, "btn_guardar_edicion"):
                try:
                    self.btn_guardar_edicion.configure(
                        state="normal",
                        text="GUARDAR CAMBIOS"
                    )
                except Exception:
                    pass

            messagebox.showerror(
                "Error",
                str(e),
                parent=self.ventana_editar
            )

        except Exception as e:
            self.guardando_edicion = False

            if hasattr(self, "btn_guardar_edicion"):
                try:
                    self.btn_guardar_edicion.configure(
                        state="normal",
                        text="GUARDAR CAMBIOS"
                    )
                except Exception:
                    pass

            try:
                messagebox.showerror(
                    "Error",
                    f"No se pudo guardar la edición: {e}",
                    parent=self.ventana_editar
                )
            except Exception:
                print(f"No se pudo guardar la edición: {e}")
