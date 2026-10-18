/** Configuração persistida do avatar criado pelo jogador. */
export interface BodyShape {
  /** 0 = masculino, 1 = feminino. Valores intermediários são permitidos. */
  type: number;
  height: number;
  muscle: number;
  weight: number;
  shoulders: number;
  torso: number;
  hips: number;
  legs: number;
  head: number;
  /** Barriga: -1 chapada .. 1 redonda. */
  belly: number;
  /** 0 = adulto, 1 = criança (proporções infantis: baixo, cabeça maior, membros curtos). */
  child: number;
  /** 0 = realista, 1 = estilo animação (cabeça e olhos maiores). */
  style: number;
}

export type FaceShape = 'natural' | 'oval' | 'round' | 'square' | 'triangle';

export interface FaceConfig {
  shape: FaceShape;
  shapeAmount: number;
  width: number;
  jaw: number;
  chin: number;
  cheekbones: number;
  eyeSize: number;
  eyeDistance: number;
  eyeTilt: number;
  noseWidth: number;
  noseLength: number;
  noseTip: number;
  lips: number;
  mouthWidth: number;
  browHeight: number;
  browAngle: number;
  ears: number;
  earShape: number;
  /** Traços de personagem: bochechas (magras ↔ cheias), olhos (amendoados ↔ redondos), idade (jovem ↔ madura),
   *  nariz (arrebitado ↔ aquilino), cantos da boca (caídos ↔ erguidos), rosto (curto ↔ comprido). */
  cheeks: number;
  eyeShape: number;
  age: number;
  noseBridge: number;
  mouthCorners: number;
  faceLength: number;
  /** Expressão de repouso (personalidade): sorriso 0..1, olhar semicerrado 0..1, sobrancelhas -1 (franzidas) .. 1 (erguidas). */
  smile: number;
  squint: number;
  browMood: number;
}

/** Slots do guarda-roupa. Cada item ocupa exatamente um slot. */
export const SLOTS = ['hair', 'brows', 'beard', 'top', 'bottom', 'socks', 'shoes', 'headwear', 'eyewear', 'neck', 'wrist', 'bodyart', 'hands', 'back', 'belt', 'prop'] as const;
export type Slot = typeof SLOTS[number];

export interface AvatarConfig {
  v: 2;
  body: BodyShape;
  face: FaceConfig;
  skinTone: string;
  eyeColor: string;
  hairColor: string;
  /** Cor das pontas (descolorido). null = sem pontas. */
  hairTips: string | null;
  /** Item equipado por slot (null = vazio quando o slot permite). */
  items: Partial<Record<Slot, string | null>>;
  /** Variação de cor por item (quando o item permite recolorir). */
  tints: Record<string, string>;
  dance: string;
  celebration: string;
}

export const DEFAULT_BODY: BodyShape = { type: 0, height: 0, muscle: 0, weight: 0, shoulders: 0, torso: 0, hips: 0, legs: 0, head: 0, belly: 0, child: 0, style: 0 };
export const DEFAULT_FACE: FaceConfig = {
  shape: 'natural', shapeAmount: .6, width: 0, jaw: 0, chin: 0, cheekbones: 0, eyeSize: 0, eyeDistance: 0, eyeTilt: 0,
  noseWidth: 0, noseLength: 0, noseTip: 0, lips: 0, mouthWidth: 0, browHeight: 0, browAngle: 0, ears: 0, earShape: 0,
  cheeks: 0, eyeShape: 0, age: 0, noseBridge: 0, mouthCorners: 0, faceLength: 0,
  smile: 0, squint: 0, browMood: 0,
};

export const clamp = (v: number, a = -1, b = 1) => Math.min(b, Math.max(a, Number.isFinite(v) ? v : 0));
const pair = (v: number, up: string, down: string, out: Record<string, number>, k = 1) => {
  if (v > 0) out[up] = (out[up] ?? 0) + v * k;
  else if (v < 0) out[down] = (out[down] ?? 0) - v * k;
};

/** Expressão de repouso do rosto (somada às expressões das danças, que podem ir além). */
export function restExpression(face: Partial<FaceConfig>): Record<string, number> {
  const smile = clamp(face.smile ?? 0, 0, 1), squint = clamp(face.squint ?? 0, 0, 1), mood = clamp(face.browMood ?? 0);
  return {
    expr_smile: smile * .75, expr_grin: smile * .3, expr_squint: squint * .7 + smile * .15,
    expr_brows_up: Math.max(0, mood) * .7, expr_brows_down: Math.max(0, -mood) * .7,
  };
}

