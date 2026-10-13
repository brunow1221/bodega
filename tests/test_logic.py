import unittest
import threading
from decimal import Decimal

from database.db_manager import DatabaseManager
from views.tab_mapa_bodega import MapaBodegaTab
from views.tab_salidas import SalidasTab
from views.tab_trabajadores import validar_rut_chileno
from views.tab_consumo_proyecto import ConsumoProyectoTab
from views.tab_registro_epp import RegistroEppTab
from views.tab_inventario import (
    InventarioTab,
    es_producto_aseo,
    es_producto_cafeteria,
    es_producto_libreria,
)
from utils.searchable_combobox import SearchableCombobox
from utils.ui_dispatcher import ejecutar_en_ui, iniciar_despachador_ui
from utils.ui_zoom import normalizar_zoom
from utils.pgp import (
    TIPO_ENTREGA_PGP,
    TIPO_PRESTAMO_PGP,
    cantidad_pendiente_item_pgp,
    preparar_items_pgp,
)


class FakeResponse:
    def __init__(self, data=None):
        self.data = data


class FakeRpcRequest:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class FakeSupabase:
    def __init__(self, rpc_data=None):
        self.rpc_data = rpc_data
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return FakeRpcRequest(FakeResponse(self.rpc_data))


class FlakyRpcRequest:
    def __init__(self, owner):
        self.owner = owner

    def execute(self):
        if self.owner.attempts == 1:
            raise RuntimeError("Server disconnected")
        return FakeResponse({"ok": True})


class FlakySupabase:
    def __init__(self):
        self.attempts = 0
        self.request_ids = []

    def rpc(self, name, params):
        self.attempts += 1
        self.request_ids.append(params.get("p_request_id"))
        return FlakyRpcRequest(self)


