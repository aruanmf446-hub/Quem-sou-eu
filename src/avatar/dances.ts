import type { ArmPose, Choreography, Pose } from './animation';

/**
 * Coreografias originais do Quem Sou Eu?. Valores em graus e metros.
 * Pés: [para fora, para cima, para a frente] relativos ao repouso; o IK mantém os pés plantados.
 */
const stance = (out = -.065, rot = 9) => ({ foot: [out, 0, 0] as [number, number, number], footRot: [0, rot, 0] as [number, number, number] });
const arm = (raise: number, forward: number, elbow: number, extra: Partial<ArmPose> = {}): ArmPose => ({ raise, forward, elbow, ...extra });
const mirror = (p: Pose): Pose => ({
  ...p,
  hips: p.hips ? [-p.hips[0], p.hips[1], p.hips[2]] : undefined,
  hipsRot: p.hipsRot ? [p.hipsRot[0], -p.hipsRot[1], -p.hipsRot[2]] : undefined,
  spine: p.spine ? [p.spine[0], -p.spine[1], -p.spine[2]] : undefined,
  chest: p.chest ? [p.chest[0], -p.chest[1], -p.chest[2]] : undefined,
  neck: p.neck ? [p.neck[0], -p.neck[1], -p.neck[2]] : undefined,
  head: p.head ? [p.head[0], -p.head[1], -p.head[2]] : undefined,
  armL: p.armR, armR: p.armL, legL: p.legR, legR: p.legL,
});
const bounce = (depth: number, phase = 0) => (beat: number): Pose => ({ hips: [0, -depth * (.5 - .5 * Math.cos(2 * Math.PI * (beat + phase))), 0] });

export const IDLE: Choreography = {
  id: 'idle', bpm: 60, beats: 6, loop: true,
  keys: [
    [0, { hips: [.008, -.006, 0], legL: stance(), legR: stance(), armL: arm(8, 2, 14), armR: arm(9, 0, 12), head: [2, 0, 0], face: { smile: .06 } }],
    [3, { hips: [-.008, -.008, 0], legL: stance(), legR: stance(), chest: [1.5, 0, 0], armL: arm(9, 0, 12), armR: arm(8, 3, 15), head: [0, 6, 0], face: { smile: .08 } }],
    [6, { hips: [.008, -.006, 0], legL: stance(), legR: stance(), armL: arm(8, 2, 14), armR: arm(9, 0, 12), head: [2, 0, 0], face: { smile: .06 } }],
  ],
};

// No embalo: passo-toque lateral com balanço de braços e quique.
const grooveA: Pose = {
  hips: [.03, -.012, 0], hipsRot: [0, 6, 3], chest: [2, 8, -2], head: [5, 6, -3],
  legL: { foot: [-.05, 0, 0], footRot: [0, 10, 0] }, legR: { foot: [-.12, .02, .015], footRot: [14, -5, 0] },
  armL: arm(22, 35, 85, { hand: 'fist', twist: 20 }), armR: arm(18, -15, 55, { fist: .4 }),
  face: { smile: .55, squint: .15 },
};
const grooveMid: Pose = {
  hips: [0, -.004, 0], hipsRot: [0, 0, 0], chest: [0, 0, 0], head: [-2, 0, 0],
  legL: stance(-.06), legR: stance(-.06), armL: arm(16, 10, 60, { fist: .4 }), armR: arm(16, 10, 60, { fist: .4 }),
  face: { smile: .45 },
};
export const GROOVE: Choreography = {
  id: 'groove', bpm: 112, beats: 4, loop: true,
  keys: [[0, grooveA], [1, grooveMid], [2, mirror(grooveA)], [3, grooveMid], [4, grooveA]],
  groove: bounce(.007, .5),
};

// Passinho do craque: pés rápidos em giro, joelho alto e braços de corrida.
const sambaA: Pose = {
  hips: [.03, -.045, .01], hipsRot: [4, 14, 5], chest: [6, -12, -3], head: [4, 10, 0],
  legL: { foot: [-.05, 0, .02], footRot: [0, 28, 0] }, legR: { foot: [-.04, .09, .05], footRot: [25, -10, 0], knee: 10 },
  armL: arm(28, -20, 100, { fist: .7 }), armR: arm(30, 35, 95, { fist: .7 }),
  face: { smile: .8, squint: .25 },
};
const sambaB: Pose = {
  hips: [-.01, -.05, 0], hipsRot: [4, -6, -2], chest: [5, 6, 2], head: [2, -4, 0],
  legL: { foot: [-.03, 0, -.03], footRot: [0, -18, 0] }, legR: { foot: [-.07, 0, .03], footRot: [0, 22, 0] },
  armL: arm(25, 10, 95, { fist: .7 }), armR: arm(25, 5, 95, { fist: .7 }),
  face: { smile: .9, grin: .3 },
};
export const SAMBA: Choreography = {
  id: 'samba', bpm: 128, beats: 4, loop: true,
  keys: [[0, sambaA], [1, sambaB], [2, mirror(sambaA)], [3, mirror(sambaB)], [4, sambaA]],
  groove: beat => ({ chest: [0, 0, 3 * Math.sin(beat * Math.PI * 4)], hips: [0, -.01 * Math.abs(Math.sin(beat * Math.PI)), 0] }),
};

