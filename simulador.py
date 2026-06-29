import random
import os
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# ============================================================
# CONEXION SUPABASE DESDE VARIABLES DE ENTORNO
# ============================================================

URL_SUPABASE = os.environ.get("SUPABASE_URL", "").strip()
KEY_SUPABASE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
supabase: Client | None = None


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

TOTAL_PROYECTOS = 10
TOTAL_TRABAJADORES = 40
TOTAL_PRODUCTOS = 200
TOTAL_MOVIMIENTOS = 1200

ANIO_SIMULACION = 2025

# Si tienes DELETE permitido por RLS, puedes poner True.
# Si no, déjalo en False.
LIMPIAR_ANTES = os.environ.get("SIMULADOR_LIMPIAR_ANTES") == "1"


def crear_cliente_seguro():
    if not URL_SUPABASE or not KEY_SUPABASE:
        raise RuntimeError(
            "Defina SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY para ejecutar "
            "el simulador."
        )
    if KEY_SUPABASE.startswith("sb_publishable"):
        raise RuntimeError("El simulador requiere una service role key.")
    return create_client(URL_SUPABASE, KEY_SUPABASE)


# ============================================================
# UTILIDADES
# ============================================================

def calcular_dv(rut_sin_dv):
    suma = 0
    multiplo = 2

    for c in reversed(str(rut_sin_dv)):
        suma += int(c) * multiplo
        multiplo = multiplo + 1 if multiplo < 7 else 2

    dv = 11 - (suma % 11)

    if dv == 11:
        return "0"
    if dv == 10:
        return "K"

    return str(dv)


def fecha_aleatoria_2025():
    inicio = datetime(ANIO_SIMULACION, 1, 1, 8, 0, 0)
    fin = datetime(ANIO_SIMULACION, 12, 31, 18, 0, 0)

    delta = fin - inicio
    segundos = random.randint(0, int(delta.total_seconds()))

    fecha = inicio + timedelta(seconds=segundos)

    # Evita horarios muy nocturnos
    hora = random.randint(8, 18)
    minuto = random.choice([0, 5, 10, 15, 20, 30, 40, 45, 50])

    return fecha.replace(hour=hora, minute=minuto, second=0, microsecond=0)


def insertar_en_bloques(tabla, datos, tamano=100):
    if not datos:
        return

    for i in range(0, len(datos), tamano):
        bloque = datos[i:i + tamano]
        supabase.table(tabla).insert(bloque).execute()


def formatear_codigo_producto(numero):
    return f"SIM2025-PRD-{numero:04d}"


def formatear_sku(numero):
    return f"SKU-SIM2025-{numero:04d}"


# ============================================================
# LIMPIEZA OPCIONAL
# ============================================================

def vaciar_base_de_datos():
    print("🧹 Intentando vaciar datos simulados...")

    productos_sim = (
        supabase.table("productos")
        .select("id")
        .like("codigo_barras", "SIM2025-PRD-%")
        .execute()
    ).data or []
    ids_productos = [p["id"] for p in productos_sim]

    try:
        eliminadas = 0
        for i in range(0, len(ids_productos), 100):
            bloque = ids_productos[i:i + 100]
            if bloque:
                supabase.table("transacciones").delete().in_(
                    "producto_id",
                    bloque
                ).execute()
                eliminadas += len(bloque)
        print(f"  - Transacciones de {eliminadas} productos simulados eliminadas.")
    except Exception as e:
        print(f"  ⚠️ No se pudieron eliminar transacciones: {e}")

    try:
        supabase.table("productos").delete().like("codigo_barras", "SIM2025-PRD-%").execute()
        print("  - Productos simulados eliminados.")
    except Exception as e:
        print(f"  ⚠️ No se pudieron eliminar productos: {e}")

    try:
        supabase.table("trabajadores").delete().like("rut", "99%").execute()
        print("  - Trabajadores simulados eliminados.")
    except Exception as e:
        print(f"  ⚠️ No se pudieron eliminar trabajadores: {e}")

    try:
        supabase.table("proyectos").delete().like("ot", "SIM-2025-%").execute()
        print("  - Proyectos simulados eliminados.")
    except Exception as e:
        print(f"  ⚠️ No se pudieron eliminar proyectos: {e}")


