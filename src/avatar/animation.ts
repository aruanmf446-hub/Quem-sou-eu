import * as THREE from 'three';

/**
 * Sistema de animação compartilhado.
 *
 * As coreografias são descritas por poses-chave anatômicas (alvos dos pés,
 * altura do quadril, ângulos dos braços, dedos e expressões). Elas são
 * compiladas uma única vez no esqueleto-padrão (nomes Mixamo) e viram
 * AnimationClips do three.js. Como todos os avatares compartilham o mesmo
 * esqueleto e a mesma orientação de repouso, a mesma dança produz os mesmos
 * movimentos em qualquer personagem criado.
 */

export type V3 = [number, number, number];

export interface ArmPose {
  /** Abdução: ângulo de elevação lateral em graus (0 = braço junto ao corpo, 90 = horizontal). */
  raise: number;
  /** Flexão: braço à frente (+) ou para trás (-), graus. */
  forward: number;
  /** Dobra do cotovelo (0 = esticado). */
  elbow: number;
  /** Gira o plano do cotovelo (graus). 0: antebraço dobra para a frente; 90: para cima/dentro. */
  twist?: number;
  /** Punho: flexão, desvio e rotação (graus). */
  wrist?: V3;
  /** 0 = mão aberta, 1 = punho fechado. */
  fist?: number;
  /** Gestos de mão. */
  hand?: 'open' | 'fist' | 'point' | 'peace' | 'thumb' | 'claw' | 'relaxed';
  /** Ombro (clavícula): elevação e avanço, graus. */
  shrug?: number;
}

export interface LegPose {
  /** Alvo do tornozelo relativo à posição de repouso (metros, eixos do corpo). */
  foot: V3;
  /** Rotação do pé (graus): y = abrir para fora, x = ponta para baixo (+). */
  footRot?: V3;
  /** Direção do joelho (graus para fora). */
  knee?: number;
}

export interface Pose {
  /** Deslocamento do quadril (metros) e rotação (graus, x frente, y giro, z inclinação lateral). */
  hips?: V3;
  hipsRot?: V3;
  spine?: V3;
  chest?: V3;
  neck?: V3;
  head?: V3;
  armL?: ArmPose;
  armR?: ArmPose;
  legL?: LegPose;
  legR?: LegPose;
  face?: Partial<Record<'smile' | 'grin' | 'mouth_open' | 'brows_up' | 'brows_down' | 'squint' | 'pucker' | 'blink', number>>;
}

export interface Choreography {
  id: string;
  /** Batidas por minuto e duração do ciclo em batidas. */
  bpm: number;
  beats: number;
  loop: boolean;
  /** Poses-chave: [batida, pose]. A última pode repetir a primeira para fechar o ciclo. */
  keys: [number, Pose][];
  /** Movimento secundário contínuo (balanço, respiração) somado às poses. */
  groove?: (beat: number) => Pose;
}

const BASE_ARM: ArmPose = { raise: 8, forward: 0, elbow: 12, twist: 0, wrist: [0, 0, 0], hand: 'relaxed', shrug: 0 };
const BASE_LEG: LegPose = { foot: [0, 0, 0], footRot: [0, 0, 0], knee: 0 };

export interface RestBone { name: string; parent: string | null; head: THREE.Vector3; }

/** Esqueleto de repouso lido da base (posições de mundo das juntas). */
export class RestSkeleton {
  bones = new Map<string, RestBone>();
  constructor(root: THREE.Object3D) {
    root.updateMatrixWorld(true);
    root.traverse(o => {
      if ((o as THREE.Bone).isBone) {
        const parent = (o.parent as THREE.Bone)?.isBone ? o.parent!.name : null;
        this.bones.set(o.name, { name: o.name, parent, head: o.getWorldPosition(new THREE.Vector3()) });
      }
    });
  }
  head(name: string) { return this.bones.get(name)!.head; }
  dir(from: string, to: string) { return this.head(to).clone().sub(this.head(from)).normalize(); }
}

const X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0), Z = new THREE.Vector3(0, 0, 1);
const deg = THREE.MathUtils.degToRad;
const qEuler = (v: V3 | undefined, order: THREE.EulerOrder = 'YXZ') => new THREE.Quaternion().setFromEuler(new THREE.Euler(deg(v?.[0] ?? 0), deg(v?.[1] ?? 0), deg(v?.[2] ?? 0), order));
const qAxis = (axis: THREE.Vector3, angle: number) => new THREE.Quaternion().setFromAxisAngle(axis, deg(angle));

const FINGERS = ['Index', 'Middle', 'Ring', 'Pinky'] as const;