/** Converte a configuração em influências dos morph targets compartilhados. */
export function morphInfluences(config: Pick<AvatarConfig, 'body' | 'face'>): Record<string, number> {
  const out: Record<string, number> = {};
  const b = config.body, f = config.face;
  const fem = clamp(b.type, 0, 1);
  out.body_feminine = fem;
  for (const [axis, value] of [['muscle', b.muscle], ['weight', b.weight], ['height', b.height]] as const) {
    const v = clamp(value);
    pair(v, `${axis}_up_m`, `${axis}_down_m`, out, 1 - fem);
    pair(v, `${axis}_up_f`, `${axis}_down_f`, out, fem);
  }
  pair(clamp(b.shoulders), 'shoulders_wide', 'shoulders_narrow', out);
  pair(clamp(b.torso), 'torso_v', 'torso_straight', out);
  pair(clamp(b.hips), 'hips_wide', 'hips_narrow', out);
  pair(clamp(b.legs), 'legs_long', 'legs_short', out, .8);
  pair(clamp(b.head), 'head_big', 'head_small', out);
  pair(clamp(b.belly ?? 0), 'belly_round', 'belly_flat', out);
  const child = clamp(b.child ?? 0, 0, 1);
  if (child > 0) { out.body_child_m = child * (1 - fem); out.body_child_f = child * fem; }
  if (b.style > 0) out.style_toon = clamp(b.style, 0, 1);
  if (f.shape !== 'natural') out[`face_${f.shape}`] = clamp(f.shapeAmount, 0, 1);
  pair(clamp(f.width), 'face_wide', 'face_narrow', out);
  pair(clamp(f.jaw), 'jaw_strong', 'jaw_soft', out);
  pair(clamp(f.chin), 'chin_forward', 'chin_back', out);
  pair(clamp(f.cheekbones), 'cheekbones_high', 'cheekbones_low', out);
  pair(clamp(f.eyeSize), 'eyes_big', 'eyes_small', out, .8);
  pair(clamp(f.eyeDistance), 'eyes_apart', 'eyes_close', out, .8);
  pair(clamp(f.eyeTilt), 'eyes_up', 'eyes_down', out);
  pair(clamp(f.noseWidth), 'nose_wide', 'nose_narrow', out);
  pair(clamp(f.noseLength), 'nose_long', 'nose_short', out);
  pair(clamp(f.noseTip), 'nose_tip_up', 'nose_tip_down', out);
  pair(clamp(f.lips), 'lips_full', 'lips_thin', out);
  pair(clamp(f.mouthWidth), 'mouth_wide', 'mouth_narrow', out);
  pair(clamp(f.browHeight), 'brows_high', 'brows_low', out);
  pair(clamp(f.browAngle), 'brows_angle_up', 'brows_angle_down', out);
  pair(clamp(f.ears), 'ears_big', 'ears_small', out);
  if (f.earShape > 0) out.ears_pointed = clamp(f.earShape, 0, 1);
  pair(clamp(f.cheeks ?? 0), 'cheeks_full', 'cheeks_hollow', out);
  pair(clamp(f.eyeShape ?? 0), 'eyes_round', 'eyes_almond', out);
  pair(clamp(f.age ?? 0), 'face_mature', 'face_young', out);
  pair(clamp(f.noseBridge ?? 0), 'nose_aquiline', 'nose_button', out);
  pair(clamp(f.mouthCorners ?? 0), 'mouth_corners_up', 'mouth_corners_down', out);
  pair(clamp(f.faceLength ?? 0), 'face_long', 'face_short', out);
  return out;
}

const HEX = /^#[0-9a-f]{6}$/i;
export const safeColor = (value: unknown, fallback: string) => (typeof value === 'string' && HEX.test(value) ? value.toLowerCase() : fallback);

function numbers<T extends object>(defaults: T, raw: unknown): T {
  const out = { ...defaults } as Record<string, unknown>;
  if (raw && typeof raw === 'object') {
    for (const [k, v] of Object.entries(defaults)) {
      const r = (raw as Record<string, unknown>)[k];
      if (typeof v === 'number' && typeof r === 'number' && Number.isFinite(r)) out[k] = clamp(r, k === 'type' || k === 'style' || k === 'child' || k === 'shapeAmount' || k === 'earShape' || k === 'smile' || k === 'squint' ? 0 : -1, 1);
      if (typeof v === 'string' && typeof r === 'string') out[k] = r;
    }
  }
  return out as T;
}

/** Normaliza dados vindos do armazenamento local ou do servidor. */
export function sanitizeConfig(raw: unknown, fallback: AvatarConfig): AvatarConfig {
  if (!raw || typeof raw !== 'object') return structuredClone(fallback);
  const r = raw as Partial<AvatarConfig>;
  const face = numbers(DEFAULT_FACE, r.face);
  if (!['natural', 'oval', 'round', 'square', 'triangle'].includes(face.shape)) face.shape = 'natural';
  const items: AvatarConfig['items'] = { ...fallback.items };
  if (r.items && typeof r.items === 'object') {
    for (const slot of SLOTS) {
      const v = (r.items as Record<string, unknown>)[slot];
      if (v === null || typeof v === 'string') items[slot] = v;
    }
  }
  const tints: Record<string, string> = {};
  if (r.tints && typeof r.tints === 'object') for (const [k, v] of Object.entries(r.tints)) if (typeof v === 'string' && HEX.test(v)) tints[k] = v;
  return {
    v: 2,
    body: numbers(DEFAULT_BODY, r.body),
    face,
    skinTone: safeColor(r.skinTone, fallback.skinTone),
    eyeColor: safeColor(r.eyeColor, fallback.eyeColor),
    hairColor: safeColor(r.hairColor, fallback.hairColor),
    hairTips: r.hairTips === null ? null : safeColor(r.hairTips, fallback.hairTips ?? '#e8c27a'),
    items,
    tints,
    dance: typeof r.dance === 'string' ? r.dance : fallback.dance,
    celebration: typeof r.celebration === 'string' ? r.celebration : fallback.celebration,
  };
}
