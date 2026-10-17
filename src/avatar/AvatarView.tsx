import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Avatar, AVATAR_BASE_URL, loadAvatarAsset } from './Avatar';
import { itemUrl } from './catalog';
import { SLOTS, type AvatarConfig } from './config';
import { AvatarStage, type CameraFocus, type StageMood } from './stage';

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
      onReady?.({ stage, avatar, snapshot: (w = 512, h = 640) => snapshot(stage, w, h) });
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

  /** Aplica a configuração: forma, cores e troca apenas as peças que mudaram. */
  function applyConfig(c: AvatarConfig, first = false) {
    const state = ctx.current;
    const avatar = state?.avatar;
    if (!state || !avatar) return;
    avatar.setShape(c);
    avatar.setColors(c);
    const token = ++state.token;
    const pending: string[] = [];
    for (const slot of SLOTS) {
      const id = c.items[slot] ?? null;
      if (!first && state.applied[slot] === id) continue;
      state.applied[slot] = id;
      if (!id) { avatar.equip(slot, null); continue; }
      pending.push(id);
      loadAvatarAsset(itemUrl(id)).then(asset => {
        if (ctx.current !== state || state.applied[slot] !== id) return;
        avatar.equip(slot, id, asset);
        avatar.setColors(props.current.config);
      }).catch(() => {
        if (state.applied[slot] === id) state.applied[slot] = undefined;
      }).finally(() => {
        const i = pending.indexOf(id);
        if (i >= 0) pending.splice(i, 1);
        if (token === state.token) onLoading?.([...pending]);
      });
    }
    onLoading?.([...pending]);
    state.stage.height = Math.max(1.4, avatar.headHeight());
  }

  useEffect(() => { applyConfig(config); }, [config]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (motion) ctx.current?.avatar?.play(motion); }, [motion, status]);
  useEffect(() => { ctx.current?.stage.setMood(mood); }, [mood, status]);
  useEffect(() => { const s = ctx.current?.stage; if (s) s.controls.autoRotate = autoRotate && !reduced(); }, [autoRotate, status]);
  useEffect(() => {
    const s = ctx.current?.stage, a = ctx.current?.avatar;
    if (!s) return;
    if (a) s.height = Math.max(1.4, a.headHeight());
    s.focus(focus, status !== 'ready');
  }, [focus, focusKey, status]);

  return <div className={`avatar-view ${status === 'ready' ? 'is-ready' : ''} ${className ?? ''}`} ref={host}>
    {status === 'loading' && <div className="avatar-view-status" role="status"><span className="avatar-view-spinner" /><b>Preparando seu personagem</b><small>{progress ? `${progress}%` : 'Carregando modelo e materiais…'}</small></div>}
    {status === 'error' && <div className="avatar-view-status" role="alert"><b>Não foi possível abrir o 3D</b><small>Verifique a conexão e a aceleração gráfica do navegador.</small><button type="button" onClick={() => setRetry(v => v + 1)}>Tentar novamente</button></div>}
  </div>;
}

function snapshot(stage: AvatarStage, w: number, h: number) {
  // Renderiza direto no canvas (mesma tonalização da tela) e lê na mesma tarefa.
  const { renderer, scene, camera } = stage;
  const size = renderer.getSize(new THREE.Vector2());
  const ratio = renderer.getPixelRatio();
  const aspect = camera.aspect;
  renderer.setPixelRatio(1);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  const url = renderer.domElement.toDataURL('image/webp', .86);
  renderer.setPixelRatio(ratio);
  renderer.setSize(size.x, size.y, false);
  camera.aspect = aspect;
  camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  return url;
}
