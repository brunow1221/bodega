# views/forms.py
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from uuid import uuid4

class FormularioProducto(ctk.CTkToplevel):
    def __init__(self, master, db_manager, barcode_gen, callback_actualizar):
        super().__init__(master)
        self.title("Nuevo Producto")
        self.geometry("450x600")
        self.db = db_manager
        self.barcode = barcode_gen
        self.callback = callback_actualizar
        self.grab_set()
        
        self.crear_widgets()

    def crear_widgets(self):
        ctk.CTkLabel(self, text="Registro de Producto", font=("Arial", 20, "bold")).pack(pady=20)
        self.entry_nombre = ctk.CTkEntry(self, placeholder_text="Nombre", width=300)
        self.entry_nombre.pack(pady=10)
        self.combo_categoria = ctk.CTkComboBox(
            self,
            values=["Herramientas", "Insumos", "EPP", "Equipos", "Materiales", "Otros"],
            state="readonly",
            width=300
        )
        self.combo_categoria.set("Herramientas")
        self.combo_categoria.pack(pady=10)
        self.entry_stock = ctk.CTkEntry(self, placeholder_text="Stock inicial", width=300)
        self.entry_stock.pack(pady=10)
        self.entry_precio = ctk.CTkEntry(self, placeholder_text="Precio unitario", width=300)
        self.entry_precio.pack(pady=10)
        ctk.CTkButton(self, text="Guardar", fg_color="green", command=self.guardar).pack(pady=20)

    def guardar(self):
        nombre = self.entry_nombre.get().strip()
        if not nombre:
            return messagebox.showwarning(
                "Aviso",
                "El nombre es obligatorio.",
                parent=self
            )

        try:
            stock = int(self.entry_stock.get().strip() or 0)
            precio = int(self.entry_precio.get().strip() or 0)
            if stock < 0 or precio < 0:
                raise ValueError
        except ValueError:
            return messagebox.showwarning(
                "Aviso",
                "Stock y precio deben ser enteros mayores o iguales a 0.",
                parent=self
            )

        codigo = (
            f"PRD{datetime.now().strftime('%y%m%d')}"
            f"{uuid4().hex[:10].upper()}"
        )
        exito, mensaje = self.db.guardar_producto_nube(
            codigo,
            "",
            nombre,
            self.combo_categoria.get(),
            "",
            "",
            "",
            stock,
            precio
        )
        if not exito:
            return messagebox.showerror("Error", mensaje, parent=self)

        self.barcode.generar_codigo_barras(codigo, nombre)
        self.callback()
        self.destroy()
