import os
import sys

def obtener_ruta_recurso(ruta_relativa):
    """ Obtiene la ruta absoluta para recursos (iconos, logos), compatible con .exe """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, ruta_relativa)

def obtener_ruta_icono(nombre_icono="icono.ico"):
    """ Retorna la ruta completa al icono dentro de la carpeta assets """
    return obtener_ruta_recurso(os.path.join("assets", nombre_icono))
