import os
import sys

from config import KEY_SUPABASE, URL_SUPABASE
from database.db_manager import DatabaseManager


def ocultar_key(key):
    if not key:
        return "(vacia)"
    return f"{key[:12]}...{key[-6:]}"


def contar(nombre, funcion):
    try:
        datos = funcion() or []
        print(f"{nombre}: OK ({len(datos)} filas)")
    except Exception as e:
        print(f"{nombre}: ERROR {type(e).__name__}: {e}")


def main():
    print("=== Diagnostico conexion app bodega ===")
    print(f"Python: {sys.executable}")
    print(f"Carpeta actual: {os.getcwd()}")
    print(f"SUPABASE_URL: {URL_SUPABASE}")
    print(f"SUPABASE_PUBLISHABLE_KEY: {ocultar_key(KEY_SUPABASE)}")

    os.environ["DEBUG_DB"] = "1"
    db = DatabaseManager(URL_SUPABASE, KEY_SUPABASE)

    contar("bodegas", db.cargar_bodegas)
    contar("racks", db.cargar_racks)
    contar("ubicaciones", db.cargar_ubicaciones)
    contar("productos", db.cargar_inventario_nube)
    contar("proyectos", db.cargar_proyectos_completo)
    contar("trabajadores", db.cargar_trabajadores_nube)


if __name__ == "__main__":
    main()
