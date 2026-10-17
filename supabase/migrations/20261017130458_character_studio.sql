-- Shared humanoid skins and dances, priced and unlocked on the server.
alter table public.profiles
  add column if not exists owned_characters text[] not null default array['street'],
  add column if not exists owned_dances text[] not null default array['groove'],
  add column if not exists avatar jsonb not null default '{"character":"street","dance":"groove","color":"#7857ff","height":1}';
grant update (avatar) on public.profiles to authenticated;

alter table public.shop_items drop constraint shop_items_kind_check;
alter table public.shop_items add constraint shop_items_kind_check
  check (kind in ('color','hat','visor','deck','character','dance'));
insert into public.shop_items (kind, item_id, price) values
  ('character','street',0), ('character','striker',150), ('character','night-clown',250),
  ('dance','groove',0), ('dance','samba',100), ('dance','robot',150), ('dance','thriller',200)
on conflict (kind, item_id) do update set price = excluded.price;

-- Only this private function can debit balances or write ownership arrays.
create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;
create or replace function private.purchase_item(p_kind text, p_item_id text)
returns integer language plpgsql security definer set search_path = '' as $$
declare
  v_price integer;
  v_profile public.profiles%rowtype;
  v_field text;
  v_owned text[];
  v_coins integer;
begin
  if auth.uid() is null then raise exception 'não autenticado'; end if;
  select price into v_price from public.shop_items where kind = p_kind and item_id = p_item_id;
  if v_price is null then raise exception 'item inexistente'; end if;
  v_field := case p_kind
    when 'color' then 'owned_colors' when 'hat' then 'owned_hats'
    when 'visor' then 'owned_visors' when 'deck' then 'owned_decks'
    when 'character' then 'owned_characters' when 'dance' then 'owned_dances' end;
  if v_field is null then raise exception 'tipo inválido'; end if;
  select * into v_profile from public.profiles where id = auth.uid() for update;
  if not found then raise exception 'perfil inexistente'; end if;
  select array_agg(value) into v_owned from jsonb_array_elements_text(to_jsonb(v_profile)->v_field);
  if p_item_id = any(coalesce(v_owned, '{}')) then return v_profile.coins; end if;
  if v_profile.coins < v_price then raise exception 'moedas insuficientes'; end if;
  execute format('update public.profiles set coins = coins - $1, %I = array_append(%I, $2) where id = $3 returning coins', v_field, v_field)
    into v_coins using v_price, p_item_id, auth.uid();
  return v_coins;
end;
$$;
revoke all on function private.purchase_item(text,text) from public, anon;
grant execute on function private.purchase_item(text,text) to authenticated;

-- Keep the existing RPC contract; do not expose a SECURITY DEFINER in public.
create or replace function public.purchase_item(p_kind text, p_item_id text)
returns integer language sql security invoker set search_path = '' as $$
  select private.purchase_item(p_kind, p_item_id);
$$;
revoke all on function public.purchase_item(text,text) from public, anon;
grant execute on function public.purchase_item(text,text) to authenticated;

-- Reject equipping an unowned item, including forged requests outside the UI.
create or replace function private.validate_avatar()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if not ((new.avatar->>'character') = any(new.owned_characters))
     or not ((new.avatar->>'dance') = any(new.owned_dances))
     or new.avatar->>'character' is null or new.avatar->>'dance' is null then
    raise exception 'personagem ou dança não adquirido';
  end if;
  if coalesce(new.avatar->>'color', '') !~ '^#[0-9a-fA-F]{6}$'
     or (new.avatar->>'height') is null
     or (new.avatar->>'height')::numeric not between 0.85 and 1.15 then
    raise exception 'aparência inválida';
  end if;
  return new;
end;
$$;
create trigger validate_character_avatar before insert or update of avatar on public.profiles
  for each row execute function private.validate_avatar();
