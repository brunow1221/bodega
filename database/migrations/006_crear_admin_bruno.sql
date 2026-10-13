-- Crea o repara el usuario administrador "bruno".
-- Copie el script a SQL Editor y cambie solo v_nueva_clave en esa copia.
-- No guarde la clave real en este archivo ni la suba al repositorio.

begin;

create extension if not exists pgcrypto;

-- Normaliza el login sobre las columnas que utiliza actualmente la app.
-- Supabase instala normalmente pgcrypto dentro del esquema extensions.
create or replace function public.login_usuario_app(
    p_usuario text,
    p_password text
)
returns table (
    id text,
    usuario text,
    nombre text,
    rol text
)
language sql
stable
security definer
set search_path = public, extensions
as $login$
    select
        u.id::text,
        u.usuario::text,
        u.nombre::text,
        u.rol::text
      from public.usuarios_app u
     where lower(u.usuario) = lower(trim(p_usuario))
       and lower(coalesce(u.estado, 'Activo')) in (
           'activo', 'active', 'true', 't', '1', 'si', 'sí', 'habilitado'
       )
       and case
           when u.password_hash = p_password then true
           when u.password_hash like '$2%' then
               crypt(p_password, u.password_hash) = u.password_hash
           else false
       end
     limit 1;
$login$;

revoke all on function public.login_usuario_app(text, text) from public;
grant execute on function public.login_usuario_app(text, text)
    to anon, authenticated;

do $admin$
declare
    v_nueva_clave text := 'REEMPLAZAR_POR_NUEVA_CLAVE';
begin
    if v_nueva_clave like 'REEMPLAZAR%'
       or length(v_nueva_clave) < 12 then
        raise exception
            'Cambie v_nueva_clave por una clave de al menos 12 caracteres.';
    end if;

    if to_regclass('public.usuarios_app') is null then
        raise exception 'No existe public.usuarios_app.';
    end if;

    if exists (
        select 1
          from unnest(array[
              'usuario', 'nombre', 'rol', 'estado', 'password_hash'
          ]) as requerida(nombre)
         where not exists (
             select 1
               from information_schema.columns c
              where c.table_schema = 'public'
                and c.table_name = 'usuarios_app'
                and c.column_name = requerida.nombre
         )
    ) then
        raise exception
            'usuarios_app no tiene todas las columnas requeridas por la aplicacion.';
    end if;

    update public.usuarios_app
       set usuario = 'bruno',
           nombre = 'Bruno',
           rol = 'Administrador',
           estado = 'Activo',
           password_hash = crypt(v_nueva_clave, gen_salt('bf', 12))
     where lower(usuario) = 'bruno';

    if not found then
        insert into public.usuarios_app (
            usuario,
            nombre,
            rol,
            estado,
            password_hash
        ) values (
            'bruno',
            'Bruno',
            'Administrador',
            'Activo',
            crypt(v_nueva_clave, gen_salt('bf', 12))
        );
    end if;

    if not exists (
        select 1
          from public.login_usuario_app('bruno', v_nueva_clave)
    ) then
        raise exception
            'El usuario fue escrito, pero login_usuario_app no lo pudo validar.';
    end if;

    raise notice 'Usuario bruno creado y login comprobado correctamente.';
end;
$admin$;

commit;
