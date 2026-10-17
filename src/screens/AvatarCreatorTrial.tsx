import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import './avatarCreatorTrial.css';

const STUDIO_URL = 'https://three.ws/avatar-studio';
const MAX_GLB_BYTES = 25 * 1024 * 1024;

function validGlb(data: ArrayBuffer): boolean {
  return data.byteLength >= 12 && data.byteLength <= MAX_GLB_BYTES &&
    new DataView(data).getUint32(0, true) === 0x46546c67;
}

function ExternalAvatarPreview({ data }: { data: ArrayBuffer }) {
  const host = useRef<HTMLDivElement>(null);
  const mixer = useRef<THREE.AnimationMixer | null>(null);
  const actions = useRef<THREE.AnimationClip[]>([]);
  const [clips, setClips] = useState<string[]>([]);
  const [selectedClip, setSelectedClip] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    } catch {
      setError('Este navegador não conseguiu iniciar o visualizador 3D.');
      return;
    }
    setError('');
    setClips([]);
    setSelectedClip('');
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, 0.05, 100);
    camera.position.set(0, 0.1, 4);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    element.appendChild(renderer.domElement);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x394963, 2.5));
    const light = new THREE.DirectionalLight(0xfff1d9, 2.8);
    light.position.set(3, 5, 5);
    scene.add(light);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.minDistance = 1.6;
    controls.maxDistance = 8;
    let active = true;
    let root: THREE.Group | null = null;
    const clock = new THREE.Clock();
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    loader.parse(data.slice(0), '', gltf => {
      if (!active) return;
      root = gltf.scene;
      const box = new THREE.Box3().setFromObject(root);
      if (box.isEmpty()) { setError('O arquivo não contém uma malha 3D visível.'); return; }
      const height = box.getSize(new THREE.Vector3()).y;
      const largest = box.getSize(new THREE.Vector3()).length();
      const scale = 2.25 / Math.max(height, largest * 0.5, 0.01);
      root.scale.setScalar(scale);
      const centered = new THREE.Box3().setFromObject(root);
      root.position.sub(centered.getCenter(new THREE.Vector3()));
      scene.add(root);
      mixer.current = new THREE.AnimationMixer(root);
      actions.current = gltf.animations;
      setClips(gltf.animations.map((clip, i) => clip.name || 'Animação ' + (i + 1)));
      if (gltf.animations.length) {
        mixer.current.clipAction(gltf.animations[0]).play();
        setSelectedClip('0');
      }
    }, err => { if (active) setError('Não foi possível abrir este GLB: ' + String(err)); });

    const observer = new ResizeObserver(() => {
      if (!element.clientWidth || !element.clientHeight) return;
      renderer.setSize(element.clientWidth, element.clientHeight);
      camera.aspect = element.clientWidth / element.clientHeight;
      camera.updateProjectionMatrix();
    });
    observer.observe(element);
    let frame = 0;
    function draw() {
      frame = requestAnimationFrame(draw);
      mixer.current?.update(Math.min(clock.getDelta(), 0.05));
      controls.update();
      renderer.render(scene, camera);
    }
    draw();
    return () => {
      active = false;
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      mixer.current?.stopAllAction();
      mixer.current = null;
      actions.current = [];
      if (root) {
        const geometries = new Set<THREE.BufferGeometry>();
        const materials = new Set<THREE.Material>();
        root.traverse(node => {
          if (!(node instanceof THREE.Mesh)) return;
          geometries.add(node.geometry);
          (Array.isArray(node.material) ? node.material : [node.material]).forEach(mat => materials.add(mat));
        });
        geometries.forEach(geo => geo.dispose());
        materials.forEach(mat => mat.dispose());
      }
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [data]);

  function selectAnimation(value: string) {
    setSelectedClip(value);
    const player = mixer.current;
    if (!player) return;
    player.stopAllAction();
    if (value !== '' && actions.current[Number(value)]) player.clipAction(actions.current[Number(value)]).reset().play();
  }

  return <section className="avatar-trial-preview" aria-label="Prévia do avatar importado">
    <div className="avatar-trial-canvas" ref={host} />
    {error && <p className="avatar-trial-error" role="alert">{error}</p>}
    <div className="avatar-trial-animation">
      <label htmlFor="external-avatar-clip">Animação do próprio arquivo</label>
      <select id="external-avatar-clip" value={selectedClip} onChange={event => selectAnimation(event.target.value)}>
        <option value="">Parado</option>
        {clips.map((name, i) => <option key={i} value={String(i)}>{name}</option>)}
      </select>
      <small>{clips.length ? clips.length + ' animação(ões) encontrada(s).' : 'Sem animações embutidas. Ainda não há dança compartilhada neste teste.'}</small>
    </div>
  </section>;
}