/** Resolve uma pose em rotações locais (quaternions) para cada osso. */
export class PoseSolver {
  private world = new Map<string, THREE.Quaternion>();
  out = new Map<string, THREE.Quaternion>();
  constructor(private rest: RestSkeleton) {}

  private setWorld(name: string, q: THREE.Quaternion) {
    const bone = this.rest.bones.get(name);
    if (!bone) return;
    const parentWorld = bone.parent ? this.world.get(bone.parent) ?? new THREE.Quaternion() : new THREE.Quaternion();
    this.world.set(name, q.clone());
    this.out.set(name, parentWorld.clone().invert().multiply(q));
  }

  private setLocal(name: string, q: THREE.Quaternion) {
    const bone = this.rest.bones.get(name);
    if (!bone) return;
    const parentWorld = bone.parent ? this.world.get(bone.parent) ?? new THREE.Quaternion() : new THREE.Quaternion();
    this.out.set(name, q.clone());
    this.world.set(name, parentWorld.clone().multiply(q));
  }

  /** Gira o osso (no mundo) para que sua direção de repouso aponte para `dir`, mantendo o giro mínimo. */
  private aim(name: string, restDir: THREE.Vector3, dir: THREE.Vector3, twist = 0, parentOverride?: THREE.Quaternion) {
    const bone = this.rest.bones.get(name)!;
    const parentWorld = parentOverride ?? (bone.parent ? this.world.get(bone.parent)! : new THREE.Quaternion());
    // Direção atual herdada do pai.
    const inherited = restDir.clone().applyQuaternion(parentWorld);
    const swing = new THREE.Quaternion().setFromUnitVectors(inherited, dir.clone().normalize());
    const world = swing.multiply(parentWorld).multiply(qAxis(restDir, twist));
    this.setWorld(name, world);
  }

  solve(pose: Pose) {
    this.world.clear();
    this.out.clear();
    const r = this.rest;
    const hipsQ = qEuler(pose.hipsRot);
    this.setLocal('Hips', hipsQ);
    const spine = pose.spine ?? [0, 0, 0];
    const chest = pose.chest ?? [0, 0, 0];
    this.setLocal('Spine', qEuler([spine[0] * .4, spine[1] * .35, spine[2] * .4]));
    this.setLocal('Spine1', qEuler([spine[0] * .35 + chest[0] * .4, spine[1] * .35 + chest[1] * .5, spine[2] * .35 + chest[2] * .4]));
    this.setLocal('Spine2', qEuler([spine[0] * .25 + chest[0] * .6, spine[1] * .3 + chest[1] * .5, spine[2] * .25 + chest[2] * .6]));
    this.setLocal('Neck', qEuler(pose.neck));
    this.setLocal('Head', qEuler(pose.head));
    const chestWorld = this.world.get('Spine2')!;
    for (const side of ['Left', 'Right'] as const) {
      const s = side === 'Left' ? 1 : -1;
      const arm = { ...BASE_ARM, ...(side === 'Left' ? pose.armL : pose.armR) };
      this.setLocal(`${side}Shoulder`, qEuler([-(arm.shrug ?? 0) * .3, 0, s * (arm.shrug ?? 0)]));
      // Braço: parte do corpo "pendurado", aplica abdução e flexão no referencial do peito.
      const down = new THREE.Vector3(0, -1, 0);
      const upper = down.clone()
        .applyAxisAngle(Z, deg(s * arm.raise))
        .applyAxisAngle(X, deg(-arm.forward))
        .applyQuaternion(chestWorld);
      const restUpper = r.dir(`${side}Arm`, `${side}ForeArm`);
      this.aim(`${side}Arm`, restUpper, upper);
      // Cotovelo dobra para a frente do braço, girando o plano pelo twist.
      const front = Z.clone().applyQuaternion(chestWorld);
      let hinge = new THREE.Vector3().crossVectors(upper, front);
      if (hinge.lengthSq() < 1e-6) hinge = X.clone().multiplyScalar(-s).applyQuaternion(chestWorld);
      hinge.normalize().negate();
      hinge.applyAxisAngle(upper, deg(s * (arm.twist ?? 0)));
      const fore = upper.clone().applyAxisAngle(hinge, -deg(arm.elbow)).normalize();
      const restFore = r.dir(`${side}ForeArm`, `${side}Hand`);
      this.aim(`${side}ForeArm`, restFore, fore);
      // Mão segue o antebraço; punho em eixos anatômicos de repouso.
      const restHand = r.dir(`${side}Hand`, `${side}HandMiddle1`);
      const palmSide = r.dir(`${side}HandIndex1`, `${side}HandPinky1`);
      const palmNormal = new THREE.Vector3().crossVectors(restHand, palmSide).normalize().multiplyScalar(s);
      const flexAxis = new THREE.Vector3().crossVectors(restHand, palmNormal).normalize();
      const w = arm.wrist ?? [0, 0, 0];
      const wristQ = qAxis(flexAxis, w[0]).multiply(qAxis(palmNormal, s * w[1])).multiply(qAxis(restHand, s * w[2]));
      this.setLocal(`${side}Hand`, wristQ);
      this.fingers(side, arm, palmNormal);
    }
    for (const side of ['Left', 'Right'] as const) {
      const leg = { ...BASE_LEG, ...(side === 'Left' ? pose.legL : pose.legR) };
      this.leg(side, leg, pose.hips ?? [0, 0, 0], hipsQ);
    }
  }

