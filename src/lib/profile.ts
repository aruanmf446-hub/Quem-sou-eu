import { useSyncExternalStore } from 'react';
import { DEFAULT_LOOK, type AvatarLook } from '../data/characters';
import type { Deck, Skin } from '../game/types';
import { OFFICIAL_DECKS } from '../data/decks';

export interface StoryProgress {
  unlocked: number;
  best: Record<number, { coins: number; cards: number }>;
}

export interface Profile {
  id: string;
  name: string;
  coins: number;
  skin: Skin;
  ownedColors: string[];
  ownedHats: string[];
  ownedVisors: string[];
  ownedDecks: string[];
  ownedCharacters: string[];
  ownedDances: string[];
  avatar: AvatarLook;
  customDecks: Deck[];
  selectedDeckId: string;
  story: StoryProgress;
  settings: { music: number; sfx: number };
}

const KEY = 'quem-sou-eu:profile:v1';

function randomId() {
  return Math.random().toString(36).slice(2, 10);
}

export function defaultProfile(): Profile {
  return {
    id: `local-${randomId()}`,
    name: `Jogador${Math.floor(Math.random() * 900 + 100)}`,
    coins: 200,
    skin: { body: '#e8384f', visor: '#9fe7ff', hat: 'none' },
    ownedColors: ['vermelho', 'azul', 'verde', 'amarelo'],
    ownedHats: [],
    ownedVisors: ['gelo'],
    ownedDecks: OFFICIAL_DECKS.filter((d) => d.price === 0).map((d) => d.id),
    ownedCharacters: ['street'],
    ownedDances: ['groove'],
    avatar: { ...DEFAULT_LOOK },
    customDecks: [],
    selectedDeckId: 'espaco',
    story: { unlocked: 1, best: {} },
    settings: { music: 0.5, sfx: 0.7 },
  };
}

function load(): Profile {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { ...defaultProfile(), ...JSON.parse(raw) };
  } catch {
    /* armazenamento indisponível: segue com o padrão */
  }
  return defaultProfile();
}

let profile: Profile = load();
const listeners = new Set<() => void>();
const changeHooks = new Set<(p: Profile) => void>();

export function getProfile() {
  return profile;
}

export function setProfile(update: Partial<Profile> | ((p: Profile) => Partial<Profile>)) {
  const patch = typeof update === 'function' ? update(profile) : update;
  profile = { ...profile, ...patch };
  try {
    localStorage.setItem(KEY, JSON.stringify(profile));
  } catch {
    /* ignora */
  }
  listeners.forEach((l) => l());
  changeHooks.forEach((h) => h(profile));
}

/** Usado pela sincronização com o Supabase. */
export function onProfileChange(fn: (p: Profile) => void) {
  changeHooks.add(fn);
  return () => changeHooks.delete(fn);
}

export function useProfile(): Profile {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => profile,
  );
}

export function allDecks(p: Profile): Deck[] {
  return [...OFFICIAL_DECKS, ...p.customDecks];
}

export function ownsDeck(p: Profile, deck: Deck) {
  return deck.price === 0 || !deck.official || p.ownedDecks.includes(deck.id);
}

export function playableDecks(p: Profile): Deck[] {
  return allDecks(p).filter((d) => ownsDeck(p, d));
}
