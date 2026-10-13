from views.tab_registro_epp import RegistroEppTab
from utils.ui_dispatcher import ejecutar_en_ui


class HerramientasPersonalesTab(RegistroEppTab):
    """Historial de herramientas entregadas en forma personal y permanente."""

    TITULO_REGISTRO = "Registro de Herramientas Personales"
    NOMBRE_ELEMENTO = "Herramienta"
    NOMBRE_ELEMENTO_TABLA = "Herramienta entregada"
    CLAVE_ELEMENTO = "herramienta"
    ELEMENTO_DESCONOCIDO = "Herramienta desconocida"
    TEXTO_CARGANDO = "Cargando herramientas personales..."

    def _cargar_pesado(self, carga_id):
        entregas = self.db.obtener_registro_herramientas_personales()
        try:
            ejecutar_en_ui(self, self._actualizar_datos, entregas, carga_id)
        except Exception:
            pass
