-- Corrige instalaciones donde producto_origen_id quedó con un tipo distinto
-- al de productos.id. La aplicación usa este vínculo para los retazos.

begin;

do $migracion$
declare
    v_tipo_id text;
    v_tipo_origen text;
begin
    if to_regclass('public.productos') is null then
        raise exception 'No existe public.productos.';
    end if;

    select format_type(a.atttypid, a.atttypmod)
      into v_tipo_id
      from pg_attribute a
     where a.attrelid = 'public.productos'::regclass
       and a.attname = 'id'
       and not a.attisdropped;

    if v_tipo_id is null then
        raise exception 'No existe public.productos.id.';
    end if;

    select format_type(a.atttypid, a.atttypmod)
      into v_tipo_origen
      from pg_attribute a
     where a.attrelid = 'public.productos'::regclass
       and a.attname = 'producto_origen_id'
       and not a.attisdropped;

    if v_tipo_origen is null then
        execute format(
            'alter table public.productos '
            'add column producto_origen_id %s',
            v_tipo_id
        );
        raise notice 'Se creó producto_origen_id con tipo %.', v_tipo_id;
        return;
    end if;

    if v_tipo_origen = v_tipo_id then
        raise notice
            'producto_origen_id ya usa el tipo correcto: %.',
            v_tipo_id;
        return;
    end if;

    -- Conserva cualquier dato anterior antes de normalizar el tipo. Los UUID
    -- antiguos no pueden transformarse en bigint, pero quedarán respaldados.
    alter table public.productos
        add column if not exists producto_origen_id_legacy text;

    update public.productos
       set producto_origen_id_legacy = producto_origen_id::text
     where producto_origen_id is not null
       and producto_origen_id_legacy is null;

    execute 'alter table public.productos '
            'alter column producto_origen_id drop default';

    execute format(
        'alter table public.productos '
        'alter column producto_origen_id type %s using null::%s',
        v_tipo_id,
        v_tipo_id
    );

    -- Recupera automáticamente los valores que sí sean compatibles con el
    -- tipo real de productos.id.
    if v_tipo_id in ('bigint', 'integer', 'smallint') then
        execute format(
            'update public.productos '
            'set producto_origen_id = producto_origen_id_legacy::%s '
            'where producto_origen_id_legacy ~ ''^[0-9]+$''',
            v_tipo_id
        );
    elsif v_tipo_id = 'uuid' then
        execute format(
            'update public.productos '
            'set producto_origen_id = producto_origen_id_legacy::%s '
            'where producto_origen_id_legacy ~* ''^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$''',
            v_tipo_id
        );
    end if;

    raise notice
        'producto_origen_id cambió de % a %. Los valores anteriores quedaron respaldados en producto_origen_id_legacy.',
        v_tipo_origen,
        v_tipo_id;
end;
$migracion$;

create index if not exists idx_productos_producto_origen
    on public.productos(producto_origen_id);

commit;
