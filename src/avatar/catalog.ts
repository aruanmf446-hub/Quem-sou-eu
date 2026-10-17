import { DEFAULT_BODY, DEFAULT_FACE, type AvatarConfig, type Slot } from './config';

export type Rarity = 'comum' | 'raro' | 'épico' | 'lendário';

export interface CatalogItem {
  id: string;
  slot: Slot;
  name: string;
  price: number;
  rarity: Rarity;
  /** Pacote (personagem legado) que libera o item ao ser adquirido. */
  bundle?: 'street' | 'striker' | 'night-clown';
  /** Partes recoloríveis e cor padrão. */
  tints?: Record<string, string>;
  /** Cor de cabelo sugerida ao escolher este estilo. */
  suggestHair?: string;
  tags?: string[];
}

export const SLOT_LABELS: Record<Slot, string> = {
  hair: 'Cabelo', brows: 'Sobrancelhas', beard: 'Barba', top: 'Parte de cima', bottom: 'Parte de baixo',
  socks: 'Meias', shoes: 'Calçados', headwear: 'Cabeça', eyewear: 'Óculos', neck: 'Pescoço', wrist: 'Pulso', bodyart: 'Arte corporal',
};

/** Slots que nunca ficam vazios (o corpo sempre aparece vestido). */
export const REQUIRED_SLOTS: Slot[] = ['top', 'bottom', 'shoes', 'brows'];

export const ITEMS: CatalogItem[] = [
  // Cabelo
  { id: 'hair_curly_fade', slot: 'hair', name: 'Cacheado degradê', price: 120, rarity: 'épico', bundle: 'striker', suggestHair: '#2b1d14' },
  { id: 'hair_buzz', slot: 'hair', name: 'Raspado', price: 0, rarity: 'comum' },
  { id: 'hair_afro', slot: 'hair', name: 'Black power', price: 140, rarity: 'épico' },
  { id: 'hair_bun', slot: 'hair', name: 'Coque alto', price: 0, rarity: 'raro', bundle: 'street' },
  { id: 'hair_clown', slot: 'hair', name: 'Tufos da meia-noite', price: 90, rarity: 'raro', bundle: 'night-clown', suggestHair: '#d9481c' },
  // Sobrancelhas
  { id: 'brows_natural', slot: 'brows', name: 'Natural', price: 0, rarity: 'comum' },
  { id: 'brows_thick', slot: 'brows', name: 'Marcante', price: 0, rarity: 'comum' },
  { id: 'brows_thin', slot: 'brows', name: 'Fina', price: 0, rarity: 'comum' },
  { id: 'brows_arched', slot: 'brows', name: 'Arqueada', price: 0, rarity: 'comum' },
  // Barba
  { id: 'beard_stubble', slot: 'beard', name: 'Por fazer', price: 0, rarity: 'comum' },
  { id: 'beard_goatee', slot: 'beard', name: 'Cavanhaque', price: 0, rarity: 'comum' },
  { id: 'beard_chinstrap', slot: 'beard', name: 'Contorno', price: 0, rarity: 'comum' },
  { id: 'beard_full', slot: 'beard', name: 'Cheia', price: 0, rarity: 'comum' },
  // Parte de cima
  { id: 'top_tee', slot: 'top', name: 'Camiseta essencial', price: 0, rarity: 'comum', tints: { main: '#f2f2ee' } },
  { id: 'top_tank', slot: 'top', name: 'Regata de treino', price: 0, rarity: 'comum', tints: { main: '#2d3442' } },
  { id: 'top_jersey_10', slot: 'top', name: 'Camisa 10 · titular', price: 120, rarity: 'épico', bundle: 'striker' },
  { id: 'top_jersey_away', slot: 'top', name: 'Camisa 10 · reserva', price: 150, rarity: 'épico' },
  { id: 'top_track_jacket', slot: 'top', name: 'Jaqueta Nova', price: 0, rarity: 'raro', bundle: 'street', tints: { main: '#7c5ce0' } },
  { id: 'top_clown_tunic', slot: 'top', name: 'Túnica da meia-noite', price: 160, rarity: 'lendário', bundle: 'night-clown' },
  // Parte de baixo
  { id: 'bottom_shorts', slot: 'bottom', name: 'Bermuda esportiva', price: 0, rarity: 'comum', tints: { main: '#262c3a' } },
  { id: 'bottom_shorts_10', slot: 'bottom', name: 'Calção Camisa 10', price: 80, rarity: 'raro', bundle: 'striker' },
  { id: 'bottom_joggers', slot: 'bottom', name: 'Calça jogger', price: 0, rarity: 'comum', bundle: 'street', tints: { main: '#1e2230' } },
  { id: 'bottom_clown_pants', slot: 'bottom', name: 'Calça listrada da meia-noite', price: 110, rarity: 'épico', bundle: 'night-clown' },
  // Meias
  { id: 'socks_crew', slot: 'socks', name: 'Meia cano médio', price: 0, rarity: 'comum', tints: { main: '#f4f4f0' } },
  { id: 'socks_football', slot: 'socks', name: 'Meião liso', price: 30, rarity: 'comum', tints: { main: '#f1f1ec' } },
  { id: 'socks_football_10', slot: 'socks', name: 'Meião Camisa 10', price: 40, rarity: 'raro', bundle: 'striker' },
  // Calçados
  { id: 'shoes_sneakers', slot: 'shoes', name: 'Tênis casual', price: 0, rarity: 'comum', tints: { accent: '#7c5ce0' } },
  { id: 'shoes_cleats_10', slot: 'shoes', name: 'Chuteira Camisa 10', price: 110, rarity: 'épico', bundle: 'striker' },
  { id: 'shoes_hightops', slot: 'shoes', name: 'Tênis cano alto', price: 90, rarity: 'raro', bundle: 'street', tints: { main: '#1c1f29' } },
  { id: 'shoes_clown', slot: 'shoes', name: 'Sapato da meia-noite', price: 90, rarity: 'raro', bundle: 'night-clown' },
  // Acessórios
  { id: 'cap_snapback', slot: 'headwear', name: 'Boné aba reta', price: 60, rarity: 'raro', tints: { main: '#1d2433' } },
  { id: 'headband', slot: 'headwear', name: 'Faixa esportiva', price: 25, rarity: 'comum', tints: { main: '#f2f2ee' } },
  { id: 'glasses_sport', slot: 'eyewear', name: 'Óculos esportivos', price: 90, rarity: 'épico' },
  { id: 'glasses_round', slot: 'eyewear', name: 'Óculos redondos', price: 70, rarity: 'raro' },
  { id: 'chain_gold', slot: 'neck', name: 'Corrente dourada', price: 120, rarity: 'épico' },
  { id: 'wristband', slot: 'wrist', name: 'Munhequeira', price: 25, rarity: 'comum', tints: { main: '#1b8a46' } },
  { id: 'watch', slot: 'wrist', name: 'Relógio esportivo', price: 80, rarity: 'raro' },
  { id: 'tattoo_sleeve', slot: 'bodyart', name: 'Tatuagem geométrica', price: 100, rarity: 'épico', bundle: 'striker' },
  { id: 'facepaint_midnight', slot: 'bodyart', name: 'Pintura da meia-noite', price: 80, rarity: 'raro', bundle: 'night-clown' },
];