# ============================================================
# BODEGA / RACKS / UBICACIONES
# ============================================================

def obtener_bodega_principal():
    res = (
        supabase
        .table("bodegas")
        .select("*")
        .eq("nombre", "Bodega 1")
        .execute()
    )

    if not res.data:
        raise Exception("No existe 'Bodega 1'. Créala primero en Supabase.")

    return res.data[0]


def asegurar_racks_y_ubicaciones():
    print("📦 Verificando racks y ubicaciones 3x3...")

    bodega = obtener_bodega_principal()
    bodega_id = bodega["id"]

    # Crear R01 a R06 si no existen
    for i in range(1, 7):
        codigo_rack = f"R{i:02d}"

        existe = (
            supabase
            .table("racks")
            .select("*")
            .eq("bodega_id", bodega_id)
            .eq("codigo_rack", codigo_rack)
            .execute()
        )

        if not existe.data:
            supabase.table("racks").insert({
                "bodega_id": bodega_id,
                "codigo_rack": codigo_rack,
                "nombre": f"Rack {i:02d}",
                "descripcion": f"Rack de 200 cm - posición {i}",
                "niveles": 3,
                "columnas": 3,
                "estado": "Activo"
            }).execute()

    racks = (
        supabase
        .table("racks")
        .select("*")
        .eq("bodega_id", bodega_id)
        .eq("estado", "Activo")
        .order("codigo_rack")
        .execute()
    ).data

    niveles = ["N01", "N02", "N03"]
    columnas = ["C01", "C02", "C03"]

    for rack in racks:
        for nivel in niveles:
            for columna in columnas:
                codigo_ubicacion = f"B1-{rack['codigo_rack']}-{nivel}-{columna}"

                existe = (
                    supabase
                    .table("ubicaciones")
                    .select("id")
                    .eq("codigo_ubicacion", codigo_ubicacion)
                    .execute()
                )

                if not existe.data:
                    supabase.table("ubicaciones").insert({
                        "bodega_id": bodega_id,
                        "rack_id": rack["id"],
                        "codigo_ubicacion": codigo_ubicacion,
                        "tipo": "Bloque",
                        "nivel": nivel,
                        "columna": columna,
                        "subdivision": None,
                        "ubicacion_padre_id": None,
                        "descripcion": f"{rack['codigo_rack']} {nivel} {columna}",
                        "estado": "Activo"
                    }).execute()

    # Crear algunas subdivisiones simuladas para probar el mapa
    bloques = (
        supabase
        .table("ubicaciones")
        .select("*")
        .eq("tipo", "Bloque")
        .eq("estado", "Activo")
        .execute()
    ).data

    bloques_para_subdividir = random.sample(bloques, min(12, len(bloques)))

    for bloque in bloques_para_subdividir:
        for n in range(1, 5):
            sub = f"S{n:02d}"
            codigo_sub = f"{bloque['codigo_ubicacion']}-{sub}"

            existe = (
                supabase
                .table("ubicaciones")
                .select("id")
                .eq("codigo_ubicacion", codigo_sub)
                .execute()
            )

            if not existe.data:
                supabase.table("ubicaciones").insert({
                    "bodega_id": bloque["bodega_id"],
                    "rack_id": bloque["rack_id"],
                    "codigo_ubicacion": codigo_sub,
                    "tipo": "Subdivision",
                    "nivel": bloque["nivel"],
                    "columna": bloque["columna"],
                    "subdivision": sub,
                    "ubicacion_padre_id": bloque["id"],
                    "descripcion": f"{sub} de {bloque['codigo_ubicacion']}",
                    "estado": "Activo"
                }).execute()

    ubicaciones = (
        supabase
        .table("ubicaciones")
        .select("*")
        .eq("estado", "Activo")
        .execute()
    ).data

    print(f"  - Ubicaciones disponibles: {len(ubicaciones)}")

    return ubicaciones


