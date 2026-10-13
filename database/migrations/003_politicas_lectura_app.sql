-- Permite que la aplicacion lea tablas operativas con la llave publica.
-- Las escrituras siguen pasando por RPCs con sesion de la app.

do $$
declare
    v_tabla text;
    v_politica text;
    v_tablas text[] := array[
        'bodegas',
        'racks',
        'ubicaciones',
        'productos',
        'proyectos',
        'trabajadores',
        'transacciones',
        'categorias',
        'config_app',
        'configuracion',
        'historial',
        'historial_salidas',
        'historial_precios'
    ];
begin
    grant usage on schema public to anon, authenticated;

    foreach v_tabla in array v_tablas loop
        if to_regclass(format('public.%I', v_tabla)) is null then
            continue;
        end if;

        execute format(
            'alter table public.%I enable row level security',
            v_tabla
        );

        execute format(
            'grant select on public.%I to anon, authenticated',
            v_tabla
        );

        v_politica := 'app_select_' || v_tabla;

        execute format(
            'drop policy if exists %I on public.%I',
            v_politica,
            v_tabla
        );

        execute format(
            'create policy %I on public.%I for select to anon, authenticated using (true)',
            v_politica,
            v_tabla
        );
    end loop;
end
$$;

notify pgrst, 'reload schema';
