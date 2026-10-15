import { openCards, type Rng } from './engine';
import type { Deck, GameState, PlayerInfo, Skin } from './types';
import { SKIN_COLORS, HATS } from '../data/skins';

const BOT_NAMES = [
  'Bolinha', 'Tico', 'Juju', 'Zeca', 'Nina', 'Pipoca', 'Dudu', 'Lulu', 'Biscoito',
  'Fumaça', 'Kiko', 'Mel', 'Gugu', 'Tatá', 'Paçoca', 'Xuxu',
];

export function makeBots(count: number, takenNames: string[], rng: Rng = Math.random): PlayerInfo[] {
  const names = BOT_NAMES.filter((n) => !takenNames.includes(n));
  const bots: PlayerInfo[] = [];
  for (let i = 0; i < count; i++) {
    const idx = Math.floor(rng() * names.length);
    const name = names.splice(idx, 1)[0] ?? `Bot ${i + 1}`;
    const skin: Skin = {
      body: SKIN_COLORS[Math.floor(rng() * SKIN_COLORS.length)].color,
      visor: '#9fe7ff',
      hat: rng() < 0.5 ? 'none' : HATS[Math.floor(rng() * HATS.length)].id,
    };
    bots.push({ id: `bot-${i}-${Math.floor(rng() * 1e6)}`, name, isBot: true, skin });
  }
  return bots;
}

/** O bot só sabe a própria mão e o que é público, então chuta entre o que sobrou. */
export function botChooseCard(state: GameState, botId: string, rng: Rng = Math.random): string | null {
  const me = state.players.find((p) => p.id === botId);
  if (!me) return null;
  const options = openCards(state).filter((id) => !me.hand.includes(id));
  if (options.length === 0) return null;
  return options[Math.floor(rng() * options.length)];
}

const BLUFFS = [
  'Eu não tenho {c}, juro 😇',
  'Quem chutar {c} vai se dar mal...',
  'Hmm, alguém aqui tá com cara de {c}',
  'Tô tranquilo, ninguém vai achar os meus',
  'Aposto que {p} tem {c}!',
  '{p} tá muito quietinho... suspeito 👀',
  'Sério, {c} não tá comigo',
  'Essa rodada é minha!',
  'kkkkk',
  'Vocês nunca vão adivinhar',
];

export function botChatLine(state: GameState, botId: string, deck: Deck, rng: Rng = Math.random): string {
  const open = openCards(state);
  const cardId = open[Math.floor(rng() * open.length)];
  const card = deck.cards.find((c) => c.id === cardId);
  const others = state.players.filter((p) => p.id !== botId && !p.eliminated);
  const other = others[Math.floor(rng() * others.length)];
  return BLUFFS[Math.floor(rng() * BLUFFS.length)]
    .replace('{c}', card ? card.name : 'esse aí')
    .replace('{p}', other ? other.name : 'alguém');
}