  private fingers(side: 'Left' | 'Right', arm: ArmPose, palmNormal: THREE.Vector3) {
    const r = this.rest;
    const curls: Record<string, number> = { Index: .15, Middle: .2, Ring: .25, Pinky: .3, Thumb: .1 };
    const set = (v: number) => { for (const k of Object.keys(curls)) curls[k] = v; };
    switch (arm.hand) {
      case 'fist': set(1); curls.Thumb = .7; break;
      case 'point': set(1); curls.Index = 0; curls.Thumb = .6; break;
      case 'peace': set(1); curls.Index = 0; curls.Middle = 0; curls.Thumb = .7; break;
      case 'thumb': set(1); curls.Thumb = -.2; break;
      case 'claw': set(.55); curls.Thumb = .3; break;
      case 'open': set(-.05); curls.Thumb = -.1; break;
      default: if (arm.fist !== undefined) set(arm.fist);
    }
    for (const f of FINGERS) {
      const a = `${side}Hand${f}1`, b = `${side}Hand${f}2`, c = `${side}Hand${f}3`;
      if (!r.bones.has(a)) continue;
      const dir = r.dir(a, b);
      const axis = new THREE.Vector3().crossVectors(dir, palmNormal).normalize();
      const k = curls[f];
      this.setLocal(a, qAxis(axis, -k * 70));
      this.setLocal(b, qAxis(axis, -k * 95));
      this.setLocal(c, qAxis(axis, -k * 60));
    }
    const t1 = `${side}HandThumb1`;
    if (r.bones.has(t1)) {
      const dir = r.dir(t1, `${side}HandThumb2`);
      const axis = new THREE.Vector3().crossVectors(dir, palmNormal).normalize();
      const k = curls.Thumb;
      this.setLocal(t1, qAxis(palmNormal, (side === 'Left' ? 1 : -1) * k * 25).multiply(qAxis(axis, -k * 25)));
      this.setLocal(`${side}HandThumb2`, qAxis(axis, -k * 40));
      this.setLocal(`${side}HandThumb3`, qAxis(axis, -k * 40));
    }
  }

  /** IK analítico de duas articulações: tornozelo no alvo, joelho para a frente. */
  private leg(side: 'Left' | 'Right', leg: LegPose, hipsOffset: V3, hipsQ: THREE.Quaternion) {
    const r = this.rest;
    const s = side === 'Left' ? 1 : -1;
    const hipsRest = r.head('Hips');
    const hipJoint = r.head(`${side}UpLeg`).clone().sub(hipsRest).applyQuaternion(hipsQ).add(hipsRest).add(new THREE.Vector3(...hipsOffset));
    const ankleRest = r.head(`${side}Foot`);
    const target = ankleRest.clone().add(new THREE.Vector3(leg.foot[0] * s, leg.foot[1], leg.foot[2]));
    const l1 = r.head(`${side}Leg`).distanceTo(r.head(`${side}UpLeg`));
    const l2 = r.head(`${side}Foot`).distanceTo(r.head(`${side}Leg`));
    const toTarget = target.clone().sub(hipJoint);
    const d = THREE.MathUtils.clamp(toTarget.length(), Math.abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4);
    const dirT = toTarget.normalize();
    // Plano do joelho: frente do corpo, aberta pelo ângulo `knee`.
    const fwd = Z.clone().applyQuaternion(hipsQ).applyAxisAngle(Y, deg(s * (leg.knee ?? 0)));
    const bendAxis = new THREE.Vector3().crossVectors(dirT, fwd).normalize();
    const a = Math.acos(THREE.MathUtils.clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1));
    const thighDir = dirT.clone().applyAxisAngle(bendAxis, -a);
    const kneePos = hipJoint.clone().add(thighDir.clone().multiplyScalar(l1));
    const shinDir = hipJoint.clone().add(dirT.clone().multiplyScalar(d)).sub(kneePos).normalize();
    this.aim(`${side}UpLeg`, r.dir(`${side}UpLeg`, `${side}Leg`), thighDir);
    this.aim(`${side}Leg`, r.dir(`${side}Leg`, `${side}Foot`), shinDir);
    // Pé plano no chão (orientação no mundo), com giro e ponta configuráveis.
    const fr = leg.footRot ?? [0, 0, 0];
    const footWorld = qAxis(Y, s * fr[1]).multiply(qAxis(X, fr[0])).multiply(qAxis(Z, -s * fr[2]));
    this.setWorld(`${side}Foot`, footWorld);
    this.setLocal(`${side}ToeBase`, qAxis(X, -Math.max(0, fr[0]) * .6));
  }
}