class FakeQuery:
    def __init__(self, data):
        self.data = data

    def select(self, *args, **kwargs):
        return self

    def in_(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def range(self, *args, **kwargs):
        return self

    def execute(self):
        return FakeResponse(self.data)


class FakeTableSupabase:
    def __init__(self, table_data):
        self.table_data = table_data

    def table(self, name):
        return FakeQuery(self.table_data[name])


class FakePagedQuery(FakeQuery):
    def __init__(self, data):
        super().__init__(data)
        self.inicio = 0
        self.fin = len(data) - 1

    def range(self, inicio, fin):
        self.inicio = inicio
        self.fin = fin
        return self

    def execute(self):
        return FakeResponse(self.data[self.inicio:self.fin + 1])


class FakePagedTableSupabase(FakeTableSupabase):
    def table(self, name):
        return FakePagedQuery(self.table_data[name])


def crear_manager(supabase, token="token-prueba"):
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.supabase = supabase
    manager.session_token = token
    manager.usuario_actual = {
        "usuario": "admin",
        "nombre": "Administrador",
        "rol": "Administrador"
    }
    manager.migracion_seguridad_disponible = bool(token)
    manager._lock_supabase = threading.RLock()
    manager._reiniciar_cliente_supabase = lambda: None
    return manager


class ValidacionRutTests(unittest.TestCase):
    def test_rut_valido(self):
        self.assertTrue(validar_rut_chileno("12.345.678-5"))

    def test_rut_invalido(self):
        self.assertFalse(validar_rut_chileno("12.345.678-9"))


class RackValidationTests(unittest.TestCase):
    def setUp(self):
        self.tab = MapaBodegaTab.__new__(MapaBodegaTab)

    def test_decimal_opcional(self):
        self.assertEqual(
            self.tab.leer_decimal_opcional("200,5", "ancho"),
            200.5
        )
        self.assertIsNone(self.tab.leer_decimal_opcional("", "ancho"))

    def test_dimension_no_positiva(self):
        with self.assertRaises(ValueError):
            self.tab.leer_decimal_opcional("0", "alto")

    def test_codigos_de_sector(self):
        self.assertEqual(self.tab.codigo_rack_desde_numero(1), "S01")
        self.assertEqual(self.tab.codigo_rack_desde_numero(2), "S02")
        self.assertEqual(self.tab.codigo_rack_desde_numero(12), "S12")
        self.assertEqual(self.tab.codigo_rack_desde_numero(0), "")

    def test_sector_acepta_codigos_descriptivos(self):
        self.assertEqual(
            self.tab.validar_codigo_sector("caf_aseo"),
            "CAF_ASEO"
        )
        with self.assertRaises(ValueError):
            self.tab.validar_codigo_sector("sector con espacios")

    def test_etiqueta_sector_prioriza_nombre(self):
        mapa = self.tab.construir_mapa_etiquetas([
            {"codigo_rack": "APORTES", "nombre": "Aportes"},
            {"codigo_rack": "TUERCAS", "nombre": "Tuercas"},
        ])
        self.assertEqual(list(mapa), ["Aportes", "Tuercas"])

    def test_bodega_principal_se_mantiene_como_predeterminada(self):
        bodegas = [
            {"id": 2, "codigo_bodega": "EXT", "nombre": "Afuera de bodega"},
            {"id": 1, "codigo_bodega": "B1", "nombre": "Bodega 1"},
        ]
        self.assertEqual(
            self.tab.nombre_bodega_predeterminada(bodegas),
            "Bodega 1"
        )

    def test_numero_estante(self):
        self.assertEqual(self.tab.numero_estante("E001"), 1)
        self.assertEqual(self.tab.numero_estante("E010"), 10)

    def test_numeracion_abajo_arriba_y_derecha_izquierda(self):
        self.assertEqual(self.tab.calcular_numero_estante(1, 1, 5), 1)
        self.assertEqual(self.tab.calcular_numero_estante(1, 5, 5), 5)
        self.assertEqual(self.tab.calcular_numero_estante(2, 1, 5), 6)
        self.assertEqual(self.tab.calcular_numero_estante(2, 5, 5), 10)


class RetazoTests(unittest.TestCase):
    def setUp(self):
        self.tab = SalidasTab.__new__(SalidasTab)

    def test_calculo_por_largo(self):
        producto = {
            "precio_unitario": 30000,
            "tipo_medicion": "Largo",
            "medida_largo": 6,
            "medida_ancho": None
        }
        precio, porcentaje = self.tab.calcular_precio_retazo(
            producto,
            cantidad_cortada=1,
            largo_retazo=1.5
        )
        self.assertEqual(precio, 7500)
        self.assertEqual(porcentaje, 25.0)

    def test_retazo_no_puede_superar_material(self):
        producto = {
            "precio_unitario": 30000,
            "tipo_medicion": "Largo",
            "medida_largo": 6,
            "medida_ancho": None
        }
        with self.assertRaises(ValueError):
            self.tab.calcular_precio_retazo(
                producto,
                cantidad_cortada=1,
                largo_retazo=7
            )


class FormatoMedicionTests(unittest.TestCase):
    def test_formato_tubo_se_conserva_al_codificar_y_decodificar(self):
        datos = {
            "formato": "Tubo cuadrado / rectangular",
            "principal": 6,
            "secundaria": 100,
            "adicional": 50,
            "espesor": 3,
            "unidad_principal": "m",
            "unidad_secundaria": "mm",
        }
        texto = InventarioTab.codificar_dimensiones(datos)
        resultado = InventarioTab.decodificar_dimensiones({
            "tamaño_dimensiones": texto,
            "tipo_medicion": "Largo",
            "medida_largo": 6,
            "medida_ancho": None,
            "unidad_medida": "m",
        })

        self.assertEqual(
            resultado["formato"],
            "Tubo cuadrado / rectangular"
        )
        self.assertEqual(resultado["principal"], 6)
        self.assertEqual(resultado["secundaria"], 100)
        self.assertEqual(resultado["adicional"], 50)
        self.assertEqual(resultado["espesor"], 3)
        self.assertEqual(resultado["unidad_secundaria"], "mm")
        self.assertNotIn('"detalle"', texto)

    def test_producto_legacy_por_area_se_muestra_como_plancha(self):
        resultado = InventarioTab.decodificar_dimensiones({
            "tamaño_dimensiones": "Plancha antigua",
            "tipo_medicion": "Área",
            "medida_largo": 2.4,
            "medida_ancho": 1.2,
            "unidad_medida": "m",
        })

        self.assertEqual(resultado["formato"], "Plancha / Malla")
        self.assertEqual(resultado["principal"], 2.4)
        self.assertEqual(resultado["secundaria"], 1.2)

    def test_convierte_ancho_de_milimetros_a_metros(self):
        self.assertAlmostEqual(
            InventarioTab.convertir_entre_unidades(1200, "mm", "m"),
            1.2
        )

    def test_cantidad_editada_debe_ser_entero_no_negativo(self):
        self.assertEqual(InventarioTab.validar_cantidad_edicion("12"), 12)
        self.assertEqual(InventarioTab.validar_cantidad_edicion("0"), 0)

        for valor in ("-1", "2.5", "texto"):
            with self.assertRaisesRegex(ValueError, "número entero"):
                InventarioTab.validar_cantidad_edicion(valor)


class PgpValidationTests(unittest.TestCase):
    def test_prepara_entrega_y_prestamo(self):
        items = [
            {
                "producto": {"id": "p1", "nombre": "Perno", "stock": 20},
                "tipo_movimiento": TIPO_ENTREGA_PGP,
                "cantidad": 10,
            },
            {
                "producto": {"id": "p2", "nombre": "Taladro", "stock": 3},
                "tipo_movimiento": TIPO_PRESTAMO_PGP,
                "cantidad": 1,
            },
        ]
        resultado = preparar_items_pgp(items, "12.345.678-5")
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]["producto_id"], "p1")
        self.assertNotIn("producto", resultado[0])

    def test_prestamo_requiere_responsable(self):
        with self.assertRaisesRegex(ValueError, "responsable"):
            preparar_items_pgp([{
                "producto": {"id": "p1", "nombre": "Taladro", "stock": 2},
                "tipo_movimiento": TIPO_PRESTAMO_PGP,
                "cantidad": 1,
            }])

    def test_no_admite_repetidos_ni_sobrepasar_stock(self):
        producto = {"id": "p1", "nombre": "Perno", "stock": 4}
        with self.assertRaisesRegex(ValueError, "ya está agregado"):
            preparar_items_pgp([
                {
                    "producto": producto,
                    "tipo_movimiento": TIPO_ENTREGA_PGP,
                    "cantidad": 1,
                },
                {
                    "producto": producto,
                    "tipo_movimiento": TIPO_ENTREGA_PGP,
                    "cantidad": 1,
                },
            ])
        with self.assertRaisesRegex(ValueError, "Stock insuficiente"):
            preparar_items_pgp([{
                "producto": producto,
                "tipo_movimiento": TIPO_ENTREGA_PGP,
                "cantidad": 5,
            }])

    def test_calcula_cantidad_pendiente(self):
        self.assertEqual(cantidad_pendiente_item_pgp({
            "cantidad": 5,
            "cantidad_devuelta": 2,
        }), 3)


