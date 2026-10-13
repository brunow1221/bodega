-- Ejecutar primero si la base viene de una version antigua del sistema.
-- Crea las tablas/columnas minimas que la aplicacion actual necesita.

create extension if not exists pgcrypto;

create table if not exists public.categorias (
    id bigserial primary key,
    nombre text not null,
    descripcion text,
    estado text not null default 'Activo',
    creado_en timestamptz not null default now()
);

alter table public.categorias
    add column if not exists nombre text,
    add column if not exists descripcion text,
    add column if not exists estado text not null default 'Activo',
    add column if not exists creado_en timestamptz not null default now();

create table if not exists public.config_app (
    clave text primary key,
    valor text,
    actualizado_en timestamptz not null default now()
);

alter table public.config_app
    add column if not exists clave text,
    add column if not exists valor text,
    add column if not exists actualizado_en timestamptz not null default now();

insert into public.config_app (clave, valor)
values
    ('version_actual', '1.0.0'),
    ('mensaje_update', 'Hay una nueva version disponible.'),
    ('url_descarga', 'pendiente')
on conflict (clave) do nothing;

create table if not exists public.proyectos (
    id bigserial primary key,
    nombre text not null,
    ot text,
    cliente text,
    descripcion text,
    fecha_inicio date,
    fecha_fin date,
    estado text not null default 'Activo',
    creado_en timestamptz not null default now()
);

alter table public.proyectos
    add column if not exists nombre text,
    add column if not exists ot text,
    add column if not exists cliente text,
    add column if not exists descripcion text,
    add column if not exists fecha_inicio date,
    add column if not exists fecha_fin date,
    add column if not exists estado text not null default 'Activo',
    add column if not exists creado_en timestamptz not null default now();

insert into public.proyectos (nombre, ot, cliente, descripcion, estado)
select 'Taller Interno', 'INTERNO', 'Interno', 'Proyecto interno por defecto', 'Activo'
where not exists (
    select 1 from public.proyectos where nombre = 'Taller Interno'
);

create table if not exists public.trabajadores (
    id bigserial primary key,
    rut text not null,
    nombre text not null,
    cargo text,
    estado text not null default 'Activo',
    creado_en timestamptz not null default now()
);

alter table public.trabajadores
    add column if not exists rut text,
    add column if not exists nombre text,
    add column if not exists cargo text,
    add column if not exists estado text not null default 'Activo',
    add column if not exists creado_en timestamptz not null default now();

create table if not exists public.bodegas (
    id bigserial primary key,
    codigo_bodega text,
    nombre text not null,
    descripcion text,
    estado text not null default 'Activo',
    creado_en timestamptz not null default now()
);

alter table public.bodegas
    add column if not exists codigo_bodega text,
    add column if not exists nombre text,
    add column if not exists descripcion text,
    add column if not exists estado text not null default 'Activo',
    add column if not exists creado_en timestamptz not null default now();

create table if not exists public.racks (
    id bigserial primary key,
    bodega_id bigint,
    codigo_rack text not null,
    nombre text,
    descripcion text,
    niveles integer not null default 5,
    columnas integer not null default 2,
    ancho_cm numeric,
    alto_cm numeric,
    profundidad_cm numeric,
    capacidad_kg numeric,
    posicion_orden integer,
    estado text not null default 'Activo',
    creado_en timestamptz not null default now()
);

alter table public.racks
    add column if not exists bodega_id bigint,
    add column if not exists codigo_rack text,
    add column if not exists nombre text,
    add column if not exists descripcion text,
    add column if not exists niveles integer not null default 5,
    add column if not exists columnas integer not null default 2,
    add column if not exists ancho_cm numeric,
    add column if not exists alto_cm numeric,
    add column if not exists profundidad_cm numeric,
    add column if not exists capacidad_kg numeric,
    add column if not exists posicion_orden integer,
    add column if not exists estado text not null default 'Activo',
    add column if not exists creado_en timestamptz not null default now();

create table if not exists public.ubicaciones (
    id bigserial primary key,
    bodega_id bigint,
    rack_id bigint,
    codigo_ubicacion text not null,
    tipo text not null default 'Bloque',
    nivel text,
    columna text,
    subdivision text,
    ubicacion_padre_id bigint,
    descripcion text,
    estado text not null default 'Activo',
    creado_en timestamptz not null default now()
);

alter table public.ubicaciones
    add column if not exists bodega_id bigint,
    add column if not exists rack_id bigint,
    add column if not exists codigo_ubicacion text,
    add column if not exists tipo text not null default 'Bloque',
    add column if not exists nivel text,
    add column if not exists columna text,
    add column if not exists subdivision text,
    add column if not exists ubicacion_padre_id bigint,
    add column if not exists descripcion text,
    add column if not exists estado text not null default 'Activo',
    add column if not exists creado_en timestamptz not null default now();

