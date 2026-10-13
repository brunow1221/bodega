import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_logic import FakeTableSupabase, crear_manager
from utils.fechas import fecha_hora_local, formatear_fecha_hora
from views.tab_registro_epp import RegistroEppTab
from views.tab_terreno import TerrenoTab


class FechasTests(unittest.TestCase):
    def test_hora_reportada_en_invierno(self):
        self.assertEqual(
            formatear_fecha_hora("2026-08-31T12:45:00+00:00"),
            "2026-08-31 08:45",
        )

    def test_verano_no_resta_cuatro_horas_fijas(self):
        self.assertEqual(
            formatear_fecha_hora("2026-01-15T12:45:00Z"),
            "2026-01-15 09:45",
        )

    def test_respeta_offset_local_sin_convertir_dos_veces(self):
        for valor in (
            "2026-08-31T08:45:00-04:00",
            "2026-08-31T12:45:00+00:00",
            "2026-08-31T14:45:00+02:00",
            "2026-08-31T12:45:00.123456Z",
        ):
            with self.subTest(valor=valor):
                self.assertEqual(formatear_fecha_hora(valor), "2026-08-31 08:45")

    def test_cambia_fecha_y_ano_si_corresponde(self):
        self.assertEqual(
            formatear_fecha_hora("2026-01-01T01:30:00Z"),
            "2025-12-31 22:30",
        )

    def test_timestamps_sin_zona_se_interpretan_como_utc(self):
        self.assertEqual(
            formatear_fecha_hora("2026-08-31 12:45:00"),
            "2026-08-31 08:45",
        )

    def test_acepta_datetime_y_formato_de_terreno(self):
        valor = datetime(2026, 8, 31, 12, 45, tzinfo=timezone.utc)
        self.assertEqual(
            formatear_fecha_hora(valor, "%d/%m/%Y %H:%M"),
            "31/08/2026 08:45",
        )
        self.assertEqual(fecha_hora_local(valor).tzinfo.key, "America/Santiago")

    def test_datos_vacios_o_invalidos_no_rompen_la_vista(self):
        for valor in (None, "", "Sin fecha", "no es fecha", "2026-02-30T12:00:00Z"):
            with self.subTest(valor=valor):
                self.assertIsNone(fecha_hora_local(valor))
                self.assertEqual(formatear_fecha_hora(valor), "-")


class HistorialHoraLocalTests(unittest.TestCase):
    def setUp(self):
        self.movimiento = {
            "id": 1,
            "producto_id": "p1",
            "trabajador_id": "t1",
            "proyecto_id": "pr1",
            "tipo_movimiento": "Entrega / Consumo",
            "cantidad_movida": 2,
            "fecha_hora": "2026-08-31T12:45:00+00:00",
        }
        self.manager = crear_manager(
            FakeTableSupabase({"transacciones": [self.movimiento]})
        )
        self.manager.cargar_inventario_nube = lambda: [
            {"id": "p1", "nombre": "Guantes", "categoria": "EPP"}
        ]
        self.manager.cargar_trabajadores_nube = lambda solo_activos=False: [
            {"id": "t1", "nombre": "Ana"}
        ]
        self.manager.cargar_proyectos_completo = lambda: [
            {"id": "pr1", "nombre": "Proyecto A"}
        ]
        self.manager.obtener_proyecto_por_nombre = lambda _: {"id": "pr1"}

    def test_historial_y_ultimos_movimientos_muestran_hora_local(self):
        for obtener in (
            self.manager.obtener_historial_reciente,
            self.manager.obtener_ultimos_movimientos,
        ):
            with self.subTest(metodo=obtener.__name__):
                self.assertEqual(obtener()[0][0], "2026-08-31 08:45")
        self.assertEqual(self.movimiento["fecha_hora"], "2026-08-31T12:45:00+00:00")

    def test_historial_proyecto_muestra_hora_local(self):
        filas = self.manager.obtener_historial_consumo_proyecto("Proyecto A")
        self.assertEqual(filas[0][0], "2026-08-31 08:45")

    def test_registro_epp_muestra_hora_local_y_conserva_timestamp_original(self):
        entrega = self.manager.obtener_registro_entregas_epp()[0]
        self.assertEqual(entrega["fecha"], "2026-08-31 08:45")
        self.assertEqual(entrega["fecha_hora"], self.movimiento["fecha_hora"])

    def test_filtro_epp_usa_dia_local_no_dia_utc(self):
        self.movimiento["fecha_hora"] = "2026-08-31T02:00:00Z"
        entregas = self.manager.obtener_registro_entregas_epp()
        self.assertEqual(entregas[0]["fecha"], "2026-08-30 22:00")
        self.assertEqual(
            RegistroEppTab.filtrar_entregas(entregas, desde="2026-08-30", hasta="2026-08-30"),
            entregas,
        )
        self.assertEqual(
            RegistroEppTab.filtrar_entregas(entregas, desde="2026-08-31"),
            [],
        )

    def test_filtro_epp_no_reconvierte_texto_local_sin_timestamp(self):
        self.assertEqual(
            RegistroEppTab.fecha_de_entrega({"fecha": "2026-08-31 01:00"}),
            date(2026, 8, 31),
        )

    def test_terreno_muestra_hora_local(self):
        tab = SimpleNamespace(
            db=SimpleNamespace(obtener_herramientas_en_terreno=lambda: [self.movimiento]),
            actualizar_interfaz_tabla=lambda filas: None,
        )
        with patch("views.tab_terreno.ejecutar_en_ui") as enviar:
            TerrenoTab.cargar_terreno_pesado(tab)
        filas = enviar.call_args.args[2]
        self.assertEqual(filas[0][4], "31/08/2026 08:45")


if __name__ == "__main__":
    unittest.main()
