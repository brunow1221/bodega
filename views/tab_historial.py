import customtkinter as ctk
from tkinter import ttk
import threading

class HistorialTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.crear_interfaz()
        self.iniciar_carga_hilo()

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Encabezado ---
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(frame_top, text="Últimos 100 Movimientos (Solo Lectura)", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        
        self.btn_refrescar = ctk.CTkButton(frame_top, text="Refrescar Historial", command=self.iniciar_carga_hilo)
        self.btn_refrescar.pack(side="right")

        # --- Tabla ---
        frame_tabla = ctk.CTkFrame(self)
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
        self.tabla.tag_configure("par", background="#F5F5F5")
        self.tabla.tag_configure("impar", background="#FFFFFF")

    def iniciar_carga_hilo(self):
        self.btn_refrescar.configure(state="disabled", text="Cargando...")
        for row in self.tabla.get_children(): self.tabla.delete(row)
        threading.Thread(target=self.tarea_carga, daemon=True).start()

    def tarea_carga(self):
        filas = self.db.obtener_historial_reciente()
        self.after(0, self.actualizar_tabla, filas)

    def actualizar_tabla(self, filas):
        for i, f in enumerate(filas):
            tag = "par" if i % 2 == 0 else "impar"
            self.tabla.insert("", "end", values=f, tags=(tag,))
        self.btn_refrescar.configure(state="normal", text="Refrescar Historial")