# ============================================================
# PROYECTOS
# ============================================================

def generar_proyectos():
    print(f"🏗️ Generando {TOTAL_PROYECTOS} proyectos 2025...")

    proyectos_base = [
        ("Montaje Norte", "Cliente Minera Norte"),
        ("Mantención Planta", "Cliente Industrial Sur"),
        ("Ampliación Bodega", "Cliente Logística Central"),
        ("Sala Eléctrica", "Cliente Energía Andina"),
        ("Estructuras Metálicas", "Cliente Constructora Pacífico"),
        ("Línea Productiva", "Cliente Manufactura Los Andes"),
        ("Proyecto Hospitalario", "Cliente Salud Regional"),
        ("Mejoramiento Taller", "Interno"),
        ("Sistema de Ventilación", "Cliente Climatización Pro"),
        ("Obra Civil Menor", "Cliente Obras Integrales")
    ]

    proyectos_insertar = []

    for i, (nombre, cliente) in enumerate(proyectos_base, start=1):
        mes_inicio = random.randint(1, 9)
        dia_inicio = random.randint(1, 20)

        fecha_inicio = date(ANIO_SIMULACION, mes_inicio, dia_inicio)
        fecha_fin = fecha_inicio + timedelta(days=random.randint(45, 150))

        if fecha_fin.year > ANIO_SIMULACION:
            fecha_fin = date(ANIO_SIMULACION, 12, random.randint(15, 31))

        proyectos_insertar.append({
            "nombre": f"SIM 2025 - {nombre}",
            "ot": f"SIM-2025-{i:03d}",
            "cliente": cliente,
            "descripcion": f"Proyecto simulado {i} para pruebas de consumo por proyecto.",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "estado": random.choice(["Activo", "Activo", "Activo", "Finalizado"])
        })

    # Insertar evitando duplicados por nombre
    for p in proyectos_insertar:
        existe = (
            supabase
            .table("proyectos")
            .select("id")
            .eq("nombre", p["nombre"])
            .execute()
        )

        if not existe.data:
            supabase.table("proyectos").insert(p).execute()

    proyectos = (
        supabase
        .table("proyectos")
        .select("*")
        .like("ot", "SIM-2025-%")
        .execute()
    ).data

    print(f"  - Proyectos simulados disponibles: {len(proyectos)}")

    return proyectos


# ============================================================
# TRABAJADORES
# ============================================================

def generar_trabajadores():
    print(f"👷 Generando {TOTAL_TRABAJADORES} trabajadores...")

    cargos = [
        "Soldador",
        "Eléctrico",
        "Mecánico",
        "Ayudante",
        "Supervisor",
        "Prevencionista",
        "Bodeguero",
        "Operador",
        "Maestro Primera",
        "Maestro Segunda",
        "Rigger",
        "Pañolero"
    ]

    nombres = [
        "Juan", "Pedro", "Luis", "Carlos", "Miguel", "Jorge", "Mateo", "Lucas",
        "Diego", "Felipe", "Andrés", "Cristóbal", "Sebastián", "Tomás",
        "Francisco", "Nicolás", "Matías", "Benjamín", "Ignacio", "Vicente",
        "Camila", "Valentina", "Fernanda", "Daniela", "Catalina", "Javiera"
    ]

    apellidos = [
        "Pérez", "González", "Tapia", "Muñoz", "Rojas", "Díaz", "Soto",
        "Contreras", "Silva", "Martínez", "Vargas", "Castro", "Flores",
        "Herrera", "Morales", "Fuentes", "Araya", "Navarro", "Cortés",
        "Espinoza"
    ]

    trabajadores = []

    for i in range(TOTAL_TRABAJADORES):
        rut_base = 99000000 + i
        rut = f"{rut_base}-{calcular_dv(rut_base)}"

        nombre = (
            f"{random.choice(nombres)} "
            f"{random.choice(apellidos)} "
            f"{random.choice(apellidos)}"
        )

        trabajadores.append({
            "rut": rut,
            "nombre": nombre,
            "cargo": random.choice(cargos),
            "estado": "Activo"
        })

    existentes = (
        supabase
        .table("trabajadores")
        .select("rut")
        .like("rut", "99%")
        .execute()
    ).data or []
    ruts_existentes = {t["rut"] for t in existentes}
    trabajadores_nuevos = [
        t for t in trabajadores
        if t["rut"] not in ruts_existentes
    ]
    insertar_en_bloques("trabajadores", trabajadores_nuevos, 100)

    trabajadores_db = (
        supabase
        .table("trabajadores")
        .select("*")
        .in_("rut", [t["rut"] for t in trabajadores])
        .execute()
    ).data

    print(f"  - Trabajadores insertados: {len(trabajadores_db)}")

    return trabajadores_db


