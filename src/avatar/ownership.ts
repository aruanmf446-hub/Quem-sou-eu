import type { AvatarLook, CharacterId } from '../data/characters';
import type { Profile } from '../lib/profile';
import { BUNDLES, BUNDLE_BY_ID, DEFAULT_CONFIG, ITEM_BY_ID, ITEMS, MOTION_BY_ID, REQUIRED_SLOTS, type Bundle, type CatalogItem, type Motion } from './catalog';
import { sanitizeConfig, SLOTS, type AvatarConfig } from './config';

type Owner = Pick<Profile, 'ownedItems' | 'ownedCharacters' | 'ownedDances'>;

export function ownsItem(p: Owner, id: string) {
  const item = ITEM_BY_ID.get(id);
  if (!item) return false;
  return item.price === 0 || (p.ownedItems ?? []).includes(id) || (!!item.bundle && p.ownedCharacters.includes(item.bundle));
}

export function ownsMotion(p: Owner, id: string) {
  const m = MOTION_BY_ID.get(id);
  return !!m && (m.price === 0 || p.ownedDances.includes(id));
}

/** Configuração completa do avatar a partir do perfil (inclui perfis antigos sem `creator`). */
export function resolveConfig(look: AvatarLook | undefined): AvatarConfig {
  const bundle = BUNDLE_BY_ID.get((look?.character ?? 'street') as CharacterId) ?? BUNDLES[0];
  const fallback = { ...structuredClone(bundle.config), dance: look?.dance ?? bundle.config.dance };
  const config = look?.creator ? sanitizeConfig(look.creator, fallback) : fallback;
  return normalize(config);
}

/** Garante itens válidos, slots coerentes e obrigatórios preenchidos. */
export function normalize(config: AvatarConfig): AvatarConfig {
  const out = structuredClone(config);
  for (const slot of SLOTS) {
    const id = out.items[slot];
    if (id && ITEM_BY_ID.get(id)?.slot !== slot) out.items[slot] = null;
  }
  for (const slot of REQUIRED_SLOTS) {
    if (!out.items[slot]) out.items[slot] = DEFAULT_CONFIG.items[slot] ?? ITEMS.find(i => i.slot === slot && i.price === 0)?.id ?? null;
  }
  if (!MOTION_BY_ID.has(out.dance) || MOTION_BY_ID.get(out.dance)!.kind !== 'dance') out.dance = 'groove';
  if (!MOTION_BY_ID.has(out.celebration) || MOTION_BY_ID.get(out.celebration)!.kind !== 'celebration') out.celebration = 'airplane';
  return out;
}

export interface Cart { items: CatalogItem[]; bundles: Bundle[]; motions: Motion[]; total: number; }

/**
 * O que falta comprar para equipar esta configuração. Quando as peças de um
 * personagem original custariam mais que o próprio personagem, o carrinho
 * oferece o pacote completo (que libera todas as peças dele).
 */
export function cartFor(p: Owner, config: AvatarConfig): Cart {
  const items = Object.values(config.items).filter((id): id is string => !!id).map(id => ITEM_BY_ID.get(id)!).filter(i => i && !ownsItem(p, i.id));
  let unique = [...new Map(items.map(i => [i.id, i])).values()];
  const bundles: Bundle[] = [];
  for (const b of BUNDLES) {
    if (b.price === 0 || p.ownedCharacters.includes(b.id)) continue;
    const inBundle = unique.filter(i => i.bundle === b.id);
    if (inBundle.length && inBundle.reduce((s, i) => s + i.price, 0) >= b.price) {
      bundles.push(b);
      unique = unique.filter(i => i.bundle !== b.id);
    }
  }
  const motions = [config.dance, config.celebration].map(id => MOTION_BY_ID.get(id)!).filter(m => m && !ownsMotion(p, m.id));
  const total = unique.reduce((s, i) => s + i.price, 0) + bundles.reduce((s, b) => s + b.price, 0) + motions.reduce((s, m) => s + m.price, 0);
  return { items: unique, bundles, motions, total };
}

/** Converte a configuração em AvatarLook compatível com o formato antigo e com o banco. */
export function toLook(p: Owner, config: AvatarConfig, previous?: AvatarLook): AvatarLook {
  const owned = BUNDLES.filter(b => b.price === 0 || p.ownedCharacters.includes(b.id));
  const score = (b: typeof BUNDLES[number]) => Object.values(config.items).filter(id => id && ITEM_BY_ID.get(id)?.bundle === b.id).length;
  const best = [...owned].sort((a, b) => score(b) - score(a))[0] ?? BUNDLES[0];
  const character = (previous && owned.some(b => b.id === previous.character) && score(BUNDLE_BY_ID.get(previous.character)!) >= score(best) ? previous.character : best.id) as CharacterId;
  return { character, dance: config.dance, celebration: config.celebration, color: BUNDLE_BY_ID.get(character)!.color, height: 1, creator: structuredClone(config) };
}