class SearchableSelectorTests(unittest.TestCase):
    def setUp(self):
        self.productos = [
            {
                "nombre": "Taladro Eléctrico",
                "categoria": "Herramientas",
            },
            {
                "nombre": "Guante de Protección",
                "categoria": "EPP",
            }
        ]

    def test_filtra_por_varias_palabras_y_sin_tildes(self):
        resultado = SearchableCombobox.filtrar(
            self.productos,
            "taladro electrico herramientas",
            SalidasTab.texto_busqueda_producto
        )
        self.assertEqual([p["nombre"] for p in resultado], ["Taladro Eléctrico"])

        resultado = SearchableCombobox.filtrar(
            self.productos,
            "proteccion",
            SalidasTab.texto_busqueda_producto
        )
        self.assertEqual([p["nombre"] for p in resultado], ["Guante de Protección"])

    def test_etiqueta_producto_no_expone_codigo_de_barras(self):
        producto = {
            "nombre": "Taladro",
            "categoria": "Herramientas",
            "stock": 3,
            "codigo_barras": "INTERNO-123"
        }
        etiqueta = SalidasTab.etiqueta_producto(producto)
        self.assertIn("Taladro", etiqueta)
        self.assertIn("Stock 3", etiqueta)
        self.assertNotIn("INTERNO-123", etiqueta)


