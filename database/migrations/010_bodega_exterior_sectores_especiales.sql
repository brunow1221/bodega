-- Agrega la zona exterior y permite administrar más de dos sectores.
-- Conserva los sectores existentes y crea ubicaciones iniciales sin mover productos.

begin;

do $datos_iniciales$
declare
    v_bodega_principal_id bigint;
    v_bodega_exterior_id bigint;
    v_sector record;
    v_sector_id bigint;
    v_posicion integer;
    v_i integer;
begin
    select id
      into v_bodega_principal_id
      from public.bodegas
     where lower(trim(nombre)) <> 'afuera de bodega'
     order by case when upper(coalesce(codigo_bodega, '')) = 'B1' then 0 else 1 end,
              id
     limit 1;

    if v_bodega_principal_id is null then
        insert into public.bodegas (
            codigo_bodega,
            nombre,
            descripcion,
            estado
        ) values (
            'B1',
            'Bodega 1',
            'Bodega principal',
            'Activo'
        ) returning id into v_bodega_principal_id;
    end if;

    select id
      into v_bodega_exterior_id
      from public.bodegas
     where lower(trim(nombre)) = 'afuera de bodega'
     limit 1;

    if v_bodega_exterior_id is null then
        insert into public.bodegas (
            codigo_bodega,
            nombre,
            descripcion,
            estado
        ) values (
            'EXT',
            'Afuera de bodega',
            'Elementos almacenados en sectores exteriores',
            'Activo'
        ) returning id into v_bodega_exterior_id;
    else
        update public.bodegas
           set estado = 'Activo'
         where id = v_bodega_exterior_id;
    end if;

    for v_sector in
        select *
          from (values
              (
                  v_bodega_principal_id,
                  'APORTES',
                  'Aportes',
                  'Sector exclusivo para aportes'
              ),
              (
                  v_bodega_principal_id,
                  'TUERCAS',
                  'Tuercas',
                  'Sector exclusivo para tuercas y fijaciones'
              ),
              (
                  v_bodega_principal_id,
                  'CAFETERIA',
                  'Cafetería',
                  'Sector exclusivo para cafetería'
              ),
              (
                  v_bodega_principal_id,
                  'ASEO',
                  'Aseo',
                  'Sector exclusivo para aseo y limpieza'
              ),
              (
                  v_bodega_exterior_id,
                  'CILINDROS',
                  'Botellas y cilindros',
                  'Sector exterior para botellas de argón y otros cilindros'
              )
          ) as sectores(bodega_id, codigo, nombre, descripcion)
    loop
        select id
          into v_sector_id
          from public.racks
         where bodega_id = v_sector.bodega_id
           and (
               upper(trim(codigo_rack)) = v_sector.codigo
               or lower(trim(coalesce(nombre, ''))) = lower(v_sector.nombre)
           )
         order by id
         limit 1;

        if v_sector_id is null then
            select coalesce(max(posicion_orden), 0) + 1
              into v_posicion
              from public.racks
             where bodega_id = v_sector.bodega_id;

            insert into public.racks (
                bodega_id,
                codigo_rack,
                nombre,
                descripcion,
                niveles,
                columnas,
                posicion_orden,
                estado
            ) values (
                v_sector.bodega_id,
                v_sector.codigo,
                v_sector.nombre,
                v_sector.descripcion,
                5,
                1,
                v_posicion,
                'Activo'
            ) returning id into v_sector_id;
        else
            update public.racks
               set codigo_rack = v_sector.codigo,
                   nombre = v_sector.nombre,
                   descripcion = coalesce(
                       nullif(descripcion, ''),
                       v_sector.descripcion
                   ),
                   estado = 'Activo'
             where id = v_sector_id;
        end if;

        for v_i in 1..5 loop
            update public.ubicaciones ubicacion
               set bodega_id = v_sector.bodega_id,
                   codigo_ubicacion =
                       'B' || v_sector.bodega_id::text || '-'
                       || v_sector.codigo || '-E'
                       || lpad(v_i::text, 3, '0'),
                   columna = 'M01',
                   descripcion = v_sector.nombre || ' - Estante '
                       || v_i::text,
                   estado = 'Activo'
             where ubicacion.rack_id = v_sector_id
               and ubicacion.tipo = 'Bloque'
               and ubicacion.nivel = 'E' || lpad(v_i::text, 3, '0');

            insert into public.ubicaciones (
                bodega_id,
                rack_id,
                codigo_ubicacion,
                tipo,
                nivel,
                columna,
                descripcion,
                estado
            )
            select
                v_sector.bodega_id,
                v_sector_id,
                'B' || v_sector.bodega_id::text || '-'
                    || v_sector.codigo || '-E' || lpad(v_i::text, 3, '0'),
                'Bloque',
                'E' || lpad(v_i::text, 3, '0'),
                'M01',
                v_sector.nombre || ' - Estante ' || v_i::text,
                'Activo'
            where not exists (
                select 1
                  from public.ubicaciones ubicacion
                 where ubicacion.rack_id = v_sector_id
                   and ubicacion.tipo = 'Bloque'
                   and ubicacion.nivel = 'E' || lpad(v_i::text, 3, '0')
            );
        end loop;
    end loop;
