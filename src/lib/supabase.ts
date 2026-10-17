import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { Deck } from '../game/types';
import { getProfile, onProfileChange, setProfile, type Profile } from './profile';

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const supabase: SupabaseClient | null = url && key ? createClient(url, key) : null;
export const isOnlineAvailable = supabase !== null;

let userId: string | null = null;

/**
 * Login anônimo (sem e-mail) e sincronização do perfil.
 * Moedas e compras passam por funções no banco para não serem editadas pelo cliente.
 */
let initPromise: Promise<string | null> | null = null;

export function initOnline(): Promise<string | null> {
  initPromise ??= doInit();
  return initPromise;
}

async function doInit(): Promise<string | null> {
  if (!supabase) return null;
  const { data: sessionData } = await supabase.auth.getSession();
  let user = sessionData.session?.user ?? null;
  if (!user) {
    const { data, error } = await supabase.auth.signInAnonymously();
    if (error) {
      console.warn('Login anônimo falhou', error.message);
      return null;
    }
    user = data.user;
  }
  if (!user) return null;
  userId = user.id;

  const local = getProfile();
  const { data: row } = await supabase.from('profiles').select('*').eq('id', user.id).maybeSingle();
  if (row) {
    setProfile({
      id: user.id,
      name: row.username ?? local.name,
      coins: row.coins,
      skin: row.skin ?? local.skin,
      ownedColors: row.owned_colors ?? local.ownedColors,
      ownedHats: row.owned_hats ?? local.ownedHats,
      ownedVisors: row.owned_visors ?? local.ownedVisors,
      ownedDecks: row.owned_decks ?? local.ownedDecks,
      story: row.story ?? local.story,
      ownedCharacters: row.owned_characters ?? ['street'],
      ownedDances: row.owned_dances ?? ['groove'],
      avatar: row.avatar ?? local.avatar,
    });
  } else {
    await supabase.from('profiles').insert({ id: user.id, username: local.name, skin: local.skin, story: local.story });
    setProfile({ id: user.id });
  }

  const { data: decks } = await supabase.from('decks').select('*').eq('owner', user.id);
  if (decks) setProfile({ customDecks: decks.map(rowToDeck) });

  let timer: number | undefined;
  onProfileChange((p: Profile) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      void supabase!.from('profiles').update({ username: p.name, skin: p.skin, story: p.story, avatar: p.avatar }).eq('id', user!.id);
    }, 800);
  });
  return user.id;
}

function rowToDeck(r: { id: string; name: string; description: string; cards: Deck['cards']; owner_name?: string }): Deck {
  return { id: r.id, name: r.name, description: r.description ?? '', cards: r.cards, price: 0, official: false, author: r.owner_name };
}

export async function saveDeckRemote(deck: Deck, isPublic: boolean): Promise<Deck> {
  if (!supabase || !userId) return deck;
  const payload = { name: deck.name, description: deck.description, cards: deck.cards, is_public: isPublic, owner: userId, owner_name: getProfile().name };
  const isNew = deck.id.startsWith('custom-');
  const query = isNew
    ? supabase.from('decks').insert(payload).select().single()
    : supabase.from('decks').update(payload).eq('id', deck.id).select().single();
  const { data, error } = await query;
  if (error || !data) throw new Error(error?.message ?? 'Erro ao salvar deck');
  return rowToDeck(data);
}

export async function deleteDeckRemote(id: string) {
  if (!supabase || !userId || id.startsWith('custom-')) return;
  await supabase.from('decks').delete().eq('id', id);
}

export async function listCommunityDecks(): Promise<Deck[]> {
  if (!supabase) return [];
  const { data } = await supabase.from('decks').select('*').eq('is_public', true).order('created_at', { ascending: false }).limit(50);
  return (data ?? []).map(rowToDeck);
}

export type ItemKind = 'color' | 'hat' | 'visor' | 'deck' | 'character' | 'dance';

/** Compra no servidor (o preço vem da tabela shop_items, não do cliente). */
export async function purchaseRemote(kind: ItemKind, itemId: string): Promise<number | null> {
  if (!supabase || !userId) return null;
  const { data, error } = await supabase.rpc('purchase_item', { p_kind: kind, p_item_id: itemId });
  if (error) throw new Error(error.message);
  return data as number;
}

export async function awardCoinsRemote(amount: number, reason: string): Promise<number | null> {
  if (!supabase || !userId) return null;
  const { data, error } = await supabase.rpc('award_coins', { p_amount: amount, p_reason: reason });
  if (error) {
    console.warn(error.message);
    return null;
  }
  return data as number;
}