// Curto-circuito: travas e poses rígidas, cabeça e braços em ângulos retos.
const robotHold = (b: number, p: Pose): [number, Pose][] => [[b, p], [b + .7, p]];
const r1: Pose = { hips: [0, -.03, 0], legL: stance(-.04, 0), legR: stance(-.04, 0), armL: arm(85, 0, 90, { twist: -90, hand: 'open', wrist: [0, 0, 0] }), armR: arm(85, 0, 90, { twist: 90, hand: 'open' }), head: [0, 35, 0], face: { brows_down: .3 } };
const r2: Pose = { hips: [0, -.03, 0], legL: stance(-.04, 0), legR: stance(-.04, 0), armL: arm(85, 0, 90, { twist: 90, hand: 'open' }), armR: arm(85, 0, 90, { twist: -90, hand: 'open' }), head: [0, -35, 0], face: { brows_down: .3 } };
const r3: Pose = { hips: [0, -.06, 0], legL: stance(-.04, 0), legR: stance(-.04, 0), chest: [0, 25, 0], armL: arm(10, 85, 0, { hand: 'open' }), armR: arm(10, 85, 0, { hand: 'open' }), head: [10, -25, 0], face: { mouth_open: .2 } };
const r4: Pose = { hips: [0, -.02, 0], legL: { foot: [-.04, .06, .02], footRot: [10, 0, 0] }, legR: stance(-.04, 0), chest: [0, -15, 0], armL: arm(90, 0, 0, { hand: 'open' }), armR: arm(90, 0, 0, { hand: 'open' }), head: [-10, 0, 0], face: { smile: .3 } };
export const ROBOT: Choreography = {
  id: 'robot', bpm: 100, beats: 8, loop: true,
  keys: [...robotHold(0, r1), ...robotHold(2, r2), ...robotHold(4, r3), ...robotHold(6, r4), [8, r1]],
};

// Baile da meia-noite: garras para o lado, ombros e passos arrastados.
const tA: Pose = {
  hips: [.04, -.035, 0], hipsRot: [0, 18, 0], chest: [8, 15, 10], head: [5, 20, 15],
  legL: { foot: [-.03, 0, .02], footRot: [0, 15, 0] }, legR: { foot: [-.1, .02, -.02], footRot: [10, 0, 0] },
  armL: arm(55, 55, 45, { hand: 'claw', wrist: [-35, 0, 0], twist: 10 }), armR: arm(35, 75, 55, { hand: 'claw', wrist: [-35, 0, 0] }),
  face: { mouth_open: .35, brows_up: .5 },
};
const tB: Pose = { ...tA, hips: [.02, -.05, 0], chest: [10, 15, 14], head: [10, 22, 22], armL: { ...tA.armL!, shrug: 18 }, armR: { ...tA.armR!, shrug: 18 }, face: { grin: .5, brows_down: .4 } };
export const THRILLER: Choreography = {
  id: 'thriller', bpm: 96, beats: 8, loop: true,
  keys: [[0, tA], [1, tB], [2, tA], [3, tB], [4, mirror(tA)], [5, mirror(tB)], [6, mirror(tA)], [7, mirror(tB)], [8, tA]],
};

// Aviãozinho: braços abertos, inclinação e voo em círculo.
const plane = (lean: number, yaw: number, step: 'L' | 'R'): Pose => ({
  hips: [lean * .002, -.04, 0], hipsRot: [8, yaw, 0], chest: [10, yaw * .3, lean], head: [-6, yaw * .4, lean * .4],
  legL: step === 'L' ? { foot: [-.04, .05, .06], footRot: [15, 0, 0] } : stance(-.06), legR: step === 'R' ? { foot: [-.04, .05, .06], footRot: [15, 0, 0] } : stance(-.06),
  armL: arm(86, -8, 6, { hand: 'open', wrist: [0, 0, 0] }), armR: arm(86, -8, 6, { hand: 'open' }),
  face: { smile: 1, mouth_open: .45, squint: .3 },
});
export const AIRPLANE: Choreography = {
  id: 'airplane', bpm: 110, beats: 4, loop: true,
  keys: [[0, plane(22, 25, 'L')], [1, plane(10, 0, 'R')], [2, plane(-22, -25, 'L')], [3, plane(-10, 0, 'R')], [4, plane(22, 25, 'L')]],
};