end;
$datos_iniciales$;

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
as $funcion$
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

    select respuesta
      into v_respuesta
      from public.solicitudes_app
     where request_id = p_request_id;
    if found then
        return v_respuesta;
    end if;

    insert into public.solicitudes_app (request_id, operacion)
    values (p_request_id, 'sector_' || p_accion)
    on conflict (request_id) do nothing;

    if not found then
        select respuesta
          into v_respuesta
          from public.solicitudes_app
         where request_id = p_request_id;
        return v_respuesta;
    end if;

    if p_accion not in ('crear', 'actualizar', 'retirar', 'reactivar') then
        raise exception 'Accion de sector no permitida.';
    end if;

    if p_accion = 'crear' then
        select id
          into v_bodega_id
          from public.bodegas
         where id::text = p_datos ->> 'bodega_id'
           and estado = 'Activo'
         limit 1;
        if not found then
            raise exception 'La bodega seleccionada no existe o está inactiva.';
        end if;

        v_codigo := upper(trim(p_datos ->> 'codigo_rack'));
        v_nombre := trim(coalesce(p_datos ->> 'nombre', 'Sector ' || v_codigo));
        v_descripcion := trim(coalesce(p_datos ->> 'descripcion', ''));
        v_estantes_modulo := coalesce((p_datos ->> 'niveles')::integer, 5);
        v_modulos := coalesce((p_datos ->> 'columnas')::integer, 1);
        v_ancho := nullif(p_datos ->> 'ancho_cm', '')::numeric;
        v_alto := nullif(p_datos ->> 'alto_cm', '')::numeric;
        v_profundidad := nullif(p_datos ->> 'profundidad_cm', '')::numeric;
        v_capacidad := nullif(p_datos ->> 'capacidad_kg', '')::numeric;
        v_posicion := coalesce(
            (p_datos ->> 'posicion_orden')::integer,
            (
                select coalesce(max(posicion_orden), 0) + 1
                  from public.racks
                 where bodega_id = v_bodega_id
            )
        );

        if v_codigo !~ '^[A-Z0-9_-]{1,20}$' then
            raise exception 'Codigo de sector invalido.';
        end if;
        if nullif(v_nombre, '') is null then
            raise exception 'El nombre del sector es obligatorio.';
        end if;
        if exists (
            select 1
              from public.racks
             where bodega_id = v_bodega_id
               and upper(trim(codigo_rack)) = v_codigo
        ) then
            raise exception 'El sector % ya existe.', v_codigo;
        end if;

        insert into public.racks (
            bodega_id,
            codigo_rack,
            nombre,
            descripcion,
            niveles,
            columnas,
            ancho_cm,
            alto_cm,
            profundidad_cm,
            capacidad_kg,
            posicion_orden,
            estado
        ) values (
            v_bodega_id,
            v_codigo,
            v_nombre,
            v_descripcion,
            v_estantes_modulo,
            v_modulos,
            v_ancho,
            v_alto,
            v_profundidad,
            v_capacidad,
            v_posicion,
            'Activo'
        ) returning id into v_rack_id;
        v_estado := 'Activo';
    else
        select *
          into v_rack
          from public.racks
         where id::text = p_datos ->> 'id'
         for update;
        if not found then
            raise exception 'Sector no encontrado.';
        end if;

        v_rack_id := v_rack.id;
        v_bodega_id := v_rack.bodega_id;
        v_codigo := v_rack.codigo_rack;
        v_nombre := trim(coalesce(p_datos ->> 'nombre', v_rack.nombre));
        v_descripcion := trim(coalesce(
            p_datos ->> 'descripcion',
            v_rack.descripcion,
            ''
        ));
        v_estantes_modulo := coalesce(
            (p_datos ->> 'niveles')::integer,
            v_rack.niveles,
            5
        );
        v_modulos := coalesce(
            (p_datos ->> 'columnas')::integer,
            v_rack.columnas,
            1
        );
        v_ancho := case when p_datos ? 'ancho_cm'
            then nullif(p_datos ->> 'ancho_cm', '')::numeric
            else v_rack.ancho_cm end;
        v_alto := case when p_datos ? 'alto_cm'
            then nullif(p_datos ->> 'alto_cm', '')::numeric
            else v_rack.alto_cm end;
        v_profundidad := case when p_datos ? 'profundidad_cm'
            then nullif(p_datos ->> 'profundidad_cm', '')::numeric
            else v_rack.profundidad_cm end;
        v_capacidad := case when p_datos ? 'capacidad_kg'
            then nullif(p_datos ->> 'capacidad_kg', '')::numeric
            else v_rack.capacidad_kg end;
        v_posicion := coalesce(
            (p_datos ->> 'posicion_orden')::integer,
            v_rack.posicion_orden,
            1
        );

        if p_accion = 'retirar' then
            select count(*)
              into v_productos_afectados
              from public.productos producto
              join public.ubicaciones ubicacion
                on ubicacion.id = producto.ubicacion_id
             where ubicacion.rack_id = v_rack_id;
            if v_productos_afectados > 0 then
                raise exception
                    'No se puede retirar el sector: hay % productos asignados.',
                    v_productos_afectados;
            end if;
            update public.ubicaciones
               set estado = 'Inactivo'
             where rack_id = v_rack_id;
            update public.racks
               set estado = 'Inactivo'
             where id = v_rack_id;
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
        select array_agg(ubicacion.id)
          into v_ubicaciones_retirar
          from public.ubicaciones ubicacion
         where ubicacion.rack_id = v_rack_id
           and ubicacion.tipo = 'Bloque'
           and nullif(
               regexp_replace(ubicacion.nivel, '\D', '', 'g'),
               ''
           )::integer > v_total_estantes;

        if v_ubicaciones_retirar is not null then
            select count(*)
              into v_productos_afectados
              from public.productos
             where ubicacion_id = any(v_ubicaciones_retirar);
            if v_productos_afectados > 0 then
                raise exception
                    'No se puede reducir el sector: % productos quedarian fuera de los estantes.',
                    v_productos_afectados;
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
            update public.ubicaciones ubicacion
               set codigo_ubicacion =
                       'B' || v_bodega_id::text || '-' || v_codigo
                       || '-E' || lpad(v_i::text, 3, '0'),
                   nivel = 'E' || lpad(v_i::text, 3, '0'),
                   columna = 'M' || lpad(
                       (((v_i - 1) / v_estantes_modulo) + 1)::text,
                       2,
                       '0'
                   ),
                   descripcion = v_nombre || ' - Estante ' || v_i::text,
                   estado = 'Activo'
             where ubicacion.rack_id = v_rack_id
               and ubicacion.tipo = 'Bloque'
               and ubicacion.nivel = 'E' || lpad(v_i::text, 3, '0');

            if not found then
                insert into public.ubicaciones (
                    bodega_id,
                    rack_id,
                    codigo_ubicacion,
                    tipo,
                    nivel,
                    columna,
                    subdivision,
                    ubicacion_padre_id,
                    descripcion,
                    estado
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
                    v_nombre || ' - Estante ' || v_i::text,
                    'Activo'
                );
            end if;
        end loop;
        v_estado := 'Activo';
    end if;

    insert into public.auditoria (
        modulo,
        accion,
        detalle,
        usuario_app,
        datos
    ) values (
        'Sectores',
        initcap(p_accion) || ' sector',
        p_accion || ' sector ' || v_nombre,
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
$funcion$;

revoke all on function public.gestionar_rack_app(
    uuid,
    uuid,
    text,
    jsonb
) from public;

grant execute on function public.gestionar_rack_app(
    uuid,
    uuid,
    text,
    jsonb
) to anon, authenticated;

insert into public.config_app (clave, valor, actualizado_en)
values ('modo_ubicaciones', 'bodegas_sectores_multiples_v1', now())
on conflict (clave) do update
set valor = excluded.valor,
    actualizado_en = excluded.actualizado_en;

notify pgrst, 'reload schema';

commit;
