-- Separa Cafetería y Aseo en sectores independientes.
-- Si existe el sector combinado anterior, conserva los artículos y los
-- distribuye según su categoría o subcategoría.

begin;

do $separacion$
declare
    v_bodega_id bigint;
    v_sector_combinado_id bigint;
    v_cafeteria_id bigint;
    v_aseo_id bigint;
    v_sector record;
    v_sector_id bigint;
    v_posicion integer;
    v_i integer;
begin
    select id
      into v_bodega_id
      from public.bodegas
     where lower(trim(nombre)) <> 'afuera de bodega'
     order by case when upper(coalesce(codigo_bodega, '')) = 'B1' then 0 else 1 end,
              id
     limit 1;

    if v_bodega_id is null then
        raise exception 'No existe una bodega principal activa.';
    end if;

    select id
      into v_sector_combinado_id
      from public.racks
     where bodega_id = v_bodega_id
       and (
           upper(trim(codigo_rack)) = 'CAF_ASEO'
           or lower(trim(coalesce(nombre, ''))) = 'cafetería/aseo'
       )
     order by id
     limit 1;

    select id
      into v_cafeteria_id
      from public.racks
     where bodega_id = v_bodega_id
       and upper(trim(codigo_rack)) = 'CAFETERIA'
     order by id
     limit 1;

    if v_sector_combinado_id is not null and v_cafeteria_id is null then
        update public.racks
           set codigo_rack = 'CAFETERIA',
               nombre = 'Cafetería',
               descripcion = 'Sector exclusivo para cafetería',
               estado = 'Activo'
         where id = v_sector_combinado_id;
        v_cafeteria_id := v_sector_combinado_id;
    end if;

    for v_sector in
        select *
          from (values
              (
                  'CAFETERIA',
                  'Cafetería',
                  'Sector exclusivo para cafetería'
              ),
              (
                  'ASEO',
                  'Aseo',
                  'Sector exclusivo para aseo y limpieza'
              )
          ) as sectores(codigo, nombre, descripcion)
    loop
        select id
          into v_sector_id
          from public.racks
         where bodega_id = v_bodega_id
           and upper(trim(codigo_rack)) = v_sector.codigo
         order by id
         limit 1;

        if v_sector_id is null then
            select coalesce(max(posicion_orden), 0) + 1
              into v_posicion
              from public.racks
             where bodega_id = v_bodega_id;

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
                v_bodega_id,
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
               set nombre = v_sector.nombre,
                   descripcion = coalesce(
                       nullif(descripcion, ''),
                       v_sector.descripcion
                   ),
                   estado = 'Activo'
             where id = v_sector_id;
        end if;

        if v_sector.codigo = 'CAFETERIA' then
            v_cafeteria_id := v_sector_id;
        else
            v_aseo_id := v_sector_id;
        end if;

        for v_i in 1..5 loop
            update public.ubicaciones ubicacion
               set bodega_id = v_bodega_id,
                   codigo_ubicacion = 'B' || v_bodega_id::text || '-'
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
                v_bodega_id,
                v_sector_id,
                'B' || v_bodega_id::text || '-' || v_sector.codigo
                    || '-E' || lpad(v_i::text, 3, '0'),
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

    if v_sector_combinado_id is not null then
        update public.productos producto
           set ubicacion_id = coalesce(
               (
                   select destino.id
                     from public.ubicaciones destino
                    where destino.rack_id = v_aseo_id
                      and destino.tipo = 'Bloque'
                      and destino.nivel = origen.nivel
                      and destino.estado = 'Activo'
                    limit 1
               ),
               (
                   select destino.id
                     from public.ubicaciones destino
                    where destino.rack_id = v_aseo_id
                      and destino.tipo = 'Bloque'
                      and destino.estado = 'Activo'
                    order by destino.nivel
                    limit 1
               )
           )
          from public.ubicaciones origen
         where producto.ubicacion_id = origen.id
           and origen.rack_id = v_sector_combinado_id
           and lower(
               coalesce(producto.categoria, '') || ' '
               || coalesce(producto.subcategoria, '')
           ) ~ '(aseo|limpieza|higiene)';
    end if;

    if v_sector_combinado_id is not null
       and v_sector_combinado_id <> v_cafeteria_id then
        update public.productos producto
           set ubicacion_id = coalesce(
               (
                   select destino.id
                     from public.ubicaciones destino
                    where destino.rack_id = case
                        when lower(
                            coalesce(producto.categoria, '') || ' '
                            || coalesce(producto.subcategoria, '')
                        ) ~ '(aseo|limpieza|higiene)'
                        then v_aseo_id
                        else v_cafeteria_id
                    end
                      and destino.tipo = 'Bloque'
                      and destino.nivel = origen.nivel
                      and destino.estado = 'Activo'
                    limit 1
               ),
               (
                   select destino.id
                     from public.ubicaciones destino
                    where destino.rack_id = case
                        when lower(
                            coalesce(producto.categoria, '') || ' '
                            || coalesce(producto.subcategoria, '')
                        ) ~ '(aseo|limpieza|higiene)'
                        then v_aseo_id
                        else v_cafeteria_id
                    end
                      and destino.tipo = 'Bloque'
                      and destino.estado = 'Activo'
                    order by destino.nivel
                    limit 1
               )
           )
          from public.ubicaciones origen
         where producto.ubicacion_id = origen.id
           and origen.rack_id = v_sector_combinado_id;

        update public.ubicaciones
           set estado = 'Inactivo'
         where rack_id = v_sector_combinado_id;
        update public.racks
           set estado = 'Inactivo',
               nombre = 'Sector combinado anterior'
         where id = v_sector_combinado_id;
    end if;
end;
$separacion$;

insert into public.config_app (clave, valor, actualizado_en)
values ('modo_cafeteria_aseo', 'separados_v1', now())
on conflict (clave) do update
set valor = excluded.valor,
    actualizado_en = excluded.actualizado_en;

notify pgrst, 'reload schema';

commit;
