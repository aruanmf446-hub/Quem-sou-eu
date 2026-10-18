import { useEffect, useRef, useState, type CSSProperties } from 'react';
import * as THREE from 'three';
import type { GLTF } from 'three/addons/loaders/GLTFLoader.js';
import { Avatar, AVATAR_BASE_URL, loadAvatarAsset } from './Avatar';
import { itemUrl } from './catalog';
import { SLOTS, type AvatarConfig } from './config';
import { AvatarStage, type CameraFocus, type StageMood } from './stage';
import './avatarView.css';

/** Peças já carregadas (para trocar na hora, sem tela de carregamento). */
const loaded = new Map<string, GLTF>();

export interface AvatarViewHandle {
  stage: AvatarStage;
  avatar: Avatar;
  /** Captura uma imagem do avatar (retrato para outras telas). */
  snapshot(width?: number, height?: number): string;
}

interface Props {
  config: AvatarConfig;
  motion?: string | null;
  playing?: boolean;
  speed?: number;
  focus?: CameraFocus;
  focusKey?: number;
  mood?: StageMood;
  autoRotate?: boolean;
  interactive?: boolean;
  className?: string;
  label?: string;
  onReady?: (h: AvatarViewHandle) => void;
  onLoading?: (pending: string[]) => void;
}

const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Avatar 3D completo dentro do jogo: carrega base e peças sob demanda, aplica
 * corpo/rosto/cores/roupas e toca danças. Usado no estúdio, no lobby e na partida.
 */
