// Ferramenta de desenvolvimento: renderiza o avatar para validação visual automatizada.
import * as THREE from 'three';
import { Avatar, loadAvatarAsset, AVATAR_BASE_URL } from '../../../src/avatar/Avatar';
import { AvatarStage, type CameraFocus } from '../../../src/avatar/stage';
import { DEFAULT_BODY, DEFAULT_FACE, type AvatarConfig } from '../../../src/avatar/config';

const params = new URLSearchParams(location.search);
const host = document.getElementById('host')!;
const transparent = params.get('transparent') === '1';
const stage = new AvatarStage(host, { controls: false, pixelRatio: 1, transparent, background: transparent ? undefined : '#3a4152' });
if (transparent) stage.setFloorVisible(false);
stage.resize(host.clientWidth, host.clientHeight);
import { BUNDLE_BY_ID } from '../../../src/avatar/catalog';
const bundle = params.get('bundle') ? BUNDLE_BY_ID.get(params.get('bundle') as 'street') : null;
const cfg = bundle ? bundle.config : JSON.parse(params.get('cfg') ?? '{}');
const config: AvatarConfig = {
  v: 2, body: { ...DEFAULT_BODY, ...(cfg.body ?? {}) }, face: { ...DEFAULT_FACE, ...(cfg.face ?? {}) },
  skinTone: cfg.skinTone ?? '#a8714e', eyeColor: cfg.eyeColor ?? '#4a2c1a', hairColor: cfg.hairColor ?? '#24170f', hairTips: cfg.hairTips ?? null,
  items: cfg.items ?? {}, tints: cfg.tints ?? {}, dance: 'groove', celebration: 'airplane',
};
(async () => {
  const base = await loadAvatarAsset(AVATAR_BASE_URL);
  const avatar = new Avatar(base);
  stage.scene.add(avatar.root);
  for (const [slot, id] of Object.entries(config.items)) if (id) { try { avatar.equip(slot, id, await loadAvatarAsset(`/avatar/items/${id}.glb`)); } catch { console.warn('peça ausente', id); } }
  avatar.setShape(config);
  avatar.setColors(config);
  if (params.get('expr')) for (const kv of params.get('expr')!.split(',')) { const [k, v] = kv.split(':'); avatar.animatedExpression[k] = Number(v); }
  avatar.root.rotation.y = Number(params.get('rot') ?? 0);
  if (params.get('nobody')) avatar.model.traverse(o => { if (o.name.startsWith('body_')) o.visible = false; });
  stage.height = avatar.headHeight();
  avatar.root.updateMatrixWorld(true);
  const faceBone = avatar.bones.get('Head');
  if (faceBone) stage.faceCenterY = faceBone.getWorldPosition(new THREE.Vector3()).y - .02;
  stage.focus((params.get('view') ?? 'full') as CameraFocus, true);
  if (params.get('q')) for (const part of params.get('q')!.split(';')) {
    const [name, v] = part.split(':'); const [x, y, z] = v.split(',').map(Number);
    avatar.bones.get(name)!.quaternion.setFromEuler(new THREE.Euler(x * Math.PI / 180, y * Math.PI / 180, z * Math.PI / 180));
  }
  if (params.get('anim')) avatar.seek(params.get('anim')!, Number(params.get('t') ?? 0));
  avatar.update(0);
  const only = params.get('only');
  if (only) {
    const keepHead = params.get('keepHead') === '1', keepBody = params.get('keepBody') === '1';
    avatar.model.traverse(o => {
      if (!(o as THREE.Mesh).isMesh) return;
      const n = o.name;
      const head = /^body_head|^eye_.*_real|^lashes|^teeth|^tongue|^brows_/.test(n);
      o.visible = n.startsWith(only) || (keepHead && head) || (keepBody && o.visible && !n.startsWith('underwear'));
    });
  }
  if (params.get('fit')) {
    avatar.root.updateMatrixWorld(true);
    const box = new THREE.Box3();
    avatar.model.traverse(o => {
      if (!(o as THREE.Mesh).isMesh || !o.visible) return;
      if (only && params.get('fit') === 'item' && !o.name.startsWith(only)) return;
      const m = o as THREE.SkinnedMesh;
      if (m.isSkinnedMesh) m.computeBoundingBox();
      else m.geometry.computeBoundingBox();
      const b = (m.boundingBox ?? m.geometry.boundingBox)!.clone().applyMatrix4(m.matrixWorld);
      box.union(b);
    });
    stage.frameBox(box, Number(params.get('az') ?? .55), Number(params.get('el') ?? .12), Number(params.get('pad') ?? 1.18));
  }
  stage.render(0);
  stage.render(0);
  (window as any).__avatar = avatar;
  (window as any).__stage = stage;
  (window as any).__ready = true;
})().catch(e => { document.body.textContent = String(e.stack ?? e); (window as any).__ready = 'error'; });
