import customtkinter as ctk
from tkinter import ttk
import threading # NUEVO
from utils.fechas import formatear_fecha_hora
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.ui_theme import (
    color_estado,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)

class TerrenoTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        iniciar_despachador_ui(self)
        self.crear_interfaz()

    def crear_interfaz(self):
        self.frame_top = ctk.CTkFrame(self, **estilos_barra())
        self.frame_top.pack(fill="x", pady=10, padx=10)
        self.frame_top.grid_columnconfigure(0, weight=1)

        self.titulo_terreno = ctk.CTkLabel(
            self.frame_top,
            text="Control de Activos Fuera de Bodega",
            font=ctk.CTkFont(size=14, slant="italic"),
            anchor="e",
            justify="right",
        )
        self.titulo_terreno.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(8, 4),
        )

        self.fila_acciones = ctk.CTkFrame(self.frame_top, fg_color="transparent")
        self.fila_acciones.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=12,
            pady=(4, 8),
        )
        self.fila_acciones.grid_columnconfigure(1, weight=1)

        self.boton_refrescar = ctk.CTkButton(
            self.fila_acciones,
            text="Refrescar Préstamos",
            command=self.iniciar_carga_hilo,
            **estilos_boton("primario"),
        )
        self.boton_refrescar.grid(row=0, column=0, sticky="w")

        self.label_estado = ctk.CTkLabel(
            self.fila_acciones,
            text="",
            text_color=color_estado("info"),
            anchor="w",
            justify="left",
        )
        self.label_estado.grid(row=0, column=1, sticky="ew", padx=(12, 0))

        self.frame_top.bind("<Configure>", self._ajustar_textos_encabezado)

        columnas = (
            "Producto",
            "Poseedor",
            "Proyecto",
            "Cantidad",
            "Fecha Salida",
            "Movimiento"
        )
        frame_tabla = ctk.CTkFrame(self, **estilos_panel())
        frame_tabla.pack(fill="both", expand=True, padx=10, pady=10)

        self.tabla_terreno = ttk.Treeview(frame_tabla, columns=columnas, show="headings", height=15)
        
        for col in columnas:
            self.tabla_terreno.heading(col, text=col)
            self.tabla_terreno.column(col, width=200, anchor="center")
            
        self.tabla_terreno.pack(fill="both", expand=True, padx=8, pady=8)
        self.after(3500, self.iniciar_carga_hilo)
        estilizar_treeview(self.tabla_terreno)

    def _ajustar_textos_encabezado(self, event):
        ancho_interior = max(160, event.width - 32)
        self.titulo_terreno.configure(wraplength=ancho_interior)

        ancho_boton = self.boton_refrescar.winfo_reqwidth()
        ancho_estado = max(120, ancho_interior - ancho_boton - 20)
        self.label_estado.configure(wraplength=ancho_estado)

    # NUEVAS FUNCIONES DE HILOS
    def iniciar_carga_hilo(self):
        self.label_estado.configure(
            text="Calculando estado en terreno...",
            text_color=color_estado("cargando")
        )
        for item in self.tabla_terreno.get_children(): self.tabla_terreno.delete(item)
        threading.Thread(target=self.cargar_terreno_pesado, daemon=True).start()

    def cargar_terreno_pesado(self):
        terreno_data = self.db.obtener_herramientas_en_terreno()
        filas = []
        for item in terreno_data:
            fecha_legible = formatear_fecha_hora(
                item.get("fecha_hora"), "%d/%m/%Y %H:%M"
            )
            
            filas.append((
                item.get("nombre_producto", item.get("codigo_producto", "Desconocido")),
                item.get("nombre_trabajador", "Desconocido"),
                item.get("nombre_proyecto", "-"),
                item.get("cantidad_pendiente", 0),
                fecha_legible,
                item["tipo_movimiento"]
            ))
            
        ejecutar_en_ui(self, self.actualizar_interfaz_tabla, filas)

    def actualizar_interfaz_tabla(self, filas):
        for i, f in enumerate(filas):
            tag = "par" if i % 2 == 0 else "impar"
            # AQUÍ ESTABA EL ERROR, CÁMBIALO A tabla_terreno:
            self.tabla_terreno.insert("", "end", values=f, tags=(tag,))
            
        self.label_estado.configure(
            text=f"{len(filas)} activos fuera.",
            text_color=color_estado("ok")
        )
