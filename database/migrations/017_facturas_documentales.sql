-- Registra facturas de compra como respaldo documental.
-- Esta migracion NO modifica stock, precios vigentes ni transacciones.

begin;

create extension if not exists pgcrypto;

create table if not exists public.facturas_compra (
    id uuid primary key default gen_random_uuid(),
    proveedor text not null,
    numero_factura text not null,
    fecha_factura date not null,
    ruta_archivo text not null,
    archivo_original text not null,
    observacion text,
    estado text not null default 'Activa',
    usuario_app text not null,
    creado_en timestamptz not null default now(),
    constraint facturas_compra_estado_valido
        check (estado in ('Activa', 'Anulada'))
);

create table if not exists public.factura_items (
    id bigserial primary key,
    factura_id uuid not null references public.facturas_compra(id),
    -- Texto mantiene compatibilidad con instalaciones que usan bigint o UUID.
    producto_id text not null,
    producto_nombre text not null,
    cantidad numeric(14, 3) not null,
    precio_unitario numeric(16, 4) not null default 0,
    creado_en timestamptz not null default now(),
    constraint factura_items_cantidad_positiva check (cantidad > 0),
    constraint factura_items_precio_no_negativo check (precio_unitario >= 0),
    constraint factura_items_producto_unico unique (factura_id, producto_id)
);

create unique index if not exists uq_factura_proveedor_numero_activa
    on public.facturas_compra (
        lower(trim(proveedor)),
        lower(trim(numero_factura))
    )
    where estado = 'Activa';

create index if not exists idx_factura_items_producto_factura
    on public.factura_items(producto_id, factura_id);
create index if not exists idx_facturas_compra_fecha
    on public.facturas_compra(fecha_factura desc, creado_en desc);

