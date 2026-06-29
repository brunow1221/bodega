# utils/barcode_utils.py
import os
import re
import shutil
import qrcode

from barcode import Code128
from barcode.writer import ImageWriter

import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from . import obtener_directorios_app


class BarcodeGenerator:
    def __init__(self, base_dir=None):
        """
        Guarda códigos de barras y QR en Documentos/SistemaBodega,
        para que funcione bien tanto en Python normal como en .exe instalado.
        """
        self.products_dir, self.workers_dir = obtener_directorios_app()
        self._asegurar_directorios()

    def _asegurar_directorios(self):
        os.makedirs(self.products_dir, exist_ok=True)
        os.makedirs(self.workers_dir, exist_ok=True)

    def _limpiar_nombre(self, texto):
        limpio = re.sub(r'[\\/*?:"<>|]', "_", str(texto))
        limpio = limpio.replace(" ", "_")
        return limpio

    def obtener_ruta_codigo_barras(self, codigo, nombre):
        nombre_archivo = f"{codigo}_{self._limpiar_nombre(nombre)}.png"
        return os.path.join(self.products_dir, nombre_archivo)

    def obtener_ruta_qr_trabajador(self, rut, nombre):
        nombre_archivo = f"{rut}_{self._limpiar_nombre(nombre)}.png"
        return os.path.join(self.workers_dir, nombre_archivo)

    def generar_codigo_barras(self, codigo, nombre, mostrar_error=True):
        """
        Genera código de barras en:
        Documentos/SistemaBodega/Codigos_Barras
        """
        try:
            self._asegurar_directorios()

            codigo = str(codigo).strip()
            nombre = str(nombre).strip()

            if not codigo:
                if mostrar_error:
                    messagebox.showerror("Error", "El código del producto está vacío.")
                return False

            nombre_archivo_sin_extension = f"{codigo}_{self._limpiar_nombre(nombre)}"
            ruta_sin_extension = os.path.join(self.products_dir, nombre_archivo_sin_extension)
            ruta_final = ruta_sin_extension + ".png"

            imagen = Code128(codigo, writer=ImageWriter())

            imagen.save(
                ruta_sin_extension,
                options={
                    "write_text": True,
                    "module_height": 15.0,
                    "module_width": 0.3,
                    "quiet_zone": 6.5,
                    "font_size": 10,
                    "text_distance": 5.0
                }
            )

            return os.path.exists(ruta_final)

        except Exception as e:
            if mostrar_error:
                messagebox.showerror(
                    "Error al generar código de barras",
                    f"No se pudo generar el código de barras.\n\n"
                    f"Error:\n{e}\n\n"
                    f"Carpeta destino:\n{self.products_dir}"
                )
            else:
                print(f"Error al generar código de barras: {e}")

            return False

    def generar_qr_trabajador(self, rut, nombre, mostrar_error=True):
        """
        Genera QR en:
        Documentos/SistemaBodega/Codigos_QR
        """
        try:
            self._asegurar_directorios()

            rut = str(rut).strip()
            nombre = str(nombre).strip()

            if not rut:
                if mostrar_error:
                    messagebox.showerror("Error", "El RUT del trabajador está vacío.")
                return False

            ruta_completa = self.obtener_ruta_qr_trabajador(rut, nombre)

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(rut)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            img.save(ruta_completa)

            return os.path.exists(ruta_completa)

        except Exception as e:
            if mostrar_error:
                messagebox.showerror(
                    "Error al generar QR",
                    f"No se pudo generar el QR.\n\n"
                    f"Error:\n{e}\n\n"
                    f"Carpeta destino:\n{self.workers_dir}"
                )
            else:
                print(f"Error al generar QR: {e}")

            return False

    def verificar_y_generar_faltantes(self, productos, trabajadores):
        """
        Revisa si faltan códigos de barras o QR en Documentos.
        Si faltan, los genera automáticamente.
        """
        self._asegurar_directorios()

        barras_creadas = 0
        qr_creados = 0
        errores = 0

        productos_revisados = 0
        trabajadores_revisados = 0

        for p in productos:
            codigo = p.get("codigo_barras")
            nombre = p.get("nombre")

            if not codigo or not nombre:
                continue

            productos_revisados += 1
            ruta = self.obtener_ruta_codigo_barras(codigo, nombre)

            if not os.path.exists(ruta):
                creado = self.generar_codigo_barras(codigo, nombre, mostrar_error=False)

                if creado:
                    barras_creadas += 1
                else:
                    errores += 1

        for t in trabajadores:
            rut = t.get("rut")
            nombre = t.get("nombre")

            if not rut or not nombre:
                continue

            trabajadores_revisados += 1
            ruta = self.obtener_ruta_qr_trabajador(rut, nombre)

            if not os.path.exists(ruta):
                creado = self.generar_qr_trabajador(rut, nombre, mostrar_error=False)

                if creado:
                    qr_creados += 1
                else:
                    errores += 1

        return {
            "productos_revisados": productos_revisados,
            "barras_creadas": barras_creadas,
            "trabajadores_revisados": trabajadores_revisados,
            "qr_creados": qr_creados,
            "errores": errores
        }

    def exportar_archivo(self, ruta_origen, nombre_sugerido, ventana=None):
        destino = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=nombre_sugerido,
            title="Exportar Imagen",
            filetypes=[("PNG files", "*.png")]
        )

        if destino:
            try:
                shutil.copy(ruta_origen, destino)
                messagebox.showinfo("Éxito", "Archivo exportado correctamente.", parent=ventana)
                return True
            except Exception as e:
                messagebox.showerror("Error", f"Fallo al copiar: {e}", parent=ventana)

        return False