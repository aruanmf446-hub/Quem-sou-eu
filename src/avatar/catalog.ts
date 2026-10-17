import { DEFAULT_BODY, DEFAULT_FACE, type AvatarConfig, type Slot } from './config';

export type Rarity = 'comum' | 'raro' | 'épico' | 'lendário';

export interface CatalogItem {
  id: string;
  slot: Slot;
  name: string;
  price: number;
  rarity: Rarity;
  /** Pacote (personagem legado) que libera o item ao ser adquirido. */
  bundle?: BundleId;
  /** Partes recoloríveis e cor padrão. */
  tints?: Record<string, string>;
  /** Cor de cabelo sugerida ao escolher este estilo. */
  suggestHair?: string;
  tags?: string[];
}

export const SLOT_LABELS: Record<Slot, string> = {
  hair: 'Cabelo', brows: 'Sobrancelhas', beard: 'Barba', top: 'Parte de cima', bottom: 'Parte de baixo',
  socks: 'Meias', shoes: 'Calçados', headwear: 'Cabeça', eyewear: 'Óculos', neck: 'Pescoço', wrist: 'Pulso', bodyart: 'Arte corporal',
  hands: 'Luvas', back: 'Capa e costas', belt: 'Cintos e bolsas', prop: 'Na mão',
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
  // Coleção Mecânica dos Céus
  { id: 'hair_wild_ponytail', slot: 'hair', name: 'Rabo de cavalo rebelde', price: 120, rarity: 'épico', bundle: 'sky-mechanic', suggestHair: '#a8401f' },
  { id: 'goggles_brass', slot: 'headwear', name: 'Óculos de aviador', price: 90, rarity: 'épico', bundle: 'sky-mechanic' },
  { id: 'top_aviator_jacket', slot: 'top', name: 'Jaqueta de aviadora', price: 150, rarity: 'épico', bundle: 'sky-mechanic' },
  { id: 'bottom_cargo_navy', slot: 'bottom', name: 'Calça cargo de oficina', price: 110, rarity: 'raro', bundle: 'sky-mechanic' },
  { id: 'shoes_lace_boots', slot: 'shoes', name: 'Botas de cano alto com engrenagens', price: 130, rarity: 'épico', bundle: 'sky-mechanic' },
  { id: 'gloves_fingerless', slot: 'hands', name: 'Luvas sem dedos', price: 50, rarity: 'raro', bundle: 'sky-mechanic' },
  { id: 'belt_tool_harness', slot: 'belt', name: 'Cinturão de ferramentas', price: 120, rarity: 'épico', bundle: 'sky-mechanic' },
  { id: 'scarf_wind', slot: 'back', name: 'Lenço ao vento', price: 90, rarity: 'raro', bundle: 'sky-mechanic', tints: { main: '#e8735a' } },
  { id: 'prop_wrench', slot: 'prop', name: 'Chave inglesa', price: 80, rarity: 'raro', bundle: 'sky-mechanic' },
  // Coleção Astrônoma
  { id: 'hair_wavy_long', slot: 'hair', name: 'Ondas longas', price: 120, rarity: 'épico', bundle: 'astronomer', suggestHair: '#1f2a5c' },
  { id: 'circlet_gear', slot: 'headwear', name: 'Tiara de engrenagem', price: 70, rarity: 'raro', bundle: 'astronomer' },
  { id: 'top_star_tunic', slot: 'top', name: 'Túnica estelar', price: 150, rarity: 'épico', bundle: 'astronomer' },
  { id: 'back_star_capelet', slot: 'back', name: 'Capa das constelações', price: 140, rarity: 'épico', bundle: 'astronomer' },
  { id: 'bottom_star_pants', slot: 'bottom', name: 'Calça bufante estrelada', price: 110, rarity: 'raro', bundle: 'astronomer' },
  { id: 'shoes_gold_boots', slot: 'shoes', name: 'Botas de bordas douradas', price: 120, rarity: 'épico', bundle: 'astronomer' },
  { id: 'belt_compass', slot: 'belt', name: 'Cinto da bússola', price: 90, rarity: 'raro', bundle: 'astronomer' },
  { id: 'bracers_leather', slot: 'wrist', name: 'Braçadeiras de couro', price: 60, rarity: 'raro', bundle: 'astronomer' },
  { id: 'prop_orrery_staff', slot: 'prop', name: 'Cajado orrery', price: 150, rarity: 'lendário', bundle: 'astronomer' },
  // Coleção Arlequina
  { id: 'hair_curly_pigtails', slot: 'hair', name: 'Maria-chiquinha cacheada', price: 130, rarity: 'épico', bundle: 'harlequin', suggestHair: '#e0367d' },
  { id: 'hat_jester', slot: 'headwear', name: 'Chapéu de guizos', price: 120, rarity: 'épico', bundle: 'harlequin' },
  { id: 'top_harlequin', slot: 'top', name: 'Blusa losango com gola franzida', price: 150, rarity: 'épico', bundle: 'harlequin' },
  { id: 'bottom_puff_shorts', slot: 'bottom', name: 'Short bufante losango', price: 100, rarity: 'raro', bundle: 'harlequin' },
  { id: 'socks_harlequin', slot: 'socks', name: 'Meias 7/8 desencontradas', price: 70, rarity: 'raro', bundle: 'harlequin' },
  { id: 'shoes_jester', slot: 'shoes', name: 'Botinhas de bico enrolado', price: 120, rarity: 'épico', bundle: 'harlequin' },
  { id: 'gloves_ruffle', slot: 'hands', name: 'Luvas com babado', price: 60, rarity: 'raro', bundle: 'harlequin' },
  { id: 'prop_bomb', slot: 'prop', name: 'Bomba sorridente', price: 90, rarity: 'épico', bundle: 'harlequin' },
  { id: 'facepaint_diamond', slot: 'bodyart', name: 'Losango no rosto', price: 40, rarity: 'comum', bundle: 'harlequin' },
  // Coleção Guardião Anúbis
  { id: 'mask_anubis', slot: 'headwear', name: 'Máscara de Anúbis', price: 220, rarity: 'lendário', bundle: 'anubis' },
  { id: 'neck_usekh', slot: 'neck', name: 'Colar real dourado', price: 120, rarity: 'épico', bundle: 'anubis' },
  { id: 'top_anubis_harness', slot: 'top', name: 'Faixas do guardião', price: 120, rarity: 'épico', bundle: 'anubis' },
  { id: 'bottom_shendyt', slot: 'bottom', name: 'Saiote cerimonial', price: 130, rarity: 'épico', bundle: 'anubis' },
  { id: 'back_cape_night', slot: 'back', name: 'Manto noturno', price: 120, rarity: 'raro', bundle: 'anubis', tints: { main: '#24264a' } },
  { id: 'bracers_gold', slot: 'wrist', name: 'Braceletes de ouro', price: 90, rarity: 'épico', bundle: 'anubis' },
  { id: 'shoes_gold_greaves', slot: 'shoes', name: 'Grevas douradas', price: 130, rarity: 'épico', bundle: 'anubis' },
  { id: 'prop_sun_staff', slot: 'prop', name: 'Cetro solar', price: 150, rarity: 'lendário', bundle: 'anubis' },
  // Coleção Cientista Voltaico
  { id: 'hair_spiky', slot: 'hair', name: 'Espetado elétrico', price: 120, rarity: 'épico', bundle: 'volt', suggestHair: '#2f7ad8' },
  { id: 'top_lab_coat', slot: 'top', name: 'Jaleco de bordas douradas', price: 170, rarity: 'lendário', bundle: 'volt' },
  { id: 'bottom_cargo_dark', slot: 'bottom', name: 'Calça de laboratório', price: 100, rarity: 'raro', bundle: 'volt' },
  { id: 'shoes_buckle_boots', slot: 'shoes', name: 'Botas de fivela', price: 120, rarity: 'épico', bundle: 'volt' },
  { id: 'hands_mech_arm', slot: 'hands', name: 'Braço mecânico voltaico', price: 180, rarity: 'lendário', bundle: 'volt' },
  { id: 'belt_bolt', slot: 'belt', name: 'Cinto do raio', price: 80, rarity: 'raro', bundle: 'volt' },
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

export type BundleId = 'street' | 'striker' | 'night-clown' | 'sky-mechanic' | 'astronomer' | 'harlequin' | 'anubis' | 'volt';

export interface Bundle {
  id: BundleId;
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
      face: { ...DEFAULT_FACE, shape: 'oval', shapeAmount: .5, lips: .35, eyeSize: .35, noseWidth: -.3, jaw: -.4, eyeShape: -.3, cheeks: .1, mouthCorners: .3, smile: .35 },
      skinTone: '#bd8058', eyeColor: '#4a2c1a', hairColor: '#1d1418',
      items: { hair: 'hair_bun', brows: 'brows_arched', beard: null, top: 'top_track_jacket', bottom: 'bottom_joggers', socks: 'socks_crew', shoes: 'shoes_hightops', headwear: null, eyewear: null, neck: null, wrist: null, bodyart: null },
      tints: { 'top_track_jacket:main': '#7c5ce0', 'bottom_joggers:main': '#1e2230', 'shoes_hightops:main': '#1c1f29' },
    }),
  },
  {
    id: 'striker', name: 'Camisa 10', subtitle: 'Talento de sobra, dentro e fora do campo', price: 150, color: '#efc51d',
    config: base({
      body: { ...DEFAULT_BODY, muscle: .25, legs: .1 },
      face: { ...DEFAULT_FACE, jaw: .35, chin: .2, cheekbones: .3, cheeks: -.3, age: .15, mouthCorners: .3, smile: .5, browMood: -.15 },
      skinTone: '#8d5a3b', eyeColor: '#3a2215', hairColor: '#2b1d14', hairTips: '#e2bf7a',
      items: { hair: 'hair_curly_fade', brows: 'brows_thick', beard: 'beard_goatee', top: 'top_jersey_10', bottom: 'bottom_shorts_10', socks: 'socks_football_10', shoes: 'shoes_cleats_10', headwear: null, eyewear: null, neck: null, wrist: null, bodyart: 'tattoo_sleeve' },
      dance: 'samba', celebration: 'airplane',
    }),
  },
  {
    id: 'night-clown', name: 'Riso da Meia-Noite', subtitle: 'Um espetáculo de arrepiar', price: 250, color: '#c2b9a4',
    config: base({
      body: { ...DEFAULT_BODY, muscle: -.2, weight: -.2, height: .25, legs: .3 },
      face: { ...DEFAULT_FACE, shape: 'triangle', shapeAmount: .6, cheekbones: .7, chin: .5, mouthWidth: .5, earShape: .4, cheeks: -.7, faceLength: .6, mouthCorners: 1, smile: .7, squint: .3, browMood: .3 },
      skinTone: '#e9dccf', eyeColor: '#7a4d1c', hairColor: '#d9481c',
      items: { hair: 'hair_clown', brows: 'brows_arched', beard: null, top: 'top_clown_tunic', bottom: 'bottom_clown_pants', socks: null, shoes: 'shoes_clown', headwear: null, eyewear: null, neck: null, wrist: null, bodyart: 'facepaint_midnight' },
      dance: 'thriller', celebration: 'shh',
    }),
  },
  {
    id: 'sky-mechanic', name: 'Mecânica dos Céus', subtitle: 'Conserta dirigíveis com uma chave e um sorriso', price: 320, color: '#e8735a',
    config: base({
      body: { ...DEFAULT_BODY, type: 1, style: .8, muscle: .3, weight: .15, height: -.3, shoulders: .2, head: .1 },
      face: { ...DEFAULT_FACE, shape: 'round', shapeAmount: .8, width: .35, jaw: -.3, chin: -.2, cheekbones: -.3, eyeSize: .2, eyeDistance: .25, eyeTilt: .1, noseWidth: .15, noseLength: -.6, noseTip: .8, lips: .1, mouthWidth: .5, browHeight: .25, browAngle: .2, cheeks: .55, eyeShape: .5, age: -.3, noseBridge: -.6, mouthCorners: .6, faceLength: -.4, smile: .9, squint: .25, browMood: .25 },
      skinTone: '#f2c9a8', eyeColor: '#3f7a3a', hairColor: '#a8401f',
      items: { hair: 'hair_wild_ponytail', brows: 'brows_arched', beard: null, top: 'top_aviator_jacket', bottom: 'bottom_cargo_navy', socks: null, shoes: 'shoes_lace_boots', headwear: 'goggles_brass', hands: 'gloves_fingerless', belt: 'belt_tool_harness', back: 'scarf_wind', prop: 'prop_wrench', eyewear: null, neck: null, wrist: null, bodyart: null },
      tints: { 'scarf_wind:main': '#e8735a' }, dance: 'groove', celebration: 'flex',
    }),
  },
  {
    id: 'astronomer', name: 'Astrônoma', subtitle: 'Lê o futuro no movimento dos planetas', price: 320, color: '#3d4f9e',
    config: base({
      body: { ...DEFAULT_BODY, type: 1, style: .85, height: .1, weight: -.1, legs: .3, shoulders: -.2 },
      face: { ...DEFAULT_FACE, shape: 'oval', shapeAmount: .9, width: -.35, jaw: -.6, chin: .25, cheekbones: .6, eyeSize: .75, eyeDistance: -.1, eyeTilt: -.35, noseWidth: .25, noseLength: .1, noseTip: .1, lips: .7, mouthWidth: -.25, browHeight: .35, browAngle: -.3, cheeks: -.2, eyeShape: -.7, age: -.1, noseBridge: .1, mouthCorners: .2, faceLength: .3, smile: .3, squint: .4, browMood: .2 },
      skinTone: '#9a6040', eyeColor: '#d9a43a', hairColor: '#1f2a5c',
      items: { hair: 'hair_wavy_long', brows: 'brows_thick', beard: null, top: 'top_star_tunic', bottom: 'bottom_star_pants', socks: null, shoes: 'shoes_gold_boots', headwear: 'circlet_gear', back: 'back_star_capelet', belt: 'belt_compass', wrist: 'bracers_leather', prop: 'prop_orrery_staff', hands: null, eyewear: null, neck: null, bodyart: null },
      dance: 'groove', celebration: 'heart',
    }),
  },
  {
    id: 'harlequin', name: 'Arlequina', subtitle: 'O espetáculo explode quando ela entra', price: 320, color: '#e0367d',
    config: base({
      body: { ...DEFAULT_BODY, type: 1, style: 1, height: -.25, hips: .3, legs: .3, head: .2, weight: -.2 },
      face: { ...DEFAULT_FACE, shape: 'triangle', shapeAmount: .75, width: .1, jaw: -.5, chin: .5, cheekbones: .8, eyeSize: 1, eyeDistance: .3, eyeTilt: .8, noseWidth: -.5, noseLength: -.7, noseTip: 1, lips: .45, mouthWidth: .7, browHeight: .45, browAngle: .9, earShape: .25, cheeks: .4, eyeShape: .9, age: -.9, noseBridge: -.9, mouthCorners: 1, faceLength: -.6, smile: 1, squint: .1, browMood: .5 },
      skinTone: '#f7e1d3', eyeColor: '#1fa8a4', hairColor: '#e0367d', hairTips: '#2ec4c4',
      items: { hair: 'hair_curly_pigtails', brows: 'brows_arched', beard: null, top: 'top_harlequin', bottom: 'bottom_puff_shorts', socks: 'socks_harlequin', shoes: 'shoes_jester', headwear: 'hat_jester', hands: 'gloves_ruffle', prop: 'prop_bomb', bodyart: 'facepaint_diamond', back: null, belt: null, eyewear: null, neck: null, wrist: null },
      dance: 'thriller', celebration: 'jump',
    }),
  },
  {
    id: 'anubis', name: 'Guardião Anúbis', subtitle: 'Guarda os segredos do templo do sol', price: 400, color: '#d8a531',
    config: base({
      body: { ...DEFAULT_BODY, style: .5, muscle: .9, shoulders: .6, torso: .5, height: .3 },
      face: { ...DEFAULT_FACE },
      skinTone: '#33201a', eyeColor: '#7a5a2a', hairColor: '#0f0c0b',
      items: { hair: null, brows: 'brows_natural', beard: null, top: 'top_anubis_harness', bottom: 'bottom_shendyt', socks: null, shoes: 'shoes_gold_greaves', headwear: 'mask_anubis', neck: 'neck_usekh', back: 'back_cape_night', wrist: 'bracers_gold', prop: 'prop_sun_staff', hands: null, belt: null, eyewear: null, bodyart: null },
      dance: 'robot', celebration: 'flex',
    }),
  },
  {
    id: 'volt', name: 'Cientista Voltaico', subtitle: 'Cada experimento termina em faísca', price: 320, color: '#3b8cff',
    config: base({
      body: { ...DEFAULT_BODY, style: .7, muscle: -.3, weight: -.3, height: .3, legs: .3, head: -.1 },
      face: { ...DEFAULT_FACE, shape: 'square', shapeAmount: .5, width: -.55, jaw: .8, chin: .9, cheekbones: .9, eyeSize: -.1, eyeDistance: -.35, eyeTilt: -.15, noseWidth: -.3, noseLength: .9, noseTip: -.5, lips: -.6, mouthWidth: .35, browHeight: -.25, browAngle: 1, ears: .35, cheeks: -.9, eyeShape: -.5, age: .7, noseBridge: 1, mouthCorners: -.2, faceLength: 1, smile: .5, squint: .5, browMood: -.6 },
      skinTone: '#e8cbb4', eyeColor: '#2f7ad8', hairColor: '#2f7ad8',
      items: { hair: 'hair_spiky', brows: 'brows_thick', beard: null, top: 'top_lab_coat', bottom: 'bottom_cargo_dark', socks: null, shoes: 'shoes_buckle_boots', headwear: 'goggles_brass', hands: 'hands_mech_arm', belt: 'belt_bolt', back: null, prop: null, eyewear: null, neck: null, wrist: null, bodyart: null },
      dance: 'robot', celebration: 'jump',
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