class DatabaseManagerTests(unittest.TestCase):
    def test_pgp_considera_pendientes_tambien_las_entregas(self):
        manager = crear_manager(FakeTableSupabase({
            "pgp_contenedores": [{
                "id": "pgp-1",
                "fecha_creacion": "2026-09-21T12:00:00Z",
            }],
            "pgp_items": [{
                "id": 1,
                "pgp_id": "pgp-1",
                "creado_en": "2026-09-21T12:30:00Z",
                "producto_id": "p1",
                "producto_nombre": "Perno",
                "tipo_movimiento": TIPO_ENTREGA_PGP,
                "cantidad": 5,
                "cantidad_devuelta": 2,
            }],
        }))

        resultado = manager.cargar_pgp_contenedores()
        pgp = resultado["contenedores"][0]
        self.assertEqual(pgp["items"][0]["cantidad_pendiente"], 3)
        self.assertNotEqual(pgp["items"][0]["fecha_salida"], "-")
        self.assertEqual(pgp["unidades_pendientes"], 3)

    def test_pgp_carga_todas_las_paginas_de_items(self):
        items = [{
            "id": indice,
            "pgp_id": "pgp-1",
            "producto_id": f"p-{indice}",
            "producto_nombre": f"Artículo {indice}",
            "tipo_movimiento": TIPO_ENTREGA_PGP,
            "cantidad": 1,
            "cantidad_devuelta": 0,
        } for indice in range(1, 1002)]
        manager = crear_manager(FakePagedTableSupabase({
            "pgp_contenedores": [{
                "id": "pgp-1",
                "fecha_creacion": "2026-09-21T12:00:00Z",
            }],
            "pgp_items": items,
        }))

        resultado = manager.cargar_pgp_contenedores()

        self.assertEqual(
            resultado["contenedores"][0]["cantidad_items"],
            1001,
        )
        self.assertEqual(
            resultado["contenedores"][0]["unidades_pendientes"],
            1001,
        )

    def test_mutacion_bloqueada_sin_sesion(self):
        manager = crear_manager(FakeSupabase(), token=None)
        exito, mensaje, respuesta = manager._mutar("crear_producto", {})
        self.assertFalse(exito)
        self.assertIsNone(respuesta)
        self.assertIn("migración", mensaje.lower())

    def test_movimiento_usa_rpc_atomica(self):
        supabase = FakeSupabase({"ok": True, "stock_nuevo": 4})
        manager = crear_manager(supabase)
        exito, _ = manager.registrar_movimiento_camara(
            "12345678-5",
            "PRD1",
            "Entrega / Consumo",
            "producto-1",
            999,
            2,
            "Taller Interno"
        )
        self.assertTrue(exito)
        self.assertEqual(supabase.calls[0][0], "registrar_movimiento_app")
        self.assertEqual(supabase.calls[0][1]["p_cantidad"], 2)
        self.assertIsNone(supabase.calls[0][1]["p_comentario"])
        self.assertNotIn("stock_actual", supabase.calls[0][1])

    def test_movimiento_guarda_comentario_opcional_limpio(self):
        supabase = FakeSupabase({"ok": True, "stock_nuevo": 3})
        manager = crear_manager(supabase)
        exito, _ = manager.registrar_movimiento_camara(
            "12345678-5",
            "PRD1",
            "Préstamo de Herramienta",
            "producto-1",
            5,
            2,
            "Taller Interno",
            "  Se entrega con estuche.  "
        )
        self.assertTrue(exito)
        self.assertEqual(
            supabase.calls[0][1]["p_comentario"],
            "Se entrega con estuche."
        )

    def test_movimiento_rechaza_comentario_demasiado_largo(self):
        manager = crear_manager(FakeSupabase())
        exito, mensaje = manager.registrar_movimiento_camara(
            "",
            "PRD1",
            "Entrada / Reposición",
            "producto-1",
            0,
            1,
            "Taller Interno",
            "x" * 1001
        )
        self.assertFalse(exito)
        self.assertIn("1.000", mensaje)

    def test_movimiento_rechaza_cantidad_no_positiva(self):
        manager = crear_manager(FakeSupabase())
        exito, mensaje = manager.registrar_movimiento_camara(
            "",
            "PRD1",
            "Entrada / Reposición",
            "producto-1",
            0,
            0,
            "Taller Interno"
        )
        self.assertFalse(exito)
        self.assertIn("mayor a cero", mensaje)

    def test_crear_pgp_usa_rpc_atomica(self):
        supabase = FakeSupabase({
            "ok": True,
            "pgp_id": "pgp-1",
            "codigo_pgp": "PGP-2026-00001",
        })
        manager = crear_manager(supabase)
        exito, mensaje, datos = manager.crear_pgp(
            "Proyecto Norte",
            "12.345.678-5",
            "Despacho inicial",
            [{
                "producto": {
                    "id": "producto-1",
                    "nombre": "Taladro",
                    "stock": 4,
                },
                "tipo_movimiento": TIPO_PRESTAMO_PGP,
                "cantidad": 2,
            }],
        )
        self.assertTrue(exito)
        self.assertIn("PGP-2026-00001", mensaje)
        self.assertEqual(datos["pgp_id"], "pgp-1")
        nombre_rpc, parametros = supabase.calls[0]
        self.assertEqual(nombre_rpc, "crear_pgp_app")
        self.assertEqual(parametros["p_items"][0]["producto_id"], "producto-1")
        self.assertEqual(parametros["p_items"][0]["cantidad"], 2)

    def test_devolver_pgp_usa_rpc_atomica(self):
        supabase = FakeSupabase({"ok": True, "pendiente_item": 0})
        manager = crear_manager(supabase)
        exito, _ = manager.devolver_item_pgp(
            "pgp-1", 7, 2, "Devuelto con estuche"
        )
        self.assertTrue(exito)
        nombre_rpc, parametros = supabase.calls[0]
        self.assertEqual(nombre_rpc, "devolver_item_pgp_app")
        self.assertEqual(parametros["p_item_id"], 7)
        self.assertEqual(parametros["p_cantidad"], 2)
        self.assertEqual(parametros["p_comentario"], "Devuelto con estuche")

    def test_ampliar_pgp_usa_rpc_atomica_y_conserva_el_codigo(self):
        supabase = FakeSupabase({
            "ok": True,
            "pgp_id": "pgp-1",
            "codigo_pgp": "PGP-2026-00001",
            "unidades_agregadas": 3,
        })
        manager = crear_manager(supabase)
        exito, mensaje, datos = manager.agregar_items_pgp(
            "pgp-1",
            "12.345.678-5",
            "Segunda salida",
            [{
                "producto": {
                    "id": "producto-2",
                    "nombre": "Esmeril",
                    "stock": 5,
                },
                "tipo_movimiento": TIPO_PRESTAMO_PGP,
                "cantidad": 3,
            }],
        )
        self.assertTrue(exito)
        self.assertIn("3 unidades", mensaje)
        self.assertEqual(datos["codigo_pgp"], "PGP-2026-00001")
        nombre_rpc, parametros = supabase.calls[0]
        self.assertEqual(nombre_rpc, "agregar_items_pgp_app")
        self.assertEqual(parametros["p_pgp_id"], "pgp-1")
        self.assertEqual(parametros["p_rut_trabajador"], "12.345.678-5")
        self.assertEqual(parametros["p_observacion"], "Segunda salida")
        self.assertEqual(parametros["p_items"][0]["cantidad"], 3)

    def test_ampliar_pgp_prestamo_sin_responsable_no_llama_rpc(self):
        supabase = FakeSupabase()
        manager = crear_manager(supabase)
        exito, mensaje, datos = manager.agregar_items_pgp(
            "pgp-1",
            "",
            "",
            [{
                "producto": {
                    "id": "producto-2",
                    "nombre": "Esmeril",
                    "stock": 5,
                },
                "tipo_movimiento": TIPO_PRESTAMO_PGP,
                "cantidad": 1,
            }],
        )
        self.assertFalse(exito)
        self.assertIn("responsable", mensaje)
        self.assertIsNone(datos)
        self.assertEqual(supabase.calls, [])

    def test_devolver_pgp_completo_usa_una_sola_rpc_atomica(self):
        supabase = FakeSupabase({"ok": True, "unidades_devueltas": 8})
        manager = crear_manager(supabase)
        exito, mensaje = manager.devolver_pgp_completo(
            "pgp-1", "Retorno del contenedor"
        )
        self.assertTrue(exito)
        self.assertIn("8 unidades", mensaje)
        self.assertEqual(len(supabase.calls), 1)
        nombre_rpc, parametros = supabase.calls[0]
        self.assertEqual(nombre_rpc, "devolver_pgp_completo_app")
        self.assertEqual(parametros["p_pgp_id"], "pgp-1")
        self.assertEqual(
            parametros["p_comentario"], "Retorno del contenedor"
        )

    def test_crear_producto_usa_rpc_compatible(self):
        supabase = FakeSupabase({"ok": True, "id": "producto-1"})
        manager = crear_manager(supabase)

        exito, _ = manager.guardar_producto_nube(
            "PRD1",
            "",
            "Plancha",
            "Materiales",
            "",
            2,
            15000,
        )

        self.assertTrue(exito)
        nombre_rpc, parametros = supabase.calls[0]
        self.assertEqual(nombre_rpc, "crear_producto_app")
        self.assertEqual(parametros["p_datos"]["nombre"], "Plancha")
        self.assertEqual(parametros["p_datos"]["stock"], 2)
        for campo_retirado in ("marca", "subcategoria", "talla"):
            self.assertNotIn(campo_retirado, parametros["p_datos"])

    def test_editar_cantidad_usa_rpc_de_ajuste_seguro(self):
        supabase = FakeSupabase({
            "ok": True,
            "stock_anterior": 3,
            "stock_nuevo": 8
        })
        manager = crear_manager(supabase)

        exito, _ = manager.actualizar_producto_nube(
            "producto-1",
            {"nombre": "Resma", "stock": 8, "stock_minimo": 2}
        )

        self.assertTrue(exito)
        nombre_rpc, parametros = supabase.calls[0]
        self.assertEqual(nombre_rpc, "actualizar_producto_stock_app")
        self.assertEqual(parametros["p_datos"]["id"], "producto-1")
        self.assertEqual(parametros["p_datos"]["stock"], 8)

    def test_reintento_conserva_request_id(self):
        supabase = FlakySupabase()
        manager = crear_manager(supabase)
        exito, _, _ = manager._mutar("crear_producto", {"nombre": "Prueba"})
        self.assertTrue(exito)
        self.assertEqual(supabase.attempts, 2)
        self.assertEqual(supabase.request_ids[0], supabase.request_ids[1])

    def test_gestionar_rack_usa_rpc_segura(self):
        supabase = FakeSupabase({"ok": True, "id": 8})
        manager = crear_manager(supabase)
        exito, _ = manager.gestionar_rack(
            "crear",
            {
                "bodega_id": 1,
                "codigo_rack": "A",
                "niveles": 4,
                "columnas": 5
            }
        )
        self.assertTrue(exito)
        nombre, parametros = supabase.calls[0]
        self.assertEqual(nombre, "gestionar_rack_app")
        self.assertEqual(parametros["p_accion"], "crear")
        self.assertEqual(parametros["p_datos"]["columnas"], 5)
        self.assertTrue(parametros["p_request_id"])

    def test_herramientas_mantiene_cantidad_pendiente(self):
        movimientos = [
            {
                "producto_id": "p1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Préstamo de Herramienta",
                "cantidad_movida": 3,
                "fecha_hora": "2026-01-01T10:00:00"
            },
            {
                "producto_id": "p1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Devolución de Herramienta",
                "cantidad_movida": 1,
                "fecha_hora": "2026-01-02T10:00:00"
            }
        ]
        manager = crear_manager(
            FakeTableSupabase({"transacciones": movimientos})
        )
        manager.cargar_inventario_nube = lambda: [
            {"id": "p1", "nombre": "Taladro"}
        ]
        manager.cargar_trabajadores_nube = lambda solo_activos=False: [
            {"id": "t1", "nombre": "Ana"}
        ]
        manager.cargar_proyectos_completo = lambda: [
            {"id": "pr1", "nombre": "Proyecto A"}
        ]

        resultado = manager.obtener_herramientas_en_terreno()
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["nombre_producto"], "Taladro")
        self.assertEqual(resultado[0]["cantidad_pendiente"], 2)
        self.assertEqual(resultado[0]["nombre_proyecto"], "Proyecto A")

    def test_devolucion_pgp_de_consumo_no_descuenta_herramientas(self):
        movimientos = [
            {
                "id": "salida-prestamo",
                "producto_id": "p1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": TIPO_PRESTAMO_PGP,
                "cantidad_movida": 3,
                "fecha_hora": "2026-01-01T10:00:00",
            },
            {
                "id": "devolucion-consumo",
                "producto_id": "p1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Devolución PGP",
                "cantidad_movida": 2,
                "fecha_hora": "2026-01-02T10:00:00",
            },
            {
                "id": "devolucion-prestamo",
                "producto_id": "p1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Devolución PGP",
                "cantidad_movida": 1,
                "fecha_hora": "2026-01-03T10:00:00",
            },
        ]
        manager = crear_manager(FakeTableSupabase({
            "transacciones": movimientos,
            "pgp_items": [
                {"id": 10, "tipo_movimiento": TIPO_ENTREGA_PGP},
                {"id": 11, "tipo_movimiento": TIPO_PRESTAMO_PGP},
            ],
            "pgp_devoluciones": [
                {
                    "id": 1,
                    "pgp_item_id": 10,
                    "transaccion_id": "devolucion-consumo",
                },
                {
                    "id": 2,
                    "pgp_item_id": 11,
                    "transaccion_id": "devolucion-prestamo",
                },
            ],
        }))
        manager.cargar_inventario_nube = lambda: [
            {"id": "p1", "nombre": "Taladro"}
        ]
        manager.cargar_trabajadores_nube = lambda solo_activos=False: [
            {"id": "t1", "nombre": "Ana"}
        ]
        manager.cargar_proyectos_completo = lambda: [
            {"id": "pr1", "nombre": "Proyecto A"}
        ]

        resultado = manager.obtener_herramientas_en_terreno()

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["cantidad_pendiente"], 2)

    def test_registro_epp_solo_incluye_entregas_de_epp(self):
        movimientos = [
            {
                "id": 1,
                "producto_id": "epp1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Entrega / Consumo",
                "cantidad_movida": 2,
                "fecha_hora": "2026-08-20T10:30:00",
                "producto_nombre_snapshot": "Guante histórico",
                "creado_por_usuario": "Bruno (bruno)",
            },
            {
                "id": 2,
                "producto_id": "h1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Entrega / Consumo",
                "cantidad_movida": 1,
                "fecha_hora": "2026-08-20T11:00:00",
            },
            {
                "id": 3,
                "producto_id": "epp1",
                "trabajador_id": "t1",
                "proyecto_id": "pr1",
                "tipo_movimiento": "Baja por Daño / Merma",
                "cantidad_movida": 1,
                "fecha_hora": "2026-08-20T12:00:00",
            },
        ]
        manager = crear_manager(
            FakeTableSupabase({"transacciones": movimientos})
        )
        manager.cargar_inventario_nube = lambda: [
            {
                "id": "epp1",
                "nombre": "Guante actual",
                "categoria": "EPP",
            },
            {"id": "h1", "nombre": "Taladro", "categoria": "Herramientas"},
        ]
        manager.cargar_trabajadores_nube = lambda solo_activos=False: [
            {"id": "t1", "nombre": "Ana", "rut": "12.345.678-5"}
        ]
        manager.cargar_proyectos_completo = lambda: [
            {"id": "pr1", "nombre": "Proyecto A"}
        ]

        resultado = manager.obtener_registro_entregas_epp()

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["epp"], "Guante histórico")
        self.assertEqual(resultado[0]["trabajador"], "Ana")
        self.assertEqual(resultado[0]["cantidad"], 2)
        self.assertEqual(resultado[0]["proyecto"], "Proyecto A")


