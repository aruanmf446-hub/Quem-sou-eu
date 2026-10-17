"""Gera o SQL de preços e pacotes a partir de src/avatar/catalog.ts.

python3 scripts/avatar/catalog_sql.py > supabase/migrations/<data>_avatar_<nome>.sql
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
cat = open(os.path.join(ROOT, 'src', 'avatar', 'catalog.ts')).read()
items = re.findall(r"\{ id: '([\w-]+)', slot: '(\w+)', name: '[^']*', price: (\d+), rarity: '[^']*'(?:, bundle: '([\w-]+)')?", cat)
motions = re.findall(r"\{ id: '(\w+)', name: '[^']*', subtitle: '[^']*', price: (\d+), kind: '(\w+)' \}", cat)
bundles = re.findall(r"id: '([\w-]+)', name: '[^']+', subtitle: '[^']+', price: (\d+), color:", cat)
print('-- Gerado por scripts/avatar/catalog_sql.py: preços oficiais do Estúdio 3D (idempotente).')
print('insert into public.shop_items (kind, item_id, price) values')
rows = [f"  ('character','{b}',{p})" for b, p in bundles] + [f"  ('item','{i}',{p})" for i, _, p, _ in items] + [f"  ('dance','{i}',{p})" for i, p, _ in motions]
print(',\n'.join(rows))
print('on conflict (kind, item_id) do update set price = excluded.price;\n')
print('insert into public.item_bundles (item_id, character_id) values')
print(',\n'.join(f"  ('{i}','{b}')" for i, _, _, b in items if b))
print('on conflict (item_id) do update set character_id = excluded.character_id;')
