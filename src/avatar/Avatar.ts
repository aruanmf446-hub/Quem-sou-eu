import * as THREE from 'three';
import { GLTFLoader, type GLTF } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { clone as cloneSkinned } from 'three/addons/utils/SkeletonUtils.js';
import { morphInfluences, restExpression, type AvatarConfig } from './config';
import { applyHairTips, makeSkinMaterial, skinToneColors, type SkinUniforms } from './materials';
import { compile, PoseSolver, RestSkeleton, sampleFace, type CompiledClip } from './animation';
import { CHOREOGRAPHIES } from './dances';

let restSkeleton: RestSkeleton | null = null;
const grips = new Map<string, Map<string, THREE.Quaternion>>();
/** Rotações dos dedos para segurar um objeto (calculadas uma vez no esqueleto-padrão). */
function gripPose(kind: 'fist' | 'staff' | 'open', side: 'Right' | 'Left', base: GLTF) {
  const key = `${kind}:${side}`;
  let g = grips.get(key);
  if (!g) {
    restSkeleton ??= new RestSkeleton(base.scene);
    const solver = new PoseSolver(restSkeleton);
    const arm = { raise: 8, forward: 0, elbow: 12, hand: kind === 'open' ? 'open' as const : 'fist' as const, fist: kind === 'staff' ? .85 : 1 };
    solver.solve(side === 'Right' ? { armR: arm } : { armL: arm });
    g = new Map([...solver.out].filter(([n]) => n.startsWith(`${side}Hand`) && n !== `${side}Hand`));
    grips.set(key, g);
  }
  return g;
}
const compiled = new Map<string, CompiledClip>();
const MAX_CLIPS = 64;
/**
 * Clip da coreografia resolvido nas proporções de um esqueleto. Avatares com as mesmas
 * proporções compartilham o clip; a coreografia (poses-chave) é sempre a mesma.
 */
export function getClip(id: string, base: GLTF, rest?: RestSkeleton): CompiledClip | null {
  const choreo = CHOREOGRAPHIES[id];
  if (!choreo) return null;
  restSkeleton ??= new RestSkeleton(base.scene);
  const skeleton = rest ?? restSkeleton;
  const key = `${id}|${skeleton === restSkeleton ? 'base' : skeleton.signature()}`;
  let c = compiled.get(key);
  if (!c) {
    c = compile(choreo, skeleton, 30, restSkeleton.legLength());
    if (compiled.size >= MAX_CLIPS) compiled.delete(compiled.keys().next().value!);
    compiled.set(key, c);
  }
  return c;
}

export const AVATAR_BASE_URL = '/avatar/base.glb';
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const cache = new Map<string, Promise<GLTF>>();

/** Carrega (uma vez) um GLB do avatar. As instâncias compartilham geometria e texturas. */
export function loadAvatarAsset(url: string, onProgress?: (ratio: number) => void): Promise<GLTF> {
  let p = cache.get(url);
  if (!p) {
    p = loader.loadAsync(url, e => { if (e.total) onProgress?.(e.loaded / e.total); });
    p.catch(() => cache.delete(url));
    cache.set(url, p);
  }
  return p;
}

interface BaseExtras { morphs: string[]; jointDeltas: Record<string, Record<string, [number, number, number]>>; regions: Record<string, string[]>; bones: string[]; }
export interface ItemExtras { slot: string; hides?: string[]; tintable?: string[]; lift?: number; grip?: 'fist' | 'staff' | 'open'; hand?: 'Right' | 'Left'; }

interface Part { mesh: THREE.Mesh; item?: string; }
interface EquippedItem { id: string; slot: string; meshes: THREE.Mesh[]; hides: string[]; lift: number; grip?: ItemExtras['grip']; hand?: 'Right' | 'Left'; }

