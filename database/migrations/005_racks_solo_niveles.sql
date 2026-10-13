-- Convierte la bodega a dos sectores (A y B).
-- Cada sector contiene modulos fisicos ordenados de derecha a izquierda.
-- Los estantes se numeran de abajo hacia arriba: el modulo derecho comienza
-- en 1 y el siguiente modulo a la izquierda continua la numeracion.
-- Configuracion inicial: 2 modulos por sector y 5 estantes por modulo.
-- Requiere haber ejecutado las migraciones 000 a 004.

begin;

alter table public.racks
    alter column niveles set default 5,
    alter column columnas set default 2;

do $$
declare
    v_bodega record;
    v_rack record;
    v_ubicacion record;
    v_total_racks integer;
    v_division integer;
    v_indice integer;
    v_indice_grupo integer;
    v_cantidad_grupo integer;
    v_modulo integer;
    v_nivel_local integer;
    v_numero_estante integer;
    v_modulos_a integer;
    v_modulos_b integer;
    v_sector_id bigint;
    v_sector_a_id bigint;
    v_sector_b_id bigint;
    v_ubicacion_destino bigint;
    v_i integer;
    v_ya_migrado boolean;
begin
    select exists (
        select 1
          from public.config_app
         where clave = 'modo_racks'
           and valor = 'sectores_estantes_v1'
    ) into v_ya_migrado;

    if v_ya_migrado then
        return;
    end if;

    for v_bodega in
        select * from public.bodegas order by id
    loop
        select count(*)::integer
          into v_total_racks
          from public.racks
         where bodega_id = v_bodega.id
           and estado = 'Activo';

        v_division := greatest(1, (v_total_racks + 1) / 2);
        v_modulos_a := greatest(2, v_division);
        v_modulos_b := greatest(2, v_total_racks - v_division);

        insert into public.racks (
            bodega_id, codigo_rack, nombre, descripcion,
            niveles, columnas, posicion_orden, estado
        ) values (
            v_bodega.id,
            '__SECTOR_A_' || v_bodega.id::text,
            'Sector A',
            'Sector A: numeracion desde la derecha, de abajo hacia arriba',
            5, v_modulos_a, 1, 'Activo'
        ) returning id into v_sector_a_id;

        insert into public.racks (
            bodega_id, codigo_rack, nombre, descripcion,
            niveles, columnas, posicion_orden, estado
        ) values (
            v_bodega.id,
            '__SECTOR_B_' || v_bodega.id::text,
            'Sector B',
            'Sector B: numeracion desde la derecha, de abajo hacia arriba',
            5, v_modulos_b, 2, 'Activo'
        ) returning id into v_sector_b_id;

        -- Codigos transitorios evitan colisiones con ubicaciones antiguas.
        for v_i in 1..(v_modulos_a * 5) loop
            insert into public.ubicaciones (
                bodega_id, rack_id, codigo_ubicacion, tipo,
                nivel, columna, subdivision, ubicacion_padre_id,
                descripcion, estado
            ) values (
                v_bodega.id, v_sector_a_id,
                'NEW-' || v_sector_a_id::text || '-' || v_i::text,
                'Bloque',
                'E' || lpad(v_i::text, 3, '0'),
                'M' || lpad((((v_i - 1) / 5) + 1)::text, 2, '0'),
                null, null,
                'Sector A - Estante ' || v_i::text,
                'Activo'
            );
        end loop;

        for v_i in 1..(v_modulos_b * 5) loop
            insert into public.ubicaciones (
                bodega_id, rack_id, codigo_ubicacion, tipo,
                nivel, columna, subdivision, ubicacion_padre_id,
                descripcion, estado
            ) values (
                v_bodega.id, v_sector_b_id,
                'NEW-' || v_sector_b_id::text || '-' || v_i::text,
                'Bloque',
                'E' || lpad(v_i::text, 3, '0'),
                'M' || lpad((((v_i - 1) / 5) + 1)::text, 2, '0'),
                null, null,
                'Sector B - Estante ' || v_i::text,
                'Activo'
            );
        end loop;

        v_indice := 0;
        for v_rack in
            select r.*
              from public.racks r
             where r.bodega_id = v_bodega.id
               and r.estado = 'Activo'
               and r.id not in (v_sector_a_id, v_sector_b_id)
             order by r.posicion_orden nulls last, r.id
        loop
            v_indice := v_indice + 1;

            if v_indice <= v_division then
                v_sector_id := v_sector_a_id;
                v_indice_grupo := v_indice;
                v_cantidad_grupo := v_division;
            else
                v_sector_id := v_sector_b_id;
                v_indice_grupo := v_indice - v_division;
                v_cantidad_grupo := greatest(1, v_total_racks - v_division);
            end if;

            -- El rack con mayor posicion del grupo representa el modulo
            -- derecho y recibe primero los estantes 1 a 5.
            v_modulo := v_cantidad_grupo - v_indice_grupo + 1;

            for v_ubicacion in
                select u.*
                  from public.ubicaciones u
                 where u.rack_id = v_rack.id
                   and u.estado = 'Activo'
                   and u.tipo in ('Bloque', 'Subdivision')
                 order by u.id
            loop
                v_nivel_local := nullif(
                    regexp_replace(coalesce(v_ubicacion.nivel, ''), '\D', '', 'g'),
                    ''
                )::integer;
                -- Una base proveniente de una version intermedia puede traer
                -- niveles globales E006, E007, etc. En ese caso se conserva
                -- el numero dentro del modulo en lugar de colapsarlo en 5.
                v_nivel_local := coalesce(v_nivel_local, 1);
                v_nivel_local := ((greatest(v_nivel_local, 1) - 1) % 5) + 1;
                v_numero_estante := (v_modulo - 1) * 5 + v_nivel_local;

                select id into v_ubicacion_destino
                  from public.ubicaciones
                 where rack_id = v_sector_id
                   and nivel = 'E' || lpad(v_numero_estante::text, 3, '0')
                 limit 1;

                update public.productos
                   set ubicacion_id = v_ubicacion_destino
                 where ubicacion_id = v_ubicacion.id;
            end loop;
        end loop;

        -- Las estructuras previas quedan disponibles solo como trazabilidad.
        update public.ubicaciones u
           set estado = 'Inactivo',
               codigo_ubicacion = 'LEGACY-' || u.id::text
         where u.rack_id in (
             select r.id
               from public.racks r
              where r.bodega_id = v_bodega.id
                and r.id not in (v_sector_a_id, v_sector_b_id)
         );

        update public.racks
           set codigo_rack = 'LEGACY-' || id::text,
               estado = 'Inactivo'
         where bodega_id = v_bodega.id
           and id not in (v_sector_a_id, v_sector_b_id);

        update public.racks
           set codigo_rack = 'A', nombre = 'Sector A'
         where id = v_sector_a_id;
        update public.racks
           set codigo_rack = 'B', nombre = 'Sector B'
         where id = v_sector_b_id;

        update public.ubicaciones
           set codigo_ubicacion =
                   'B' || v_bodega.id::text || '-A-' || nivel,
               descripcion = 'Sector A - Estante '
                   || nullif(regexp_replace(nivel, '\D', '', 'g'), '')::integer
         where rack_id = v_sector_a_id;

        update public.ubicaciones
           set codigo_ubicacion =
                   'B' || v_bodega.id::text || '-B-' || nivel,
               descripcion = 'Sector B - Estante '
                   || nullif(regexp_replace(nivel, '\D', '', 'g'), '')::integer
         where rack_id = v_sector_b_id;
    end loop;