// --- interpolação entre poses -------------------------------------------------

type Flat = Record<string, number>;
type HandName = NonNullable<ArmPose['hand']>;

function flatten(p: Pose, out: Flat = {}, prefix = ''): Flat {
  for (const [k, v] of Object.entries(p)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) v.forEach((x, i) => { out[`${prefix}${k}.${i}`] = x as number; });
    else if (typeof v === 'object') flatten(v as Pose, out, `${prefix}${k}.`);
    else if (typeof v === 'number') out[`${prefix}${k}`] = v;
  }
  return out;
}

function unflatten(f: Flat, hands: { L?: HandName; R?: HandName }): Pose {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(f)) {
    const parts = key.split('.');
    let node = out as Record<string, unknown>;
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i], next = parts[i + 1];
      if (node[p] === undefined) node[p] = /^\d+$/.test(next) ? [0, 0, 0] : {};
      node = node[p] as Record<string, unknown>;
    }
    node[parts[parts.length - 1]] = value;
  }
  const pose = out as Pose;
  if (pose.armL) pose.armL.hand = hands.L ?? pose.armL.hand;
  if (pose.armR) pose.armR.hand = hands.R ?? pose.armR.hand;
  return pose;
}

const NEUTRAL: Pose = {
  hips: [0, 0, 0], hipsRot: [0, 0, 0], spine: [0, 0, 0], chest: [0, 0, 0], neck: [0, 0, 0], head: [0, 0, 0],
  armL: { ...BASE_ARM }, armR: { ...BASE_ARM },
  legL: { foot: [0, 0, 0], footRot: [0, 0, 0], knee: 0 }, legR: { foot: [0, 0, 0], footRot: [0, 0, 0], knee: 0 },
  face: { smile: 0, grin: 0, mouth_open: 0, brows_up: 0, brows_down: 0, squint: 0, pucker: 0, blink: 0 },
};

/** Avalia a coreografia num instante (em batidas) com spline Catmull-Rom entre poses. */
export function samplePose(c: Choreography, beat: number): Pose {
  const keys = c.keys.map(([b, p]) => [b, flatten(mergePose(NEUTRAL, p))] as const);
  const n = keys.length;
  const t = c.loop ? ((beat % c.beats) + c.beats) % c.beats : Math.min(beat, c.beats);
  let i = keys.findIndex(([b], k) => k < n - 1 && t >= b && t <= keys[k + 1][0]);
  if (i < 0) i = t < keys[0][0] ? 0 : n - 2;
  const [b1, p1] = keys[i], [b2, p2] = keys[Math.min(i + 1, n - 1)];
  const p0 = keys[i > 0 ? i - 1 : c.loop ? n - 2 : 0][1];
  const p3 = keys[i + 2 < n ? i + 2 : c.loop ? 1 : n - 1][1];
  const f = b2 > b1 ? (t - b1) / (b2 - b1) : 0;
  const out: Flat = {};
  for (const k of Object.keys(p1)) {
    const a0 = p0[k] ?? p1[k], a1 = p1[k], a2 = p2[k] ?? a1, a3 = p3[k] ?? a2;
    out[k] = .5 * ((2 * a1) + (-a0 + a2) * f + (2 * a0 - 5 * a1 + 4 * a2 - a3) * f * f + (-a0 + 3 * a1 - 3 * a2 + a3) * f * f * f);
  }
  const src = c.keys[i][1], dst = c.keys[Math.min(i + 1, n - 1)][1];
  const hands = { L: (f < .5 ? src.armL?.hand : dst.armL?.hand) ?? src.armL?.hand, R: (f < .5 ? src.armR?.hand : dst.armR?.hand) ?? src.armR?.hand };
  let pose = unflatten(out, hands);
  if (c.groove) pose = addPose(pose, c.groove(beat));
  return pose;
}

