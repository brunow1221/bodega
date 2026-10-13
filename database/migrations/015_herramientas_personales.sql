begin;

-- Incorpora un movimiento permanente, separado de los préstamos y devoluciones.
-- La función existente se conserva completa y solo se amplía en dos puntos
-- controlados para mantener compatibilidad con instalaciones ya migradas.
do $migracion$
declare
    v_firma regprocedure :=
        'public.registrar_movimiento_app(uuid,uuid,text,text,text,text,integer,text,text)'::regprocedure;
    v_definicion text;
    v_marcador_stock text :=
        $$'Entrega / Consumo', 'Baja por Dano / Merma',$$;
    v_reemplazo_stock text :=
        $$'Entrega / Consumo', 'Entrega de Herramienta Personal',
        'Baja por Dano / Merma',$$;
    v_marcador_trabajador text :=
        $$    v_es_resta := p_tipo_movimiento in ($$;
    v_reemplazo_trabajador text :=
        $$    if p_tipo_movimiento = 'Entrega de Herramienta Personal'
       and v_trabajador_id is null then
        raise exception 'La entrega de herramienta personal requiere un trabajador.';
    end if;

    v_es_resta := p_tipo_movimiento in ($$;
begin
    select pg_get_functiondef(v_firma) into v_definicion;

    if position('Entrega de Herramienta Personal' in v_definicion) = 0 then
        if position(v_marcador_stock in v_definicion) = 0
           or position(v_marcador_trabajador in v_definicion) = 0 then
            raise exception
                'No se reconoció registrar_movimiento_app. Ejecute antes la migración 001.';
        end if;

        v_definicion := replace(
            v_definicion,
            v_marcador_stock,
            v_reemplazo_stock
        );
        v_definicion := replace(
            v_definicion,
            v_marcador_trabajador,
            v_reemplazo_trabajador
        );
        execute v_definicion;
    end if;
end;
$migracion$;

revoke all on function public.registrar_movimiento_app(
    uuid, uuid, text, text, text, text, integer, text, text
) from public;
grant execute on function public.registrar_movimiento_app(
    uuid, uuid, text, text, text, text, integer, text, text
) to anon, authenticated;

notify pgrst, 'reload schema';

commit;
