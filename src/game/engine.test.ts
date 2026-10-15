import { describe, expect, it } from 'vitest';
import {
  applyGuess,
  applyLeave,
  applyTimeout,
  createGame,
  findWinner,
  GameError,
  openCards,
  toPublic,
} from './engine';
import { botChooseCard } from './bots';
import type { Deck, GameState, PlayerInfo } from './types';

const deck: Deck = {
  id: 'test',
  name: 'Teste',
  description: '',
  price: 0,
  official: true,
  cards: Array.from({ length: 15 }, (_, i) => ({ id: `c${i}`, name: `Carta ${i}`, emoji: '🃏' })),
};

const skin = { body: '#f00', visor: '#0ff', hat: 'none' };
const players: PlayerInfo[] = ['a', 'b', 'c', 'd'].map((id) => ({ id, name: id, isBot: false, skin }));

function seeded(seed = 1) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/** Monta um estado com mãos conhecidas. */
function fixed(hands: Record<string, string[]>): GameState {
  const g = createGame(deck, players, { cardsPerPlayer: 3, turnSeconds: 20 }, seeded(), 0);
  g.players = players.map((p) => ({ ...p, hand: hands[p.id] ?? [], eliminated: (hands[p.id] ?? []).length === 0 }));
  g.turnIndex = 0;
  return g;
}

describe('findWinner', () => {
  it('quem sobrar sozinho vence', () => {
    expect(findWinner([{ id: 'a', hand: ['x'] }, { id: 'b', hand: [] }])).toBe('a');
  });
  it('3 contra 0 vence', () => {
    expect(findWinner([{ id: 'a', handCount: 3 }, { id: 'b', handCount: 0 }])).toBe('a');
  });
  it('2 contra 1+1 vence', () => {
    expect(
      findWinner([
        { id: 'a', handCount: 1 },
        { id: 'b', handCount: 2 },
        { id: 'c', handCount: 1 },
      ]),
    ).toBe('b');
  });
  it('empate não decide', () => {
    expect(findWinner([{ id: 'a', handCount: 1 }, { id: 'b', handCount: 1 }])).toBeNull();
    expect(findWinner([{ id: 'a', handCount: 2 }, { id: 'b', handCount: 2 }, { id: 'c', handCount: 1 }])).toBeNull();
  });
  it('início da partida não tem vencedor', () => {
    expect(findWinner(players.map((p) => ({ id: p.id, handCount: 3 })))).toBeNull();
  });
});

describe('createGame', () => {
  it('distribui 3 cartas diferentes para cada um', () => {
    const g = createGame(deck, players, undefined, seeded(7));
    const all = g.players.flatMap((p) => p.hand);
    expect(all).toHaveLength(12);
    expect(new Set(all).size).toBe(12);
  });
  it('recusa deck pequeno demais', () => {
    expect(() => createGame({ ...deck, cards: deck.cards.slice(0, 5) }, players)).toThrow();
  });
});

describe('applyGuess', () => {
  it('acerto descarta a carta do outro jogador e passa a vez', () => {
    const g = fixed({ a: ['c0', 'c1', 'c2'], b: ['c3', 'c4', 'c5'], c: ['c6', 'c7', 'c8'], d: ['c9', 'c10', 'c11'] });
    const next = applyGuess(g, 'a', 'c4', 0);
    expect(next.players[1].hand).toEqual(['c3', 'c5']);
    expect(next.discarded).toEqual(['c4']);
    expect(next.turnIndex).toBe(1);
    expect(g.players[1].hand).toHaveLength(3); // imutável
  });
  it('erro só passa a vez e marca o personagem', () => {
    const g = fixed({ a: ['c0', 'c1', 'c2'], b: ['c3', 'c4', 'c5'], c: ['c6', 'c7', 'c8'], d: ['c9', 'c10', 'c11'] });
    const next = applyGuess(g, 'a', 'c14', 0);
    expect(next.missed).toEqual(['c14']);
    expect(next.players.every((p) => p.hand.length === 3)).toBe(true);
    expect(next.turnIndex).toBe(1);
  });
  it('valida turno, cartas próprias e repetidas', () => {
    const g = fixed({ a: ['c0', 'c1', 'c2'], b: ['c3', 'c4', 'c5'], c: ['c6', 'c7', 'c8'], d: ['c9', 'c10', 'c11'] });
    expect(() => applyGuess(g, 'b', 'c0')).toThrow(GameError);
    expect(() => applyGuess(g, 'a', 'c0')).toThrow(GameError);
    const g2 = applyGuess(g, 'a', 'c14', 0);
    g2.turnIndex = 0;
    expect(() => applyGuess(g2, 'a', 'c14')).toThrow(GameError);
  });
  it('perder a última carta elimina e o turno pula o eliminado', () => {
    const g = fixed({ a: ['c0', 'c1', 'c2'], b: ['c3'], c: ['c6', 'c7'], d: ['c9', 'c10'] });
    const next = applyGuess(g, 'a', 'c3', 0);
    expect(next.players[1].eliminated).toBe(true);
    expect(next.turnIndex).toBe(2);
  });
  it('conta rodadas quando a vez volta ao primeiro', () => {
    let g = fixed({ a: ['c0', 'c1', 'c2'], b: ['c3', 'c4', 'c5'], c: ['c6', 'c7', 'c8'], d: ['c9', 'c10', 'c11'] });
    g = applyTimeout(g, 0);
    g = applyTimeout(g, 0);
    g = applyTimeout(g, 0);
    expect(g.round).toBe(1);
    g = applyTimeout(g, 0);
    expect(g.round).toBe(2);
    expect(g.turnIndex).toBe(0);
  });
  it('termina quando alguém domina a mesa', () => {
    const g = fixed({ a: ['c0', 'c1'], b: ['c3'], c: ['c6'], d: [] });
    const next = applyGuess(g, 'a', 'c3', 0);
    expect(next.phase).toBe('finished');
    expect(next.winnerId).toBe('a');
  });
});

describe('applyLeave', () => {
  it('descarta as cartas de quem sai', () => {
    const g = fixed({ a: ['c0', 'c1', 'c2'], b: ['c3', 'c4', 'c5'], c: ['c6', 'c7', 'c8'], d: ['c9', 'c10', 'c11'] });
    const next = applyLeave(g, 'a', 0);
    expect(next.players[0].eliminated).toBe(true);
    expect(next.discarded).toEqual(['c0', 'c1', 'c2']);
    expect(next.turnIndex).toBe(1);
  });
});

describe('simulação com bots', () => {
  it('toda partida termina com um vencedor', () => {
    for (let seed = 1; seed < 200; seed++) {
      const rng = seeded(seed);
      let g = createGame(deck, players, undefined, rng, 0);
      let guard = 0;
      while (g.phase === 'playing' && guard++ < 500) {
        const me = g.players[g.turnIndex];
        const card = botChooseCard(g, me.id, rng);
        g = card ? applyGuess(g, me.id, card, 0) : applyTimeout(g, 0);
      }
      expect(g.phase).toBe('finished');
      expect(g.winnerId).not.toBeNull();
    }
  });
});

describe('toPublic', () => {
  it('não vaza as mãos', () => {
    const g = createGame(deck, players, undefined, seeded(3));
    const pub = toPublic(g);
    expect(JSON.stringify(pub.players)).not.toContain('"hand"');
    expect(pub.players[0].handCount).toBe(3);
    expect(openCards(pub)).toHaveLength(15);
  });
});