export const ITEM_BY_ID = new Map(ITEMS.map(i => [i.id, i]));

export interface Motion {
  id: string;
  name: string;
  subtitle: string;
  price: number;
  kind: 'dance' | 'celebration';
}

/** Danças (IDs legados preservados) e comemorações. Todas usam o mesmo esqueleto. */
export const MOTIONS: Motion[] = [
  { id: 'groove', name: 'No embalo', subtitle: 'Um groove para qualquer ocasião', price: 0, kind: 'dance' },
  { id: 'samba', name: 'Passinho do craque', subtitle: 'Leve o ritmo para o campo', price: 100, kind: 'dance' },
  { id: 'robot', name: 'Curto-circuito', subtitle: 'Precisão em cada movimento', price: 150, kind: 'dance' },
  { id: 'thriller', name: 'Baile da meia-noite', subtitle: 'A pista também tem seus monstros', price: 200, kind: 'dance' },
  { id: 'airplane', name: 'Aviãozinho', subtitle: 'Braços abertos, volta olímpica', price: 0, kind: 'celebration' },
  { id: 'heart', name: 'Coração para a torcida', subtitle: 'Gol dedicado a quem está na arquibancada', price: 80, kind: 'celebration' },
  { id: 'shh', name: 'Silêncio na arena', subtitle: 'Quem duvidou, agora escuta', price: 120, kind: 'celebration' },
  { id: 'flex', name: 'Muque do craque', subtitle: 'Força de quem decide', price: 100, kind: 'celebration' },
  { id: 'jump', name: 'Soco no ar', subtitle: 'Salto de quem marcou o gol do título', price: 150, kind: 'celebration' },
];
export const MOTION_BY_ID = new Map(MOTIONS.map(m => [m.id, m]));

export interface Bundle {
  id: 'street' | 'striker' | 'night-clown';
  name: string;
  subtitle: string;
  price: number;
  color: string;
  config: AvatarConfig;
}

