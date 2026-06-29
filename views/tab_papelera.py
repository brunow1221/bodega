import customtkinter as ctk
from tkinter import ttk

class PapeleraTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.crear_interfaz()

    def crear_interfaz(self):
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.pack(fill="x", pady=10, padx=10)

        ctk.CTkButton(frame_top, text="Refrescar Papelera", command=self.cargar_papelera).pack(side="left")

        frame_tabla = ctk.CTkFrame(self)
        frame_tabla.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar_pap = ctk.CTkScrollbar(frame_tabla, orientation="vertical")
        scrollbar_pap.pack(side="right", fill="y")

        columnas = ("ID", "Código", "OT", "Nombre", "Categoría", "Marca/Subcategoría", "Stock", "Bodega")
        columnas_visibles = ("Código", "OT", "Nombre", "Categoría", "Marca/Subcategoría", "Stock", "Bodega")
        
        self.tabla_papelera = ttk.Treeview(frame_tabla, columns=columnas, displaycolumns=columnas_visibles, show="headings", height=15, yscrollcommand=scrollbar_pap.set)
        scrollbar_pap.configure(command=self.tabla_papelera.yview)
        
        anchos = {"Código": 110, "OT": 70, "Nombre": 180, "Categoría": 110, "Marca/Subcategoría": 120, "Stock": 60, "Bodega": 100}
        
        for col in columnas_visibles:
            self.tabla_papelera.heading(col, text=col)
            self.tabla_papelera.column(col, width=anchos[col], anchor="center")
            
        self.tabla_papelera.pack(side="left", fill="both", expand=True)
        self.cargar_papelera()

    def cargar_papelera(self):
        for item in self.tabla_papelera.get_children(): self.tabla_papelera.delete(item)
        for p in self.db.cargar_papelera_nube(): 
            fila = (p.get('id', ''), p.get('codigo_barras', ''), p.get('ot', '') or '-', p.get('nombre', ''), p.get('categoria', ''), p.get('subcategoria', '') or '-', p.get('stock', 0), p.get('bodega', 'Bodega 1'))
            self.tabla_papelera.insert("", "end", values=fila)