import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CHARACTERS, type AvatarLook } from '../data/characters';

interface Props { look: AvatarLook; playing?: boolean; speed?: number; rig?: boolean; }

/** Rigid meshes bound to a shared Bone hierarchy. Every outfit uses the same joints. */
export function CharacterStage({ look, playing = !window.matchMedia('(prefers-reduced-motion: reduce)').matches, speed = 1, rig = false }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const state = useRef({ look, playing, speed, rig });
  state.current = { look, playing, speed, rig };
  const [error, setError] = useState(false);
  useEffect(() => {
    const el = host.current!;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
    catch { setError(true); return; }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, .1, 100);
    camera.position.set(4.2, 3.1, 7);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.65, 0); controls.enableDamping = true;
    controls.enablePan = false; controls.minDistance = 4; controls.maxDistance = 11;
    controls.maxPolarAngle = Math.PI / 2; controls.update();
    scene.add(new THREE.HemisphereLight('#d9e4ff', '#483a69', 3));
    const key = new THREE.DirectionalLight('#fff2df', 4); key.position.set(3, 6, 5); scene.add(key);
    const rim = new THREE.DirectionalLight('#9b78ff', 5); rim.position.set(-3, 3, -3); scene.add(rim);
    const platform = new THREE.Mesh(new THREE.CylinderGeometry(1.35, 1.5, .14, 64), new THREE.MeshStandardMaterial({ color: '#26233c', metalness: .65, roughness: .3 }));
    platform.position.y = -.1; scene.add(platform);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(1.38, .025, 8, 80), new THREE.MeshBasicMaterial({ color: '#a493ff' }));
    ring.rotation.x = Math.PI / 2; ring.position.y = -.02; scene.add(ring);
    const root = new THREE.Bone(); root.position.y = 1.45; scene.add(root);
    function bone(parent: THREE.Bone, name: string, x: number, y: number, z = 0) {
      const b = new THREE.Bone(); b.name = name; b.position.set(x, y, z); parent.add(b); return b;
    }
    const spine = bone(root, 'spine', 0, .05);
    const head = bone(spine, 'head', 0, 1.05);
    const leftArm = bone(spine, 'upper_arm.L', -.48, .69);
    const rightArm = bone(spine, 'upper_arm.R', .48, .69);
    const leftElbow = bone(leftArm, 'forearm.L', 0, -.48);
    const rightElbow = bone(rightArm, 'forearm.R', 0, -.48);
    const leftLeg = bone(root, 'thigh.L', -.22, -.05);
    const rightLeg = bone(root, 'thigh.R', .22, -.05);
    const leftKnee = bone(leftLeg, 'shin.L', 0, -.62);
    const rightKnee = bone(rightLeg, 'shin.R', 0, -.62);
    const material = (color: string) => new THREE.MeshStandardMaterial({ color, roughness: .65 });
    const shirt = material(look.color), skin = material('#bd8058'), hair = material('#261b26');
    const trousers = material('#24243d'), white = material('#f2f0ff'), black = material('#171725'), red = material('#eb3753');
    function mesh(parent: THREE.Object3D, geometry: THREE.BufferGeometry, mat: THREE.Material, x: number, y: number, z = 0) {
      const m = new THREE.Mesh(geometry, mat); m.position.set(x, y, z); parent.add(m); return m;
    }
    const ball = (parent: THREE.Object3D, radius: number, mat: THREE.Material, x: number, y: number, z = 0) => mesh(parent, new THREE.SphereGeometry(radius, 20, 16), mat, x, y, z);
    mesh(spine, new THREE.CapsuleGeometry(.36, .39, 6, 20), shirt, 0, .42).scale.z = .72;
    ball(head, .32, skin, 0, 0).scale.y = 1.13;
    const hairCap = ball(head, .326, hair, 0, .14, -.04); hairCap.scale.set(1, .7, .95);
    for (const side of [-1, 1]) {
      ball(head, .045, black, side * .115, .025, .287);
      ball(head, .064, skin, side * .31, 0);
    }
    mesh(head, new THREE.BoxGeometry(.12, .025, .025), black, 0, -.15, .303);
    [leftArm, rightArm].forEach(a => {
      mesh(a, new THREE.CapsuleGeometry(.115, .23, 4, 12), shirt, 0, -.18);
      ball(a, .12, skin, 0, -.42);
    });
    [leftElbow, rightElbow].forEach(a => {
      mesh(a, new THREE.CapsuleGeometry(.09, .25, 4, 12), skin, 0, -.2);
      ball(a, .115, skin, 0, -.43);
    });
    [leftLeg, rightLeg].forEach(a => mesh(a, new THREE.CapsuleGeometry(.155, .34, 4, 12), trousers, 0, -.28));
    [leftKnee, rightKnee].forEach(a => {
      mesh(a, new THREE.CapsuleGeometry(.12, .30, 4, 12), trousers, 0, -.25);
      mesh(a, new THREE.BoxGeometry(.28, .18, .45), white, 0, -.56, .09);
    });
    const clown = new THREE.Group(); head.add(clown);
    ball(clown, .085, red, 0, -.035, .335);
    [-1, 1].forEach(s => {
      const tuft = ball(clown, .24, hair, s * .32, .13, -.06); tuft.scale.set(.65, 1.3, 1);
      mesh(clown, new THREE.ConeGeometry(.055, .23, 3), red, s * .115, .13, .307);
    });
    const buttons = new THREE.Group(); spine.add(buttons);
    [.2, .4, .6].forEach(y => ball(buttons, .065, red, 0, y, .29));
    const collar = mesh(buttons, new THREE.TorusGeometry(.28, .095, 8, 24), white, 0, .85); collar.rotation.x = Math.PI / 2;
    const rigHelper = new THREE.SkeletonHelper(root); rigHelper.visible = rig; scene.add(rigHelper);
    const resize = new ResizeObserver(() => {
      const w = el.clientWidth, h = el.clientHeight; if (!w || !h) return;
      renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
    }); resize.observe(el);
    let frame = 0, time = 0, previous = performance.now(), oldCharacter = '';
    function render(now: number) {
      const s = state.current; const dt = Math.min((now - previous) / 1000, .05); previous = now;
      if (s.playing) time += dt * s.speed;
      const c = CHARACTERS.find(c => c.id === s.look.character) ?? CHARACTERS[0];
      if (oldCharacter !== c.id) {
        skin.color.set(c.skin); hair.color.set(c.hair);
        clown.visible = buttons.visible = c.theme === 'clown';
        trousers.color.set(c.theme === 'football' ? '#234a9c' : c.theme === 'clown' ? '#8b899d' : '#24243d');
        oldCharacter = c.id;
      }
      shirt.color.set(s.look.color); root.scale.y = s.look.height; root.position.y = 1.45 * s.look.height;
      rigHelper.visible = s.rig;
      [root, spine, head, leftArm, rightArm, leftElbow, rightElbow, leftLeg, rightLeg, leftKnee, rightKnee].forEach(b => b.rotation.set(0, 0, 0));
      const t = time * 5, wave = Math.sin(t);
      root.position.y += .06 * Math.abs(wave); spine.rotation.z = wave * .12;
      head.rotation.y = Math.sin(t / 2) * .2;
      leftArm.rotation.z = -.2; rightArm.rotation.z = .2;
      if (s.look.dance === 'groove') {
        leftArm.rotation.x = wave * .55; rightArm.rotation.x = -wave * .55;
        leftElbow.rotation.x = rightElbow.rotation.x = -.6;
        leftLeg.rotation.x = -wave * .2; rightLeg.rotation.x = wave * .2;
      } else if (s.look.dance === 'samba') {
        root.rotation.y = Math.sin(t / 2) * .4;
        leftArm.rotation.z = -.7 - wave * .45; rightArm.rotation.z = .7 - wave * .45;
        leftElbow.rotation.x = rightElbow.rotation.x = -1;
        leftLeg.rotation.x = wave * .65; rightLeg.rotation.x = -wave * .65;
        leftKnee.rotation.x = Math.max(0, -wave) * .9; rightKnee.rotation.x = Math.max(0, wave) * .9;
      } else if (s.look.dance === 'robot') {
        const step = Math.round(Math.sin(t * .6) * 2) / 2;
        spine.rotation.z = step * .15; head.rotation.y = step * .6;
        leftArm.rotation.z = -1.4; rightArm.rotation.z = 1.4;
        leftElbow.rotation.x = step * 1.3; rightElbow.rotation.x = -step * 1.3;
        leftLeg.rotation.z = step * .2; rightLeg.rotation.z = step * .2;
      } else {
        leftArm.rotation.x = rightArm.rotation.x = -1.2;
        leftElbow.rotation.z = wave * .7; rightElbow.rotation.z = wave * .7;
        leftLeg.rotation.x = wave * .35; rightLeg.rotation.x = -wave * .35;
        root.rotation.y = Math.sin(t / 3) * .6;
      }
      controls.update(); renderer.render(scene, camera); frame = requestAnimationFrame(render);
    }
    frame = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(frame); resize.disconnect(); controls.dispose();
      scene.traverse(o => {
        if (o instanceof THREE.Mesh || o instanceof THREE.LineSegments) {
          o.geometry.dispose(); const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach(m => m.dispose());
        }
      });
      renderer.dispose(); renderer.domElement.remove();
    };
  }, []);
  return <div className="character-canvas" ref={host} role="img" aria-label="Personagem 3D articulado. Arraste para girar e use o scroll para aproximar.">{error && <p className="error">O 3D precisa de WebGL. Ative a aceleração gráfica do navegador.</p>}</div>;
}
