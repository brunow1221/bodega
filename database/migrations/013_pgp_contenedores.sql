-- Agrupa entregas y préstamos enviados juntos a un proyecto.
-- Cada despacho es atómico: si un artículo falla, no se descuenta ninguno.

begin;

create extension if not exists pgcrypto;
create sequence if not exists public.pgp_codigo_seq;

create table if not exists public.pgp_contenedores (
    id uuid primary key default gen_random_uuid(),
    codigo_pgp text not null unique,
    proyecto_id text not null,
    proyecto_nombre text not null,
    trabajador_id text,
    trabajador_nombre text,
    trabajador_rut text,
    estado text not null default 'Despachado'
        check (estado in (
            'Despachado',
            'Entregado',
            'Devolución parcial',
            'Cerrado'
        )),
    observacion text,
    creado_por_usuario text not null,
    fecha_creacion timestamptz not null default now(),
    fecha_ultima_devolucion timestamptz
);

create table if not exists public.pgp_items (
    id bigserial primary key,
    pgp_id uuid not null references public.pgp_contenedores(id)
        on delete cascade,
    producto_id text not null,
    producto_nombre text not null,
    tipo_movimiento text not null
        check (tipo_movimiento in (
            'Entrega / Consumo',
            'Préstamo de Herramienta'
        )),
    cantidad integer not null check (cantidad > 0),
    cantidad_devuelta integer not null default 0
        check (cantidad_devuelta >= 0 and cantidad_devuelta <= cantidad),
    transaccion_salida_id text,
    creado_en timestamptz not null default now(),
    unique (pgp_id, producto_id)
);

create table if not exists public.pgp_devoluciones (
    id bigserial primary key,
    pgp_id uuid not null references public.pgp_contenedores(id)
        on delete cascade,
    pgp_item_id bigint not null references public.pgp_items(id)
        on delete cascade,
    cantidad integer not null check (cantidad > 0),
    comentario text,
    transaccion_id text,
    usuario_app text not null,
    fecha_hora timestamptz not null default now()
);

alter table public.transacciones
    add column if not exists pgp_id uuid;

create index if not exists idx_pgp_contenedores_fecha
    on public.pgp_contenedores(fecha_creacion desc);
create index if not exists idx_pgp_contenedores_proyecto
    on public.pgp_contenedores(proyecto_id, fecha_creacion desc);
create index if not exists idx_pgp_items_pgp
    on public.pgp_items(pgp_id);
create index if not exists idx_pgp_devoluciones_pgp
    on public.pgp_devoluciones(pgp_id, fecha_hora desc);
create index if not exists idx_transacciones_pgp
    on public.transacciones(pgp_id);

