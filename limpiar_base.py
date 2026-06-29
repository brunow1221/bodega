import os
from supabase import create_client, Client

URL_SUPABASE = os.environ.get("SUPABASE_URL", "").strip()
KEY_SUPABASE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
supabase: Client | None = None


def crear_cliente_seguro():
    if not URL_SUPABASE or not KEY_SUPABASE:
        raise RuntimeError(
            "Defina SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY antes de ejecutar "
            "una limpieza destructiva."
        )
    if KEY_SUPABASE.startswith("sb_publishable"):
        raise RuntimeError("La limpieza requiere una service role key, no una clave pública.")
    return create_client(URL_SUPABASE, KEY_SUPABASE)


def contar_registros():
    """Muestra cuántos registros hay antes o después de limpiar."""
    try:
        productos = supabase.table("productos").select("id", count="exact").execute()
        trabajadores = supabase.table("trabajadores").select("id", count="exact").execute()
        transacciones = supabase.table("transacciones").select("id", count="exact").execute()

        print("\n📊 Estado actual de la base:")
        print(f"  - Productos: {productos.count}")
        print(f"  - Trabajadores: {trabajadores.count}")
        print(f"  - Transacciones: {transacciones.count}")

    except Exception as e:
        print(f"⚠️ No se pudieron contar los registros: {e}")


def vaciar_base_de_datos():
    print("🧹 Vaciando datos operativos de la base de datos...")

    try:
        # Primero transacciones, porque dependen de productos y trabajadores
        supabase.table("transacciones").delete().gt("id", -1).execute()
        print("  ✅ Transacciones eliminadas.")

        # Luego trabajadores
        supabase.table("trabajadores").delete().gt("id", -1).execute()
        print("  ✅ Trabajadores eliminados.")

        # Finalmente productos
        supabase.table("productos").delete().gt("id", 0).execute()
        print("  ✅ Productos eliminados.")

        print("\n✨ Base de datos limpia.")
        print("No se eliminaron config_app ni proyectos.")

    except Exception as e:
        print(f"\n⚠️ Error al vaciar la base de datos: {e}")
        print("Revisa permisos RLS para DELETE en Supabase.")


if __name__ == "__main__":
    supabase = crear_cliente_seguro()
    print("========================================")
    print(" LIMPIEZA DE BASE DE DATOS - BODEGA")
    print("========================================")

    contar_registros()

    print("\n⚠️ Esta acción eliminará:")
    print("  - Productos")
    print("  - Trabajadores")
    print("  - Transacciones")
    print("\nNo eliminará:")
    print("  - config_app")
    print("  - proyectos")

    print(f"\nProyecto objetivo: {URL_SUPABASE}")
    confirmacion = input(
        "\nEscribe la URL completa del proyecto para confirmar la limpieza: "
    ).strip()

    if confirmacion == URL_SUPABASE:
        vaciar_base_de_datos()
        contar_registros()
    else:
        print("\nOperación cancelada. No se eliminó nada.")
