import customtkinter as ctk
from tkinter import ttk
from datetime import datetime
import threading # NUEVO

class TerrenoTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.crear_interfaz()

    def crear_interfaz(self):
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.pack(fill="x", pady=10, padx=10)

        ctk.CTkButton(frame_top, text="Refrescar Préstamos", command=self.iniciar_carga_hilo).pack(side="left")
        
        self.label_estado = ctk.CTkLabel(frame_top, text="", text_color="blue")
        self.label_estado.pack(side="left", padx=10)

        ctk.CTkLabel(frame_top, text="Control de Activos Fuera de Bodega", font=ctk.CTkFont(size=14, slant="italic")).pack(side="right", padx=10)

        columnas = (
            "Producto",
            "Poseedor",
            "Proyecto",
            "Cantidad",
            "Fecha Salida",
            "Movimiento"
        )
        self.tabla_terreno = ttk.Treeview(self, columns=columnas, show="headings", height=15)
        
        for col in columnas:
            self.tabla_terreno.heading(col, text=col)
            self.tabla_terreno.column(col, width=200, anchor="center")
            
        self.tabla_terreno.pack(fill="both", expand=True, padx=10, pady=10)
        self.after(3500, self.iniciar_carga_hilo)
        self.tabla_terreno.tag_configure("par", background="#F5F5F5") 
        self.tabla_terreno.tag_configure("impar", background="#FFFFFF")

    # NUEVAS FUNCIONES DE HILOS
    def iniciar_carga_hilo(self):
        self.label_estado.configure(text="Calculando estado en terreno...", text_color="orange")
        for item in self.tabla_terreno.get_children(): self.tabla_terreno.delete(item)
        threading.Thread(target=self.cargar_terreno_pesado, daemon=True).start()

    def cargar_terreno_pesado(self):
        terreno_data = self.db.obtener_herramientas_en_terreno()
        filas = []
        for item in terreno_data:
            try:
                fecha_dt = datetime.fromisoformat(item['fecha_hora'])
                fecha_legible = fecha_dt.strftime("%d/%m/%Y %H:%M")
            except:
                fecha_legible = item['fecha_hora']
            
            filas.append((
                item.get("nombre_producto", item.get("codigo_producto", "Desconocido")),
                item.get("nombre_trabajador", "Desconocido"),
                item.get("nombre_proyecto", "-"),
                item.get("cantidad_pendiente", 0),
                fecha_legible,
                item["tipo_movimiento"]
            ))
            
        self.after(0, self.actualizar_interfaz_tabla, filas)

    def actualizar_interfaz_tabla(self, filas):
        for i, f in enumerate(filas):
            tag = "par" if i % 2 == 0 else "impar"
            # AQUÍ ESTABA EL ERROR, CÁMBIALO A tabla_terreno:
            self.tabla_terreno.insert("", "end", values=f, tags=(tag,))
            
        self.label_estado.configure(text=f"{len(filas)} activos fuera.", text_color="green")