create or replace function public.crear_pgp_app(
    p_token uuid,
    p_request_id uuid,
    p_proyecto text,
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
    v_proyecto public.proyectos%rowtype;
    v_trabajador public.trabajadores%rowtype;
    v_producto public.productos%rowtype;
    v_item jsonb;
    v_pgp_id uuid;
    v_codigo text;
    v_tipo text;
    v_producto_id text;
    v_cantidad integer;
    v_stock_anterior integer;
    v_stock_nuevo integer;
    v_transaccion_id text;
    v_ubicacion text;
    v_tiene_prestamo boolean := false;
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
    values (p_request_id, 'crear_pgp')
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
        raise exception 'Un PGP admite como maximo 100 articulos.';
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
        raise exception 'Un articulo no puede repetirse dentro del mismo PGP.';
    end if;

    select *
      into v_proyecto
      from public.proyectos
     where nombre = trim(coalesce(p_proyecto, ''))
       and estado = 'Activo'
     limit 1;
    if not found then
        raise exception 'Proyecto inexistente o inactivo.';
    end if;

    if nullif(trim(coalesce(p_rut_trabajador, '')), '') is not null then
        select *
          into v_trabajador
          from public.trabajadores
         where rut = trim(p_rut_trabajador)
           and estado = 'Activo'
         limit 1;
        if not found then
            raise exception 'Trabajador inexistente o inactivo.';
        end if;
    end if;

    select exists (
        select 1
          from jsonb_array_elements(p_items) item
         where item ->> 'tipo_movimiento' = 'Préstamo de Herramienta'
    ) into v_tiene_prestamo;
    if v_tiene_prestamo and v_trabajador.id is null then
        raise exception 'Los prestamos requieren un trabajador responsable.';
    end if;

    v_codigo := 'PGP-' || to_char(current_date, 'YYYY') || '-' ||
        lpad(nextval('public.pgp_codigo_seq')::text, 5, '0');

    insert into public.pgp_contenedores (
        codigo_pgp,
        proyecto_id,
        proyecto_nombre,
        trabajador_id,
        trabajador_nombre,
        trabajador_rut,
        estado,
        observacion,
        creado_por_usuario
    ) values (
        v_codigo,
        v_proyecto.id::text,
        v_proyecto.nombre,
        case when v_trabajador.id is null then null else v_trabajador.id::text end,
        v_trabajador.nombre,
        v_trabajador.rut,
        'Despachado',
        nullif(trim(coalesce(p_observacion, '')), ''),
        v_sesion.nombre || ' (' || v_sesion.usuario || ')'
    ) returning id into v_pgp_id;

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
            concat_ws(' | ', v_codigo, nullif(trim(coalesce(p_observacion, '')), '')),
            v_sesion.nombre || ' (' || v_sesion.usuario || ')',
            coalesce(v_producto.precio_unitario, 0),
            v_producto.nombre,
            v_producto.codigo_barras,
            v_ubicacion,
            v_pgp_id
        ) returning id::text into v_transaccion_id;

        insert into public.pgp_items (
            pgp_id, producto_id, producto_nombre, tipo_movimiento,
            cantidad, transaccion_salida_id
        ) values (
            v_pgp_id,
            v_producto.id::text,
            v_producto.nombre,
            v_tipo,
            v_cantidad,
            v_transaccion_id
        );
    end loop;

    insert into public.auditoria (
        modulo, accion, detalle, usuario_app, datos
    ) values (
        'PGP',
        'Despachar contenedor',
        v_codigo || ' | Proyecto: ' || v_proyecto.nombre,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        jsonb_build_object(
            'pgp_id', v_pgp_id,
            'codigo_pgp', v_codigo,
            'proyecto_id', v_proyecto.id,
            'trabajador_id', v_trabajador.id,
            'items', p_items
        )
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'pgp_id', v_pgp_id,
        'codigo_pgp', v_codigo,
        'cantidad_items', jsonb_array_length(p_items)
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;
    return v_respuesta;
end;
$funcion$;

create or replace function public.devolver_item_pgp_app(
    p_token uuid,
    p_request_id uuid,
    p_pgp_id uuid,
    p_item_id bigint,
    p_cantidad integer,
    p_comentario text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $funcion$
declare
    v_sesion public.sesiones_app%rowtype;
    v_pgp public.pgp_contenedores%rowtype;
    v_item public.pgp_items%rowtype;
    v_producto public.productos%rowtype;
    v_proyecto public.proyectos%rowtype;
    v_trabajador public.trabajadores%rowtype;
    v_stock_anterior integer;
    v_stock_nuevo integer;
    v_pendiente integer;
    v_pendiente_total integer;
    v_transaccion_id text;
    v_ubicacion text;
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
    values (p_request_id, 'devolver_item_pgp')
    on conflict (request_id) do nothing;
    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    if p_cantidad is null or p_cantidad <= 0 then
        raise exception 'La cantidad debe ser mayor a cero.';
    end if;
    if char_length(coalesce(p_comentario, '')) > 1000 then
        raise exception 'El comentario admite como maximo 1.000 caracteres.';
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
      into v_item
      from public.pgp_items
     where id = p_item_id
       and pgp_id = p_pgp_id
     for update;
    if not found then
        raise exception 'El articulo no pertenece al PGP seleccionado.';
    end if;
    v_pendiente := v_item.cantidad - v_item.cantidad_devuelta;
    if p_cantidad > v_pendiente then
        raise exception 'La devolucion supera la cantidad pendiente (%).', v_pendiente;
    end if;

    select *
      into v_producto
      from public.productos
     where id::text = v_item.producto_id
     for update;
    if not found then
        raise exception 'El articulo asociado al PGP ya no existe.';
    end if;
    select * into v_proyecto
      from public.proyectos
     where id::text = v_pgp.proyecto_id
     limit 1;
    select * into v_trabajador
      from public.trabajadores
     where id::text = v_pgp.trabajador_id
     limit 1;

    v_stock_anterior := coalesce(v_producto.stock, 0);
    v_stock_nuevo := v_stock_anterior + p_cantidad;
    update public.productos
       set stock = v_stock_nuevo
     where id = v_producto.id;

    select codigo_ubicacion
      into v_ubicacion
      from public.ubicaciones
     where id = v_producto.ubicacion_id;

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
        'Devolución PGP',
        p_cantidad,
        v_stock_anterior,
        v_stock_nuevo,
        concat_ws(' | ', v_pgp.codigo_pgp, nullif(trim(coalesce(p_comentario, '')), '')),
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        coalesce(v_producto.precio_unitario, 0),
        v_producto.nombre,
        v_producto.codigo_barras,
        v_ubicacion,
        v_pgp.id
    ) returning id::text into v_transaccion_id;

    update public.pgp_items
       set cantidad_devuelta = cantidad_devuelta + p_cantidad
     where id = v_item.id;

    insert into public.pgp_devoluciones (
        pgp_id, pgp_item_id, cantidad, comentario,
        transaccion_id, usuario_app
    ) values (
        v_pgp.id,
        v_item.id,
        p_cantidad,
        nullif(trim(coalesce(p_comentario, '')), ''),
        v_transaccion_id,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')'
    );

    select coalesce(sum(greatest(cantidad - cantidad_devuelta, 0)), 0)::integer
     into v_pendiente_total
      from public.pgp_items
     where pgp_id = v_pgp.id;

    update public.pgp_contenedores
       set estado = case
               when v_pendiente_total = 0 then 'Cerrado'
               else 'Devolución parcial'
           end,
           fecha_ultima_devolucion = now()
     where id = v_pgp.id;

    insert into public.auditoria (
        modulo, accion, detalle, usuario_app, datos
    ) values (
        'PGP',
        'Registrar devolución',
        v_pgp.codigo_pgp || ' | ' || v_item.producto_nombre ||
            ' | Cantidad: ' || p_cantidad,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        jsonb_build_object(
            'pgp_id', v_pgp.id,
            'pgp_item_id', v_item.id,
            'producto_id', v_item.producto_id,
            'cantidad', p_cantidad,
            'pendiente_total', v_pendiente_total
        )
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'stock_anterior', v_stock_anterior,
        'stock_nuevo', v_stock_nuevo,
        'pendiente_item', v_pendiente - p_cantidad,
        'pendiente_pgp', v_pendiente_total
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;
    return v_respuesta;
end;
$funcion$;

create or replace function public.devolver_pgp_completo_app(
    p_token uuid,
    p_request_id uuid,
    p_pgp_id uuid,
    p_comentario text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $funcion$
declare
    v_sesion public.sesiones_app%rowtype;
    v_pgp public.pgp_contenedores%rowtype;
    v_item public.pgp_items%rowtype;
    v_producto public.productos%rowtype;
    v_proyecto public.proyectos%rowtype;
    v_trabajador public.trabajadores%rowtype;
    v_stock_anterior integer;
    v_stock_nuevo integer;
    v_cantidad integer;
    v_total_items integer := 0;
    v_total_unidades integer := 0;
    v_transaccion_id text;
    v_ubicacion text;
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
    values (p_request_id, 'devolver_pgp_completo')
    on conflict (request_id) do nothing;
    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    if char_length(coalesce(p_comentario, '')) > 1000 then
        raise exception 'El comentario admite como maximo 1.000 caracteres.';
    end if;

    select *
      into v_pgp
      from public.pgp_contenedores
     where id = p_pgp_id
     for update;
    if not found then
        raise exception 'El PGP seleccionado no existe.';
    end if;

    select * into v_proyecto
      from public.proyectos
     where id::text = v_pgp.proyecto_id
     limit 1;
    select * into v_trabajador
      from public.trabajadores
     where id::text = v_pgp.trabajador_id
     limit 1;

    for v_item in
        select *
          from public.pgp_items
         where pgp_id = v_pgp.id
           and cantidad_devuelta < cantidad
         order by id
         for update
    loop
        v_cantidad := v_item.cantidad - v_item.cantidad_devuelta;

        select *
          into v_producto
          from public.productos
         where id::text = v_item.producto_id
         for update;
        if not found then
            raise exception 'El articulo % asociado al PGP ya no existe.',
                v_item.producto_nombre;
        end if;

        v_stock_anterior := coalesce(v_producto.stock, 0);
        v_stock_nuevo := v_stock_anterior + v_cantidad;
        update public.productos
           set stock = v_stock_nuevo
         where id = v_producto.id;

        select codigo_ubicacion
          into v_ubicacion
          from public.ubicaciones
         where id = v_producto.ubicacion_id;

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
            'Devolución PGP',
            v_cantidad,
            v_stock_anterior,
            v_stock_nuevo,
            concat_ws(
                ' | ',
                v_pgp.codigo_pgp,
                'Devolución completa',
                nullif(trim(coalesce(p_comentario, '')), '')
            ),
            v_sesion.nombre || ' (' || v_sesion.usuario || ')',
            coalesce(v_producto.precio_unitario, 0),
            v_producto.nombre,
            v_producto.codigo_barras,
            v_ubicacion,
            v_pgp.id
        ) returning id::text into v_transaccion_id;

        update public.pgp_items
           set cantidad_devuelta = cantidad
         where id = v_item.id;

        insert into public.pgp_devoluciones (
            pgp_id, pgp_item_id, cantidad, comentario,
            transaccion_id, usuario_app
        ) values (
            v_pgp.id,
            v_item.id,
            v_cantidad,
            nullif(trim(coalesce(p_comentario, '')), ''),
            v_transaccion_id,
            v_sesion.nombre || ' (' || v_sesion.usuario || ')'
        );

        v_total_items := v_total_items + 1;
        v_total_unidades := v_total_unidades + v_cantidad;
    end loop;

    if v_total_items = 0 then
        raise exception 'El PGP ya fue devuelto completamente.';
    end if;

    update public.pgp_contenedores
       set estado = 'Cerrado',
           fecha_ultima_devolucion = now()
     where id = v_pgp.id;

    insert into public.auditoria (
        modulo, accion, detalle, usuario_app, datos
    ) values (
        'PGP',
        'Devolución completa',
        v_pgp.codigo_pgp || ' | Articulos: ' || v_total_items ||
            ' | Unidades: ' || v_total_unidades,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        jsonb_build_object(
            'pgp_id', v_pgp.id,
            'articulos_devueltos', v_total_items,
            'unidades_devueltas', v_total_unidades
        )
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'articulos_devueltos', v_total_items,
        'unidades_devueltas', v_total_unidades,
        'pendiente_pgp', 0
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;
    return v_respuesta;
end;
$funcion$;

alter table public.pgp_contenedores enable row level security;
alter table public.pgp_items enable row level security;
alter table public.pgp_devoluciones enable row level security;

grant select on public.pgp_contenedores, public.pgp_items,
    public.pgp_devoluciones to anon, authenticated;

drop policy if exists app_select_pgp_contenedores
    on public.pgp_contenedores;
create policy app_select_pgp_contenedores
    on public.pgp_contenedores for select to anon, authenticated
    using (true);

drop policy if exists app_select_pgp_items on public.pgp_items;
create policy app_select_pgp_items
    on public.pgp_items for select to anon, authenticated
    using (true);

drop policy if exists app_select_pgp_devoluciones
    on public.pgp_devoluciones;
create policy app_select_pgp_devoluciones
    on public.pgp_devoluciones for select to anon, authenticated
    using (true);

revoke insert, update, delete on public.pgp_contenedores,
    public.pgp_items, public.pgp_devoluciones from anon, authenticated;

revoke all on function public.crear_pgp_app(
    uuid, uuid, text, text, text, jsonb
) from public;
grant execute on function public.crear_pgp_app(
    uuid, uuid, text, text, text, jsonb
) to anon, authenticated;

revoke all on function public.devolver_item_pgp_app(
    uuid, uuid, uuid, bigint, integer, text
) from public;
grant execute on function public.devolver_item_pgp_app(
    uuid, uuid, uuid, bigint, integer, text
) to anon, authenticated;

revoke all on function public.devolver_pgp_completo_app(
    uuid, uuid, uuid, text
) from public;
grant execute on function public.devolver_pgp_completo_app(
    uuid, uuid, uuid, text
) to anon, authenticated;

notify pgrst, 'reload schema';

commit;
