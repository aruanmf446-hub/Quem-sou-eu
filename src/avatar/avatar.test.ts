import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { GLTFLoader, type GLTF } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { Avatar } from './Avatar';
import { BUNDLES, ITEMS, MOTIONS } from './catalog';
import { DEFAULT_BODY, DEFAULT_FACE, morphInfluences, sanitizeConfig, type AvatarConfig } from './config';
import { CHOREOGRAPHIES } from './dances';

// Texturas não são necessárias para validar geometria, rig e animação no Node:
// removemos as referências a imagens do JSON do GLB antes de decodificar.
function withoutTextures(bytes: Buffer): ArrayBuffer {
  const jsonLength = bytes.readUInt32LE(12);
  const json = JSON.parse(bytes.subarray(20, 20 + jsonLength).toString('utf8'));
  for (const m of json.materials ?? []) {
    for (const k of ['normalTexture', 'occlusionTexture', 'emissiveTexture']) delete m[k];
    if (m.pbrMetallicRoughness) { delete m.pbrMetallicRoughness.baseColorTexture; delete m.pbrMetallicRoughness.metallicRoughnessTexture; }
  }
  delete json.textures; delete json.images; delete json.samplers;
  json.extensionsUsed = (json.extensionsUsed ?? []).filter((e: string) => e !== 'EXT_texture_webp');
  json.extensionsRequired = (json.extensionsRequired ?? []).filter((e: string) => e !== 'EXT_texture_webp');
  let text = Buffer.from(JSON.stringify(json));
  text = Buffer.concat([text, Buffer.alloc((4 - text.length % 4) % 4, 0x20)]);
  const rest = bytes.subarray(20 + jsonLength);
  const header = Buffer.alloc(20);
  header.writeUInt32LE(0x46546c67, 0); header.writeUInt32LE(2, 4); header.writeUInt32LE(20 + text.length + rest.length, 8);
  header.writeUInt32LE(text.length, 12); header.writeUInt32LE(0x4e4f534a, 16);
  const out = Buffer.concat([header, text, rest]);
  return out.buffer.slice(out.byteOffset, out.byteOffset + out.byteLength);
}
const cache = new Map<string, Promise<GLTF>>();
function load(path: string): Promise<GLTF> {
  if (!cache.has(path)) cache.set(path, new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).parseAsync(withoutTextures(readFileSync(path)), ''));
  return cache.get(path)!;
}
const itemPath = (id: string) => `public/avatar/items/${id}.glb`;

function skinnedBounds(avatar: Avatar) {
  avatar.root.updateMatrixWorld(true);
  const box = new THREE.Box3(), p = new THREE.Vector3();
  avatar.model.traverse(o => {
    const m = o as THREE.SkinnedMesh;
    if (!m.isSkinnedMesh || !m.visible) return;
    m.skeleton.update();
    const pos = m.geometry.getAttribute('position');
    for (let i = 0; i < pos.count; i += 5) {
      m.getVertexPosition(i, p);
      p.applyMatrix4(m.matrixWorld);
      if (!Number.isFinite(p.x + p.y + p.z)) throw new Error(`Vértice inválido em ${m.name}`);
      box.expandByPoint(p);
    }
  });
  return box;
}

const config = (over: Partial<AvatarConfig> = {}): AvatarConfig => ({ ...structuredClone(BUNDLES[1].config), ...over });

describe('base do avatar', () => {
  it('tem esqueleto padrão Mixamo, morphs compartilhados e deltas de juntas', async () => {
    const base = await load('public/avatar/base.glb');
    const extras = base.scene.userData;
    expect(extras.bones).toContain('Hips');
    expect(extras.bones).toContain('LeftHandIndex3');
    expect(extras.bones.length).toBeGreaterThanOrEqual(54);
    expect(extras.morphs).toContain('body_feminine');
    expect(extras.morphs).toContain('expr_blink_l');
    expect(Object.keys(extras.jointDeltas.height_up_m)).toContain('Head');
    let skinned = 0;
    base.scene.traverse(o => { if ((o as THREE.SkinnedMesh).isSkinnedMesh) skinned++; });
    expect(skinned).toBeGreaterThan(20);
  });
});

describe('guarda-roupa modular', () => {
  const ids = ITEMS.map(i => i.id).filter(id => existsSync(itemPath(id)));
  it('todo item do catálogo tem um GLB publicado', () => {
    const missing = ITEMS.map(i => i.id).filter(id => !existsSync(itemPath(id)));
    expect(missing).toEqual([]);
  });
  it('não há GLB órfão fora do catálogo', () => {
    const files = readdirSync('public/avatar/items').filter(f => f.endsWith('.glb')).map(f => f.replace('.glb', ''));
    expect(files.filter(f => !ITEMS.some(i => i.id === f))).toEqual([]);
  });
  it.each(ids)('%s usa somente ossos do esqueleto compartilhado e declara o slot certo', async id => {
    const base = await load('public/avatar/base.glb');
    const item = await load(itemPath(id));
    const bones = new Set(base.scene.userData.bones as string[]);
    const slot = ITEMS.find(i => i.id === id)!.slot;
    expect(item.scene.userData.slot).toBe(slot);
    const regions = new Set(Object.keys(base.scene.userData.regions));
    for (const r of item.scene.userData.hides ?? []) expect(regions.has(r), `região ${r}`).toBe(true);
    item.scene.traverse(o => {
      const m = o as THREE.SkinnedMesh;
      if (!m.isSkinnedMesh) return;
      for (const b of m.skeleton.bones) expect(bones.has(b.name)).toBe(true);
      const names = Object.keys(m.morphTargetDictionary ?? {});
      for (const n of names) expect((base.scene.userData.morphs as string[])).toContain(n);
    });
  });
});