class RegistroEppTests(unittest.TestCase):
    def setUp(self):
        self.entregas = [
            {
                "fecha_hora": "2026-08-20T10:30:00",
                "fecha": "2026-08-20 10:30",
                "trabajador": "José Pérez",
                "rut": "12.345.678-5",
                "epp": "Guante anticorte",
                "cantidad": 2,
                "proyecto": "Proyecto Norte",
                "entregado_por": "Bruno",
                "comentario": "-",
            },
            {
                "fecha_hora": "2026-08-10T09:00:00",
                "fecha": "2026-08-10 09:00",
                "trabajador": "Ana Soto",
                "rut": "9.999.999-9",
                "epp": "Casco",
                "cantidad": 1,
                "proyecto": "Taller Interno",
                "entregado_por": "Bruno",
                "comentario": "Reposición",
            },
        ]

    def test_busqueda_sin_tildes_y_filtro_de_fecha(self):
        resultado = RegistroEppTab.filtrar_entregas(
            self.entregas,
            texto="jose guante",
            desde="2026-08-15",
            hasta="2026-08-20",
        )
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["trabajador"], "José Pérez")

    def test_rechaza_rango_de_fechas_invertido(self):
        with self.assertRaises(ValueError):
            RegistroEppTab.filtrar_entregas(
                self.entregas,
                desde="2026-08-21",
                hasta="2026-08-20",
            )