function mergePose(a: Pose, b: Pose): Pose {
  const out: Pose = JSON.parse(JSON.stringify(a));
  for (const [k, v] of Object.entries(b)) {
    if (v && typeof v === 'object' && !Array.isArray(v)) (out as Record<string, unknown>)[k] = { ...((out as Record<string, unknown>)[k] as object), ...v };
    else (out as Record<string, unknown>)[k] = v;
  }
  return out;
}

function addPose(a: Pose, b: Pose): Pose {
  const fa = flatten(a), fb = flatten(b);
  for (const [k, v] of Object.entries(fb)) fa[k] = (fa[k] ?? 0) + v;
  return unflatten(fa, { L: a.armL?.hand, R: a.armR?.hand });
}

export const FACE_MORPHS: Record<string, string> = {
  smile: 'expr_smile', grin: 'expr_grin', mouth_open: 'expr_mouth_open', brows_up: 'expr_brows_up',
  brows_down: 'expr_brows_down', squint: 'expr_squint', pucker: 'expr_pucker',
};

export interface CompiledClip { clip: THREE.AnimationClip; face: { times: Float32Array; values: Record<string, Float32Array> }; }

/** Compila a coreografia em um AnimationClip (30 quadros/s). */
export function compile(c: Choreography, rest: RestSkeleton, fps = 30): CompiledClip {
  const solver = new PoseSolver(rest);
  const duration = c.beats * 60 / c.bpm;
  const frames = Math.max(2, Math.round(duration * fps) + 1);
  const times = new Float32Array(frames);
  const quats = new Map<string, Float32Array>();
  const motion = new Float32Array(frames * 3);
  const face: Record<string, Float32Array> = {};
  for (const k of Object.keys(FACE_MORPHS)) face[FACE_MORPHS[k]] = new Float32Array(frames);
  face.expr_blink_l = new Float32Array(frames);
  face.expr_blink_r = new Float32Array(frames);
  const prev = new Map<string, THREE.Quaternion>();
  for (let i = 0; i < frames; i++) {
    const t = i / (frames - 1) * duration;
    times[i] = t;
    const pose = samplePose(c, t * c.bpm / 60);
    solver.solve(pose);
    for (const [name, q] of solver.out) {
      let arr = quats.get(name);
      if (!arr) { arr = new Float32Array(frames * 4); quats.set(name, arr); }
      // Mantém o hemisfério contínuo para a interpolação.
      const p = prev.get(name);
      if (p && p.dot(q) < 0) q.set(-q.x, -q.y, -q.z, -q.w);
      prev.set(name, q.clone());
      q.toArray(arr, i * 4);
    }
    const h = pose.hips ?? [0, 0, 0];
    motion[i * 3] = h[0]; motion[i * 3 + 1] = h[1]; motion[i * 3 + 2] = h[2];
    for (const [k, morph] of Object.entries(FACE_MORPHS)) face[morph][i] = Math.max(0, (pose.face as Flat | undefined)?.[k] ?? 0);
    const blink = Math.max(0, pose.face?.blink ?? 0);
    face.expr_blink_l[i] = blink;
    face.expr_blink_r[i] = blink;
  }
  const tracks: THREE.KeyframeTrack[] = [];
  for (const [name, values] of quats) tracks.push(new THREE.QuaternionKeyframeTrack(`${name}.quaternion`, times, values));
  tracks.push(new THREE.VectorKeyframeTrack('AvatarMotion.position', times, motion));
  const clip = new THREE.AnimationClip(c.id, duration, tracks);
  return { clip, face: { times, values: face } };
}

/** Avalia as curvas faciais do clip ativo (interpolação linear). */
export function sampleFace(face: CompiledClip['face'], time: number, out: Record<string, number>, weight = 1) {
  const { times, values } = face;
  const duration = times[times.length - 1];
  const t = duration > 0 ? Math.min(time, duration) : 0;
  let i = Math.min(times.length - 2, Math.max(0, Math.floor(t / duration * (times.length - 1))));
  while (i < times.length - 2 && times[i + 1] < t) i++;
  const f = times[i + 1] > times[i] ? (t - times[i]) / (times[i + 1] - times[i]) : 0;
  for (const [k, arr] of Object.entries(values)) out[k] = (out[k] ?? 0) + (arr[i] + (arr[i + 1] - arr[i]) * f) * weight;
}