const EXPRESSIONS = ['expr_blink_l', 'expr_blink_r', 'expr_smile', 'expr_squint', 'expr_brows_up', 'expr_brows_down', 'expr_mouth_open', 'expr_pucker', 'expr_grin'] as const;
export type Expression = typeof EXPRESSIONS[number];

const tmpMatrix = new THREE.Matrix4();
const LASH_DARK = new THREE.Color('#0d0907');
const tmpInverseRoot = new THREE.Matrix4();

/**
 * Avatar montado a partir da base compartilhada + peças modulares.
 * Todas as peças usam o mesmo esqueleto e os mesmos nomes de morph, então
 * qualquer roupa, cabelo ou animação funciona em qualquer corpo criado.
 */
export class Avatar {
  readonly root = new THREE.Group();
  /** Recebe o deslocamento do quadril das animações; aplicado ao osso Hips a cada quadro. */
  readonly motion = new THREE.Object3D();
  private hipsBase = new THREE.Vector3();
  /** Esqueleto de repouso nas proporções atuais (as danças são resolvidas nele). */
  private skeletonRest: RestSkeleton | null = null;
  private retargetIn = -1;
  readonly model: THREE.Object3D;
  readonly bones = new Map<string, THREE.Bone>();
  readonly mixer: THREE.AnimationMixer;
  readonly expression: Record<string, number> = {};
  private extras: BaseExtras;
  private restLocal = new Map<string, THREE.Vector3>();
  private inverses = new Map<string, THREE.Matrix4>();
  private parts: Part[] = [];
  private regions = new Map<string, THREE.Mesh[]>();
  private equipped = new Map<string, EquippedItem>();
  private influences: Record<string, number> = {};
  private skinUniforms: SkinUniforms;
  private irisMaterials: THREE.MeshStandardMaterial[] = [];
  private skinMaterials: THREE.MeshPhysicalMaterial[] = [];
  private hairColor = new THREE.Color('#2a1c14');
  private hairTips = { value: new THREE.Color('#e8c27a') };
  private hairTipAmount = { value: 0 };
  private tintTargets = new Map<string, THREE.MeshStandardMaterial[]>();
  private groundOffset = 0;
  private blinkTimer = 2;
  private blinkPhase = -1;
  private lookTarget: THREE.Vector3 | null = null;

  private base: GLTF;
  private current: { id: string; action: THREE.AnimationAction; face: CompiledClip['face'] } | null = null;
  private fading: { action: THREE.AnimationAction; face: CompiledClip['face'] }[] = [];