# ============================================================
# PRODUCTOS
# ============================================================

def generar_productos(ubicaciones):
    print(f"🧰 Generando {TOTAL_PRODUCTOS} artículos de inventario...")

    marcas = [
        "TecnoPro", "InduMax", "FerraChile", "SegurWork", "MetalPro",
        "ElectroAndes", "BodegaPlus", "Herratek", "ProTools", "MaxSteel",
        "AndesTools", "NorteFix", "SteelWork", "Maestranza Pro", "Bosch",
        "Stanley", "Makita", "DeWalt", "3M", "Sika"
    ]

    catalogo = {
        "Herramientas": {
            "subcategorias": ["Manual", "Medición", "Ajuste", "Golpe"],
            "productos": [
                "Llave inglesa", "Alicate universal", "Destornillador cruz",
                "Destornillador paleta", "Martillo carpintero", "Huincha de medir",
                "Nivel magnético", "Llave punta corona", "Prensa C", "Lima metálica"
            ],
            "tallas": ["No aplica"],
            "dimensiones": ["8 pulgadas", "10 pulgadas", "12 pulgadas", "5 metros", "30 cm"]
        },
        "Insumos": {
            "subcategorias": ["Consumibles", "Eléctricos", "Fijaciones", "Soldadura"],
            "productos": [
                "Disco de corte", "Disco de desbaste", "Electrodo 6011", "Electrodo 7018",
                "Cinta aislante", "Amarra plástica", "Broca acero rápido",
                "Tornillo autoperforante", "Perno hexagonal", "Tuerca zincada",
                "Golilla plana", "Silicona industrial", "Sellador poliuretano"
            ],
            "tallas": ["No aplica"],
            "dimensiones": ["4.5 pulgadas", "1/8 pulgadas", "3/32 pulgadas", "10 metros", "100 unidades"]
        },
        "EPP": {
            "subcategorias": [
                "Protección manos", "Protección cabeza", "Protección visual",
                "Protección respiratoria", "Protección pies", "Alta visibilidad"
            ],
            "productos": [
                "Guantes cabritilla", "Guantes nitrilo", "Casco de seguridad",
                "Lentes claros", "Lentes oscuros", "Mascarilla medio rostro",
                "Chaleco reflectante", "Zapatos de seguridad", "Protector auditivo",
                "Arnés de seguridad"
            ],
            "tallas": ["S", "M", "L", "XL", "42", "43", "44"],
            "dimensiones": ["Estándar", "Ajustable", "Reforzado", "Certificado"]
        },
        "Equipos": {
            "subcategorias": ["Soldadura", "Corte", "Perforación", "Pulido", "Izaje"],
            "productos": [
                "Máquina de soldar inverter", "Esmeril angular", "Taladro percutor",
                "Sierra circular", "Cortadora sensitiva", "Rotomartillo",
                "Tecle manual", "Eslinga poliéster", "Grillete lira", "Tirfor manual"
            ],
            "tallas": ["No aplica"],
            "dimensiones": ["220V", "110V", "7 pulgadas", "4.5 pulgadas", "1 tonelada", "2 toneladas"]
        },
        "Materiales": {
            "subcategorias": ["Acero", "Perfiles", "Planchas", "Tuberías", "Eléctricos"],
            "productos": [
                "Perfil ángulo", "Perfil canal", "Tubo cuadrado", "Plancha acero",
                "Cable eléctrico", "Canaleta PVC", "Conduit galvanizado",
                "Barra roscada", "Malla metálica", "Pletina acero"
            ],
            "tallas": ["No aplica"],
            "dimensiones": ["20x20x3 mm", "40x40x3 mm", "1.5 mm", "3 mm", "6 metros", "100 metros"]
        }
    }

    productos = []
    codigos_usados = set()
    skus_usados = set()

    for i in range(1, TOTAL_PRODUCTOS + 1):
        categoria = random.choice(list(catalogo.keys()))
        data_cat = catalogo[categoria]

        nombre_base = random.choice(data_cat["productos"])
        marca = random.choice(marcas)
        subcategoria = random.choice(data_cat["subcategorias"])
        talla = random.choice(data_cat["tallas"])
        dimensiones = random.choice(data_cat["dimensiones"])

        codigo = formatear_codigo_producto(i)
        sku = formatear_sku(i)

        if codigo in codigos_usados or sku in skus_usados:
            continue

        codigos_usados.add(codigo)
        skus_usados.add(sku)

        if categoria in ["Herramientas", "Equipos"]:
            stock = random.randint(2, 20)
            stock_minimo = random.randint(1, 4)
            precio = random.randint(15000, 450000)
        elif categoria == "EPP":
            stock = random.randint(20, 180)
            stock_minimo = random.randint(10, 30)
            precio = random.randint(2500, 85000)
        elif categoria == "Materiales":
            stock = random.randint(10, 120)
            stock_minimo = random.randint(5, 20)
            precio = random.randint(1200, 180000)
        else:
            stock = random.randint(30, 250)
            stock_minimo = random.randint(10, 40)
            precio = random.randint(500, 45000)

        ubicacion = random.choice(ubicaciones)

        productos.append({
            "codigo_barras": codigo,
            "sku": sku,
            "nombre": f"{nombre_base} {marca} {dimensiones}",
            "categoria": categoria,
            "subcategoria": subcategoria,
            "marca": marca,
            "tamaño_dimensiones": dimensiones,
            "talla": talla,
            "stock": stock,
            "stock_minimo": stock_minimo,
            "precio_unitario": precio,
            "ubicacion_id": ubicacion["id"],
            "estado": "Activo"
        })

    existentes = (
        supabase
        .table("productos")
        .select("codigo_barras")
        .like("codigo_barras", "SIM2025-PRD-%")
        .execute()
    ).data or []
    codigos_existentes = {p["codigo_barras"] for p in existentes}
    productos_nuevos = [
        p for p in productos
        if p["codigo_barras"] not in codigos_existentes
    ]
    insertar_en_bloques("productos", productos_nuevos, 100)

    productos_db = (
        supabase
        .table("productos")
        .select("*")
        .like("codigo_barras", "SIM2025-PRD-%")
        .execute()
    ).data

    print(f"  - Productos simulados disponibles: {len(productos_db)}")

    return productos_db