create or replace function public.registrar_factura_compra_app(
    p_token uuid,
    p_request_id uuid,
    p_factura jsonb,
    p_items jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $funcion$
declare
    v_sesion public.sesiones_app%rowtype;
    v_factura_id uuid;
    v_item jsonb;
    v_producto record;
    v_proveedor text;
    v_numero text;
    v_fecha date;
    v_ruta text;
    v_archivo text;
    v_observacion text;
    v_producto_id text;
    v_cantidad numeric;
    v_precio numeric;
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
    values (p_request_id, 'registrar_factura_compra')
    on conflict (request_id) do nothing;
    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    if jsonb_typeof(p_factura) is distinct from 'object' then
        raise exception 'Los datos de la factura no son validos.';
    end if;
    if jsonb_typeof(p_items) is distinct from 'array'
       or jsonb_array_length(p_items) = 0 then
        raise exception 'La factura debe estar asociada al menos a un producto.';
    end if;
    if jsonb_array_length(p_items) > 100 then
        raise exception 'Una factura admite como maximo 100 productos.';
    end if;
    if exists (
        select 1
          from jsonb_array_elements(p_items) item
         group by item ->> 'producto_id'
        having count(*) > 1
    ) then
        raise exception 'Un producto no puede repetirse en la misma factura.';
    end if;

    v_proveedor := trim(coalesce(p_factura ->> 'proveedor', ''));
    v_numero := trim(coalesce(p_factura ->> 'numero_factura', ''));
    v_ruta := trim(coalesce(p_factura ->> 'ruta_archivo', ''));
    v_archivo := trim(coalesce(p_factura ->> 'archivo_original', ''));
    v_observacion := nullif(trim(coalesce(p_factura ->> 'observacion', '')), '');

    if v_proveedor = '' or char_length(v_proveedor) > 200 then
        raise exception 'El proveedor es obligatorio y admite hasta 200 caracteres.';
    end if;
    if v_numero = '' or char_length(v_numero) > 100 then
        raise exception 'El numero de factura es obligatorio y admite hasta 100 caracteres.';
    end if;
    if v_ruta = '' or char_length(v_ruta) > 1000
       or v_ruta like '/%' or v_ruta like E'\\\\%'
       or v_ruta ~ '(^|[\\/])\.\.([\\/]|$)' then
        raise exception 'La ruta relativa del archivo no es valida.';
    end if;
    if v_archivo = '' or char_length(v_archivo) > 255 then
        raise exception 'El nombre original del archivo no es valido.';
    end if;
    if char_length(coalesce(v_observacion, '')) > 2000 then
        raise exception 'La observacion admite hasta 2.000 caracteres.';
    end if;

    begin
        v_fecha := (p_factura ->> 'fecha_factura')::date;
    exception when others then
        raise exception 'La fecha de la factura no es valida.';
    end;

    begin
        insert into public.facturas_compra (
            proveedor,
            numero_factura,
            fecha_factura,
            ruta_archivo,
            archivo_original,
            observacion,
            usuario_app
        ) values (
            v_proveedor,
            v_numero,
            v_fecha,
            v_ruta,
            v_archivo,
            v_observacion,
            v_sesion.nombre || ' (' || v_sesion.usuario || ')'
        ) returning id into v_factura_id;
    exception when unique_violation then
        raise exception 'Ya existe una factura activa de este proveedor con el mismo numero.';
    end;

    for v_item in
        select item
          from jsonb_array_elements(p_items) item
         order by item ->> 'producto_id'
    loop
        v_producto_id := trim(coalesce(v_item ->> 'producto_id', ''));
        if v_producto_id = '' then
            raise exception 'Uno de los productos no tiene identificador.';
        end if;
        if coalesce(v_item ->> 'cantidad', '') !~ '^[0-9]+([.][0-9]{1,3})?$'
           or (v_item ->> 'cantidad')::numeric <= 0 then
            raise exception 'Las cantidades deben ser numeros mayores que cero.';
        end if;
        if coalesce(v_item ->> 'precio_unitario', '') !~ '^[0-9]+([.][0-9]{1,4})?$'
           or (v_item ->> 'precio_unitario')::numeric < 0 then
            raise exception 'Los precios deben ser numeros mayores o iguales a cero.';
        end if;

        select id::text as id, nombre
          into v_producto
          from public.productos
         where id::text = v_producto_id
         limit 1;
        if not found then
            raise exception 'Uno de los productos asociados no existe.';
        end if;

        v_cantidad := (v_item ->> 'cantidad')::numeric;
        v_precio := (v_item ->> 'precio_unitario')::numeric;

        insert into public.factura_items (
            factura_id,
            producto_id,
            producto_nombre,
            cantidad,
            precio_unitario
        ) values (
            v_factura_id,
            v_producto.id,
            v_producto.nombre,
            v_cantidad,
            v_precio
        );
    end loop;

    insert into public.auditoria (
        modulo,
        accion,
        detalle,
        usuario_app,
        datos
    ) values (
        'Facturas',
        'Registrar factura documental',
        v_proveedor || ' | Factura ' || v_numero,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        jsonb_build_object(
            'factura_id', v_factura_id,
            'proveedor', v_proveedor,
            'numero_factura', v_numero,
            'fecha_factura', v_fecha,
            'items', p_items
        )
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'factura_id', v_factura_id
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;
    return v_respuesta;
end;
$funcion$;

create or replace function public.listar_facturas_producto_app(
    p_token uuid,
    p_producto_id text
)
returns table (
    factura_id uuid,
    proveedor text,
    numero_factura text,
    fecha_factura date,
    cantidad numeric,
    precio_unitario numeric,
    ruta_archivo text,
    archivo_original text,
    observacion text,
    usuario_app text,
    creado_en timestamptz
)
language plpgsql
security definer
set search_path = public
as $funcion$
begin
    perform public.validar_sesion_app(p_token, false);

    return query
    select
        factura.id,
        factura.proveedor,
        factura.numero_factura,
        factura.fecha_factura,
        item.cantidad,
        item.precio_unitario,
        factura.ruta_archivo,
        factura.archivo_original,
        factura.observacion,
        factura.usuario_app,
        factura.creado_en
    from public.factura_items item
    join public.facturas_compra factura on factura.id = item.factura_id
    where item.producto_id = trim(coalesce(p_producto_id, ''))
      and factura.estado = 'Activa'
    order by factura.fecha_factura desc, factura.creado_en desc;
end;
$funcion$;

alter table public.facturas_compra enable row level security;
alter table public.factura_items enable row level security;

revoke all on public.facturas_compra, public.factura_items
    from public, anon, authenticated;

revoke all on function public.registrar_factura_compra_app(
    uuid, uuid, jsonb, jsonb
) from public;
grant execute on function public.registrar_factura_compra_app(
    uuid, uuid, jsonb, jsonb
) to anon, authenticated;

revoke all on function public.listar_facturas_producto_app(
    uuid, text
) from public;
grant execute on function public.listar_facturas_producto_app(
    uuid, text
) to anon, authenticated;

notify pgrst, 'reload schema';

commit;