end;
$$;

insert into public.config_app (clave, valor, actualizado_en)
values ('modo_racks', 'sectores_estantes_v1', now())
on conflict (clave) do update
set valor = excluded.valor,
    actualizado_en = excluded.actualizado_en;

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
    v_respuesta jsonb;
    v_rack_id bigint;
    v_bodega_id bigint;
    v_codigo text;
    v_nombre text;
    v_descripcion text;
    v_estantes_modulo integer;
    v_modulos integer;
    v_total_estantes integer;
    v_ancho numeric;
    v_alto numeric;
    v_profundidad numeric;
    v_capacidad numeric;
    v_posicion integer;
    v_estado text;
    v_ubicaciones_retirar bigint[];
    v_productos_afectados integer;
    v_i integer;
begin
    v_sesion := public.validar_sesion_app(p_token, true);

    select respuesta into v_respuesta
      from public.solicitudes_app
     where request_id = p_request_id;
    if found then
        return v_respuesta;
    end if;

    insert into public.solicitudes_app (request_id, operacion)
    values (p_request_id, 'sector_' || p_accion)
    on conflict (request_id) do nothing;

    if not found then
        select respuesta into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    if p_accion not in ('crear', 'actualizar', 'retirar', 'reactivar') then
        raise exception 'Accion de sector no permitida.';
    end if;

    if p_accion = 'crear' then
        v_bodega_id := (p_datos ->> 'bodega_id')::bigint;
        v_codigo := upper(trim(p_datos ->> 'codigo_rack'));
        v_nombre := trim(coalesce(p_datos ->> 'nombre', 'Sector ' || v_codigo));
        v_descripcion := trim(coalesce(p_datos ->> 'descripcion', ''));
        v_estantes_modulo := coalesce(
            (p_datos ->> 'niveles')::integer,
            5
        );
        v_modulos := coalesce(
            (p_datos ->> 'columnas')::integer,
            2
        );
        v_ancho := nullif(p_datos ->> 'ancho_cm', '')::numeric;
        v_alto := nullif(p_datos ->> 'alto_cm', '')::numeric;
        v_profundidad := nullif(p_datos ->> 'profundidad_cm', '')::numeric;
        v_capacidad := nullif(p_datos ->> 'capacidad_kg', '')::numeric;
        v_posicion := case when v_codigo = 'A' then 1 else 2 end;

        if v_codigo not in ('A', 'B') then
            raise exception 'El sector debe ser A o B.';
        end if;
        if exists (
            select 1 from public.racks
             where bodega_id = v_bodega_id
               and codigo_rack = v_codigo
               and estado = 'Activo'
        ) then
            raise exception 'El sector % ya existe.', v_codigo;
        end if;

        insert into public.racks (
            bodega_id, codigo_rack, nombre, descripcion,
            niveles, columnas, ancho_cm, alto_cm, profundidad_cm,
            capacidad_kg, posicion_orden, estado
        ) values (
            v_bodega_id, v_codigo, v_nombre, v_descripcion,
            v_estantes_modulo, v_modulos, v_ancho, v_alto, v_profundidad,
            v_capacidad, v_posicion, 'Activo'
        ) returning id into v_rack_id;
        v_estado := 'Activo';
    else
        select * into v_rack
          from public.racks
         where id = (p_datos ->> 'id')::bigint
           and codigo_rack in ('A', 'B')
         for update;
        if not found then
            raise exception 'Sector no encontrado.';
        end if;

        v_rack_id := v_rack.id;
        v_bodega_id := v_rack.bodega_id;
        v_codigo := v_rack.codigo_rack;
        v_nombre := trim(coalesce(p_datos ->> 'nombre', v_rack.nombre));
        v_descripcion := trim(coalesce(p_datos ->> 'descripcion', v_rack.descripcion, ''));
        v_estantes_modulo := coalesce(
            (p_datos ->> 'niveles')::integer,
            v_rack.niveles,
            5
        );
        v_modulos := coalesce(
            (p_datos ->> 'columnas')::integer,
            v_rack.columnas,
            2
        );
        v_ancho := case when p_datos ? 'ancho_cm'
            then nullif(p_datos ->> 'ancho_cm', '')::numeric else v_rack.ancho_cm end;
        v_alto := case when p_datos ? 'alto_cm'
            then nullif(p_datos ->> 'alto_cm', '')::numeric else v_rack.alto_cm end;
        v_profundidad := case when p_datos ? 'profundidad_cm'
            then nullif(p_datos ->> 'profundidad_cm', '')::numeric else v_rack.profundidad_cm end;
        v_capacidad := case when p_datos ? 'capacidad_kg'
            then nullif(p_datos ->> 'capacidad_kg', '')::numeric else v_rack.capacidad_kg end;
        v_posicion := case when v_codigo = 'A' then 1 else 2 end;

        if p_accion = 'retirar' then
            select count(*) into v_productos_afectados
              from public.productos p
              join public.ubicaciones u on u.id = p.ubicacion_id
             where u.rack_id = v_rack_id;
            if v_productos_afectados > 0 then
                raise exception 'No se puede retirar el sector: hay % productos asignados.', v_productos_afectados;
            end if;
            update public.ubicaciones set estado = 'Inactivo' where rack_id = v_rack_id;
            update public.racks set estado = 'Inactivo' where id = v_rack_id;
            v_estado := 'Inactivo';
        elsif p_accion = 'reactivar' then
            v_estado := 'Activo';
        else
            v_estado := v_rack.estado;
        end if;
    end if;

    if v_estantes_modulo not between 1 and 10 then
        raise exception 'Los estantes por modulo deben estar entre 1 y 10.';
    end if;
    if v_modulos not between 1 and 20 then
        raise exception 'Los modulos deben estar entre 1 y 20.';
    end if;
    if coalesce(v_ancho, 1) <= 0
       or coalesce(v_alto, 1) <= 0
       or coalesce(v_profundidad, 1) <= 0
       or coalesce(v_capacidad, 1) <= 0 then
        raise exception 'Las dimensiones y la capacidad deben ser mayores a cero.';
    end if;

    v_total_estantes := v_estantes_modulo * v_modulos;

    if p_accion in ('crear', 'actualizar', 'reactivar') then
        select array_agg(u.id) into v_ubicaciones_retirar
          from public.ubicaciones u
         where u.rack_id = v_rack_id
           and u.tipo = 'Bloque'
           and nullif(regexp_replace(u.nivel, '\D', '', 'g'), '')::integer
               > v_total_estantes;

        if v_ubicaciones_retirar is not null then
            select count(*) into v_productos_afectados
              from public.productos
             where ubicacion_id = any(v_ubicaciones_retirar);
            if v_productos_afectados > 0 then
                raise exception 'No se puede reducir el sector: % productos quedarian fuera de los estantes.', v_productos_afectados;
            end if;
            update public.ubicaciones
               set estado = 'Inactivo'
             where id = any(v_ubicaciones_retirar);
        end if;

        update public.racks
           set nombre = v_nombre,
               descripcion = v_descripcion,
               niveles = v_estantes_modulo,
               columnas = v_modulos,
               ancho_cm = v_ancho,
               alto_cm = v_alto,
               profundidad_cm = v_profundidad,
               capacidad_kg = v_capacidad,
               posicion_orden = v_posicion,
               estado = 'Activo'
         where id = v_rack_id;

        for v_i in 1..v_total_estantes loop
            update public.ubicaciones u
               set codigo_ubicacion =
                       'B' || v_bodega_id::text || '-' || v_codigo
                       || '-E' || lpad(v_i::text, 3, '0'),
                   nivel = 'E' || lpad(v_i::text, 3, '0'),
                   columna = 'M' || lpad(
                       (((v_i - 1) / v_estantes_modulo) + 1)::text,
                       2,
                       '0'
                   ),
                   descripcion = 'Sector ' || v_codigo || ' - Estante ' || v_i,
                   estado = 'Activo'
             where u.rack_id = v_rack_id
               and u.tipo = 'Bloque'
               and u.nivel = 'E' || lpad(v_i::text, 3, '0');

            if not found then
                insert into public.ubicaciones (
                    bodega_id, rack_id, codigo_ubicacion, tipo,
                    nivel, columna, subdivision, ubicacion_padre_id,
                    descripcion, estado
                ) values (
                    v_bodega_id,
                    v_rack_id,
                    'B' || v_bodega_id::text || '-' || v_codigo
                        || '-E' || lpad(v_i::text, 3, '0'),
                    'Bloque',
                    'E' || lpad(v_i::text, 3, '0'),
                    'M' || lpad(
                        (((v_i - 1) / v_estantes_modulo) + 1)::text,
                        2,
                        '0'
                    ),
                    null,
                    null,
                    'Sector ' || v_codigo || ' - Estante ' || v_i,
                    'Activo'
                );
            end if;
        end loop;
        v_estado := 'Activo';
    end if;

    insert into public.auditoria (modulo, accion, detalle, usuario_app, datos)
    values (
        'Sectores',
        initcap(p_accion) || ' sector',
        p_accion || ' sector ' || v_codigo,
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

notify pgrst, 'reload schema';

commit;
