import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { TOON } from './materials';

export type StageMood = 'studio' | 'arena' | 'midnight';
export type CameraFocus = 'full' | 'face' | 'eye' | 'torso' | 'legs' | 'feet' | 'back';

const MOODS: Record<StageMood, { key: string; fill: string; rim: string; floor: string; accent: string; exposure: number; bg: string }> = {
  studio: { key: '#fff3e6', fill: '#e6eeff', rim: '#ffffff', floor: '#c9ccd3', accent: '#d9b46a', exposure: 1.12, bg: '#d6d8dd' },
  arena: { key: '#fff2de', fill: '#7fe7c6', rim: '#52f2c8', floor: '#0f2622', accent: '#5dffc5', exposure: 1.05, bg: '#0b1d1a' },
  midnight: { key: '#ffe6f0', fill: '#7d85ff', rim: '#ff6f92', floor: '#1d1426', accent: '#ff5b77', exposure: .98, bg: '#140d1c' },
};

/** Palco 3D reutilizável: estúdio, lobby e prévias usam a mesma luz e câmera. */
export class AvatarStage {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(28, 1, .05, 60);
  readonly controls: OrbitControls;
  // Luz de cinema de animação: chave quente e forte, preenchimento frio e baixo, dois recortes coloridos por trás.
  private key = new THREE.DirectionalLight('#ffffff', 2.1);
  private fill = new THREE.DirectionalLight('#ffffff', 1.35);
  private rim = new THREE.DirectionalLight('#ffffff', 1.1);
  private rim2 = new THREE.DirectionalLight('#ffffff', .7);
  private hemi = new THREE.HemisphereLight('#f4f6ff', '#8a7f78', .9);
  private floorMat = new THREE.MeshStandardMaterial({ color: '#1b2130', roughness: .42, metalness: .35 });
  private ringMat = new THREE.MeshBasicMaterial({ color: '#c6ff6a' });
  private envMap: THREE.Texture;
  private props: THREE.Object3D[] = [];
  private destination = { pos: new THREE.Vector3(0, 1.1, 5), target: new THREE.Vector3(0, 1, 0), t: 1 };
  height = 1.8;
  /** Altura do centro do rosto (osso Head), independente do topete ou chapéu. */
  faceCenterY = 1.57;
  private currentFocus: CameraFocus = 'full';

  private composer: EffectComposer | null = null;

