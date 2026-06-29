import customtkinter as ctk
from tkinter import ttk, messagebox
import threading
from datetime import date


class ProyectosTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.crear_interfaz()
        self.after(2500, self.iniciar_carga_hilo)

    def crear_interfaz(self):
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.pack(fill="x", pady=10, padx=10)

        ctk.CTkButton(
            frame_top,
            text="Refrescar",
            command=self.iniciar_carga_hilo
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="+ Nuevo Proyecto",
            fg_color="green",
            hover_color="darkgreen",
            command=self.abrir_formulario_proyecto
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="Editar Seleccionado",
            fg_color="#24608a",
            command=self.abrir_formulario_edicion
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="Inactivar",
            fg_color="#8B0000",
            hover_color="#5C0000",
            command=lambda: self.cambiar_estado_proyecto("Inactivo")
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="Finalizar",
            fg_color="#B8860B",
            hover_color="#8B6508",
            command=lambda: self.cambiar_estado_proyecto("Finalizado")
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top,
            text="Reactivar",
            fg_color="#1f538d",
            hover_color="#163c65",
            command=lambda: self.cambiar_estado_proyecto("Activo")
        ).pack(side="left", padx=5)

        self.label_estado = ctk.CTkLabel(frame_top, text="", text_color="blue")
        self.label_estado.pack(side="left", padx=10)

        frame_tabla = ctk.CTkFrame(self)
        frame_tabla.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ctk.CTkScrollbar(frame_tabla, orientation="vertical")
        scrollbar.pack(side="right", fill="y")

        columnas = (
            "ID",
            "Nombre",
            "OT",
            "Cliente",
            "Estado",
            "Fecha Inicio",
            "Fecha Fin",
            "Descripción"
        )

        columnas_visibles = (
            "Nombre",
            "OT",
            "Cliente",
            "Estado",
            "Fecha Inicio",
            "Fecha Fin",
            "Descripción"
        )

        self.tabla = ttk.Treeview(
            frame_tabla,
            columns=columnas,
            displaycolumns=columnas_visibles,
            show="headings",
            height=15,
            yscrollcommand=scrollbar.set
        )

        scrollbar.configure(command=self.tabla.yview)

        anchos = {
            "Nombre": 220,
            "OT": 120,
            "Cliente": 160,
            "Estado": 100,
            "Fecha Inicio": 100,
            "Fecha Fin": 100,
            "Descripción": 300
        }

        for col in columnas_visibles:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos[col], anchor="center")

        self.tabla.tag_configure("activo", background="#FFFFFF")
        self.tabla.tag_configure("inactivo", background="#D3D3D3", foreground="gray")
        self.tabla.tag_configure("finalizado", background="#FFF2CC", foreground="black")

        self.tabla.pack(side="left", fill="both", expand=True)

    # ============================================================
    # NOTIFICAR CAMBIO A SALIDAS
    # ============================================================
    def notificar_cambio_proyectos(self):
        try:
            app = self.winfo_toplevel()

            if hasattr(app, "vista_salidas"):
                if hasattr(app.vista_salidas, "cargar_proyectos"):
                    app.vista_salidas.cargar_proyectos()
                elif hasattr(app.vista_salidas, "actualizar_proyectos"):
                    app.vista_salidas.actualizar_proyectos()

            if hasattr(app, "vista_consumo_proyecto"):
                if hasattr(app.vista_consumo_proyecto, "actualizar_proyectos"):
                    app.vista_consumo_proyecto.actualizar_proyectos()
                elif hasattr(app.vista_consumo_proyecto, "cargar_proyectos"):
                    app.vista_consumo_proyecto.cargar_proyectos()

        except Exception as e:
            print(f"No se pudo actualizar vistas dependientes de proyectos: {e}")

    # ============================================================
    # CARGA
    # ============================================================
    def iniciar_carga_hilo(self):
        self.label_estado.configure(text="Cargando proyectos...", text_color="orange")

        for item in self.tabla.get_children():
            self.tabla.delete(item)

        threading.Thread(
            target=self.cargar_proyectos_pesado,
            daemon=True
        ).start()

    def cargar_proyectos_pesado(self):
        proyectos = self.db.cargar_proyectos_completo()
        filas = []

        for p in proyectos:
            estado = p.get("estado", "Activo")

            if estado == "Inactivo":
                tag = "inactivo"
            elif estado == "Finalizado":
                tag = "finalizado"
            else:
                tag = "activo"

            filas.append({
                "values": (
                    p.get("id", ""),
                    p.get("nombre", ""),
                    p.get("ot", "") or "-",
                    p.get("cliente", "") or "-",
                    estado,
                    p.get("fecha_inicio", "") or "-",
                    p.get("fecha_fin", "") or "-",
                    p.get("descripcion", "") or "-"
                ),
                "tag": tag
            })

        self.after(0, self.actualizar_tabla, filas)

    def actualizar_tabla(self, filas):
        for f in filas:
            self.tabla.insert(
                "",
                "end",
                values=f["values"],
                tags=(f["tag"],)
            )

        self.label_estado.configure(text=f"{len(filas)} proyectos.", text_color="green")

    # ============================================================
    # NUEVO PROYECTO
    # ============================================================
    def validar_fechas(self, fecha_inicio, fecha_fin):
        inicio = date.fromisoformat(fecha_inicio) if fecha_inicio else None
        fin = date.fromisoformat(fecha_fin) if fecha_fin else None
        if inicio and fin and fin < inicio:
            raise ValueError("La fecha de término no puede ser anterior al inicio.")

    def abrir_formulario_proyecto(self):
        self.ventana_proyecto = ctk.CTkToplevel(self)
        self.ventana_proyecto.title("Nuevo Proyecto")
        self.ventana_proyecto.geometry("450x520")
        self.ventana_proyecto.grab_set()

        ctk.CTkLabel(
            self.ventana_proyecto,
            text="Crear Proyecto",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=15)

        self.entry_nombre = ctk.CTkEntry(
            self.ventana_proyecto,
            placeholder_text="Nombre del proyecto",
            width=350
        )
        self.entry_nombre.pack(pady=6)

        self.entry_ot = ctk.CTkEntry(
            self.ventana_proyecto,
            placeholder_text="OT",
            width=350
        )
        self.entry_ot.pack(pady=6)

        self.entry_cliente = ctk.CTkEntry(
            self.ventana_proyecto,
            placeholder_text="Cliente",
            width=350
        )
        self.entry_cliente.pack(pady=6)

        self.entry_fecha_inicio = ctk.CTkEntry(
            self.ventana_proyecto,
            placeholder_text="Fecha inicio YYYY-MM-DD",
            width=350
        )
        self.entry_fecha_inicio.pack(pady=6)

        self.entry_fecha_fin = ctk.CTkEntry(
            self.ventana_proyecto,
            placeholder_text="Fecha fin YYYY-MM-DD",
            width=350
        )
        self.entry_fecha_fin.pack(pady=6)

        self.entry_descripcion = ctk.CTkEntry(
            self.ventana_proyecto,
            placeholder_text="Descripción",
            width=350
        )
        self.entry_descripcion.pack(pady=6)

        ctk.CTkButton(
            self.ventana_proyecto,
            text="Guardar Proyecto",
            fg_color="green",
            hover_color="darkgreen",
            height=45,
            command=self.guardar_proyecto
        ).pack(pady=20)

    def guardar_proyecto(self):
        nombre = self.entry_nombre.get().strip()
        ot = self.entry_ot.get().strip()
        cliente = self.entry_cliente.get().strip()
        fecha_inicio = self.entry_fecha_inicio.get().strip()
        fecha_fin = self.entry_fecha_fin.get().strip()
        descripcion = self.entry_descripcion.get().strip()

        if not nombre:
            return messagebox.showwarning(
                "Aviso",
                "El nombre del proyecto es obligatorio.",
                parent=self.ventana_proyecto
            )

        try:
            self.validar_fechas(fecha_inicio, fecha_fin)
        except ValueError as e:
            return messagebox.showwarning(
                "Fechas inválidas",
                str(e),
                parent=self.ventana_proyecto
            )

        exito, msg = self.db.crear_proyecto(
            nombre=nombre,
            ot=ot,
            cliente=cliente,
            descripcion=descripcion,
            fecha_inicio=fecha_inicio or None,
            fecha_fin=fecha_fin or None
        )

        if exito:
            messagebox.showinfo("Éxito", msg, parent=self.ventana_proyecto)
            self.ventana_proyecto.destroy()
            self.iniciar_carga_hilo()
            self.notificar_cambio_proyectos()
        else:
            messagebox.showerror("Error", msg, parent=self.ventana_proyecto)

    # ============================================================
    # EDITAR PROYECTO
    # ============================================================
    def abrir_formulario_edicion(self):
        seleccion = self.tabla.selection()

        if not seleccion:
            return messagebox.showwarning("Aviso", "Seleccione un proyecto.")

        item = self.tabla.item(seleccion[0])
        valores = item["values"]

        self.proyecto_editando_id = valores[0]

        self.ventana_editar = ctk.CTkToplevel(self)
        self.ventana_editar.title("Editar Proyecto")
        self.ventana_editar.geometry("450x560")
        self.ventana_editar.grab_set()

        ctk.CTkLabel(
            self.ventana_editar,
            text="Editar Proyecto",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=15)

        self.ed_nombre = ctk.CTkEntry(self.ventana_editar, width=350)
        self.ed_nombre.insert(0, valores[1])
        self.ed_nombre.pack(pady=6)

        self.ed_ot = ctk.CTkEntry(self.ventana_editar, width=350)
        self.ed_ot.insert(0, "" if valores[2] == "-" else valores[2])
        self.ed_ot.pack(pady=6)

        self.ed_cliente = ctk.CTkEntry(self.ventana_editar, width=350)
        self.ed_cliente.insert(0, "" if valores[3] == "-" else valores[3])
        self.ed_cliente.pack(pady=6)

        self.ed_estado = ctk.CTkComboBox(
            self.ventana_editar,
            values=["Activo", "Inactivo", "Finalizado"],
            width=350,
            state="readonly"
        )
        self.ed_estado.set(valores[4])
        self.ed_estado.pack(pady=6)

        self.ed_fecha_inicio = ctk.CTkEntry(self.ventana_editar, width=350)
        self.ed_fecha_inicio.insert(0, "" if valores[5] == "-" else valores[5])
        self.ed_fecha_inicio.pack(pady=6)

        self.ed_fecha_fin = ctk.CTkEntry(self.ventana_editar, width=350)
        self.ed_fecha_fin.insert(0, "" if valores[6] == "-" else valores[6])
        self.ed_fecha_fin.pack(pady=6)

        self.ed_descripcion = ctk.CTkEntry(self.ventana_editar, width=350)
        self.ed_descripcion.insert(0, "" if valores[7] == "-" else valores[7])
        self.ed_descripcion.pack(pady=6)

        ctk.CTkButton(
            self.ventana_editar,
            text="Guardar Cambios",
            fg_color="#24608a",
            height=45,
            command=self.guardar_edicion
        ).pack(pady=20)

    def guardar_edicion(self):
        nombre = self.ed_nombre.get().strip()

        if not nombre:
            return messagebox.showwarning(
                "Aviso",
                "El nombre del proyecto es obligatorio.",
                parent=self.ventana_editar
            )

        fecha_inicio = self.ed_fecha_inicio.get().strip()
        fecha_fin = self.ed_fecha_fin.get().strip()
        try:
            self.validar_fechas(fecha_inicio, fecha_fin)
        except ValueError as e:
            return messagebox.showwarning(
                "Fechas inválidas",
                str(e),
                parent=self.ventana_editar
            )

        datos = {
            "nombre": nombre,
            "ot": self.ed_ot.get().strip(),
            "cliente": self.ed_cliente.get().strip(),
            "estado": self.ed_estado.get(),
            "fecha_inicio": fecha_inicio or None,
            "fecha_fin": fecha_fin or None,
            "descripcion": self.ed_descripcion.get().strip()
        }

        exito, msg = self.db.actualizar_proyecto(
            self.proyecto_editando_id,
            datos
        )

        if exito:
            messagebox.showinfo("Éxito", msg, parent=self.ventana_editar)
            self.ventana_editar.destroy()
            self.iniciar_carga_hilo()
            self.notificar_cambio_proyectos()
        else:
            messagebox.showerror("Error", msg, parent=self.ventana_editar)

    # ============================================================
    # CAMBIAR ESTADO
    # ============================================================
    def cambiar_estado_proyecto(self, nuevo_estado):
        seleccion = self.tabla.selection()

        if not seleccion:
            return messagebox.showwarning("Aviso", "Seleccione un proyecto.")

        item = self.tabla.item(seleccion[0])
        valores = item["values"]

        id_proyecto = valores[0]
        nombre = valores[1]

        if nombre == "Taller Interno" and nuevo_estado != "Activo":
            return messagebox.showwarning(
                "Aviso",
                "El proyecto Taller Interno no puede inactivarse ni finalizarse."
            )

        if messagebox.askyesno(
            "Confirmar",
            f"¿Desea cambiar el estado de '{nombre}' a {nuevo_estado}?"
        ):
            exito, msg = self.db.actualizar_proyecto(
                id_proyecto,
                {"estado": nuevo_estado}
            )

            if exito:
                messagebox.showinfo("Éxito", msg)
                self.iniciar_carga_hilo()
                self.notificar_cambio_proyectos()
            else:
                messagebox.showerror("Error", msg)
