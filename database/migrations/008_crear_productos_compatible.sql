-- Crea productos y retazos sin asumir que los identificadores son bigint.
-- Es compatible con instalaciones antiguas que usan UUID.

begin;

create or replace function public.crear_producto_app(
    p_token uuid,
    p_request_id uuid,
    p_datos jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $funcion$
declare
    v_sesion public.sesiones_app%rowtype;
    v_respuesta jsonb;
    v_producto_id text;
    v_proyecto text;
    v_rut_trabajador text;
    v_stock integer;
    v_es_retazo boolean;
begin
    v_sesion := public.validar_sesion_app(p_token, true);

    select respuesta
      into v_respuesta
      from public.solicitudes_app
     where request_id = p_request_id;
    if found then
        return v_respuesta;
    end if;

    insert into public.solicitudes_app (request_id, operacion)
    values (p_request_id, 'crear_producto_compatible')
    on conflict (request_id) do nothing;

    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    v_es_retazo := coalesce((p_datos ->> 'es_retazo')::boolean, false);
    v_stock := case
        when v_es_retazo then 1
        else coalesce((p_datos ->> 'stock')::integer, 0)
    end;
    v_proyecto := case
        when v_es_retazo then p_datos ->> 'proyecto'
        else 'Taller Interno'
    end;
    v_rut_trabajador := nullif(
        trim(coalesce(p_datos ->> 'rut_trabajador', '')),
        ''
    );

    if nullif(trim(coalesce(p_datos ->> 'nombre', '')), '') is null then
        raise exception 'El nombre del producto es obligatorio.';
    end if;
    if v_stock < 0
       or coalesce((p_datos ->> 'stock_minimo')::integer, 0) < 0
       or coalesce((p_datos ->> 'precio_unitario')::numeric, 0) < 0 then
        raise exception 'Stock, stock minimo y precio no pueden ser negativos.';
    end if;

    if nullif(p_datos ->> 'ubicacion_id', '') is not null
       and not exists (
           select 1
             from public.ubicaciones u
            where u.id::text = p_datos ->> 'ubicacion_id'
       ) then
        raise exception 'La ubicacion seleccionada no existe.';
    end if;

    if v_es_retazo and not exists (
        select 1
          from public.proyectos pr
         where pr.nombre = v_proyecto
           and pr.estado = 'Activo'
    ) then
        raise exception 'Proyecto inexistente o inactivo.';
    end if;

    if v_rut_trabajador is not null and not exists (
        select 1
          from public.trabajadores tr
         where tr.rut = v_rut_trabajador
           and tr.estado = 'Activo'
    ) then
        raise exception 'Trabajador inexistente o inactivo.';
    end if;

    insert into public.productos (
        codigo_barras, nombre, categoria, subcategoria, marca,
        "tamaño_dimensiones", talla, stock, stock_minimo,
        precio_unitario, ubicacion_id, estado, tipo_medicion,
        medida_largo, medida_ancho, unidad_medida,
        es_retazo, porcentaje_valor_origen, observacion_retazo
    )
    values (
        p_datos ->> 'codigo_barras',
        p_datos ->> 'nombre',
        p_datos ->> 'categoria',
        p_datos ->> 'subcategoria',
        p_datos ->> 'marca',
        p_datos ->> 'tamaño_dimensiones',
        p_datos ->> 'talla',
        v_stock,
        coalesce((p_datos ->> 'stock_minimo')::integer, 0),
        coalesce((p_datos ->> 'precio_unitario')::numeric, 0),
        (
            select u.id
              from public.ubicaciones u
             where u.id::text = nullif(p_datos ->> 'ubicacion_id', '')
             limit 1
        ),
        'Activo',
        coalesce(p_datos ->> 'tipo_medicion', 'No aplica'),
        nullif(p_datos ->> 'medida_largo', '')::numeric,
        nullif(p_datos ->> 'medida_ancho', '')::numeric,
        nullif(p_datos ->> 'unidad_medida', ''),
        v_es_retazo,
        nullif(p_datos ->> 'porcentaje_valor_origen', '')::numeric,
        nullif(p_datos ->> 'observacion_retazo', '')
    )
    returning id::text into v_producto_id;

    -- La asignación usa productos.id directamente, por lo que funciona tanto
    -- con UUID como con bigint después de aplicar la migración 007.
    if nullif(p_datos ->> 'producto_origen_id', '') is not null then
        update public.productos destino
           set producto_origen_id = origen.id
          from public.productos origen
         where destino.id::text = v_producto_id
           and origen.id::text = p_datos ->> 'producto_origen_id';
        if not found then
            raise exception 'No existe el producto de origen del retazo.';
        end if;
    end if;

    if v_stock > 0 and exists (
        select 1
          from public.proyectos pr
         where pr.nombre = v_proyecto
           and pr.estado = 'Activo'
    ) then
        insert into public.transacciones (
            producto_id, proyecto_id, trabajador_id, tipo_movimiento,
            cantidad_movida, stock_anterior, stock_nuevo, comentario,
            creado_por_usuario, precio_unitario_movimiento,
            producto_nombre_snapshot, producto_codigo_snapshot,
            ubicacion_snapshot
        )
        select
            producto.id,
            proyecto.id,
            trabajador.id,
            'Entrada / Reposición',
            v_stock,
            0,
            v_stock,
            case
                when v_es_retazo then 'Entrada automática de retazo'
                else 'Stock inicial del producto'
            end,
            v_sesion.nombre || ' (' || v_sesion.usuario || ')',
            producto.precio_unitario,
            producto.nombre,
            producto.codigo_barras,
            ubicacion.codigo_ubicacion
          from public.productos producto
          join public.proyectos proyecto
            on proyecto.nombre = v_proyecto
           and proyecto.estado = 'Activo'
          left join public.trabajadores trabajador
            on trabajador.rut = v_rut_trabajador
           and trabajador.estado = 'Activo'
          left join public.ubicaciones ubicacion
            on ubicacion.id = producto.ubicacion_id
         where producto.id::text = v_producto_id
         limit 1;
    end if;

    insert into public.auditoria (
        modulo, accion, detalle, usuario_app, datos
    )
    values (
        'Inventario',
        case when v_es_retazo then 'Crear retazo' else 'Crear producto' end,
        case
            when v_es_retazo then 'Se creó el retazo '
            else 'Se creó el producto '
        end || coalesce(p_datos ->> 'nombre', ''),
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        p_datos - '_modulo' - '_accion' - '_detalle'
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'id', v_producto_id
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;

    return v_respuesta;
end;
$funcion$;

revoke all on function public.crear_producto_app(uuid, uuid, jsonb)
    from public;
grant execute on function public.crear_producto_app(uuid, uuid, jsonb)
    to anon, authenticated;

notify pgrst, 'reload schema';

commit;
