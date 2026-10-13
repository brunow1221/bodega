-- La fecha real de término corresponde al cambio de estado a Finalizado.
begin;

create or replace function public.actualizar_fecha_termino_proyecto()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    if new.estado = 'Finalizado' then
        if TG_OP = 'INSERT' then
            new.fecha_fin := (current_timestamp at time zone 'America/Santiago')::date;
        elsif old.estado is distinct from 'Finalizado' then
            new.fecha_fin := (current_timestamp at time zone 'America/Santiago')::date;
        else
            new.fecha_fin := old.fecha_fin;
        end if;
        if new.fecha_inicio > new.fecha_fin then
            raise exception 'La fecha de inicio es posterior a la fecha de término.';
        end if;
    else
        new.fecha_fin := null;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_fecha_termino_proyecto on public.proyectos;
create trigger trg_fecha_termino_proyecto
before insert or update on public.proyectos
for each row execute function public.actualizar_fecha_termino_proyecto();

commit;