class DespachadorUiTests(unittest.TestCase):
    def test_hilo_solo_encola_y_callback_se_ejecuta_al_procesar(self):
        class WidgetFalso:
            def __init__(self):
                self.callbacks = []

            def after(self, _demora, callback):
                self.callbacks.append(callback)

            def winfo_exists(self):
                return True

        widget = WidgetFalso()
        resultados = []
        iniciar_despachador_ui(widget)
        ejecutar_en_ui(widget, resultados.append, "ok")

        self.assertEqual(resultados, [])
        widget.callbacks.pop(0)()
        self.assertEqual(resultados, ["ok"])


class ConsumoProyectoTests(unittest.TestCase):
    def test_resumen_conserva_decimales_y_precio_promedio(self):
        movimientos = [
            {
                "producto_id": "p1",
                "cantidad_movida": 2,
                "precio_unitario_movimiento": "1250.50",
                "producto_nombre_snapshot": "Cable",
                "producto_codigo_snapshot": "CAB1",
                "ubicacion_snapshot": "B1-A-N01"
            },
            {
                "producto_id": "p1",
                "cantidad_movida": 1,
                "precio_unitario_movimiento": "1000.25",
                "producto_nombre_snapshot": "Cable",
                "producto_codigo_snapshot": "CAB1",
                "ubicacion_snapshot": "B1-A-N01"
            }
        ]
        manager = crear_manager(
            FakeTableSupabase({"transacciones": movimientos})
        )
        manager.obtener_proyecto_por_nombre = lambda nombre: {"id": "pr1"}
        manager.cargar_inventario_nube = lambda: [
            {
                "id": "p1",
                "nombre": "Cable",
                "codigo_barras": "CAB1",
                "categoria": "Materiales",
                "precio_unitario": 999
            }
        ]

        fila = manager.obtener_resumen_consumo_proyecto("Proyecto A")[0]

        self.assertEqual(fila[4], 3)
        self.assertEqual(fila[5], Decimal("1167.083333333333333333333333"))
        self.assertEqual(fila[6], Decimal("3501.25"))

    def test_formato_pesos_no_trunca_centavos(self):
        tab = ConsumoProyectoTab.__new__(ConsumoProyectoTab)
        self.assertEqual(tab.formatear_pesos("1234.50"), "$1.234,50")
        self.assertEqual(tab.formatear_pesos("2500"), "$2.500")

    def test_articulos_utilizados_se_agrupan_por_nombre(self):
        resumen = [
            ("Paños", "P1", "Aseo", "B1", 10, 0, 0),
            ("panos", "P2", "Aseo", "B2", 20, 0, 0),
            ("Aportes", "A1", "Materiales", "B1", 300, 0, 0),
        ]

        texto = ConsumoProyectoTab.formatear_articulos_utilizados(resumen)

        self.assertIn("Paños × 30", texto)
        self.assertIn("Aportes × 300", texto)

    def test_articulos_utilizados_muestra_estado_vacio(self):
        texto = ConsumoProyectoTab.formatear_articulos_utilizados([])

        self.assertEqual(
            texto,
            "Sin consumos registrados para este proyecto."
        )


