import customtkinter as ctk
from utils.ui_windows import VentanaAdaptable
from tkinter import ttk, messagebox
import threading
import re
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.ui_theme import (
    PALETA,
    color_estado,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)


class MapaBodegaTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")

        self.db = db_manager
        iniciar_despachador_ui(self)

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
        frame_top = ctk.CTkFrame(self, **estilos_barra())
        frame_top.grid(row=0, column=0, sticky="ew", padx=15, pady=10)

        fila_titulo = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_titulo.pack(fill="x", padx=12, pady=(10, 4))

        fila_selectores = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_selectores.pack(fill="x", padx=12, pady=4)
        fila_selectores.grid_columnconfigure((0, 1), weight=1)

        fila_acciones = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_acciones.pack(fill="x", padx=12, pady=(4, 10))
        fila_acciones.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            fila_titulo,
            text="Mapa de Bodega / Sectores y Estantes",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETA["primario"]
        ).pack(side="left", padx=(0, 20))

        campo_bodega = ctk.CTkFrame(fila_selectores, fg_color="transparent")
        campo_bodega.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(campo_bodega, text="Bodega:").pack(anchor="w")

        self.combo_bodega = ctk.CTkComboBox(
            campo_bodega,
            values=[],
            state="readonly",
            command=self.al_cambiar_bodega
        )
        self.combo_bodega.pack(fill="x")

        campo_sector = ctk.CTkFrame(fila_selectores, fg_color="transparent")
        campo_sector.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(campo_sector, text="Sector:").pack(anchor="w")

        self.combo_rack = ctk.CTkComboBox(
            campo_sector,
            values=[],
            state="readonly",
            command=self.al_cambiar_rack
        )
        self.combo_rack.pack(fill="x")

        ctk.CTkButton(
            fila_acciones,
            text="Actualizar",
            **estilos_boton("primario"),
            command=self.cargar_mapa_actual
        ).grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.btn_administrar_racks = ctk.CTkButton(
            fila_acciones,
            text="Administrar sectores",
            **estilos_boton("fantasma"),
            command=self.abrir_gestor_racks
        )
        self.btn_administrar_racks.grid(
            row=0, column=1, sticky="w", padx=(6, 10)
        )

        self.label_estado = ctk.CTkLabel(
            fila_acciones,
            text="",
            text_color=color_estado("suave"),
            anchor="e",
            justify="right",
        )
        self.label_estado.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        # =========================
        # CONTENEDOR PRINCIPAL
        # =========================
        self.frame_principal = ctk.CTkFrame(self, **estilos_panel())
        self.frame_principal.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

        self.frame_principal.grid_columnconfigure(0, weight=2)
        self.frame_principal.grid_columnconfigure(1, weight=1)
        self.frame_principal.grid_rowconfigure(0, weight=1)

        # Izquierda: módulos y estantes del sector
        self.frame_rack = ctk.CTkFrame(self.frame_principal, **estilos_panel())
        self.frame_rack.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        self.frame_rack.grid_columnconfigure((0, 1, 2), weight=1)
        self.frame_rack.grid_rowconfigure((0, 1, 2), weight=1)

        # Derecha: detalle
        self.frame_detalle = ctk.CTkFrame(self.frame_principal, **estilos_panel())
        self.frame_detalle.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        self.frame_detalle.grid_columnconfigure(0, weight=1)
        self.frame_detalle.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self.frame_detalle,
            text="Detalle del estante",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETA["primario"]
        ).grid(row=0, column=0, pady=(15, 5), padx=10, sticky="ew")

        self.label_detalle = ctk.CTkLabel(
            self.frame_detalle,
            text="Seleccione un estante del sector.",
            text_color=color_estado("suave"),
            wraplength=330
        )
        self.label_detalle.grid(row=1, column=0, pady=(0, 10), padx=10, sticky="ew")

        self.frame_tabla_productos = ctk.CTkFrame(self.frame_detalle, **estilos_panel())
        self.frame_tabla_productos.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        self.frame_tabla_productos.grid_columnconfigure(0, weight=1)
        self.frame_tabla_productos.grid_rowconfigure(0, weight=1)

        columnas = ("Producto", "Stock", "Categoría", "Código")

        self.tabla_productos = ttk.Treeview(
            self.frame_tabla_productos,
            columns=columnas,
            show="headings",
            height=10
        )
        estilizar_treeview(self.tabla_productos)

        anchos = {
            "Producto": 180,
            "Stock": 60,
            "Categoría": 100,
            "Código": 110
        }

        for col in columnas:
            self.tabla_productos.heading(col, text=col)
            self.tabla_productos.column(col, width=anchos[col], anchor="center")

        self.tabla_productos.grid(row=0, column=0, sticky="nsew")

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
            ejecutar_en_ui(self, self._actualizar_bodegas_ui, bodegas)
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
            self.combo_bodega.set(
                self.nombre_bodega_predeterminada(self.bodegas)
            )
            self.cargar_racks_por_bodega()
        else:
            self.label_estado.configure(text="No hay bodegas activas.")

    @staticmethod
    def nombre_bodega_predeterminada(bodegas):
        if not bodegas:
            return ""

        for bodega in bodegas:
            if str(bodega.get("codigo_bodega") or "").strip().upper() == "B1":
                return bodega.get("nombre", "")

        for bodega in bodegas:
            if str(bodega.get("nombre") or "").strip().casefold() != (
                "afuera de bodega"
            ):
                return bodega.get("nombre", "")

        return bodegas[0].get("nombre", "")

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
            ejecutar_en_ui(self, self._actualizar_racks_ui, racks)
        except Exception as e:
            print(f"Error cargando sectores: {e}")

    def _actualizar_racks_ui(self, racks):
        rack_actual = self.combo_rack.get()
        self.racks = list(racks or [])
        self.mapa_racks = self.construir_mapa_etiquetas(self.racks)

        codigos = list(self.mapa_racks.keys())

        self.combo_rack.configure(values=codigos)

        if codigos:
            self.combo_rack.set(
                rack_actual if rack_actual in codigos else codigos[0]
            )
            self.cargar_mapa_actual()
        else:
            self.limpiar_rack()
            self.label_estado.configure(text="No hay sectores activos.")

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

        self.label_estado.configure(
            text="Cargando mapa...",
            text_color=color_estado("cargando")
        )
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
            ejecutar_en_ui(
                self,
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

    @staticmethod
    def numero_estante(valor):
        digitos = "".join(c for c in str(valor or "") if c.isdigit())
        return int(digitos or 0)

    @staticmethod
    def calcular_numero_estante(modulo, nivel_local, estantes_por_modulo):
        return (modulo - 1) * estantes_por_modulo + nivel_local

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
        self.label_detalle.configure(
            text="Seleccione un estante del sector.",
            text_color=color_estado("suave")
        )
        self.limpiar_tabla_productos()

        ubicaciones = self.datos_mapa.get("ubicaciones_base", [])
        resumenes = self.datos_mapa.get("resumen_por_ubicacion", {})

        ubicaciones_por_numero = {
            self.numero_estante(u.get("nivel")): u
            for u in ubicaciones
            if self.numero_estante(u.get("nivel")) > 0
        }

        estantes_por_modulo = max(1, int(rack_actual.get("niveles") or 5))
        cantidad_modulos = max(1, int(rack_actual.get("columnas") or 2))

        for indice in range(max(20, cantidad_modulos)):
            self.frame_rack.grid_columnconfigure(
                indice,
                weight=1 if indice < cantidad_modulos else 0
            )
        for indice in range(max(12, estantes_por_modulo + 1)):
            self.frame_rack.grid_rowconfigure(
                indice,
                weight=1 if 1 <= indice <= estantes_por_modulo else 0
            )

        alto_boton = max(54, min(105, int(470 / estantes_por_modulo)))
        productos_por_ubicacion = self.datos_mapa.get(
            "productos_por_ubicacion",
            {}
        )
        subs_por_padre = self.datos_mapa.get(
            "sububicaciones_por_padre",
            {}
        )

        # El módulo 1 es el de más a la derecha. Se dibuja el último módulo
        # a la izquierda para respetar el recorrido físico derecha → izquierda.
        for columna_ui, modulo in enumerate(
            range(cantidad_modulos, 0, -1)
        ):
            titulo = f"Módulo {modulo}"
            if modulo == 1:
                titulo += " · derecha"
            ctk.CTkLabel(
                self.frame_rack,
                text=titulo,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=PALETA["primario"]
            ).grid(row=0, column=columna_ui, padx=7, pady=(8, 3))

            for fila_ui, nivel_local in enumerate(
                range(estantes_por_modulo, 0, -1),
                start=1
            ):
                numero = self.calcular_numero_estante(
                    modulo,
                    nivel_local,
                    estantes_por_modulo
                )
                ubicacion = ubicaciones_por_numero.get(numero)

                if not ubicacion:
                    boton = ctk.CTkButton(
                        self.frame_rack,
                        text=f"Estante {numero}\nSin crear",
                        height=alto_boton,
                        fg_color=PALETA["borde"],
                        hover_color=PALETA["borde"],
                        text_color=PALETA["texto_suave"],
                        state="disabled"
                    )
                    boton.grid(
                        row=fila_ui,
                        column=columna_ui,
                        padx=7,
                        pady=5,
                        sticky="nsew"
                    )
                    continue

                resumen = resumenes.get(
                    ubicacion["id"],
                    {"productos_total": 0, "stock_total": 0}
                )
                productos_estante = list(
                    productos_por_ubicacion.get(ubicacion["id"], [])
                )
                for sub in subs_por_padre.get(ubicacion["id"], []):
                    productos_estante.extend(
                        productos_por_ubicacion.get(sub["id"], [])
                    )

                if resumen.get("productos_total", 0) > 0:
                    nombres = " · ".join(
                        p.get("nombre", "-")
                        for p in productos_estante[:3]
                    )
                    if len(productos_estante) > 3:
                        nombres += f" · +{len(productos_estante) - 3}"
                    texto = (
                        f"Estante {numero}\n{nombres}\n"
                        f"Stock: {resumen.get('stock_total', 0)}"
                    )
                    color = PALETA["primario"]
                    hover = PALETA["primario_hover"]
                else:
                    texto = f"Estante {numero}\nLibre"
                    color = PALETA["exito"]
                    hover = PALETA["exito_hover"]

                boton = ctk.CTkButton(
                    self.frame_rack,
                    text=texto,
                    height=alto_boton,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=color,
                    hover_color=hover,
                    command=lambda u=ubicacion: self.seleccionar_ubicacion(u)
                )
                boton.grid(
                    row=fila_ui,
                    column=columna_ui,
                    padx=7,
                    pady=5,
                    sticky="nsew"
                )

        self.label_estado.configure(
            text=f"{self.combo_rack.get()} cargado.",
            text_color=color_estado("ok")
        )

    # ============================================================
    # DETALLE UBICACIÓN
    # ============================================================
    def seleccionar_ubicacion(self, ubicacion):
        self.ubicacion_seleccionada = ubicacion

        self.label_detalle.configure(
            text=(
                f"Sector: {self.combo_rack.get()}\n"
                f"Estante: {self.numero_estante(ubicacion.get('nivel'))}\n"
                f"Código: {ubicacion.get('codigo_ubicacion')}"
            )
        )

        sububicaciones_por_padre = self.datos_mapa.get("sububicaciones_por_padre", {})
        productos_por_ubicacion = self.datos_mapa.get("productos_por_ubicacion", {})

        sububicaciones = sububicaciones_por_padre.get(ubicacion["id"], [])
        productos = list(productos_por_ubicacion.get(ubicacion["id"], []))
        for sub in sububicaciones:
            productos.extend(productos_por_ubicacion.get(sub["id"], []))
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

    # ============================================================
    # ADMINISTRACIÓN DE SECTORES
    # ============================================================
    def abrir_gestor_racks(self):
        bodega = self.mapa_bodegas.get(self.combo_bodega.get())
        if not bodega:
            return messagebox.showwarning(
                "Aviso",
                "Seleccione una bodega antes de administrar sectores."
            )

        self.ventana_racks = VentanaAdaptable(self)
        self.ventana_racks.title("Administrar sectores")
        self.ventana_racks.geometry("1180x650")
        self.ventana_racks.minsize(980, 560)
        self.ventana_racks.transient(self.winfo_toplevel())
        self.ventana_racks.grab_set()
        self.ventana_racks.configure(fg_color=PALETA["fondo"])

        encabezado = ctk.CTkFrame(self.ventana_racks, **estilos_barra())
        encabezado.pack(fill="x", padx=15, pady=(15, 8))

        fila_titulo = ctk.CTkFrame(encabezado, fg_color="transparent")
        fila_titulo.pack(fill="x", padx=12, pady=(10, 4))

        fila_acciones = ctk.CTkFrame(encabezado, fg_color="transparent")
        fila_acciones.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(
            fila_titulo,
            text=f"Sectores de {bodega.get('nombre', 'Bodega')}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETA["primario"]
        ).pack(side="left")

        self.label_cantidad_racks = ctk.CTkLabel(
            fila_titulo,
            text="",
            text_color=color_estado("suave")
        )
        self.label_cantidad_racks.pack(side="left", padx=15)

        ctk.CTkButton(
            fila_acciones,
            text="+ Nuevo sector",
            **estilos_boton("primario"),
            command=lambda: self.abrir_formulario_rack()
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            fila_acciones,
            text="Editar sector",
            **estilos_boton("primario"),
            command=self.editar_rack_seleccionado
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            fila_acciones,
            text="Retirar sector",
            **estilos_boton("peligro"),
            command=self.retirar_rack_seleccionado
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            fila_acciones,
            text="Reactivar sector",
            **estilos_boton("exito"),
            command=self.reactivar_rack_seleccionado
        ).pack(side="left", padx=5)

        frame_tabla = ctk.CTkFrame(self.ventana_racks, **estilos_panel())
        frame_tabla.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columnas = (
            "ID", "Sector", "Nombre", "Módulos", "Estantes/Módulo",
            "Total Estantes", "Ancho", "Alto", "Profundidad",
            "Capacidad", "Estado"
        )
        visibles = columnas[1:]
        self.tabla_racks = ttk.Treeview(
            frame_tabla,
            columns=columnas,
            displaycolumns=visibles,
            show="headings"
        )
        estilizar_treeview(self.tabla_racks)
        anchos = {
            "Sector": 75,
            "Nombre": 150,
            "Módulos": 75,
            "Estantes/Módulo": 120,
            "Total Estantes": 105,
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
                    rack.get("columnas", 0),
                    rack.get("niveles", 0),
                    int(rack.get("columnas") or 0)
                    * int(rack.get("niveles") or 0),
                    self.formatear_medida(rack.get("ancho_cm")),
                    self.formatear_medida(rack.get("alto_cm")),
                    self.formatear_medida(rack.get("profundidad_cm")),
                    self.formatear_medida(rack.get("capacidad_kg"), " kg"),
                    rack.get("estado", "")
                )
            )

        self.racks_gestor = {rack.get("id"): rack for rack in racks}
        self.label_cantidad_racks.configure(
            text=f"{activos} activos / {len(racks)} sectores"
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
                "Seleccione un sector.",
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
                "El sector ya está retirado.",
                parent=self.ventana_racks
            )
        if not messagebox.askyesno(
            "Retirar sector",
            f"¿Desea retirar el sector {rack.get('codigo_rack')}?\n\n"
            "La operación se bloqueará si existen productos asignados.",
            parent=self.ventana_racks
        ):
            return

        exito, mensaje = self.db.retirar_rack(rack.get("id"))
        if exito:
            self.refrescar_despues_cambio_rack()
        else:
            titulo = "Error"
            detalle = mensaje
            if "productos asignados" in mensaje:
                titulo = "Sector con productos asignados"
                detalle = (
                    f"{mensaje}\n\n"
                    "Antes de retirarlo, mueva esos productos a otro sector "
                    "desde Inventario."
                )
            messagebox.showerror(titulo, detalle, parent=self.ventana_racks)

    def reactivar_rack_seleccionado(self):
        rack = self.obtener_rack_gestor_seleccionado()
        if not rack:
            return
        if rack.get("estado") == "Activo":
            return messagebox.showinfo(
                "Aviso",
                "El sector ya está activo.",
                parent=self.ventana_racks
            )

        exito, mensaje = self.db.reactivar_rack(rack.get("id"))
        if exito:
            self.refrescar_despues_cambio_rack()
        else:
            messagebox.showerror("Error", mensaje, parent=self.ventana_racks)

    @staticmethod
    def codigo_rack_desde_numero(numero):
        if numero < 1:
            return ""
        return f"S{numero:02d}"

    @staticmethod
    def etiqueta_sector(rack):
        nombre = str(rack.get("nombre") or "").strip()
        codigo = str(rack.get("codigo_rack") or "").strip()
        return nombre or codigo or "Sector sin nombre"

    @classmethod
    def construir_mapa_etiquetas(cls, racks):
        mapa = {}
        for rack in racks:
            etiqueta_base = cls.etiqueta_sector(rack)
            etiqueta = etiqueta_base
            if etiqueta in mapa:
                codigo = str(rack.get("codigo_rack") or "").strip()
                etiqueta = f"{etiqueta_base} ({codigo})"
            mapa[etiqueta] = rack
        return mapa

    @staticmethod
    def validar_codigo_sector(codigo):
        codigo = str(codigo or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]{1,20}", codigo):
            raise ValueError(
                "El código del sector debe tener entre 1 y 20 caracteres "
                "y usar solo letras, números, guion o guion bajo."
            )
        return codigo

    def siguiente_codigo_rack(self):
        racks = list(getattr(self, "racks_gestor", {}).values())
        if not racks:
            racks = self.racks
        usados = {
            str(r.get("codigo_rack") or "").strip().upper()
            for r in racks
        }
        for numero in range(1, 100):
            codigo = self.codigo_rack_desde_numero(numero)
            if codigo not in usados:
                return codigo
        return "S99"

    def abrir_formulario_rack(self, rack=None):
        editando = rack is not None
        ventana = VentanaAdaptable(self.ventana_racks)
        ventana.title("Editar sector" if editando else "Nuevo sector")
        ventana.geometry("620x680")
        ventana.minsize(620, 680)
        ventana.transient(self.ventana_racks)
        ventana.grab_set()
        ventana.configure(fg_color=PALETA["fondo"])

        scroll = ctk.CTkScrollableFrame(ventana, **estilos_panel())
        scroll.pack(fill="both", expand=True, padx=12, pady=12)
        scroll.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            scroll,
            text="Configuración del sector",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETA["primario"]
        ).grid(row=0, column=0, columnspan=2, pady=(8, 18))

        codigo_sugerido = self.siguiente_codigo_rack()
        campos = [
            ("Código interno", "codigo_rack", "Ej: APORTES"),
            ("Nombre", "nombre", "Ej: Aportes"),
            ("Módulos físicos", "columnas", "Ej: 2"),
            ("Estantes por módulo", "niveles", "Ej: 5"),
            ("Ancho (cm)", "ancho_cm", "Ej: 200"),
            ("Alto (cm)", "alto_cm", "Ej: 220"),
            ("Profundidad (cm)", "profundidad_cm", "Ej: 60"),
            ("Capacidad (kg)", "capacidad_kg", "Ej: 1500")
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
            if not rack and clave == "codigo_rack":
                valor = codigo_sugerido
            elif not rack and clave == "nombre":
                valor = f"Sector {codigo_sugerido}"
            elif not rack and clave == "columnas":
                valor = 2
            elif not rack and clave == "niveles":
                valor = 5
            if valor is not None and valor != "":
                entrada.insert(0, str(valor))
            if editando and clave == "codigo_rack":
                entrada.configure(state="disabled")
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
                codigo = self.validar_codigo_sector(
                    entradas["codigo_rack"].get()
                )
                nombre = entradas["nombre"].get().strip()
                niveles = int(entradas["niveles"].get().strip())
                modulos = int(entradas["columnas"].get().strip())

                if not codigo or not nombre:
                    raise ValueError("Código y nombre son obligatorios.")
                if not 1 <= niveles <= 10:
                    raise ValueError(
                        "Los estantes por módulo deben estar entre 1 y 10."
                    )
                if not 1 <= modulos <= 20:
                    raise ValueError("Los módulos deben estar entre 1 y 20.")

                datos = {
                    "codigo_rack": codigo,
                    "nombre": nombre,
                    "descripcion": entrada_descripcion.get(
                        "1.0",
                        "end"
                    ).strip(),
                    "niveles": niveles,
                    "columnas": modulos,
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
                    "posicion_orden": (
                        rack.get("posicion_orden")
                        if editando else
                        len(getattr(self, "racks_gestor", {})) + 1
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
            text="Guardar cambios" if editando else "Crear sector",
            height=42,
            **estilos_boton("primario"),
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
        for nombre_vista in (
            "vista_inventario",
            "vista_cafeteria",
            "vista_aseo",
            "vista_libreria"
        ):
            vista = getattr(app, nombre_vista, None)
            if vista is not None:
                vista.iniciar_carga_hilo()
