import customtkinter as ctk
from utils.ui_windows import VentanaAdaptable
from tkinter import ttk, messagebox
import threading
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.ui_theme import (
    PALETA,
    color_estado,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)


def validar_rut_chileno(rut):
    rut_limpio = rut.replace(".", "").replace("-", "").strip().upper()

    if len(rut_limpio) < 8 or not rut_limpio[:-1].isdigit():
        return False

    cuerpo = rut_limpio[:-1]
    dv_esperado = rut_limpio[-1]

    suma = 0
    multiplo = 2

    for c in reversed(cuerpo):
        suma += int(c) * multiplo
        multiplo = multiplo + 1 if multiplo < 7 else 2

    dv_calculado = str(11 - (suma % 11))

    if dv_calculado == "11":
        dv_calculado = "0"
    elif dv_calculado == "10":
        dv_calculado = "K"

    return dv_esperado == dv_calculado


class TrabajadoresTab(ctk.CTkFrame):
    def __init__(self, master, db_manager):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        iniciar_despachador_ui(self)
        self.crear_interfaz()

    def crear_interfaz(self):
        self.frame_top = ctk.CTkFrame(self, **estilos_barra())
        self.frame_top.pack(fill="x", pady=10, padx=10)
        fila_acciones = ctk.CTkFrame(self.frame_top, fg_color="transparent")
        fila_acciones.pack(fill="x", padx=12, pady=10)
        fila_acciones.grid_columnconfigure(1, weight=1)

        self.btn_refrescar = ctk.CTkButton(
            fila_acciones,
            text="Refrescar Lista",
            **estilos_boton("primario"),
            command=self.iniciar_carga_hilo
        )
        self.btn_refrescar.grid(row=0, column=0, sticky="w")

        self.label_estado = ctk.CTkLabel(
            fila_acciones,
            text="",
            text_color=color_estado("info"),
            anchor="w",
            justify="left",
        )
        self.label_estado.grid(row=0, column=1, sticky="ew", padx=10)

        self.btn_nuevo_trabajador = ctk.CTkButton(
            fila_acciones,
            text="+ Nuevo Trabajador",
            **estilos_boton("primario"),
            command=self.abrir_formulario_trabajador
        )
        self.btn_nuevo_trabajador.grid(row=0, column=2, sticky="e")

        frame_tabla = ctk.CTkFrame(self, **estilos_panel())
        frame_tabla.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ctk.CTkScrollbar(frame_tabla, orientation="vertical")
        scrollbar.pack(side="right", fill="y")

        columnas = ("RUT", "Nombre", "Cargo/Especialidad", "Estado")

        self.tabla_trabajadores = ttk.Treeview(
            frame_tabla,
            columns=columnas,
            show="headings",
            height=15,
            yscrollcommand=scrollbar.set
        )
        estilizar_treeview(self.tabla_trabajadores)

        scrollbar.configure(command=self.tabla_trabajadores.yview)

        anchos = {
            "RUT": 120,
            "Nombre": 250,
            "Cargo/Especialidad": 200,
            "Estado": 100
        }

        for col in columnas:
            self.tabla_trabajadores.heading(col, text=col)
            self.tabla_trabajadores.column(col, width=anchos[col], anchor="center")

        self.tabla_trabajadores.pack(side="left", fill="both", expand=True)

        self.after(3000, self.iniciar_carga_hilo)

    def iniciar_carga_hilo(self):
        self.label_estado.configure(
            text="Cargando...",
            text_color=color_estado("cargando")
        )

        for item in self.tabla_trabajadores.get_children():
            self.tabla_trabajadores.delete(item)

        threading.Thread(
            target=self.cargar_trabajadores_pesado,
            daemon=True
        ).start()

    def cargar_trabajadores_pesado(self):
        trabajadores = self.db.cargar_trabajadores_nube()

        filas = []

        for t in trabajadores:
            filas.append((
                t.get("rut", ""),
                t.get("nombre", ""),
                t.get("cargo", "") or "-",
                t.get("estado", "Activo")
            ))

        ejecutar_en_ui(self, self.actualizar_interfaz_tabla, filas)

    def actualizar_interfaz_tabla(self, filas):
        for f in filas:
            self.tabla_trabajadores.insert("", "end", values=f)

        self.label_estado.configure(
            text=f"{len(filas)} trab.",
            text_color=color_estado("ok")
        )

    def abrir_formulario_trabajador(self):
        ventana = VentanaAdaptable(self)
        ventana.title("Registrar Trabajador")
        ventana.geometry("400x400")
        ventana.grab_set()
        panel = ctk.CTkScrollableFrame(ventana, fg_color=PALETA["fondo"])
        panel.pack(fill="both", expand=True, padx=10, pady=10)


        ctk.CTkLabel(
            panel,
            text="Nuevo Trabajador",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=15)

        entry_rut = ctk.CTkEntry(
            panel,
            placeholder_text="RUT (Ej: 12345678-9)",
            width=300
        )
        entry_rut.pack(pady=10)

        entry_nombre = ctk.CTkEntry(
            panel,
            placeholder_text="Nombre Completo",
            width=300
        )
        entry_nombre.pack(pady=10)

        entry_cargo = ctk.CTkEntry(
            panel,
            placeholder_text="Cargo (Ej: Soldador, Eléctrico)",
            width=300
        )
        entry_cargo.pack(pady=10)

        def guardar():
            rut = entry_rut.get().strip()
            nombre = entry_nombre.get().strip()
            cargo = entry_cargo.get().strip()

            if not rut or not nombre:
                return messagebox.showwarning(
                    "Advertencia",
                    "El RUT y el Nombre son obligatorios.",
                    parent=ventana
                )

            if not validar_rut_chileno(rut):
                return messagebox.showerror(
                    "Error",
                    "El RUT ingresado no es válido.",
                    parent=ventana
                )

            exito, msg = self.db.guardar_trabajador_nube(rut, nombre, cargo)

            if exito:
                messagebox.showinfo("Éxito", msg, parent=ventana)
                ventana.destroy()
                self.after(3000, self.iniciar_carga_hilo)
                app = self.winfo_toplevel()
                if hasattr(app, "vista_salidas"):
                    app.vista_salidas.iniciar_carga_selectores()

            else:
                messagebox.showerror(
                    "Error",
                    f"No se pudo guardar: {msg}",
                    parent=ventana
                )

        ctk.CTkButton(
            panel,
            text="Guardar",
            **estilos_boton("primario"),
            command=guardar
        ).pack(pady=20)
