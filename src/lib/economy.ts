import { CHARACTERS, DANCES } from '../data/characters';
import { HATS, SKIN_COLORS, VISORS } from '../data/skins';
import { OFFICIAL_DECKS } from '../data/decks';
import { getProfile, setProfile } from './profile';
import { awardCoinsRemote, isOnlineAvailable, purchaseRemote, type ItemKind } from './supabase';
import { audio } from '../audio/music';

export function priceOf(kind: ItemKind, id: string): number {
  const list = kind === 'character' ? CHARACTERS : kind === 'dance' ? DANCES : kind === 'color' ? SKIN_COLORS : kind === 'hat' ? HATS : kind === 'visor' ? VISORS : OFFICIAL_DECKS;
  return list.find((i) => i.id === id)?.price ?? Infinity;
}

const OWN_FIELD = { color: 'ownedColors', hat: 'ownedHats', visor: 'ownedVisors', deck: 'ownedDecks', character: 'ownedCharacters', dance: 'ownedDances' } as const;

export function owns(kind: ItemKind, id: string) {
  return getProfile()[OWN_FIELD[kind]].includes(id);
}

let purchaseQueue: Promise<void> = Promise.resolve();
export function buy(kind: ItemKind, id: string): Promise<void> {
  const operation = purchaseQueue.then(() => purchase(kind, id));
  purchaseQueue = operation.catch(() => {});
  return operation;
}

async function purchase(kind: ItemKind, id: string): Promise<void> {
  const price = priceOf(kind, id);
  const p = getProfile();
  if (!Number.isFinite(price)) throw new Error('Item inexistente');
  if (owns(kind, id)) return;
  if (p.coins < price) throw new Error('Moedas insuficientes');
  let coins = p.coins - price;
  if (isOnlineAvailable && !p.id.startsWith('local-')) {
    const remote = await purchaseRemote(kind, id);
    if (remote === null) throw new Error('Conecte sua conta para comprar');
    coins = remote;
  }
  const field = OWN_FIELD[kind];
  setProfile((cur) => ({ coins, [field]: [...cur[field], id] }));
  audio.sfx('coin');
}

export async function award(amount: number, reason: string) {
  const p = getProfile();
  let coins = p.coins + amount;
  if (isOnlineAvailable && !p.id.startsWith('local-')) {
    const remote = await awardCoinsRemote(amount, reason);
    if (remote !== null) coins = remote;
  }
  setProfile({ coins });
}
