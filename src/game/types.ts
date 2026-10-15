export interface CharacterCard {
  id: string;
  name: string;
  /** Emoji usado como placeholder quando não há imagem. */
  emoji: string;
  /** Caminho relativo no bucket R2 (ex.: "decks/espaco/astronauta.png") ou URL absoluta. */
  image?: string;
}

export interface Deck {
  id: string;
  name: string;
  description: string;
  cards: CharacterCard[];
  /** Preço em moedas. 0 = grátis. */
  price: number;
  /** Deck oficial (vendido/distribuído pelo jogo) ou criado por jogador. */
  official: boolean;
  author?: string;
  cover?: string;
}

export interface Skin {
  body: string;
  visor: string;
  hat: string;
}

export interface PlayerInfo {
  id: string;
  name: string;
  isBot: boolean;
  skin: Skin;
}

export interface PlayerState extends PlayerInfo {
  hand: string[];
  eliminated: boolean;
}

export type LogEntry =
  | { kind: 'hit'; round: number; by: string; target: string; cardId: string }
  | { kind: 'miss'; round: number; by: string; cardId: string }
  | { kind: 'timeout'; round: number; by: string }
  | { kind: 'eliminated'; round: number; player: string }
  | { kind: 'round'; round: number }
  | { kind: 'win'; round: number; player: string };

export interface ChatMessage {
  id: string;
  from: string;
  text: string;
  round: number;
  at: number;
}

export interface GameSettings {
  cardsPerPlayer: number;
  turnSeconds: number;
}

export interface GameState {
  deck: Deck;
  players: PlayerState[];
  settings: GameSettings;
  turnIndex: number;
  round: number;
  phase: 'playing' | 'finished';
  /** Cartas acertadas e removidas do jogo. */
  discarded: string[];
  /** Personagens chutados que ninguém tinha (informação pública). */
  missed: string[];
  log: LogEntry[];
  chat: ChatMessage[];
  winnerId: string | null;
  turnEndsAt: number;
}

export interface PublicPlayer extends PlayerInfo {
  handCount: number;
  eliminated: boolean;
}

/** Estado sem as mãos dos jogadores — é o que vai pela rede. */
export interface PublicState extends Omit<GameState, 'players'> {
  players: PublicPlayer[];
}