create table if not exists public.productos (
    id bigserial primary key,
    codigo_barras text,
    nombre text not null,
    categoria text,
    subcategoria text,
    marca text,
    "tamaño_dimensiones" text,
    talla text,
    stock integer not null default 0,
    stock_minimo integer not null default 0,
    precio_unitario numeric not null default 0,
    ubicacion_id bigint,
    estado text not null default 'Activo',
    tipo_medicion text not null default 'No aplica',
    medida_largo numeric,
    medida_ancho numeric,
    unidad_medida text,
    producto_origen_id bigint,
    es_retazo boolean not null default false,
    porcentaje_valor_origen numeric,
    observacion_retazo text,
    creado_en timestamptz not null default now()
);

alter table public.productos
    add column if not exists codigo_barras text,
    add column if not exists nombre text,
    add column if not exists categoria text,
    add column if not exists subcategoria text,
    add column if not exists marca text,
    add column if not exists "tamaño_dimensiones" text,
    add column if not exists talla text,
    add column if not exists stock integer not null default 0,
    add column if not exists stock_minimo integer not null default 0,
    add column if not exists precio_unitario numeric not null default 0,
    add column if not exists ubicacion_id bigint,
    add column if not exists estado text not null default 'Activo',
    add column if not exists tipo_medicion text not null default 'No aplica',
    add column if not exists medida_largo numeric,
    add column if not exists medida_ancho numeric,
    add column if not exists unidad_medida text,
    add column if not exists producto_origen_id bigint,
    add column if not exists es_retazo boolean not null default false,
    add column if not exists porcentaje_valor_origen numeric,
    add column if not exists observacion_retazo text,
    add column if not exists creado_en timestamptz not null default now();

create table if not exists public.transacciones (
    id bigserial primary key,
    producto_id bigint,
    proyecto_id bigint,
    trabajador_id bigint,
    tipo_movimiento text,
    cantidad_movida integer not null default 1,
    stock_anterior integer,
    stock_nuevo integer,
    comentario text,
    creado_por_usuario text,
    fecha_hora timestamptz not null default now()
);

alter table public.transacciones
    add column if not exists producto_id bigint,
    add column if not exists proyecto_id bigint,
    add column if not exists trabajador_id bigint,
    add column if not exists tipo_movimiento text,
    add column if not exists cantidad_movida integer not null default 1,
    add column if not exists stock_anterior integer,
    add column if not exists stock_nuevo integer,
    add column if not exists comentario text,
    add column if not exists creado_por_usuario text,
    add column if not exists fecha_hora timestamptz not null default now();

create table if not exists public.auditoria (
    id bigserial primary key,
    modulo text,
    accion text,
    detalle text,
    usuario_app text,
    datos jsonb,
    fecha_hora timestamptz not null default now()
);

alter table public.auditoria
    add column if not exists modulo text,
    add column if not exists accion text,
    add column if not exists detalle text,
    add column if not exists usuario_app text,
    add column if not exists datos jsonb,
    add column if not exists fecha_hora timestamptz not null default now();

do $$
declare
    v_bodega_id bigint;
    v_i integer;
    v_estante integer;
    v_codigo text;
    v_rack record;
begin
    select id
      into v_bodega_id
      from public.bodegas
     where estado = 'Activo'
     order by id
     limit 1;

    if v_bodega_id is null then
        insert into public.bodegas (codigo_bodega, nombre, descripcion, estado)
        values ('B1', 'Bodega 1', 'Bodega principal', 'Activo')
        returning id into v_bodega_id;
    end if;

    if not exists (select 1 from public.racks) then
        for v_i in 1..2 loop
            insert into public.racks (
                bodega_id, codigo_rack, nombre, descripcion,
                niveles, columnas, ancho_cm, alto_cm, profundidad_cm,
                posicion_orden, estado
            )
            values (
                v_bodega_id,
                chr(64 + v_i),
                'Sector ' || chr(64 + v_i),
                'Sector inicial',
                5,
                2,
                200,
                220,
                80,
                v_i,
                'Activo'
            );
        end loop;
    end if;

    update public.racks
       set bodega_id = coalesce(bodega_id, v_bodega_id),
           niveles = coalesce(niveles, 5),
           columnas = coalesce(columnas, 2),
           posicion_orden = coalesce(
               posicion_orden,
               nullif(regexp_replace(codigo_rack, '\D', '', 'g'), '')::integer,
               id::integer
           )
     where estado = 'Activo';

    for v_rack in
        select *
          from public.racks
         where estado = 'Activo'
    loop
        for v_estante in 1..least(
            greatest(coalesce(v_rack.niveles, 5), 1)
            * greatest(coalesce(v_rack.columnas, 2), 1),
            200
        ) loop
            v_codigo := 'B' || v_rack.bodega_id::text || '-' || v_rack.codigo_rack
                || '-E' || lpad(v_estante::text, 3, '0');

            insert into public.ubicaciones (
                bodega_id, rack_id, codigo_ubicacion, tipo,
                nivel, columna, descripcion, estado
            )
            select
                v_rack.bodega_id,
                v_rack.id,
                v_codigo,
                'Bloque',
                'E' || lpad(v_estante::text, 3, '0'),
                'M' || lpad(
                    (((v_estante - 1) / greatest(v_rack.niveles, 1)) + 1)::text,
                    2,
                    '0'
                ),
                'Estante ' || v_estante::text,
                'Activo'
            where not exists (
                select 1
                  from public.ubicaciones
                 where codigo_ubicacion = v_codigo
            );
        end loop;
    end loop;