const base = (over: Partial<AvatarConfig>): AvatarConfig => ({
  v: 2, body: { ...DEFAULT_BODY }, face: { ...DEFAULT_FACE }, skinTone: '#a8714e', eyeColor: '#3b2416', hairColor: '#24170f', hairTips: null,
  items: {}, tints: {}, dance: 'groove', celebration: 'airplane', ...over,
});

/** Visuais completos dos personagens originais (IDs e preços legados preservados). */
export const BUNDLES: Bundle[] = [
  {
    id: 'street', name: 'Nova', subtitle: 'Seu estilo começa aqui', price: 0, color: '#8463df',
    config: base({
      body: { ...DEFAULT_BODY, type: 1, muscle: .1, height: -.15 },
      face: { ...DEFAULT_FACE, shape: 'oval', shapeAmount: .5, lips: .35, eyeSize: .35, noseWidth: -.3, jaw: -.4 },
      skinTone: '#bd8058', eyeColor: '#4a2c1a', hairColor: '#1d1418',
      items: { hair: 'hair_bun', brows: 'brows_arched', beard: null, top: 'top_track_jacket', bottom: 'bottom_joggers', socks: 'socks_crew', shoes: 'shoes_hightops', headwear: null, eyewear: null, neck: null, wrist: null, bodyart: null },
      tints: { 'top_track_jacket:main': '#7c5ce0', 'bottom_joggers:main': '#1e2230', 'shoes_hightops:main': '#1c1f29' },
    }),
  },
  {
    id: 'striker', name: 'Camisa 10', subtitle: 'Talento de sobra, dentro e fora do campo', price: 150, color: '#efc51d',
    config: base({
      body: { ...DEFAULT_BODY, muscle: .25, legs: .1 },
      face: { ...DEFAULT_FACE, jaw: .35, chin: .2, cheekbones: .3 },
      skinTone: '#8d5a3b', eyeColor: '#3a2215', hairColor: '#2b1d14', hairTips: '#e2bf7a',
      items: { hair: 'hair_curly_fade', brows: 'brows_thick', beard: 'beard_goatee', top: 'top_jersey_10', bottom: 'bottom_shorts_10', socks: 'socks_football_10', shoes: 'shoes_cleats_10', headwear: null, eyewear: null, neck: null, wrist: null, bodyart: 'tattoo_sleeve' },
      dance: 'samba', celebration: 'airplane',
    }),
  },
  {
    id: 'night-clown', name: 'Riso da Meia-Noite', subtitle: 'Um espetáculo de arrepiar', price: 250, color: '#c2b9a4',
    config: base({
      body: { ...DEFAULT_BODY, muscle: -.2, weight: -.2, height: .25, legs: .3 },
      face: { ...DEFAULT_FACE, shape: 'triangle', shapeAmount: .6, cheekbones: .7, chin: .5, mouthWidth: .5, earShape: .4 },
      skinTone: '#e9dccf', eyeColor: '#7a4d1c', hairColor: '#d9481c',
      items: { hair: 'hair_clown', brows: 'brows_arched', beard: null, top: 'top_clown_tunic', bottom: 'bottom_clown_pants', socks: null, shoes: 'shoes_clown', headwear: null, eyewear: null, neck: null, wrist: null, bodyart: 'facepaint_midnight' },
      dance: 'thriller', celebration: 'shh',
    }),
  },
];
export const BUNDLE_BY_ID = new Map(BUNDLES.map(b => [b.id, b]));

export const DEFAULT_CONFIG: AvatarConfig = structuredClone(BUNDLES[0].config);

/** Paleta de tons de pele (do claro ao retinto) e cores sugeridas. */
export const SKIN_TONES = ['#f3d6c1', '#e9c3a3', '#d9a47f', '#c68b62', '#b0744e', '#a8714e', '#8d5a3b', '#734428', '#5c3420', '#45261a', '#33201a'];
export const HAIR_COLORS = ['#0f0c0b', '#24170f', '#3a2618', '#5b3a22', '#8a5a33', '#b07a45', '#d8b276', '#e9d3a6', '#b8b2ab', '#d9481c', '#7c5ce0', '#2f7ad8'];
export const EYE_COLORS = ['#2a1810', '#4a2c1a', '#6b4423', '#7a5a2a', '#4f6b3a', '#3d6a7a', '#5c7fa6', '#8a8f96'];
export const OUTFIT_COLORS = ['#f2f2ee', '#1e2230', '#2d3442', '#7c5ce0', '#efc51d', '#169a4a', '#1f2c66', '#e65068', '#2f7ad8', '#d9481c', '#c2b9a4', '#111111'];

export const itemUrl = (id: string) => `/avatar/items/${id}.glb`;
export const thumbUrl = (id: string) => `/avatar/thumbs/${id}.webp`;
