import time
from uuid import uuid4

from supabase import create_client, Client


class DatabaseManager:
    def __init__(self, url, key):
        self.supabase: Client = create_client(url, key)
        self.session_token = None
        self.usuario_actual = None
        self.migracion_seguridad_disponible = False
        self.migracion_racks_disponible = False

    def verificar_migracion_racks(self):
        try:
            (
                self.supabase
                .table("racks")
                .select(
                    "id,ancho_cm,alto_cm,profundidad_cm,"
                    "capacidad_kg,posicion_orden"
                )
                .limit(1)
                .execute()
            )
            self.migracion_racks_disponible = True
        except Exception:
            self.migracion_racks_disponible = False
        return self.migracion_racks_disponible

    def _ejecutar_con_reintentos(self, operacion, intentos=3):
        ultimo_error = None
        marcadores_transitorios = (
            "timeout",
            "timed out",
            "server disconnected",
            "connection",
            "temporarily unavailable",
            "remote protocol error",
            "502",
            "503",
            "504"
        )

        for intento in range(intentos):
            try:
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
                time.sleep(0.4 * (2 ** intento))

        raise ultimo_error

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
            res = self.supabase.table("config_app").select("*").execute()

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
            res = (
                self.supabase
                .table("bodegas")
                .select("*")
                .eq("estado", "Activo")
                .order("nombre")
                .execute()
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
                res = construir_query(con_posicion=True).execute()
            except Exception as e:
                if "posicion_orden" not in str(e):
                    raise
                res = construir_query(con_posicion=False).execute()
            return res.data

        except Exception as e:
            print(f"Error cargando racks: {e}")
            return []

    def cargar_ubicaciones(self, rack_id=None, solo_activas=True):
        try:
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

            res = query.execute()
            return res.data

        except Exception as e:
            print(f"Error cargando ubicaciones: {e}")
            return []

    def cargar_ubicaciones_lista(self):
        """
        Devuelve lista simple para combos.
        """
        try:
            res = (
                self.supabase
                .table("ubicaciones")
                .select("id, codigo_ubicacion, tipo, estado")
                .eq("estado", "Activo")
                .order("codigo_ubicacion")
                .execute()
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
            request_id = str(uuid4())
            self._ejecutar_con_reintentos(
                lambda: self.supabase.rpc(
                    "gestionar_rack_app",
                    {
                        "p_token": self.session_token,
                        "p_request_id": request_id,
                        "p_accion": accion,
                        "p_datos": datos
                    }
                ).execute()
            )
            return True, "Rack actualizado correctamente."
        except Exception as e:
            return False, str(e)

    def crear_rack(
        self,
        bodega_id,
        codigo_rack,
        nombre="",
        descripcion="",
        niveles=3,
        columnas=3,
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
            "columnas": columnas,
            "ancho_cm": ancho_cm,
            "alto_cm": alto_cm,
            "profundidad_cm": profundidad_cm,
            "capacidad_kg": capacidad_kg,
            "posicion_orden": posicion_orden
        }
        exito, mensaje = self.gestionar_rack("crear", data)
        if exito:
            return True, "Rack creado correctamente."
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
            res = (
                self.supabase
                .table("proyectos")
                .select("nombre")
                .eq("estado", "Activo")
                .order("nombre")
                .execute()
            )

            if res.data:
                return [p["nombre"] for p in res.data]

            return ["Taller Interno"]

        except Exception as e:
            print(f"Error cargando proyectos: {e}")
            return ["Taller Interno"]

    def cargar_proyectos_completo(self):
        try:
            res = (
                self.supabase
                .table("proyectos")
                .select("*")
                .order("nombre")
                .execute()
            )

            return res.data

        except Exception as e:
            print(f"Error cargando proyectos completos: {e}")
            return []

    def obtener_proyecto_por_nombre(self, nombre):
        try:
            res = (
                self.supabase
                .table("proyectos")
                .select("*")
                .eq("nombre", nombre)
                .execute()
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
            "fecha_fin": fecha_fin,
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
    def obtener_nombre_trabajador(self, codigo_qr):
        try:
            respuesta = (
                self.supabase
                .table("trabajadores")
                .select("nombre")
                .eq("rut", codigo_qr)
                .execute()
            )

            return respuesta.data[0]["nombre"] if respuesta.data else None

        except Exception as e:
            print(f"Error al validar trabajador: {e}")
            return None

    def cargar_trabajadores_nube(self, solo_activos=True):
        try:
            query = (
                self.supabase
                .table("trabajadores")
                .select("*")
                .order("nombre")
            )
            if solo_activos:
                query = query.eq("estado", "Activo")
            respuesta = query.execute()

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
            res = (
                self.supabase
                .table("trabajadores")
                .select("*")
                .eq("rut", rut)
                .eq("estado", "Activo")
                .execute()
            )

            return res.data[0] if res.data else None

        except Exception as e:
            print(f"Error buscando trabajador: {e}")
            return None

    # ============================================================
    # PRODUCTOS / INVENTARIO
    # ============================================================
    def cargar_inventario_nube(self):
        try:
            respuesta = self.supabase.table("productos").select("*").execute()

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
            return []

    def cargar_inactivos_nube(self):
        try:
            respuesta = (
                self.supabase
                .table("productos")
                .select("*")
                .eq("estado", "Inactivo")
                .order("id")
                .execute()
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
        subcategoria,
        tamano,
        talla,
        stock,
        precio_unitario=0,
        ubicacion_id=None,
        stock_minimo=0,
        marca="",
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
            "subcategoria": subcategoria,
            "marca": marca,
            "tamaño_dimensiones": tamano,
            "talla": talla,
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
        exito, mensaje, _ = self._mutar("crear_producto", data)
        if exito:
            return True, "Producto guardado correctamente."
        return False, mensaje

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
        exito, mensaje, respuesta = self._mutar("crear_retazo", payload)
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
            "subcategoria",
            "marca",
            "tamaño_dimensiones",
            "talla",
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
        exito, mensaje, _ = self._mutar("actualizar_producto", datos_limpios)
        if exito:
            return True, "Producto actualizado con éxito."
        return False, mensaje

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
        proyecto="Taller Interno"
    ):
        sesion_ok, mensaje = self._requiere_sesion()
        if not sesion_ok:
            return False, mensaje

        try:
            cantidad = int(cantidad_movida)
            if cantidad <= 0:
                return False, "La cantidad debe ser mayor a cero."

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
                        "p_comentario": None
                    }
                ).execute()
            )
            return True, "Movimiento registrado."
        except Exception as e:
            return False, str(e)

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
                fecha_cruda = t.get("fecha_hora") or ""

                if fecha_cruda:
                    fecha_limpia = str(fecha_cruda)[:16].replace("T", " ")
                else:
                    fecha_limpia = "-"

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
                fecha_cruda = t.get("fecha_hora") or "Sin fecha"

                if fecha_cruda != "Sin fecha":
                    fecha_limpia = str(fecha_cruda)[:16].replace("T", " ")
                else:
                    fecha_limpia = "-"

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

    # ============================================================
    # HERRAMIENTAS EN TERRENO
    # ============================================================
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
                        "Devolución de Herramienta"
                    ]
                )
                .order("fecha_hora")
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

            estado_herramientas = {}

            for m in movimientos.data:
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

                elif m.get("tipo_movimiento") == "Devolución de Herramienta":
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
    def obtener_resumen_consumo_proyecto(self, nombre_proyecto):
        """
        Devuelve resumen agrupado por producto para un proyecto:
        Producto | Categoría | Cantidad consumida | Valor estimado

        Solo considera movimientos que representan salida/consumo real:
        - Entrega / Consumo
        - Baja por Daño / Merma
        - Corte / Transformación
        """
        try:
            proyecto = self.obtener_proyecto_por_nombre(nombre_proyecto)

            if not proyecto:
                return []

            movimientos_consumo = [
                "Entrega / Consumo",
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
                precio = int(
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
                        "valor_estimado": 0
                    }

                resumen[producto_id]["cantidad"] += cantidad
                resumen[producto_id]["valor_estimado"] += valor

            filas = []

            for item in resumen.values():
                filas.append((
                    item["producto"],
                    item["codigo"],
                    item["categoria"],
                    item["ubicacion"],
                    item["cantidad"],
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

                fecha_cruda = mov.get("fecha_hora") or ""

                if fecha_cruda:
                    fecha = str(fecha_cruda)[:16].replace("T", " ")
                else:
                    fecha = "-"

                cantidad = int(mov.get("cantidad_movida") or 0)
                precio = int(
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
                total_valor += int(fila[5] or 0)

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
        
