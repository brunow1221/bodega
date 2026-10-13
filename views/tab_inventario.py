import customtkinter as ctk
from utils.ui_windows import VentanaAdaptable, adaptar_campos_en_fila
from tkinter import filedialog, ttk, messagebox
from datetime import datetime
from uuid import uuid4
import json
import unicodedata
from utils import obtener_ruta_icono
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.importador_precios import (
    leer_precios_referenciales,
    preparar_actualizaciones_precios,
)
import threading
from utils.ui_theme import (
    PALETA,
    color_estado,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)


def normalizar_clasificacion(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(
        caracter for caracter in texto
        if not unicodedata.combining(caracter)
    ).strip().casefold()


def es_producto_cafeteria(producto):
    categoria = normalizar_clasificacion(producto.get("categoria"))
    palabras_cafeteria = (
        "cafeteria", "comida", "alimento", "alimentacion"
    )

    if categoria == "cafeteria/aseo":
        return True

    return any(palabra in categoria for palabra in palabras_cafeteria)


def es_producto_aseo(producto):
    categoria = normalizar_clasificacion(producto.get("categoria"))
    palabras = ("aseo", "limpieza", "higiene")

    if categoria == "cafeteria/aseo":
        return False

    return any(palabra in categoria for palabra in palabras)


def es_producto_libreria(producto):
    categoria = normalizar_clasificacion(producto.get("categoria"))
    clasificaciones = (
        "libreria",
        "papeleria",
        "utiles de oficina",
        "utiles escolares",
        "articulos de oficina",
        "insumos de oficina",
    )

    return any(
        clasificacion in categoria
        for clasificacion in clasificaciones
    )


class InventarioTab(ctk.CTkFrame):
    CATEGORIAS = [
        "Herramientas",
        "Insumos",
        "Cafetería",
        "Aseo",
        "Librería",
        "EPP",
        "Equipos",
        "Materiales",
        "Otros"
    ]

    def __init__(
        self,
        master,
        db_manager,
        solo_cafeteria=False,
        solo_aseo=False,
        solo_libreria=False
    ):
        super().__init__(master, fg_color="transparent")

        if sum(bool(valor) for valor in (
            solo_cafeteria,
            solo_aseo,
            solo_libreria
        )) > 1:
            raise ValueError(
                "Un inventario especializado no puede ser de dos tipos."
            )

        self.db = db_manager
        self.solo_cafeteria = solo_cafeteria
        self.solo_aseo = solo_aseo
        self.solo_libreria = solo_libreria
        iniciar_despachador_ui(self)

        self.racks_cache = []
        self.bodegas_cache = []
        self.ubicaciones_cache = []

        self.bodega_nombre_a_id = {}
        self.bodega_id_a_nombre = {}
        self.racks_por_bodega = {}
        self.rack_etiqueta_a_id_por_bodega = {}
        self.rack_id_a_etiqueta = {}
        self.rack_por_id = {}
        self.ubicacion_por_id = {}
        self.bloques_por_posicion = {}
        self._carga_inventario_id = 0
        self._cargando_inventario = False
        self._recarga_pendiente = False
        self._importando_precios = False

        self.crear_interfaz()

    # ============================================================
    # INTERFAZ PRINCIPAL
    # ============================================================
    def crear_interfaz(self):
        frame_top = ctk.CTkFrame(self, **estilos_barra())
        frame_top.pack(fill="x", pady=10, padx=10)

        fila_filtros = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_filtros.pack(fill="x", padx=12, pady=(10, 4))

        fila_acciones = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_acciones.pack(fill="x", padx=12, pady=(4, 10))

        self.entry_busqueda = ctk.CTkEntry(
            fila_filtros,
            placeholder_text=(
                f"🔍 Buscar insumo de {self.obtener_nombre_inventario().lower()}..."
                if self.obtener_nombre_inventario() else
                "🔍 Buscar nombre, código, categoría o ubicación..."
            ),
            width=280
        )
        self.entry_busqueda.pack(side="left", padx=5)
        self.entry_busqueda.bind("<Return>", lambda e: self.iniciar_carga_hilo())

        ctk.CTkButton(
            fila_filtros,
            text="Buscar",
            width=70,
            **estilos_boton("primario"),
            command=self.iniciar_carga_hilo
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            fila_filtros,
            text="Limpiar",
            width=70,
            **estilos_boton("secundario"),
            command=self.limpiar_filtros
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            fila_filtros,
            text="Actualizar Lista",
            **estilos_boton("primario"),
            command=self.iniciar_carga_hilo
        ).pack(side="left", padx=5)

        self.label_estado = ctk.CTkLabel(
            fila_filtros,
            text="",
            text_color=color_estado("info")
        )
        self.label_estado.pack(side="left", padx=10)

        self.btn_excel = ctk.CTkButton(
            fila_acciones,
            text="Exportar a Excel",
            **estilos_boton("exito"),
            width=140,
            command=self.exportar_a_excel
        )
        self.btn_excel.pack(side="right", padx=5)

        self.btn_importar_precios = None
        if not any((
            self.solo_cafeteria,
            self.solo_aseo,
            self.solo_libreria,
        )):
            self.btn_importar_precios = ctk.CTkButton(
                fila_acciones,
                text="Importar precios Excel",
                **estilos_boton("secundario"),
                width=150,
                command=self.seleccionar_excel_precios,
            )
            self.btn_importar_precios.pack(side="left", padx=5)

        self.btn_editar = ctk.CTkButton(
            fila_acciones,
            text="Editar Seleccionado",
            **estilos_boton("primario"),
            width=140,
            command=self.abrir_formulario_edicion
        )
        self.btn_editar.pack(side="right", padx=5)

        self.btn_nuevo = ctk.CTkButton(
            fila_acciones,
            text="+ Nuevo Producto",
            **estilos_boton("primario"),
            command=self.abrir_formulario_producto
        )
        self.btn_nuevo.pack(side="right", padx=(5, 0))

        self.btn_restaurar = ctk.CTkButton(
            fila_acciones,
            text="Restaurar",
            **estilos_boton("alerta"),
            command=self.restaurar_producto
        )
        self.btn_restaurar.pack(side="right", padx=5)

        # =========================
        # TABLA
        # =========================
        frame_tabla = ctk.CTkFrame(self, **estilos_panel())
        frame_tabla.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar_inv = ctk.CTkScrollbar(frame_tabla, orientation="vertical")
        scrollbar_inv.pack(side="right", fill="y")

        columnas = (
            "ID",
            "Código",
            "Nombre",
            "Categoría",
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

        estilizar_treeview(self.tabla_inventario)

        anchos = {
            "Código": 120,
            "Nombre": 220,
            "Categoría": 120,
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
        if self._cargando_inventario:
            self._recarga_pendiente = True
            return
        self._carga_inventario_id += 1
        carga_id = self._carga_inventario_id
        self._cargando_inventario = True
        try:
            self.label_estado.configure(
                text="Cargando datos...",
                text_color=color_estado("cargando")
            )

            texto_busqueda = self.entry_busqueda.get().strip().lower()
            # Conservar los datos visibles y no acumular consultas al pulsar varias veces.
            self.after(30000, self._avisar_carga_lenta, carga_id)
            hilo = threading.Thread(
                target=self.cargar_inventario_pesado,
                args=(texto_busqueda, carga_id),
                daemon=True
            )
            hilo.start()

        except Exception as e:
            self._mostrar_error_carga(str(e), carga_id)

    def _avisar_carga_lenta(self, carga_id):
        if carga_id == self._carga_inventario_id and self._cargando_inventario:
            self.label_estado.configure(
                text="La conexión tarda. Esperando respuesta...",
                text_color=color_estado("error"),
            )

    def _mostrar_error_carga(self, error, carga_id):
        if carga_id != self._carga_inventario_id:
            return
        self._cargando_inventario = False
        self._recarga_pendiente = False
        print(f"Error cargando inventario: {error}")
        self.label_estado.configure(
            text="Error al cargar. Pulse Actualizar Lista para reintentar.",
            text_color=color_estado("error"),
        )

    def cargar_inventario_pesado(self, texto_busqueda, carga_id):
        try:
            productos = self.db.cargar_inventario_nube(propagar_error=True)
            filas_a_insertar = []

            for p in productos:
                if not self.producto_pertenece_a_vista(p):
                    continue

                nombre_prod = str(p.get("nombre", "")).lower()
                codigo_prod = str(p.get("codigo_barras", "")).lower()
                cat_prod = str(p.get("categoria", "")).lower()
                ubicacion_prod = str(p.get("ubicacion_codigo", "")).lower()
                dimensiones = self.decodificar_dimensiones(p)
                dimensiones_prod = " ".join(
                    str(dimensiones.get(campo) or "")
                    for campo in (
                        "formato",
                        "principal",
                        "secundaria",
                        "adicional",
                        "espesor",
                        "unidad_principal",
                        "unidad_secundaria",
                    )
                ).lower()

                if texto_busqueda and not (
                    texto_busqueda in nombre_prod
                    or texto_busqueda in codigo_prod
                    or texto_busqueda in cat_prod
                    or texto_busqueda in ubicacion_prod
                    or texto_busqueda in dimensiones_prod
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

            ejecutar_en_ui(
                self,
                self.actualizar_interfaz_tabla,
                filas_a_insertar,
                carga_id
            )

        except Exception as e:
            ejecutar_en_ui(self, self._mostrar_error_carga, str(e), carga_id)

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
                text_color=color_estado("ok")
            )
            self._cargando_inventario = False
            if self._recarga_pendiente:
                self._recarga_pendiente = False
                self.iniciar_carga_hilo()

        except Exception as e:
            self._mostrar_error_carga(str(e), carga_id)

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
    # IMPORTAR PRECIOS REFERENCIALES
    # ============================================================
    def seleccionar_excel_precios(self):
        if self._importando_precios:
            return

        ruta = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Seleccionar Excel de precios referenciales",
            filetypes=[("Archivos Excel", "*.xlsx")],
        )
        if not ruta:
            return

        self._importando_precios = True
        self._cambiar_estado_boton_importacion("disabled")
        self.label_estado.configure(
            text="Revisando precios y productos...",
            text_color=color_estado("cargando"),
        )
        threading.Thread(
            target=self._preparar_importacion_precios,
            args=(ruta,),
            daemon=True,
        ).start()

    def _cambiar_estado_boton_importacion(self, estado):
        if self.btn_importar_precios is not None:
            self.btn_importar_precios.configure(state=estado)

    def _preparar_importacion_precios(self, ruta):
        try:
            datos_excel = leer_precios_referenciales(ruta)
            productos = self.db.cargar_inventario_nube(propagar_error=True)
            plan = preparar_actualizaciones_precios(datos_excel, productos)
            ejecutar_en_ui(
                self,
                self._confirmar_importacion_precios,
                plan,
            )
        except Exception as error:
            ejecutar_en_ui(
                self,
                self._error_importacion_precios,
                str(error),
            )

    def _confirmar_importacion_precios(self, plan):
        cantidad = len(plan["actualizaciones"])
        resumen = (
            f"Productos revisados en el Excel: {plan['filas_revisadas']}\n"
            f"Con precio referencial CLP: {plan['con_precio']}\n"
            f"Sin precio referencial: {plan['sin_precio']}\n"
            f"Listos para actualizar: {cantidad}\n"
            f"Sin coincidencia: {len(plan['sin_coincidencia'])}\n"
            f"Coincidencias ambiguas: {len(plan['ambiguos'])}\n"
            f"Ya valorizados y omitidos: {len(plan['ya_valorizados'])}\n"
            f"Productos inactivos incluidos: {len(plan['inactivos'])}\n\n"
            "Se usará exclusivamente la columna 'Precio referencial CLP'.\n"
            "La columna 'Valor stock CLP' no será importada."
        )

        if not cantidad:
            self._restablecer_importacion_precios()
            return messagebox.showinfo(
                "Importación de precios",
                resumen + "\n\nNo hay precios nuevos para actualizar.",
                parent=self,
            )

        if not messagebox.askyesno(
            "Confirmar importación de precios",
            resumen + f"\n\n¿Actualizar los {cantidad} precios unitarios?",
            parent=self,
        ):
            self._restablecer_importacion_precios()
            return

        self.label_estado.configure(
            text=f"Actualizando 0 de {cantidad} precios...",
            text_color=color_estado("cargando"),
        )
        threading.Thread(
            target=self._aplicar_importacion_precios,
            args=(plan["actualizaciones"],),
            daemon=True,
        ).start()

    def _aplicar_importacion_precios(self, actualizaciones):
        exitos = 0
        errores = []
        total = len(actualizaciones)
        for indice, item in enumerate(actualizaciones, start=1):
            exito, mensaje = self.db.actualizar_producto_nube(
                item["producto_id"],
                {"precio_unitario": item["precio"]},
            )
            if exito:
                exitos += 1
            else:
                errores.append(f"{item['producto']}: {mensaje}")

            if indice == total or indice % 10 == 0:
                ejecutar_en_ui(
                    self,
                    self._mostrar_progreso_importacion,
                    indice,
                    total,
                )

        ejecutar_en_ui(
            self,
            self._finalizar_importacion_precios,
            exitos,
            errores,
        )

    def _mostrar_progreso_importacion(self, procesados, total):
        self.label_estado.configure(
            text=f"Actualizando {procesados} de {total} precios...",
            text_color=color_estado("cargando"),
        )

    def _finalizar_importacion_precios(self, exitos, errores):
        self._restablecer_importacion_precios()
        self.iniciar_carga_hilo()
        self.notificar_cambio_selectores()

        if errores:
            detalle = "\n".join(errores[:8])
            adicional = (
                f"\n... y {len(errores) - 8} errores más."
                if len(errores) > 8 else ""
            )
            return messagebox.showwarning(
                "Importación parcialmente completada",
                f"Precios actualizados: {exitos}\n"
                f"Errores: {len(errores)}\n\n{detalle}{adicional}\n\n"
                "Puede volver a importar el mismo Excel para reintentar los pendientes.",
                parent=self,
            )

        messagebox.showinfo(
            "Importación completada",
            f"Se actualizaron correctamente {exitos} precios unitarios.",
            parent=self,
        )

    def _error_importacion_precios(self, mensaje):
        self._restablecer_importacion_precios()
        self.label_estado.configure(
            text="No se pudo importar el Excel.",
            text_color=color_estado("error"),
        )
        messagebox.showerror(
            "Error importando precios",
            mensaje,
            parent=self,
        )

    def _restablecer_importacion_precios(self):
        self._importando_precios = False
        self._cambiar_estado_boton_importacion("normal")

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
        self.bodegas_cache = self.db.cargar_bodegas()
        self.racks_cache = self.db.cargar_racks()
        self.ubicaciones_cache = self.db.cargar_ubicaciones(solo_activas=True)

        self.bodega_nombre_a_id = {
            bodega.get("nombre"): bodega.get("id")
            for bodega in self.bodegas_cache
            if bodega.get("nombre") and bodega.get("id") is not None
        }
        self.bodega_id_a_nombre = {
            bodega_id: nombre
            for nombre, bodega_id in self.bodega_nombre_a_id.items()
        }
        self.racks_por_bodega = {}
        self.rack_etiqueta_a_id_por_bodega = {}
        self.rack_id_a_etiqueta = {}
        self.rack_por_id = {}

        for r in self.racks_cache:
            rack_id = r.get("id")
            bodega_id = r.get("bodega_id")

            if rack_id is not None and bodega_id is not None:
                self.racks_por_bodega.setdefault(bodega_id, []).append(r)
                self.rack_por_id[rack_id] = r

        for bodega_id, racks in self.racks_por_bodega.items():
            mapa = {}
            for rack in racks:
                etiqueta_base = self.etiqueta_sector_ubicacion(rack)
                etiqueta = etiqueta_base
                if etiqueta in mapa:
                    codigo = str(rack.get("codigo_rack") or "").strip()
                    etiqueta = f"{etiqueta_base} ({codigo})"
                mapa[etiqueta] = rack.get("id")
                self.rack_id_a_etiqueta[rack.get("id")] = etiqueta
            self.rack_etiqueta_a_id_por_bodega[bodega_id] = mapa

        self.ubicacion_por_id = {}
        self.bloques_por_posicion = {}

        for u in self.ubicaciones_cache:
            ubicacion_id = u.get("id")
            self.ubicacion_por_id[ubicacion_id] = u

            if u.get("tipo") == "Bloque":
                llave = (
                    u.get("rack_id"),
                    u.get("nivel")
                )
                actual = self.bloques_por_posicion.get(llave)
                if (
                    actual is None
                    or u.get("columna") in (None, "", "C01")
                ):
                    self.bloques_por_posicion[llave] = u

    @staticmethod
    def etiqueta_sector_ubicacion(rack):
        nombre = str(rack.get("nombre") or "").strip()
        codigo = str(rack.get("codigo_rack") or "").strip()
        return nombre or codigo or "Sector sin nombre"

    def crear_selector_ubicacion(self, parent, prefijo, ubicacion_id_actual=None):
        self.cargar_datos_ubicaciones_selector()

        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=0, pady=(5, 12))
        frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            frame,
            text="Bodega:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            frame,
            text="Sector:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=1, sticky="w", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            frame,
            text="Estante:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=2, sticky="w", padx=10, pady=(10, 0))

        bodega_values = ["Sin ubicación"] + list(
            self.bodega_nombre_a_id.keys()
        )

        combo_bodega = ctk.CTkComboBox(
            frame,
            values=bodega_values,
            width=150,
            state="readonly"
        )
        combo_bodega.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        combo_rack = ctk.CTkComboBox(
            frame,
            values=["Sin sector"],
            width=150,
            state="disabled"
        )
        combo_rack.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        combo_nivel = ctk.CTkComboBox(
            frame,
            values=["E001"],
            width=130,
            state="disabled"
        )
        combo_nivel.grid(row=1, column=2, padx=10, pady=5, sticky="ew")

        label_resultado = ctk.CTkLabel(
            frame,
            text="Ubicación seleccionada: Sin ubicación",
            text_color=color_estado("suave"),
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_resultado.grid(
            row=2,
            column=0,
            columnspan=3,
            padx=10,
            pady=(8, 10),
            sticky="ew"
        )
        adaptar_campos_en_fila(frame, 3, label_resultado)

        setattr(self, f"{prefijo}_combo_bodega", combo_bodega)
        setattr(self, f"{prefijo}_combo_rack", combo_rack)
        setattr(self, f"{prefijo}_combo_nivel", combo_nivel)
        setattr(self, f"{prefijo}_label_ubicacion", label_resultado)

        combo_bodega.configure(
            command=lambda value=None: self.actualizar_sectores_selector(
                prefijo
            )
        )
        combo_rack.configure(
            command=lambda value=None: self.actualizar_selector_ubicacion(prefijo)
        )
        combo_nivel.configure(
            command=lambda value=None: self.actualizar_selector_ubicacion(prefijo)
        )
        combo_bodega.set("Sin ubicación")
        combo_rack.set("Sin sector")
        combo_nivel.set("E001")

        if ubicacion_id_actual:
            self.seleccionar_ubicacion_en_selector(
                prefijo,
                ubicacion_id_actual
            )
        else:
            self.actualizar_selector_ubicacion(prefijo)

        return frame

    def actualizar_sectores_selector(self, prefijo):
        combo_bodega = getattr(self, f"{prefijo}_combo_bodega")
        combo_rack = getattr(self, f"{prefijo}_combo_rack")
        combo_nivel = getattr(self, f"{prefijo}_combo_nivel")
        bodega_nombre = combo_bodega.get()

        if bodega_nombre == "Sin ubicación":
            combo_rack.configure(values=["Sin sector"], state="disabled")
            combo_rack.set("Sin sector")
            combo_nivel.configure(state="disabled")
            self.actualizar_selector_ubicacion(prefijo)
            return

        bodega_id = self.bodega_nombre_a_id.get(bodega_nombre)
        mapa_racks = self.rack_etiqueta_a_id_por_bodega.get(bodega_id, {})
        etiquetas = list(mapa_racks.keys())
        rack_actual = combo_rack.get()

        if not etiquetas:
            combo_rack.configure(values=["Sin sectores"], state="disabled")
            combo_rack.set("Sin sectores")
            combo_nivel.configure(state="disabled")
            self.actualizar_selector_ubicacion(prefijo)
            return

        combo_rack.configure(values=etiquetas, state="readonly")
        combo_rack.set(
            rack_actual if rack_actual in etiquetas else etiquetas[0]
        )
        self.actualizar_selector_ubicacion(prefijo)

    def actualizar_selector_ubicacion(self, prefijo):
        combo_bodega = getattr(self, f"{prefijo}_combo_bodega")
        combo_rack = getattr(self, f"{prefijo}_combo_rack")
        combo_nivel = getattr(self, f"{prefijo}_combo_nivel")
        label_resultado = getattr(self, f"{prefijo}_label_ubicacion")

        bodega_nombre = combo_bodega.get()
        rack_etiqueta = combo_rack.get()

        if (
            bodega_nombre == "Sin ubicación"
            or rack_etiqueta in {"Sin sector", "Sin sectores"}
        ):
            combo_nivel.configure(state="disabled")
            label_resultado.configure(
                text="Ubicación seleccionada: Sin ubicación",
                text_color=color_estado("suave")
            )
            return

        combo_nivel.configure(state="readonly")

        bodega_id = self.bodega_nombre_a_id.get(bodega_nombre)
        rack_id = self.rack_etiqueta_a_id_por_bodega.get(
            bodega_id,
            {}
        ).get(rack_etiqueta)
        rack = self.rack_por_id.get(rack_id, {})

        total_estantes = (
            int(rack.get("niveles") or 5)
            * int(rack.get("columnas") or 2)
        )
        niveles_disponibles = [
            f"E{i:03d}"
            for i in range(1, total_estantes + 1)
        ]
        nivel_actual = combo_nivel.get()
        combo_nivel.configure(values=niveles_disponibles)
        combo_nivel.set(
            nivel_actual
            if nivel_actual in niveles_disponibles
            else niveles_disponibles[0]
        )

        nivel = combo_nivel.get()
        bloque = self.bloques_por_posicion.get((rack_id, nivel))

        if not bloque:
            label_resultado.configure(
                text=(
                    f"Ubicación seleccionada: "
                    f"{rack_etiqueta}, estante "
                    f"{nivel.lstrip('E0') or '0'} no existe"
                ),
                text_color=color_estado("cargando")
            )
            return

        ubicacion_id = self.obtener_ubicacion_id_selector(prefijo)
        ubicacion = self.ubicacion_por_id.get(ubicacion_id)

        if ubicacion:
            label_resultado.configure(
                text=(
                    f"Ubicación seleccionada: "
                    f"{ubicacion.get('codigo_ubicacion')}"
                ),
                text_color=color_estado("info")
            )
        else:
            label_resultado.configure(
                text="Ubicación seleccionada: Sin ubicación",
                text_color=color_estado("suave")
            )

    def obtener_ubicacion_id_selector(self, prefijo):
        combo_bodega = getattr(self, f"{prefijo}_combo_bodega")
        combo_rack = getattr(self, f"{prefijo}_combo_rack")
        combo_nivel = getattr(self, f"{prefijo}_combo_nivel")

        bodega_nombre = combo_bodega.get()
        rack_etiqueta = combo_rack.get()

        if bodega_nombre == "Sin ubicación":
            return None

        bodega_id = self.bodega_nombre_a_id.get(bodega_nombre)
        rack_id = self.rack_etiqueta_a_id_por_bodega.get(
            bodega_id,
            {}
        ).get(rack_etiqueta)
        nivel = combo_nivel.get()

        bloque = self.bloques_por_posicion.get((rack_id, nivel))

        if not bloque:
            return None

        return bloque.get("id")

    def seleccionar_ubicacion_en_selector(self, prefijo, ubicacion_id_actual):
        ubicacion = self.ubicacion_por_id.get(ubicacion_id_actual)

        combo_bodega = getattr(self, f"{prefijo}_combo_bodega")
        combo_rack = getattr(self, f"{prefijo}_combo_rack")
        combo_nivel = getattr(self, f"{prefijo}_combo_nivel")

        if not ubicacion:
            combo_bodega.set("Sin ubicación")
            self.actualizar_sectores_selector(prefijo)
            return

        if ubicacion.get("tipo") == "Subdivision":
            padre = self.ubicacion_por_id.get(
                ubicacion.get("ubicacion_padre_id")
            )

            if padre:
                ubicacion = padre

        rack = self.rack_por_id.get(ubicacion.get("rack_id"), {})
        bodega_nombre = self.bodega_id_a_nombre.get(rack.get("bodega_id"))
        rack_etiqueta = self.rack_id_a_etiqueta.get(rack.get("id"))

        if not bodega_nombre or not rack_etiqueta:
            combo_bodega.set("Sin ubicación")
            self.actualizar_sectores_selector(prefijo)
            return

        combo_bodega.set(bodega_nombre)
        self.actualizar_sectores_selector(prefijo)
        combo_rack.set(rack_etiqueta)
        combo_nivel.set(ubicacion.get("nivel", "E001"))

        self.actualizar_selector_ubicacion(prefijo)

    # ============================================================
    # FORMATO Y MEDICIÓN ESTRUCTURADA PARA RETAZOS
    # ============================================================
    FORMATOS_MEDICION = (
        "No aplica",
        "Plancha / Malla",
        "Tubo redondo",
        "Tubo cuadrado / rectangular",
        "Perfil / Barra",
        "Rollo",
        "Otro material",
        "Cálculo manual por porcentaje",
    )
    PREFIJO_DIMENSIONES = "MEDIDAS_V1:"

    def crear_selector_medicion(self, parent, prefijo, producto_actual=None):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=0, pady=(5, 12))
        frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            frame,
            text="Formato físico (opcional):",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=10,
            pady=(10, 0)
        )

        combo_formato = ctk.CTkComboBox(
            frame,
            values=list(self.FORMATOS_MEDICION),
            state="readonly",
            width=360,
            command=lambda value=None: self.actualizar_estado_medicion(prefijo)
        )
        combo_formato.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=10,
            pady=5,
            sticky="ew"
        )

        label_principal = ctk.CTkLabel(
            frame,
            text="Largo:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_principal.grid(
            row=2, column=0, sticky="w", padx=10, pady=(8, 0)
        )

        label_unidad_principal = ctk.CTkLabel(
            frame,
            text="Unidad del largo:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_unidad_principal.grid(
            row=2, column=1, sticky="w", padx=10, pady=(8, 0)
        )

        entry_principal = ctk.CTkEntry(
            frame,
            placeholder_text="Ej: 6 o 2,5",
            width=170
        )
        entry_principal.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        combo_unidad_principal = ctk.CTkComboBox(
            frame,
            values=["mm", "cm", "m", "unidad"],
            state="readonly",
            width=170
        )
        combo_unidad_principal.grid(
            row=3, column=1, padx=10, pady=5, sticky="ew"
        )

        label_secundaria = ctk.CTkLabel(
            frame,
            text="Ancho:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_secundaria.grid(
            row=4, column=0, sticky="w", padx=10, pady=(8, 0)
        )

        label_unidad_secundaria = ctk.CTkLabel(
            frame,
            text="Unidad de sección:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_unidad_secundaria.grid(
            row=4, column=1, sticky="w", padx=10, pady=(8, 0)
        )

        entry_secundaria = ctk.CTkEntry(
            frame,
            placeholder_text="Ej: 1200 o 50",
            width=170
        )
        entry_secundaria.grid(
            row=5, column=0, padx=10, pady=5, sticky="ew"
        )

        combo_unidad_secundaria = ctk.CTkComboBox(
            frame,
            values=["mm", "cm", "m", "unidad"],
            state="readonly",
            width=170
        )
        combo_unidad_secundaria.grid(
            row=5, column=1, padx=10, pady=5, sticky="ew"
        )

        label_adicional = ctk.CTkLabel(
            frame,
            text="Alto exterior:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_adicional.grid(
            row=6, column=0, sticky="w", padx=10, pady=(8, 0)
        )

        label_espesor = ctk.CTkLabel(
            frame,
            text="Espesor:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_espesor.grid(
            row=6, column=1, sticky="w", padx=10, pady=(8, 0)
        )

        entry_adicional = ctk.CTkEntry(
            frame,
            placeholder_text="Opcional",
            width=170
        )
        entry_adicional.grid(
            row=7, column=0, padx=10, pady=5, sticky="ew"
        )

        entry_espesor = ctk.CTkEntry(
            frame,
            placeholder_text="Opcional",
            width=170
        )
        entry_espesor.grid(
            row=7, column=1, padx=10, pady=5, sticky="ew"
        )

        label_ayuda = ctk.CTkLabel(
            frame,
            text=(
                "Todos estos datos son opcionales. Al elegir un formato se "
                "muestran las medidas adecuadas para ese material."
            ),
            text_color=color_estado("suave"),
            font=ctk.CTkFont(size=11),
            wraplength=390
        )
        label_ayuda.grid(
            row=8,
            column=0,
            columnspan=2,
            padx=10,
            pady=(5, 10),
            sticky="ew"
        )

        widgets = {
            "combo_formato": combo_formato,
            "label_principal": label_principal,
            "label_unidad_principal": label_unidad_principal,
            "entry_principal": entry_principal,
            "combo_unidad_principal": combo_unidad_principal,
            "label_secundaria": label_secundaria,
            "label_unidad_secundaria": label_unidad_secundaria,
            "entry_secundaria": entry_secundaria,
            "combo_unidad_secundaria": combo_unidad_secundaria,
            "label_adicional": label_adicional,
            "entry_adicional": entry_adicional,
            "label_espesor": label_espesor,
            "entry_espesor": entry_espesor,
        }
        setattr(self, f"{prefijo}_widgets_medicion", widgets)

        configuracion = self.decodificar_dimensiones(producto_actual or {})
        combo_formato.set(configuracion["formato"])
        combo_unidad_principal.set(configuracion["unidad_principal"])
        combo_unidad_secundaria.set(configuracion["unidad_secundaria"])

        for widget, valor in (
            (entry_principal, configuracion["principal"]),
            (entry_secundaria, configuracion["secundaria"]),
            (entry_adicional, configuracion["adicional"]),
            (entry_espesor, configuracion["espesor"]),
        ):
            if valor not in (None, ""):
                widget.insert(0, str(valor))

        self.actualizar_estado_medicion(prefijo)

        return frame

    def actualizar_estado_medicion(self, prefijo):
        widgets = getattr(self, f"{prefijo}_widgets_medicion")
        formato = widgets["combo_formato"].get()

        etiquetas = {
            "Plancha / Malla": ("Largo:", "Ancho:", "", "Espesor:"),
            "Tubo redondo": (
                "Largo del tubo:",
                "Diámetro exterior:",
                "",
                "Espesor de pared:",
            ),
            "Tubo cuadrado / rectangular": (
                "Largo del tubo:",
                "Ancho exterior:",
                "Alto exterior:",
                "Espesor de pared:",
            ),
            "Perfil / Barra": (
                "Largo:",
                "Ancho o diámetro:",
                "Alto:",
                "Espesor:",
            ),
            "Rollo": ("Largo total:", "Ancho:", "", "Espesor:"),
            "Otro material": (
                "Medida principal:",
                "Medida secundaria:",
                "Medida adicional:",
                "Espesor:",
            ),
        }
        es_fisico = formato in etiquetas
        tiene_adicional = es_fisico and bool(etiquetas[formato][2])

        widgets_basicos = (
            widgets["label_principal"],
            widgets["label_unidad_principal"],
            widgets["entry_principal"],
            widgets["combo_unidad_principal"],
            widgets["label_secundaria"],
            widgets["label_unidad_secundaria"],
            widgets["entry_secundaria"],
            widgets["combo_unidad_secundaria"],
            widgets["label_espesor"],
            widgets["entry_espesor"],
        )
        for widget in widgets_basicos:
            if es_fisico:
                widget.grid()
            else:
                widget.grid_remove()

        for widget in (
            widgets["label_adicional"],
            widgets["entry_adicional"],
        ):
            if tiene_adicional:
                widget.grid()
            else:
                widget.grid_remove()

        for nombre in (
            "entry_principal",
            "entry_secundaria",
            "entry_adicional",
            "entry_espesor",
        ):
            widgets[nombre].configure(
                state="normal" if es_fisico else "disabled"
            )

        for nombre in ("combo_unidad_principal", "combo_unidad_secundaria"):
            widgets[nombre].configure(
                state="readonly" if es_fisico else "disabled"
            )

        if es_fisico:
            principal, secundaria, adicional, espesor = etiquetas[formato]
            widgets["label_principal"].configure(text=principal)
            widgets["label_secundaria"].configure(text=secundaria)
            widgets["label_adicional"].configure(
                text=adicional or "Medida adicional:"
            )
            widgets["label_espesor"].configure(text=espesor)

        widgets["entry_adicional"].configure(
            state="normal" if tiene_adicional else "disabled"
        )

    @classmethod
    def decodificar_dimensiones(cls, producto):
        texto = str(producto.get("tamaño_dimensiones") or "").strip()
        tipo_legacy = producto.get("tipo_medicion") or "No aplica"
        formatos_legacy = {
            "Área": "Plancha / Malla",
            "Largo": "Perfil / Barra",
            "Porcentaje": "Cálculo manual por porcentaje",
        }
        resultado = {
            "formato": formatos_legacy.get(tipo_legacy, "No aplica"),
            "principal": producto.get("medida_largo") or "",
            "secundaria": producto.get("medida_ancho") or "",
            "adicional": "",
            "espesor": "",
            "unidad_principal": producto.get("unidad_medida") or "m",
            "unidad_secundaria": producto.get("unidad_medida") or "mm",
        }

        if not texto.startswith(cls.PREFIJO_DIMENSIONES):
            return resultado

        try:
            datos = json.loads(texto[len(cls.PREFIJO_DIMENSIONES):])
            formato = datos.get("formato")
            if formato in cls.FORMATOS_MEDICION:
                resultado["formato"] = formato
            for campo in ("principal", "secundaria", "adicional", "espesor"):
                resultado[campo] = datos.get(campo) or ""
            resultado["unidad_principal"] = (
                datos.get("unidad_principal") or resultado["unidad_principal"]
            )
            resultado["unidad_secundaria"] = (
                datos.get("unidad_secundaria")
                or resultado["unidad_secundaria"]
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

        return resultado

    @classmethod
    def codificar_dimensiones(cls, datos):
        if datos.get("formato") == "No aplica":
            return ""

        payload = {
            "formato": datos.get("formato"),
            "principal": datos.get("principal"),
            "secundaria": datos.get("secundaria"),
            "adicional": datos.get("adicional"),
            "espesor": datos.get("espesor"),
            "unidad_principal": datos.get("unidad_principal"),
            "unidad_secundaria": datos.get("unidad_secundaria"),
        }
        return cls.PREFIJO_DIMENSIONES + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":")
        )

    def convertir_numero_decimal(self, texto):
        texto = str(texto).strip().replace(",", ".")

        if texto == "":
            return None

        return float(texto)

    def obtener_datos_medicion(self, prefijo):
        widgets = getattr(self, f"{prefijo}_widgets_medicion")
        formato = widgets["combo_formato"].get()

        if formato == "Cálculo manual por porcentaje":
            datos = {
                "formato": formato,
                "principal": None,
                "secundaria": None,
                "adicional": None,
                "espesor": None,
                "unidad_principal": "%",
                "unidad_secundaria": "%",
            }
            return {
                "tipo_medicion": "Porcentaje",
                "medida_largo": None,
                "medida_ancho": None,
                "unidad_medida": "%",
                "tamaño_dimensiones": self.codificar_dimensiones(datos),
            }

        campos_activos = set()
        if formato in self.FORMATOS_MEDICION[1:7]:
            campos_activos.update(("principal", "secundaria", "espesor"))
        if formato in (
            "Tubo cuadrado / rectangular",
            "Perfil / Barra",
            "Otro material",
        ):
            campos_activos.add("adicional")

        valores = {}
        for campo, widget_nombre in (
            ("principal", "entry_principal"),
            ("secundaria", "entry_secundaria"),
            ("adicional", "entry_adicional"),
            ("espesor", "entry_espesor"),
        ):
            if campo not in campos_activos:
                valores[campo] = None
                continue
            try:
                valor = self.convertir_numero_decimal(
                    widgets[widget_nombre].get()
                )
            except Exception as error:
                raise ValueError(
                    "Las medidas deben ser números válidos mayores a cero."
                ) from error
            if valor is not None and valor <= 0:
                raise ValueError(
                    "Las medidas ingresadas deben ser mayores a cero."
                )
            valores[campo] = valor

        if formato in ("Plancha / Malla", "Rollo"):
            una_sola = (valores["principal"] is None) != (
                valores["secundaria"] is None
            )
            if una_sola:
                raise ValueError(
                    "Para calcular retazos de una plancha o rollo, complete "
                    "largo y ancho, o deje ambas medidas vacías."
                )

        if formato in ("Plancha / Malla", "Rollo") and all((
            valores["principal"] is not None,
            valores["secundaria"] is not None,
        )):
            tipo_medicion = "Área"
        elif valores["principal"] is not None:
            tipo_medicion = "Largo"
        else:
            tipo_medicion = "No aplica"

        datos = {
            "formato": formato,
            **valores,
            "unidad_principal": widgets["combo_unidad_principal"].get(),
            "unidad_secundaria": widgets["combo_unidad_secundaria"].get(),
        }
        medida_ancho_base = None
        if tipo_medicion == "Área":
            medida_ancho_base = self.convertir_entre_unidades(
                valores["secundaria"],
                datos["unidad_secundaria"],
                datos["unidad_principal"]
            )

        return {
            "tipo_medicion": tipo_medicion,
            "medida_largo": valores["principal"],
            "medida_ancho": medida_ancho_base,
            "unidad_medida": (
                datos["unidad_principal"]
                if tipo_medicion != "No aplica" else None
            ),
            "tamaño_dimensiones": self.codificar_dimensiones(datos),
        }

    @staticmethod
    def convertir_entre_unidades(valor, unidad_origen, unidad_destino):
        if valor is None or unidad_origen == unidad_destino:
            return valor

        factores_metros = {
            "mm": 0.001,
            "cm": 0.01,
            "m": 1.0,
        }
        if (
            unidad_origen not in factores_metros
            or unidad_destino not in factores_metros
        ):
            return valor

        valor_metros = valor * factores_metros[unidad_origen]
        return valor_metros / factores_metros[unidad_destino]

    # ============================================================
    # RESTAURAR
    # ============================================================
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
        estado = item["values"][8]

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
                self.notificar_cambio_selectores()
            else:
                messagebox.showerror("Error", msg)

    # ============================================================
    # NUEVO PRODUCTO
    # ============================================================
    def abrir_formulario_producto(self):
        nombre_inventario = self.obtener_nombre_inventario()
        self.ventana_nuevo = VentanaAdaptable(self)
        self.ventana_nuevo.title(
            f"Agregar Insumo de {nombre_inventario}"
            if nombre_inventario else
            "Agregar Nuevo Producto"
        )
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

        self.ventana_nuevo.configure(fg_color=PALETA["fondo"])
        scroll = ctk.CTkScrollableFrame(self.ventana_nuevo, fg_color=PALETA["panel"])
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            scroll,
            text=(
                f"Registro de Insumo de {nombre_inventario}"
                if nombre_inventario else
                "Registro Manual de Producto"
            ),
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=15)

        categorias = self.obtener_categorias_formulario()

        self.entry_nombre = ctk.CTkEntry(
            scroll,
            placeholder_text="Nombre del Producto",
            width=390
        )
        self.entry_nombre.pack(fill="x", padx=25, pady=5)

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
        self.combo_categoria.pack(fill="x", padx=25, pady=5)
        self.combo_categoria.set(categorias[0])

        self.entry_stock = ctk.CTkEntry(
            scroll,
            placeholder_text="Stock Inicial",
            width=390
        )
        self.entry_stock.pack(fill="x", padx=25, pady=5)

        self.entry_stock_minimo = ctk.CTkEntry(
            scroll,
            placeholder_text="Stock Mínimo",
            width=390
        )
        self.entry_stock_minimo.pack(fill="x", padx=25, pady=5)

        self.entry_precio = ctk.CTkEntry(
            scroll,
            placeholder_text="Precio Unitario Neto",
            width=390
        )
        self.entry_precio.pack(fill="x", padx=25, pady=5)

        ctk.CTkLabel(
            scroll,
            text="Formato y mediciones (opcional):",
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
            **estilos_boton("primario"),
            height=45,
            width=390,
            command=self.guardar_producto
        ).pack(fill="x", padx=25, pady=15)

    def guardar_producto(self):
        nombre = self.entry_nombre.get().strip()
        cat = self.combo_categoria.get().strip()
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
            datos_medicion["tamaño_dimensiones"],
            stock_int,
            precio_int,
            ubicacion_id=ubicacion_id,
            stock_minimo=stock_minimo_int,
            tipo_medicion=datos_medicion["tipo_medicion"],
            medida_largo=datos_medicion["medida_largo"],
            medida_ancho=datos_medicion["medida_ancho"],
            unidad_medida=datos_medicion["unidad_medida"]
        )

        if exito:
            messagebox.showinfo(
                "Éxito",
                "Producto registrado correctamente.",
                parent=self.ventana_nuevo
            )
            self.ventana_nuevo.destroy()
            self.iniciar_carga_hilo()
            self.notificar_cambio_selectores()

        else:
            messagebox.showerror("Error", msg, parent=self.ventana_nuevo)

    def notificar_cambio_selectores(self):
        app = self.winfo_toplevel()
        if hasattr(app, "vista_salidas"):
            app.vista_salidas.iniciar_carga_selectores()
        if hasattr(app, "vista_pgp"):
            app.vista_pgp.iniciar_carga_selectores()

        for nombre_vista in (
            "vista_inventario",
            "vista_cafeteria",
            "vista_aseo",
            "vista_libreria"
        ):
            vista = getattr(app, nombre_vista, None)
            if vista is not None and vista is not self:
                vista.iniciar_carga_hilo()

    def obtener_nombre_inventario(self):
        if getattr(self, "solo_cafeteria", False):
            return "Cafetería"
        if getattr(self, "solo_aseo", False):
            return "Aseo"
        if getattr(self, "solo_libreria", False):
            return "Librería"
        return None

    def producto_pertenece_a_vista(self, producto):
        if getattr(self, "solo_cafeteria", False):
            return es_producto_cafeteria(producto)
        if getattr(self, "solo_aseo", False):
            return es_producto_aseo(producto)
        if getattr(self, "solo_libreria", False):
            return es_producto_libreria(producto)
        return True

    def obtener_categorias_formulario(self):
        nombre_inventario = self.obtener_nombre_inventario()
        if nombre_inventario:
            return [nombre_inventario]
        return list(self.CATEGORIAS)

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

        self.ventana_editar = VentanaAdaptable(self)
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

        self.ventana_editar.configure(fg_color=PALETA["fondo"])
        scroll = ctk.CTkScrollableFrame(self.ventana_editar, fg_color=PALETA["panel"])
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            scroll,
            text="EDITAR PRODUCTO",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            scroll,
            text=f"Código: {prod_db.get('codigo_barras', '')}",
            text_color=color_estado("suave")
        ).pack(pady=(0, 20))

        frame_form = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_form.pack(fill="both", expand=True, padx=20)

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

        categorias = self.obtener_categorias_formulario()

        self.ed_cat = ctk.CTkComboBox(
            frame_form,
            values=categorias,
            height=35,
            state="readonly"
        )
        categoria_actual = prod_db.get("categoria")
        if categoria_actual in categorias:
            categoria_formulario = categoria_actual
        elif (
            es_producto_cafeteria(prod_db)
            and "Cafetería" in categorias
        ):
            categoria_formulario = "Cafetería"
        elif es_producto_aseo(prod_db) and "Aseo" in categorias:
            categoria_formulario = "Aseo"
        elif es_producto_libreria(prod_db) and "Librería" in categorias:
            categoria_formulario = "Librería"
        else:
            categoria_formulario = categorias[0]

        self.ed_cat.set(categoria_formulario)
        self.ed_cat.pack(fill="x", pady=(0, 10))

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
            text="Cantidad / Stock:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=1, sticky="w")

        self.ed_stock = ctk.CTkEntry(frame_num, height=35)
        self.ed_stock.insert(0, prod_db.get("stock", 0))
        self.ed_stock.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkLabel(
            frame_num,
            text="Stock mín.:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=2, sticky="w")

        self.ed_stock_min = ctk.CTkEntry(frame_num, height=35)
        self.ed_stock_min.insert(0, prod_db.get("stock_minimo", 0))
        self.ed_stock_min.grid(row=1, column=2, sticky="ew")
        adaptar_campos_en_fila(frame_num, 3)

        ctk.CTkLabel(
            frame_form,
            text="Formato y mediciones (opcional):",
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
    **estilos_boton("primario"),
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
                self.ed_cat
            ]

            for w in widgets:
                if not w.winfo_exists():
                    self.guardando_edicion = False
                    return

            precio_txt = self.ed_precio.get().strip()
            stock_txt = self.ed_stock.get().strip()
            stock_min_txt = self.ed_stock_min.get().strip()

            precio = int(precio_txt) if precio_txt else 0
            stock = self.validar_cantidad_edicion(stock_txt)
            stock_min = int(stock_min_txt) if stock_min_txt else 0

            if precio < 0 or stock < 0 or stock_min < 0:
                raise ValueError(
                    "El precio, la cantidad y el stock mínimo deben ser "
                    "mayores o iguales a 0."
                )

            nombre = self.ed_nombre.get().strip()
            if not nombre:
                raise ValueError("El nombre del producto es obligatorio.")

            ubicacion_id = self.obtener_ubicacion_id_selector("editar")
            datos_medicion = self.obtener_datos_medicion("editar")

            datos = {
                "nombre": nombre,
                "categoria": self.ed_cat.get(),
                "precio_unitario": precio,
                "stock": stock,
                "stock_minimo": stock_min,
                "ubicacion_id": ubicacion_id,
                "tamaño_dimensiones": datos_medicion["tamaño_dimensiones"],
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
                self.notificar_cambio_selectores()
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

    @staticmethod
    def validar_cantidad_edicion(valor):
        texto = str(valor or "").strip()
        try:
            cantidad = int(texto) if texto else 0
        except (TypeError, ValueError):
            raise ValueError(
                "La cantidad debe ser un número entero mayor o igual a 0."
            )

        if cantidad < 0:
            raise ValueError(
                "La cantidad debe ser un número entero mayor o igual a 0."
            )
        return cantidad
