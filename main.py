import customtkinter as ctk
import os
import tkinter as tk
import traceback
from tkinter import TclError, ttk, messagebox

from config import (
    KEY_SUPABASE,
    URL_SUPABASE,
    VERIFICAR_ACTUALIZACIONES,
    VERSION_APP,
)
from views.tab_consumo_proyecto import ConsumoProyectoTab
from views.tab_mapa_bodega import MapaBodegaTab
from database.db_manager import DatabaseManager
from views.tab_salidas import SalidasTab
from views.tab_inventario import InventarioTab
from views.tab_terreno import TerrenoTab
from views.tab_trabajadores import TrabajadoresTab
from views.tab_proyectos import ProyectosTab
from views.tab_pgp import PgpTab
from views.tab_registro_epp import RegistroEppTab
from views.tab_herramientas_personales import HerramientasPersonalesTab
from views.tab_estadisticas import EstadisticasTab
from utils import obtener_ruta_icono
from utils.ui_zoom import (
    PASO_ZOOM,
    ZOOM_PREDETERMINADO,
    cargar_tema,
    cargar_zoom,
    guardar_tema,
    guardar_zoom,
    normalizar_zoom,
)
from utils.ui_theme import (
    PALETA,
    aplicar_tema_base,
    color_actual,
    configurar_treeview_global,
    estilos_barra,
    estilos_boton,
    estilos_panel,
    estilizar_treeview,
)
from utils.ui_windows import (
    VentanaAdaptable,
    area_disponible,
    dimensiones_ventana_principal,
)