class ZoomInterfazTests(unittest.TestCase):
    def test_zoom_se_ajusta_en_pasos_de_diez(self):
        self.assertEqual(normalizar_zoom(126), 130)
        self.assertEqual(normalizar_zoom("114"), 110)

    def test_zoom_respeta_limites_y_valor_predeterminado(self):
        self.assertEqual(normalizar_zoom(20), 80)
        self.assertEqual(normalizar_zoom(500), 160)
        self.assertEqual(normalizar_zoom("invalido"), 100)


class InventarioCafeteriaTests(unittest.TestCase):
    def test_reconoce_solo_cafeteria_y_comida(self):
        self.assertTrue(es_producto_cafeteria({"categoria": "Cafetería"}))
        self.assertTrue(es_producto_cafeteria({"categoria": "Comida"}))
        self.assertFalse(es_producto_cafeteria({"categoria": "Aseo"}))
        self.assertFalse(es_producto_cafeteria({"categoria": "Limpieza"}))
        self.assertTrue(es_producto_cafeteria({"categoria": "Alimentos"}))
        self.assertFalse(es_producto_cafeteria({
            "categoria": "Insumos",
            "subcategoria": "Cafetería",
        }))

    def test_no_incluye_productos_de_otras_clasificaciones(self):
        self.assertFalse(es_producto_cafeteria({
            "nombre": "Cafetera eléctrica",
            "categoria": "Equipos",
        }))

    def test_formulario_cafeteria_fija_su_categoria(self):
        vista = InventarioTab.__new__(InventarioTab)
        vista.solo_cafeteria = True

        self.assertEqual(
            vista.obtener_categorias_formulario(),
            ["Cafetería"]
        )