describe('montagem, proporções e animações', () => {
  it('veste o Camisa 10 completo e mantém o corpo inteiro coerente', async () => {
    const base = await load('public/avatar/base.glb');
    const avatar = new Avatar(base);
    const c = config();
    for (const [slot, id] of Object.entries(c.items)) if (id && existsSync(itemPath(id))) avatar.equip(slot, id, await load(itemPath(id)));
    avatar.setShape(c);
    avatar.setColors(c);
    avatar.update(0);
    const box = skinnedBounds(avatar);
    const size = box.getSize(new THREE.Vector3());
    expect(size.y).toBeGreaterThan(1.6);
    expect(size.y).toBeLessThan(2.1);
    expect(box.min.y).toBeGreaterThan(-.03);
    expect(box.min.y).toBeLessThan(.03);
  });

  it('altura e proporções movem as juntas sem tirar os pés do chão', async () => {
    const base = await load('public/avatar/base.glb');
    const tall = new Avatar(base), short = new Avatar(base);
    tall.setShape({ body: { ...DEFAULT_BODY, height: 1, legs: 1 }, face: DEFAULT_FACE });
    short.setShape({ body: { ...DEFAULT_BODY, height: -1, type: 1 }, face: DEFAULT_FACE });
    tall.update(0); short.update(0);
    const tb = skinnedBounds(tall), sb = skinnedBounds(short);
    expect(tb.max.y - sb.max.y).toBeGreaterThan(.12);
    for (const b of [tb, sb]) expect(Math.abs(b.min.y)).toBeLessThan(.04);
  });

  it.each(MOTIONS.map(m => m.id))('%s: mesma coreografia em corpos diferentes, sem poses inválidas', async id => {
    expect(CHOREOGRAPHIES[id]).toBeDefined();
    const base = await load('public/avatar/base.glb');
    const a = new Avatar(base), b = new Avatar(base);
    b.setShape({ body: { ...DEFAULT_BODY, type: 1, height: -.6, weight: .8 }, face: DEFAULT_FACE });
    const duration = CHOREOGRAPHIES[id].beats * 60 / CHOREOGRAPHIES[id].bpm;
    for (const t of [0, duration * .27, duration * .61]) {
      a.seek(id, t); b.seek(id, t);
      // Tronco e cabeça: mesma rotação; braços: mesma direção (ajuste de poucos graus às proporções).
      for (const name of ['Spine1', 'Head']) expect(a.bones.get(name)!.quaternion.angleTo(b.bones.get(name)!.quaternion)).toBeLessThan(2e-3);
      const dir = (av: Avatar, from: string, to: string) => {
        av.root.updateMatrixWorld(true);
        return av.bones.get(to)!.getWorldPosition(new THREE.Vector3()).sub(av.bones.get(from)!.getWorldPosition(new THREE.Vector3())).normalize();
      };
      for (const [from, to] of [['LeftArm', 'LeftForeArm'], ['RightForeArm', 'RightHand']]) expect(dir(a, from, to).angleTo(dir(b, from, to))).toBeLessThan(.05);
      // Pernas resolvidas nas proporções de cada corpo: joelho sempre à frente e pé no chão.
      for (const av of [a, b]) {
        av.root.updateMatrixWorld(true);
        for (const side of ['Left', 'Right']) {
          const [hip, knee, ankle] = ['UpLeg', 'Leg', 'Foot'].map(n => av.bones.get(side + n)!.getWorldPosition(new THREE.Vector3()));
          const u = (knee.y - hip.y) / (ankle.y - hip.y);
          expect(knee.z - (hip.z + (ankle.z - hip.z) * u)).toBeGreaterThan(-.005);
          expect(ankle.y).toBeGreaterThan(id === 'jump' ? .03 : .05);
        }
      }
      const box = skinnedBounds(a);
      expect(box.getSize(new THREE.Vector3()).y).toBeGreaterThan(1.1);
      expect(box.getSize(new THREE.Vector3()).x).toBeLessThan(2.4);
    }
    // A dança realmente move os membros.
    a.seek(id, duration * .3);
    const q1 = a.bones.get('LeftArm')!.quaternion.clone();
    a.seek(id, duration * .8);
    expect(a.bones.get('LeftArm')!.quaternion.angleTo(q1) + a.bones.get('Spine1')!.quaternion.angleTo(new THREE.Quaternion())).toBeGreaterThan(.02);
  });
});

describe('configuração do avatar', () => {
  it('converte sliders em morphs nomeados e nunca extrapola', () => {
    const inf = morphInfluences({ body: { ...DEFAULT_BODY, type: .5, muscle: 1, height: -2 }, face: { ...DEFAULT_FACE, shape: 'square', shapeAmount: .7, lips: -.4 } });
    expect(inf.body_feminine).toBe(.5);
    expect(inf.muscle_up_m).toBeCloseTo(.5);
    expect(inf.muscle_up_f).toBeCloseTo(.5);
    expect(inf.height_down_m).toBeCloseTo(.5);
    expect(inf.face_square).toBeCloseTo(.7);
    expect(inf.lips_thin).toBeCloseTo(.4);
  });
  it('sanitiza dados externos', () => {
    const c = sanitizeConfig({ body: { muscle: 9, type: -3 }, skinTone: 'javascript:alert(1)', items: { top: 'x', hair: 7 }, tints: { a: '#zzzzzz', b: '#112233' } }, BUNDLES[0].config);
    expect(c.body.muscle).toBe(1);
    expect(c.body.type).toBe(0);
    expect(c.skinTone).toBe(BUNDLES[0].config.skinTone);
    expect(c.items.top).toBe('x');
    expect(c.items.hair).toBe(BUNDLES[0].config.items.hair);
    expect(c.tints).toEqual({ b: '#112233' });
  });
});