end $$;

do $$
begin
    if exists (
        select 1
          from information_schema.columns
         where table_schema = 'public'
           and table_name = 'transacciones'
           and column_name = 'proyecto'
    ) then
        update public.transacciones t
           set proyecto_id = p.id
          from public.proyectos p
         where t.proyecto_id is null
           and (
               t.proyecto = p.nombre
               or t.proyecto = p.ot
           );
    end if;
end $$;

drop function if exists public.login_usuario_app(text, text);

create function public.login_usuario_app(
    p_usuario text,
    p_password text
)
returns table (
    id text,
    usuario text,
    nombre text,
    rol text
)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    v_user_col text;
    v_pass_col text;
    v_nombre_col text;
    v_rol_col text;
    v_estado_col text;
    v_id_col text;
    v_row jsonb;
    v_password_guardada text;
    v_estado text;
    v_match boolean;
begin
    select column_name
      into v_user_col
      from information_schema.columns
     where table_schema = 'public'
       and table_name = 'usuarios_app'
       and column_name in ('usuario', 'username', 'email', 'correo')
     order by array_position(
         array['usuario', 'username', 'email', 'correo'],
         column_name
     )
     limit 1;

    select column_name
      into v_pass_col
      from information_schema.columns
     where table_schema = 'public'
       and table_name = 'usuarios_app'
       and column_name in (
           'password_hash', 'clave_hash', 'hash_password',
           'password', 'clave', 'contrasena', 'contraseña'
       )
     order by array_position(
         array[
             'password_hash', 'clave_hash', 'hash_password',
             'password', 'clave', 'contrasena', 'contraseña'
         ],
         column_name
     )
     limit 1;

    if v_user_col is null or v_pass_col is null then
        return;
    end if;

    execute format(
        'select to_jsonb(u) from public.usuarios_app u where u.%I = $1 limit 1',
        v_user_col
    )
    into v_row
    using p_usuario;

    if v_row is null then
        return;
    end if;

    v_password_guardada := v_row ->> v_pass_col;
    v_match := v_password_guardada = p_password;

    if not v_match and v_password_guardada is not null then
        begin
            v_match := crypt(p_password, v_password_guardada) = v_password_guardada;
        exception when others then
            v_match := false;
        end;
    end if;

    if not v_match then
        return;
    end if;

    select column_name
      into v_estado_col
      from information_schema.columns
     where table_schema = 'public'
       and table_name = 'usuarios_app'
       and column_name in ('estado', 'activo', 'habilitado')
     order by array_position(array['estado', 'activo', 'habilitado'], column_name)
     limit 1;

    if v_estado_col is not null then
        v_estado := lower(coalesce(v_row ->> v_estado_col, ''));
        if v_estado not in ('activo', 'active', 'true', 't', '1', 'si', 'sí', 'habilitado') then
            return;
        end if;
    end if;

    select column_name
      into v_id_col
      from information_schema.columns
     where table_schema = 'public'
       and table_name = 'usuarios_app'
       and column_name in ('id', 'uuid', 'usuario_id')
     order by array_position(array['id', 'uuid', 'usuario_id'], column_name)
     limit 1;

    select column_name
      into v_nombre_col
      from information_schema.columns
     where table_schema = 'public'
       and table_name = 'usuarios_app'
       and column_name in ('nombre', 'nombre_completo', 'name')
     order by array_position(array['nombre', 'nombre_completo', 'name'], column_name)
     limit 1;

    select column_name
      into v_rol_col
      from information_schema.columns
     where table_schema = 'public'
       and table_name = 'usuarios_app'
       and column_name in ('rol', 'role', 'perfil')
     order by array_position(array['rol', 'role', 'perfil'], column_name)
     limit 1;

    id := coalesce(v_row ->> v_id_col, v_row ->> v_user_col);
    usuario := coalesce(v_row ->> v_user_col, p_usuario);
    nombre := coalesce(v_row ->> v_nombre_col, usuario);
    rol := coalesce(v_row ->> v_rol_col, 'Consulta');

    return next;
end;
$$;

revoke all on function public.login_usuario_app(text, text) from public;
grant execute on function public.login_usuario_app(text, text) to anon, authenticated;

create index if not exists idx_productos_estado on public.productos(estado);
create index if not exists idx_productos_codigo on public.productos(codigo_barras);
create index if not exists idx_productos_ubicacion on public.productos(ubicacion_id);
create index if not exists idx_transacciones_fecha on public.transacciones(fecha_hora);
create index if not exists idx_transacciones_proyecto on public.transacciones(proyecto_id);
create index if not exists idx_transacciones_producto on public.transacciones(producto_id);
create index if not exists idx_racks_bodega on public.racks(bodega_id);
create index if not exists idx_ubicaciones_rack on public.ubicaciones(rack_id);
create index if not exists idx_ubicaciones_codigo on public.ubicaciones(codigo_ubicacion);

grant select on all tables in schema public to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

notify pgrst, 'reload schema';
