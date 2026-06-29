-- Requiere haber ejecutado 001_integridad_seguridad.sql.

alter table public.racks
    add column if not exists ancho_cm numeric,
    add column if not exists alto_cm numeric,
    add column if not exists profundidad_cm numeric,
    add column if not exists capacidad_kg numeric,
    add column if not exists posicion_orden integer;

update public.racks
   set ancho_cm = coalesce(ancho_cm, 200),
       niveles = coalesce(niveles, 3),
       columnas = coalesce(columnas, 3),
       posicion_orden = coalesce(
           posicion_orden,
           nullif(regexp_replace(codigo_rack, '\D', '', 'g'), '')::integer,
           id::integer
       );

create or replace function public.gestionar_rack_app(
    p_token uuid,
    p_request_id uuid,
    p_accion text,
    p_datos jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_sesion public.sesiones_app%rowtype;
    v_rack public.racks%rowtype;
    v_request public.solicitudes_app%rowtype;
    v_respuesta jsonb;
    v_rack_id bigint;
    v_bodega_id bigint;
    v_codigo text;
    v_codigo_anterior text;
    v_nombre text;
    v_descripcion text;
    v_niveles integer;
    v_columnas integer;
    v_ancho numeric;
    v_alto numeric;
    v_profundidad numeric;
    v_capacidad numeric;
    v_posicion integer;
    v_estado text;
    v_codigo_ubicacion text;
    v_ubicaciones_retirar bigint[];
    v_productos_afectados integer;
    fila integer;
    columna integer;
begin
    v_sesion := public.validar_sesion_app(p_token, true);

    select *
      into v_request
      from public.solicitudes_app
     where request_id = p_request_id;
    if found then
        return v_request.respuesta;
    end if;

    insert into public.solicitudes_app (request_id, operacion)
    values (p_request_id, 'rack_' || p_accion)
    on conflict (request_id) do nothing;

    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    if p_accion not in ('crear', 'actualizar', 'retirar', 'reactivar') then
        raise exception 'Accion de rack no permitida.';
    end if;

    if p_accion = 'crear' then
        v_bodega_id := (p_datos ->> 'bodega_id')::bigint;
        v_codigo := upper(trim(p_datos ->> 'codigo_rack'));
        v_nombre := trim(coalesce(p_datos ->> 'nombre', v_codigo));
        v_descripcion := trim(coalesce(p_datos ->> 'descripcion', ''));
        v_niveles := (p_datos ->> 'niveles')::integer;
        v_columnas := (p_datos ->> 'columnas')::integer;
        v_ancho := nullif(p_datos ->> 'ancho_cm', '')::numeric;
        v_alto := nullif(p_datos ->> 'alto_cm', '')::numeric;
        v_profundidad := nullif(p_datos ->> 'profundidad_cm', '')::numeric;
        v_capacidad := nullif(p_datos ->> 'capacidad_kg', '')::numeric;
        v_posicion := nullif(p_datos ->> 'posicion_orden', '')::integer;

        if v_codigo !~ '^[A-Z0-9_-]{1,12}$' then
            raise exception 'El codigo del rack solo puede contener letras, numeros, guion y guion bajo.';
        end if;
        if v_niveles not between 1 and 8 or v_columnas not between 1 and 8 then
            raise exception 'Niveles y columnas deben estar entre 1 y 8.';
        end if;
        if coalesce(v_ancho, 1) <= 0
           or coalesce(v_alto, 1) <= 0
           or coalesce(v_profundidad, 1) <= 0
           or coalesce(v_capacidad, 1) <= 0 then
            raise exception 'Las dimensiones y la capacidad deben ser mayores a cero.';
        end if;
        if exists (
            select 1
              from public.racks
             where bodega_id = v_bodega_id
               and upper(codigo_rack) = v_codigo
        ) then
            raise exception 'Ya existe un rack con el codigo % en esta bodega.', v_codigo;
        end if;

        insert into public.racks (
            bodega_id, codigo_rack, nombre, descripcion, niveles, columnas,
            ancho_cm, alto_cm, profundidad_cm, capacidad_kg,
            posicion_orden, estado
        )
        values (
            v_bodega_id, v_codigo, v_nombre, v_descripcion, v_niveles,
            v_columnas, v_ancho, v_alto, v_profundidad, v_capacidad,
            v_posicion, 'Activo'
        )
        returning id into v_rack_id;

    else
        select *
          into v_rack
          from public.racks
         where id = (p_datos ->> 'id')::bigint
         for update;
        if not found then
            raise exception 'Rack no encontrado.';
        end if;

        v_rack_id := v_rack.id;
        v_bodega_id := v_rack.bodega_id;
        v_codigo_anterior := v_rack.codigo_rack;
        v_codigo := upper(trim(coalesce(p_datos ->> 'codigo_rack', v_rack.codigo_rack)));
        v_nombre := trim(coalesce(p_datos ->> 'nombre', v_rack.nombre));
        v_descripcion := trim(coalesce(p_datos ->> 'descripcion', v_rack.descripcion, ''));
        v_niveles := coalesce((p_datos ->> 'niveles')::integer, v_rack.niveles, 3);
        v_columnas := coalesce((p_datos ->> 'columnas')::integer, v_rack.columnas, 3);
        v_ancho := case when p_datos ? 'ancho_cm'
            then nullif(p_datos ->> 'ancho_cm', '')::numeric else v_rack.ancho_cm end;
        v_alto := case when p_datos ? 'alto_cm'
            then nullif(p_datos ->> 'alto_cm', '')::numeric else v_rack.alto_cm end;
        v_profundidad := case when p_datos ? 'profundidad_cm'
            then nullif(p_datos ->> 'profundidad_cm', '')::numeric else v_rack.profundidad_cm end;
        v_capacidad := case when p_datos ? 'capacidad_kg'
            then nullif(p_datos ->> 'capacidad_kg', '')::numeric else v_rack.capacidad_kg end;
        v_posicion := case when p_datos ? 'posicion_orden'
            then nullif(p_datos ->> 'posicion_orden', '')::integer else v_rack.posicion_orden end;

        if p_accion = 'retirar' then
            select count(*)
              into v_productos_afectados
              from public.productos p
              join public.ubicaciones u on u.id = p.ubicacion_id
             where u.rack_id = v_rack_id;

            if v_productos_afectados > 0 then
                raise exception 'No se puede retirar el rack: hay % productos asignados.', v_productos_afectados;
            end if;

            update public.ubicaciones
               set estado = 'Inactivo'
             where rack_id = v_rack_id;
            update public.racks
               set estado = 'Inactivo'
             where id = v_rack_id;
            v_estado := 'Inactivo';

        elsif p_accion = 'reactivar' then
            update public.racks
               set estado = 'Activo'
             where id = v_rack_id;
            v_estado := 'Activo';

        else
            if v_codigo !~ '^[A-Z0-9_-]{1,12}$' then
                raise exception 'El codigo del rack no es valido.';
            end if;
            if v_niveles not between 1 and 8 or v_columnas not between 1 and 8 then
                raise exception 'Niveles y columnas deben estar entre 1 y 8.';
            end if;
            if coalesce(v_ancho, 1) <= 0
               or coalesce(v_alto, 1) <= 0
               or coalesce(v_profundidad, 1) <= 0
               or coalesce(v_capacidad, 1) <= 0 then
                raise exception 'Las dimensiones y la capacidad deben ser mayores a cero.';
            end if;
            if exists (
                select 1
                  from public.racks
                 where bodega_id = v_bodega_id
                   and upper(codigo_rack) = v_codigo
                   and id <> v_rack_id
            ) then
                raise exception 'Ya existe otro rack con el codigo %.', v_codigo;
            end if;

            select array_agg(id)
              into v_ubicaciones_retirar
              from public.ubicaciones
             where rack_id = v_rack_id
               and tipo = 'Bloque'
               and (
                   substring(nivel from 2)::integer > v_niveles
                   or substring(columna from 2)::integer > v_columnas
               );

            if v_ubicaciones_retirar is not null then
                select count(*)
                  into v_productos_afectados
                  from public.productos p
                  join public.ubicaciones u on u.id = p.ubicacion_id
                 where u.id = any(v_ubicaciones_retirar)
                    or u.ubicacion_padre_id = any(v_ubicaciones_retirar);

                if v_productos_afectados > 0 then
                    raise exception 'No se puede reducir el rack: % productos quedarian fuera de la matriz.', v_productos_afectados;
                end if;

                update public.ubicaciones
                   set estado = 'Inactivo'
                 where id = any(v_ubicaciones_retirar)
                    or ubicacion_padre_id = any(v_ubicaciones_retirar);
            end if;

            update public.racks
               set codigo_rack = v_codigo,
                   nombre = v_nombre,
                   descripcion = v_descripcion,
                   niveles = v_niveles,
                   columnas = v_columnas,
                   ancho_cm = v_ancho,
                   alto_cm = v_alto,
                   profundidad_cm = v_profundidad,
                   capacidad_kg = v_capacidad,
                   posicion_orden = v_posicion
             where id = v_rack_id;

            if v_codigo <> v_codigo_anterior then
                update public.ubicaciones
                   set codigo_ubicacion = replace(
                           codigo_ubicacion,
                           '-' || v_codigo_anterior,
                           '-' || v_codigo
                       ),
                       descripcion = replace(
                           coalesce(descripcion, ''),
                           v_codigo_anterior,
                           v_codigo
                       )
                 where rack_id = v_rack_id;
            end if;
            v_estado := v_rack.estado;
        end if;
    end if;

    if p_accion in ('crear', 'actualizar', 'reactivar') then
        for fila in 1..v_niveles loop
            for columna in 1..v_columnas loop
                v_codigo_ubicacion :=
                    'B' || v_bodega_id || '-' || v_codigo
                    || '-N' || lpad(fila::text, 2, '0')
                    || '-C' || lpad(columna::text, 2, '0');

                update public.ubicaciones
                   set codigo_ubicacion = v_codigo_ubicacion,
                       nivel = 'N' || lpad(fila::text, 2, '0'),
                       columna = 'C' || lpad(columna::text, 2, '0'),
                       estado = 'Activo'
                 where rack_id = v_rack_id
                   and tipo = 'Bloque'
                   and nivel = 'N' || lpad(fila::text, 2, '0')
                   and columna = 'C' || lpad(columna::text, 2, '0');

                if not found then
                    insert into public.ubicaciones (
                        bodega_id, rack_id, codigo_ubicacion, tipo,
                        nivel, columna, subdivision, ubicacion_padre_id,
                        descripcion, estado
                    )
                    values (
                        v_bodega_id, v_rack_id, v_codigo_ubicacion, 'Bloque',
                        'N' || lpad(fila::text, 2, '0'),
                        'C' || lpad(columna::text, 2, '0'),
                        null, null,
                        v_codigo || ' N' || lpad(fila::text, 2, '0')
                            || ' C' || lpad(columna::text, 2, '0'),
                        'Activo'
                    );
                end if;
            end loop;
        end loop;

        update public.racks
           set estado = 'Activo'
         where id = v_rack_id;
        update public.ubicaciones sub
           set estado = 'Activo'
         where sub.rack_id = v_rack_id
           and sub.tipo = 'Subdivision'
           and exists (
               select 1
                 from public.ubicaciones padre
                where padre.id = sub.ubicacion_padre_id
                  and padre.estado = 'Activo'
           );
        v_estado := 'Activo';
    end if;

    insert into public.auditoria (
        modulo, accion, detalle, usuario_app, datos
    )
    values (
        'Racks',
        initcap(p_accion) || ' rack',
        p_accion || ' rack ' || coalesce(v_codigo, v_rack.codigo_rack),
        v_sesion.nombre || ' (' || v_sesion.usuario || ')',
        p_datos
    );

    v_respuesta := jsonb_build_object(
        'ok', true,
        'id', v_rack_id,
        'estado', v_estado
    );
    update public.solicitudes_app
       set respuesta = v_respuesta
     where request_id = p_request_id;

    return v_respuesta;
end;
$$;

revoke all on function public.gestionar_rack_app(
    uuid, uuid, text, jsonb
) from public;
grant execute on function public.gestionar_rack_app(
    uuid, uuid, text, jsonb
) to anon, authenticated;