  constructor(canvasHost: HTMLElement, opts: { transparent?: boolean; controls?: boolean; pixelRatio?: number; background?: string; effects?: boolean } = {}) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: !!opts.transparent, powerPreference: 'high-performance', preserveDrawingBuffer: false });
    const coarse = typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches;
    // Celulares: resolução e sombra um pouco menores para manter a fluidez das danças.
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, opts.pixelRatio ?? (coarse ? 1.5 : 2)));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.NeutralToneMapping;
    this.renderer.toneMappingExposure = 1;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    canvasHost.prepend(this.renderer.domElement);
    // Oclusão de ambiente em tela (dobras, encaixes, axilas, sob o chapéu), como nas artes de animação.
    // Fica de fora no celular para manter a fluidez das danças.
    if (opts.effects ?? !coarse) {
      try {
        const target = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
        this.composer = new EffectComposer(this.renderer, target);
        this.composer.addPass(new RenderPass(this.scene, this.camera));
        const gtao = new GTAOPass(this.scene, this.camera, 1, 1);
        gtao.blendIntensity = .3;
        gtao.updateGtaoMaterial({ radius: .10, distanceExponent: 1.4, thickness: .8, scale: 1.15, samples: 16, distanceFallOff: 1, screenSpaceRadius: false });
        gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 16 });
        this.composer.addPass(gtao);
        this.composer.addPass(new OutputPass());
      } catch { this.composer = null; }
    }
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const room = new RoomEnvironment();
    this.envMap = pmrem.fromScene(room, .035).texture;
    room.dispose();
    pmrem.dispose();
    this.scene.environment = this.envMap;
    if (opts.background) this.scene.background = new THREE.Color(opts.background);
    this.scene.environmentIntensity = .6;
    this.key.position.set(3.0, 3.4, 2.6);
    this.key.castShadow = true;
    this.key.shadow.mapSize.setScalar(coarse ? 1024 : 2048);
    Object.assign(this.key.shadow.camera, { left: -1.4, right: 1.4, top: 2.4, bottom: -.4, near: .5, far: 12 });
    this.key.shadow.bias = -.0004;
    this.key.shadow.normalBias = .015;
    this.key.shadow.radius = 8;
    this.fill.position.set(-3.0, 2.0, 3.2);
    this.rim.position.set(-2.2, 3.2, -3.4);
    this.rim2.position.set(2.6, 1.8, -2.8);
    this.scene.add(this.key, this.key.target, this.fill, this.rim, this.rim2, this.hemi);
    const floor = new THREE.Mesh(new THREE.CylinderGeometry(.82, .86, .06, 96), this.floorMat);
    floor.position.y = -.031;
    floor.receiveShadow = true;
    this.scene.add(floor);
    this.props.push(floor);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(.835, .005, 8, 160), this.ringMat);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = .001;
    this.scene.add(ring);
    this.props.push(ring);
    const shadowCatcher = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), new THREE.ShadowMaterial({ opacity: .18 }));
    shadowCatcher.rotation.x = -Math.PI / 2;
    shadowCatcher.position.y = -.062;
    shadowCatcher.receiveShadow = true;
    this.scene.add(shadowCatcher);
    this.props.push(shadowCatcher);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enabled = opts.controls !== false;
    this.controls.enableDamping = true;
    this.controls.dampingFactor = .09;
    this.controls.enablePan = false;
    this.controls.minDistance = .45;
    this.controls.maxDistance = 7.5;
    this.controls.minPolarAngle = .25;
    this.controls.maxPolarAngle = Math.PI / 2 + .05;
    this.controls.rotateSpeed = .8;
    this.controls.zoomSpeed = .9;
    this.controls.autoRotateSpeed = 1.6;
    this.controls.addEventListener('start', () => { this.destination.t = 1; });
    this.setMood('studio');
    this.focus('full', true);
  }

  /** Esconde plataforma e sombra (miniaturas com fundo transparente). */
  setFloorVisible(visible: boolean) { this.props.forEach(p => { p.visible = visible; }); }

  /** Enquadra uma caixa (miniaturas): azimute em radianos. */
  frameBox(box: THREE.Box3, azimuth = .55, elevation = .12, padding = 1.18) {
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z) * .5 * padding;
    const dist = radius / Math.sin(THREE.MathUtils.degToRad(this.camera.fov) / 2);
    const dir = new THREE.Vector3(Math.sin(azimuth) * Math.cos(elevation), Math.sin(elevation), Math.cos(azimuth) * Math.cos(elevation));
    this.controls.target.copy(center);
    this.camera.position.copy(center).addScaledVector(dir, dist);
    this.camera.near = Math.max(.01, dist / 50);
    this.camera.updateProjectionMatrix();
    this.destination.pos.copy(this.camera.position);
    this.destination.target.copy(center);
    this.destination.t = 1;
  }

  setMood(mood: StageMood) {
    const m = MOODS[mood];
    this.key.color.set(m.key);
    this.fill.color.set(m.fill);
    this.rim.color.set(m.rim);
    this.rim2.color.set(m.fill);
    this.floorMat.color.set(m.floor);
    this.ringMat.color.set(m.accent);
    this.renderer.toneMappingExposure = m.exposure;
    TOON.rimColor.value.set(m.rim);
  }

  focus(view: CameraFocus, instant = false) {
    this.currentFocus = view;
    this.follow = null;
    const h = this.height;
    const d = this.destination;
    const azimuth = view === 'back' ? Math.PI : .18;
    // Palco largo: aproxima o herói. Palco estreito mantém margem para dança e acessórios.
    const fitMultiplier = this.camera.aspect < .8 ? 2.78 : 2.4;
    const fullDistance = Math.max(fitMultiplier * h, h * .65 / (Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2) * this.camera.aspect));
    const frames: Record<CameraFocus, [number, number, number]> = {
      full: [h * .57, h * .54, fullDistance],
      back: [h * .57, h * .54, fullDistance],
      // O valor h inclui cabelo alto: NÃO o use para centralizar o rosto.
      // Distância suficiente para enquadrar sobrancelhas, olhos, nariz e boca.
      face: [this.faceCenterY - .045, this.faceCenterY - .045, 1.18],
      eye: [this.faceCenterY + .027, this.faceCenterY + .027, .62],
      torso: [h * .72, h * .7, 1.75],
      legs: [h * .32, h * .3, 2.1],
      feet: [h * .1, h * .06, 1.25],
    };
    const [camY, targetY, dist] = frames[view];
    d.target.set(0, targetY, 0);
    d.pos.set(Math.sin(azimuth) * dist, camY, Math.cos(azimuth) * dist);
    d.t = 0;
    if (instant) {
      this.camera.position.copy(d.pos);
      this.controls.target.copy(d.target);
      d.t = 1;
    }
  }

  /** Zoom relativo (botões e gestos): 1 = mantém, <1 aproxima. */
  zoom(factor: number) {
    const offset = this.camera.position.clone().sub(this.controls.target);
    const len = THREE.MathUtils.clamp(offset.length() * factor, this.controls.minDistance, this.controls.maxDistance);
    this.destination.pos.copy(this.controls.target).add(offset.setLength(len));
    this.destination.target.copy(this.controls.target);
    this.destination.t = 0;
  }

  rotate(radians: number) {
    const offset = this.camera.position.clone().sub(this.controls.target);
    offset.applyAxisAngle(new THREE.Vector3(0, 1, 0), radians);
    this.destination.pos.copy(this.controls.target).add(offset);
    this.destination.target.copy(this.controls.target);
    this.destination.t = 0;
  }

  resize(w: number, h: number) {
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    if (this.composer) { this.composer.setPixelRatio(this.renderer.getPixelRatio()); this.composer.setSize(w, h); }
    this.renderer.domElement.style.width = '100%';
    this.renderer.domElement.style.height = '100%';
    this.camera.aspect = w / h;
    // Em telas estreitas, abre o campo de visão para manter o corpo inteiro visível.
    this.camera.fov = w / h < .62 ? 34 : 28;
    this.camera.updateProjectionMatrix();
    this.focus(this.currentFocus, true);
  }

  private follow: THREE.Vector3 | null = null;
  private followOffset = new THREE.Vector3();
  /** Faz a câmera acompanhar um ponto (cabeça durante a dança) mantendo o enquadramento. */
  track(point: THREE.Vector3 | null) {
    if (!point) { this.follow = null; return; }
    if (!this.follow) { this.follow = point.clone(); this.followOffset.copy(this.destination.target).sub(point); return; }
    this.follow.copy(point);
  }

  render(dt: number, reducedMotion = false) {
    if (this.follow && this.destination.t >= 1) {
      const want = this.follow.clone().add(this.followOffset);
      const delta = want.sub(this.controls.target).multiplyScalar(reducedMotion ? 1 : 1 - Math.exp(-dt * 4));
      this.controls.target.add(delta);
      this.camera.position.add(delta);
    }
    const d = this.destination;
    if (d.t < 1) {
      const k = reducedMotion ? 1 : 1 - Math.exp(-dt * 6);
      this.camera.position.lerp(d.pos, k);
      this.controls.target.lerp(d.target, k);
      d.t = this.camera.position.distanceTo(d.pos) < .002 ? 1 : d.t;
    }
    this.controls.update(dt);
    if (this.composer) this.composer.render(dt);
    else this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.controls.dispose();
    this.envMap.dispose();
    this.scene.traverse(o => {
      if ((o as THREE.Mesh).isMesh && !(o as THREE.SkinnedMesh).isSkinnedMesh) {
        (o as THREE.Mesh).geometry.dispose();
        const m = (o as THREE.Mesh).material;
        (Array.isArray(m) ? m : [m]).forEach(x => x.dispose());
      }
    });
    this.key.shadow.map?.dispose();
    this.composer?.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
