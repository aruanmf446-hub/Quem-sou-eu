-- Quem Sou Eu: esquema inicial
-- Aplique com `supabase db push` ou cole no SQL Editor do painel.
-- Ative também: Authentication > Providers > Anonymous sign-ins.

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  username text not null default 'Jogador',
  coins integer not null default 200 check (coins >= 0),
  skin jsonb not null default '{"body":"#e8384f","visor":"#9fe7ff","hat":"none"}',
  owned_colors text[] not null default array['vermelho','azul','verde','amarelo'],
  owned_hats text[] not null default '{}',
  owned_visors text[] not null default array['gelo'],
  owned_decks text[] not null default array['espaco','profissoes'],
  story jsonb not null default '{"unlocked":1,"best":{}}',
  last_award_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "perfil: ler o próprio" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "perfil: criar o próprio" on public.profiles
  for insert to authenticated with check ((select auth.uid()) = id);
create policy "perfil: editar o próprio" on public.profiles
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

-- O cliente só pode mudar nome, skin e progresso. Moedas e itens só via funções abaixo.
revoke insert, update on public.profiles from authenticated, anon;
grant insert (id, username, skin, story) on public.profiles to authenticated;
grant update (username, skin, story) on public.profiles to authenticated;

-- Catálogo com os preços oficiais (fonte da verdade para compras).
create table if not exists public.shop_items (
  kind text not null check (kind in ('color','hat','visor','deck')),
  item_id text not null,
  price integer not null check (price >= 0),
  primary key (kind, item_id)
);
alter table public.shop_items enable row level security;
create policy "loja: leitura pública" on public.shop_items for select using (true);

insert into public.shop_items (kind, item_id, price) values
  ('color','vermelho',0),('color','azul',0),('color','verde',0),('color','amarelo',0),
  ('color','rosa',100),('color','laranja',100),('color','roxo',150),('color','ciano',150),
  ('color','preto',250),('color','branco',250),('color','dourado',800),('color','galaxia',1200),
  ('hat','bone',150),('hat','festa',200),('hat','cartola',400),('hat','chifres',450),
  ('hat','planta',500),('hat','coroa',1000),('hat','aureola',1500),
  ('visor','gelo',0),('visor','menta',120),('visor','lava',120),('visor','neon',300),
  ('deck','espaco',0),('deck','profissoes',0),('deck','folclore',600),('deck','monstros',400)
on conflict (kind, item_id) do update set price = excluded.price;

-- Decks criados pelos jogadores.
create table if not exists public.decks (
  id uuid primary key default gen_random_uuid(),
  owner uuid not null references auth.users (id) on delete cascade,
  owner_name text,
  name text not null check (char_length(name) between 1 and 40),
  description text not null default '',
  cards jsonb not null check (jsonb_typeof(cards) = 'array' and jsonb_array_length(cards) between 12 and 60),
  is_public boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists decks_owner_idx on public.decks (owner);
create index if not exists decks_public_idx on public.decks (created_at desc) where is_public;

alter table public.decks enable row level security;
create policy "decks: ver públicos e os meus" on public.decks
  for select using (is_public or (select auth.uid()) = owner);
create policy "decks: criar os meus" on public.decks
  for insert to authenticated with check ((select auth.uid()) = owner);
create policy "decks: editar os meus" on public.decks
  for update to authenticated using ((select auth.uid()) = owner) with check ((select auth.uid()) = owner);
create policy "decks: apagar os meus" on public.decks
  for delete to authenticated using ((select auth.uid()) = owner);

-- Compra: confere preço e saldo no servidor. Retorna o novo saldo.
create or replace function public.purchase_item(p_kind text, p_item_id text)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_price integer;
  v_coins integer;
  v_uid uuid := auth.uid();
begin
  if v_uid is null then raise exception 'não autenticado'; end if;
  select price into v_price from public.shop_items where kind = p_kind and item_id = p_item_id;
  if v_price is null then raise exception 'item inexistente'; end if;

  update public.profiles set
    coins = coins - v_price,
    owned_colors = case when p_kind = 'color' and not (p_item_id = any(owned_colors)) then array_append(owned_colors, p_item_id) else owned_colors end,
    owned_hats   = case when p_kind = 'hat'   and not (p_item_id = any(owned_hats))   then array_append(owned_hats, p_item_id)   else owned_hats end,
    owned_visors = case when p_kind = 'visor' and not (p_item_id = any(owned_visors)) then array_append(owned_visors, p_item_id) else owned_visors end,
    owned_decks  = case when p_kind = 'deck'  and not (p_item_id = any(owned_decks))  then array_append(owned_decks, p_item_id)  else owned_decks end
  where id = v_uid
    and coins >= v_price
    and not (
      (p_kind = 'color' and p_item_id = any(owned_colors)) or
      (p_kind = 'hat'   and p_item_id = any(owned_hats)) or
      (p_kind = 'visor' and p_item_id = any(owned_visors)) or
      (p_kind = 'deck'  and p_item_id = any(owned_decks))
    )
  returning coins into v_coins;

  if v_coins is null then raise exception 'moedas insuficientes ou item já comprado'; end if;
  return v_coins;
end;
$$;

-- Recompensa de partida/fase: limite por chamada e intervalo mínimo entre chamadas.
create or replace function public.award_coins(p_amount integer, p_reason text)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_coins integer;
begin
  if auth.uid() is null then raise exception 'não autenticado'; end if;
  if p_amount < 0 or p_amount > 150 then raise exception 'valor inválido'; end if;
  update public.profiles
    set coins = coins + p_amount, last_award_at = now()
    where id = auth.uid()
      and (last_award_at is null or last_award_at < now() - interval '20 seconds')
    returning coins into v_coins;
  if v_coins is null then raise exception 'aguarde para receber novas moedas'; end if;
  return v_coins;
end;
$$;

revoke execute on function public.purchase_item(text, text) from public, anon;
revoke execute on function public.award_coins(integer, text) from public, anon;
grant execute on function public.purchase_item(text, text) to authenticated;
grant execute on function public.award_coins(integer, text) to authenticated;
