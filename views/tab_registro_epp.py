from datetime import datetime
import threading
import unicodedata

import customtkinter as ctk
from tkinter import ttk

from utils.ui_theme import (
    PALETA,
    color_estado,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.fechas import fecha_hora_local


class RegistroEppTab(ctk.CTkFrame):
    TODOS = "Todos"
    TITULO_REGISTRO = "Registro de Entregas EPP"
    NOMBRE_ELEMENTO = "EPP"
    NOMBRE_ELEMENTO_TABLA = "EPP entregado"
    CLAVE_ELEMENTO = "epp"
    ELEMENTO_DESCONOCIDO = "EPP desconocido"
    TEXTO_CARGANDO = "Cargando entregas EPP..."

    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")

        self.db = db_manager
        iniciar_despachador_ui(self)
        self.entregas = []
        self._carga_id = 0

        self.crear_interfaz()
        self.after(1000, self.iniciar_carga)

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        frame_top = ctk.CTkFrame(self, **estilos_barra())
        frame_top.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        frame_top.grid_columnconfigure(0, weight=1)

        fila_titulo = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_titulo.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        ctk.CTkLabel(
            fila_titulo,
            text=self.TITULO_REGISTRO,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETA["primario"]
        ).pack(side="left")

        self.label_estado = ctk.CTkLabel(
            fila_titulo,
            text="",
            text_color=color_estado("suave")
        )
        self.label_estado.pack(side="right", padx=10)

        filtros = ctk.CTkFrame(frame_top, fg_color="transparent")
        filtros.grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 4))
        for columna in range(5):
            filtros.grid_columnconfigure(columna, weight=1)

        self.entry_busqueda = self.crear_filtro_entrada(
            filtros,
            "Búsqueda general",
            f"Nombre, RUT, {self.NOMBRE_ELEMENTO}, proyecto o comentario",
            0
        )
        self.entry_busqueda.bind("<KeyRelease>", self.aplicar_filtros)

        self.combo_trabajador = self.crear_filtro_combo(
            filtros,
            "Trabajador",
            1
        )
        self.combo_epp = self.crear_filtro_combo(
            filtros, self.NOMBRE_ELEMENTO, 2
        )
        self.combo_proyecto = self.crear_filtro_combo(
            filtros,
            "Proyecto / destino",
            3
        )

        frame_fechas = ctk.CTkFrame(filtros, fg_color="transparent")
        frame_fechas.grid(row=0, column=4, sticky="ew", padx=5)
        frame_fechas.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(frame_fechas, text="Desde").grid(
            row=0, column=0, sticky="w", padx=(0, 4)
        )
        ctk.CTkLabel(frame_fechas, text="Hasta").grid(
            row=0, column=1, sticky="w", padx=(4, 0)
        )

        self.entry_desde = ctk.CTkEntry(
            frame_fechas,
            placeholder_text="AAAA-MM-DD"
        )
        self.entry_desde.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        self.entry_desde.bind("<Return>", self.aplicar_filtros)

        self.entry_hasta = ctk.CTkEntry(
            frame_fechas,
            placeholder_text="AAAA-MM-DD"
        )
        self.entry_hasta.grid(row=1, column=1, sticky="ew", padx=(4, 0))
        self.entry_hasta.bind("<Return>", self.aplicar_filtros)

        fila_acciones = ctk.CTkFrame(frame_top, fg_color="transparent")
        fila_acciones.grid(row=2, column=0, sticky="ew", padx=12, pady=(5, 10))

        ctk.CTkButton(
            fila_acciones,
            text="Aplicar filtros",
            width=120,
            **estilos_boton("primario"),
            command=self.aplicar_filtros
        ).pack(side="left", padx=(5, 5))

        ctk.CTkButton(
            fila_acciones,
            text="Limpiar filtros",
            width=120,
            **estilos_boton("secundario"),
            command=self.limpiar_filtros
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            fila_acciones,
            text="Actualizar registro",
            width=135,
            **estilos_boton("fantasma"),
            command=self.iniciar_carga
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            fila_acciones,
            text="Fechas en formato AAAA-MM-DD",
            text_color=PALETA["texto_suave"]
        ).pack(side="right", padx=8)

        frame_resumen = ctk.CTkFrame(self, **estilos_panel())
        frame_resumen.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        frame_resumen.grid_columnconfigure((0, 1, 2), weight=1)

        self.card_entregas = self.crear_card(
            frame_resumen, "Entregas encontradas", 0
        )
        self.card_unidades = self.crear_card(
            frame_resumen, "Unidades entregadas", 1
        )
        self.card_trabajadores = self.crear_card(
            frame_resumen, "Trabajadores distintos", 2
        )

        frame_tabla = ctk.CTkFrame(self, **estilos_panel())
        frame_tabla.grid(
            row=2, column=0, sticky="nsew", padx=15, pady=(0, 15)
        )
        frame_tabla.grid_columnconfigure(0, weight=1)
        frame_tabla.grid_rowconfigure(0, weight=1)

        columnas = (
            "Fecha",
            "Trabajador",
            "RUT",
            self.NOMBRE_ELEMENTO_TABLA,
            "Cantidad",
            "Proyecto / Destino",
            "Entregado por",
            "Comentario",
        )

        self.tabla = ttk.Treeview(
            frame_tabla,
            columns=columnas,
            show="headings"
        )
        estilizar_treeview(self.tabla)

        barra_vertical = ctk.CTkScrollbar(
            frame_tabla,
            orientation="vertical",
            command=self.tabla.yview
        )
        barra_horizontal = ctk.CTkScrollbar(
            frame_tabla,
            orientation="horizontal",
            command=self.tabla.xview
        )
        self.tabla.configure(
            yscrollcommand=barra_vertical.set,
            xscrollcommand=barra_horizontal.set
        )

        anchos = {
            "Fecha": 135,
            "Trabajador": 190,
            "RUT": 110,
            self.NOMBRE_ELEMENTO_TABLA: 220,
            "Cantidad": 80,
            "Proyecto / Destino": 180,
            "Entregado por": 180,
            "Comentario": 260,
        }
        for columna in columnas:
            self.tabla.heading(columna, text=columna)
            self.tabla.column(
                columna,
                width=anchos[columna],
                minwidth=70,
                anchor="center"
            )

        self.tabla.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))
        barra_vertical.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=(10, 0))
        barra_horizontal.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(4, 8))

    def crear_filtro_entrada(self, parent, titulo, placeholder, columna):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=columna, sticky="ew", padx=5)
        ctk.CTkLabel(frame, text=titulo).pack(anchor="w")
        entry = ctk.CTkEntry(frame, placeholder_text=placeholder)
        entry.pack(fill="x")
        return entry

    def crear_filtro_combo(self, parent, titulo, columna):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=columna, sticky="ew", padx=5)
        ctk.CTkLabel(frame, text=titulo).pack(anchor="w")
        combo = ctk.CTkComboBox(
            frame,
            values=[self.TODOS],
            state="readonly",
            command=lambda _valor: self.aplicar_filtros()
        )
        combo.pack(fill="x")
        combo.set(self.TODOS)
        return combo

    def crear_card(self, parent, titulo, columna):
        frame = ctk.CTkFrame(parent, fg_color=PALETA["panel_alt"])
        frame.grid(row=0, column=columna, padx=8, pady=10, sticky="ew")
        ctk.CTkLabel(
            frame,
            text=titulo,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETA["texto_suave"]
        ).pack(pady=(10, 2))
        valor = ctk.CTkLabel(
            frame,
            text="0",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETA["primario"]
        )
        valor.pack(pady=(0, 10))
        return valor

    def iniciar_carga(self):
        self._carga_id += 1
        carga_id = self._carga_id
        self.label_estado.configure(
            text=self.TEXTO_CARGANDO,
            text_color=color_estado("cargando")
        )
        threading.Thread(
            target=self._cargar_pesado,
            args=(carga_id,),
            daemon=True
        ).start()

    def _cargar_pesado(self, carga_id):
        entregas = self.db.obtener_registro_entregas_epp()
        try:
            ejecutar_en_ui(
                self,
                self._actualizar_datos,
                entregas,
                carga_id
            )
        except Exception:
            pass

    def _actualizar_datos(self, entregas, carga_id):
        if carga_id != self._carga_id:
            return

        self.entregas = list(entregas or [])
        self.actualizar_opciones_filtros()
        self.aplicar_filtros()

    def actualizar_opciones_filtros(self):
        selecciones = {
            "trabajador": self.combo_trabajador.get(),
            "epp": self.combo_epp.get(),
            "proyecto": self.combo_proyecto.get(),
        }
        opciones = {
            "trabajador": sorted({
                e.get("trabajador") or "Sin responsable"
                for e in self.entregas
            }, key=self.normalizar),
            "epp": sorted({
                e.get(self.CLAVE_ELEMENTO) or self.ELEMENTO_DESCONOCIDO
                for e in self.entregas
            }, key=self.normalizar),
            "proyecto": sorted({
                e.get("proyecto") or "-"
                for e in self.entregas
            }, key=self.normalizar),
        }

        for nombre, combo in (
            ("trabajador", self.combo_trabajador),
            ("epp", self.combo_epp),
            ("proyecto", self.combo_proyecto),
        ):
            valores = [self.TODOS] + opciones[nombre]
            combo.configure(values=valores)
            combo.set(
                selecciones[nombre]
                if selecciones[nombre] in valores
                else self.TODOS
            )

    def aplicar_filtros(self, _evento=None):
        desde = self.entry_desde.get().strip()
        hasta = self.entry_hasta.get().strip()
        try:
            filtradas = self.filtrar_entregas(
                self.entregas,
                texto=self.entry_busqueda.get(),
                trabajador=self.combo_trabajador.get(),
                epp=self.combo_epp.get(),
                proyecto=self.combo_proyecto.get(),
                desde=desde,
                hasta=hasta,
            )
        except ValueError as error:
            self.label_estado.configure(
                text=str(error),
                text_color=color_estado("error")
            )
            return

        for item in self.tabla.get_children():
            self.tabla.delete(item)

        for indice, entrega in enumerate(filtradas):
            self.tabla.insert(
                "",
                "end",
                values=(
                    entrega.get("fecha", "-"),
                    entrega.get("trabajador", "Sin responsable"),
                    entrega.get("rut", "-"),
                    entrega.get(
                        self.CLAVE_ELEMENTO,
                        self.ELEMENTO_DESCONOCIDO
                    ),
                    entrega.get("cantidad", 0),
                    entrega.get("proyecto", "-"),
                    entrega.get("entregado_por", "-"),
                    entrega.get("comentario", "-"),
                ),
                tags=("par" if indice % 2 == 0 else "impar",)
            )

        self.card_entregas.configure(text=str(len(filtradas)))
        self.card_unidades.configure(
            text=str(sum(int(e.get("cantidad") or 0) for e in filtradas))
        )
        trabajadores = {
            e.get("trabajador")
            for e in filtradas
            if e.get("trabajador") not in (None, "", "Sin responsable")
        }
        self.card_trabajadores.configure(text=str(len(trabajadores)))
        self.label_estado.configure(
            text=f"{len(filtradas)} entregas mostradas.",
            text_color=color_estado("ok")
        )

    def limpiar_filtros(self):
        self.entry_busqueda.delete(0, "end")
        self.entry_desde.delete(0, "end")
        self.entry_hasta.delete(0, "end")
        self.combo_trabajador.set(self.TODOS)
        self.combo_epp.set(self.TODOS)
        self.combo_proyecto.set(self.TODOS)
        self.aplicar_filtros()

    @classmethod
    def filtrar_entregas(
        cls,
        entregas,
        texto="",
        trabajador=TODOS,
        epp=TODOS,
        proyecto=TODOS,
        desde="",
        hasta="",
    ):
        fecha_desde = cls.validar_fecha(desde, "desde")
        fecha_hasta = cls.validar_fecha(hasta, "hasta")
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise ValueError("La fecha desde no puede ser posterior a la fecha hasta.")

        palabras = cls.normalizar(texto).split()
        resultado = []
        for entrega in entregas:
            if (
                trabajador != cls.TODOS
                and entrega.get("trabajador") != trabajador
            ):
                continue
            if (
                epp != cls.TODOS
                and entrega.get(cls.CLAVE_ELEMENTO) != epp
            ):
                continue
            if proyecto != cls.TODOS and entrega.get("proyecto") != proyecto:
                continue

            fecha_entrega = cls.fecha_de_entrega(entrega)
            if fecha_desde and (not fecha_entrega or fecha_entrega < fecha_desde):
                continue
            if fecha_hasta and (not fecha_entrega or fecha_entrega > fecha_hasta):
                continue

            buscable = cls.normalizar(" ".join(str(entrega.get(campo) or "") for campo in (
                "trabajador",
                "rut",
                cls.CLAVE_ELEMENTO,
                "proyecto",
                "entregado_por",
                "comentario",
                "fecha",
            )))
            if palabras and not all(palabra in buscable for palabra in palabras):
                continue

            resultado.append(entrega)

        return resultado

    @staticmethod
    def normalizar(valor):
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        return "".join(
            caracter for caracter in texto
            if not unicodedata.combining(caracter)
        ).casefold().strip()

    @staticmethod
    def validar_fecha(valor, nombre):
        if not valor:
            return None
        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except ValueError as error:
            raise ValueError(
                f"La fecha {nombre} debe usar el formato AAAA-MM-DD."
            ) from error

    @staticmethod
    def fecha_de_entrega(entrega):
        if entrega.get("fecha_hora"):
            fecha = fecha_hora_local(entrega["fecha_hora"])
            return fecha.date() if fecha is not None else None

        # "fecha" ya es el texto local presentado en pantalla, no otro UTC.
        fecha = str(entrega.get("fecha") or "")[:10]
        try:
            return datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            return None
