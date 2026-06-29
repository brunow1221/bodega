import customtkinter as ctk
import os
import threading
import traceback
from tkinter import ttk, messagebox

from config import (
    KEY_SUPABASE,
    URL_SUPABASE,
    VERIFICAR_ACTUALIZACIONES,
    VERSION_APP,
)
from views.tab_consumo_proyecto import ConsumoProyectoTab
from views.tab_mapa_bodega import MapaBodegaTab
from database.db_manager import DatabaseManager
from utils.barcode_utils import BarcodeGenerator
from views.tab_salidas import SalidasTab
from views.tab_inventario import InventarioTab
from views.tab_terreno import TerrenoTab
from views.tab_trabajadores import TrabajadoresTab
from views.tab_proyectos import ProyectosTab
from utils import obtener_ruta_icono


ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class AplicacionBodega(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.usuario_actual = None
        self.rol_actual = None

        self.title("Sistema de Gestión de Bodega")
        self.geometry("1200x800")
        self.minsize(1200, 800)

        # Ocultar ventana principal hasta que todo esté listo
        self.withdraw()

        # Ícono global
        ruta_icono = obtener_ruta_icono("icono.ico")
        if os.path.exists(ruta_icono):
            self.iconbitmap(ruta_icono)

        # Estilo tabla
        self.configurar_estilo_tablas()

        if not URL_SUPABASE or not KEY_SUPABASE:
            messagebox.showerror(
                "Configuración incompleta",
                "Faltan SUPABASE_URL y SUPABASE_PUBLISHABLE_KEY.\n\n"
                "Configure esas variables de entorno antes de abrir la aplicación."
            )
            self.destroy()
            return

        # Motores
        self.db = DatabaseManager(URL_SUPABASE, KEY_SUPABASE)

        # Login
        self.mostrar_login()

        # Si cerraron el login sin iniciar sesión, no seguimos
        if not self.usuario_actual:
            return

        # Datos de sesión
        self.rol_actual = self.usuario_actual.get("rol", "Consulta")
        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

        # Cargar motores restantes
        self.barcode = BarcodeGenerator()

        # Revisar códigos de barras y QR faltantes en segundo plano
        self.after(8000, self.iniciar_verificacion_codigos)

        # Cargar interfaz completa mientras la ventana sigue oculta
        self.inicializar_interfaz()

        # Aplicar permisos visuales según rol
        self.aplicar_permisos_por_rol()

        # Forzar cálculo visual antes de mostrar
        self.update_idletasks()

        # Preparar tamaño antes de mostrar para evitar ventana blanca
        self.preparar_ventana_principal()

        # Mostrar ventana principal
        self.deiconify()
        self.lift()
        self.focus_force()

        if (
            self.rol_actual in ["Administrador", "Admin", "Bodeguero"]
            and not self.db.migracion_seguridad_disponible
        ):
            messagebox.showwarning(
                "Migración de seguridad pendiente",
                "La aplicación quedó en modo de solo lectura porque falta aplicar "
                "database/migrations/001_integridad_seguridad.sql en Supabase."
            )
        elif (
            self.rol_actual in ["Administrador", "Admin", "Bodeguero"]
            and hasattr(self, "vista_mapa_bodega")
            and not self.db.migracion_racks_disponible
        ):
            self.vista_mapa_bodega.btn_administrar_racks.configure(
                state="disabled"
            )
            messagebox.showwarning(
                "Migración de racks pendiente",
                "Para crear y editar racks debe ejecutar "
                "database/migrations/002_racks_configurables.sql en Supabase."
            )

        # Maximizar luego de mostrarse
        self.after(100, self.maximizar_ventana)

        # Verificar actualización después de mostrar la app
        if VERIFICAR_ACTUALIZACIONES:
            self.after(400, self.verificar_actualizacion)

    # ============================================================
    # ESTILOS
    # ============================================================
    def configurar_estilo_tablas(self):
        estilo = ttk.Style()
        estilo.theme_use("clam")

        estilo.configure(
            "Treeview",
            background="#ffffff",
            foreground="black",
            rowheight=30,
            fieldbackground="#ffffff",
            bordercolor="#cccccc",
            borderwidth=1
        )

        estilo.configure(
            "Treeview.Heading",
            font=("Arial", 11, "bold"),
            background="#e1e1e1",
            foreground="black",
            relief="solid"
        )

        estilo.map("Treeview", background=[("selected", "#1f538d")])

    # ============================================================
    # LOGIN
    # ============================================================
    def mostrar_login(self):
        login = ctk.CTkToplevel(self)
        login.title("Iniciar Sesión")
        login.geometry("420x360")
        login.resizable(False, False)
        login.grab_set()

        ruta_icono = obtener_ruta_icono("icono.ico")
        if os.path.exists(ruta_icono):
            login.after(200, lambda: login.iconbitmap(ruta_icono))

        login.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion_desde_login)

        self.centrar_ventana(login, 420, 360)

        frame = ctk.CTkFrame(login, corner_radius=15)
        frame.pack(fill="both", expand=True, padx=25, pady=25)

        ctk.CTkLabel(
            frame,
            text="Sistema de Gestión de Bodega",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(25, 5))

        ctk.CTkLabel(
            frame,
            text="Ingrese sus credenciales para continuar",
            text_color="gray"
        ).pack(pady=(0, 20))

        entry_usuario = ctk.CTkEntry(
            frame,
            placeholder_text="Usuario",
            width=280,
            height=40
        )
        entry_usuario.pack(pady=8)

        entry_clave = ctk.CTkEntry(
            frame,
            placeholder_text="Contraseña",
            width=280,
            height=40,
            show="*"
        )
        entry_clave.pack(pady=8)

        label_error = ctk.CTkLabel(
            frame,
            text="",
            text_color="red",
            font=ctk.CTkFont(size=12)
        )
        label_error.pack(pady=(5, 0))

        def validar_login(event=None):
            usuario = entry_usuario.get().strip()
            clave = entry_clave.get().strip()

            if not usuario or not clave:
                label_error.configure(text="Debe ingresar usuario y contraseña.")
                return

            datos_usuario = self.db.login_usuario_app(usuario, clave)

            if datos_usuario:
                self.usuario_actual = datos_usuario

                nombre = datos_usuario.get("nombre", usuario)
                rol = datos_usuario.get("rol", "Sin rol")

                self.title(
                    f"Sistema de Gestión de Bodega - {nombre} ({rol})"
                )

                login.destroy()
            else:
                label_error.configure(text="Usuario o contraseña incorrectos.")
                entry_clave.delete(0, "end")
                entry_clave.focus_set()

        ctk.CTkButton(
            frame,
            text="Ingresar",
            height=42,
            width=280,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=validar_login
        ).pack(pady=(20, 10))

        ctk.CTkButton(
            frame,
            text="Salir",
            height=34,
            width=280,
            fg_color="#555555",
            hover_color="#333333",
            command=self.cerrar_aplicacion_desde_login
        ).pack(pady=(0, 10))

        entry_usuario.bind("<Return>", lambda e: entry_clave.focus_set())
        entry_clave.bind("<Return>", validar_login)

        entry_usuario.focus_set()

        login.wait_window()

    def cerrar_aplicacion_desde_login(self):
        self.usuario_actual = None
        self.destroy()

    def cerrar_aplicacion(self):
        try:
            self.db.cerrar_sesion()
        finally:
            self.destroy()

    def centrar_ventana(self, ventana, ancho, alto):
        ventana.update_idletasks()

        pantalla_ancho = ventana.winfo_screenwidth()
        pantalla_alto = ventana.winfo_screenheight()

        x = int((pantalla_ancho / 2) - (ancho / 2))
        y = int((pantalla_alto / 2) - (alto / 2))

        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

    # ============================================================
    # INTERFAZ PRINCIPAL
    # ============================================================
    def inicializar_interfaz(self):
        nombre = self.usuario_actual.get("nombre", "Usuario")
        rol = self.usuario_actual.get("rol", "Consulta")

        self.frame_superior = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_superior.pack(fill="x", padx=20, pady=(12, 0))

        self.label_sesion = ctk.CTkLabel(
            self.frame_superior,
            text=f"Usuario: {nombre}  |  Rol: {rol}  |  Versión: {VERSION_APP}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray"
        )
        self.label_sesion.pack(side="left")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)

        # Administrador y Bodeguero pueden usar todo
        if rol in ["Administrador", "Admin", "Bodeguero"]:
            self.vista_salidas = SalidasTab(
                self.tabview.add("Registro de Salidas"),
                self.db,
                self.barcode
            )
            self.vista_salidas.pack(fill="both", expand=True)

            self.vista_inventario = InventarioTab(
                self.tabview.add("Inventario General"),
                self.db,
                self.barcode
            )
            self.vista_inventario.pack(fill="both", expand=True)

            self.vista_mapa_bodega = MapaBodegaTab(
                self.tabview.add("Mapa de Bodega"),
                self.db
            )
            self.vista_mapa_bodega.pack(fill="both", expand=True)

            self.vista_terreno = TerrenoTab(
                self.tabview.add("Herramientas en Terreno"),
                self.db
            )
            self.vista_terreno.pack(fill="both", expand=True)

            self.vista_trabajadores = TrabajadoresTab(
                self.tabview.add("Trabajadores"),
                self.db,
                self.barcode
            )
            self.vista_trabajadores.pack(fill="both", expand=True)

            self.vista_proyectos = ProyectosTab(
                self.tabview.add("Proyectos"),
                self.db
            )
            self.vista_proyectos.pack(fill="both", expand=True)

            self.vista_consumo_proyecto = ConsumoProyectoTab(
                self.tabview.add("Consumo por Proyecto"),
                self.db
            )
            self.vista_consumo_proyecto.pack(fill="both", expand=True)

        # Consulta solo puede ver inventario y terreno
        elif rol == "Consulta":
            self.vista_inventario = InventarioTab(
                self.tabview.add("Inventario General"),
                self.db,
                self.barcode
            )
            self.vista_inventario.pack(fill="both", expand=True)

            self.vista_terreno = TerrenoTab(
                self.tabview.add("Herramientas en Terreno"),
                self.db
            )
            self.vista_terreno.pack(fill="both", expand=True)

        # Si por error viene un rol no reconocido, se deja como consulta
        else:
            self.vista_inventario = InventarioTab(
                self.tabview.add("Inventario General"),
                self.db,
                self.barcode
            )
            self.vista_inventario.pack(fill="both", expand=True)

            self.vista_terreno = TerrenoTab(
                self.tabview.add("Herramientas en Terreno"),
                self.db
            )
            self.vista_terreno.pack(fill="both", expand=True)

    # ============================================================
    # PERMISOS POR ROL
    # ============================================================
    def aplicar_permisos_por_rol(self):
        rol = self.rol_actual
        puede_escribir = (
            rol in ["Administrador", "Admin", "Bodeguero"]
            and self.db.migracion_seguridad_disponible
        )

        if puede_escribir:
            return

        botones_bloqueados = [
            "Editar Seleccionado",
            "+ Nuevo Producto",
            "Dar de Baja",
            "Restaurar",
            "Registrar Movimiento",
            "+ Nuevo Proyecto",
            "Inactivar",
            "Finalizar",
            "Reactivar",
            "+ Nuevo Trabajador",
            "Crear 4 subdivisiones",
            "Administrar racks"
        ]

        for nombre_vista in (
            "vista_inventario",
            "vista_salidas",
            "vista_mapa_bodega",
            "vista_trabajadores",
            "vista_proyectos"
        ):
            vista = getattr(self, nombre_vista, None)
            if vista is not None:
                self.deshabilitar_botones_por_texto(
                    vista,
                    botones_bloqueados
                )

        if rol == "Consulta" and hasattr(self, "vista_inventario"):
            self.deshabilitar_botones_por_texto(
                self.vista_inventario,
                ["Exportar a Excel"]
            )

    def deshabilitar_botones_por_texto(self, widget_padre, textos_bloqueados):
        for widget in widget_padre.winfo_children():
            try:
                if isinstance(widget, ctk.CTkButton):
                    texto = widget.cget("text")

                    if texto in textos_bloqueados:
                        widget.configure(
                            state="disabled",
                            fg_color="#777777",
                            hover_color="#777777",
                            text_color="#dddddd"
                        )

                self.deshabilitar_botones_por_texto(widget, textos_bloqueados)

            except Exception:
                pass

    # ============================================================
    # VERIFICACIÓN DE CÓDIGOS LOCALES
    # ============================================================
    def iniciar_verificacion_codigos(self):
        hilo = threading.Thread(
            target=self.verificar_codigos_faltantes,
            daemon=True
        )
        hilo.start()

    def verificar_codigos_faltantes(self):
        try:
            productos = self.db.cargar_inventario_nube()
            trabajadores = self.db.cargar_trabajadores_nube()

            resumen = self.barcode.verificar_y_generar_faltantes(
                productos,
                trabajadores
            )

            print("Verificación de códigos locales completada:")
            print(resumen)

        except Exception as e:
            print(f"Error verificando códigos faltantes: {e}")

    # ============================================================
    # VENTANA / ACTUALIZACIÓN
    # ============================================================
    def preparar_ventana_principal(self):
        try:
            ancho = self.winfo_screenwidth()
            alto = self.winfo_screenheight()
            self.geometry(f"{ancho}x{alto}+0+0")
        except Exception:
            self.geometry("1200x800")

    def maximizar_ventana(self):
        try:
            self.state("zoomed")
        except Exception:
            self.geometry(
                f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0"
            )

    def verificar_actualizacion(self):
        try:
            config_app = self.db.obtener_config_app()

            version_actual = config_app.get("version_actual")
            mensaje = config_app.get(
                "mensaje_update",
                "Hay una nueva versión disponible."
            )
            url_descarga = config_app.get("url_descarga", "pendiente")

            if version_actual and version_actual != VERSION_APP:
                texto = (
                    f"{mensaje}\n\n"
                    f"Versión instalada: {VERSION_APP}\n"
                    f"Versión disponible: {version_actual}\n\n"
                    f"Descarga: {url_descarga}"
                )

                messagebox.showinfo("Actualización disponible", texto)

        except Exception as e:
            print(f"No se pudo verificar actualización: {e}")


if __name__ == "__main__":
    app = AplicacionBodega()

    try:
        if app.winfo_exists():
            app.mainloop()
    except Exception as e:
        traceback.print_exc()
        try:
            messagebox.showerror(
                "Error inesperado",
                f"La aplicación se cerró por un error inesperado:\n\n{e}"
            )
        except Exception:
            pass
