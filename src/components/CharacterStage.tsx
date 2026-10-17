import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { animateCharacter, type CharacterRig } from '../three/choreography';
import { CHARACTERS, type AvatarLook } from '../data/characters';

export type CameraView = 'full' | 'portrait' | 'back';
interface Props {
  look: AvatarLook;
  playing?: boolean;
  speed?: number;
  rig?: boolean;
  view?: CameraView;
  autoRotate?: boolean;
  environment?: 'studio' | 'arena' | 'midnight';
}
interface LoadedCharacter { root: THREE.Group; rig: CharacterRig; helper: THREE.SkeletonHelper; clothing: THREE.MeshStandardMaterial[]; }

function disposeObject(root: THREE.Object3D) {
  const materials = new Set<THREE.Material>(), geometries = new Set<THREE.BufferGeometry>(), skeletons = new Set<THREE.Skeleton>();
  root.traverse(object => {
    if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
      geometries.add(object.geometry);
      (Array.isArray(object.material) ? object.material : [object.material]).forEach(material => materials.add(material));
      if (object instanceof THREE.SkinnedMesh) skeletons.add(object.skeleton);
    }
  });
  skeletons.forEach(s => s.dispose());
  geometries.forEach(g => g.dispose());
  materials.forEach(m => m.dispose());
}

