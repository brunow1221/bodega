import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from utils.importador_precios import (
    leer_precios_referenciales,
    preparar_actualizaciones_precios,
)


class ImportadorPreciosTests(unittest.TestCase):
    def test_importa_aunque_haya_un_numpy_incompleto(self):
        with tempfile.TemporaryDirectory() as temporal:
            paquete_numpy = Path(temporal) / "numpy"
            paquete_numpy.mkdir()
            (paquete_numpy / "__init__.py").write_text(
                "__version__ = 'incompleto'\n",
                encoding="utf-8",
            )
            entorno = os.environ.copy()
            raiz_proyecto = str(Path(__file__).resolve().parents[1])
            entorno["PYTHONPATH"] = os.pathsep.join([
                temporal,
                raiz_proyecto,
            ])

            resultado = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import utils.importador_precios; print('IMPORT_OK')",
                ],
                cwd=raiz_proyecto,
                env=entorno,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )

        self.assertEqual(
            resultado.returncode,
            0,
            msg=resultado.stderr,
        )
        self.assertIn("IMPORT_OK", resultado.stdout)

    def crear_excel(self, filas):
        temporal = tempfile.TemporaryDirectory()
        ruta = Path(temporal.name) / "precios.xlsx"
        libro = Workbook()
        hoja = libro.active
        hoja.title = "Precios referenciales"
        hoja.append([
            "Producto original",
            "Stock",
            "Precio referencial CLP",
            "Valor stock CLP",
        ])
        for fila in filas:
            hoja.append(fila)
        libro.save(ruta)
        return temporal, ruta

    def test_usa_precio_referencial_y_no_valor_total_stock(self):
        temporal, ruta = self.crear_excel([
            ["Taladro", 3, 125000, 375000],
            ["Producto sin precio", 10, None, None],
        ])
        try:
            datos = leer_precios_referenciales(ruta)
        finally:
            temporal.cleanup()

        self.assertEqual(datos["filas_revisadas"], 2)
        self.assertEqual(datos["con_precio"], 1)
        self.assertEqual(datos["sin_precio"], 1)
        self.assertEqual(datos["filas"][0]["precio_referencial"], 125000)

    def test_prepara_solo_coincidencias_unicas_activas_y_en_cero(self):
        datos = {
            "filas": [
                {"fila": 2, "nombre": "Taladro Makita", "precio_referencial": 100000},
                {"fila": 3, "nombre": "Casco", "precio_referencial": 15000},
                {"fila": 4, "nombre": "Sin coincidencia", "precio_referencial": 5000},
                {"fila": 5, "nombre": "Spray negro", "precio_referencial": 4000},
            ],
            "filas_revisadas": 4,
            "con_precio": 4,
            "sin_precio": 0,
        }
        productos = [
            {"id": 1, "nombre": "TALADRO MÁKITA", "precio_unitario": 0, "estado": "Activo"},
            {"id": 2, "nombre": "Casco", "precio_unitario": 12000, "estado": "Activo"},
            {"id": 3, "nombre": "Spray negro", "precio_unitario": 0, "estado": "Inactivo"},
        ]

        plan = preparar_actualizaciones_precios(datos, productos)

        self.assertEqual(len(plan["actualizaciones"]), 2)
        self.assertEqual(plan["actualizaciones"][0]["producto_id"], 1)
        self.assertEqual(plan["actualizaciones"][0]["precio"], 100000)
        self.assertEqual(len(plan["ya_valorizados"]), 1)
        self.assertEqual(len(plan["sin_coincidencia"]), 1)
        self.assertEqual(len(plan["inactivos"]), 1)

    def test_rechaza_productos_repetidos_en_excel(self):
        temporal, ruta = self.crear_excel([
            ["Llave 10 mm", 1, 1000, 1000],
            ["LLAVE 10 MM", 2, 1100, 2200],
        ])
        try:
            with self.assertRaisesRegex(ValueError, "repetidos"):
                leer_precios_referenciales(ruta)
        finally:
            temporal.cleanup()


if __name__ == "__main__":
    unittest.main()
