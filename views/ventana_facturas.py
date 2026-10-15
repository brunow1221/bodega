import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from utils.facturas import AlmacenFacturasNAS, RegistroFacturaDocumental
from utils.searchable_combobox import SearchableCombobox
from utils.ui_theme import (
    PALETA,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)
from utils.ui_windows import VentanaAdaptable


def _formatear_numero(valor, decimales=0):
    try:
        numero = Decimal(str(valor or 0))
    except (InvalidOperation, ValueError):
        return str(valor or "0")
    if decimales == 0 and numero == numero.to_integral_value():
        return f"{int(numero):,}".replace(",", ".")
    texto = f"{numero:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


class VentanaFacturasProducto(VentanaAdaptable):
    def __init__(self, master, db_manager, producto, directorio_nas):
        rol = getattr(master.winfo_toplevel(), "rol_actual", "Consulta")
        self.puede_registrar = (
            rol in ("Administrador", "Admin", "Bodeguero")
            and bool(getattr(db_manager, "session_token", None))
        )
        super().__init__(master, fg_color=PALETA["fondo"])
        self.db = db_manager
        self.producto = producto
        self.directorio_nas = directorio_nas
        self.facturas_por_fila = {}
        self.archivo_seleccionado = ""

        self.title(f"Facturas — {producto.get('nombre', 'Producto')}")
        self.geometry("1040x620")
        self.minsize(820, 500)
        self.grab_set()
        self.crear_interfaz()
        self.cargar_facturas()

    def crear_interfaz(self):
        cabecera = ctk.CTkFrame(self, **estilos_barra())
        cabecera.pack(fill="x", padx=14, pady=(14, 8))

        ctk.CTkLabel(
            cabecera,
            text=f"Facturas de {self.producto.get('nombre', '')}",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=PALETA["primario"],
        ).pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            cabecera,
            text=(
                f"Código: {self.producto.get('codigo_barras') or '-'}  ·  "
                "Archivo histórico: registrar aquí no modifica el stock."
            ),
            text_color=PALETA["texto_suave"],
        ).pack(anchor="w", padx=14, pady=(0, 10))

        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(fill="x", padx=14, pady=4)

        self.btn_agregar = ctk.CTkButton(
            acciones,
            text="+ Agregar factura",
            **estilos_boton("primario"),
            command=self.abrir_formulario_factura,
        )
        self.btn_agregar.pack(side="left", padx=(0, 6))
        if not self.puede_registrar:
            self.btn_agregar.configure(state="disabled")

        ctk.CTkButton(
            acciones,
            text="Abrir archivo",
            **estilos_boton("secundario"),
            command=self.abrir_archivo_seleccionado,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            acciones,
            text="Actualizar",
            **estilos_boton("fantasma"),
            command=self.cargar_facturas,
        ).pack(side="left", padx=6)

        self.label_estado = ctk.CTkLabel(
            acciones,
            text="",
            text_color=PALETA["texto_suave"],
        )
        self.label_estado.pack(side="right", padx=6)

        panel = ctk.CTkFrame(self, **estilos_panel())
        panel.pack(fill="both", expand=True, padx=14, pady=(8, 14))

        columnas = (
            "Fecha",
            "Proveedor",
            "Factura",
            "Cantidad",
            "Precio unitario",
            "Archivo",
            "Registrada por",
        )
        scroll_y = ctk.CTkScrollbar(panel, orientation="vertical")
        scroll_y.pack(side="right", fill="y")
        scroll_x = ctk.CTkScrollbar(panel, orientation="horizontal")
        scroll_x.pack(side="bottom", fill="x")
        self.tabla = ttk.Treeview(
            panel,
            columns=columnas,
            show="headings",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )
        estilizar_treeview(self.tabla)
        scroll_y.configure(command=self.tabla.yview)
        scroll_x.configure(command=self.tabla.xview)

        anchos = {
            "Fecha": 95,
            "Proveedor": 180,
            "Factura": 110,
            "Cantidad": 90,
            "Precio unitario": 120,
            "Archivo": 180,
            "Registrada por": 170,
        }
        for columna in columnas:
            self.tabla.heading(columna, text=columna)
            self.tabla.column(columna, width=anchos[columna], anchor="center")
        self.tabla.pack(side="left", fill="both", expand=True)
        self.tabla.bind("<Double-1>", lambda _evento: self.abrir_archivo_seleccionado())

    def cargar_facturas(self):
        try:
            facturas = self.db.listar_facturas_producto(self.producto.get("id"))
        except Exception as error:
            self.label_estado.configure(text="No se pudieron cargar las facturas.")
            messagebox.showerror(
                "Facturas",
                f"No se pudieron cargar las facturas.\n\n{error}",
                parent=self,
            )
            return

        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        self.facturas_por_fila.clear()

        for indice, factura in enumerate(facturas):
            fila = self.tabla.insert(
                "",
                "end",
                values=(
                    factura.get("fecha_factura") or "-",
                    factura.get("proveedor") or "-",
                    factura.get("numero_factura") or "-",
                    _formatear_numero(factura.get("cantidad"), 3),
                    f"$ {_formatear_numero(factura.get('precio_unitario'), 2)}",
                    factura.get("archivo_original") or "-",
                    factura.get("usuario_app") or "-",
                ),
                tags=(("par",) if indice % 2 == 0 else ("impar",)),
            )
            self.facturas_por_fila[fila] = factura

        self.label_estado.configure(
            text=f"{len(facturas)} factura(s) asociada(s)"
        )

    def _almacen(self):
        return AlmacenFacturasNAS(self.directorio_nas)

    def abrir_archivo_seleccionado(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning(
                "Facturas",
                "Seleccione una factura de la tabla.",
                parent=self,
            )
            return
        factura = self.facturas_por_fila.get(seleccion[0], {})
        try:
            ruta = self._almacen().resolver(factura.get("ruta_archivo"))
            if not ruta.is_file():
                raise FileNotFoundError(
                    "El archivo no existe o la carpeta del NAS no está disponible."
                )
            os.startfile(str(ruta))
        except Exception as error:
            messagebox.showerror(
                "No se pudo abrir la factura",
                str(error),
                parent=self,
            )

    def abrir_formulario_factura(self):
        ventana = VentanaAdaptable(self, fg_color=PALETA["fondo"])
        ventana.title("Agregar factura documental")
        ventana.geometry("680x820")
        ventana.minsize(600, 680)
        ventana.grab_set()

        panel = ctk.CTkScrollableFrame(ventana, **estilos_panel())
        panel.pack(fill="both", expand=True, padx=14, pady=14)
        ctk.CTkLabel(
            panel,
            text="Agregar factura documental",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=PALETA["primario"],
        ).pack(pady=(10, 2))
        ctk.CTkLabel(
            panel,
            text="Esta operación no modifica el stock ni el precio vigente.",
            text_color=PALETA["texto_suave"],
        ).pack(pady=(0, 14))

        campos = {}
        for clave, etiqueta, valor in (
            ("proveedor", "Proveedor", ""),
            ("numero", "Número o folio de factura", ""),
            ("fecha", "Fecha (AAAA-MM-DD)", date.today().isoformat()),
        ):
            ctk.CTkLabel(panel, text=etiqueta).pack(anchor="w", padx=18)
            entrada = ctk.CTkEntry(panel)
            if valor:
                entrada.insert(0, valor)
            entrada.pack(fill="x", padx=18, pady=(2, 9))
            campos[clave] = entrada

        ctk.CTkLabel(
            panel,
            text="Productos incluidos en la factura",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=18, pady=(8, 4))

        productos = self.db.cargar_productos_activos_selector()
        if not any(str(p.get("id")) == str(self.producto.get("id")) for p in productos):
            productos.insert(0, self.producto)

        def etiqueta_producto(producto):
            codigo = producto.get("codigo_barras") or "Sin código"
            return f"{codigo} | {producto.get('nombre', 'Producto')}"

        selector_producto = SearchableCombobox(
            panel,
            label_getter=etiqueta_producto,
            search_getter=lambda producto: (
                f"{producto.get('codigo_barras', '')} {producto.get('nombre', '')} "
                f"{producto.get('categoria', '')}"
            ),
            width=60,
            font=("Segoe UI", 11),
        )
        selector_producto.set_items(productos)
        selector_producto.set(etiqueta_producto(self.producto))
        selector_producto.pack(fill="x", padx=18, pady=(2, 7), ipady=5)

        fila_item = ctk.CTkFrame(panel, fg_color="transparent")
        fila_item.pack(fill="x", padx=18, pady=(0, 6))
        entry_cantidad = ctk.CTkEntry(
            fila_item,
            placeholder_text="Cantidad",
            width=130,
        )
        entry_cantidad.insert(0, "1")
        entry_cantidad.pack(side="left", fill="x", expand=True, padx=(0, 4))
        entry_precio = ctk.CTkEntry(
            fila_item,
            placeholder_text="Precio unitario",
            width=150,
        )
        entry_precio.insert(0, "0")
        entry_precio.pack(side="left", fill="x", expand=True, padx=4)

        items_factura = [{
            "producto": self.producto,
            "cantidad": "1",
            "precio_unitario": "0",
        }]
        tabla_items = ttk.Treeview(
            panel,
            columns=("ID", "Producto", "Cantidad", "Precio"),
            displaycolumns=("Producto", "Cantidad", "Precio"),
            show="headings",
            height=5,
        )
        estilizar_treeview(tabla_items)
        for columna, ancho in {
            "Producto": 310,
            "Cantidad": 90,
            "Precio": 120,
        }.items():
            tabla_items.heading(columna, text=columna)
            tabla_items.column(columna, width=ancho, anchor="center")

        def actualizar_tabla_items():
            for fila in tabla_items.get_children():
                tabla_items.delete(fila)
            for indice, item in enumerate(items_factura):
                producto = item["producto"]
                tabla_items.insert(
                    "",
                    "end",
                    iid=str(producto.get("id")),
                    values=(
                        producto.get("id"),
                        producto.get("nombre", "Producto"),
                        item["cantidad"],
                        f"$ {_formatear_numero(item['precio_unitario'], 2)}",
                    ),
                    tags=("par" if indice % 2 == 0 else "impar",),
                )

        def agregar_o_actualizar_item():
            producto = selector_producto.get_selected()
            if not producto:
                messagebox.showwarning(
                    "Factura",
                    "Seleccione un producto de la lista.",
                    parent=ventana,
                )
                return False
            cantidad = entry_cantidad.get().strip().replace(",", ".")
            precio = entry_precio.get().strip().replace(",", ".")
            try:
                if Decimal(cantidad) <= 0 or Decimal(precio) < 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                messagebox.showwarning(
                    "Factura",
                    "La cantidad debe ser mayor que cero y el precio no puede ser negativo.",
                    parent=ventana,
                )
                return False

            nuevo = {
                "producto": producto,
                "cantidad": cantidad,
                "precio_unitario": precio,
            }
            for indice, item in enumerate(items_factura):
                if str(item["producto"].get("id")) == str(producto.get("id")):
                    items_factura[indice] = nuevo
                    break
            else:
                items_factura.append(nuevo)
            actualizar_tabla_items()
            return True

        def quitar_item():
            seleccion = tabla_items.selection()
            if not seleccion:
                return
            producto_id = seleccion[0]
            items_factura[:] = [
                item for item in items_factura
                if str(item["producto"].get("id")) != producto_id
            ]
            actualizar_tabla_items()

        ctk.CTkButton(
            fila_item,
            text="Agregar / actualizar",
            **estilos_boton("secundario"),
            command=agregar_o_actualizar_item,
        ).pack(side="left", padx=(4, 0))
        tabla_items.pack(fill="x", padx=18, pady=(2, 5))
        actualizar_tabla_items()
        ctk.CTkButton(
            panel,
            text="Quitar producto seleccionado",
            height=30,
            **estilos_boton("fantasma"),
            command=quitar_item,
        ).pack(anchor="e", padx=18, pady=(0, 8))

        ctk.CTkLabel(panel, text="Observación (opcional)").pack(anchor="w", padx=18)
        observacion = ctk.CTkTextbox(panel, height=85)
        observacion.pack(fill="x", padx=18, pady=(2, 9))

        self.archivo_seleccionado = ""
        etiqueta_archivo = ctk.CTkLabel(
            panel,
            text="Ningún archivo seleccionado",
            text_color=PALETA["texto_suave"],
            wraplength=480,
        )
        etiqueta_archivo.pack(fill="x", padx=18, pady=(4, 4))

        def seleccionar_archivo():
            ruta = filedialog.askopenfilename(
                parent=ventana,
                title="Seleccionar factura",
                filetypes=[
                    ("Facturas", "*.pdf *.jpg *.jpeg *.png"),
                    ("PDF", "*.pdf"),
                    ("Imágenes", "*.jpg *.jpeg *.png"),
                ],
            )
            if ruta:
                self.archivo_seleccionado = ruta
                etiqueta_archivo.configure(text=Path(ruta).name)

        ctk.CTkButton(
            panel,
            text="Seleccionar PDF o imagen",
            **estilos_boton("secundario"),
            command=seleccionar_archivo,
        ).pack(fill="x", padx=18, pady=5)

        def guardar():
            if not agregar_o_actualizar_item():
                return
            try:
                almacen = self._almacen()
                registro = RegistroFacturaDocumental(self.db, almacen)
                exito, mensaje, _datos = registro.registrar(
                    archivo_origen=self.archivo_seleccionado,
                    proveedor=campos["proveedor"].get(),
                    numero_factura=campos["numero"].get(),
                    fecha_factura=campos["fecha"].get(),
                    observacion=observacion.get("1.0", "end").strip(),
                    items=items_factura,
                )
            except Exception as error:
                messagebox.showerror("Factura", str(error), parent=ventana)
                return

            if not exito:
                messagebox.showerror("Factura", mensaje, parent=ventana)
                return
            messagebox.showinfo(
                "Factura",
                "Factura guardada correctamente. El stock no fue modificado.",
                parent=ventana,
            )
            ventana.destroy()
            self.cargar_facturas()

        ctk.CTkButton(
            panel,
            text="Guardar factura",
            height=42,
            **estilos_boton("primario"),
            command=guardar,
        ).pack(fill="x", padx=18, pady=(12, 16))