class AplicacionBodega(ctk.CTk):
    def __init__(self):
        tema_inicial = cargar_tema()
        aplicar_tema_base(tema_inicial)
        super().__init__()

        self.usuario_actual = None
        self.rol_actual = None
        self.tema_actual = tema_inicial
        self.zoom_porcentaje = cargar_zoom()
        self.aplicar_zoom(self.zoom_porcentaje, guardar=False)

        self.title("Sistema de Gestión de Bodega")
        self.configurar_tamano_inicial()
        self.configure(fg_color=PALETA["fondo"])

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
                "Migración de sectores pendiente",
                "Para usar sectores con numeración física de estantes debe "
                "ejecutar las migraciones hasta "
                "database/migrations/005_racks_solo_niveles.sql en Supabase."
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
        configurar_treeview_global(
            estilo,
            escala=self.zoom_porcentaje / 100
        )

    # ============================================================
    # LOGIN
    # ============================================================
    def mostrar_login(self):
        login = VentanaAdaptable(self)
        login.title("Iniciar Sesión")
        login.geometry("420x360")
        login.resizable(False, False)
        login.grab_set()
        login.configure(fg_color=PALETA["fondo"])

        ruta_icono = obtener_ruta_icono("icono.ico")
        if os.path.exists(ruta_icono):
            login.after(200, lambda: login.iconbitmap(ruta_icono))

        login.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion_desde_login)

        self.centrar_ventana(login, 420, 360)

        frame = ctk.CTkFrame(login, **estilos_panel())
        frame.pack(fill="both", expand=True, padx=25, pady=25)

        ctk.CTkLabel(
            frame,
            text="Sistema de Gestión de Bodega",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETA["primario"]
        ).pack(pady=(25, 5))

        ctk.CTkLabel(
            frame,
            text="Ingrese sus credenciales para continuar",
            text_color=PALETA["texto_suave"]
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
            text_color=PALETA["peligro"],
            font=ctk.CTkFont(size=12)
        )
        label_error.pack(pady=(5, 0))

        def validar_login(event=None):
            usuario = entry_usuario.get().strip()
            clave = entry_clave.get().strip()

            if not usuario or not clave:
                label_error.configure(text="Debe ingresar usuario y contraseña.")
                return

            datos_usuario = self.db.login_usuario_app_con_logs(usuario, clave)

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
            **estilos_boton("primario"),
            command=validar_login
        ).pack(pady=(20, 10))

        ctk.CTkButton(
            frame,
            text="Salir",
            height=34,
            width=280,
            **estilos_boton("secundario"),
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

        self.frame_superior = ctk.CTkFrame(self, **estilos_barra())
        self.frame_superior.pack(fill="x", padx=20, pady=(12, 0))
        self.frame_superior.grid_columnconfigure(0, weight=1)

        self.label_sesion = ctk.CTkLabel(
            self.frame_superior,
            text=f"Usuario: {nombre}  |  Rol: {rol}  |  Versión: {VERSION_APP}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETA["texto_suave"]
        )
        self.label_sesion.grid(
            row=0, column=0, sticky="w", padx=14, pady=10
        )

        self.frame_controles = ctk.CTkFrame(
            self.frame_superior,
            fg_color="transparent",
        )
        self.frame_controles.grid(
            row=0, column=1, sticky="e", padx=(4, 8), pady=4
        )

        self.boton_estadisticas = ctk.CTkButton(
            self.frame_controles,
            text="Ver estadísticas",
            width=125,
            **estilos_boton("fantasma"),
            command=self.abrir_estadisticas,
        )
        self.boton_estadisticas.pack(side="right", padx=4, pady=2)

        self.boton_tema = ctk.CTkButton(
            self.frame_controles,
            text=self.texto_boton_tema(),
            width=118,
            **estilos_boton("fantasma"),
            command=self.alternar_tema,
        )
        self.boton_tema.pack(side="right", padx=4, pady=2)

        frame_zoom = ctk.CTkFrame(
            self.frame_controles,
            fg_color="transparent"
        )
        frame_zoom.pack(side="right", padx=6, pady=2)

        ctk.CTkLabel(
            frame_zoom,
            text="Zoom:",
            text_color=PALETA["texto_suave"]
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            frame_zoom,
            text="−",
            width=34,
            height=30,
            font=ctk.CTkFont(size=16, weight="bold"),
            **estilos_boton("fantasma"),
            command=self.disminuir_zoom
        ).pack(side="left", padx=2)

        self.boton_zoom_actual = ctk.CTkButton(
            frame_zoom,
            text=f"{self.zoom_porcentaje}%",
            width=62,
            height=30,
            **estilos_boton("fantasma"),
            command=self.restablecer_zoom
        )
        self.boton_zoom_actual.pack(side="left", padx=2)

        ctk.CTkButton(
            frame_zoom,
            text="+",
            width=34,
            height=30,
            font=ctk.CTkFont(size=16, weight="bold"),
            **estilos_boton("fantasma"),
            command=self.aumentar_zoom
        ).pack(side="left", padx=2)

        self._barra_compacta = None
        self.frame_superior.bind(
            "<Configure>", self.adaptar_barra_superior, add="+"
        )
        self.configurar_atajos_zoom()

        self.tabview = ctk.CTkTabview(
            self,
            fg_color=PALETA["panel"],
            segmented_button_fg_color=PALETA["primario_suave"],
            segmented_button_selected_color=PALETA["primario"],
            segmented_button_selected_hover_color=PALETA["primario_hover"],
            segmented_button_unselected_color=PALETA["primario_suave"],
            segmented_button_unselected_hover_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)

        # Administrador y Bodeguero pueden usar todo
        if rol in ["Administrador", "Admin", "Bodeguero"]:
            self.vista_salidas = SalidasTab(
                self.tabview.add("Salidas"),
                self.db
            )
            self.vista_salidas.pack(fill="both", expand=True)

            self.vista_registro_epp = RegistroEppTab(
                self.tabview.add("EPP"),
                self.db
            )
            self.vista_registro_epp.pack(fill="both", expand=True)
            self.vista_salidas.on_epp_registrado = (
                self.vista_registro_epp.iniciar_carga
            )

            self.vista_herramientas_personales = HerramientasPersonalesTab(
                self.tabview.add("Herr. pers."),
                self.db
            )
            self.vista_herramientas_personales.pack(fill="both", expand=True)
            self.vista_salidas.on_herramienta_personal_registrada = (
                self.vista_herramientas_personales.iniciar_carga
            )

            self.crear_pestanas_inventario()

            self.vista_mapa_bodega = MapaBodegaTab(
                self.tabview.add("Sectores"),
                self.db
            )
            self.vista_mapa_bodega.pack(fill="both", expand=True)

            self.vista_terreno = TerrenoTab(
                self.tabview.add("Terreno"),
                self.db
            )
            self.vista_terreno.pack(fill="both", expand=True)

            self.vista_trabajadores = TrabajadoresTab(
                self.tabview.add("Personal"),
                self.db
            )
            self.vista_trabajadores.pack(fill="both", expand=True)

            self.vista_proyectos = ProyectosTab(
                self.tabview.add("Proyectos"),
                self.db
            )
            self.vista_proyectos.pack(fill="both", expand=True)

            self.vista_consumo_proyecto = ConsumoProyectoTab(
                self.tabview.add("Consumo"),
                self.db
            )
            self.vista_consumo_proyecto.pack(fill="both", expand=True)

            self.vista_pgp = PgpTab(
                self.tabview.add("PGP"),
                self.db
            )
            self.vista_pgp.pack(fill="both", expand=True)

        # Consulta solo puede ver inventario y terreno
        elif rol == "Consulta":
            self.crear_pestanas_inventario()

            self.vista_terreno = TerrenoTab(
                self.tabview.add("Terreno"),
                self.db
            )
            self.vista_terreno.pack(fill="both", expand=True)

        # Si por error viene un rol no reconocido, se deja como consulta
        else:
            self.crear_pestanas_inventario()

            self.vista_terreno = TerrenoTab(
                self.tabview.add("Terreno"),
                self.db
            )
            self.vista_terreno.pack(fill="both", expand=True)

    def crear_pestanas_inventario(self):
        contenedor = self.tabview.add("Stock")
        self.tabview_inventarios = ctk.CTkTabview(
            contenedor,
            fg_color=PALETA["panel"],
            segmented_button_fg_color=PALETA["primario_suave"],
            segmented_button_selected_color=PALETA["primario"],
            segmented_button_selected_hover_color=PALETA["primario_hover"],
            segmented_button_unselected_color=PALETA["primario_suave"],
            segmented_button_unselected_hover_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self.tabview_inventarios.pack(fill="both", expand=True)

        self.vista_inventario = InventarioTab(
            self.tabview_inventarios.add("General"), self.db
        )
        self.vista_cafeteria = InventarioTab(
            self.tabview_inventarios.add("Cafetería"),
            self.db,
            solo_cafeteria=True,
        )
        self.vista_aseo = InventarioTab(
            self.tabview_inventarios.add("Aseo"),
            self.db,
            solo_aseo=True,
        )
        self.vista_libreria = InventarioTab(
            self.tabview_inventarios.add("Librería"),
            self.db,
            solo_libreria=True,
        )
        for vista in (
            self.vista_inventario,
            self.vista_cafeteria,
            self.vista_aseo,
            self.vista_libreria,
        ):
            vista.pack(fill="both", expand=True)

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
            "Importar precios Excel",
            "Registrar Movimiento",
            "Registrar y despachar PGP",
            "Agregar artículos al PGP",
            "Registrar devolución",
            "+ Nuevo Proyecto",
            "Inactivar",
            "Finalizar",
            "Reactivar",
            "+ Nuevo Trabajador",
            "Administrar sectores"
        ]

        for nombre_vista in (
            "vista_inventario",
            "vista_cafeteria",
            "vista_aseo",
            "vista_libreria",
            "vista_salidas",
            "vista_mapa_bodega",
            "vista_trabajadores",
            "vista_proyectos",
            "vista_pgp"
        ):
            vista = getattr(self, nombre_vista, None)
            if vista is not None:
                self.deshabilitar_botones_por_texto(
                    vista,
                    botones_bloqueados
                )

        if rol == "Consulta":
            for nombre_vista in (
                "vista_inventario",
                "vista_cafeteria",
                "vista_aseo",
                "vista_libreria"
            ):
                vista = getattr(self, nombre_vista, None)
                if vista is not None:
                    self.deshabilitar_botones_por_texto(
                        vista,
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
                            fg_color=PALETA["borde"],
                            hover_color=PALETA["borde"],
                            text_color=PALETA["texto_suave"]
                        )

                self.deshabilitar_botones_por_texto(widget, textos_bloqueados)

            except Exception:
                pass

    # ============================================================
    # VENTANA / ACTUALIZACIÓN
    # ============================================================
    def abrir_estadisticas(self):
        ventana = getattr(self, "ventana_estadisticas", None)
        try:
            if ventana is not None and ventana.winfo_exists():
                ventana.deiconify()
                ventana.lift()
                ventana.focus_force()
                return
        except TclError:
            pass

        ventana = ctk.CTkToplevel(self)
        self.ventana_estadisticas = ventana
        ventana.title("Estadísticas de artículos y proyectos")
        ventana.geometry("1180x780")
        ventana.minsize(920, 620)
        ventana.configure(fg_color=PALETA["fondo"])
        ventana.after(80, self.maximizar_ventana_estadisticas)
        try:
            ruta_icono = obtener_ruta_icono("icono.ico")
            if os.path.exists(ruta_icono):
                ventana.after(150, lambda: ventana.iconbitmap(ruta_icono))
        except Exception:
            pass

        self.vista_estadisticas = EstadisticasTab(
            ventana,
            self.db,
            escala_zoom=self.zoom_porcentaje / 100,
        )
        self.vista_estadisticas.pack(fill="both", expand=True)

        def cerrar():
            try:
                ventana.destroy()
            finally:
                self.ventana_estadisticas = None
                self.vista_estadisticas = None

        ventana.protocol("WM_DELETE_WINDOW", cerrar)

    def maximizar_ventana_estadisticas(self):
        ventana = getattr(self, "ventana_estadisticas", None)
        try:
            if ventana is not None and ventana.winfo_exists():
                ventana.state("zoomed")
        except TclError:
            pass

    def configurar_atajos_zoom(self):
        for secuencia in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.bind_all(secuencia, self.aumentar_zoom, add="+")

        for secuencia in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.bind_all(secuencia, self.disminuir_zoom, add="+")

        for secuencia in ("<Control-0>", "<Control-KP_0>"):
            self.bind_all(secuencia, self.restablecer_zoom, add="+")

    def adaptar_barra_superior(self, event):
        ancho = event.width / self.frame_superior._get_widget_scaling()
        compacta = ancho < 1050
        if compacta == self._barra_compacta:
            return
        self._barra_compacta = compacta

        if compacta:
            self.label_sesion.grid_configure(
                row=0, column=0, columnspan=2, sticky="w",
            )
            self.frame_controles.grid_configure(
                row=1, column=0, columnspan=2, sticky="e",
            )
        else:
            self.label_sesion.grid_configure(
                row=0, column=0, columnspan=1, sticky="w",
            )
            self.frame_controles.grid_configure(
                row=0, column=1, columnspan=1, sticky="e",
            )

    def texto_boton_tema(self):
        return "☀ Modo claro" if self.tema_actual == "Dark" else "🌙 Modo oscuro"

    def alternar_tema(self):
        self.tema_actual = "Light" if self.tema_actual == "Dark" else "Dark"
        ctk.set_appearance_mode(self.tema_actual)
        guardar_tema(self.tema_actual)

        if hasattr(self, "boton_tema"):
            self.boton_tema.configure(text=self.texto_boton_tema())

        self.configurar_estilo_tablas()
        self.actualizar_treeviews(self)

        vista_estadisticas = getattr(self, "vista_estadisticas", None)
        try:
            if vista_estadisticas is not None and vista_estadisticas.winfo_exists():
                vista_estadisticas.aplicar_tema()
        except TclError:
            pass

    def actualizar_treeviews(self, widget):
        try:
            if isinstance(widget, ttk.Treeview):
                estilizar_treeview(widget)
            elif isinstance(widget, tk.Listbox):
                widget.configure(
                    background=color_actual(PALETA["panel_alt"]),
                    foreground=color_actual(PALETA["texto"]),
                    selectbackground=color_actual(PALETA["seleccion"]),
                    selectforeground="white",
                )
            for hijo in widget.winfo_children():
                self.actualizar_treeviews(hijo)
        except TclError:
            pass

    def aplicar_zoom(self, porcentaje, guardar=True):
        self.zoom_porcentaje = normalizar_zoom(porcentaje)
        escala = self.zoom_porcentaje / 100

        ctk.set_widget_scaling(escala)
        ctk.set_window_scaling(escala)

        try:
            self.configurar_estilo_tablas()
        except TclError:
            pass

        vista_estadisticas = getattr(self, "vista_estadisticas", None)
        try:
            if vista_estadisticas is not None and vista_estadisticas.winfo_exists():
                vista_estadisticas.aplicar_zoom(escala)
        except TclError:
            pass

        if hasattr(self, "boton_zoom_actual"):
            self.boton_zoom_actual.configure(
                text=f"{self.zoom_porcentaje}%"
            )

        if guardar:
            guardar_zoom(self.zoom_porcentaje)

    def aumentar_zoom(self, event=None):
        self.aplicar_zoom(self.zoom_porcentaje + PASO_ZOOM)
        return "break" if event is not None else None

    def disminuir_zoom(self, event=None):
        self.aplicar_zoom(self.zoom_porcentaje - PASO_ZOOM)
        return "break" if event is not None else None

    def restablecer_zoom(self, event=None):
        self.aplicar_zoom(ZOOM_PREDETERMINADO)
        return "break" if event is not None else None

    def preparar_ventana_principal(self):
        self.configurar_tamano_inicial()

    def configurar_tamano_inicial(self):
        try:
            self.update_idletasks()
            izquierda, arriba, area_ancho, area_alto = area_disponible(self)
            escala = self._get_window_scaling()
            ancho, alto, minimo_ancho, minimo_alto = (
                dimensiones_ventana_principal(
                    area_ancho,
                    area_alto,
                    escala,
                )
            )
            x = izquierda + max(0, int((area_ancho - ancho * escala) / 2))
            y = arriba + max(0, int((area_alto - alto * escala) / 2))
            self.minsize(minimo_ancho, minimo_alto)
            self.geometry(f"{ancho}x{alto}{x:+d}{y:+d}")
        except Exception:
            self.minsize(800, 560)
            self.geometry("1200x800")

    def maximizar_ventana(self):
        try:
            self.state("zoomed")
        except Exception:
            self.configurar_tamano_inicial()

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
    except TclError:
        pass
    except Exception as e:
        traceback.print_exc()
        try:
            messagebox.showerror(
                "Error inesperado",
                f"La aplicación se cerró por un error inesperado:\n\n{e}"
            )
        except Exception:
            pass
