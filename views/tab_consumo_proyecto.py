import customtkinter as ctk
from tkinter import ttk, messagebox
import threading


class ConsumoProyectoTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")

        self.db = db_manager
        self.proyectos = []
        self._carga_consumo_id = 0

        self.crear_interfaz()
        self.after(2500, self.cargar_proyectos)

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # =====================================================
        # BARRA SUPERIOR
        # =====================================================
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.grid(row=0, column=0, sticky="ew", padx=15, pady=10)

        ctk.CTkLabel(
            frame_top,
            text="Consumo por Proyecto",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(
            frame_top,
            text="Proyecto:"
        ).pack(side="left", padx=(5, 5))

        self.combo_proyecto = ctk.CTkComboBox(
            frame_top,
            values=[],
            width=260,
            state="readonly"
        )
        self.combo_proyecto.pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="Actualizar",
            width=110,
            command=self.cargar_consumo
        ).pack(side="left", padx=10)

        self.label_estado = ctk.CTkLabel(
            frame_top,
            text="",
            text_color="gray"
        )
        self.label_estado.pack(side="left", padx=10)

        # =====================================================
        # TARJETAS RESUMEN
        # =====================================================
        frame_resumen = ctk.CTkFrame(self)
        frame_resumen.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        frame_resumen.grid_columnconfigure((0, 1, 2), weight=1)

        self.card_productos = self.crear_card_resumen(
            frame_resumen,
            "Productos distintos",
            "0",
            0
        )

        self.card_cantidad = self.crear_card_resumen(
            frame_resumen,
            "Cantidad consumida",
            "0",
            1
        )

        self.card_valor = self.crear_card_resumen(
            frame_resumen,
            "Valor estimado",
            "$0",
            2
        )

        # =====================================================
        # TABLAS
        # =====================================================
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 15))

        self.tab_resumen = self.tabview.add("Resumen por Producto")
        self.tab_historial = self.tabview.add("Historial Detallado")

        self.crear_tabla_resumen()
        self.crear_tabla_historial()

    def crear_card_resumen(self, parent, titulo, valor, columna):
        frame = ctk.CTkFrame(parent, corner_radius=15)
        frame.grid(row=0, column=columna, padx=8, pady=10, sticky="ew")

        label_titulo = ctk.CTkLabel(
            frame,
            text=titulo,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray"
        )
        label_titulo.pack(pady=(12, 3))

        label_valor = ctk.CTkLabel(
            frame,
            text=valor,
            font=ctk.CTkFont(size=24, weight="bold")
        )
        label_valor.pack(pady=(0, 12))

        return label_valor

    def crear_tabla_resumen(self):
        frame = ctk.CTkFrame(self.tab_resumen)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ctk.CTkScrollbar(frame, orientation="vertical")
        scrollbar.pack(side="right", fill="y")

        columnas = (
            "Producto",
            "Código",
            "Categoría",
            "Ubicación",
            "Cantidad",
            "Valor Estimado"
        )

        self.tabla_resumen = ttk.Treeview(
            frame,
            columns=columnas,
            show="headings",
            yscrollcommand=scrollbar.set
        )

        scrollbar.configure(command=self.tabla_resumen.yview)

        anchos = {
            "Producto": 240,
            "Código": 130,
            "Categoría": 130,
            "Ubicación": 160,
            "Cantidad": 90,
            "Valor Estimado": 130
        }

        for col in columnas:
            self.tabla_resumen.heading(col, text=col)
            self.tabla_resumen.column(col, width=anchos[col], anchor="center")

        self.tabla_resumen.pack(fill="both", expand=True)

    def crear_tabla_historial(self):
        frame = ctk.CTkFrame(self.tab_historial)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ctk.CTkScrollbar(frame, orientation="vertical")
        scrollbar.pack(side="right", fill="y")

        columnas = (
            "Fecha",
            "Producto",
            "Código",
            "Movimiento",
            "Cantidad",
            "Valor",
            "Responsable",
            "Ubicación"
        )

        self.tabla_historial = ttk.Treeview(
            frame,
            columns=columnas,
            show="headings",
            yscrollcommand=scrollbar.set
        )

        scrollbar.configure(command=self.tabla_historial.yview)

        anchos = {
            "Fecha": 130,
            "Producto": 220,
            "Código": 120,
            "Movimiento": 170,
            "Cantidad": 80,
            "Valor": 110,
            "Responsable": 160,
            "Ubicación": 160
        }

        for col in columnas:
            self.tabla_historial.heading(col, text=col)
            self.tabla_historial.column(col, width=anchos[col], anchor="center")

        self.tabla_historial.pack(fill="both", expand=True)

    # ============================================================
    # CARGA DE PROYECTOS
    # ============================================================
    def cargar_proyectos(self):
        try:
            proyectos = self.db.cargar_proyectos()

            if not proyectos:
                proyectos = ["Taller Interno"]

            self.proyectos = proyectos
            self.combo_proyecto.configure(values=proyectos)

            if proyectos:
                self.combo_proyecto.set(proyectos[0])

            self.cargar_consumo()

        except Exception as e:
            print(f"Error cargando proyectos en consumo: {e}")
            self.label_estado.configure(
                text="Error cargando proyectos.",
                text_color="red"
            )

    # ============================================================
    # CARGA DE CONSUMO
    # ============================================================
    def cargar_consumo(self):
        proyecto = self.combo_proyecto.get()

        if not proyecto:
            return messagebox.showwarning(
                "Aviso",
                "Seleccione un proyecto."
            )

        self.label_estado.configure(text="Cargando consumo...", text_color="orange")
        self._carga_consumo_id += 1
        carga_id = self._carga_consumo_id

        threading.Thread(
            target=self.cargar_consumo_pesado,
            args=(proyecto, carga_id),
            daemon=True
        ).start()

    def cargar_consumo_pesado(self, proyecto, carga_id):
        try:
            resumen = self.db.obtener_resumen_consumo_proyecto(proyecto)
            historial = self.db.obtener_historial_consumo_proyecto(proyecto)
            totales = {
                "productos_distintos": len(resumen),
                "cantidad_total": sum(int(fila[4] or 0) for fila in resumen),
                "valor_total": sum(int(fila[5] or 0) for fila in resumen)
            }

            self.after(
                0,
                self.actualizar_interfaz,
                resumen,
                historial,
                totales,
                proyecto,
                carga_id
            )

        except Exception as e:
            print(f"Error cargando consumo pesado: {e}")
            try:
                self.after(
                    0,
                    lambda: self.label_estado.configure(
                        text="Error cargando consumo.",
                        text_color="red"
                    )
                )
            except Exception:
                pass

    def actualizar_interfaz(
        self,
        resumen,
        historial,
        totales,
        proyecto,
        carga_id
    ):
        try:
            if (
                carga_id != self._carga_consumo_id
                or proyecto != self.combo_proyecto.get()
            ):
                return

            for item in self.tabla_resumen.get_children():
                self.tabla_resumen.delete(item)

            for item in self.tabla_historial.get_children():
                self.tabla_historial.delete(item)

            for fila in resumen:
                fila_formateada = (
                    fila[0],
                    fila[1],
                    fila[2],
                    fila[3],
                    fila[4],
                    self.formatear_pesos(fila[5])
                )

                self.tabla_resumen.insert("", "end", values=fila_formateada)

            for fila in historial:
                fila_formateada = (
                    fila[0],
                    fila[1],
                    fila[2],
                    fila[3],
                    fila[4],
                    self.formatear_pesos(fila[5]),
                    fila[6],
                    fila[7]
                )

                self.tabla_historial.insert("", "end", values=fila_formateada)

            self.card_productos.configure(
                text=str(totales.get("productos_distintos", 0))
            )

            self.card_cantidad.configure(
                text=str(totales.get("cantidad_total", 0))
            )

            self.card_valor.configure(
                text=self.formatear_pesos(totales.get("valor_total", 0))
            )

            self.label_estado.configure(
                text="Consumo actualizado.",
                text_color="green"
            )

        except Exception as e:
            print(f"Error actualizando consumo: {e}")
            self.label_estado.configure(
                text="Error actualizando vista.",
                text_color="red"
            )

    def formatear_pesos(self, valor):
        try:
            valor_int = int(valor or 0)
            return "$" + f"{valor_int:,}".replace(",", ".")
        except Exception:
            return "$0"
        
    def actualizar_proyectos(self):
        try:
            proyecto_actual = self.combo_proyecto.get()

            proyectos = self.db.cargar_proyectos()

            if not proyectos:
                proyectos = ["Taller Interno"]

            self.proyectos = proyectos
            self.combo_proyecto.configure(values=proyectos)

            if proyecto_actual in proyectos:
                self.combo_proyecto.set(proyecto_actual)
            else:
                self.combo_proyecto.set(proyectos[0])

            self.cargar_consumo()

            return True

        except Exception as e:
            print(f"Error actualizando proyectos en consumo: {e}")
            return False