class InventarioAseoTests(unittest.TestCase):
    def test_reconoce_solo_aseo_limpieza_e_higiene(self):
        self.assertTrue(es_producto_aseo({"categoria": "Aseo"}))
        self.assertTrue(es_producto_aseo({"categoria": "Limpieza"}))
        self.assertTrue(es_producto_aseo({"categoria": "Higiene"}))
        self.assertFalse(es_producto_aseo({"categoria": "Cafetería"}))
        self.assertFalse(es_producto_aseo({
            "categoria": "Insumos",
            "subcategoria": "Aseo",
        }))

    def test_clasificacion_legacy_no_duplica_producto(self):
        producto = {"categoria": "Cafetería/Aseo"}
        self.assertTrue(es_producto_cafeteria(producto))
        self.assertFalse(es_producto_aseo(producto))

    def test_formulario_aseo_fija_su_categoria(self):
        vista = InventarioTab.__new__(InventarioTab)
        vista.solo_cafeteria = False
        vista.solo_aseo = True
        vista.solo_libreria = False

        self.assertEqual(vista.obtener_categorias_formulario(), ["Aseo"])


class InventarioLibreriaTests(unittest.TestCase):
    def test_reconoce_categoria_de_libreria(self):
        self.assertTrue(es_producto_libreria({"categoria": "Librería"}))
        self.assertTrue(es_producto_libreria({"categoria": "Papelería"}))
        self.assertTrue(es_producto_libreria({"categoria": "Útiles de oficina"}))

    def test_no_incluye_productos_de_otras_clasificaciones(self):
        self.assertFalse(es_producto_libreria({
            "nombre": "Estante para libros",
            "categoria": "Muebles",
        }))

    def test_formulario_libreria_fija_su_categoria(self):
        vista = InventarioTab.__new__(InventarioTab)
        vista.solo_cafeteria = False
        vista.solo_libreria = True

        self.assertEqual(vista.obtener_categorias_formulario(), ["Librería"])


if __name__ == "__main__":
    unittest.main()