  constructor(base: GLTF) {
    this.base = base;
    this.extras = base.scene.userData as BaseExtras;
    this.model = cloneSkinned(base.scene);
    this.model.name = 'AvatarModel';
    this.motion.name = 'AvatarMotion';
    this.root.name = 'Avatar';
    this.root.add(this.model, this.motion);
    this.mixer = new THREE.AnimationMixer(this.root);
    const tone = skinToneColors('#a8714e');
    this.skinUniforms = { tone: { value: tone.tone }, light: { value: tone.light }, scatter: { value: tone.scatter } };
    const skinMaterials = new Map<THREE.Material, THREE.Material>();
    this.model.traverse(o => {
      if ((o as THREE.Bone).isBone) {
        const bone = o as THREE.Bone;
        this.bones.set(bone.name, bone);
        this.restLocal.set(bone.name, bone.position.clone());
      }
      if ((o as THREE.Mesh).isMesh) {
        const mesh = o as THREE.Mesh;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.frustumCulled = false;
        const material = mesh.material as THREE.MeshStandardMaterial;
        if (material.userData.skin) {
          let skin = skinMaterials.get(material);
          if (!skin) { skin = makeSkinMaterial(material, this.skinUniforms); skinMaterials.set(material, skin); this.skinMaterials.push(skin as THREE.MeshPhysicalMaterial); }
          mesh.material = skin;
        } else if (material.userData.irisColor) {
          const iris = material.clone();
          if (material.userData.catchlight) {
            // Reflexo branco desenhado na textura (valores acima de 0,9) não recebe a cor da íris.
            iris.onBeforeCompile = shader => {
              shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>', `
#ifdef USE_MAP
  vec4 irisTexel = texture2D( map, vMapUv );
  float glint = smoothstep( 0.88, 0.97, irisTexel.r );
  diffuseColor.rgb = mix( diffuseColor.rgb * irisTexel.rgb, vec3( 1.0 ), glint );
  totalEmissiveRadiance += glint * 0.6;
#endif`).replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>');
            };
            iris.customProgramCacheKey = () => 'avatar-iris-glint';
          }
          mesh.material = iris;
          this.irisMaterials.push(iris as THREE.MeshStandardMaterial);
        } else if (material.userData.cornea) {
          const cornea = new THREE.MeshPhysicalMaterial({ transparent: true, opacity: .08, roughness: 0, metalness: 0, clearcoat: 1, clearcoatRoughness: 0, depthWrite: false, envMapIntensity: 1.6 });
          mesh.material = cornea;
          mesh.renderOrder = 2;
          mesh.castShadow = false;
        } else if (material.userData.hairColor === 'brows') {
          mesh.material = material.clone();
          (mesh.material as THREE.MeshStandardMaterial).depthWrite = false;
          mesh.castShadow = false;
          this.addTint('lashes', mesh.material as THREE.MeshStandardMaterial);
        }
        this.parts.push({ mesh });
        const region = mesh.userData.region as string | undefined;
        if (region) {
          const list = this.regions.get(region) ?? [];
          list.push(mesh);
          this.regions.set(region, list);
        }
      }
    });
    for (const name of this.bones.keys()) this.inverses.set(name, new THREE.Matrix4());
    // Todas as malhas da base passam a compartilhar as mesmas matrizes inversas.
    for (const { mesh } of this.parts) if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) this.adoptSkeleton(mesh as THREE.SkinnedMesh);
    this.recomputeBind();
  }

  private addTint(key: string, material: THREE.MeshStandardMaterial) {
    const list = this.tintTargets.get(key) ?? [];
    list.push(material);
    this.tintTargets.set(key, list);
  }

  private adoptSkeleton(mesh: THREE.SkinnedMesh) {
    const names = mesh.skeleton.bones.map(b => b.name);
    const bones = names.map(n => this.bones.get(n)!);
    if (bones.some(b => !b)) throw new Error(`Peça incompatível com o esqueleto: ${names.find(n => !this.bones.has(n))}`);
    // A compressão Meshopt embute a dequantização das posições nas matrizes inversas do arquivo
    // (IBM' = IBM * D). Recuperamos D com o primeiro osso em repouso e a usamos como bindMatrix,
    // para que todas as peças compartilhem as mesmas inversas do avatar.
    const src = mesh.skeleton;
    const root = src.bones[0];
    let top: THREE.Object3D = root;
    while (top.parent) top = top.parent;
    top.updateMatrixWorld(true);
    const dequant = root.matrixWorld.clone().premultiply(tmpInverseRoot.copy(top.matrixWorld).invert()).multiply(src.boneInverses[0]);
    const skeleton = new THREE.Skeleton(bones, names.map(n => this.inverses.get(n)!));
    mesh.bind(skeleton, dequant);
  }

  /** Atualiza posições de repouso das juntas para a proporção atual e recalcula o bind. */
  private recomputeBind() {
    const offsets = new Map<string, THREE.Vector3>();
    let ground = 0;
    for (const [morph, w] of Object.entries(this.influences)) {
      const deltas = this.extras.jointDeltas[morph];
      if (!deltas || !w) continue;
      for (const [bone, d] of Object.entries(deltas)) {
        if (bone === 'ground') { ground += d[1] * w; continue; }
        const v = offsets.get(bone) ?? new THREE.Vector3();
        v.x += d[0] * w; v.y += d[1] * w; v.z += d[2] * w;
        offsets.set(bone, v);
      }
    }
    const saved = new Map<string, THREE.Quaternion>();
    for (const [name, bone] of this.bones) {
      saved.set(name, bone.quaternion.clone());
      bone.quaternion.identity();
      const rest = this.restLocal.get(name)!;
      const own = offsets.get(name) ?? new THREE.Vector3();
      const parentOffset = bone.parent && (bone.parent as THREE.Bone).isBone ? offsets.get(bone.parent.name) ?? new THREE.Vector3() : new THREE.Vector3();
      bone.position.copy(rest).add(own).sub(parentOffset);
    }
    this.model.updateMatrixWorld(true);
    tmpInverseRoot.copy(this.model.matrixWorld).invert();
    for (const [name, bone] of this.bones) {
      tmpMatrix.multiplyMatrices(tmpInverseRoot, bone.matrixWorld);
      this.inverses.get(name)!.copy(tmpMatrix).invert();
      bone.quaternion.copy(saved.get(name)!);
    }
    this.groundOffset = -ground;
    this.hipsBase.copy(this.bones.get('Hips')!.position);
    // Esqueleto de repouso desta proporção (rotações identidade, referencial do modelo).
    for (const bone of this.bones.values()) bone.quaternion.identity();
    this.model.updateMatrixWorld(true);
    this.skeletonRest = new RestSkeleton(this.model, this.model);
    for (const [name, bone] of this.bones) bone.quaternion.copy(saved.get(name)!);
    // A dança em curso é refeita para o novo corpo (com pequeno atraso enquanto o slider é arrastado).
    if (this.current) this.retargetIn = .12;
    this.placeOnGround();
  }

  /** Corpo e rosto: aplica morphs em todas as peças e reposiciona as juntas. */
  setShape(config: Pick<AvatarConfig, 'body' | 'face'>) {
    this.influences = morphInfluences(config);
    this.rest = restExpression(config.face);
    for (const name of EXPRESSIONS) if (!name.startsWith('expr_blink')) this.expression[name] = Math.max(this.animatedExpression[name] ?? 0, this.rest[name] ?? 0);
    this.feminine = config.body.type;
    this.toon = (config.body.style ?? 0) >= .45;
    // Estilo animação: pele mais lisa (menos poros) e bochechas levemente coradas.
    const smooth = 1 - .8 * Math.min(1, Math.max(0, config.body.style ?? 0));
    for (const m of this.skinMaterials) {
      const base = (m.userData.baseNormalScale as THREE.Vector2 | undefined) ?? (m.userData.baseNormalScale = m.normalScale.clone());
      m.normalScale.copy(base).multiplyScalar(smooth);
    }
    this.recomputeBind();
    this.applyMorphs();
    this.updateVisibility();
  }

  private applyMorphs() {
    for (const { mesh } of this.parts) {
      const dict = mesh.morphTargetDictionary;
      const inf = mesh.morphTargetInfluences;
      if (!dict || !inf) continue;
      inf.fill(0);
      for (const [name, w] of Object.entries(this.influences)) { const i = dict[name]; if (i !== undefined) inf[i] = w; }
      for (const name of EXPRESSIONS) { const i = dict[name]; if (i !== undefined) inf[i] = this.expression[name] ?? 0; }
    }
  }

  setColors(config: Pick<AvatarConfig, 'skinTone' | 'eyeColor' | 'hairColor' | 'hairTips' | 'tints'>) {
    const tone = skinToneColors(config.skinTone);
    this.skinUniforms.tone.value.copy(tone.tone);
    this.skinUniforms.light.value.copy(tone.light);
    this.skinUniforms.scatter.value.copy(tone.scatter);
    for (const m of this.irisMaterials) m.color.set(config.eyeColor);
    this.hairColor.set(config.hairColor);
    this.hairTipAmount.value = config.hairTips ? 1 : 0;
    if (config.hairTips) this.hairTips.value.set(config.hairTips);
    for (const [key, materials] of this.tintTargets) {
      if (key === 'lashes') { for (const m of materials) m.color.copy(this.hairColor).lerp(LASH_DARK, .8); continue; }
      if (key.startsWith('hair:')) { for (const m of materials) m.color.copy(this.hairColor); continue; }
      const [item, part] = key.split(':');
      const tint = config.tints[`${item}:${part}`];
      for (const m of materials) m.color.set(tint ?? (m.userData.defaultColor as string) ?? '#ffffff');
    }
  }

  /** Equipa uma peça carregada. A peça é religada ao esqueleto deste avatar. */
  equip(slot: string, id: string | null, asset?: GLTF) {
    this.unequip(slot);
    if (!id || !asset) { this.updateVisibility(); return; }
    const scene = cloneSkinned(asset.scene);
    const extras = asset.scene.userData as ItemExtras;
    const meshes: THREE.Mesh[] = [];
    scene.traverse(o => { if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh); });
    for (const mesh of meshes) if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) this.adoptSkeleton(mesh as THREE.SkinnedMesh);
    for (const mesh of meshes) {
      mesh.removeFromParent();
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.frustumCulled = false;
      const src = mesh.material as THREE.MeshStandardMaterial;
      const material = src.clone();
      material.userData = { ...src.userData };
      mesh.material = material;
      const tint = material.userData.tint as string | undefined;
      if (material.userData.hair) {
        this.addTint(`hair:${id}`, material);
        if (material.userData.tips) applyHairTips(material, this.hairTips, this.hairTipAmount);
      } else if (material.userData.hairColor === 'brows') {
        this.addTint(`hair:brows:${id}`, material);
      } else if (tint) {
        material.userData.defaultColor = '#' + src.color.getHexString();
        this.addTint(`${id}:${tint}`, material);
      }
      if (material.userData.overlay) { material.polygonOffset = true; material.polygonOffsetFactor = -2; material.polygonOffsetUnits = -2; mesh.renderOrder = 1; }
      if (material.transparent) { material.depthWrite = false; mesh.castShadow = false; }
      mesh.position.set(0, 0, 0);
      mesh.quaternion.identity();
      mesh.scale.set(1, 1, 1);
      this.model.add(mesh);
      this.parts.push({ mesh, item: id });
    }
    // Compatibilidade com o GLB já publicado: o saiote cobre também o segundo
    // quarto da coxa. Sem essa região, a perna atravessa o tecido ao dançar.
    const hides = id === 'bottom_shendyt' ? [...new Set([...(extras.hides ?? []), 'thigh_b'])] : extras.hides ?? [];
    this.equipped.set(slot, { id, slot, meshes, hides, lift: extras.lift ?? 0, grip: extras.grip, hand: extras.hand });
    this.applyMorphs();
    this.updateVisibility();
  }

  unequip(slot: string) {
    const old = this.equipped.get(slot);
    if (!old) return;
    for (const mesh of old.meshes) {
      mesh.removeFromParent();
      (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).forEach(m => m.dispose());
    }
    this.parts = this.parts.filter(p => p.item !== old.id);
    for (const key of [...this.tintTargets.keys()]) if (key.startsWith(`${old.id}:`) || key === `hair:${old.id}` || key === `hair:brows:${old.id}`) this.tintTargets.delete(key);
    this.equipped.delete(slot);
  }

  equippedId(slot: string) { return this.equipped.get(slot)?.id ?? null; }

  private placeOnGround() {
    let lift = 0;
    for (const item of this.equipped.values()) lift = Math.max(lift, item.lift);
    this.model.position.y = this.groundOffset + lift;
  }

  private updateVisibility() {
    this.placeOnGround();
    const hidden = new Set<string>();
    for (const item of this.equipped.values()) item.hides.forEach(r => hidden.add(r));
    for (const [region, meshes] of this.regions) for (const m of meshes) m.visible = !hidden.has(region);
    // Máscaras que cobrem a cabeça inteira escondem também olhos, boca, cabelo e pelos.
    const headHidden = hidden.has('head');
    const faceSlots = new Set(['hair', 'brows', 'beard', 'eyewear']);
    for (const item of this.equipped.values()) if (faceSlots.has(item.slot)) item.meshes.forEach(m => { m.visible = !headHidden; });
    // Roupa íntima neutra da base: aparece só quando a peça correspondente não está vestida.
    for (const { mesh } of this.parts) {
      if (mesh.userData.eyeSet) mesh.visible = (mesh.userData.eyeSet === 'toon') === this.toon && !headHidden;
      if (/^(lashes|teeth|tongue)/.test(String(mesh.userData.layer ?? ''))) mesh.visible = !headHidden;
      if (mesh.userData.layer === 'underwear_bottom') mesh.visible = !this.equipped.has('bottom');
      if (mesh.userData.layer === 'underwear_top') mesh.visible = !this.equipped.has('top') && this.feminine > .3;
    }
  }

  private feminine = 0;
  private toon = false;

  lookAt(target: THREE.Vector3 | null) { this.lookTarget = target; }

  /** Toca uma dança/comemoração com transição suave. */
  play(id: string, fade = .35) {
    if (this.current?.id === id) return;
    const compiledClip = getClip(id, this.base, this.skeletonRest ?? undefined);
    if (!compiledClip) return;
    const action = this.mixer.clipAction(compiledClip.clip);
    action.reset().setEffectiveWeight(1).setEffectiveTimeScale(1).setLoop(THREE.LoopRepeat, Infinity).play();
    if (this.current) {
      this.current.action.crossFadeTo(action, fade, false);
      this.fading.push({ action: this.current.action, face: this.current.face });
    } else action.fadeIn(fade);
    this.current = { id, action, face: compiledClip.face };
  }

  /** Troca o clip em curso pelo resolvido nas proporções atuais, mantendo o tempo da dança. */
  private retarget() {
    this.retargetIn = -1;
    const cur = this.current;
    if (!cur) return;
    const next = getClip(cur.id, this.base, this.skeletonRest ?? undefined);
    if (!next || next.clip === cur.action.getClip()) return;
    const action = this.mixer.clipAction(next.clip);
    action.reset().setLoop(THREE.LoopRepeat, Infinity).play();
    action.time = cur.action.time;
    // O fade anterior será removido abaixo. Copiar seu peso parcial deixava
    // permanentemente o restante da pose misturado com a posição de repouso (T).
    action.setEffectiveWeight(1).setEffectiveTimeScale(1);
    for (const f of [cur, ...this.fading]) { f.action.stop(); this.mixer.uncacheAction(f.action.getClip()); }
    this.fading = [];
    this.current = { id: cur.id, action, face: next.face };
  }

  get playing() { return this.current?.id ?? null; }

  set speed(v: number) { this.mixer.timeScale = v; }

  /** Pose fixa num instante (prévias e miniaturas). */
  seek(id: string, time: number) {
    this.play(id, 0);
    if (this.retargetIn >= 0) this.retarget();
    this.mixer.update(0);
    if (this.current) { this.current.action.time = time; this.current.action.setEffectiveWeight(1); }
    this.fading.forEach(f => f.action.stop());
    this.fading = [];
    this.update(0);
  }

  /** Avança animação, piscadas e olhar. */
  update(dt: number) {
    if (this.retargetIn >= 0 && (this.retargetIn -= dt) <= 0) this.retarget();
    this.mixer.update(dt);
    const hips = this.bones.get('Hips');
    if (hips) hips.position.copy(this.motion.position).add(this.hipsBase);
    // Objeto na mão: os dedos seguram o cabo durante qualquer dança.
    for (const item of this.equipped.values()) {
      if (!item.grip) continue;
      for (const [name, q] of gripPose(item.grip, item.hand ?? 'Right', this.base)) this.bones.get(name)?.quaternion.copy(q);
    }
    this.blinkTimer -= dt;
    if (this.blinkTimer <= 0 && this.blinkPhase < 0) { this.blinkPhase = 0; this.blinkTimer = 2 + Math.random() * 3.5; }
    let blink = 0;
    if (this.blinkPhase >= 0) {
      this.blinkPhase += dt / .16;
      blink = Math.sin(Math.min(1, this.blinkPhase) * Math.PI);
      if (this.blinkPhase >= 1) this.blinkPhase = -1;
    }
    const base: Record<string, number> = { ...this.animatedExpression };
    for (const [name, v] of Object.entries(this.rest)) base[name] = Math.max(base[name] ?? 0, v);
    this.fading = this.fading.filter(f => f.action.getEffectiveWeight() > .001 && f.action.isRunning());
    for (const f of [...this.fading, ...(this.current ? [this.current] : [])]) sampleFace(f.face, f.action.time, base, f.action.getEffectiveWeight());
    for (const name of EXPRESSIONS) this.expression[name] = Math.min(1, base[name] ?? 0);
    this.expression.expr_blink_l = Math.max(this.expression.expr_blink_l, blink);
    this.expression.expr_blink_r = Math.max(this.expression.expr_blink_r, blink);
    this.applyMorphs();
    if (this.lookTarget) {
      for (const side of ['LeftEye', 'RightEye']) {
        const eye = this.bones.get(side);
        if (!eye) continue;
        eye.quaternion.identity();
        eye.updateMatrixWorld();
        const local = eye.worldToLocal(this.lookTarget.clone()).normalize();
        const yaw = THREE.MathUtils.clamp(Math.atan2(local.x, local.z), -.35, .35);
        const pitch = THREE.MathUtils.clamp(-Math.atan2(local.y, Math.hypot(local.x, local.z)), -.25, .25);
        eye.quaternion.setFromEuler(new THREE.Euler(pitch, yaw, 0, 'YXZ'));
      }
    }
  }

  /** Expressões definidas pela animação atual (atualizadas pelo controlador de danças). */
  animatedExpression: Record<string, number> = {};
  /** Expressão de repouso do personagem (sorriso, olhar, sobrancelhas). */
  private rest: Record<string, number> = {};

  /** Altura atual do topo da cabeça em metros (para enquadrar a câmera). */
  headHeight() {
    const head = this.bones.get('Head');
    if (!head) return 1.7;
    this.root.updateMatrixWorld(true);
    let top = head.getWorldPosition(new THREE.Vector3()).y + .2;
    // Cabelos altos e chapéus entram no enquadramento.
    for (const slot of ['hair', 'headwear']) {
      for (const mesh of this.equipped.get(slot)?.meshes ?? []) {
        if (!mesh.visible) continue;
        const m = mesh as THREE.SkinnedMesh;
        if (m.isSkinnedMesh) m.computeBoundingBox();
        else m.geometry.computeBoundingBox();
        const box = (m.isSkinnedMesh ? m.boundingBox : m.geometry.boundingBox)?.clone().applyMatrix4(m.matrixWorld);
        if (box && Number.isFinite(box.max.y)) top = Math.max(top, Math.min(box.max.y + .04, top + .45));
      }
    }
    return top - this.root.position.y;
  }

  dispose() {
    this.mixer.stopAllAction();
    this.root.removeFromParent();
    for (const slot of [...this.equipped.keys()]) this.unequip(slot);
    const materials = new Set<THREE.Material>();
    this.model.traverse(o => { if ((o as THREE.Mesh).isMesh) (Array.isArray((o as THREE.Mesh).material) ? (o as THREE.Mesh).material as THREE.Material[] : [(o as THREE.Mesh).material as THREE.Material]).forEach(m => materials.add(m)); });
    materials.forEach(m => m.dispose());
  }
}
