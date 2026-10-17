-- Estúdio 3D: criador de avatar, guarda-roupa modular, comemorações e visuais salvos.
-- Aplique depois de 0001_init.sql e 20261017130458_character_studio.sql. Preserva saldos, compras e personagens.

alter table public.profiles
  add column if not exists owned_items text[] not null default '{}',
  add column if not exists outfits jsonb not null default '[]';
grant update (outfits) on public.profiles to authenticated;

alter table public.shop_items drop constraint if exists shop_items_kind_check;
alter table public.shop_items add constraint shop_items_kind_check
  check (kind in ('color','hat','visor','deck','character','dance','item'));

-- Preços oficiais das peças e dos movimentos (danças e comemorações usam owned_dances).
insert into public.shop_items (kind, item_id, price) values
  ('item','hair_curly_fade',120),
  ('item','hair_buzz',0),
  ('item','hair_afro',140),
  ('item','hair_bun',0),
  ('item','hair_clown',90),
  ('item','brows_natural',0),
  ('item','brows_thick',0),
  ('item','brows_thin',0),
  ('item','brows_arched',0),
  ('item','beard_stubble',0),
  ('item','beard_goatee',0),
  ('item','beard_chinstrap',0),
  ('item','beard_full',0),
  ('item','top_tee',0),
  ('item','top_tank',0),
  ('item','top_jersey_10',120),
  ('item','top_jersey_away',150),
  ('item','top_track_jacket',0),
  ('item','top_clown_tunic',160),
  ('item','bottom_shorts',0),
  ('item','bottom_shorts_10',80),
  ('item','bottom_joggers',0),
  ('item','bottom_clown_pants',110),
  ('item','socks_crew',0),
  ('item','socks_football',30),
  ('item','socks_football_10',40),
  ('item','shoes_sneakers',0),
  ('item','shoes_cleats_10',110),
  ('item','shoes_hightops',90),
  ('item','shoes_clown',90),
  ('item','cap_snapback',60),
  ('item','headband',25),
  ('item','glasses_sport',90),
  ('item','glasses_round',70),
  ('item','chain_gold',120),
  ('item','wristband',25),
  ('item','watch',80),
  ('item','tattoo_sleeve',100),
  ('item','facepaint_midnight',80),
  ('dance','groove',0),
  ('dance','samba',100),
  ('dance','robot',150),
  ('dance','thriller',200),
  ('dance','airplane',0),
  ('dance','heart',80),
  ('dance','shh',120),
  ('dance','flex',100),
  ('dance','jump',150)
on conflict (kind, item_id) do update set price = excluded.price;

-- Peças incluídas nos personagens originais: quem já comprou o personagem já possui as peças.
create table if not exists public.item_bundles (
  item_id text primary key,
  character_id text not null
);
alter table public.item_bundles enable row level security;
drop policy if exists "pacotes: leitura pública" on public.item_bundles;
create policy "pacotes: leitura pública" on public.item_bundles for select using (true);
insert into public.item_bundles (item_id, character_id) values
  ('hair_curly_fade','striker'),
  ('hair_bun','street'),
  ('hair_clown','night-clown'),
  ('top_jersey_10','striker'),
  ('top_track_jacket','street'),
  ('top_clown_tunic','night-clown'),
  ('bottom_shorts_10','striker'),
  ('bottom_joggers','street'),
  ('bottom_clown_pants','night-clown'),
  ('socks_football_10','striker'),
  ('shoes_cleats_10','striker'),
  ('shoes_hightops','street'),
  ('shoes_clown','night-clown'),
  ('tattoo_sleeve','striker'),
  ('facepaint_midnight','night-clown')
on conflict (item_id) do update set character_id = excluded.character_id;

-- A compra continua sendo a única forma de debitar saldo e gravar posse.
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
    when 'character' then 'owned_characters' when 'dance' then 'owned_dances'
    when 'item' then 'owned_items' end;
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

create or replace function private.owns_item(p_item text, p_items text[], p_characters text[])
returns boolean language sql stable security invoker set search_path = '' as $$
  select exists (select 1 from public.shop_items s where s.kind = 'item' and s.item_id = p_item and s.price = 0)
      or p_item = any(coalesce(p_items, '{}'))
      or exists (select 1 from public.item_bundles b where b.item_id = p_item and b.character_id = any(coalesce(p_characters, '{}')));
$$;

create or replace function private.owns_motion(p_id text, p_dances text[])
returns boolean language sql stable security invoker set search_path = '' as $$
  select p_id = any(coalesce(p_dances, '{}'))
      or exists (select 1 from public.shop_items s where s.kind = 'dance' and s.item_id = p_id and s.price = 0);
$$;

-- Rejeita equipar o que não foi adquirido, inclusive requisições forjadas fora da interface.
create or replace function private.validate_avatar()
returns trigger language plpgsql security invoker set search_path = '' as $$
declare
  v_item text;
begin
  if new.avatar->>'character' is null or not ((new.avatar->>'character') = any(new.owned_characters)) then
    raise exception 'personagem não adquirido';
  end if;
  if new.avatar->>'dance' is null or not private.owns_motion(new.avatar->>'dance', new.owned_dances) then
    raise exception 'dança não adquirida';
  end if;
  if new.avatar ? 'celebration' and not private.owns_motion(new.avatar->>'celebration', new.owned_dances) then
    raise exception 'comemoração não adquirida';
  end if;
  if coalesce(new.avatar->>'color', '') !~ '^#[0-9a-fA-F]{6}$'
     or (new.avatar->>'height') is null
     or (new.avatar->>'height')::numeric not between 0.85 and 1.15 then
    raise exception 'aparência inválida';
  end if;
  if new.avatar ? 'creator' then
    if jsonb_typeof(new.avatar->'creator') <> 'object' or pg_column_size(new.avatar) > 16384 then
      raise exception 'avatar inválido';
    end if;
    for v_item in select value from jsonb_each_text(coalesce(new.avatar->'creator'->'items', '{}'::jsonb)) where value is not null loop
      if not private.owns_item(v_item, new.owned_items, new.owned_characters) then
        raise exception 'peça não adquirida: %', v_item;
      end if;
    end loop;
  end if;
  return new;
end;
$$;

create or replace function private.validate_outfits()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if jsonb_typeof(new.outfits) <> 'array' or jsonb_array_length(new.outfits) > 12 or pg_column_size(new.outfits) > 200000 then
    raise exception 'visuais salvos inválidos';
  end if;
  return new;
end;
$$;
drop trigger if exists validate_avatar_outfits on public.profiles;
create trigger validate_avatar_outfits before insert or update of outfits on public.profiles
  for each row execute function private.validate_outfits();