// Coração para a torcida.
const heart: Pose = {
  hips: [0, -.015, 0], chest: [-4, 0, 0], head: [6, 0, 6], legL: stance(), legR: stance(),
  armL: arm(28, 70, 118, { twist: 55, hand: 'claw', wrist: [20, 0, 0] }), armR: arm(28, 70, 118, { twist: 55, hand: 'claw', wrist: [20, 0, 0] }),
  face: { smile: .9, squint: .4 },
};
const pointCrowd: Pose = {
  hips: [.02, -.02, 0], hipsRot: [0, -10, 0], chest: [-3, -15, 0], head: [-4, -15, 0], legL: stance(), legR: stance(-.03),
  armL: arm(20, 5, 30, { fist: .3 }), armR: arm(55, 75, 5, { hand: 'point' }),
  face: { smile: 1, grin: .4, brows_up: .3 },
};
export const HEART: Choreography = {
  id: 'heart', bpm: 90, beats: 8, loop: true,
  keys: [[0, heart], [2.5, { ...heart, chest: [-6, 8, 0], head: [4, 8, 8] }], [3.5, heart], [4.5, pointCrowd], [6.5, { ...pointCrowd, armR: arm(60, 70, 5, { hand: 'point' }), hipsRot: [0, 10, 0], chest: [-3, 15, 0], head: [-4, 15, 0] }], [8, heart]],
};

// Silêncio na arena: dedo nos lábios, depois braços abertos.
const shh: Pose = {
  hips: [0, -.01, 0], chest: [-2, -6, 0], head: [8, -8, -6], legL: stance(), legR: stance(-.03),
  armL: arm(12, 0, 15, { fist: .3 }), armR: arm(52, 92, 124, { twist: -24, hand: 'point', wrist: [56, 23, 0] }),
  face: { pucker: .6, brows_down: .4, squint: .2 },
};
const open: Pose = {
  hips: [0, -.03, 0], chest: [-10, 0, 0], head: [-12, 0, 0], legL: stance(-.02), legR: stance(-.02),
  armL: arm(70, 10, 15, { hand: 'open', twist: -40 }), armR: arm(70, 10, 15, { hand: 'open', twist: -40 }),
  face: { smile: .9, mouth_open: .5, brows_up: .6 },
};
export const SHH: Choreography = {
  id: 'shh', bpm: 84, beats: 8, loop: true,
  keys: [[0, shh], [3, { ...shh, head: [10, 8, 6], chest: [-2, 6, 0] }], [4.5, open], [6.5, { ...open, chest: [-12, 0, 0], hips: [0, -.045, 0] }], [8, shh]],
};

// Muque do craque: duplo bíceps.
const flex = (t: number): Pose => ({
  hips: [0, -.025 - .01 * t, 0], chest: [-6 - 3 * t, 0, 0], head: [-4, 0, 0], legL: stance(-.02), legR: stance(-.02),
  armL: arm(88, -5, 110 + 15 * t, { twist: -95, hand: 'fist', shrug: 4 + 4 * t }), armR: arm(88, -5, 110 + 15 * t, { twist: -95, hand: 'fist', shrug: 4 + 4 * t }),
  face: { grin: .6 + .4 * t, squint: .4 + .3 * t, brows_down: .3 * t },
});
export const FLEX: Choreography = {
  id: 'flex', bpm: 80, beats: 4, loop: true,
  keys: [[0, flex(0)], [1, flex(1)], [2, { ...flex(.6), chest: [-6, 18, 0], head: [-4, 15, 0] }], [3, { ...flex(.6), chest: [-6, -18, 0], head: [-4, -15, 0] }], [4, flex(0)]],
};

// Soco no ar: agacha, salta e comemora.
const crouch: Pose = { hips: [0, -.14, .02], chest: [18, 0, 0], head: [-10, 0, 0], legL: stance(-.04), legR: stance(-.04), armL: arm(20, -30, 40, { fist: .8 }), armR: arm(20, -40, 50, { hand: 'fist' }), face: { brows_down: .5, mouth_open: .2 } };
const air: Pose = { hips: [0, .14, 0], chest: [-12, 0, 0], head: [-18, 0, 0], legL: { foot: [-.04, .16, -.02], footRot: [35, 0, 0] }, legR: { foot: [-.03, .22, -.06], footRot: [40, 0, 0] }, armL: arm(30, 10, 60, { hand: 'fist' }), armR: arm(170, 10, 5, { hand: 'fist' }), face: { mouth_open: 1, brows_up: .8, smile: .5 } };
const land: Pose = { hips: [0, -.08, 0], chest: [8, 0, 0], head: [-6, 0, 0], legL: stance(-.03), legR: stance(-.03), armL: arm(25, 20, 70, { hand: 'fist' }), armR: arm(150, 10, 25, { hand: 'fist' }), face: { grin: 1, mouth_open: .6, squint: .4 } };
export const JUMP: Choreography = {
  id: 'jump', bpm: 100, beats: 6, loop: true,
  keys: [[0, grooveMid], [1, crouch], [1.7, air], [2.4, land], [3.4, { ...land, armR: arm(160, 15, 20, { hand: 'fist' }) }], [4.4, { ...land, armR: arm(150, 10, 40, { hand: 'fist' }), hips: [0, -.03, 0] }], [6, grooveMid]],
};

export const CHOREOGRAPHIES: Record<string, Choreography> = {
  idle: IDLE, groove: GROOVE, samba: SAMBA, robot: ROBOT, thriller: THRILLER,
  airplane: AIRPLANE, heart: HEART, shh: SHH, flex: FLEX, jump: JUMP,
};