# ============================================================
# TRANSACCIONES
# ============================================================

def generar_transacciones(productos, proyectos, trabajadores):
    print(f"🔁 Generando {TOTAL_MOVIMIENTOS} movimientos durante 2025...")

    productos_estado = {
        p["id"]: dict(p)
        for p in productos
    }

    trabajadores_ids = [t["id"] for t in trabajadores]
    proyectos_ids = [p["id"] for p in proyectos]

    movimientos_resta = [
        "Entrega / Consumo",
        "Baja por Daño / Merma",
        "Préstamo de Herramienta",
        "Envío a Calibración / Reparación",
        "Corte / Transformación"
    ]

    movimientos_suma = [
        "Entrada / Reposición",
        "Devolución de Herramienta",
        "Retorno de Reparación"
    ]

    tipos_todos = [
        "Entrega / Consumo",
        "Baja por Daño / Merma",
        "Préstamo de Herramienta",
        "Devolución de Herramienta",
        "Envío a Calibración / Reparación",
        "Retorno de Reparación",
        "Corte / Transformación",
        "Entrada / Reposición"
    ]

    prestamos_activos = {}
    reparaciones_activas = {}

    transacciones = []
    fechas_movimientos = sorted(
        fecha_aleatoria_2025()
        for _ in range(TOTAL_MOVIMIENTOS)
    )

    for fecha in fechas_movimientos:
        producto = random.choice(list(productos_estado.values()))
        producto_id = producto["id"]

        categoria = producto.get("categoria", "")
        stock_actual = int(producto.get("stock") or 0)

        proyecto_id = random.choice(proyectos_ids)

        # 20% sin responsable, para probar responsable opcional
        trabajador_id = random.choice(trabajadores_ids) if random.random() > 0.20 else None

        # Selección inteligente según categoría
        if categoria in ["Insumos", "EPP", "Materiales"]:
            tipo = random.choices(
                [
                    "Entrega / Consumo",
                    "Entrada / Reposición",
                    "Baja por Daño / Merma",
                    "Corte / Transformación"
                ],
                weights=[55, 25, 10, 10],
                k=1
            )[0]
        else:
            tipo = random.choices(
                [
                    "Préstamo de Herramienta",
                    "Devolución de Herramienta",
                    "Envío a Calibración / Reparación",
                    "Retorno de Reparación",
                    "Entrada / Reposición",
                    "Baja por Daño / Merma"
                ],
                weights=[35, 25, 10, 10, 15, 5],
                k=1
            )[0]

        # Control de préstamos activos
        if tipo == "Préstamo de Herramienta":
            if trabajador_id is None:
                trabajador_id = random.choice(trabajadores_ids)

            llave = (producto_id, trabajador_id)

            if llave in prestamos_activos:
                tipo = "Devolución de Herramienta"
                del prestamos_activos[llave]
            else:
                prestamos_activos[llave] = True

        elif tipo == "Devolución de Herramienta":
            if prestamos_activos:
                llave = random.choice(list(prestamos_activos.keys()))
                producto_id, trabajador_id = llave
                producto = productos_estado[producto_id]
                stock_actual = int(producto.get("stock") or 0)
                del prestamos_activos[llave]
            else:
                tipo = "Entrada / Reposición"

        # Control de reparación
        if tipo == "Envío a Calibración / Reparación":
            llave_rep = producto_id

            if llave_rep in reparaciones_activas:
                tipo = "Retorno de Reparación"
                del reparaciones_activas[llave_rep]
            else:
                reparaciones_activas[llave_rep] = True

        elif tipo == "Retorno de Reparación":
            if reparaciones_activas:
                llave_rep = random.choice(list(reparaciones_activas.keys()))
                producto_id = llave_rep
                producto = productos_estado[producto_id]
                stock_actual = int(producto.get("stock") or 0)
                del reparaciones_activas[llave_rep]
            else:
                tipo = "Entrada / Reposición"

        if tipo in ["Entrega / Consumo", "Baja por Daño / Merma", "Corte / Transformación"]:
            cantidad = random.randint(1, 8)

        elif tipo == "Entrada / Reposición":
            cantidad = random.randint(5, 40)

        else:
            cantidad = 1

        # Evitar stock negativo
        if tipo in movimientos_resta and stock_actual < cantidad:
            if tipo == "Préstamo de Herramienta":
                prestamos_activos.pop((producto_id, trabajador_id), None)
            elif tipo == "Envío a Calibración / Reparación":
                reparaciones_activas.pop(producto_id, None)
            tipo = "Entrada / Reposición"
            cantidad = random.randint(5, 30)

        if tipo in movimientos_resta:
            stock_nuevo = stock_actual - cantidad
        elif tipo in movimientos_suma:
            stock_nuevo = stock_actual + cantidad
        else:
            stock_nuevo = stock_actual

        comentario = generar_comentario(tipo)

        transacciones.append({
            "fecha_hora": fecha.isoformat(),
            "producto_id": producto_id,
            "proyecto_id": proyecto_id,
            "trabajador_id": trabajador_id,
            "tipo_movimiento": tipo,
            "cantidad_movida": cantidad,
            "stock_anterior": stock_actual,
            "stock_nuevo": stock_nuevo,
            "comentario": comentario,
            "creado_por_usuario": "Simulador 2025"
        })

        producto["stock"] = stock_nuevo
        productos_estado[producto_id] = producto

    insertar_en_bloques("transacciones", transacciones, 100)

    print(f"  - Transacciones insertadas: {len(transacciones)}")

    # Actualizar stock final de cada producto
    print("📌 Actualizando stock final en productos...")

    for producto_id, producto in productos_estado.items():
        supabase.table("productos").update({
            "stock": int(producto.get("stock") or 0)
        }).eq("id", producto_id).execute()

    print("  - Stock final actualizado.")


