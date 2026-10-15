import {
  addChat,
  applyGuess,
  applyLeave,
  applyTimeout,
  currentPlayer,
  DEFAULT_SETTINGS,
  createGame,
  GameError,
  toPublic,
} from '../game/engine';
import { botChatLine, botChooseCard } from '../game/bots';
import type { ChatMessage, Deck, GameSettings, GameState, PlayerInfo, PublicState } from '../game/types';

export interface MatchSnapshot {
  state: PublicState;
  myId: string;
  myHand: string[];
  error?: string;
}

export interface MatchController {
  subscribe(fn: (s: MatchSnapshot) => void): () => void;
  guess(cardId: string): void;
  chat(text: string): void;
  leave(): void;
}

export type HostTransport = {
  /** Envia o estado público e a mão privada de cada jogador remoto. */
  publish(state: PublicState, hands: Record<string, string[]>): void;
};

let msgSeq = 0;
export function chatMessage(from: string, text: string, round: number): ChatMessage {
  return { id: `${Date.now()}-${msgSeq++}-${Math.random().toString(36).slice(2, 6)}`, from, text: text.slice(0, 140), round, at: Date.now() };
}

/**
 * Roda a partida de verdade: regras, bots e cronômetro.
 * Offline é usado direto; online, o anfitrião roda isto e transmite o estado.
 */
export class HostMatch implements MatchController {
  private state: GameState;
  private listeners = new Set<(s: MatchSnapshot) => void>();
  private ticker: number;
  private botTimer: number | null = null;
  private botTurnKey = '';
  private lastRound = 0;
  private stopped = false;
  private lastError: string | undefined;

  constructor(
    deck: Deck,
    players: PlayerInfo[],
    private myId: string,
    private transport?: HostTransport,
    settings: GameSettings = DEFAULT_SETTINGS,
  ) {
    this.state = createGame(deck, players, settings);
    this.ticker = window.setInterval(() => this.tick(), 400);
    this.emit();
  }

  subscribe(fn: (s: MatchSnapshot) => void) {
    this.listeners.add(fn);
    fn(this.snapshot());
    return () => {
      this.listeners.delete(fn);
    };
  }

  private snapshot(): MatchSnapshot {
    const me = this.state.players.find((p) => p.id === this.myId);
    return { state: toPublic(this.state), myId: this.myId, myHand: me ? me.hand : [], error: this.lastError };
  }

  private emit() {
    const snap = this.snapshot();
    this.listeners.forEach((l) => l(snap));
    if (this.transport) {
      const hands: Record<string, string[]> = {};
      for (const p of this.state.players) if (!p.isBot) hands[p.id] = p.hand;
      this.transport.publish(snap.state, hands);
    }
    this.lastError = undefined;
    this.onStateChanged();
  }

  private onStateChanged() {
    if (this.state.phase === 'finished') return this.stop(false);
    if (this.state.round !== this.lastRound) {
      this.lastRound = this.state.round;
      this.scheduleBotChat();
    }
    const cur = currentPlayer(this.state);
    const key = `${this.state.round}:${this.state.turnIndex}`;
    if (cur.isBot && this.botTurnKey !== key) {
      this.botTurnKey = key;
      const delay = 1200 + Math.random() * 1600;
      this.botTimer = window.setTimeout(() => {
        if (this.stopped || currentPlayer(this.state).id !== cur.id) return;
        const card = botChooseCard(this.state, cur.id);
        this.state = card ? applyGuess(this.state, cur.id, card) : applyTimeout(this.state);
        this.emit();
      }, delay);
    }
  }

  private scheduleBotChat() {
    for (const bot of this.state.players.filter((p) => p.isBot && !p.eliminated)) {
      if (Math.random() > 0.35) continue;
      window.setTimeout(() => {
        if (this.stopped) return;
        const line = botChatLine(this.state, bot.id, this.state.deck);
        this.state = addChat(this.state, chatMessage(bot.id, line, this.state.round));
        this.emit();
      }, 800 + Math.random() * 6000);
    }
  }

  private tick() {
    if (this.stopped || this.state.phase !== 'playing') return;
    const cur = currentPlayer(this.state);
    // Bots têm uma margem extra para não estourar o tempo por causa do atraso simulado.
    const grace = cur.isBot ? 5000 : 0;
    if (Date.now() > this.state.turnEndsAt + grace) {
      this.state = applyTimeout(this.state);
      this.emit();
    }
  }

  /** Ação vinda de qualquer jogador humano (local ou remoto). */
  handleGuess(from: string, cardId: string) {
    try {
      this.state = applyGuess(this.state, from, cardId);
    } catch (e) {
      if (!(e instanceof GameError)) throw e;
      if (from === this.myId) this.lastError = e.message;
    }
    this.emit();
  }

  handleChat(from: string, text: string) {
    const clean = text.trim();
    if (!clean || !this.state.players.some((p) => p.id === from)) return;
    this.state = addChat(this.state, chatMessage(from, clean, this.state.round));
    this.emit();
  }

  handleLeave(playerId: string) {
    this.state = applyLeave(this.state, playerId);
    this.emit();
  }

  /** Reenvia o estado (ex.: alguém reconectou). */
  republish() {
    this.emit();
  }

  guess(cardId: string) {
    this.handleGuess(this.myId, cardId);
  }

  chat(text: string) {
    this.handleChat(this.myId, text);
  }

  leave() {
    this.stop(true);
  }

  private stop(clearListeners: boolean) {
    this.stopped = true;
    window.clearInterval(this.ticker);
    if (this.botTimer) window.clearTimeout(this.botTimer);
    if (clearListeners) this.listeners.clear();
  }
}

/** Lado do convidado: só recebe o estado e envia ações para o anfitrião. */
export class GuestMatch implements MatchController {
  private listeners = new Set<(s: MatchSnapshot) => void>();
  private last: MatchSnapshot | null = null;
  private hand: string[] = [];

  constructor(
    private myId: string,
    private send: { guess(cardId: string): void; chat(text: string): void; leave(): void },
  ) {}

  receiveState(state: PublicState) {
    this.last = { state, myId: this.myId, myHand: this.hand };
    this.listeners.forEach((l) => l(this.last!));
  }

  receiveHand(hand: string[]) {
    this.hand = hand;
    if (this.last) this.receiveState(this.last.state);
  }

  subscribe(fn: (s: MatchSnapshot) => void) {
    this.listeners.add(fn);
    if (this.last) fn(this.last);
    return () => {
      this.listeners.delete(fn);
    };
  }

  guess(cardId: string) {
    this.send.guess(cardId);
  }

  chat(text: string) {
    if (text.trim()) this.send.chat(text.trim());
  }

  leave() {
    this.send.leave();
    this.listeners.clear();
  }
}
