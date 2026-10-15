import customtkinter as ctk
from tkinter import ttk
import threading
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.ui_theme import estilos_barra, estilos_boton, estilos_panel, estilizar_treeview

class HistorialTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        iniciar_despachador_ui(self)
        self.crear_interfaz()
        self.iniciar_carga_hilo()

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Encabezado ---
        self.frame_top = ctk.CTkFrame(self, **estilos_barra())
        self.frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.frame_top.grid_columnconfigure(0, weight=1)

        self.titulo_historial = ctk.CTkLabel(
            self.frame_top,
            text="Últimos 100 Movimientos (Solo Lectura)",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
            justify="left",
        )
        self.titulo_historial.grid(
            row=0, column=0, sticky="ew", padx=12, pady=(10, 4)
        )
        
        self.btn_refrescar = ctk.CTkButton(
            self.frame_top,
            text="Refrescar Historial",
            **estilos_boton("primario"),
            command=self.iniciar_carga_hilo
        )
        self.btn_refrescar.grid(
            row=1, column=0, sticky="e", padx=12, pady=(4, 10)
        )
        self.frame_top.bind("<Configure>", self._ajustar_titulo)

        # --- Tabla ---
        frame_tabla = ctk.CTkFrame(self, **estilos_panel())
        frame_tabla.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        frame_tabla.pack_propagate(False)

        scroll_y = ttk.Scrollbar(frame_tabla)
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(frame_tabla, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")

        columnas = ("Fecha/Hora", "Trabajador", "Producto", "Movimiento", "Cant", "Proyecto")
        self.tabla = ttk.Treeview(frame_tabla, columns=columnas, show="headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        anchos = {"Fecha/Hora": 120, "Trabajador": 180, "Producto": 200, "Movimiento": 180, "Cant": 50, "Proyecto": 150}
        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos[col], anchor="center" if col in ["Cant", "Fecha/Hora"] else "w")

        self.tabla.pack(expand=True, fill="both")
        scroll_y.config(command=self.tabla.yview)
        scroll_x.config(command=self.tabla.xview)
        
        # Colores cebra
        estilizar_treeview(self.tabla)

    def _ajustar_titulo(self, event):
        self.titulo_historial.configure(wraplength=max(220, event.width - 32))

    def iniciar_carga_hilo(self):
        self.btn_refrescar.configure(state="disabled", text="Cargando...")
        for row in self.tabla.get_children(): self.tabla.delete(row)
        threading.Thread(target=self.tarea_carga, daemon=True).start()

    def tarea_carga(self):
        filas = self.db.obtener_historial_reciente()
        ejecutar_en_ui(self, self.actualizar_tabla, filas)

    def actualizar_tabla(self, filas):
        for i, f in enumerate(filas):
            tag = "par" if i % 2 == 0 else "impar"
            self.tabla.insert("", "end", values=f, tags=(tag,))
        self.btn_refrescar.configure(state="normal", text="Refrescar Historial")