export function AvatarView({ config, motion = 'groove', playing = true, speed = 1, focus = 'full', focusKey = 0, mood = 'studio', autoRotate = false, interactive = true, className, label, onReady, onLoading }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const ctx = useRef<{ stage: AvatarStage; avatar: Avatar | null; applied: Partial<Record<string, string | null>>; token: number } | null>(null);
  const props = useRef({ config, motion, playing, speed });
  const focusRef = useRef(focus);
  focusRef.current = focus;
  props.current = { config, motion, playing, speed };
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [progress, setProgress] = useState(0);
  const [retry, setRetry] = useState(0);
  /** Troca de visual em andamento (peças baixadas / total). */
  const [swap, setSwap] = useState<{ done: number; total: number; first: boolean } | null>(null);

  useEffect(() => {
    const el = host.current!;
    let stage: AvatarStage;
    try { stage = new AvatarStage(el, { transparent: true, controls: interactive }); }
    catch { setStatus('error'); return; }
    stage.renderer.domElement.setAttribute('aria-label', label ?? 'Avatar 3D. Arraste para girar e use a roda do mouse ou o gesto de pinça para aproximar.');
    stage.renderer.domElement.setAttribute('role', 'img');
    const state = { stage, avatar: null as Avatar | null, applied: {} as Partial<Record<string, string | null>>, token: 0 };
    ctx.current = state;
    let disposed = false;
    setStatus('loading');
    const resize = new ResizeObserver(() => stage.resize(el.clientWidth, el.clientHeight));
    resize.observe(el);
    stage.resize(el.clientWidth, el.clientHeight);
    loadAvatarAsset(AVATAR_BASE_URL, r => !disposed && setProgress(Math.round(r * 100))).then(base => {
      if (disposed) return;
      const avatar = new Avatar(base);
      state.avatar = avatar;
      stage.scene.add(avatar.root);
      applyConfig(props.current.config, true);
      avatar.play(props.current.motion ?? 'idle', 0);
      setStatus('ready');
      onReady?.({ stage, avatar, snapshot: (w = 512, h = 640) => snapshot(stage, w, h, avatar) });
      if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__avatarStage = stage;
    }).catch(() => !disposed && setStatus('error'));
    const lookTarget = new THREE.Vector3(), trackPoint = new THREE.Vector3();
    let frame = 0, last = performance.now();
    const loop = (now: number) => {
      const dt = Math.min((now - last) / 1000, .05);
      last = now;
      const a = state.avatar;
      if (a) {
        a.mixer.timeScale = props.current.playing ? props.current.speed : 0;
        lookTarget.copy(stage.camera.position);
        a.lookAt(lookTarget);
        a.update(dt);
        const tracked = focusRef.current === 'face' ? 'Head' : focusRef.current === 'torso' ? 'Spine2' : null;
        if (tracked) {
          const bone = a.bones.get(tracked);
          if (bone) { a.root.updateMatrixWorld(); stage.track(bone.getWorldPosition(trackPoint)); }
        } else stage.track(null);
      }
      stage.render(dt, reduced());
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    const lost = (e: Event) => { e.preventDefault(); setStatus('error'); };
    stage.renderer.domElement.addEventListener('webglcontextlost', lost);
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      stage.renderer.domElement.removeEventListener('webglcontextlost', lost);
      state.avatar?.dispose();
      stage.dispose();
      ctx.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retry, interactive]);

  /**
   * Aplica a configuração de uma vez: primeiro baixa todas as peças novas (o visual atual
   * continua na tela, com a tela de carregamento por cima) e só então troca corpo, cores e
   * roupas no mesmo quadro. Assim nunca aparece um personagem misturado com outro.
   */
  function applyConfig(c: AvatarConfig, first = false) {
    const state = ctx.current;
    const avatar = state?.avatar;
    if (!state || !avatar) return;
    const token = ++state.token;
    const changed = SLOTS.filter(slot => first || state.applied[slot] !== (c.items[slot] ?? null));
    const ids = [...new Set(changed.map(slot => c.items[slot]).filter((id): id is string => !!id))];
    const missing = ids.filter(id => !loaded.has(id));
    const commit = (assets: Map<string, GLTF | null>) => {
      if (ctx.current !== state || token !== state.token) return;
      avatar.setShape(c);
      for (const slot of changed) {
        const id = c.items[slot] ?? null;
        const asset = id ? assets.get(id) : null;
        state.applied[slot] = id;
        if (id && !asset) { state.applied[slot] = undefined; avatar.equip(slot, null); continue; }
        avatar.equip(slot, id, asset ?? undefined);
      }
      avatar.setColors(c);
      // Reenquadra quando a altura do personagem muda (cabelos altos, chapéus, corpos diferentes).
      const height = Math.max(1.4, avatar.headHeight());
      const reframe = Math.abs(height - state.stage.height) > .03;
      state.stage.height = height;
      if (reframe && !first) state.stage.focus(focusRef.current, false);
      avatar.root.visible = true;
      setSwap(null);
      onLoading?.([]);
    };
    if (!missing.length) {
      // Tudo já está na memória: troca imediata (sliders, cores, peças já vistas).
      commit(new Map(ids.map(id => [id, loaded.get(id)!])));
      return;
    }
    if (first) avatar.root.visible = false;
    let done = ids.length - missing.length;
    setSwap({ done, total: ids.length, first });
    onLoading?.([...missing]);
    const assets = new Map<string, GLTF | null>();
    Promise.all(ids.map(id => loadAvatarAsset(itemUrl(id))
      .then(a => { loaded.set(id, a); assets.set(id, a); }, () => { assets.set(id, null); })
      .finally(() => {
        if (token !== state.token || !missing.includes(id)) return;
        done++;
        setSwap({ done, total: ids.length, first });
        onLoading?.(missing.filter(m => !assets.has(m)));
      }))).then(() => commit(assets));
  }

  useEffect(() => { applyConfig(config); }, [config]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (motion) ctx.current?.avatar?.play(motion); }, [motion, status]);
  useEffect(() => { ctx.current?.stage.setMood(mood); }, [mood, status]);
  useEffect(() => { const s = ctx.current?.stage; if (s) s.controls.autoRotate = autoRotate && !reduced(); }, [autoRotate, status]);
  const shown = useRef(false);
  useEffect(() => {
    const s = ctx.current?.stage, a = ctx.current?.avatar;
    if (!s) return;
    if (a) s.height = Math.max(1.4, a.headHeight());
    // Na primeira exibição a câmera já nasce enquadrada; depois, transições suaves.
    s.focus(focus, status !== 'ready' || !shown.current);
    if (status === 'ready') shown.current = true;
  }, [focus, focusKey, status]);

  const swapping = status === 'ready' && swap !== null;
  const pct = swap ? Math.round(swap.done / Math.max(1, swap.total) * 100) : 0;
  return <div className={`avatar-view ${status === 'ready' ? 'is-ready' : ''} ${swapping ? 'is-swapping' : ''} ${swapping && swap.first ? 'is-first' : ''} ${className ?? ''}`} ref={host}>
    {status === 'loading' && <div className="avatar-view-status" role="status"><span className="avatar-view-spinner" /><b>Preparando seu personagem</b><small>{progress ? `${progress}%` : 'Carregando modelo e materiais…'}</small></div>}
    {swapping && <div className="avatar-view-swap" role="status" aria-live="polite">
      <div className="avatar-view-swap-card">
        <span className="avatar-view-ring" style={{ '--p': pct } as CSSProperties}><em>{pct}%</em></span>
        <b>{swap.first ? 'Vestindo seu personagem' : 'Trocando o visual'}</b>
        <small>{swap.done} de {swap.total} {swap.total > 1 ? 'peças prontas' : 'peça pronta'}</small>
        <i className="avatar-view-bar"><i style={{ width: `${pct}%` }} /></i>
      </div>
    </div>}
    {status === 'error' && <div className="avatar-view-status" role="alert"><b>Não foi possível abrir o 3D</b><small>Verifique a conexão e a aceleração gráfica do navegador.</small><button type="button" onClick={() => setRetry(v => v + 1)}>Tentar novamente</button></div>}
  </div>;
}

function snapshot(stage: AvatarStage, w: number, h: number, avatar?: Avatar) {
  // Retrato de busto renderizado direto no canvas (mesma tonalização da tela), lido na mesma tarefa.
  const { renderer, scene, camera } = stage;
  const size = renderer.getSize(new THREE.Vector2());
  const ratio = renderer.getPixelRatio();
  const cam = new THREE.PerspectiveCamera(24, w / h, .05, 30);
  const head = avatar?.bones.get('Head');
  if (head) {
    avatar!.root.updateMatrixWorld(true);
    const target = head.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(0, .02, 0));
    cam.position.copy(target).add(new THREE.Vector3(.28, .04, 1.25));
    cam.lookAt(target.x, target.y - .08, target.z);
  } else {
    cam.copy(camera);
    cam.aspect = w / h;
  }
  cam.updateProjectionMatrix();
  renderer.setPixelRatio(1);
  renderer.setSize(w, h, false);
  renderer.render(scene, cam);
  const url = renderer.domElement.toDataURL('image/webp', .86);
  renderer.setPixelRatio(ratio);
  renderer.setSize(size.x, size.y, false);
  renderer.render(scene, camera);
  return url;
}