export function CharacterStage({ look, playing = !window.matchMedia('(prefers-reduced-motion: reduce)').matches, speed = 1, rig = false, view = 'full', autoRotate = false, environment = 'studio' }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const state = useRef({ look, playing, speed, rig, view, autoRotate, environment });
  state.current = { look, playing, speed, rig, view, autoRotate, environment };
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [progress, setProgress] = useState(0);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const el = host.current!;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' }); }
    catch { setStatus('error'); return; }
    let disposed = false;
    setStatus('loading'); setProgress(0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.domElement.setAttribute('aria-label', 'Provador 3D. Arraste para girar e use a roda do mouse para aproximar.');
    el.prepend(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, .05, 50);
    camera.position.set(.35, 1.22, 4.8);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.06, 0); controls.enableDamping = true; controls.dampingFactor = .08;
    controls.enablePan = false; controls.minDistance = 1.4; controls.maxDistance = 7;
    controls.minPolarAngle = .4; controls.maxPolarAngle = Math.PI / 2 + .04;
    controls.autoRotateSpeed = .8; controls.update();
    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const envMap = pmrem.fromScene(room, .04); scene.environment = envMap.texture;
    room.dispose(); pmrem.dispose();
    scene.add(new THREE.HemisphereLight('#c3d4ff', '#191a24', 1.2));
    const key = new THREE.DirectionalLight('#fff1de', 3.8); key.position.set(2.5, 4, 3); scene.add(key);
    key.castShadow = true; key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.left = -2; key.shadow.camera.right = 2; key.shadow.camera.top = 3; key.shadow.camera.bottom = -1;
    key.shadow.normalBias = .02; key.shadow.bias = -.0002; key.shadow.radius = 4;
    const fill = new THREE.DirectionalLight('#9ac9ff', 1.5); fill.position.set(-3, 2, 2); scene.add(fill);
    const rim = new THREE.SpotLight('#9e83ff', 30, 10, .6, .7, 1.4); rim.position.set(-1.4, 3, -2); scene.add(rim);
    const platformMat = new THREE.MeshStandardMaterial({ color: '#151d2c', roughness: .35, metalness: .6 });
    const platform = new THREE.Mesh(new THREE.CylinderGeometry(.73, .77, .09, 96), platformMat);
    platform.position.y = -.055; platform.receiveShadow = true; scene.add(platform);
    const ringMat = new THREE.MeshBasicMaterial({ color: '#abff69' });
    const ring = new THREE.Mesh(new THREE.TorusGeometry(.745, .006, 8, 128), ringMat);
    ring.rotation.x = Math.PI / 2; ring.position.y = -.015; scene.add(ring);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(100, 100), new THREE.ShadowMaterial({ color: '#000000', opacity: .24 }));
    floor.rotation.x = -Math.PI / 2; floor.position.y = -.103; floor.receiveShadow = true; scene.add(floor);
    const particlesGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(80 * 3);
    for (let i = 0; i < 80; i++) {
      // Deterministic arrangement avoids sparkle changing on every remount.
      positions[i * 3] = Math.sin(i * 39.43) * 3;
      positions[i * 3 + 1] = ((i * .137) % 1) * 4;
      positions[i * 3 + 2] = -1 - ((i * .319) % 1) * 3;
    }
    particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const particles = new THREE.Points(particlesGeometry, new THREE.PointsMaterial({ color: '#aec3ff', size: .008, transparent: true, opacity: .5, depthWrite: false })); scene.add(particles);
    const cache = new Map<string, LoadedCharacter>();
    const pending = new Set<string>();
    const failed = new Set<string>();
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    let active: LoadedCharacter | undefined, selected = '', lastView = '', lastEnvironment = '';
    function selectCharacter(id: string) {
      if (selected === id && active?.root.visible) return;
      const cached = cache.get(id);
      if (active) { active.root.visible = false; active.helper.visible = false; }
      if (cached) { active = cached; selected = id; active.root.visible = true; setStatus('ready'); return; }
      if (failed.has(id) || pending.has(id)) return;
      pending.add(id); setStatus('loading'); setProgress(0);
      loader.load(`/models/${id}.glb`, gltf => {
        pending.delete(id);
        if (disposed) { disposeObject(gltf.scene); return; }
        const bones: CharacterRig = new Map();
        const clothing: THREE.MeshStandardMaterial[] = [];
        gltf.scene.traverse(object => {
          if (object instanceof THREE.Bone) bones.set(object.name, { bone: object, rest: object.quaternion.clone(), position: object.position.clone() });
          if (object instanceof THREE.Mesh) {
            object.castShadow = object.receiveShadow = true; object.frustumCulled = false;
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            for (const material of materials) if (material instanceof THREE.MeshStandardMaterial && material.name === 'OutfitPrimary') clothing.push(material);
          }
        });
        gltf.scene.visible = false; scene.add(gltf.scene);
        const helper = new THREE.SkeletonHelper(gltf.scene); helper.visible = false; helper.renderOrder = 10;
        if (helper.material instanceof THREE.LineBasicMaterial) { helper.material.depthTest = false; helper.material.transparent = true; helper.material.opacity = .65; }
        scene.add(helper); cache.set(id, { root: gltf.scene, rig: bones, helper, clothing });
        if (state.current.look.character === id) selectCharacter(id);
      }, event => { if (!disposed && state.current.look.character === id && event.total) setProgress(Math.round(event.loaded / event.total * 100)); }, () => {
        pending.delete(id); failed.add(id);
        if (!disposed && state.current.look.character === id) setStatus('error');
      });
    }
    const resize = new ResizeObserver(() => {
      if (!el.clientWidth || !el.clientHeight) return;
      renderer.setSize(el.clientWidth, el.clientHeight);
      camera.aspect = el.clientWidth / el.clientHeight; camera.updateProjectionMatrix();
    }); resize.observe(el);
    let frame = 0, time = 0, previous = performance.now();
    let lastDance = '', blendTime = 1;
    const previousPose = new Map<string, { q: THREE.Quaternion; p: THREE.Vector3 }>();
    const targetQuaternion = new THREE.Quaternion();
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const cameraDestination = new THREE.Vector3(), targetDestination = new THREE.Vector3();
    let cameraTransition = 0;
    function render(now: number) {
      const s = state.current, dt = Math.min((now - previous) / 1000, .05); previous = now;
      if (s.playing) time += dt * s.speed;
      const characterId = CHARACTERS.some(c => c.id === s.look.character) ? s.look.character : 'street';
      selectCharacter(characterId);
      if (`${s.view}:${s.look.height}` !== lastView) {
        lastView = `${s.view}:${s.look.height}`; cameraTransition = 1;
        if (s.view === 'portrait') { cameraDestination.set(.05, 1.98 * s.look.height, 1.35); targetDestination.set(0, 1.94 * s.look.height, 0); }
        else if (s.view === 'back') { cameraDestination.set(.3, 1.3, -4.8); targetDestination.set(0, 1.05, 0); }
        else { cameraDestination.set(.35, 1.22, 4.8); targetDestination.set(0, 1.06, 0); }
      }
      if (cameraTransition > .005) {
        camera.position.lerp(cameraDestination, reducedMotion ? 1 : 1 - Math.exp(-dt * 7));
        controls.target.lerp(targetDestination, reducedMotion ? 1 : 1 - Math.exp(-dt * 7)); cameraTransition *= reducedMotion ? 0 : Math.exp(-dt * 7);
      }
      if (lastEnvironment !== s.environment) {
        lastEnvironment = s.environment;
        ringMat.color.set(s.environment === 'arena' ? '#68ffc8' : s.environment === 'midnight' ? '#ff5b71' : '#b4f76c');
        rim.color.set(s.environment === 'midnight' ? '#ff3c62' : s.environment === 'arena' ? '#4feec8' : '#a38bff');
        fill.color.set(s.environment === 'midnight' ? '#828dff' : '#9ac9ff');
      }
      if (active && selected === characterId) {
        active.root.scale.setScalar(s.look.height);
        const safeColor = /^#[0-9a-f]{6}$/i.test(s.look.color) ? s.look.color : '#8b6bfa';
        active.clothing.forEach(m => m.color.set(safeColor));
        if (lastDance !== s.look.dance) {
          previousPose.clear();
          for (const [name, joint] of active.rig) previousPose.set(name, { q: joint.bone.quaternion.clone(), p: joint.bone.position.clone() });
          blendTime = lastDance && !reducedMotion ? 0 : 1; lastDance = s.look.dance;
        }
        animateCharacter(active.rig, s.look.dance, time, s.look.height);
        if (blendTime < 1) {
          blendTime = Math.min(1, blendTime + dt / .32);
          const eased = blendTime * blendTime * (3 - 2 * blendTime);
          for (const [name, joint] of active.rig) {
            const old = previousPose.get(name); if (!old) continue;
            targetQuaternion.copy(joint.bone.quaternion);
            joint.bone.quaternion.copy(old.q).slerp(targetQuaternion, eased);
            joint.bone.position.lerpVectors(old.p, joint.bone.position, eased);
          }
        }
        active.helper.visible = s.rig;
      }
      controls.autoRotate = s.autoRotate;
      controls.update(); renderer.render(scene, camera); frame = requestAnimationFrame(render);
    }
    frame = requestAnimationFrame(render);
    const onContextLost = (event: Event) => { event.preventDefault(); setStatus('error'); };
    renderer.domElement.addEventListener('webglcontextlost', onContextLost);
    return () => {
      disposed = true; cancelAnimationFrame(frame); resize.disconnect(); controls.dispose();
      renderer.domElement.removeEventListener('webglcontextlost', onContextLost);
      scene.traverse(object => { if (object instanceof THREE.Light && 'shadow' in object) (object as THREE.DirectionalLight).shadow?.dispose(); });
      disposeObject(scene); envMap.dispose(); renderer.dispose(); renderer.domElement.remove();
    };
  }, [retry]);
  return <div className={`character-canvas ${status === 'ready' ? 'is-ready' : ''}`} ref={host}>
    {status === 'loading' && <div className="character-loading" role="status"><span className="character-loader" /><b>PREPARANDO PERSONAGEM</b><small>{progress ? `${progress}%` : 'Carregando modelo e materiais…'}</small></div>}
    {status === 'error' && <div className="character-loading" role="alert"><b>Não foi possível abrir o 3D</b><small>Verifique a conexão e a aceleração gráfica do navegador.</small><button onClick={() => setRetry(v => v + 1)}>Tentar novamente</button></div>}
  </div>;
}
