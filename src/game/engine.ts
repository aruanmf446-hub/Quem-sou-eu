import type {
  ChatMessage,
  Deck,
  GameSettings,
  GameState,
  PlayerInfo,
  PlayerState,
  PublicState,
} from './types';

export type Rng = () => number;

export const MIN_PLAYERS = 4;
export const MAX_PLAYERS = 10;
export const DEFAULT_SETTINGS: GameSettings = { cardsPerPlayer: 3, turnSeconds: 20 };

export function shuffle<T>(items: T[], rng: Rng = Math.random): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** Quantos jogadores um deck comporta com N cartas por jogador. */
export function maxPlayersForDeck(deck: Deck, cardsPerPlayer = DEFAULT_SETTINGS.cardsPerPlayer): number {
  return Math.min(MAX_PLAYERS, Math.floor(deck.cards.length / cardsPerPlayer));
}

export function createGame(
  deck: Deck,
  players: PlayerInfo[],
  settings: GameSettings = DEFAULT_SETTINGS,
  rng: Rng = Math.random,
  now = Date.now(),
): GameState {
  if (players.length < 2) throw new Error('São necessários pelo menos 2 jogadores');
  const needed = players.length * settings.cardsPerPlayer;
  if (deck.cards.length < needed) {
    throw new Error(`O deck tem ${deck.cards.length} cartas, mas são necessárias ${needed}`);
  }
  const pool = shuffle(deck.cards.map((c) => c.id), rng);
  const seated: PlayerState[] = shuffle(players, rng).map((p, i) => ({
    ...p,
    hand: pool.slice(i * settings.cardsPerPlayer, (i + 1) * settings.cardsPerPlayer),
    eliminated: false,
  }));
  return {
    deck,
    players: seated,
    settings,
    turnIndex: 0,
    round: 1,
    phase: 'playing',
    discarded: [],
    missed: [],
    log: [{ kind: 'round', round: 1 }],
    chat: [],
    winnerId: null,
    turnEndsAt: now + settings.turnSeconds * 1000,
  };
}

export function currentPlayer<P extends { id: string }>(state: { players: P[]; turnIndex: number }): P {
  return state.players[state.turnIndex];
}

/** Personagens que ainda podem ser chutados (nem descartados nem já errados). */
export function openCards(state: Pick<GameState, 'deck' | 'discarded' | 'missed'>): string[] {
  const closed = new Set([...state.discarded, ...state.missed]);
  return state.deck.cards.map((c) => c.id).filter((id) => !closed.has(id));
}

/**
 * Regra de vitória: vence quem sobrar sozinho, ou quem tiver pelo menos
 * tantas cartas quanto todos os outros juntos E mais do que cada adversário.
 */
export function findWinner(players: { id: string; hand?: string[]; handCount?: number }[]): string | null {
  const counts = players.map((p) => ({ id: p.id, n: p.hand ? p.hand.length : (p.handCount ?? 0) }));
  const alive = counts.filter((c) => c.n > 0);
  if (alive.length === 1) return alive[0].id;
  if (alive.length === 0) return null;
  const total = alive.reduce((s, c) => s + c.n, 0);
  for (const c of alive) {
    const others = total - c.n;
    const bestOther = Math.max(...alive.filter((o) => o.id !== c.id).map((o) => o.n));
    if (c.n >= others && c.n > bestOther) return c.id;
  }
  return null;
}

function advanceTurn(state: GameState, now: number) {
  const n = state.players.length;
  let next = state.turnIndex;
  for (let step = 1; step <= n; step++) {
    const idx = (state.turnIndex + step) % n;
    if (!state.players[idx].eliminated) {
      next = idx;
      // Passou pelo fim da roda: nova rodada.
      if (idx <= state.turnIndex) {
        state.round += 1;
        state.log.push({ kind: 'round', round: state.round });
      }
      break;
    }
  }
  state.turnIndex = next;
  state.turnEndsAt = now + state.settings.turnSeconds * 1000;
}

function checkEnd(state: GameState): boolean {
  const winner = findWinner(state.players);
  if (winner) {
    state.phase = 'finished';
    state.winnerId = winner;
    state.log.push({ kind: 'win', round: state.round, player: winner });
    return true;
  }
  return false;
}

export class GameError extends Error {}

/** Aplica um chute. Retorna um novo estado (o original não é alterado). */
export function applyGuess(prev: GameState, playerId: string, cardId: string, now = Date.now()): GameState {
  if (prev.phase !== 'playing') throw new GameError('A partida já acabou');
  const me = currentPlayer(prev);
  if (me.id !== playerId) throw new GameError('Não é a sua vez');
  if (!prev.deck.cards.some((c) => c.id === cardId)) throw new GameError('Carta desconhecida');
  if (prev.discarded.includes(cardId) || prev.missed.includes(cardId)) {
    throw new GameError('Esse personagem já saiu da mesa');
  }
  if (me.hand.includes(cardId)) throw new GameError('Esse personagem é seu');

  const state: GameState = structuredClone(prev);
  const holder = state.players.find((p) => p.hand.includes(cardId));
  if (holder) {
    holder.hand = holder.hand.filter((c) => c !== cardId);
    state.discarded.push(cardId);
    state.log.push({ kind: 'hit', round: state.round, by: playerId, target: holder.id, cardId });
    if (holder.hand.length === 0) {
      holder.eliminated = true;
      state.log.push({ kind: 'eliminated', round: state.round, player: holder.id });
    }
  } else {
    state.missed.push(cardId);
    state.log.push({ kind: 'miss', round: state.round, by: playerId, cardId });
  }
  if (!checkEnd(state)) advanceTurn(state, now);
  return state;
}

/** O tempo do turno acabou: passa a vez sem punição. */
export function applyTimeout(prev: GameState, now = Date.now()): GameState {
  if (prev.phase !== 'playing') return prev;
  const state: GameState = structuredClone(prev);
  state.log.push({ kind: 'timeout', round: state.round, by: currentPlayer(state).id });
  advanceTurn(state, now);
  return state;
}

/** Um jogador saiu da partida: as cartas dele são descartadas. */
export function applyLeave(prev: GameState, playerId: string, now = Date.now()): GameState {
  const state: GameState = structuredClone(prev);
  const p = state.players.find((x) => x.id === playerId);
  if (!p || p.eliminated || state.phase !== 'playing') return prev;
  state.discarded.push(...p.hand);
  p.hand = [];
  p.eliminated = true;
  state.log.push({ kind: 'eliminated', round: state.round, player: p.id });
  const wasTurn = currentPlayer(state).id === playerId;
  if (!checkEnd(state) && wasTurn) advanceTurn(state, now);
  return state;
}

export function addChat(prev: GameState, msg: ChatMessage): GameState {
  return { ...prev, chat: [...prev.chat, msg].slice(-100) };
}

export function toPublic(state: GameState): PublicState {
  return {
    ...state,
    players: state.players.map(({ hand, ...rest }) => ({ ...rest, handCount: hand.length })),
  };
}

/** Moedas ganhas no fim da partida. */
export function coinsForResult(state: PublicState | GameState, playerId: string): number {
  const hits = state.log.filter((l) => l.kind === 'hit' && l.by === playerId).length;
  const won = state.winnerId === playerId;
  return 10 + hits * 5 + (won ? 50 : 0);
}
