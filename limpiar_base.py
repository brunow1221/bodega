import os
from supabase import create_client, Client


URL_SUPABASE = os.environ.get(
    "SUPABASE_URL",
    "https://vqxvuwepzzexnmhenitt.supabase.co"
).strip()

KEY_SUPABASE = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZxeHZ1d2VwenpleG5taGVuaXR0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzM2ODM5NywiZXhwIjoyMDg4OTQ0Mzk3fQ.UHo44UYq2FzsnXTyNYVaBJlsL-SLByVXNkRARWMN2Ew"
).strip()

supabase: Client | None = None


def crear_cliente_seguro():
    """
    Crea el cliente de Supabase usando una Service Role Key.
    """

    if not URL_SUPABASE:
        raise RuntimeError(
            "No se encontró SUPABASE_URL."
        )

    if not KEY_SUPABASE:
        raise RuntimeError(
            "No se encontró SUPABASE_SERVICE_ROLE_KEY.\n"
            "Debes definirla como variable de entorno antes de ejecutar "
            "una limpieza destructiva."
        )

    if KEY_SUPABASE.startswith("sb_publishable"):
        raise RuntimeError(
            "La limpieza requiere una Service Role Key, "
            "no una clave pública."
        )

    return create_client(URL_SUPABASE, KEY_SUPABASE)


def contar_registros():
    """
    Muestra la cantidad actual de registros en las tablas
    que serán limpiadas.
    """

    try:
        productos = (
            supabase
            .table("productos")
            .select("id", count="exact")
            .execute()
        )

        trabajadores = (
            supabase
            .table("trabajadores")
            .select("id", count="exact")
            .execute()
        )

        transacciones = (
            supabase
            .table("transacciones")
            .select("id", count="exact")
            .execute()
        )

        print("\n📊 Estado actual de la base:")
        print(f"  - Productos: {productos.count}")
        print(f"  - Trabajadores: {trabajadores.count}")
        print(f"  - Transacciones: {transacciones.count}")

    except Exception as e:
        print(f"\n⚠️ No se pudieron contar los registros:")
        print(e)


def eliminar_todos_los_registros(tabla):
    """
    Elimina todos los registros de una tabla utilizando
    un filtro compatible con IDs UUID o numéricos.
    """

    return (
        supabase
        .table(tabla)
        .delete()
        .not_
        .is_("id", "null")
        .execute()
    )


def vaciar_base_de_datos():
    """
    Elimina datos operativos respetando el orden de
    dependencias entre tablas.
    """

    print("\n🧹 Vaciando datos operativos de la base de datos...")

    try:

        # -------------------------------------------------
        # TRANSACCIONES
        # -------------------------------------------------

        # Primero se eliminan porque pueden depender
        # de productos y trabajadores.
        eliminar_todos_los_registros("transacciones")

        print("  ✅ Transacciones eliminadas.")


        # -------------------------------------------------
        # TRABAJADORES
        # -------------------------------------------------

        eliminar_todos_los_registros("trabajadores")

        print("  ✅ Trabajadores eliminados.")


        # -------------------------------------------------
        # PRODUCTOS
        # -------------------------------------------------

        # El ID de productos es UUID.
        # Por eso NO debemos usar:
        #
        # .gt("id", 0)
        #
        # porque PostgreSQL intentaría comparar un UUID
        # contra el número 0.
        eliminar_todos_los_registros("productos")

        print("  ✅ Productos eliminados.")


        print("\n========================================")
        print(" ✨ BASE DE DATOS LIMPIADA CORRECTAMENTE")
        print("========================================")

        print("\nSe eliminaron:")
        print("  - Productos")
        print("  - Trabajadores")
        print("  - Transacciones")

        print("\nNo se eliminaron:")
        print("  - config_app")
        print("  - proyectos")


    except Exception as e:

        print("\n========================================")
        print(" ⚠️ ERROR DURANTE LA LIMPIEZA")
        print("========================================")

        print(f"\n{e}")

        print(
            "\nLa limpieza se detuvo en la tabla que produjo el error."
        )


def solicitar_confirmacion():
    """
    Solicita escribir exactamente la URL del proyecto
    para evitar eliminaciones accidentales.
    """

    print("\n⚠️ ADVERTENCIA")
    print("----------------------------------------")

    print("Esta acción eliminará TODOS los registros de:")

    print("\n  - productos")
    print("  - trabajadores")
    print("  - transacciones")

    print("\nNO eliminará:")

    print("\n  - config_app")
    print("  - proyectos")

    print("\n----------------------------------------")

    print(f"\nProyecto objetivo:\n{URL_SUPABASE}")

    confirmacion = input(
        "\nEscribe la URL completa del proyecto "
        "para confirmar la limpieza:\n> "
    ).strip()

    return confirmacion == URL_SUPABASE


def main():

    global supabase

    print("========================================")
    print(" LIMPIEZA DE BASE DE DATOS - BODEGA")
    print("========================================")

    try:
        supabase = crear_cliente_seguro()

    except Exception as e:

        print("\n❌ No fue posible conectarse a Supabase.")

        print(f"\n{e}")

        return


    # Mostrar estado antes de borrar
    contar_registros()


    # Confirmación de seguridad
    if not solicitar_confirmacion():

        print("\n❌ Confirmación incorrecta.")

        print("Operación cancelada.")

        print("\nNo se eliminó ningún registro.")

        return


    # Ejecutar limpieza
    vaciar_base_de_datos()


    # Mostrar resultado
    contar_registros()


if __name__ == "__main__":
    main()