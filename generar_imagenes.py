from supabase import create_client, Client
from utils.barcode_utils import BarcodeGenerator
from config import URL_SUPABASE, KEY_SUPABASE


def generar_todo_masivo():
    print("🚀 Iniciando fábrica de códigos...")
    
    # Conectamos a las herramientas
    supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)
    barcode_gen = BarcodeGenerator()

    # 1. GENERAR QRs DE TRABAJADORES
    print("\nDescargando lista de trabajadores...")
    try:
        res_trab = supabase.table("trabajadores").select("*").execute()
        trabajadores = res_trab.data
        print(f"Generando {len(trabajadores)} códigos QR...")
        for t in trabajadores:
            # Usamos el generador que creaste para hacer la imagen
            barcode_gen.generar_qr_trabajador(t['rut'], t['nombre'])
        print(f"✅ QRs de trabajadores listos en '{barcode_gen.workers_dir}'.")
    except Exception as e:
        print(f"Error con trabajadores: {e}")

    # 2. GENERAR BARRAS DE PRODUCTOS
    print("\nDescargando lista de productos...")
    try:
        res_prod = supabase.table("productos").select("*").execute()
        productos = res_prod.data
        print(f"Generando {len(productos)} códigos de barras...")
        for p in productos:
            if p.get('codigo_barras') and p.get('nombre'):
                barcode_gen.generar_codigo_barras(p['codigo_barras'], p['nombre'])
        print(f"✅ Códigos de barras listos en '{barcode_gen.products_dir}'.")
    except Exception as e:
        print(f"Error con productos: {e}")

    print("\n🎉 ¡Proceso finalizado! Ya puedes imprimir los códigos para probar la cámara.")

if __name__ == "__main__":
    generar_todo_masivo()
