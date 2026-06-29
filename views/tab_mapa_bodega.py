import customtkinter as ctk
from tkinter import ttk, messagebox
import threading


class MapaBodegaTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")

        self.db = db_manager

        self.bodegas = []
        self.racks = []

        self.mapa_bodegas = {}
        self.mapa_racks = {}

        self.datos_mapa = {}
        self.ubicacion_seleccionada = None
        self._solicitud_mapa = 0

        self.crear_interfaz()
        self.after(2000, self.cargar_bodegas_inicial)

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # =========================
        # BARRA SUPERIOR
        # =========================
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.grid(row=0, column=0, sticky="ew", padx=15, pady=10)

        ctk.CTkLabel(
            frame_top,
            text="Mapa de Bodega / Vista Rack",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(frame_top, text="Bodega:").pack(side="left", padx=(5, 5))

        self.combo_bodega = ctk.CTkComboBox(
            frame_top,
            values=[],
            width=180,
            state="readonly",
            command=self.al_cambiar_bodega
        )
        self.combo_bodega.pack(side="left", padx=5)

        ctk.CTkLabel(frame_top, text="Rack:").pack(side="left", padx=(15, 5))

        self.combo_rack = ctk.CTkComboBox(
            frame_top,
            values=[],
            width=160,
            state="readonly",
            command=self.al_cambiar_rack
        )
        self.combo_rack.pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="Actualizar",
            width=100,
            command=self.cargar_mapa_actual
        ).pack(side="left", padx=15)

        self.btn_administrar_racks = ctk.CTkButton(
            frame_top,
            text="Administrar racks",
            width=135,
            fg_color="#24608a",
            hover_color="#17415f",
            command=self.abrir_gestor_racks
        )
        self.btn_administrar_racks.pack(side="left", padx=(0, 10))

        self.label_estado = ctk.CTkLabel(
            frame_top,
            text="",
            text_color="gray"
        )
        self.label_estado.pack(side="left", padx=10)

        # =========================
        # CONTENEDOR PRINCIPAL
        # =========================
        self.frame_principal = ctk.CTkFrame(self)
        self.frame_principal.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

        self.frame_principal.grid_columnconfigure(0, weight=2)
        self.frame_principal.grid_columnconfigure(1, weight=1)
        self.frame_principal.grid_rowconfigure(0, weight=1)

        # Izquierda: rack
        self.frame_rack = ctk.CTkFrame(self.frame_principal, corner_radius=15)
        self.frame_rack.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        self.frame_rack.grid_columnconfigure((0, 1, 2), weight=1)
        self.frame_rack.grid_rowconfigure((0, 1, 2), weight=1)

        # Derecha: detalle
        self.frame_detalle = ctk.CTkFrame(self.frame_principal, corner_radius=15)
        self.frame_detalle.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        self.frame_detalle.grid_columnconfigure(0, weight=1)
        self.frame_detalle.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self.frame_detalle,
            text="Detalle de ubicación",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, pady=(15, 5), padx=10, sticky="ew")

        self.label_detalle = ctk.CTkLabel(
            self.frame_detalle,
            text="Seleccione una ubicación del rack.",
            text_color="gray",
            wraplength=330
        )
        self.label_detalle.grid(row=1, column=0, pady=(0, 10), padx=10, sticky="ew")

        self.frame_tabla_productos = ctk.CTkFrame(self.frame_detalle)
        self.frame_tabla_productos.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        self.frame_tabla_productos.grid_columnconfigure(0, weight=1)
        self.frame_tabla_productos.grid_rowconfigure(0, weight=1)

        columnas = ("Producto/Sububicación", "Stock", "Categoría", "Código")

        self.tabla_productos = ttk.Treeview(
            self.frame_tabla_productos,
            columns=columnas,
            show="headings",
            height=10
        )

        anchos = {
            "Producto/Sububicación": 180,
            "Stock": 60,
            "Categoría": 100,
            "Código": 110
        }

        for col in columnas:
            self.tabla_productos.heading(col, text=col)
            self.tabla_productos.column(col, width=anchos[col], anchor="center")

        self.tabla_productos.grid(row=0, column=0, sticky="nsew")

        self.btn_subdividir = ctk.CTkButton(
            self.frame_detalle,
            text="Crear 4 subdivisiones",
            fg_color="#B8860B",
            hover_color="#8B6508",
            command=self.crear_subdivisiones_seleccionadas,
            state="disabled"
        )
        self.btn_subdividir.grid(row=3, column=0, pady=(5, 15), padx=10, sticky="ew")

    # ============================================================
    # CARGA INICIAL
    # ============================================================
    def cargar_bodegas_inicial(self):
        threading.Thread(
            target=self._cargar_bodegas_inicial_pesado,
            daemon=True
        ).start()

    def _cargar_bodegas_inicial_pesado(self):
        try:
            bodegas = self.db.cargar_bodegas()
            self.after(0, self._actualizar_bodegas_ui, bodegas)
        except Exception as e:
            print(f"Error cargando bodegas iniciales: {e}")

    def _actualizar_bodegas_ui(self, bodegas):
        self.bodegas = bodegas or []
        self.mapa_bodegas = {
            b["nombre"]: b
            for b in self.bodegas
        }

        nombres = list(self.mapa_bodegas.keys())

        self.combo_bodega.configure(values=nombres)

        if nombres:
            self.combo_bodega.set(nombres[0])
            self.cargar_racks_por_bodega()
        else:
            self.label_estado.configure(text="No hay bodegas activas.")

    def al_cambiar_bodega(self, opcion=None):
        self.cargar_racks_por_bodega()

    def cargar_racks_por_bodega(self):
        bodega_nombre = self.combo_bodega.get()
        bodega = self.mapa_bodegas.get(bodega_nombre)

        if not bodega:
            return

        threading.Thread(
            target=self._cargar_racks_pesado,
            args=(bodega["id"],),
            daemon=True
        ).start()

    def _cargar_racks_pesado(self, bodega_id):
        try:
            racks = self.db.cargar_racks(bodega_id)
            self.after(0, self._actualizar_racks_ui, racks)
        except Exception as e:
            print(f"Error cargando racks: {e}")

    def _actualizar_racks_ui(self, racks):
        rack_actual = self.combo_rack.get()
        self.racks = racks or []
        self.mapa_racks = {
            r["codigo_rack"]: r
            for r in self.racks
        }

        codigos = list(self.mapa_racks.keys())

        self.combo_rack.configure(values=codigos)

        if codigos:
            self.combo_rack.set(
                rack_actual if rack_actual in codigos else codigos[0]
            )
            self.cargar_mapa_actual()
        else:
            self.limpiar_rack()
            self.label_estado.configure(text="No hay racks activos.")

    def al_cambiar_rack(self, opcion=None):
        self.cargar_mapa_actual()

    # ============================================================
    # CARGA MAPA OPTIMIZADA
    # ============================================================
    def cargar_mapa_actual(self):
        rack_codigo = self.combo_rack.get()
        rack = self.mapa_racks.get(rack_codigo)

        if not rack:
            return

        self.label_estado.configure(text="Cargando mapa...", text_color="orange")
        self._solicitud_mapa += 1
        solicitud_id = self._solicitud_mapa

        threading.Thread(
            target=self._cargar_mapa_pesado,
            args=(rack["id"], solicitud_id),
            daemon=True
        ).start()

    def _cargar_mapa_pesado(self, rack_id, solicitud_id):
        try:
            datos_mapa = self.db.cargar_mapa_rack_completo(rack_id)
            self.after(
                0,
                self._dibujar_rack,
                datos_mapa,
                rack_id,
                solicitud_id
            )
        except Exception as e:
            print(f"Error cargando mapa: {e}")

    def limpiar_rack(self):
        for widget in self.frame_rack.winfo_children():
            widget.destroy()

    def _dibujar_rack(self, datos_mapa, rack_id, solicitud_id):
        rack_actual = self.mapa_racks.get(self.combo_rack.get())
        if (
            solicitud_id != self._solicitud_mapa
            or not rack_actual
            or rack_actual.get("id") != rack_id
        ):
            return

        self.limpiar_rack()

        self.datos_mapa = datos_mapa or {}
        self.ubicacion_seleccionada = None
        self.btn_subdividir.configure(state="disabled")
        self.label_detalle.configure(
            text="Seleccione una ubicación del rack.",
            text_color="gray"
        )
        self.limpiar_tabla_productos()

        ubicaciones = self.datos_mapa.get("ubicaciones_base", [])
        resumenes = self.datos_mapa.get("resumen_por_ubicacion", {})

        matriz = {}

        for u in ubicaciones:
            nivel = u.get("nivel", "")
            columna = u.get("columna", "")
            matriz[(nivel, columna)] = u

        cantidad_niveles = max(1, int(rack_actual.get("niveles") or 3))
        cantidad_columnas = max(1, int(rack_actual.get("columnas") or 3))

        for indice in range(8):
            self.frame_rack.grid_columnconfigure(
                indice,
                weight=1 if indice < cantidad_columnas else 0
            )
            self.frame_rack.grid_rowconfigure(
                indice,
                weight=1 if indice < cantidad_niveles else 0
            )

        niveles = [
            f"N{i:02d}"
            for i in range(cantidad_niveles, 0, -1)
        ]
        columnas = [
            f"C{i:02d}"
            for i in range(1, cantidad_columnas + 1)
        ]
        alto_boton = max(58, min(120, int(510 / cantidad_niveles)))

        for fila, nivel in enumerate(niveles):
            for col, columna in enumerate(columnas):
                ubicacion = matriz.get((nivel, columna))

                if not ubicacion:
                    boton = ctk.CTkButton(
                        self.frame_rack,
                        text=f"{nivel}-{columna}\nSin crear",
                        height=alto_boton,
                        fg_color="#777777",
                        hover_color="#777777",
                        state="disabled"
                    )
                    boton.grid(row=fila, column=col, padx=10, pady=10, sticky="nsew")
                    continue

                resumen = resumenes.get(
                    ubicacion["id"],
                    {
                        "productos_directos": 0,
                        "productos_sububicaciones": 0,
                        "productos_total": 0,
                        "subdivisiones": 0,
                        "stock_total": 0
                    }
                )

                texto = (
                    f"{ubicacion['nivel']}-{ubicacion['columna']}\n"
                    f"{ubicacion['codigo_ubicacion']}\n"
                )

                if resumen["subdivisiones"] > 0:
                    texto += (
                        f"Subdivisiones: {resumen['subdivisiones']}\n"
                        f"Prod.: {resumen['productos_total']} | Stock: {resumen['stock_total']}"
                    )
                    color = "#B8860B"
                    hover = "#8B6508"

                elif resumen["productos_total"] > 0:
                    texto += (
                        f"Productos: {resumen['productos_total']}\n"
                        f"Stock: {resumen['stock_total']}"
                    )
                    color = "#1f538d"
                    hover = "#163c65"

                else:
                    texto += "Libre"
                    color = "#2E8B57"
                    hover = "#246B45"

                boton = ctk.CTkButton(
                    self.frame_rack,
                    text=texto,
                    height=alto_boton,
                    font=ctk.CTkFont(
                        size=11 if cantidad_columnas > 4 else 12,
                        weight="bold"
                    ),
                    fg_color=color,
                    hover_color=hover,
                    command=lambda u=ubicacion: self.seleccionar_ubicacion(u)
                )
                boton.grid(row=fila, column=col, padx=10, pady=10, sticky="nsew")

        self.label_estado.configure(
            text=f"Rack {self.combo_rack.get()} cargado.",
            text_color="green"
        )

    # ============================================================
    # DETALLE UBICACIÓN
    # ============================================================
    def seleccionar_ubicacion(self, ubicacion):
        self.ubicacion_seleccionada = ubicacion

        self.label_detalle.configure(
            text=(
                f"Ubicación: {ubicacion.get('codigo_ubicacion')}\n"
                f"Tipo: {ubicacion.get('tipo')}\n"
                f"Nivel: {ubicacion.get('nivel')} | Columna: {ubicacion.get('columna')}"
            )
        )

        self.btn_subdividir.configure(state="normal")

        sububicaciones_por_padre = self.datos_mapa.get("sububicaciones_por_padre", {})
        productos_por_ubicacion = self.datos_mapa.get("productos_por_ubicacion", {})

        sububicaciones = sububicaciones_por_padre.get(ubicacion["id"], [])

        if sububicaciones:
            productos_directos = productos_por_ubicacion.get(ubicacion["id"], [])
            self._mostrar_sububicaciones(
                ubicacion,
                sububicaciones,
                productos_por_ubicacion,
                productos_directos
            )
        else:
            productos = productos_por_ubicacion.get(ubicacion["id"], [])
            self._mostrar_productos(productos)

    def limpiar_tabla_productos(self):
        for item in self.tabla_productos.get_children():
            self.tabla_productos.delete(item)

    def _mostrar_productos(self, productos):
        self.limpiar_tabla_productos()

        if not productos:
            self.tabla_productos.insert(
                "",
                "end",
                values=("Sin productos", "-", "-", "-")
            )
            return

        for p in productos:
            self.tabla_productos.insert(
                "",
                "end",
                values=(
                    p.get("nombre", "-"),
                    p.get("stock", 0),
                    p.get("categoria", "-"),
                    p.get("codigo_barras", "-")
                )
            )

    def _mostrar_sububicaciones(
        self,
        ubicacion,
        sububicaciones,
        productos_por_ubicacion,
        productos_directos
    ):
        self.limpiar_tabla_productos()

        for p in productos_directos:
            self.tabla_productos.insert(
                "",
                "end",
                values=(
                    f"Bloque | {p.get('nombre', '-')}",
                    p.get("stock", 0),
                    p.get("categoria", "-"),
                    p.get("codigo_barras", "-")
                )
            )

        for sub in sububicaciones:
            productos = productos_por_ubicacion.get(sub["id"], [])

            if not productos:
                self.tabla_productos.insert(
                    "",
                    "end",
                    values=(sub.get("codigo_ubicacion"), "Libre", "Subdivisión", "-")
                )
            else:
                for p in productos:
                    self.tabla_productos.insert(
                        "",
                        "end",
                        values=(
                            f"{sub.get('subdivision')} | {p.get('nombre', '-')}",
                            p.get("stock", 0),
                            p.get("categoria", "-"),
                            p.get("codigo_barras", "-")
                        )
                    )

    # ============================================================
    # CREAR SUBDIVISIONES
    # ============================================================
    def crear_subdivisiones_seleccionadas(self):
        if not self.ubicacion_seleccionada:
            return messagebox.showwarning("Aviso", "Seleccione una ubicación.")

        ubicacion = self.ubicacion_seleccionada

        if ubicacion.get("tipo") != "Bloque":
            return messagebox.showwarning(
                "Aviso",
                "Solo se pueden subdividir ubicaciones tipo Bloque."
            )

        if messagebox.askyesno(
            "Crear subdivisiones",
            f"¿Desea crear 4 subdivisiones para {ubicacion.get('codigo_ubicacion')}?"
        ):
            exito, msg = self.db.crear_subdivisiones_ubicacion(
                ubicacion["id"],
                cantidad=4
            )

            if exito:
                messagebox.showinfo("Éxito", msg)
                self.cargar_mapa_actual()
            else:
                messagebox.showerror("Error", msg)

    # ============================================================
    # ADMINISTRACIÓN DE RACKS
    # ============================================================
    def abrir_gestor_racks(self):
        bodega = self.mapa_bodegas.get(self.combo_bodega.get())
        if not bodega:
            return messagebox.showwarning(
                "Aviso",
                "Seleccione una bodega antes de administrar racks."
            )

        self.ventana_racks = ctk.CTkToplevel(self)
        self.ventana_racks.title("Administrar racks")
        self.ventana_racks.geometry("1180x650")
        self.ventana_racks.minsize(980, 560)
        self.ventana_racks.transient(self.winfo_toplevel())
        self.ventana_racks.grab_set()

        encabezado = ctk.CTkFrame(
            self.ventana_racks,
            fg_color="transparent"
        )
        encabezado.pack(fill="x", padx=15, pady=(15, 8))

        ctk.CTkLabel(
            encabezado,
            text=f"Racks de {bodega.get('nombre', 'Bodega')}",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left")

        self.label_cantidad_racks = ctk.CTkLabel(
            encabezado,
            text="",
            text_color="gray"
        )
        self.label_cantidad_racks.pack(side="left", padx=15)

        ctk.CTkButton(
            encabezado,
            text="+ Nuevo rack",
            fg_color="green",
            hover_color="darkgreen",
            command=lambda: self.abrir_formulario_rack()
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            encabezado,
            text="Editar",
            command=self.editar_rack_seleccionado
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            encabezado,
            text="Retirar",
            fg_color="#8B0000",
            hover_color="#5C0000",
            command=self.retirar_rack_seleccionado
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            encabezado,
            text="Reactivar",
            fg_color="#B8860B",
            hover_color="#8B6508",
            command=self.reactivar_rack_seleccionado
        ).pack(side="right", padx=5)

        frame_tabla = ctk.CTkFrame(self.ventana_racks)
        frame_tabla.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columnas = (
            "ID", "Código", "Nombre", "Niveles", "Columnas", "Ancho",
            "Alto", "Profundidad", "Capacidad", "Orden", "Estado"
        )
        visibles = columnas[1:]
        self.tabla_racks = ttk.Treeview(
            frame_tabla,
            columns=columnas,
            displaycolumns=visibles,
            show="headings"
        )
        anchos = {
            "Código": 85,
            "Nombre": 150,
            "Niveles": 70,
            "Columnas": 75,
            "Ancho": 80,
            "Alto": 80,
            "Profundidad": 95,
            "Capacidad": 90,
            "Orden": 65,
            "Estado": 85
        }
        for columna in visibles:
            self.tabla_racks.heading(columna, text=columna)
            self.tabla_racks.column(
                columna,
                width=anchos[columna],
                anchor="center"
            )

        scroll_y = ctk.CTkScrollbar(
            frame_tabla,
            command=self.tabla_racks.yview
        )
        self.tabla_racks.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
        self.tabla_racks.pack(side="left", fill="both", expand=True)
        self.tabla_racks.bind(
            "<Double-1>",
            lambda event: self.editar_rack_seleccionado()
        )

        self.cargar_racks_gestor()

    def cargar_racks_gestor(self):
        if not hasattr(self, "tabla_racks"):
            return

        for item in self.tabla_racks.get_children():
            self.tabla_racks.delete(item)

        bodega = self.mapa_bodegas.get(self.combo_bodega.get())
        if not bodega:
            return

        racks = self.db.cargar_racks(
            bodega.get("id"),
            solo_activos=False
        )
        racks.sort(
            key=lambda r: (
                r.get("posicion_orden") is None,
                r.get("posicion_orden") or 0,
                r.get("codigo_rack") or ""
            )
        )

        activos = 0
        for rack in racks:
            if rack.get("estado") == "Activo":
                activos += 1
            self.tabla_racks.insert(
                "",
                "end",
                values=(
                    rack.get("id"),
                    rack.get("codigo_rack", ""),
                    rack.get("nombre", ""),
                    rack.get("niveles", 0),
                    rack.get("columnas", 0),
                    self.formatear_medida(rack.get("ancho_cm")),
                    self.formatear_medida(rack.get("alto_cm")),
                    self.formatear_medida(rack.get("profundidad_cm")),
                    self.formatear_medida(rack.get("capacidad_kg"), " kg"),
                    rack.get("posicion_orden", "") or "",
                    rack.get("estado", "")
                )
            )

        self.racks_gestor = {rack.get("id"): rack for rack in racks}
        self.label_cantidad_racks.configure(
            text=f"{activos} activos / {len(racks)} registrados"
        )

    def formatear_medida(self, valor, sufijo=" cm"):
        if valor is None or valor == "":
            return "-"
        numero = float(valor)
        texto = str(int(numero)) if numero.is_integer() else str(numero)
        return texto + sufijo

    def obtener_rack_gestor_seleccionado(self):
        seleccion = self.tabla_racks.selection()
        if not seleccion:
            messagebox.showwarning(
                "Aviso",
                "Seleccione un rack.",
                parent=self.ventana_racks
            )
            return None
        rack_id = self.tabla_racks.item(seleccion[0])["values"][0]
        return self.racks_gestor.get(rack_id)

    def editar_rack_seleccionado(self):
        rack = self.obtener_rack_gestor_seleccionado()
        if rack:
            self.abrir_formulario_rack(rack)

    def retirar_rack_seleccionado(self):
        rack = self.obtener_rack_gestor_seleccionado()
        if not rack:
            return
        if rack.get("estado") == "Inactivo":
            return messagebox.showinfo(
                "Aviso",
                "El rack ya está retirado.",
                parent=self.ventana_racks
            )
        if not messagebox.askyesno(
            "Retirar rack",
            f"¿Desea retirar {rack.get('codigo_rack')}?\n\n"
            "La operación se bloqueará si existen productos asignados.",
            parent=self.ventana_racks
        ):
            return

        exito, mensaje = self.db.retirar_rack(rack.get("id"))
        if exito:
            self.refrescar_despues_cambio_rack()
        else:
            messagebox.showerror("Error", mensaje, parent=self.ventana_racks)

    def reactivar_rack_seleccionado(self):
        rack = self.obtener_rack_gestor_seleccionado()
        if not rack:
            return
        if rack.get("estado") == "Activo":
            return messagebox.showinfo(
                "Aviso",
                "El rack ya está activo.",
                parent=self.ventana_racks
            )

        exito, mensaje = self.db.reactivar_rack(rack.get("id"))
        if exito:
            self.refrescar_despues_cambio_rack()
        else:
            messagebox.showerror("Error", mensaje, parent=self.ventana_racks)

    def abrir_formulario_rack(self, rack=None):
        editando = rack is not None
        ventana = ctk.CTkToplevel(self.ventana_racks)
        ventana.title("Editar rack" if editando else "Nuevo rack")
        ventana.geometry("620x680")
        ventana.minsize(620, 680)
        ventana.transient(self.ventana_racks)
        ventana.grab_set()

        scroll = ctk.CTkScrollableFrame(ventana)
        scroll.pack(fill="both", expand=True, padx=12, pady=12)
        scroll.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            scroll,
            text="Configuración del rack",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, columnspan=2, pady=(8, 18))

        campos = [
            ("Código", "codigo_rack", "Ej: R07"),
            ("Nombre", "nombre", "Nombre descriptivo"),
            ("Niveles", "niveles", "1 a 8"),
            ("Columnas", "columnas", "1 a 8"),
            ("Ancho (cm)", "ancho_cm", "Ej: 200"),
            ("Alto (cm)", "alto_cm", "Ej: 220"),
            ("Profundidad (cm)", "profundidad_cm", "Ej: 60"),
            ("Capacidad (kg)", "capacidad_kg", "Ej: 1500"),
            ("Orden físico", "posicion_orden", "Ej: 7")
        ]
        entradas = {}

        for indice, (etiqueta, clave, placeholder) in enumerate(campos):
            fila = 1 + (indice // 2) * 2
            columna = indice % 2
            ctk.CTkLabel(
                scroll,
                text=etiqueta,
                font=ctk.CTkFont(weight="bold")
            ).grid(
                row=fila,
                column=columna,
                sticky="w",
                padx=10,
                pady=(4, 0)
            )
            entrada = ctk.CTkEntry(scroll, placeholder_text=placeholder)
            entrada.grid(
                row=fila + 1,
                column=columna,
                sticky="ew",
                padx=10,
                pady=(3, 10)
            )
            valor = rack.get(clave) if rack else ""
            if valor is not None and valor != "":
                entrada.insert(0, str(valor))
            entradas[clave] = entrada

        fila_descripcion = 1 + ((len(campos) + 1) // 2) * 2
        ctk.CTkLabel(
            scroll,
            text="Descripción",
            font=ctk.CTkFont(weight="bold")
        ).grid(
            row=fila_descripcion,
            column=0,
            columnspan=2,
            sticky="w",
            padx=10
        )
        entrada_descripcion = ctk.CTkTextbox(scroll, height=90)
        entrada_descripcion.grid(
            row=fila_descripcion + 1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=10,
            pady=(3, 12)
        )
        if rack and rack.get("descripcion"):
            entrada_descripcion.insert("1.0", rack.get("descripcion"))

        def guardar():
            try:
                codigo = entradas["codigo_rack"].get().strip().upper()
                nombre = entradas["nombre"].get().strip()
                niveles = int(entradas["niveles"].get().strip())
                columnas = int(entradas["columnas"].get().strip())

                if not codigo or not nombre:
                    raise ValueError("Código y nombre son obligatorios.")
                if not 1 <= niveles <= 8 or not 1 <= columnas <= 8:
                    raise ValueError(
                        "Niveles y columnas deben estar entre 1 y 8."
                    )

                datos = {
                    "codigo_rack": codigo,
                    "nombre": nombre,
                    "descripcion": entrada_descripcion.get(
                        "1.0",
                        "end"
                    ).strip(),
                    "niveles": niveles,
                    "columnas": columnas,
                    "ancho_cm": self.leer_decimal_opcional(
                        entradas["ancho_cm"].get(),
                        "ancho"
                    ),
                    "alto_cm": self.leer_decimal_opcional(
                        entradas["alto_cm"].get(),
                        "alto"
                    ),
                    "profundidad_cm": self.leer_decimal_opcional(
                        entradas["profundidad_cm"].get(),
                        "profundidad"
                    ),
                    "capacidad_kg": self.leer_decimal_opcional(
                        entradas["capacidad_kg"].get(),
                        "capacidad"
                    ),
                    "posicion_orden": self.leer_entero_opcional(
                        entradas["posicion_orden"].get(),
                        "orden"
                    )
                }

                if editando:
                    exito, mensaje = self.db.actualizar_rack(
                        rack.get("id"),
                        datos
                    )
                else:
                    bodega = self.mapa_bodegas.get(self.combo_bodega.get())
                    datos["bodega_id"] = bodega.get("id")
                    exito, mensaje = self.db.gestionar_rack(
                        "crear",
                        datos
                    )

                if not exito:
                    return messagebox.showerror(
                        "Error",
                        mensaje,
                        parent=ventana
                    )

                ventana.destroy()
                self.refrescar_despues_cambio_rack()

            except ValueError as e:
                messagebox.showwarning(
                    "Datos inválidos",
                    str(e),
                    parent=ventana
                )

        ctk.CTkButton(
            scroll,
            text="Guardar cambios" if editando else "Crear rack",
            height=42,
            fg_color="green",
            hover_color="darkgreen",
            command=guardar
        ).grid(
            row=fila_descripcion + 2,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=10,
            pady=(4, 12)
        )

    def leer_decimal_opcional(self, texto, nombre):
        texto = str(texto).strip().replace(",", ".")
        if not texto:
            return None
        valor = float(texto)
        if valor <= 0:
            raise ValueError(f"El campo {nombre} debe ser mayor a cero.")
        return valor

    def leer_entero_opcional(self, texto, nombre):
        texto = str(texto).strip()
        if not texto:
            return None
        valor = int(texto)
        if valor < 1:
            raise ValueError(f"El campo {nombre} debe ser mayor a cero.")
        return valor

    def refrescar_despues_cambio_rack(self):
        self.cargar_racks_gestor()
        self.cargar_racks_por_bodega()
        app = self.winfo_toplevel()
        if hasattr(app, "vista_inventario"):
            app.vista_inventario.iniciar_carga_hilo()
