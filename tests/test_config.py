import os
import unittest
from unittest.mock import patch

from config import (
    SUPABASE_PUBLISHABLE_KEY_PREDETERMINADA,
    SUPABASE_URL_PREDETERMINADA,
    _obtener_configuracion,
)


class ConfiguracionTests(unittest.TestCase):
    def test_usa_configuracion_publica_sin_archivo_env(self):
        with patch.dict(os.environ, {}, clear=True):
            url = _obtener_configuracion(
                "SUPABASE_URL",
                SUPABASE_URL_PREDETERMINADA,
            )
            clave = _obtener_configuracion(
                "SUPABASE_PUBLISHABLE_KEY",
                SUPABASE_PUBLISHABLE_KEY_PREDETERMINADA,
            )

        self.assertTrue(url.startswith("https://"))
        self.assertTrue(clave.startswith("sb_publishable_"))

    def test_variable_de_entorno_sobrescribe_valor_predeterminado(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "https://otro.example"}):
            valor = _obtener_configuracion(
                "SUPABASE_URL",
                SUPABASE_URL_PREDETERMINADA,
            )

        self.assertEqual(valor, "https://otro.example")


if __name__ == "__main__":
    unittest.main()
