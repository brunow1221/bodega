-- Ejecutar una vez en Supabase SQL Editor antes de distribuir la nueva version.
-- Requiere que ya exista la funcion login_usuario_app(p_usuario, p_password).

create extension if not exists pgcrypto;

alter table public.transacciones
    add column if not exists precio_unitario_movimiento numeric,
    add column if not exists producto_nombre_snapshot text,
    add column if not exists producto_codigo_snapshot text,
    add column if not exists ubicacion_snapshot text;

create table if not exists public.sesiones_app (
    token uuid primary key default gen_random_uuid(),
    usuario_app_id text,
    usuario text not null,
    nombre text not null,
    rol text not null,
    creado_en timestamptz not null default now(),
    expira_en timestamptz not null default (now() + interval '12 hours'),
    revocada boolean not null default false
);

alter table public.sesiones_app enable row level security;
revoke all on public.sesiones_app from anon, authenticated;

create table if not exists public.solicitudes_app (
    request_id uuid primary key,
    operacion text not null,
    respuesta jsonb,
    creado_en timestamptz not null default now()
);

alter table public.solicitudes_app enable row level security;
revoke all on public.solicitudes_app from anon, authenticated;

create or replace function public.iniciar_sesion_app(
    p_usuario text,
    p_password text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_usuario jsonb;
    v_token uuid;
begin
    select to_jsonb(resultado)
      into v_usuario
      from public.login_usuario_app(p_usuario, p_password) as resultado
      limit 1;

    if v_usuario is null then
        return null;
    end if;

    delete from public.sesiones_app
     where expira_en < now()
        or revocada = true;
    delete from public.solicitudes_app
     where creado_en < now() - interval '30 days';

    insert into public.sesiones_app (
        usuario_app_id,
        usuario,
        nombre,
        rol
    )
    values (
        v_usuario ->> 'id',
        coalesce(v_usuario ->> 'usuario', p_usuario),
        coalesce(v_usuario ->> 'nombre', p_usuario),
        coalesce(v_usuario ->> 'rol', 'Consulta')
    )
    returning token into v_token;

    return v_usuario || jsonb_build_object('session_token', v_token);
end;
$$;

create or replace function public.cerrar_sesion_app(p_token uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.sesiones_app
       set revocada = true
     where token = p_token;
    return found;
end;
$$;

create or replace function public.validar_sesion_app(
    p_token uuid,
    p_requiere_escritura boolean default false
)
returns public.sesiones_app
language plpgsql
security definer
set search_path = public
as $$
declare
    v_sesion public.sesiones_app%rowtype;
begin
    select *
      into v_sesion
      from public.sesiones_app
     where token = p_token
       and revocada = false
       and expira_en > now();

    if not found then
        raise exception 'Sesion invalida o expirada.';
    end if;

    if p_requiere_escritura
       and v_sesion.rol not in ('Administrador', 'Admin', 'Bodeguero') then
        raise exception 'El usuario no tiene permisos de escritura.';
    end if;

    return v_sesion;
end;
$$;

create or replace function public.app_mutar_registro(
    p_token uuid,
    p_request_id uuid,
    p_operacion text,
    p_datos jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_sesion public.sesiones_app%rowtype;
    v_id text;
    v_codigo text;
    v_padre record;
    v_sub text;
    v_creadas integer := 0;
    v_producto_id bigint;
    v_proyecto_id bigint;
    v_trabajador_id bigint;
    v_ubicacion_codigo text;
    v_respuesta jsonb;
    i integer;
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
    values (p_request_id, p_operacion)
    on conflict (request_id) do nothing;

    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    if p_operacion = 'crear_producto' then
        if (p_datos ->> 'stock')::integer < 0
           or (p_datos ->> 'stock_minimo')::integer < 0
           or (p_datos ->> 'precio_unitario')::numeric < 0 then
            raise exception 'Stock, stock minimo y precio no pueden ser negativos.';
        end if;

        insert into public.productos (
            codigo_barras, nombre, categoria, subcategoria, marca,
            "tamaño_dimensiones", talla, stock, stock_minimo,
            precio_unitario, ubicacion_id, estado, tipo_medicion,
            medida_largo, medida_ancho, unidad_medida, producto_origen_id,
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
            (p_datos ->> 'stock')::integer,
            (p_datos ->> 'stock_minimo')::integer,
            (p_datos ->> 'precio_unitario')::numeric,
            nullif(p_datos ->> 'ubicacion_id', '')::bigint,
            'Activo',
            coalesce(p_datos ->> 'tipo_medicion', 'No aplica'),
            nullif(p_datos ->> 'medida_largo', '')::numeric,
            nullif(p_datos ->> 'medida_ancho', '')::numeric,
            nullif(p_datos ->> 'unidad_medida', ''),
            nullif(p_datos ->> 'producto_origen_id', '')::bigint,
            coalesce((p_datos ->> 'es_retazo')::boolean, false),
            nullif(p_datos ->> 'porcentaje_valor_origen', '')::numeric,
            nullif(p_datos ->> 'observacion_retazo', '')
        )
        returning id into v_producto_id;
        v_id := v_producto_id::text;

        if (p_datos ->> 'stock')::integer > 0 then
            select id
              into v_proyecto_id
              from public.proyectos
             where nombre = 'Taller Interno'
               and estado = 'Activo'
             limit 1;

            if v_proyecto_id is not null then
                select codigo_ubicacion
                  into v_ubicacion_codigo
                  from public.ubicaciones
                 where id::text = p_datos ->> 'ubicacion_id';

                insert into public.transacciones (
                    producto_id, proyecto_id, trabajador_id, tipo_movimiento,
                    cantidad_movida, stock_anterior, stock_nuevo, comentario,
                    creado_por_usuario, precio_unitario_movimiento,
                    producto_nombre_snapshot, producto_codigo_snapshot,
                    ubicacion_snapshot
                )
                values (
                    v_producto_id,
                    v_proyecto_id,
                    null,
                    'Entrada / Reposición',
                    (p_datos ->> 'stock')::integer,
                    0,
                    (p_datos ->> 'stock')::integer,
                    'Stock inicial del producto',
                    v_sesion.nombre || ' (' || v_sesion.usuario || ')',
                    (p_datos ->> 'precio_unitario')::numeric,
                    p_datos ->> 'nombre',
                    p_datos ->> 'codigo_barras',
                    v_ubicacion_codigo
                );
            end if;
        end if;

    elsif p_operacion = 'crear_retazo' then
        if (p_datos ->> 'precio_unitario')::numeric < 0 then
            raise exception 'El precio del retazo no puede ser negativo.';
        end if;

        select id
          into v_proyecto_id
          from public.proyectos
         where nombre = p_datos ->> 'proyecto'
           and estado = 'Activo'
         limit 1;
        if not found then
            raise exception 'Proyecto inexistente o inactivo.';
        end if;

        if nullif(trim(coalesce(p_datos ->> 'rut_trabajador', '')), '') is not null then
            select id
              into v_trabajador_id
              from public.trabajadores
             where rut = trim(p_datos ->> 'rut_trabajador')
               and estado = 'Activo'
             limit 1;
            if not found then
                raise exception 'Trabajador inexistente o inactivo.';
            end if;
        end if;

        insert into public.productos (
            codigo_barras, nombre, categoria, subcategoria, marca,
            "tamaño_dimensiones", talla, stock, stock_minimo,
            precio_unitario, ubicacion_id, estado, tipo_medicion,
            medida_largo, medida_ancho, unidad_medida, producto_origen_id,
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
            1,
            0,
            (p_datos ->> 'precio_unitario')::numeric,
            nullif(p_datos ->> 'ubicacion_id', '')::bigint,
            'Activo',
            coalesce(p_datos ->> 'tipo_medicion', 'No aplica'),
            nullif(p_datos ->> 'medida_largo', '')::numeric,
            nullif(p_datos ->> 'medida_ancho', '')::numeric,
            nullif(p_datos ->> 'unidad_medida', ''),
            nullif(p_datos ->> 'producto_origen_id', '')::bigint,
            true,
            nullif(p_datos ->> 'porcentaje_valor_origen', '')::numeric,
            nullif(p_datos ->> 'observacion_retazo', '')
        )
        returning id into v_producto_id;

        select codigo_ubicacion
          into v_ubicacion_codigo
          from public.ubicaciones
         where id::text = p_datos ->> 'ubicacion_id';

        insert into public.transacciones (
            producto_id, proyecto_id, trabajador_id, tipo_movimiento,
            cantidad_movida, stock_anterior, stock_nuevo, comentario,
            creado_por_usuario, precio_unitario_movimiento,
            producto_nombre_snapshot, producto_codigo_snapshot, ubicacion_snapshot
        )
        values (
            v_producto_id,
            v_proyecto_id,
            v_trabajador_id,
            'Entrada / Reposición',
            1,
            0,
            1,
            'Entrada automática de retazo',
            v_sesion.nombre || ' (' || v_sesion.usuario || ')',
            (p_datos ->> 'precio_unitario')::numeric,
            p_datos ->> 'nombre',
            p_datos ->> 'codigo_barras',
            v_ubicacion_codigo
        );
        v_id := v_producto_id::text;

    elsif p_operacion = 'actualizar_producto' then
        if coalesce((p_datos ->> 'stock_minimo')::integer, 0) < 0
           or coalesce((p_datos ->> 'precio_unitario')::numeric, 0) < 0 then
            raise exception 'Stock minimo y precio no pueden ser negativos.';
        end if;

        update public.productos
           set nombre = coalesce(p_datos ->> 'nombre', nombre),
               categoria = coalesce(p_datos ->> 'categoria', categoria),
               subcategoria = coalesce(p_datos ->> 'subcategoria', subcategoria),
               marca = coalesce(p_datos ->> 'marca', marca),
               "tamaño_dimensiones" = coalesce(p_datos ->> 'tamaño_dimensiones', "tamaño_dimensiones"),
               talla = coalesce(p_datos ->> 'talla', talla),
               stock_minimo = coalesce((p_datos ->> 'stock_minimo')::integer, stock_minimo),
               precio_unitario = coalesce((p_datos ->> 'precio_unitario')::numeric, precio_unitario),
               ubicacion_id = case
                   when p_datos ? 'ubicacion_id'
                   then nullif(p_datos ->> 'ubicacion_id', '')::bigint
                   else ubicacion_id
               end,
               estado = coalesce(p_datos ->> 'estado', estado),
               tipo_medicion = coalesce(p_datos ->> 'tipo_medicion', tipo_medicion),
               medida_largo = case
                   when p_datos ? 'medida_largo'
                   then nullif(p_datos ->> 'medida_largo', '')::numeric
                   else medida_largo
               end,
               medida_ancho = case
                   when p_datos ? 'medida_ancho'
                   then nullif(p_datos ->> 'medida_ancho', '')::numeric
                   else medida_ancho
               end,
               unidad_medida = case
                   when p_datos ? 'unidad_medida'
                   then nullif(p_datos ->> 'unidad_medida', '')
                   else unidad_medida
               end
         where id::text = p_datos ->> 'id';
        if not found then
            raise exception 'Producto no encontrado.';
        end if;
        v_id := p_datos ->> 'id';

    elsif p_operacion = 'crear_proyecto' then
        insert into public.proyectos (
            nombre, ot, cliente, descripcion, fecha_inicio, fecha_fin, estado
        )
        values (
            p_datos ->> 'nombre',
            p_datos ->> 'ot',
            p_datos ->> 'cliente',
            p_datos ->> 'descripcion',
            nullif(p_datos ->> 'fecha_inicio', '')::date,
            nullif(p_datos ->> 'fecha_fin', '')::date,
            'Activo'
        )
        returning id::text into v_id;

    elsif p_operacion = 'actualizar_proyecto' then
        update public.proyectos
           set nombre = coalesce(p_datos ->> 'nombre', nombre),
               ot = coalesce(p_datos ->> 'ot', ot),
               cliente = coalesce(p_datos ->> 'cliente', cliente),
               descripcion = coalesce(p_datos ->> 'descripcion', descripcion),
               fecha_inicio = case
                   when p_datos ? 'fecha_inicio'
                   then nullif(p_datos ->> 'fecha_inicio', '')::date
                   else fecha_inicio
               end,
               fecha_fin = case
                   when p_datos ? 'fecha_fin'
                   then nullif(p_datos ->> 'fecha_fin', '')::date
                   else fecha_fin
               end,
               estado = coalesce(p_datos ->> 'estado', estado)
         where id::text = p_datos ->> 'id';
        if not found then
            raise exception 'Proyecto no encontrado.';
        end if;
        v_id := p_datos ->> 'id';

    elsif p_operacion = 'crear_trabajador' then
        insert into public.trabajadores (rut, nombre, cargo, estado)
        values (
            p_datos ->> 'rut',
            p_datos ->> 'nombre',
            p_datos ->> 'cargo',
            'Activo'
        )
        returning id::text into v_id;

    elsif p_operacion = 'crear_rack' then
        insert into public.racks (
            bodega_id, codigo_rack, nombre, descripcion, niveles, columnas, estado
        )
        values (
            (p_datos ->> 'bodega_id')::bigint,
            p_datos ->> 'codigo_rack',
            p_datos ->> 'nombre',
            p_datos ->> 'descripcion',
            (p_datos ->> 'niveles')::integer,
            (p_datos ->> 'columnas')::integer,
            'Activo'
        )
        returning id::text into v_id;

    elsif p_operacion = 'crear_ubicacion' then
        insert into public.ubicaciones (
            bodega_id, rack_id, codigo_ubicacion, tipo, nivel, columna,
            subdivision, ubicacion_padre_id, descripcion, estado
        )
        values (
            (p_datos ->> 'bodega_id')::bigint,
            (p_datos ->> 'rack_id')::bigint,
            p_datos ->> 'codigo_ubicacion',
            p_datos ->> 'tipo',
            p_datos ->> 'nivel',
            p_datos ->> 'columna',
            nullif(p_datos ->> 'subdivision', ''),
            nullif(p_datos ->> 'ubicacion_padre_id', '')::bigint,
            p_datos ->> 'descripcion',
            'Activo'
        )
        returning id::text into v_id;

    elsif p_operacion = 'crear_subdivisiones' then
        if coalesce((p_datos ->> 'cantidad')::integer, 4) not between 1 and 20 then
            raise exception 'La cantidad de subdivisiones debe estar entre 1 y 20.';
        end if;

        select *
          into v_padre
          from public.ubicaciones
         where id::text = p_datos ->> 'ubicacion_padre_id'
           and tipo = 'Bloque'
         for update;

        if not found then
            raise exception 'No se encontro una ubicacion padre valida.';
        end if;

        for i in 1..coalesce((p_datos ->> 'cantidad')::integer, 4) loop
            v_sub := 'S' || lpad(i::text, 2, '0');
            v_codigo := v_padre.codigo_ubicacion || '-' || v_sub;
            insert into public.ubicaciones (
                bodega_id, rack_id, codigo_ubicacion, tipo, nivel, columna,
                subdivision, ubicacion_padre_id, descripcion, estado
            )
            select
                v_padre.bodega_id, v_padre.rack_id, v_codigo, 'Subdivision',
                v_padre.nivel, v_padre.columna, v_sub, v_padre.id,
                v_sub || ' de ' || v_padre.codigo_ubicacion, 'Activo'
            where not exists (
                select 1
                  from public.ubicaciones
                 where codigo_ubicacion = v_codigo
            );
            if found then
                v_creadas := v_creadas + 1;
            end if;
        end loop;
        v_id := p_datos ->> 'ubicacion_padre_id';

    elsif p_operacion = 'registrar_auditoria' then
        v_id := null;

    else
        raise exception 'Operacion no permitida: %', p_operacion;
    end if;

    insert into public.auditoria (
        modulo, accion, detalle, usuario_app, datos
    )
    values (
        coalesce(p_datos ->> '_modulo', 'Sistema'),
        coalesce(p_datos ->> '_accion', p_operacion),
        coalesce(p_datos ->> '_detalle', ''),
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        p_datos - '_modulo' - '_accion' - '_detalle'
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'id', v_id,
        'creadas', v_creadas
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;
    return v_respuesta;
end;
$$;

create or replace function public.registrar_movimiento_app(
    p_token uuid,
    p_request_id uuid,
    p_rut_trabajador text,
    p_codigo_producto text,
    p_tipo_movimiento text,
    p_producto_id text,
    p_cantidad integer,
    p_proyecto text,
    p_comentario text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_sesion public.sesiones_app%rowtype;
    v_producto record;
    v_proyecto record;
    v_trabajador record;
    v_trabajador_id bigint;
    v_ubicacion_codigo text;
    v_stock_anterior integer;
    v_stock_nuevo integer;
    v_pendiente integer;
    v_es_resta boolean;
    v_es_suma boolean;
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
    values (p_request_id, 'registrar_movimiento')
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

    select *
      into v_producto
      from public.productos
     where id::text = p_producto_id
       and codigo_barras = p_codigo_producto
       and estado = 'Activo'
     for update;

    if not found then
        raise exception 'Producto inexistente o inactivo.';
    end if;

    select *
      into v_proyecto
      from public.proyectos
     where nombre = p_proyecto
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
        v_trabajador_id := v_trabajador.id;
    end if;

    v_es_resta := p_tipo_movimiento in (
        'Prestamo de Herramienta', 'Préstamo de Herramienta',
        'Entrega / Consumo', 'Baja por Dano / Merma',
        'Baja por Daño / Merma', 'Envio a Calibracion / Reparacion',
        'Envío a Calibración / Reparación', 'Corte / Transformacion',
        'Corte / Transformación'
    );
    v_es_suma := p_tipo_movimiento in (
        'Devolucion de Herramienta', 'Devolución de Herramienta',
        'Retorno de Reparacion', 'Retorno de Reparación',
        'Entrada / Reposicion', 'Entrada / Reposición'
    );

    if not v_es_resta and not v_es_suma then
        raise exception 'Tipo de movimiento no permitido.';
    end if;

    if p_tipo_movimiento in ('Devolucion de Herramienta', 'Devolución de Herramienta') then
        select coalesce(sum(
            case
                when tipo_movimiento in ('Prestamo de Herramienta', 'Préstamo de Herramienta')
                    then cantidad_movida
                when tipo_movimiento in ('Devolucion de Herramienta', 'Devolución de Herramienta')
                    then -cantidad_movida
                else 0
            end
        ), 0)::integer
          into v_pendiente
         from public.transacciones
         where producto_id = v_producto.id
           and trabajador_id is not distinct from v_trabajador_id;

        if v_pendiente < p_cantidad then
            raise exception 'La devolucion supera la cantidad prestada pendiente (%).', v_pendiente;
        end if;
    end if;

    if p_tipo_movimiento in ('Retorno de Reparacion', 'Retorno de Reparación') then
        select coalesce(sum(
            case
                when tipo_movimiento in (
                    'Envio a Calibracion / Reparacion',
                    'Envío a Calibración / Reparación'
                ) then cantidad_movida
                when tipo_movimiento in ('Retorno de Reparacion', 'Retorno de Reparación')
                    then -cantidad_movida
                else 0
            end
        ), 0)::integer
          into v_pendiente
          from public.transacciones
         where producto_id = v_producto.id;

        if v_pendiente < p_cantidad then
            raise exception 'El retorno supera la cantidad enviada a reparacion (%).', v_pendiente;
        end if;
    end if;

    v_stock_anterior := coalesce(v_producto.stock, 0);
    if v_es_resta then
        if v_stock_anterior < p_cantidad then
            raise exception 'Stock insuficiente. Disponible: %.', v_stock_anterior;
        end if;
        v_stock_nuevo := v_stock_anterior - p_cantidad;
    else
        v_stock_nuevo := v_stock_anterior + p_cantidad;
    end if;

    select codigo_ubicacion
      into v_ubicacion_codigo
      from public.ubicaciones
     where id = v_producto.ubicacion_id;

    update public.productos
       set stock = v_stock_nuevo,
           estado = case
               when p_tipo_movimiento in ('Baja por Dano / Merma', 'Baja por Daño / Merma')
                    and v_stock_nuevo <= 0 then 'Inactivo'
               else estado
           end
     where id = v_producto.id;

    insert into public.transacciones (
        producto_id, proyecto_id, trabajador_id, tipo_movimiento,
        cantidad_movida, stock_anterior, stock_nuevo, comentario,
        creado_por_usuario, precio_unitario_movimiento,
        producto_nombre_snapshot, producto_codigo_snapshot, ubicacion_snapshot
    )
    values (
        v_producto.id,
        v_proyecto.id,
        v_trabajador_id,
        p_tipo_movimiento,
        p_cantidad,
        v_stock_anterior,
        v_stock_nuevo,
        p_comentario,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        coalesce(v_producto.precio_unitario, 0),
        v_producto.nombre,
        v_producto.codigo_barras,
        v_ubicacion_codigo
    );

    insert into public.auditoria (
        modulo, accion, detalle, usuario_app, datos
    )
    values (
        'Movimientos',
        'Registrar movimiento',
        p_tipo_movimiento || ' | ' || v_producto.nombre || ' | Cantidad: ' || p_cantidad,
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        jsonb_build_object(
            'producto_id', v_producto.id,
            'proyecto_id', v_proyecto.id,
            'trabajador_id', v_trabajador_id,
            'stock_anterior', v_stock_anterior,
            'stock_nuevo', v_stock_nuevo,
            'cantidad', p_cantidad
        )
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'stock_anterior', v_stock_anterior,
        'stock_nuevo', v_stock_nuevo
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;
    return v_respuesta;
end;
$$;

revoke all on function public.validar_sesion_app(uuid, boolean) from public, anon, authenticated;
revoke all on function public.iniciar_sesion_app(text, text) from public;
revoke all on function public.cerrar_sesion_app(uuid) from public;
revoke all on function public.app_mutar_registro(uuid, uuid, text, jsonb) from public;
revoke all on function public.registrar_movimiento_app(
    uuid, uuid, text, text, text, text, integer, text, text
) from public;

grant execute on function public.iniciar_sesion_app(text, text) to anon, authenticated;
grant execute on function public.cerrar_sesion_app(uuid) to anon, authenticated;
grant execute on function public.app_mutar_registro(uuid, uuid, text, jsonb) to anon, authenticated;
grant execute on function public.registrar_movimiento_app(
    uuid, uuid, text, text, text, text, integer, text, text
) to anon, authenticated;

-- Las lecturas siguen disponibles segun las politicas existentes.
-- Las escrituras operativas deben pasar por las funciones anteriores.
revoke insert, update, delete on public.productos from anon, authenticated;
revoke insert, update, delete on public.proyectos from anon, authenticated;
revoke insert, update, delete on public.trabajadores from anon, authenticated;
revoke insert, update, delete on public.transacciones from anon, authenticated;
revoke insert, update, delete on public.racks from anon, authenticated;
revoke insert, update, delete on public.ubicaciones from anon, authenticated;
revoke insert, update, delete on public.auditoria from anon, authenticated;
