-- Permite editar la cantidad desde el formulario de producto con trazabilidad.
-- Requiere las migraciones de seguridad y creación compatible de productos.

begin;

create or replace function public.actualizar_producto_stock_app(
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
    v_producto public.productos%rowtype;
    v_respuesta jsonb;
    v_stock_anterior integer;
    v_stock_nuevo integer;
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
    values (p_request_id, 'actualizar_producto_stock')
    on conflict (request_id) do nothing;

    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    select *
      into v_producto
      from public.productos
     where id::text = p_datos ->> 'id'
     for update;

    if not found then
        raise exception 'Producto no encontrado.';
    end if;

    if not (p_datos ? 'stock') then
        raise exception 'Debe indicar la nueva cantidad.';
    end if;

    v_stock_anterior := coalesce(v_producto.stock, 0);
    v_stock_nuevo := (p_datos ->> 'stock')::integer;

    if v_stock_nuevo is null or v_stock_nuevo < 0 then
        raise exception 'La cantidad no puede ser negativa.';
    end if;
    if coalesce(
        (p_datos ->> 'stock_minimo')::integer,
        v_producto.stock_minimo,
        0
    ) < 0 then
        raise exception 'El stock minimo no puede ser negativo.';
    end if;
    if coalesce(
        (p_datos ->> 'precio_unitario')::numeric,
        v_producto.precio_unitario,
        0
    ) < 0 then
        raise exception 'El precio no puede ser negativo.';
    end if;
    if p_datos ? 'nombre'
       and nullif(trim(coalesce(p_datos ->> 'nombre', '')), '') is null then
        raise exception 'El nombre del producto es obligatorio.';
    end if;
    if nullif(p_datos ->> 'ubicacion_id', '') is not null
       and not exists (
           select 1
             from public.ubicaciones ubicacion
            where ubicacion.id::text = p_datos ->> 'ubicacion_id'
       ) then
        raise exception 'La ubicacion seleccionada no existe.';
    end if;

    update public.productos producto
       set nombre = coalesce(p_datos ->> 'nombre', producto.nombre),
           categoria = coalesce(p_datos ->> 'categoria', producto.categoria),
           subcategoria = coalesce(
               p_datos ->> 'subcategoria',
               producto.subcategoria
           ),
           marca = coalesce(p_datos ->> 'marca', producto.marca),
           "tamaño_dimensiones" = coalesce(
               p_datos ->> 'tamaño_dimensiones',
               producto."tamaño_dimensiones"
           ),
           talla = coalesce(p_datos ->> 'talla', producto.talla),
           stock = v_stock_nuevo,
           stock_minimo = coalesce(
               (p_datos ->> 'stock_minimo')::integer,
               producto.stock_minimo
           ),
           precio_unitario = coalesce(
               (p_datos ->> 'precio_unitario')::numeric,
               producto.precio_unitario
           ),
           ubicacion_id = case
               when p_datos ? 'ubicacion_id' then (
                   select ubicacion.id
                     from public.ubicaciones ubicacion
                    where ubicacion.id::text = nullif(
                        p_datos ->> 'ubicacion_id',
                        ''
                    )
                    limit 1
               )
               else producto.ubicacion_id
           end,
           tipo_medicion = coalesce(
               p_datos ->> 'tipo_medicion',
               producto.tipo_medicion
           ),
           medida_largo = case
               when p_datos ? 'medida_largo'
               then nullif(p_datos ->> 'medida_largo', '')::numeric
               else producto.medida_largo
           end,
           medida_ancho = case
               when p_datos ? 'medida_ancho'
               then nullif(p_datos ->> 'medida_ancho', '')::numeric
               else producto.medida_ancho
           end,
           unidad_medida = case
               when p_datos ? 'unidad_medida'
               then nullif(p_datos ->> 'unidad_medida', '')
               else producto.unidad_medida
           end
     where producto.id::text = p_datos ->> 'id';

    if v_stock_nuevo <> v_stock_anterior then
        insert into public.transacciones (
            producto_id,
            proyecto_id,
            trabajador_id,
            tipo_movimiento,
            cantidad_movida,
            stock_anterior,
            stock_nuevo,
            comentario,
            creado_por_usuario,
            precio_unitario_movimiento,
            producto_nombre_snapshot,
            producto_codigo_snapshot,
            ubicacion_snapshot
        )
        select
            producto.id,
            null,
            null,
            'Ajuste manual de inventario',
            abs(v_stock_nuevo - v_stock_anterior),
            v_stock_anterior,
            v_stock_nuevo,
            'Cantidad modificada desde Editar Seleccionado',
            v_sesion.nombre || ' (' || v_sesion.usuario || ')',
            coalesce(producto.precio_unitario, 0),
            producto.nombre,
            producto.codigo_barras,
            ubicacion.codigo_ubicacion
          from public.productos producto
          left join public.ubicaciones ubicacion
            on ubicacion.id = producto.ubicacion_id
         where producto.id::text = p_datos ->> 'id';
    end if;

    insert into public.auditoria (
        modulo,
        accion,
        detalle,
        usuario_app,
        datos
    )
    values (
        'Inventario',
        'Editar producto',
        'Se editó el producto ' || coalesce(
            p_datos ->> 'nombre',
            v_producto.nombre
        ) || '. Stock: ' || v_stock_anterior::text
          || ' -> ' || v_stock_nuevo::text,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        (p_datos - '_modulo' - '_accion' - '_detalle')
        || jsonb_build_object(
            'stock_anterior', v_stock_anterior,
            'stock_nuevo', v_stock_nuevo
        )
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'id', p_datos ->> 'id',
        'stock_anterior', v_stock_anterior,
        'stock_nuevo', v_stock_nuevo
    );

    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;

    return v_respuesta;
end;
$funcion$;

revoke all on function public.actualizar_producto_stock_app(
    uuid,
    uuid,
    jsonb
) from public;

grant execute on function public.actualizar_producto_stock_app(
    uuid,
    uuid,
    jsonb
) to anon, authenticated;

notify pgrst, 'reload schema';

commit;
