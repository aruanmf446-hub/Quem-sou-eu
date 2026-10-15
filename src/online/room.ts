import type { RealtimeChannel } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { makeBots } from '../game/bots';
import { MAX_PLAYERS, maxPlayersForDeck } from '../game/engine';
import type { Deck, PlayerInfo, PublicState } from '../game/types';
import { GuestMatch, HostMatch, type MatchController } from './match';

export interface LobbyMember extends PlayerInfo {
  isHost: boolean;
}

export interface LobbyState {
  code: string;
  members: LobbyMember[];
  isHost: boolean;
  status: 'lobby' | 'playing' | 'closed';
  deckName?: string;
  message?: string;
}

const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

function makeCode() {
  return Array.from({ length: 5 }, () => CODE_CHARS[Math.floor(Math.random() * CODE_CHARS.length)]).join('');
}

/**
 * Sala online via Supabase Realtime.
 * Presence = quem está na sala. Broadcast = estado da partida, mãos e ações.
 * O anfitrião é a autoridade da partida (roda as regras e os bots).
 */
export class Room {
  private channel: RealtimeChannel;
  private lobby: LobbyState;
  private listeners = new Set<(l: LobbyState) => void>();
  private host: HostMatch | null = null;
  private guest: GuestMatch | null = null;
  private onMatch: ((m: MatchController) => void) | null = null;
  private leaveTimers = new Map<string, number>();

  private constructor(private me: PlayerInfo, code: string, isHost: boolean) {
    if (!supabase) throw new Error('Online não configurado');
    this.lobby = { code, members: [], isHost, status: 'lobby' };
    this.channel = supabase.channel(`room:${code}`, {
      config: { presence: { key: me.id }, broadcast: { self: false, ack: false } },
    });
    this.wire();
  }

  static async create(me: PlayerInfo) {
    const room = new Room(me, makeCode(), true);
    await room.join();
    return room;
  }

  static async join(me: PlayerInfo, code: string) {
    const room = new Room(me, code.trim().toUpperCase(), false);
    await room.join();
    return room;
  }

  private join() {
    return new Promise<void>((resolve, reject) => {
      const timeout = window.setTimeout(() => reject(new Error('Não foi possível conectar à sala')), 10000);
      this.channel.subscribe(async (status) => {
        if (status === 'SUBSCRIBED') {
          window.clearTimeout(timeout);
          await this.channel.track({ ...this.me, isHost: this.lobby.isHost });
          resolve();
        } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
          window.clearTimeout(timeout);
          reject(new Error('Erro de conexão com a sala'));
        }
      });
    });
  }

  private wire() {
    this.channel.on('presence', { event: 'sync' }, () => {
      const presence = this.channel.presenceState<LobbyMember>();
      const members = Object.values(presence).map((metas) => metas[0]).filter(Boolean);
      const prevIds = new Set(this.lobby.members.map((m) => m.id));
      const ids = new Set(members.map((m) => m.id));
      this.lobby = { ...this.lobby, members };

      if (!this.lobby.isHost && this.lobby.members.length > 0 && !members.some((m) => m.isHost)) {
        this.lobby = { ...this.lobby, status: 'closed', message: 'O anfitrião saiu da sala.' };
      }
      if (this.host) {
        // Quem caiu tem 10s para voltar antes de ser removido da partida.
        for (const id of prevIds) {
          if (!ids.has(id) && !this.leaveTimers.has(id)) {
            this.leaveTimers.set(id, window.setTimeout(() => this.host?.handleLeave(id), 10000));
          }
        }
        for (const id of ids) {
          const t = this.leaveTimers.get(id);
          if (t) {
            window.clearTimeout(t);
            this.leaveTimers.delete(id);
          }
          if (!prevIds.has(id)) this.host.republish();
        }
      }
      this.emit();
    });

    this.channel.on('broadcast', { event: 'start' }, ({ payload }) => {
      if (this.lobby.isHost) return;
      this.lobby = { ...this.lobby, status: 'playing', deckName: payload.deckName };
      this.guest = new GuestMatch(this.me.id, {
        guess: (cardId) => this.send('action', { from: this.me.id, type: 'guess', cardId }),
        chat: (text) => this.send('action', { from: this.me.id, type: 'chat', text }),
        leave: () => this.close(),
      });
      this.onMatch?.(this.guest);
      this.emit();
    });

    this.channel.on('broadcast', { event: 'state' }, ({ payload }) => {
      this.guest?.receiveState(payload.state as PublicState);
    });

    this.channel.on('broadcast', { event: 'hand' }, ({ payload }) => {
      if (payload.to === this.me.id) this.guest?.receiveHand(payload.hand as string[]);
    });

    this.channel.on('broadcast', { event: 'action' }, ({ payload }) => {
      if (!this.host) return;
      if (payload.type === 'guess') this.host.handleGuess(payload.from, payload.cardId);
      if (payload.type === 'chat') this.host.handleChat(payload.from, String(payload.text ?? ''));
    });
  }

  private send(event: string, payload: Record<string, unknown>) {
    void this.channel.send({ type: 'broadcast', event, payload });
  }

  private emit() {
    const l = { ...this.lobby };
    this.listeners.forEach((fn) => fn(l));
  }

  subscribe(fn: (l: LobbyState) => void) {
    this.listeners.add(fn);
    fn({ ...this.lobby });
    return () => {
      this.listeners.delete(fn);
    };
  }

  onMatchStart(fn: (m: MatchController) => void) {
    this.onMatch = fn;
  }

  /** Só o anfitrião: completa com bots até `totalPlayers` e começa. */
  start(deck: Deck, totalPlayers: number) {
    if (!this.lobby.isHost) return;
    const humans: PlayerInfo[] = this.lobby.members.map(({ isHost: _h, ...p }) => p);
    const limit = Math.min(MAX_PLAYERS, maxPlayersForDeck(deck));
    if (humans.length > limit) throw new Error(`Esse deck comporta no máximo ${limit} jogadores`);
    const target = Math.max(humans.length, Math.min(totalPlayers, limit));
    const bots = makeBots(target - humans.length, humans.map((h) => h.name));
    this.send('start', { deckName: deck.name });
    this.lobby = { ...this.lobby, status: 'playing', deckName: deck.name };
    // Os convidados precisam de um instante para montar a tela antes do primeiro estado.
    window.setTimeout(() => {
      this.host = new HostMatch(deck, [...humans, ...bots], this.me.id, {
        publish: (state, hands) => {
          this.send('state', { state });
          for (const [to, hand] of Object.entries(hands)) if (to !== this.me.id) this.send('hand', { to, hand });
        },
      });
      this.onMatch?.(this.host);
      this.emit();
    }, 300);
  }

  close() {
    this.host?.leave();
    this.leaveTimers.forEach((t) => window.clearTimeout(t));
    void this.channel.untrack();
    void supabase?.removeChannel(this.channel);
    this.listeners.clear();
  }
}