def generar_comentario(tipo):
    comentarios = {
        "Entrega / Consumo": [
            "Material entregado para ejecución en terreno.",
            "Consumo asociado a frente de trabajo.",
            "Salida normal para proyecto.",
            "Retiro de materiales para instalación."
        ],
        "Baja por Daño / Merma": [
            "Producto dañado durante manipulación.",
            "Merma detectada en revisión de bodega.",
            "Material no utilizable.",
            "Baja por deterioro."
        ],
        "Préstamo de Herramienta": [
            "Herramienta prestada para faena.",
            "Préstamo temporal a equipo de trabajo.",
            "Salida a terreno con devolución esperada."
        ],
        "Devolución de Herramienta": [
            "Herramienta devuelta a bodega.",
            "Retorno desde terreno.",
            "Devolución posterior a uso."
        ],
        "Envío a Calibración / Reparación": [
            "Equipo enviado a revisión.",
            "Herramienta enviada a mantención.",
            "Equipo fuera de bodega temporalmente."
        ],
        "Retorno de Reparación": [
            "Equipo retornado desde mantención.",
            "Herramienta reparada disponible.",
            "Retorno posterior a calibración."
        ],
        "Corte / Transformación": [
            "Material cortado para ajuste de medida.",
            "Transformación de material para proyecto.",
            "Corte realizado según requerimiento."
        ],
        "Entrada / Reposición": [
            "Ingreso por compra o reposición.",
            "Reposición de stock de bodega.",
            "Entrada simulada de inventario."
        ]
    }

    return random.choice(comentarios.get(tipo, ["Movimiento simulado."]))


# ============================================================
# PROCESO PRINCIPAL
# ============================================================

def generar_datos():
    global supabase
    supabase = crear_cliente_seguro()

    print("==============================================")
    print(" SIMULADOR BODEGA V2 - DATOS AÑO 2025")
    print("==============================================")

    if LIMPIAR_ANTES:
        vaciar_base_de_datos()

    ubicaciones = asegurar_racks_y_ubicaciones()
    proyectos = generar_proyectos()
    trabajadores = generar_trabajadores()
    productos = generar_productos(ubicaciones)
    generar_transacciones(productos, proyectos, trabajadores)

    print("\n✅ Simulación completada correctamente.")
    print(f"   Proyectos: {len(proyectos)}")
    print(f"   Trabajadores: {len(trabajadores)}")
    print(f"   Productos: {len(productos)}")
    print(f"   Movimientos: {TOTAL_MOVIMIENTOS}")
    print("\nAhora abre la app y revisa:")
    print("  - Inventario General")
    print("  - Mapa de Bodega")
    print("  - Consumo por Proyecto")
    print("  - Herramientas en Terreno")


if __name__ == "__main__":
    generar_datos()
