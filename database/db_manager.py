import ast
import os
import threading
import time
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from supabase import create_client, Client
from utils.fechas import formatear_fecha_hora, fecha_actual_bodega
from utils.pgp import (
    TIPO_DEVOLUCION_PGP,
    TIPO_PRESTAMO_PGP,
    cantidad_pendiente_item_pgp,
    preparar_items_pgp,
)
from utils.movimientos import TIPO_ENTREGA_HERRAMIENTA_PERSONAL


class DatabaseManager:
    def __init__(self, url, key):
        self.url = url
        self.key = key
        self.supabase: Client = create_client(self.url, self.key)
        self._lock_supabase = threading.RLock()
        self.session_token = None
        self.usuario_actual = None
        self.migracion_seguridad_disponible = False
        self.migracion_racks_disponible = False
        self.debug_login = (
            os.environ.get("DEBUG_LOGIN", "0").strip().lower()
            in {"1", "true", "yes", "si"}
        )
        self._log_db(f"DatabaseManager cargado desde {__file__}")

    def _log_login(self, mensaje):
        if self.debug_login:
            print(f"[LOGIN DEBUG] {mensaje}")

    def _log_db(self, mensaje):
        if os.environ.get("DEBUG_DB", "0").strip().lower() in {"1", "true", "yes", "si"}:
            print(f"[DB DEBUG] {mensaje}")

    def _reiniciar_cliente_supabase(self):
        self.supabase = create_client(self.url, self.key)

    def _mensaje_error(self, error):
        datos = None
        if getattr(error, "args", None):
            datos = error.args[0]
        if isinstance(datos, dict):
            return datos.get("message") or datos.get("details") or str(error)

        texto = str(error)
        try:
            datos = ast.literal_eval(texto)
            if isinstance(datos, dict):
                return datos.get("message") or datos.get("details") or texto
        except Exception:
            pass

        return texto

    def _log_estado_usuario_login(self, usuario):
        if not self.debug_login:
            return

        try:
            res = (
                self.supabase
                .table("usuarios_app")
                .select("id,usuario,nombre,rol,estado,password_hash")
                .eq("usuario", usuario)
                .limit(1)
                .execute()
            )
            filas = res.data or []
            self._log_login(f"usuarios_app filas encontradas: {len(filas)}")

            if not filas:
                return

            fila = filas[0]
            password_hash = fila.get("password_hash") or ""
            self._log_login(
                "usuario encontrado: "
                f"id={fila.get('id')} "
                f"usuario={fila.get('usuario')} "
                f"rol={fila.get('rol')} "
                f"estado={fila.get('estado')} "
                f"hash_presente={bool(password_hash)} "
                f"hash_prefijo={password_hash[:7] if password_hash else '-'} "
                f"hash_largo={len(password_hash)}"
            )
        except Exception as e:
            self._log_login(f"no se pudo leer usuarios_app: {e}")

    def verificar_migracion_racks(self):
        try:
            self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("racks")
                    .select(
                        "id,ancho_cm,alto_cm,profundidad_cm,"
                        "capacidad_kg,posicion_orden"
                    )
                    .limit(1)
                    .execute()
                )
            )
            modo = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("config_app")
                    .select("valor")
                    .eq("clave", "modo_racks")
                    .limit(1)
                    .execute()
                )
            )
            self.migracion_racks_disponible = bool(
                modo.data
                and modo.data[0].get("valor") == "sectores_estantes_v1"
            )
        except Exception:
            self.migracion_racks_disponible = False
        return self.migracion_racks_disponible

    def _ejecutar_con_reintentos(self, operacion, intentos=6):
        ultimo_error = None
        marcadores_transitorios = (
            "timeout",
            "timed out",
            "server disconnected",
            "server disconnect",
            "connection",
            "connection reset",
            "connection aborted",
            "network",
            "temporarily unavailable",
            "remote protocol error",
            "remoteprotocolerror",
            "httpcore",
            "httpx",
            "deadlock detected",
            "40p01",
            "serialization failure",
            "40001",
            "502",
            "503",
            "504"
        )

        for intento in range(intentos):
            try:
                with self._lock_supabase:
                    return operacion()
            except Exception as e:
                ultimo_error = e
                texto = str(e).lower()
                es_transitorio = any(
                    marcador in texto
                    for marcador in marcadores_transitorios
                )
                if not es_transitorio or intento == intentos - 1:
                    raise
                self._log_db(
                    f"error transitorio, reintento {intento + 2}/{intentos}: {e}"
                )
                with self._lock_supabase:
                    self._reiniciar_cliente_supabase()
                time.sleep(min(0.75 * (2 ** intento), 6))

        raise ultimo_error

    def _cargar_tabla_paginada(
        self,
        tabla,
        columnas="*",
        ordenar_por=None,
        desc=False,
        tamano_pagina=1000,
    ):
        """Carga una tabla completa sin depender del límite de PostgREST."""
        filas = []
        inicio = 0

        while True:
            def consultar(inicio_pagina=inicio):
                consulta = self.supabase.table(tabla).select(columnas)
                if ordenar_por:
                    consulta = consulta.order(ordenar_por, desc=desc)
                return consulta.range(
                    inicio_pagina,
                    inicio_pagina + tamano_pagina - 1,
                ).execute()

            respuesta = self._ejecutar_con_reintentos(consultar)
            pagina = list(respuesta.data or [])
            filas.extend(pagina)
            if len(pagina) < tamano_pagina:
                break
            inicio += tamano_pagina

        return filas

    def _requiere_sesion(self):
        if not self.session_token:
            return (
                False,
                "La migración de seguridad no está aplicada o la sesión expiró. "
                "Ejecute database/migrations/001_integridad_seguridad.sql "
                "en Supabase y vuelva a iniciar sesión."
            )
        return True, ""

    def _mutar(self, operacion, datos):
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje, None

        try:
            request_id = str(uuid4())
            res = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "app_mutar_registro",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_operacion": operacion,
                        "p_datos": datos
                    }
                ).execute()
            )
            return True, "Operación realizada correctamente.", res.data
        except Exception as e:
            return False, str(e), None

    # ============================================================
    # LOGIN / AUDITORÍA / CONFIG
    # ============================================================
    def login_usuario_app(self, usuario, password):
        try:
            res = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "iniciar_sesion_app",
                    {
                        "p_usuario": usuario,
                        "p_password": password
                    }
                ).execute()
            )

            datos = res.data
            if isinstance(datos, list):
                datos = datos[0] if datos else None

            if datos:
                self.session_token = datos.get("session_token")
                self.usuario_actual = datos
                self.migracion_seguridad_disponible = bool(self.session_token)
                self.verificar_migracion_racks()
                return datos

            return None

        except Exception as e:
            print(f"Inicio de sesión segura no disponible: {e}")

        try:
            res = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "login_usuario_app",
                    {
                        "p_usuario": usuario,
                        "p_password": password
                    }
                ).execute()
            )

            if res.data and len(res.data) > 0:
                self.usuario_actual = res.data[0]
                self.session_token = None
                self.migracion_seguridad_disponible = False
                self.verificar_migracion_racks()
                return res.data[0]
        except Exception as e:
            print(f"Error en login: {e}")

        return None

    def login_usuario_app_con_logs(self, usuario, password):
        if not self.debug_login:
            return self.login_usuario_app(usuario, password)

        self._log_login(
            f"intentando login usuario='{usuario}' password_largo={len(password)}"
        )
        self._log_estado_usuario_login(usuario)

        try:
            self._log_login("llamando RPC iniciar_sesion_app")
            res = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "iniciar_sesion_app",
                    {
                        "p_usuario": usuario,
                        "p_password": password
                    }
                ).execute()
            )
            datos = res.data
            self._log_login(f"respuesta iniciar_sesion_app: {datos}")

            if isinstance(datos, list):
                datos = datos[0] if datos else None

            if datos:
                self.session_token = datos.get("session_token")
                self.usuario_actual = datos
                self.migracion_seguridad_disponible = bool(self.session_token)
                self.verificar_migracion_racks()
                self._log_login(
                    "login seguro OK: "
                    f"usuario={datos.get('usuario')} "
                    f"rol={datos.get('rol')} "
                    f"session_token={bool(self.session_token)}"
                )
                return datos

            self._log_login("iniciar_sesion_app no devolvio usuario")
        except Exception as e:
            print(f"Inicio de sesiÃ³n segura no disponible: {e}")
            self._log_login(f"iniciar_sesion_app fallo: {e}")

        try:
            self._log_login("llamando RPC login_usuario_app")
            res = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "login_usuario_app",
                    {
                        "p_usuario": usuario,
                        "p_password": password
                    }
                ).execute()
            )
            self._log_login(f"respuesta login_usuario_app: {res.data}")

            if res.data and len(res.data) > 0:
                self.usuario_actual = res.data[0]
                self.session_token = None
                self.migracion_seguridad_disponible = False
                self.verificar_migracion_racks()
                self._log_login(
                    "login legacy OK: "
                    f"usuario={res.data[0].get('usuario')} "
                    f"rol={res.data[0].get('rol')}"
                )
                return res.data[0]

            self._log_login("login_usuario_app no devolvio filas")
        except Exception as e:
            print(f"Error en login: {e}")
            self._log_login(f"login_usuario_app fallo: {e}")

        return None

    def cerrar_sesion(self):
        token = self.session_token
        self.session_token = None
        self.usuario_actual = None

        if not token:
            return

        try:
            self.supabase.rpc(
                "cerrar_sesion_app",
                {"p_token": token}
            ).execute()
        except Exception as e:
            print(f"No se pudo cerrar la sesión remota: {e}")

    def registrar_auditoria(
        self,
        modulo,
        accion,
        detalle="",
        datos=None,
        usuario_app=None
    ):
        usuario = self.usuario_actual or {}
        nombre_usuario = usuario_app or (
            f"{usuario.get('nombre', 'Usuario')} "
            f"({usuario.get('usuario', 'sin usuario')})"
        )
        payload = dict(datos or {})
        payload.update({
            "_modulo": modulo,
            "_accion": accion,
            "_detalle": detalle,
            "usuario_app": nombre_usuario
        })
        exito, mensaje, _ = self._mutar("registrar_auditoria", payload)
        if not exito:
            print(f"Error registrando auditoría: {mensaje}")
        return exito

    def obtener_config_app(self):
        try:
            res = self._ejecutar_con_reintentos(
                lambda: self.supabase.table("config_app").select("*").execute()
            )

            return {
                item["clave"]: item["valor"]
                for item in res.data
            }

        except Exception as e:
            print(f"Error obteniendo configuración de app: {e}")
            return {}

    # ============================================================
    # BODEGAS / RACKS / UBICACIONES
    # ============================================================
    def cargar_bodegas(self):
        try:
            res = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("bodegas")
                    .select("*")
                    .eq("estado", "Activo")
                    .order("nombre")
                    .execute()
                )
            )

            return res.data

        except Exception as e:
            print(f"Error cargando bodegas: {e}")
            return []

    def cargar_racks(self, bodega_id=None, solo_activos=True):
        try:
            def construir_query(con_posicion=True):
                query = self.supabase.table("racks").select("*")
                if bodega_id:
                    query = query.eq("bodega_id", bodega_id)
                if solo_activos:
                    query = query.eq("estado", "Activo")
                if con_posicion:
                    query = query.order("posicion_orden")
                return query.order("codigo_rack")

            try:
                res = self._ejecutar_con_reintentos(
                    lambda: construir_query(con_posicion=True).execute()
                )
            except Exception as e:
                if "posicion_orden" not in str(e):
                    raise
                res = self._ejecutar_con_reintentos(
                    lambda: construir_query(con_posicion=False).execute()
                )
            return res.data

        except Exception as e:
            print(f"Error cargando racks: {e}")
            return []

    def cargar_ubicaciones(self, rack_id=None, solo_activas=True):
        try:
            def construir_query():
                query = (
                    self.supabase
                    .table("ubicaciones")
                    .select("*")
                    .order("codigo_ubicacion")
                )

                if rack_id:
                    query = query.eq("rack_id", rack_id)

                if solo_activas:
                    query = query.eq("estado", "Activo")

                return query

            res = self._ejecutar_con_reintentos(
                lambda: construir_query().execute()
            )
            return res.data

        except Exception as e:
            print(f"Error cargando ubicaciones: {e}")
            return []

    def cargar_ubicaciones_lista(self):
        """
        Devuelve lista simple para combos.
        """
        try:
            res = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("ubicaciones")
                    .select("id, codigo_ubicacion, tipo, estado")
                    .eq("estado", "Activo")
                    .order("codigo_ubicacion")
                    .execute()
                )
            )

            return res.data

        except Exception as e:
            print(f"Error cargando lista de ubicaciones: {e}")
            return []

    def obtener_ubicacion_por_codigo(self, codigo_ubicacion):
        try:
            res = (
                self.supabase
                .table("ubicaciones")
                .select("*")
                .eq("codigo_ubicacion", codigo_ubicacion)
                .execute()
            )

            return res.data[0] if res.data else None

        except Exception as e:
            print(f"Error buscando ubicación: {e}")
            return None

    def gestionar_rack(self, accion, datos):
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje

        try:
            payload = dict(datos)
            if accion in {"crear", "actualizar"}:
                payload["columnas"] = max(
                    1,
                    int(payload.get("columnas") or 2)
                )
            request_id = str(uuid4())
            self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "gestionar_rack_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_accion": accion,
                        "p_datos": payload
                    }
                ).execute()
            )
            return True, "Sector actualizado correctamente."
        except Exception as e:
            mensaje_error = self._mensaje_error(e)
            if "debe ser a o b" in mensaje_error.lower():
                mensaje_error = (
                    "Falta ejecutar la migración 010 de bodegas y sectores "
                    "múltiples en Supabase."
                )
            return False, mensaje_error

    def crear_rack(
        self,
        bodega_id,
        codigo_rack,
        nombre="",
        descripcion="",
        niveles=5,
        columnas=2,
        ancho_cm=None,
        alto_cm=None,
        profundidad_cm=None,
        capacidad_kg=None,
        posicion_orden=None
    ):
        data = {
            "bodega_id": bodega_id,
            "codigo_rack": codigo_rack,
            "nombre": nombre or codigo_rack,
            "descripcion": descripcion,
            "niveles": niveles,
            # Compatibilidad interna: niveles = estantes por módulo y
            # columnas = módulos físicos del sector.
            "columnas": columnas,
            "ancho_cm": ancho_cm,
            "alto_cm": alto_cm,
            "profundidad_cm": profundidad_cm,
            "capacidad_kg": capacidad_kg,
            "posicion_orden": posicion_orden
        }
        exito, mensaje = self.gestionar_rack("crear", data)
        if exito:
            return True, "Sector creado correctamente."
        return False, mensaje

    def actualizar_rack(self, rack_id, datos):
        payload = dict(datos)
        payload["id"] = rack_id
        return self.gestionar_rack("actualizar", payload)

    def retirar_rack(self, rack_id):
        return self.gestionar_rack("retirar", {"id": rack_id})

    def reactivar_rack(self, rack_id):
        return self.gestionar_rack("reactivar", {"id": rack_id})

    def crear_ubicacion(
        self,
        bodega_id,
        rack_id,
        codigo_ubicacion,
        tipo,
        nivel,
        columna,
        subdivision=None,
        ubicacion_padre_id=None,
        descripcion=""
    ):
        data = {
            "bodega_id": bodega_id,
            "rack_id": rack_id,
            "codigo_ubicacion": codigo_ubicacion,
            "tipo": tipo,
            "nivel": nivel,
            "columna": columna,
            "subdivision": subdivision,
            "ubicacion_padre_id": ubicacion_padre_id,
            "descripcion": descripcion,
            "_modulo": "Ubicaciones",
            "_accion": "Crear ubicación",
            "_detalle": f"Se creó la ubicación {codigo_ubicacion}"
        }
        exito, mensaje, _ = self._mutar("crear_ubicacion", data)
        if exito:
            return True, "Ubicación creada correctamente."
        return False, mensaje

    # ============================================================
    # PROYECTOS
    # ============================================================
    def cargar_proyectos(self):
        """
        Mantiene compatibilidad con la app actual:
        devuelve una lista de nombres para el ComboBox.
        """
        try:
            res = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("proyectos")
                    .select("nombre")
                    .eq("estado", "Activo")
                    .order("nombre")
                    .execute()
                )
            )

            if res.data:
                return [p["nombre"] for p in res.data]

            return ["Taller Interno"]

        except Exception as e:
            print(f"Error cargando proyectos: {e}")
            return ["Taller Interno"]

    def cargar_proyectos_completo(self):
        try:
            res = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("proyectos")
                    .select("*")
                    .order("nombre")
                    .execute()
                )
            )

            return res.data

        except Exception as e:
            print(f"Error cargando proyectos completos: {e}")
            return []

    def obtener_proyecto_por_nombre(self, nombre):
        try:
            res = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("proyectos")
                    .select("*")
                    .eq("nombre", nombre)
                    .execute()
                )
            )

            return res.data[0] if res.data else None

        except Exception as e:
            print(f"Error buscando proyecto: {e}")
            return None

    def crear_proyecto(self, nombre, ot="", cliente="", descripcion="", fecha_inicio=None, fecha_fin=None):
        data = {
            "nombre": nombre,
            "ot": ot,
            "cliente": cliente,
            "descripcion": descripcion,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": None,
            "_modulo": "Proyectos",
            "_accion": "Crear proyecto",
            "_detalle": f"Se creó el proyecto {nombre}"
        }
        exito, mensaje, _ = self._mutar("crear_proyecto", data)
        if exito:
            return True, "Proyecto creado correctamente."
        return False, mensaje

    def actualizar_proyecto(self, id_proyecto, datos):
        payload = dict(datos)
        payload.pop("fecha_fin", None)
        if "estado" in payload:
            try:
                respuesta = self._ejecutar_con_reintentos(
                    lambda: self.supabase.table("proyectos")
                    .select("estado,fecha_fin,fecha_inicio")
                    .eq("id", id_proyecto).execute()
                )
                if not respuesta.data:
                    return False, "Proyecto no encontrado."
                anterior = respuesta.data[0]
                if payload["estado"] == "Finalizado":
                    fin = anterior.get("fecha_fin")
                    if anterior.get("estado") != "Finalizado":
                        fin = fecha_actual_bodega()
                        payload["fecha_fin"] = fin
                    inicio = payload.get("fecha_inicio", anterior.get("fecha_inicio"))
                    if inicio and fin and str(inicio) > str(fin):
                        return False, "La fecha de inicio es posterior a la fecha de término."
                else:
                    payload["fecha_fin"] = None
            except Exception as error:
                return False, self._mensaje_error(error)
        payload.update({
            "id": id_proyecto,
            "_modulo": "Proyectos",
            "_accion": "Actualizar proyecto",
            "_detalle": f"Se actualizó el proyecto ID {id_proyecto}"
        })
        exito, mensaje, _ = self._mutar("actualizar_proyecto", payload)
        if exito:
            return True, "Proyecto actualizado correctamente."
        return False, mensaje

    # ============================================================
    # TRABAJADORES
    # ============================================================
    def obtener_nombre_trabajador(self, rut):
        try:
            respuesta = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("trabajadores")
                    .select("nombre")
                    .eq("rut", rut)
                    .execute()
                )
            )

            return respuesta.data[0]["nombre"] if respuesta.data else None

        except Exception as e:
            print(f"Error al validar trabajador: {e}")
            return None

    def cargar_trabajadores_nube(self, solo_activos=True):
        try:
            def construir_query():
                query = (
                    self.supabase
                    .table("trabajadores")
                    .select("*")
                    .order("nombre")
                )
                if solo_activos:
                    query = query.eq("estado", "Activo")
                return query

            respuesta = self._ejecutar_con_reintentos(
                lambda: construir_query().execute()
            )

            return respuesta.data

        except Exception as e:
            print(f"Error cargando trabajadores: {e}")
            return []

    def guardar_trabajador_nube(self, rut, nombre, cargo):
        data = {
            "rut": rut,
            "nombre": nombre,
            "cargo": cargo,
            "_modulo": "Trabajadores",
            "_accion": "Crear trabajador",
            "_detalle": f"Se creó el trabajador {nombre} ({rut})"
        }
        exito, mensaje, _ = self._mutar("crear_trabajador", data)
        if exito:
            return True, "Trabajador registrado con éxito"
        if "duplicate key value" in mensaje:
            return False, "Este RUT ya está registrado."
        return False, mensaje

    def buscar_trabajador_por_rut(self, rut):
        try:
            res = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("trabajadores")
                    .select("*")
                    .eq("rut", rut)
                    .eq("estado", "Activo")
                    .execute()
                )
            )

            return res.data[0] if res.data else None

        except Exception as e:
            print(f"Error buscando trabajador: {e}")
            return None

    # ============================================================
    # PRODUCTOS / INVENTARIO
    # ============================================================
    def cargar_productos_activos_selector(self):
        """Carga productos activos para selección manual en movimientos."""
        try:
            respuesta = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("productos")
                    .select("*")
                    .eq("estado", "Activo")
                    .order("nombre")
                    .execute()
                )
            )
            return respuesta.data or []
        except Exception as e:
            print(f"Error cargando productos para selector: {e}")
            return []

    def cargar_inventario_nube(self, propagar_error=False):
        try:
            respuesta = self._ejecutar_con_reintentos(
                lambda: self.supabase.table("productos").select("*").execute()
            )

            productos = respuesta.data or []

            # Compatibilidad temporal con vistas V1:
            # agregamos campos calculados para que no se rompa la tabla actual.
            ubicaciones = self.cargar_ubicaciones(solo_activas=False)
            mapa_ubicaciones = {
                u["id"]: u
                for u in ubicaciones
            }

            racks = self.cargar_racks()
            mapa_racks = {
                r["id"]: r
                for r in racks
            }

            bodegas = self.cargar_bodegas()
            mapa_bodegas = {
                b["id"]: b
                for b in bodegas
            }

            for p in productos:
                ubicacion = mapa_ubicaciones.get(p.get("ubicacion_id"))

                if ubicacion:
                    rack = mapa_racks.get(ubicacion.get("rack_id"))
                    bodega = mapa_bodegas.get(ubicacion.get("bodega_id"))

                    p["ubicacion_codigo"] = ubicacion.get("codigo_ubicacion", "-")
                    p["bodega"] = bodega.get("nombre", "Bodega 1") if bodega else "Bodega 1"
                    p["rack"] = rack.get("codigo_rack", "-") if rack else "-"
                else:
                    p["ubicacion_codigo"] = "-"
                    p["bodega"] = "Bodega 1"
                    p["rack"] = "-"

                # Compatibilidad con campo antiguo
                p["ot"] = p.get("ot", "-")

            return productos

        except Exception as e:
            print(f"Error al cargar inventario: {e}")
            if propagar_error:
                raise
            return []

    def cargar_inactivos_nube(self):
        try:
            respuesta = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("productos")
                    .select("*")
                    .eq("estado", "Inactivo")
                    .order("id")
                    .execute()
                )
            )

            return respuesta.data

        except Exception as e:
            print(f"Error al cargar inactivos: {e}")
            return []

    def guardar_producto_nube(
        self,
        codigo,
        ot,
        nombre,
        categoria,
        tamano,
        stock,
        precio_unitario=0,
        ubicacion_id=None,
        stock_minimo=0,
        tipo_medicion="No aplica",
        medida_largo=None,
        medida_ancho=None,
        unidad_medida=None,
        producto_origen_id=None,
        es_retazo=False,
        porcentaje_valor_origen=None,
        observacion_retazo=None
    ):
        data = {
            "codigo_barras": codigo,
            "nombre": nombre,
            "categoria": categoria,
            "tamaño_dimensiones": tamano,
            "stock": stock,
            "stock_minimo": stock_minimo,
            "precio_unitario": precio_unitario,
            "ubicacion_id": ubicacion_id,
            "tipo_medicion": tipo_medicion or "No aplica",
            "medida_largo": medida_largo,
            "medida_ancho": medida_ancho,
            "unidad_medida": unidad_medida,
            "producto_origen_id": producto_origen_id,
            "es_retazo": es_retazo,
            "porcentaje_valor_origen": porcentaje_valor_origen,
            "observacion_retazo": observacion_retazo,
            "_modulo": "Inventario",
            "_accion": "Crear producto",
            "_detalle": f"Se creó el producto {nombre} con código {codigo}"
        }
        exito, mensaje, _ = self._crear_producto_compatible(data)
        if exito:
            return True, "Producto guardado correctamente."
        return False, mensaje

    def _crear_producto_compatible(self, datos):
        """Crea productos sin asumir si los identificadores son UUID o bigint."""
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje, None

        request_id = str(uuid4())
        try:
            respuesta = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "crear_producto_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_datos": datos
                    }
                ).execute()
            )
            return True, "Operación realizada correctamente.", respuesta.data
        except Exception as e:
            mensaje_error = self._mensaje_error(e)
            if "crear_producto_app" in mensaje_error and (
                "does not exist" in mensaje_error.lower()
                or "not found" in mensaje_error.lower()
                or "could not find" in mensaje_error.lower()
                or "pgrst202" in mensaje_error.lower()
            ):
                mensaje_error = (
                    "Falta ejecutar la migración "
                    "008_crear_productos_compatible.sql en Supabase."
                )
            return False, mensaje_error, None

    def crear_retazo_con_entrada(self, datos_retazo, proyecto, rut_trabajador=""):
        payload = dict(datos_retazo)
        payload.update({
            "proyecto": proyecto,
            "rut_trabajador": rut_trabajador or "",
            "es_retazo": True,
            "_modulo": "Inventario",
            "_accion": "Crear retazo",
            "_detalle": (
                f"Se creó el retazo {datos_retazo.get('nombre', '')} "
                f"para el proyecto {proyecto}"
            )
        })
        exito, mensaje, respuesta = self._crear_producto_compatible(payload)
        if not exito:
            return False, mensaje, None

        id_retazo = None
        if isinstance(respuesta, dict):
            id_retazo = respuesta.get("id")
        return True, "Retazo creado con trazabilidad.", id_retazo
        
    def buscar_producto_por_codigo(self, codigo):
        try:
            res = (
                self.supabase
                .table("productos")
                .select("*")
                .eq("codigo_barras", codigo)
                .eq("estado", "Activo")
                .execute()
            )

            return res.data[0] if res.data else None

        except Exception as e:
            print(f"Error buscando producto: {e}")
            return None

    def actualizar_producto_nube(self, id_producto, datos):
        campos_permitidos = {
            "nombre",
            "categoria",
            "tamaño_dimensiones",
            "stock",
            "stock_minimo",
            "precio_unitario",
            "ubicacion_id",
            "estado",
            "tipo_medicion",
            "medida_largo",
            "medida_ancho",
            "unidad_medida"
        }
        datos_limpios = {
            k: v
            for k, v in datos.items()
            if k in campos_permitidos
        }
        datos_limpios.update({
            "id": id_producto,
            "_modulo": "Inventario",
            "_accion": "Editar producto",
            "_detalle": f"Se editó el producto ID {id_producto}"
        })

        if "stock" in datos_limpios:
            exito, mensaje, _ = self._actualizar_producto_con_stock(
                datos_limpios
            )
        else:
            exito, mensaje, _ = self._mutar(
                "actualizar_producto",
                datos_limpios
            )

        if exito:
            return True, "Producto actualizado con éxito."
        return False, mensaje

    def _actualizar_producto_con_stock(self, datos):
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje, None

        request_id = str(uuid4())
        try:
            respuesta = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "actualizar_producto_stock_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_datos": datos
                    }
                ).execute()
            )
            return True, "Operación realizada correctamente.", respuesta.data
        except Exception as e:
            mensaje_error = self._mensaje_error(e)
            texto_error = mensaje_error.lower()
            if "actualizar_producto_stock_app" in texto_error and (
                "does not exist" in texto_error
                or "not found" in texto_error
                or "could not find" in texto_error
                or "pgrst202" in texto_error
            ):
                mensaje_error = (
                    "Falta ejecutar la migración 009 de ajuste manual de stock "
                    "en Supabase."
                )
            return False, mensaje_error, None

    def dar_de_baja_producto(self, id_producto):
        payload = {
            "id": id_producto,
            "estado": "Inactivo",
            "_modulo": "Inventario",
            "_accion": "Dar de baja producto",
            "_detalle": f"Se dio de baja el producto ID {id_producto}"
        }
        exito, mensaje, _ = self._mutar("actualizar_producto", payload)
        if exito:
            return True, "Producto dado de baja correctamente."
        return False, f"Error al dar de baja: {mensaje}"

    def restaurar_producto_nube(self, id_producto):
        payload = {
            "id": id_producto,
            "estado": "Activo",
            "_modulo": "Inventario",
            "_accion": "Restaurar producto",
            "_detalle": f"Se restauró el producto ID {id_producto}"
        }
        exito, mensaje, _ = self._mutar("actualizar_producto", payload)
        if exito:
            return True, "Producto restaurado y devuelto al inventario."
        return False, f"Error al restaurar: {mensaje}"

    def cargar_papelera_nube(self):
        return [
            producto
            for producto in self.cargar_inventario_nube()
            if producto.get("estado") == "Inactivo"
        ]

    # ============================================================
    # TRANSACCIONES / MOVIMIENTOS
    # ============================================================
    def registrar_movimiento_camara(
        self,
        rut_trabajador,
        codigo_producto,
        tipo_movimiento,
        id_producto,
        stock_actual,
        cantidad_movida=1,
        proyecto=None,
        comentario=None
    ):
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje

        try:
            cantidad = int(cantidad_movida)
            if cantidad <= 0:
                return False, "La cantidad debe ser mayor a cero."

            proyecto = str(proyecto or "").strip()
            if not proyecto:
                return False, "Debe seleccionar un proyecto antes de registrar el movimiento."

            comentario_limpio = str(comentario or "").strip() or None
            if comentario_limpio and len(comentario_limpio) > 1000:
                return False, "El comentario puede tener como máximo 1.000 caracteres."

            request_id = str(uuid4())
            self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "registrar_movimiento_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_rut_trabajador": rut_trabajador or "",
                        "p_codigo_producto": codigo_producto,
                        "p_tipo_movimiento": tipo_movimiento.strip(),
                        "p_producto_id": str(id_producto),
                        "p_cantidad": cantidad,
                        "p_proyecto": proyecto,
                        "p_comentario": comentario_limpio
                    }
                ).execute()
            )
            return True, "Movimiento registrado."
        except Exception as e:
            mensaje_error = self._mensaje_error(e)
            if (
                tipo_movimiento == TIPO_ENTREGA_HERRAMIENTA_PERSONAL
                and "tipo de movimiento no permitido" in mensaje_error.casefold()
            ):
                mensaje_error = (
                    "Falta ejecutar la migración 015 de herramientas "
                    "personales en Supabase."
                )
            return False, mensaje_error

    # ============================================================
    # PGP / CONTENEDORES DE PROYECTO
    # ============================================================
    def crear_pgp(
        self,
        proyecto,
        rut_responsable,
        observacion,
        items
    ):
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje, None

        proyecto_limpio = str(proyecto or "").strip()
        if not proyecto_limpio:
            return False, "Debe seleccionar un proyecto.", None

        observacion_limpia = str(observacion or "").strip() or None
        if observacion_limpia and len(observacion_limpia) > 1000:
            return False, (
                "La observación puede tener como máximo 1.000 caracteres."
            ), None

        try:
            items_limpios = preparar_items_pgp(items, rut_responsable)
        except ValueError as error:
            return False, str(error), None

        try:
            request_id = str(uuid4())
            respuesta = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "crear_pgp_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_proyecto": proyecto_limpio,
                        "p_rut_trabajador": str(
                            rut_responsable or ""
                        ).strip(),
                        "p_observacion": observacion_limpia,
                        "p_items": items_limpios,
                    }
                ).execute()
            )
            datos = respuesta.data
            if isinstance(datos, list):
                datos = datos[0] if datos else {}
            codigo = (datos or {}).get("codigo_pgp")
            texto = (
                f"PGP {codigo} registrado correctamente."
                if codigo else
                "PGP registrado correctamente."
            )
            return True, texto, datos
        except Exception as error:
            mensaje_error = self._mensaje_error(error)
            if "crear_pgp_app" in mensaje_error.lower() or (
                "pgp_contenedores" in mensaje_error.lower()
            ):
                mensaje_error = (
                    "Falta ejecutar la migración "
                    "013_pgp_contenedores.sql en Supabase."
                )
            return False, mensaje_error, None

    def agregar_items_pgp(
        self,
        pgp_id,
        rut_responsable,
        observacion,
        items,
    ):
        """Agrega nuevas salidas a un PGP existente mediante una RPC atómica."""
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje, None

        try:
            items_limpios = preparar_items_pgp(items, rut_responsable)
        except ValueError as error:
            return False, str(error), None

        observacion_limpia = str(observacion or "").strip() or None
        if observacion_limpia and len(observacion_limpia) > 1000:
            return False, (
                "La observación puede tener como máximo 1.000 caracteres."
            ), None

        try:
            request_id = str(uuid4())
            respuesta = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "agregar_items_pgp_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_pgp_id": str(pgp_id),
                        "p_rut_trabajador": str(
                            rut_responsable or ""
                        ).strip(),
                        "p_observacion": observacion_limpia,
                        "p_items": items_limpios,
                    },
                ).execute()
            )
            datos = respuesta.data
            if isinstance(datos, list):
                datos = datos[0] if datos else {}
            unidades = int((datos or {}).get("unidades_agregadas") or 0)
            codigo = (datos or {}).get("codigo_pgp") or "PGP"
            return True, (
                f"Se agregaron {unidades} unidades a {codigo}."
            ), datos
        except Exception as error:
            mensaje_error = self._mensaje_error(error)
            texto_error = mensaje_error.casefold()
            if "agregar_items_pgp_app" in texto_error or any(
                marcador in texto_error
                for marcador in ("pgrst202", "could not find the function")
            ):
                mensaje_error = (
                    "Falta ejecutar la migración "
                    "016_ampliar_pgp.sql en Supabase."
                )
            return False, mensaje_error, None

    def devolver_item_pgp(
        self,
        pgp_id,
        item_id,
        cantidad,
        comentario=""
    ):
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje

        try:
            cantidad_entera = int(cantidad)
            if cantidad_entera <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return False, "La cantidad debe ser un entero mayor a cero."

        comentario_limpio = str(comentario or "").strip() or None
        if comentario_limpio and len(comentario_limpio) > 1000:
            return False, (
                "El comentario puede tener como máximo 1.000 caracteres."
            )

        try:
            request_id = str(uuid4())
            self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "devolver_item_pgp_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_pgp_id": str(pgp_id),
                        "p_item_id": int(item_id),
                        "p_cantidad": cantidad_entera,
                        "p_comentario": comentario_limpio,
                    }
                ).execute()
            )
            return True, "Devolución registrada correctamente."
        except Exception as error:
            mensaje_error = self._mensaje_error(error)
            if "devolver_item_pgp_app" in mensaje_error.lower() or (
                "pgp_items" in mensaje_error.lower()
            ):
                mensaje_error = (
                    "Falta ejecutar la migración "
                    "013_pgp_contenedores.sql en Supabase."
                )
            return False, mensaje_error

    def devolver_pgp_completo(self, pgp_id, comentario=""):
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje

        comentario_limpio = str(comentario or "").strip() or None
        if comentario_limpio and len(comentario_limpio) > 1000:
            return False, (
                "El comentario puede tener como máximo 1.000 caracteres."
            )

        try:
            request_id = str(uuid4())
            respuesta = self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "devolver_pgp_completo_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_pgp_id": str(pgp_id),
                        "p_comentario": comentario_limpio,
                    }
                ).execute()
            )
            datos = respuesta.data
            if isinstance(datos, list):
                datos = datos[0] if datos else {}
            unidades = int((datos or {}).get("unidades_devueltas") or 0)
            return True, f"Se devolvieron {unidades} unidades correctamente."
        except Exception as error:
            mensaje_error = self._mensaje_error(error)
            if "devolver_pgp_completo_app" in mensaje_error.lower() or (
                "pgp_items" in mensaje_error.lower()
            ):
                mensaje_error = (
                    "Falta volver a ejecutar la migración "
                    "013_pgp_contenedores.sql en Supabase."
                )
            return False, mensaje_error

    def cargar_pgp_contenedores(self):
        try:
            filas_pgp = self._cargar_tabla_paginada(
                "pgp_contenedores",
                ordenar_por="fecha_creacion",
                desc=True,
            )
            filas_items = self._cargar_tabla_paginada(
                "pgp_items",
                ordenar_por="id",
            )

            items_por_pgp = {}
            for item in filas_items:
                item_copia = dict(item)
                item_copia["fecha_salida"] = formatear_fecha_hora(
                    item_copia.get("creado_en")
                )
                item_copia["cantidad_pendiente"] = (
                    cantidad_pendiente_item_pgp(item_copia)
                )
                items_por_pgp.setdefault(
                    str(item_copia.get("pgp_id")), []
                ).append(item_copia)

            contenedores = []
            for pgp in filas_pgp:
                pgp_copia = dict(pgp)
                items_pgp = items_por_pgp.get(str(pgp_copia.get("id")), [])
                pgp_copia["items"] = items_pgp
                pgp_copia["cantidad_items"] = len(items_pgp)
                pgp_copia["cantidad_unidades"] = sum(
                    int(item.get("cantidad") or 0)
                    for item in items_pgp
                )
                pgp_copia["unidades_pendientes"] = sum(
                    int(item.get("cantidad_pendiente") or 0)
                    for item in items_pgp
                )
                # Alias temporal para instalaciones que conserven una vista abierta.
                pgp_copia["prestamos_pendientes"] = pgp_copia[
                    "unidades_pendientes"
                ]
                pgp_copia["fecha"] = formatear_fecha_hora(
                    pgp_copia.get("fecha_creacion")
                )
                contenedores.append(pgp_copia)

            return {
                "disponible": True,
                "contenedores": contenedores,
                "error": None,
            }
        except Exception as error:
            mensaje = self._mensaje_error(error)
            if any(nombre in mensaje.lower() for nombre in (
                "pgp_contenedores",
                "pgp_items",
            )):
                mensaje = (
                    "Falta ejecutar la migración "
                    "013_pgp_contenedores.sql en Supabase."
                )
            return {
                "disponible": False,
                "contenedores": [],
                "error": mensaje,
            }

    def obtener_ultimos_movimientos(self, limite=5):
        try:
            res_trans = (
                self.supabase
                .table("transacciones")
                .select("*")
                .order("fecha_hora", desc=True)
                .limit(limite)
                .execute()
            )

            productos = self.cargar_inventario_nube()
            mapa_prod = {
                p["id"]: p["nombre"]
                for p in productos
            }

            trabajadores = self.cargar_trabajadores_nube(solo_activos=False)
            mapa_trab = {
                t["id"]: t["nombre"]
                for t in trabajadores
            }
            proyectos = self.cargar_proyectos_completo()
            mapa_proy = {
                p["id"]: p["nombre"]
                for p in proyectos
            }

            movimientos = []

            for t in res_trans.data:
                fecha_limpia = formatear_fecha_hora(t.get("fecha_hora"))

                producto = (
                    t.get("producto_nombre_snapshot")
                    or mapa_prod.get(t.get("producto_id"), "-")
                )
                trabajador = mapa_trab.get(t.get("trabajador_id"), "-")
                proyecto = mapa_proy.get(t.get("proyecto_id"), "-")

                movimiento = t.get("tipo_movimiento", "-")
                cantidad = t.get("cantidad_movida", 1)

                movimientos.append((
                    fecha_limpia,
                    producto,
                    trabajador,
                    f"{movimiento} | {proyecto}",
                    cantidad
                ))

            return movimientos

        except Exception as e:
            print(f"Error obteniendo últimos movimientos: {e}")
            return []

    def obtener_historial_reciente(self):
        try:
            res_trans = (
                self.supabase
                .table("transacciones")
                .select("*")
                .order("fecha_hora", desc=True)
                .limit(100)
                .execute()
            )

            productos = self.cargar_inventario_nube()
            mapa_prod = {
                p["id"]: p["nombre"]
                for p in productos
            }

            trabajadores = self.cargar_trabajadores_nube(solo_activos=False)
            mapa_trab = {
                t["id"]: t["nombre"]
                for t in trabajadores
            }

            proyectos = self.cargar_proyectos_completo()
            mapa_proy = {
                p["id"]: p["nombre"]
                for p in proyectos
            }

            historial = []

            for t in res_trans.data:
                fecha_limpia = formatear_fecha_hora(t.get("fecha_hora"))

                nombre_trab = mapa_trab.get(t.get("trabajador_id"), "Sin responsable")
                nombre_prod = (
                    t.get("producto_nombre_snapshot")
                    or mapa_prod.get(t.get("producto_id"), "Desconocido")
                )
                nombre_proy = mapa_proy.get(t.get("proyecto_id"), "-")

                historial.append((
                    fecha_limpia,
                    nombre_trab,
                    nombre_prod,
                    t.get("tipo_movimiento", "-"),
                    t.get("cantidad_movida", 1),
                    nombre_proy
                ))

            return historial

        except Exception as e:
            print(f"Error cargando historial: {e}")
            return []

    def obtener_movimientos_estadisticas(self):
        """Devuelve movimientos enriquecidos para el panel de estadísticas."""
        try:
            movimientos = []
            tamano_pagina = 1000
            inicio = 0

            while True:
                respuesta = self._ejecutar_con_reintentos(
                    lambda inicio=inicio: (
                        self.supabase
                        .table("transacciones")
                        .select(
                            "producto_id,proyecto_id,trabajador_id,tipo_movimiento,"
                            "cantidad_movida,fecha_hora,precio_unitario_movimiento,"
                            "producto_nombre_snapshot,stock_anterior,stock_nuevo,"
                            "comentario,creado_por_usuario"
                        )
                        .order("fecha_hora", desc=True)
                        .range(inicio, inicio + tamano_pagina - 1)
                        .execute()
                    )
                )
                pagina = respuesta.data or []
                movimientos.extend(pagina)
                if len(pagina) < tamano_pagina:
                    break
                inicio += tamano_pagina

            productos = self.cargar_inventario_nube()
            mapa_productos = {producto.get("id"): producto for producto in productos}
            proyectos = self.cargar_proyectos_completo()
            mapa_proyectos = {proyecto.get("id"): proyecto for proyecto in proyectos}
            trabajadores = self.cargar_trabajadores_nube(solo_activos=False)
            mapa_trabajadores = {
                trabajador.get("id"): trabajador for trabajador in trabajadores
            }

            resultado = []
            for movimiento in movimientos:
                producto = mapa_productos.get(movimiento.get("producto_id"), {})
                proyecto = mapa_proyectos.get(movimiento.get("proyecto_id"), {})
                trabajador = mapa_trabajadores.get(
                    movimiento.get("trabajador_id"), {}
                )
                precio = movimiento.get("precio_unitario_movimiento")
                if precio is None:
                    precio = producto.get("precio_unitario") or 0

                resultado.append({
                    "producto_id": movimiento.get("producto_id"),
                    "producto": (
                        movimiento.get("producto_nombre_snapshot")
                        or producto.get("nombre")
                        or "Producto desconocido"
                    ),
                    "proyecto": proyecto.get("nombre") or "Sin proyecto",
                    "trabajador": trabajador.get("nombre") or "Sin responsable",
                    "tipo_movimiento": movimiento.get("tipo_movimiento"),
                    "cantidad_movida": movimiento.get("cantidad_movida"),
                    "fecha_hora": movimiento.get("fecha_hora"),
                    "precio_unitario": precio,
                    "stock_anterior": movimiento.get("stock_anterior"),
                    "stock_nuevo": movimiento.get("stock_nuevo"),
                    "comentario": movimiento.get("comentario") or "-",
                    "registrado_por": movimiento.get("creado_por_usuario") or "-",
                })

            return resultado
        except Exception as e:
            print(f"Error cargando movimientos para estadísticas: {e}")
            return []

    def obtener_historial_precios(self):
        """Obtiene los cambios reales de precio registrados por la migración 012."""
        try:
            respuesta = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("historial_precios")
                    .select(
                        "id,producto_id,producto_nombre,precio_anterior,"
                        "precio_nuevo,fecha_hora,usuario_app"
                    )
                    .order("fecha_hora", desc=True)
                    .execute()
                )
            )
            return {
                "disponible": True,
                "filas": respuesta.data or [],
                "error": "",
            }
        except Exception as e:
            mensaje = self._mensaje_error(e)
            texto = mensaje.casefold()
            if "historial_precios" in texto and any(marcador in texto for marcador in (
                "does not exist", "not found", "could not find", "pgrst205"
            )):
                mensaje = (
                    "Falta ejecutar la migración 012 de historial de precios "
                    "en Supabase."
                )
            print(f"Error cargando historial de precios: {mensaje}")
            return {
                "disponible": False,
                "filas": [],
                "error": mensaje,
            }

    def obtener_registro_entregas_epp(self):
        """Devuelve el historial detallado de entregas de productos EPP."""
        try:
            res_trans = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("transacciones")
                    .select("*")
                    .eq("tipo_movimiento", "Entrega / Consumo")
                    .order("fecha_hora", desc=True)
                    .execute()
                )
            )

            productos = self.cargar_inventario_nube()
            productos_epp = {
                p["id"]: p
                for p in productos
                if str(p.get("categoria") or "").strip().casefold() == "epp"
            }

            trabajadores = self.cargar_trabajadores_nube(solo_activos=False)
            mapa_trabajadores = {
                t["id"]: t
                for t in trabajadores
            }

            proyectos = self.cargar_proyectos_completo()
            mapa_proyectos = {
                p["id"]: p.get("nombre") or "-"
                for p in proyectos
            }

            entregas = []
            for movimiento in res_trans.data or []:
                # La comprobación local evita mezclar otros movimientos incluso
                # si un cliente de pruebas o una API antigua ignora el filtro.
                if movimiento.get("tipo_movimiento") != "Entrega / Consumo":
                    continue

                producto = productos_epp.get(movimiento.get("producto_id"))
                if not producto:
                    continue

                trabajador = mapa_trabajadores.get(
                    movimiento.get("trabajador_id"),
                    {}
                )
                fecha_cruda = str(movimiento.get("fecha_hora") or "")

                entregas.append({
                    "id": movimiento.get("id"),
                    "fecha_hora": fecha_cruda,
                    "fecha": formatear_fecha_hora(fecha_cruda),
                    "trabajador_id": movimiento.get("trabajador_id"),
                    "trabajador": (
                        trabajador.get("nombre") or "Sin responsable"
                    ),
                    "rut": trabajador.get("rut") or "-",
                    "producto_id": movimiento.get("producto_id"),
                    "epp": (
                        movimiento.get("producto_nombre_snapshot")
                        or producto.get("nombre")
                        or "EPP desconocido"
                    ),
                    "cantidad": int(movimiento.get("cantidad_movida") or 0),
                    "proyecto": mapa_proyectos.get(
                        movimiento.get("proyecto_id"),
                        "-"
                    ),
                    "entregado_por": (
                        movimiento.get("creado_por_usuario") or "-"
                    ),
                    "comentario": movimiento.get("comentario") or "-"
                })

            return entregas

        except Exception as e:
            print(f"Error cargando registro de entregas EPP: {e}")
            return []

    def obtener_registro_herramientas_personales(self):
        """Devuelve las herramientas entregadas permanentemente a trabajadores."""
        tipo = TIPO_ENTREGA_HERRAMIENTA_PERSONAL
        try:
            res_trans = self._ejecutar_con_reintentos(
                lambda: (
                    self.supabase
                    .table("transacciones")
                    .select("*")
                    .eq("tipo_movimiento", tipo)
                    .order("fecha_hora", desc=True)
                    .execute()
                )
            )

            productos = self.cargar_inventario_nube()
            mapa_productos = {p["id"]: p for p in productos}
            trabajadores = self.cargar_trabajadores_nube(solo_activos=False)
            mapa_trabajadores = {t["id"]: t for t in trabajadores}
            proyectos = self.cargar_proyectos_completo()
            mapa_proyectos = {
                p["id"]: p.get("nombre") or "-" for p in proyectos
            }

            entregas = []
            for movimiento in res_trans.data or []:
                if movimiento.get("tipo_movimiento") != tipo:
                    continue

                producto = mapa_productos.get(
                    movimiento.get("producto_id"), {}
                )
                trabajador = mapa_trabajadores.get(
                    movimiento.get("trabajador_id"), {}
                )
                fecha_cruda = str(movimiento.get("fecha_hora") or "")
                entregas.append({
                    "id": movimiento.get("id"),
                    "fecha_hora": fecha_cruda,
                    "fecha": formatear_fecha_hora(fecha_cruda),
                    "trabajador_id": movimiento.get("trabajador_id"),
                    "trabajador": (
                        trabajador.get("nombre") or "Trabajador desconocido"
                    ),
                    "rut": trabajador.get("rut") or "-",
                    "producto_id": movimiento.get("producto_id"),
                    "herramienta": (
                        movimiento.get("producto_nombre_snapshot")
                        or producto.get("nombre")
                        or "Herramienta desconocida"
                    ),
                    "cantidad": int(movimiento.get("cantidad_movida") or 0),
                    "proyecto": mapa_proyectos.get(
                        movimiento.get("proyecto_id"), "-"
                    ),
                    "entregado_por": (
                        movimiento.get("creado_por_usuario") or "-"
                    ),
                    "comentario": movimiento.get("comentario") or "-",
                })

            return entregas
        except Exception as e:
            print(f"Error cargando herramientas personales: {e}")
            return []

    # ============================================================
    # HERRAMIENTAS EN TERRENO
    # ============================================================
    def _ids_devoluciones_prestamo_pgp(self):
        """Identifica qué devoluciones PGP corresponden realmente a préstamos."""
        try:
            items = self._cargar_tabla_paginada(
                "pgp_items",
                columnas="id,tipo_movimiento",
                ordenar_por="id",
            )
            ids_items_prestamo = {
                str(item.get("id"))
                for item in items
                if item.get("tipo_movimiento") == TIPO_PRESTAMO_PGP
            }
            if not ids_items_prestamo:
                return set()

            devoluciones = self._cargar_tabla_paginada(
                "pgp_devoluciones",
                columnas="id,pgp_item_id,transaccion_id",
                ordenar_por="id",
            )
            return {
                str(devolucion.get("transaccion_id"))
                for devolucion in devoluciones
                if str(devolucion.get("pgp_item_id")) in ids_items_prestamo
                and devolucion.get("transaccion_id") is not None
            }
        except Exception as error:
            self._log_db(
                "no fue posible clasificar devoluciones PGP por tipo: "
                f"{error}"
            )
            return None

    def obtener_herramientas_en_terreno(self):
        try:
            movimientos = (
                self.supabase
                .table("transacciones")
                .select("*")
                .in_(
                    "tipo_movimiento",
                    [
                        "Préstamo de Herramienta",
                        "Devolución de Herramienta",
                        TIPO_DEVOLUCION_PGP,
                    ]
                )
                .order("fecha_hora")
                .execute()
            )
            filas_movimientos = list(movimientos.data or [])
            ids_devoluciones_prestamo = None
            if any(
                movimiento.get("tipo_movimiento") == TIPO_DEVOLUCION_PGP
                for movimiento in filas_movimientos
            ):
                ids_devoluciones_prestamo = (
                    self._ids_devoluciones_prestamo_pgp()
                )

            productos = self.cargar_inventario_nube()
            mapa_prod = {
                p["id"]: p["nombre"]
                for p in productos
            }

            trabajadores = self.cargar_trabajadores_nube(solo_activos=False)
            mapa_trab = {
                t["id"]: t["nombre"]
                for t in trabajadores
            }
            proyectos = self.cargar_proyectos_completo()
            mapa_proy = {
                p["id"]: p["nombre"]
                for p in proyectos
            }

            estado_herramientas = {}

            for m in filas_movimientos:
                llave = (
                    m.get("producto_id"),
                    m.get("trabajador_id")
                )
                cantidad = int(m.get("cantidad_movida") or 0)

                if m.get("tipo_movimiento") == "Préstamo de Herramienta":
                    estado = estado_herramientas.setdefault(
                        llave,
                        {
                            "cantidad_pendiente": 0,
                            "transaccion": m
                        }
                    )
                    if estado["cantidad_pendiente"] <= 0:
                        estado["transaccion"] = m
                    estado["cantidad_pendiente"] += cantidad

                elif (
                    m.get("tipo_movimiento") == "Devolución de Herramienta"
                    or (
                        m.get("tipo_movimiento") == TIPO_DEVOLUCION_PGP
                        and (
                            ids_devoluciones_prestamo is None
                            or str(m.get("id")) in ids_devoluciones_prestamo
                        )
                    )
                ):
                    estado = estado_herramientas.get(llave)
                    if estado:
                        estado["cantidad_pendiente"] -= cantidad
                        if estado["cantidad_pendiente"] <= 0:
                            del estado_herramientas[llave]

            en_terreno = []

            for estado in estado_herramientas.values():
                transaccion_copia = dict(estado["transaccion"])
                transaccion_copia["cantidad_pendiente"] = estado["cantidad_pendiente"]

                transaccion_copia["nombre_trabajador"] = mapa_trab.get(
                    transaccion_copia.get("trabajador_id"),
                    "Sin responsable"
                )

                transaccion_copia["nombre_producto"] = mapa_prod.get(
                    transaccion_copia.get("producto_id"),
                    "Desconocido"
                )
                transaccion_copia["nombre_proyecto"] = mapa_proy.get(
                    transaccion_copia.get("proyecto_id"),
                    "-"
                )

                transaccion_copia["codigo_producto"] = transaccion_copia["nombre_producto"]

                en_terreno.append(transaccion_copia)

            return en_terreno

        except Exception as e:
            print(f"Error herramientas terreno: {e}")
            return []
        
    # ============================================================
    # MAPA DE BODEGA / VISTA RACK
    # ============================================================
    def cargar_productos_por_ubicacion(self, ubicacion_id):
        try:
            res = (
                self.supabase
                .table("productos")
                .select("*")
                .eq("ubicacion_id", ubicacion_id)
                .eq("estado", "Activo")
                .order("nombre")
                .execute()
            )

            return res.data or []

        except Exception as e:
            print(f"Error cargando productos por ubicación: {e}")
            return []

    def cargar_sububicaciones(self, ubicacion_padre_id):
        try:
            res = (
                self.supabase
                .table("ubicaciones")
                .select("*")
                .eq("ubicacion_padre_id", ubicacion_padre_id)
                .eq("estado", "Activo")
                .order("codigo_ubicacion")
                .execute()
            )

            return res.data or []

        except Exception as e:
            print(f"Error cargando sububicaciones: {e}")
            return []

    def cargar_ubicaciones_base_por_rack(self, rack_id):
        try:
            res = (
                self.supabase
                .table("ubicaciones")
                .select("*")
                .eq("rack_id", rack_id)
                .eq("tipo", "Bloque")
                .eq("estado", "Activo")
                .order("codigo_ubicacion")
                .execute()
            )

            return res.data or []

        except Exception as e:
            print(f"Error cargando ubicaciones base por rack: {e}")
            return []

    def obtener_resumen_ubicacion(self, ubicacion_id):
        """
        Devuelve un resumen simple para pintar el mapa:
        - cantidad de productos directos
        - cantidad de subdivisiones
        - stock total directo
        """
        try:
            productos = self.cargar_productos_por_ubicacion(ubicacion_id)
            sububicaciones = self.cargar_sububicaciones(ubicacion_id)

            stock_total = 0

            for p in productos:
                try:
                    stock_total += int(p.get("stock") or 0)
                except Exception:
                    pass

            return {
                "productos": len(productos),
                "subdivisiones": len(sububicaciones),
                "stock_total": stock_total
            }

        except Exception as e:
            print(f"Error obteniendo resumen ubicación: {e}")
            return {
                "productos": 0,
                "subdivisiones": 0,
                "stock_total": 0
            }

    # ============================================================
    # MAPA DE BODEGA / VISTA RACK OPTIMIZADA
    # ============================================================
    def cargar_mapa_rack_completo(self, rack_id):
        """
        Carga todo lo necesario para dibujar un rack en pocas consultas:
        - ubicaciones base del rack
        - subdivisiones de esas ubicaciones
        - productos asociados a ubicaciones base y subdivisiones
        - resumen por ubicación base

        Retorna:
        {
            "ubicaciones_base": [...],
            "sububicaciones": [...],
            "productos": [...],
            "sububicaciones_por_padre": {ubicacion_padre_id: [...]},
            "productos_por_ubicacion": {ubicacion_id: [...]},
            "resumen_por_ubicacion": {ubicacion_id: {...}}
        }
        """
        try:
            # 1. Ubicaciones base del rack
            res_base = (
                self.supabase
                .table("ubicaciones")
                .select("*")
                .eq("rack_id", rack_id)
                .eq("tipo", "Bloque")
                .eq("estado", "Activo")
                .order("codigo_ubicacion")
                .execute()
            )

            ubicaciones_base = res_base.data or []

            if not ubicaciones_base:
                return {
                    "ubicaciones_base": [],
                    "sububicaciones": [],
                    "productos": [],
                    "sububicaciones_por_padre": {},
                    "productos_por_ubicacion": {},
                    "resumen_por_ubicacion": {}
                }

            ids_base = [u["id"] for u in ubicaciones_base]

            # 2. Subdivisiones de esas ubicaciones base
            res_sub = (
                self.supabase
                .table("ubicaciones")
                .select("*")
                .eq("rack_id", rack_id)
                .eq("tipo", "Subdivision")
                .eq("estado", "Activo")
                .in_("ubicacion_padre_id", ids_base)
                .order("codigo_ubicacion")
                .execute()
            )

            sububicaciones = res_sub.data or []
            ids_sub = [s["id"] for s in sububicaciones]

            # 3. Productos de ubicaciones base + subdivisiones
            ids_todas = ids_base + ids_sub

            productos = []

            if ids_todas:
                res_prod = (
                    self.supabase
                    .table("productos")
                    .select("*")
                    .eq("estado", "Activo")
                    .in_("ubicacion_id", ids_todas)
                    .order("nombre")
                    .execute()
                )

                productos = res_prod.data or []

            # 4. Agrupar subdivisiones por ubicación padre
            sububicaciones_por_padre = {}

            for sub in sububicaciones:
                padre_id = sub.get("ubicacion_padre_id")

                if padre_id not in sububicaciones_por_padre:
                    sububicaciones_por_padre[padre_id] = []

                sububicaciones_por_padre[padre_id].append(sub)

            # 5. Agrupar productos por ubicación
            productos_por_ubicacion = {}

            for p in productos:
                ubicacion_id = p.get("ubicacion_id")

                if ubicacion_id not in productos_por_ubicacion:
                    productos_por_ubicacion[ubicacion_id] = []

                productos_por_ubicacion[ubicacion_id].append(p)

            # 6. Crear resumen por cada ubicación base
            resumen_por_ubicacion = {}

            for ubicacion in ubicaciones_base:
                ubicacion_id = ubicacion["id"]

                productos_directos = productos_por_ubicacion.get(ubicacion_id, [])
                subs = sububicaciones_por_padre.get(ubicacion_id, [])

                productos_subs = []
                stock_total = 0

                for p in productos_directos:
                    try:
                        stock_total += int(p.get("stock") or 0)
                    except Exception:
                        pass

                for sub in subs:
                    productos_de_sub = productos_por_ubicacion.get(sub["id"], [])
                    productos_subs.extend(productos_de_sub)

                    for p in productos_de_sub:
                        try:
                            stock_total += int(p.get("stock") or 0)
                        except Exception:
                            pass

                resumen_por_ubicacion[ubicacion_id] = {
                    "productos_directos": len(productos_directos),
                    "productos_sububicaciones": len(productos_subs),
                    "productos_total": len(productos_directos) + len(productos_subs),
                    "subdivisiones": len(subs),
                    "stock_total": stock_total
                }

            return {
                "ubicaciones_base": ubicaciones_base,
                "sububicaciones": sububicaciones,
                "productos": productos,
                "sububicaciones_por_padre": sububicaciones_por_padre,
                "productos_por_ubicacion": productos_por_ubicacion,
                "resumen_por_ubicacion": resumen_por_ubicacion
            }

        except Exception as e:
            print(f"Error cargando mapa rack completo: {e}")

            return {
                "ubicaciones_base": [],
                "sububicaciones": [],
                "productos": [],
                "sububicaciones_por_padre": {},
                "productos_por_ubicacion": {},
                "resumen_por_ubicacion": {}
            }

    def crear_subdivisiones_ubicacion(self, ubicacion_padre_id, cantidad=4):
        """
        Crea subdivisiones S01, S02, S03, S04 para un bloque existente.
        """
        data = {
            "ubicacion_padre_id": ubicacion_padre_id,
            "cantidad": cantidad,
            "_modulo": "Ubicaciones",
            "_accion": "Crear subdivisiones",
            "_detalle": (
                f"Se solicitaron {cantidad} subdivisiones para "
                f"la ubicación {ubicacion_padre_id}"
            )
        }
        exito, mensaje, respuesta = self._mutar("crear_subdivisiones", data)
        if not exito:
            return False, mensaje

        creadas = 0
        if isinstance(respuesta, dict):
            creadas = int(respuesta.get("creadas") or 0)
        return True, f"Subdivisiones creadas correctamente. Nuevas: {creadas}"
    
    # ============================================================
    # CONSUMO POR PROYECTO
    # ============================================================
    @staticmethod
    def convertir_importe(valor):
        """Convierte importes de Supabase sin perder sus decimales."""
        if valor is None or valor == "":
            return Decimal("0")
        try:
            return Decimal(str(valor))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    def obtener_resumen_consumo_proyecto(self, nombre_proyecto):
        """
        Devuelve resumen agrupado por producto para un proyecto:
        Producto | Categoría | Cantidad | Precio promedio | Valor total

        Solo considera movimientos que representan salida/consumo real:
        - Entrega / Consumo
        - Entrega de Herramienta Personal
        - Baja por Daño / Merma
        - Corte / Transformación
        """
        try:
            proyecto = self.obtener_proyecto_por_nombre(nombre_proyecto)

            if not proyecto:
                return []

            movimientos_consumo = [
                "Entrega / Consumo",
                "Entrega de Herramienta Personal",
                "Baja por Daño / Merma",
                "Corte / Transformación"
            ]

            res_trans = (
                self.supabase
                .table("transacciones")
                .select("*")
                .eq("proyecto_id", proyecto["id"])
                .in_("tipo_movimiento", movimientos_consumo)
                .order("fecha_hora", desc=True)
                .execute()
            )

            productos = self.cargar_inventario_nube()

            mapa_productos = {
                p["id"]: p
                for p in productos
            }

            resumen = {}

            for mov in res_trans.data or []:
                producto_id = mov.get("producto_id")
                producto = mapa_productos.get(producto_id, {})

                cantidad = int(mov.get("cantidad_movida") or 0)
                precio = self.convertir_importe(
                    mov.get("precio_unitario_movimiento")
                    if mov.get("precio_unitario_movimiento") is not None
                    else producto.get("precio_unitario") or 0
                )
                valor = cantidad * precio

                if producto_id not in resumen:
                    resumen[producto_id] = {
                        "producto": (
                            mov.get("producto_nombre_snapshot")
                            or producto.get("nombre", "-")
                        ),
                        "codigo": (
                            mov.get("producto_codigo_snapshot")
                            or producto.get("codigo_barras", "-")
                        ),
                        "categoria": producto.get("categoria", "-"),
                        "ubicacion": (
                            mov.get("ubicacion_snapshot")
                            or producto.get("ubicacion_codigo", "-")
                        ),
                        "cantidad": 0,
                        "valor_estimado": Decimal("0")
                    }

                resumen[producto_id]["cantidad"] += cantidad
                resumen[producto_id]["valor_estimado"] += valor

            filas = []

            for item in resumen.values():
                precio_promedio = (
                    item["valor_estimado"] / item["cantidad"]
                    if item["cantidad"]
                    else Decimal("0")
                )
                filas.append((
                    item["producto"],
                    item["codigo"],
                    item["categoria"],
                    item["ubicacion"],
                    item["cantidad"],
                    precio_promedio,
                    item["valor_estimado"]
                ))

            filas.sort(key=lambda x: x[4], reverse=True)

            return filas

        except Exception as e:
            print(f"Error obteniendo resumen consumo proyecto: {e}")
            return []

    def obtener_historial_consumo_proyecto(self, nombre_proyecto):
        """
        Devuelve historial detallado de movimientos de consumo por proyecto.
        """
        try:
            proyecto = self.obtener_proyecto_por_nombre(nombre_proyecto)

            if not proyecto:
                return []

            movimientos_consumo = [
                "Entrega / Consumo",
                "Entrega de Herramienta Personal",
                "Baja por Daño / Merma",
                "Corte / Transformación"
            ]

            res_trans = (
                self.supabase
                .table("transacciones")
                .select("*")
                .eq("proyecto_id", proyecto["id"])
                .in_("tipo_movimiento", movimientos_consumo)
                .order("fecha_hora", desc=True)
                .execute()
            )

            productos = self.cargar_inventario_nube()
            trabajadores = self.cargar_trabajadores_nube(solo_activos=False)

            mapa_productos = {
                p["id"]: p
                for p in productos
            }

            mapa_trabajadores = {
                t["id"]: t
                for t in trabajadores
            }

            historial = []

            for mov in res_trans.data or []:
                producto = mapa_productos.get(mov.get("producto_id"), {})
                trabajador = mapa_trabajadores.get(mov.get("trabajador_id"), {})

                fecha = formatear_fecha_hora(mov.get("fecha_hora"))

                cantidad = int(mov.get("cantidad_movida") or 0)
                precio = self.convertir_importe(
                    mov.get("precio_unitario_movimiento")
                    if mov.get("precio_unitario_movimiento") is not None
                    else producto.get("precio_unitario") or 0
                )
                valor = cantidad * precio

                historial.append((
                    fecha,
                    mov.get("producto_nombre_snapshot") or producto.get("nombre", "-"),
                    mov.get("producto_codigo_snapshot") or producto.get("codigo_barras", "-"),
                    mov.get("tipo_movimiento", "-"),
                    cantidad,
                    precio,
                    valor,
                    trabajador.get("nombre", "Sin responsable"),
                    mov.get("ubicacion_snapshot") or producto.get("ubicacion_codigo", "-")
                ))

            return historial

        except Exception as e:
            print(f"Error obteniendo historial consumo proyecto: {e}")
            return []

    def obtener_totales_consumo_proyecto(self, nombre_proyecto):
        try:
            resumen = self.obtener_resumen_consumo_proyecto(nombre_proyecto)

            total_items = len(resumen)
            total_cantidad = 0
            total_valor = 0

            for fila in resumen:
                total_cantidad += int(fila[4] or 0)
                total_valor += self.convertir_importe(fila[6])

            return {
                "productos_distintos": total_items,
                "cantidad_total": total_cantidad,
                "valor_total": total_valor
            }

        except Exception as e:
            print(f"Error calculando totales consumo proyecto: {e}")
            return {
                "productos_distintos": 0,
                "cantidad_total": 0,
                "valor_total": 0
            }   
        
