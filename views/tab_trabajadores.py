import customtkinter as ctk
from tkinter import ttk, messagebox
from PIL import Image
import os
import threading


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
    def __init__(self, master, db_manager, barcode_gen):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.barcode = barcode_gen
        self.crear_interfaz()

    def crear_interfaz(self):
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.pack(fill="x", pady=10, padx=10)

        ctk.CTkButton(
            frame_top,
            text="Refrescar Lista",
            command=self.iniciar_carga_hilo
        ).pack(side="left")

        self.label_estado = ctk.CTkLabel(frame_top, text="", text_color="blue")
        self.label_estado.pack(side="left", padx=10)

        ctk.CTkButton(
            frame_top,
            text="Ver Código QR",
            fg_color="#1f538d",
            command=self.ver_qr_trabajador
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            frame_top,
            text="+ Nuevo Trabajador",
            fg_color="green",
            hover_color="darkgreen",
            command=self.abrir_formulario_trabajador
        ).pack(side="right")

        frame_tabla = ctk.CTkFrame(self)
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
        self.label_estado.configure(text="Cargando...", text_color="orange")

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

        self.after(0, self.actualizar_interfaz_tabla, filas)

    def actualizar_interfaz_tabla(self, filas):
        for f in filas:
            self.tabla_trabajadores.insert("", "end", values=f)

        self.label_estado.configure(text=f"{len(filas)} trab.", text_color="green")

    def ver_qr_trabajador(self):
        seleccion = self.tabla_trabajadores.selection()

        if not seleccion:
            return messagebox.showwarning(
                "Aviso",
                "Seleccione un trabajador para ver su QR."
            )

        item = self.tabla_trabajadores.item(seleccion[0])

        rut = str(item["values"][0])
        nombre = str(item["values"][1])

        ruta_imagen = self.barcode.obtener_ruta_qr_trabajador(rut, nombre)

        if not os.path.exists(ruta_imagen):
            respuesta = messagebox.askyesno(
                "QR no encontrado",
                "No se encontró la imagen del QR en este computador.\n\n"
                "¿Desea generarla nuevamente?"
            )

            if respuesta:
                creado = self.barcode.generar_qr_trabajador(rut, nombre)

                if not creado:
                    return messagebox.showerror(
                        "Error",
                        "No se pudo generar el QR del trabajador."
                    )
            else:
                return

        ventana_img = ctk.CTkToplevel(self)
        ventana_img.title(f"QR de {nombre}")
        ventana_img.geometry("400x420")
        ventana_img.grab_set()

        img_pil = Image.open(ruta_imagen)

        img = ctk.CTkImage(
            light_image=img_pil,
            dark_image=img_pil,
            size=(250, 250)
        )

        ctk.CTkLabel(
            ventana_img,
            image=img,
            text=""
        ).pack(pady=20)

        ctk.CTkLabel(
            ventana_img,
            text=f"{nombre}\n{rut}",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(0, 10))

        ctk.CTkButton(
            ventana_img,
            text="Descargar / Imprimir Credencial",
            command=lambda: self.barcode.exportar_archivo(
                ruta_imagen,
                f"{rut}.png",
                ventana_img
            )
        ).pack(pady=10)

    def abrir_formulario_trabajador(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Registrar Trabajador")
        ventana.geometry("400x400")
        ventana.grab_set()

        ctk.CTkLabel(
            ventana,
            text="Nuevo Trabajador",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=15)

        entry_rut = ctk.CTkEntry(
            ventana,
            placeholder_text="RUT (Ej: 12345678-9)",
            width=300
        )
        entry_rut.pack(pady=10)

        entry_nombre = ctk.CTkEntry(
            ventana,
            placeholder_text="Nombre Completo",
            width=300
        )
        entry_nombre.pack(pady=10)

        entry_cargo = ctk.CTkEntry(
            ventana,
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
                qr_creado = self.barcode.generar_qr_trabajador(rut, nombre)

                if qr_creado:
                    messagebox.showinfo(
                        "Éxito",
                        f"{msg}\n\nEl QR fue creado en:\n{self.barcode.workers_dir}",
                        parent=ventana
                    )
                else:
                    messagebox.showwarning(
                        "Trabajador guardado",
                        "El trabajador fue guardado, pero no se pudo crear el QR.",
                        parent=ventana
                    )

                ventana.destroy()
                self.after(3000, self.iniciar_carga_hilo)

            else:
                messagebox.showerror(
                    "Error",
                    f"No se pudo guardar: {msg}",
                    parent=ventana
                )

        ctk.CTkButton(
            ventana,
            text="Guardar",
            fg_color="green",
            hover_color="darkgreen",
            command=guardar
        ).pack(pady=20)