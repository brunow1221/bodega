-- Permite agregar nuevas salidas a un PGP existente durante la faena.
-- Toda la ampliación es atómica: si un artículo falla, no se descuenta ninguno.

begin;

alter table public.pgp_items
    drop constraint if exists pgp_items_pgp_id_producto_id_key;
create index if not exists idx_pgp_items_pgp_producto
    on public.pgp_items(pgp_id, producto_id);

create or replace function public.agregar_items_pgp_app(
    p_token uuid,
    p_request_id uuid,
    p_pgp_id uuid,
    p_rut_trabajador text,
    p_observacion text,
    p_items jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $funcion$
declare
    v_sesion public.sesiones_app%rowtype;
    v_pgp public.pgp_contenedores%rowtype;
    v_proyecto public.proyectos%rowtype;
    v_trabajador public.trabajadores%rowtype;
    v_producto public.productos%rowtype;
    v_item jsonb;
    v_tipo text;
    v_producto_id text;
    v_cantidad integer;
    v_stock_anterior integer;
    v_stock_nuevo integer;
    v_transaccion_id text;
    v_ubicacion text;
    v_tiene_prestamo boolean := false;
    v_items_agregados integer := 0;
    v_unidades_agregadas integer := 0;
    v_hay_devoluciones boolean := false;
    v_total_lineas integer := 0;
    v_respuesta jsonb;
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
    values (p_request_id, 'agregar_items_pgp')
    on conflict (request_id) do nothing;
    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    if jsonb_typeof(p_items) is distinct from 'array'
       or jsonb_array_length(p_items) = 0 then
        raise exception 'Agregue al menos un articulo al PGP.';
    end if;
    if jsonb_array_length(p_items) > 100 then
        raise exception 'Una ampliacion admite como maximo 100 articulos.';
    end if;
    if char_length(coalesce(p_observacion, '')) > 1000 then
        raise exception 'La observacion admite como maximo 1.000 caracteres.';
    end if;
    if exists (
        select 1
          from jsonb_array_elements(p_items) item
         group by item ->> 'producto_id'
        having count(*) > 1
    ) then
        raise exception 'Un articulo no puede repetirse en la misma ampliacion.';
    end if;

    select *
      into v_pgp
      from public.pgp_contenedores
     where id = p_pgp_id
     for update;
    if not found then
        raise exception 'El PGP seleccionado no existe.';
    end if;
    select *
      into v_proyecto
      from public.proyectos
     where id::text = v_pgp.proyecto_id
       and estado = 'Activo'
     limit 1;
    if not found then
        raise exception 'El proyecto del PGP ya no se encuentra activo.';
    end if;

    if v_pgp.trabajador_id is not null then
        select *
          into v_trabajador
          from public.trabajadores
         where id::text = v_pgp.trabajador_id
         limit 1;
        if nullif(trim(coalesce(p_rut_trabajador, '')), '') is not null
           and trim(p_rut_trabajador) <> coalesce(v_pgp.trabajador_rut, '') then
            raise exception 'El responsable no coincide con el asignado al PGP.';
        end if;
    elsif nullif(trim(coalesce(p_rut_trabajador, '')), '') is not null then
        select *
          into v_trabajador
          from public.trabajadores
         where rut = trim(p_rut_trabajador)
           and estado = 'Activo'
         limit 1;
        if not found then
            raise exception 'Trabajador inexistente o inactivo.';
        end if;
        update public.pgp_contenedores
           set trabajador_id = v_trabajador.id::text,
               trabajador_nombre = v_trabajador.nombre,
               trabajador_rut = v_trabajador.rut
         where id = v_pgp.id;
    end if;

    select exists (
        select 1
          from jsonb_array_elements(p_items) item
         where item ->> 'tipo_movimiento' = 'Préstamo de Herramienta'
    ) into v_tiene_prestamo;
    if v_tiene_prestamo and (
        v_trabajador.id is null
        or coalesce(v_trabajador.estado, '') <> 'Activo'
    ) then
        raise exception 'Los prestamos requieren un trabajador responsable activo.';
    end if;

    select count(*)::integer
      into v_total_lineas
      from public.pgp_items
     where pgp_id = v_pgp.id;
    if v_total_lineas + jsonb_array_length(p_items) > 500 then
        raise exception 'Un PGP admite como maximo 500 lineas de despacho.';
    end if;

    for v_item in
        select item
          from jsonb_array_elements(p_items) item
         order by item ->> 'producto_id'
    loop
        v_producto_id := nullif(trim(v_item ->> 'producto_id'), '');
        v_tipo := v_item ->> 'tipo_movimiento';
        if coalesce(v_item ->> 'cantidad', '') !~ '^[1-9][0-9]*$' then
            raise exception 'Todas las cantidades deben ser enteros mayores a cero.';
        end if;
        v_cantidad := (v_item ->> 'cantidad')::integer;
        if v_tipo not in ('Entrega / Consumo', 'Préstamo de Herramienta') then
            raise exception 'Tipo de movimiento PGP no permitido.';
        end if;

        select *
          into v_producto
          from public.productos
         where id::text = v_producto_id
           and estado = 'Activo'
         for update;
        if not found then
            raise exception 'Uno de los articulos no existe o esta inactivo.';
        end if;

        v_stock_anterior := coalesce(v_producto.stock, 0);
        if v_stock_anterior < v_cantidad then
            raise exception 'Stock insuficiente para %. Disponible: %.',
                v_producto.nombre,
                v_stock_anterior;
        end if;
        v_stock_nuevo := v_stock_anterior - v_cantidad;

        select codigo_ubicacion
          into v_ubicacion
          from public.ubicaciones
         where id = v_producto.ubicacion_id;

        update public.productos
           set stock = v_stock_nuevo
         where id = v_producto.id;

        insert into public.transacciones (
            producto_id, proyecto_id, trabajador_id, tipo_movimiento,
            cantidad_movida, stock_anterior, stock_nuevo, comentario,
            creado_por_usuario, precio_unitario_movimiento,
            producto_nombre_snapshot, producto_codigo_snapshot,
            ubicacion_snapshot, pgp_id
        ) values (
            v_producto.id,
            v_proyecto.id,
            v_trabajador.id,
            v_tipo,
            v_cantidad,
            v_stock_anterior,
            v_stock_nuevo,
            concat_ws(
                ' | ',
                v_pgp.codigo_pgp,
                'Ampliacion',
                nullif(trim(coalesce(p_observacion, '')), '')
            ),
            v_sesion.nombre || ' (' || v_sesion.usuario || ')',
            coalesce(v_producto.precio_unitario, 0),
            v_producto.nombre,
            v_producto.codigo_barras,
            v_ubicacion,
            v_pgp.id
        ) returning id::text into v_transaccion_id;

        insert into public.pgp_items (
            pgp_id, producto_id, producto_nombre, tipo_movimiento,
            cantidad, transaccion_salida_id
        ) values (
            v_pgp.id,
            v_producto.id::text,
            v_producto.nombre,
            v_tipo,
            v_cantidad,
            v_transaccion_id
        );

        v_items_agregados := v_items_agregados + 1;
        v_unidades_agregadas := v_unidades_agregadas + v_cantidad;
    end loop;

    select exists (
        select 1
          from public.pgp_items
         where pgp_id = v_pgp.id
           and cantidad_devuelta > 0
    ) into v_hay_devoluciones;

    update public.pgp_contenedores
       set estado = case
               when v_hay_devoluciones then 'Devolución parcial'
               else 'Despachado'
           end
     where id = v_pgp.id;

    insert into public.auditoria (
        modulo, accion, detalle, usuario_app, datos
    ) values (
        'PGP',
        'Agregar articulos',
        v_pgp.codigo_pgp || ' | Articulos: ' || v_items_agregados ||
            ' | Unidades: ' || v_unidades_agregadas,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        jsonb_build_object(
            'pgp_id', v_pgp.id,
            'codigo_pgp', v_pgp.codigo_pgp,
            'items', p_items,
            'observacion', nullif(trim(coalesce(p_observacion, '')), '')
        )
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'pgp_id', v_pgp.id,
        'codigo_pgp', v_pgp.codigo_pgp,
        'items_agregados', v_items_agregados,
        'unidades_agregadas', v_unidades_agregadas
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;
    return v_respuesta;
end;
$funcion$;

revoke all on function public.agregar_items_pgp_app(
    uuid, uuid, uuid, text, text, jsonb
) from public;
grant execute on function public.agregar_items_pgp_app(
    uuid, uuid, uuid, text, text, jsonb
) to anon, authenticated;

notify pgrst, 'reload schema';

commit;
