-- Registra cada modificación real de precio con valor anterior y nuevo.
-- Puede ejecutarse más de una vez sin duplicar el historial recuperado.

begin;

create table if not exists public.historial_precios (
    id bigserial primary key,
    -- Se almacena como texto para admitir instalaciones con ID bigint o UUID.
    producto_id text,
    producto_nombre text not null,
    precio_anterior numeric not null,
    precio_nuevo numeric not null,
    fecha_hora timestamptz not null default now(),
    usuario_app text not null default 'Cambio directo en base de datos',
    auditoria_id bigint unique,
    transaccion_id bigint not null default txid_current()
);

create index if not exists idx_historial_precios_fecha
    on public.historial_precios(fecha_hora desc);
create index if not exists idx_historial_precios_producto
    on public.historial_precios(producto_id, fecha_hora desc);

create or replace function public.registrar_historial_precio_producto()
returns trigger
language plpgsql
security definer
set search_path = public
as $funcion$
begin
    if new.precio_unitario is distinct from old.precio_unitario then
        insert into public.historial_precios (
            producto_id,
            producto_nombre,
            precio_anterior,
            precio_nuevo,
            fecha_hora,
            transaccion_id
        ) values (
            new.id::text,
            new.nombre,
            coalesce(old.precio_unitario, 0),
            coalesce(new.precio_unitario, 0),
            now(),
            txid_current()
        );
    end if;
    return new;
end;
$funcion$;

drop trigger if exists trg_historial_precio_producto on public.productos;
create trigger trg_historial_precio_producto
after update of precio_unitario on public.productos
for each row
execute function public.registrar_historial_precio_producto();

create or replace function public.completar_usuario_historial_precio()
returns trigger
language plpgsql
security definer
set search_path = public
as $funcion$
declare
    v_producto_id text;
begin
    if new.modulo = 'Inventario'
       and new.accion = 'Editar producto'
       and nullif(trim(coalesce(new.datos ->> 'id', '')), '') is not null then
        v_producto_id := new.datos ->> 'id';
        update public.historial_precios
           set usuario_app = coalesce(
               nullif(trim(new.usuario_app), ''),
               usuario_app
           ),
               auditoria_id = new.id
         where producto_id = v_producto_id
           and transaccion_id = txid_current()
           and auditoria_id is null;
    end if;
    return new;
end;
$funcion$;

drop trigger if exists trg_completar_usuario_historial_precio
    on public.auditoria;
create trigger trg_completar_usuario_historial_precio
after insert on public.auditoria
for each row
execute function public.completar_usuario_historial_precio();

-- Recupera cambios anteriores cuando existe un precio previo comprobable.
with eventos as (
    select
        auditoria.id as auditoria_id,
        coalesce(producto.id::text, auditoria.datos ->> 'id') as producto_id,
        coalesce(
            nullif(auditoria.datos ->> 'nombre', ''),
            producto.nombre,
            'Producto eliminado'
        ) as producto_nombre,
        (auditoria.datos ->> 'precio_unitario')::numeric as precio_nuevo,
        lag((auditoria.datos ->> 'precio_unitario')::numeric) over (
            partition by auditoria.datos ->> 'id'
            order by auditoria.fecha_hora, auditoria.id
        ) as precio_anterior,
        auditoria.fecha_hora,
        coalesce(nullif(auditoria.usuario_app, ''), 'Usuario no identificado')
            as usuario_app
    from public.auditoria auditoria
    left join public.productos producto
      on producto.id::text = auditoria.datos ->> 'id'
    where auditoria.modulo = 'Inventario'
      and auditoria.accion = 'Editar producto'
      and nullif(trim(coalesce(auditoria.datos ->> 'id', '')), '') is not null
      and coalesce(auditoria.datos ->> 'precio_unitario', '')
          ~ '^[0-9]+([.][0-9]+)?$'
), cambios as (
    select *
      from eventos
     where precio_anterior is not null
       and precio_anterior is distinct from precio_nuevo
)
insert into public.historial_precios (
    producto_id,
    producto_nombre,
    precio_anterior,
    precio_nuevo,
    fecha_hora,
    usuario_app,
    auditoria_id
)
select
    cambios.producto_id,
    cambios.producto_nombre,
    cambios.precio_anterior,
    cambios.precio_nuevo,
    cambios.fecha_hora,
    cambios.usuario_app,
    cambios.auditoria_id
from cambios
on conflict (auditoria_id) do nothing;

alter table public.historial_precios enable row level security;
grant select on public.historial_precios to anon, authenticated;
drop policy if exists app_select_historial_precios
    on public.historial_precios;
create policy app_select_historial_precios
    on public.historial_precios
    for select
    to anon, authenticated
    using (true);

revoke insert, update, delete on public.historial_precios
    from anon, authenticated;

notify pgrst, 'reload schema';

commit;