interface Props {
  onClose: () => void;
}

/**
 * Teste isolado: nenhuma alteração em perfis, compras ou catálogo de produção.
 * O editor é de outro domínio. O handoff via postMessage depende do fornecedor.
 */
export function AvatarCreatorTrial({ onClose }: Props) {
  const iframe = useRef<HTMLIFrameElement>(null);
  const [bytes, setBytes] = useState<ArrayBuffer | null>(null);
  const [filename, setFilename] = useState('');
  const [message, setMessage] = useState('Escolha um avatar no editor ou carregue um GLB para conferir como ele aparece no jogo.');

  useEffect(() => {
    function receive(event: MessageEvent) {
      if (event.origin !== 'https://three.ws' || event.source !== iframe.current?.contentWindow) return;
      const payload = event.data;
      if (payload?.source !== 'characterstudio' || payload.type !== 'export') return;
      const glb = payload.glb;
      if (!(glb instanceof ArrayBuffer) || !validGlb(glb)) {
        setMessage('O editor respondeu, mas o arquivo GLB recebido é inválido ou excede 25 MB.');
        return;
      }
      setBytes(glb);
      setFilename('avatar-three-ws.glb');
      setMessage('Exportação recebida! Confira o personagem no visualizador de teste.');
    }
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, []);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_GLB_BYTES) {
      setMessage('Escolha um GLB com no máximo 25 MB para este teste.');
      event.target.value = '';
      return;
    }
    try {
      const buffer = await file.arrayBuffer();
      if (!validGlb(buffer)) throw new Error('Arquivo GLB inválido.');
      setBytes(buffer);
      setFilename(file.name);
      setMessage('Modelo carregado localmente. Nenhum arquivo foi enviado ao servidor.');
    } catch (err) {
      setMessage(String(err));
    }
    event.target.value = '';
  }

  function download() {
    if (!bytes) return;
    const url = URL.createObjectURL(new Blob([bytes], { type: 'model/gltf-binary' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename.endsWith('.glb') ? filename : 'avatar-teste.glb';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <main className="avatar-trial">
    <header className="avatar-trial-header">
      <div><span className="avatar-trial-eyebrow">LAB / TESTE INDEPENDENTE</span><h1>Criador de personagens</h1><p>Experimentar um editor pronto sem perder skins, moedas ou personagens atuais.</p></div>
      <button className="avatar-trial-close" type="button" onClick={onClose}>← Voltar ao estúdio</button>
    </header>
    <div className="avatar-trial-grid">
      <section className="avatar-trial-panel">
        <div className="avatar-trial-panel-head"><strong>01 / Experimente o editor</strong><a href={STUDIO_URL} target="_blank" rel="noopener noreferrer">Abrir em outra aba ↗</a></div>
        <iframe ref={iframe} title="Editor externo three.ws" src={STUDIO_URL} loading="lazy" referrerPolicy="no-referrer" allow="fullscreen" />
        <p className="avatar-trial-note">O conteúdo acima vem de <b>three.ws</b>, não do Quem Sou Eu. Se não abrir aqui, use “Abrir em outra aba”. O editor pode exigir conta para salvar e talvez não envie o modelo automaticamente ao jogo.</p>
      </section>
      <section className="avatar-trial-panel avatar-trial-import">
        <div className="avatar-trial-panel-head"><strong>02 / Confira no seu jogo</strong></div>
        {bytes ? <ExternalAvatarPreview data={bytes} /> :
          <div className="avatar-trial-placeholder"><span>3D</span><strong>Seu personagem aparece aqui</strong><small>Abra um arquivo GLB ou exporte do criador compatível para visualizar.</small></div>}
        <div className="avatar-trial-actions">
          <label className="avatar-trial-upload">Importar GLB para testar<input type="file" accept=".glb,model/gltf-binary" onChange={event => { void importFile(event); }} /></label>
          {bytes && <button type="button" onClick={download}>Baixar GLB testado ↓</button>}
        </div>
        <p role="status" className="avatar-trial-status">{message}</p>
      </section>
    </div>
    <footer className="avatar-trial-footer">Modo de demonstração: não salva no perfil, não compra itens e não substitui os modelos atuais. Venda de cosméticos e compatibilidade de danças ainda precisam ser validadas, inclusive as licenças dos assets.</footer>
  </main>;
}
