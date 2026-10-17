import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { AvatarView, type AvatarViewHandle } from '../avatar/AvatarView';
import {
  BUNDLES, EYE_COLORS, HAIR_COLORS, ITEMS, ITEM_BY_ID, MOTIONS, OUTFIT_COLORS, REQUIRED_SLOTS, SKIN_TONES, SLOT_LABELS, thumbUrl,
  type Bundle, type CatalogItem, type Motion,
} from '../avatar/catalog';
import { DEFAULT_BODY, DEFAULT_FACE, type AvatarConfig, type BodyShape, type FaceConfig, type FaceShape, type Slot } from '../avatar/config';
import { cartFor, normalize, ownsItem, ownsMotion, resolveConfig, toLook } from '../avatar/ownership';
import type { CameraFocus, StageMood } from '../avatar/stage';
import { audio } from '../audio/music';
import { buy } from '../lib/economy';
import { getProfile, setProfile, useProfile, type SavedOutfit } from '../lib/profile';
import './avatarStudio.css';

type Tab = 'looks' | 'body' | 'face' | 'hair' | 'outfit' | 'shoes' | 'extras' | 'moves';
const TABS: { id: Tab; label: string; icon: IconName; focus: CameraFocus }[] = [
  { id: 'looks', label: 'Visuais', icon: 'star', focus: 'full' },
  { id: 'body', label: 'Corpo', icon: 'body', focus: 'full' },
  { id: 'face', label: 'Rosto', icon: 'face', focus: 'face' },
  { id: 'hair', label: 'Pele e cabelo', icon: 'hair', focus: 'face' },
  { id: 'outfit', label: 'Roupas', icon: 'shirt', focus: 'torso' },
  { id: 'shoes', label: 'Calçados', icon: 'shoe', focus: 'feet' },
  { id: 'extras', label: 'Acessórios', icon: 'spark', focus: 'face' },
  { id: 'moves', label: 'Danças', icon: 'music', focus: 'full' },
];
const SLOT_FOCUS: Partial<Record<Slot, CameraFocus>> = { top: 'torso', bottom: 'legs', socks: 'legs', shoes: 'feet', headwear: 'face', eyewear: 'face', neck: 'torso', wrist: 'torso', bodyart: 'torso', hands: 'torso', back: 'back', belt: 'torso', prop: 'full' };

type IconName = 'star' | 'body' | 'face' | 'hair' | 'shirt' | 'shoe' | 'spark' | 'music' | 'play' | 'pause' | 'plus' | 'minus' | 'left' | 'right' | 'spin' | 'back' | 'check' | 'undo' | 'save' | 'trash' | 'lock' | 'none' | 'legs' | 'feet' | 'torso' | 'close' | 'coin';
const ICONS: Record<IconName, string> = {
  star: 'M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7L12 3z',
  body: 'M12 2.5a2.5 2.5 0 110 5 2.5 2.5 0 010-5zM6 9.5l6 1.2 6-1.2M12 10.7v4.8M12 15.5l-3.2 6M12 15.5l3.2 6',
  face: 'M12 3c4 0 6.5 3 6.5 7.5S15.8 21 12 21s-6.5-6-6.5-10.5S8 3 12 3zM9.3 10.5h.01M14.7 10.5h.01M9.6 15.2c1.4 1.1 3.4 1.1 4.8 0',
  hair: 'M5 13c0-6 3.2-9 7-9s7 3 7 9M5 13c1.5-3 3.7-4.5 7-4.5s5.5 1.5 7 4.5M7.5 13v6M16.5 13v6',
  shirt: 'M8 3l4 2 4-2 5 4-3 3-2-1.5V21H8V8.5L6 10 3 7l5-4z',
  shoe: 'M3 16.5V10l5 1.5 3.5-3 9 6.5v1.5H3zM3 19h18',
  spark: 'M12 2v5M12 17v5M2 12h5M17 12h5M5 5l3 3M16 16l3 3M5 19l3-3M16 8l3-3',
  music: 'M9 18V5l11-2v13M9 18a3 3 0 11-6 0 3 3 0 016 0zM20 16a3 3 0 11-6 0 3 3 0 016 0z',
  play: 'M8 5l11 7-11 7V5z', pause: 'M8 5v14M16 5v14', plus: 'M12 5v14M5 12h14', minus: 'M5 12h14',
  left: 'M4 12a8 8 0 1014.2-5M18.5 3v4h-4', right: 'M20 12a8 8 0 11-14.2-5M5.5 3v4h4', spin: 'M3 12a9 3.5 0 1018 0 9 3.5 0 00-18 0M15 9.2l3 2.8-3 2.8',
  back: 'M12 3a3 3 0 110 6 3 3 0 010-6zM7 21v-5a5 5 0 0110 0v5', check: 'M5 12.5l4.5 4.5L19 7', undo: 'M9 14L4 9l5-5M4 9h10a6 6 0 010 12h-3',
  save: 'M5 3h11l3 3v15H5V3zM8 3v5h7V3M8 21v-7h8v7', trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3', lock: 'M7 11V8a5 5 0 0110 0v3M5 11h14v10H5z',
  none: 'M5 5l14 14M12 3a9 9 0 110 18 9 9 0 010-18z', legs: 'M8 3h8l1 8-2 10h-2l-1-8-1 8H9L7 11l1-8z', feet: 'M4 15h7l1-4h3l5 4v3H4v-3z',
  torso: 'M7 4h10l2 6-2 1v9H7v-9l-2-1 2-6z', close: 'M6 6l12 12M18 6L6 18', coin: 'M12 3a9 9 0 110 18 9 9 0 010-18zM12 7v10M9 9.5c0-1.2 1.4-2 3-2s3 .8 3 2-1.4 2-3 2-3 .8-3 2 1.4 2 3 2 3-.8 3-2',
};
function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={ICONS[name]} /></svg>;
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const FACE_SHAPES: { id: FaceShape; label: string }[] = [
  { id: 'natural', label: 'Natural' }, { id: 'oval', label: 'Oval' }, { id: 'round', label: 'Redondo' }, { id: 'square', label: 'Quadrado' }, { id: 'triangle', label: 'Triangular' },
];
const BODY_SLIDERS: { key: keyof BodyShape; label: string; min?: number; left: string; right: string }[] = [
  { key: 'style', label: 'Estilo', min: 0, left: 'Realista', right: 'Animação' },
  { key: 'type', label: 'Estrutura', min: 0, left: 'Masculina', right: 'Feminina' },
  { key: 'height', label: 'Altura', left: 'Baixa', right: 'Alta' },
  { key: 'muscle', label: 'Musculatura', left: 'Leve', right: 'Definida' },
  { key: 'weight', label: 'Massa', left: 'Esguia', right: 'Robusta' },
  { key: 'shoulders', label: 'Ombros', left: 'Estreitos', right: 'Largos' },
  { key: 'torso', label: 'Tronco', left: 'Reto', right: 'Em V' },
  { key: 'hips', label: 'Quadril', left: 'Estreito', right: 'Largo' },
  { key: 'legs', label: 'Pernas', left: 'Curtas', right: 'Longas' },
  { key: 'head', label: 'Cabeça', left: 'Menor', right: 'Maior' },
];
const FACE_GROUPS: { title: string; items: { key: keyof FaceConfig; label: string; left: string; right: string; min?: number }[] }[] = [
  { title: 'Estrutura', items: [
    { key: 'width', label: 'Largura', left: 'Fino', right: 'Largo' }, { key: 'jaw', label: 'Mandíbula', left: 'Suave', right: 'Marcada' },
    { key: 'chin', label: 'Queixo', left: 'Recuado', right: 'Projetado' }, { key: 'cheekbones', label: 'Maçãs do rosto', left: 'Baixas', right: 'Altas' },
    { key: 'faceLength', label: 'Comprimento', left: 'Curto', right: 'Comprido' }, { key: 'cheeks', label: 'Bochechas', left: 'Magras', right: 'Cheias' },
    { key: 'age', label: 'Idade aparente', left: 'Jovem', right: 'Madura' },
  ] },
  { title: 'Olhos', items: [
    { key: 'eyeSize', label: 'Tamanho', left: 'Menores', right: 'Maiores' }, { key: 'eyeDistance', label: 'Distância', left: 'Próximos', right: 'Afastados' },
    { key: 'eyeShape', label: 'Formato', left: 'Amendoados', right: 'Redondos' }, { key: 'eyeTilt', label: 'Inclinação', left: 'Para baixo', right: 'Para cima' },
    { key: 'browHeight', label: 'Altura da sobrancelha', left: 'Baixa', right: 'Alta' }, { key: 'browAngle', label: 'Ângulo da sobrancelha', left: 'Caído', right: 'Arqueado' },
  ] },
  { title: 'Nariz e boca', items: [
    { key: 'noseWidth', label: 'Largura do nariz', left: 'Fino', right: 'Largo' }, { key: 'noseLength', label: 'Comprimento do nariz', left: 'Curto', right: 'Longo' },
    { key: 'noseTip', label: 'Ponta do nariz', left: 'Para baixo', right: 'Arrebitada' }, { key: 'noseBridge', label: 'Perfil do nariz', left: 'Côncavo', right: 'Aquilino' },
    { key: 'lips', label: 'Lábios', left: 'Finos', right: 'Volumosos' }, { key: 'mouthWidth', label: 'Largura da boca', left: 'Estreita', right: 'Larga' },
    { key: 'mouthCorners', label: 'Cantos da boca', left: 'Caídos', right: 'Erguidos' },
  ] },
  { title: 'Expressão', items: [
    { key: 'smile', label: 'Sorriso', min: 0, left: 'Sério', right: 'Sorridente' }, { key: 'squint', label: 'Olhar', min: 0, left: 'Aberto', right: 'Semicerrado' },
    { key: 'browMood', label: 'Sobrancelhas', left: 'Franzidas', right: 'Erguidas' },
  ] },
  { title: 'Orelhas', items: [
    { key: 'ears', label: 'Tamanho', left: 'Pequenas', right: 'Grandes' }, { key: 'earShape', label: 'Pontas', min: 0, left: 'Redondas', right: 'Pontudas' },
  ] },
];

function Slider({ label, value, min = -1, left, right, onChange }: { label: string; value: number; min?: number; left: string; right: string; onChange: (v: number) => void }) {
  const pct = (value - min) / (1 - min) * 100;
  return <label className="as-slider" onDoubleClick={() => onChange(min < 0 ? 0 : 0)}>
    <span className="as-slider-head"><b>{label}</b><output>{Math.round(value * 100)}</output></span>
    <input type="range" min={min} max={1} step={.01} value={value} style={{ '--pct': `${pct}%` } as CSSProperties} onChange={e => onChange(Number(e.target.value))} aria-label={label} />
    <span className="as-slider-ends"><small>{left}</small><small>{right}</small></span>
  </label>;
}

function Swatches({ colors, value, onChange, label, custom = true }: { colors: string[]; value: string; onChange: (c: string) => void; label: string; custom?: boolean }) {
  return <div className="as-swatches" role="radiogroup" aria-label={label}>
    {colors.map(c => <button type="button" key={c} role="radio" aria-checked={value.toLowerCase() === c} aria-label={`${label} ${c}`} className={value.toLowerCase() === c ? 'on' : ''} style={{ '--c': c } as CSSProperties} onClick={() => onChange(c)}>{value.toLowerCase() === c && <Icon name="check" size={14} />}</button>)}
    {custom && <label className={`as-swatch-custom ${colors.includes(value.toLowerCase()) ? '' : 'on'}`} style={{ '--c': value } as CSSProperties} title="Cor personalizada"><Icon name="plus" size={14} /><input type="color" value={value} aria-label={`${label} personalizada`} onChange={e => onChange(e.target.value)} /></label>}
  </div>;
}

function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return <section className="as-section"><header><h3>{title}</h3>{aside}</header>{children}</section>;
}

export function AvatarStudio({ onPlay }: { onPlay?: () => void }) {
  const profile = useProfile();
  const equippedConfig = useMemo(() => resolveConfig(profile.avatar), [profile.avatar]);
  const [draft, setDraft] = useState<AvatarConfig>(equippedConfig);
  const [history, setHistory] = useState<AvatarConfig[]>([]);
  const [tab, setTab] = useState<Tab>('looks');
  const [outfitSlot, setOutfitSlot] = useState<Slot>('top');
  const [extraSlot, setExtraSlot] = useState<Slot>('headwear');
  const [focus, setFocus] = useState<CameraFocus>('full');
  const [focusKey, setFocusKey] = useState(0);
  const [motion, setMotion] = useState(draft.dance);
  const [playing, setPlaying] = useState(() => !window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [speed, setSpeed] = useState(1);
  const [spin, setSpin] = useState(false);
  const [mood, setMood] = useState<StageMood>('studio');
  const [modal, setModal] = useState<null | 'buy' | 'save'>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: 'ok' | 'error' | 'info' } | null>(null);
  const [loading, setLoading] = useState<string[]>([]);
  const [outfitName, setOutfitName] = useState('');
  const view = useRef<AvatarViewHandle | null>(null);

  const cart = useMemo(() => cartFor(profile, draft), [profile, draft]);
  const equipped = same(normalize(draft), equippedConfig);
  const accent = BUNDLES.find(b => Object.values(draft.items).some(id => id && ITEM_BY_ID.get(id)?.bundle === b.id && b.id !== 'street'))?.color ?? '#9b86ff';

  useEffect(() => { if (!message) return; const t = window.setTimeout(() => setMessage(null), 4200); return () => window.clearTimeout(t); }, [message]);

  function update(next: AvatarConfig | ((c: AvatarConfig) => AvatarConfig)) {
    setDraft(cur => {
      const value = normalize(typeof next === 'function' ? next(cur) : next);
      if (!same(value, cur)) setHistory(h => [...h.slice(-39), cur]);
      return value;
    });
  }
  const look = (f: CameraFocus) => { setFocus(f); setFocusKey(k => k + 1); };
  function chooseTab(t: Tab) {
    setTab(t);
    audio.sfx('click');
    const def = TABS.find(x => x.id === t)!;
    look(t === 'outfit' ? SLOT_FOCUS[outfitSlot] ?? 'torso' : t === 'extras' ? SLOT_FOCUS[extraSlot] ?? 'face' : def.focus);
    if (t === 'moves') setPlaying(true);
  }
  function equipItem(slot: Slot, id: string | null) {
    update(c => {
      const next = { ...c, items: { ...c.items, [slot]: id } };
      const item = id ? ITEM_BY_ID.get(id) : null;
      if (item?.suggestHair && slot === 'hair' && !c.items.hair) next.hairColor = item.suggestHair;
      return next;
    });
    if (SLOT_FOCUS[slot]) look(SLOT_FOCUS[slot]!);
  }
  function applyBundle(b: Bundle) {
    update({ ...structuredClone(b.config) });
    setMotion(b.config.dance);
    look('full');
    setMessage({ text: `${b.name} carregado. Ajuste o que quiser antes de equipar.`, tone: 'info' });
  }
  function undo() {
    setHistory(h => {
      if (!h.length) return h;
      setDraft(h[h.length - 1]);
      return h.slice(0, -1);
    });
  }

  async function equip() {
    setBusy(true);
    try {
      const p = getProfile();
      const c = cartFor(p, draft);
      if (c.total > p.coins) throw new Error(`Faltam ${c.total - p.coins} moedas. Ganhe moedas jogando partidas e fases da história.`);
      for (const b of c.bundles) await buy('character', b.id);
      for (const item of c.items) await buy('item', item.id);
      for (const m of c.motions) await buy('dance', m.id);
      const after = getProfile();
      const left = cartFor(after, draft);
      if (left.items.length || left.bundles.length || left.motions.length) throw new Error('Não foi possível confirmar todas as compras. Nada foi equipado.');
      let portrait: string | undefined;
      try { portrait = view.current?.snapshot(320, 400); } catch { portrait = undefined; }
      setProfile({ avatar: toLook(after, draft, after.avatar), ...(portrait ? { avatarPortrait: portrait } : {}) });
      setModal(null);
      audio.sfx('coin');
      setMessage({ text: c.total ? 'Compra concluída. Seu personagem está equipado!' : 'Personagem salvo e equipado!', tone: 'ok' });
    } catch (e) {
      setMessage({ text: (e as Error).message, tone: 'error' });
    } finally { setBusy(false); }
  }

  function saveOutfit() {
    const name = outfitName.trim() || `Visual ${profile.outfits.length + 1}`;
    const outfit: SavedOutfit = { id: `o-${Date.now().toString(36)}`, name: name.slice(0, 24), config: structuredClone(draft), updatedAt: Date.now() };
    setProfile(p => ({ outfits: [outfit, ...p.outfits].slice(0, 12) }));
    setModal(null);
    setOutfitName('');
    setMessage({ text: `“${outfit.name}” salvo em Meus visuais.`, tone: 'ok' });
  }

  function preview(m: Motion) {
    update(c => m.kind === 'dance' ? { ...c, dance: m.id } : { ...c, celebration: m.id });
    setMotion(m.id);
    setPlaying(true);
    look('full');
  }

  const itemCard = (item: CatalogItem | null, slot: Slot) => {
    const selected = (draft.items[slot] ?? null) === (item?.id ?? null);
    const owned = !item || ownsItem(profile, item.id);
    const isLoading = !!item && loading.includes(item.id);
    return <button type="button" key={item?.id ?? `none-${slot}`} className={`as-item ${selected ? 'on' : ''} ${item ? `r-${item.rarity}` : 'none'}`} aria-pressed={selected} onClick={() => equipItem(slot, item?.id ?? null)}>
      <span className="as-item-art">{item ? <img src={thumbUrl(item.id)} alt="" loading="lazy" onError={e => { e.currentTarget.style.visibility = 'hidden'; }} /> : <Icon name="none" size={30} />}{isLoading && <span className="as-item-loading" />}</span>
      <span className="as-item-name">{item ? item.name : 'Nenhum'}</span>
      <span className={`as-item-price ${owned ? 'owned' : ''}`}>{!item ? '—' : owned ? (item.price === 0 && !item.bundle ? 'Grátis' : 'Seu') : <><Icon name="coin" size={12} />{item.price}</>}</span>
      {selected && <span className="as-item-check"><Icon name="check" size={13} /></span>}
    </button>;
  };
  const slotGrid = (slot: Slot) => <div className="as-items">{!REQUIRED_SLOTS.includes(slot) && itemCard(null, slot)}{ITEMS.filter(i => i.slot === slot).map(i => itemCard(i, slot))}</div>;
  const tintEditor = (slot: Slot) => {
    const id = draft.items[slot];
    const item = id ? ITEM_BY_ID.get(id) : null;
    if (!item?.tints) return null;
    return Object.entries(item.tints).map(([part, def]) => <Section key={part} title={part === 'accent' ? 'Cor de destaque' : 'Cor da peça'}>
      <Swatches label="Cor" colors={OUTFIT_COLORS} value={draft.tints[`${item.id}:${part}`] ?? def} onChange={c => update(cur => ({ ...cur, tints: { ...cur.tints, [`${item.id}:${part}`]: c } }))} />
    </Section>);
  };
  const slotTabs = (slots: Slot[], value: Slot, set: (s: Slot) => void) => <div className="as-chips" role="tablist">{slots.map(s => <button type="button" role="tab" key={s} aria-selected={value === s} className={value === s ? 'on' : ''} onClick={() => { set(s); look(SLOT_FOCUS[s] ?? 'full'); }}>{SLOT_LABELS[s]}</button>)}</div>;

  const currentMotion = MOTIONS.find(m => m.id === motion) ?? MOTIONS[0];
  const bundleOwned = (b: Bundle) => b.price === 0 || profile.ownedCharacters.includes(b.id);

  return <div className="as-root" style={{ '--accent': accent } as CSSProperties}>
    <section className={`as-stage mood-${mood}`} aria-label="Personagem em 3D">
      <div className="as-stage-bg" aria-hidden="true"><i /><i /></div>
      <AvatarView config={draft} motion={motion} playing={playing} speed={speed} focus={focus} focusKey={focusKey} mood={mood} autoRotate={spin}
        onReady={h => { view.current = h; }} onLoading={setLoading} />
      <header className="as-stage-top">
        <div><span className="as-kicker">ESTÚDIO 3D</span><strong>Crie. Vista. Dance.</strong></div>
        {loading.length > 0 && <span className="as-loading-pill" role="status"><i />Vestindo {loading.length} {loading.length > 1 ? 'peças' : 'peça'}</span>}
      </header>
      <nav className="as-camera" aria-label="Câmera">
        {([['full', 'body', 'Corpo inteiro'], ['face', 'face', 'Rosto'], ['torso', 'torso', 'Tronco'], ['legs', 'legs', 'Pernas'], ['feet', 'feet', 'Pés'], ['back', 'back', 'Costas']] as const).map(([f, icon, l]) =>
          <button type="button" key={f} className={focus === f ? 'on' : ''} title={l} aria-label={l} aria-pressed={focus === f} onClick={() => look(f)}><Icon name={icon} /></button>)}
        <span />
        <button type="button" title="Aproximar" aria-label="Aproximar" onClick={() => view.current?.stage.zoom(.8)}><Icon name="plus" /></button>
        <button type="button" title="Afastar" aria-label="Afastar" onClick={() => view.current?.stage.zoom(1.25)}><Icon name="minus" /></button>
        <button type="button" title="Girar para a esquerda" aria-label="Girar para a esquerda" onClick={() => view.current?.stage.rotate(-Math.PI / 4)}><Icon name="left" /></button>
        <button type="button" title="Girar para a direita" aria-label="Girar para a direita" onClick={() => view.current?.stage.rotate(Math.PI / 4)}><Icon name="right" /></button>
        <button type="button" className={spin ? 'on' : ''} title="Giro 360°" aria-label="Giro 360°" aria-pressed={spin} onClick={() => setSpin(v => !v)}><Icon name="spin" /></button>
      </nav>
      <div className="as-hint" aria-hidden="true">Arraste para girar · role ou faça pinça para zoom</div>
      <footer className="as-player">
        <button type="button" className="as-play" onClick={() => setPlaying(v => !v)} aria-label={playing ? 'Pausar animação' : 'Reproduzir animação'}><Icon name={playing ? 'pause' : 'play'} size={20} /></button>
        <div className="as-player-info"><small>{currentMotion.kind === 'dance' ? 'DANÇA' : 'COMEMORAÇÃO'}</small><b>{currentMotion.name}</b></div>
        <div className="as-player-motions">
          <button type="button" className={motion === draft.dance ? 'on' : ''} onClick={() => { setMotion(draft.dance); setPlaying(true); }}>Dança</button>
          <button type="button" className={motion === draft.celebration ? 'on' : ''} onClick={() => { setMotion(draft.celebration); setPlaying(true); }}>Comemoração</button>
        </div>
        <label className="as-speed"><span>Ritmo</span><select value={speed} onChange={e => setSpeed(Number(e.target.value))} aria-label="Velocidade da animação"><option value={.5}>0,5×</option><option value={1}>1×</option><option value={1.5}>1,5×</option></select></label>
        <div className="as-moods" role="radiogroup" aria-label="Cenário">{(['studio', 'arena', 'midnight'] as const).map(m => <button type="button" role="radio" aria-checked={mood === m} key={m} className={`m-${m} ${mood === m ? 'on' : ''}`} title={{ studio: 'Estúdio', arena: 'Arena', midnight: 'Meia-noite' }[m]} aria-label={{ studio: 'Estúdio', arena: 'Arena', midnight: 'Meia-noite' }[m]} onClick={() => setMood(m)} />)}</div>
      </footer>
    </section>

    <aside className="as-panel" aria-label="Editor do personagem">
      <nav className="as-tabs" role="tablist" aria-label="Categorias">{TABS.map(t => <button type="button" role="tab" key={t.id} aria-selected={tab === t.id} className={tab === t.id ? 'on' : ''} onClick={() => chooseTab(t.id)}><Icon name={t.icon} /><span>{t.label}</span></button>)}</nav>
      <div className="as-panel-body">
        {tab === 'looks' && <>
          <Section title="Personagens originais">
            <div className="as-bundles">{BUNDLES.map(b => <button type="button" key={b.id} className={`as-bundle b-${b.id}`} style={{ '--bc': b.color } as CSSProperties} onClick={() => applyBundle(b)}>
              <img src={thumbUrl(`bundle_${b.id}`)} alt="" loading="lazy" onError={e => { e.currentTarget.style.visibility = 'hidden'; }} />
              <span className="as-bundle-info"><b>{b.name}</b><small>{b.subtitle}</small></span>
              <span className={`as-item-price ${bundleOwned(b) ? 'owned' : ''}`}>{bundleOwned(b) ? 'Seu' : <><Icon name="coin" size={12} />{b.price}</>}</span>
            </button>)}</div>
            <p className="as-note">Os personagens originais trazem o visual completo. Peças avulsas podem ser compradas separadamente.</p>
          </Section>
          <Section title="Meus visuais" aside={<button type="button" className="as-link" onClick={() => setModal('save')}><Icon name="save" size={15} />Salvar atual</button>}>
            {profile.outfits.length === 0 ? <p className="as-empty">Monte combinações e salve aqui para trocar em um toque.</p> :
              <ul className="as-outfits">{profile.outfits.map(o => <li key={o.id}>
                <button type="button" className="as-outfit-load" onClick={() => { update(normalize(o.config)); setMotion(o.config.dance); look('full'); }}>
                  <b>{o.name}</b><small>{Object.values(o.config.items).filter(Boolean).map(id => ITEM_BY_ID.get(id!)?.name).filter(Boolean).slice(0, 3).join(' · ')}</small></button>
                <button type="button" className="as-icon-btn" aria-label={`Excluir ${o.name}`} onClick={() => setProfile(p => ({ outfits: p.outfits.filter(x => x.id !== o.id) }))}><Icon name="trash" size={16} /></button>
              </li>)}</ul>}
          </Section>
        </>}

        {tab === 'body' && <Section title="Proporções" aside={<button type="button" className="as-link" onClick={() => update(c => ({ ...c, body: { ...DEFAULT_BODY, type: c.body.type, style: c.body.style } }))}>Redefinir</button>}>
          {BODY_SLIDERS.map(s => <Slider key={s.key} label={s.label} min={s.min} left={s.left} right={s.right} value={draft.body[s.key]} onChange={v => update(c => ({ ...c, body: { ...c.body, [s.key]: v } }))} />)}
        </Section>}

        {tab === 'face' && <>
          <Section title="Formato do rosto" aside={<button type="button" className="as-link" onClick={() => update(c => ({ ...c, face: { ...DEFAULT_FACE } }))}>Redefinir</button>}>
            <div className="as-chips">{FACE_SHAPES.map(f => <button type="button" key={f.id} className={draft.face.shape === f.id ? 'on' : ''} aria-pressed={draft.face.shape === f.id} onClick={() => update(c => ({ ...c, face: { ...c.face, shape: f.id } }))}>{f.label}</button>)}</div>
            {draft.face.shape !== 'natural' && <Slider label="Intensidade" min={0} left="Sutil" right="Marcante" value={draft.face.shapeAmount} onChange={v => update(c => ({ ...c, face: { ...c.face, shapeAmount: v } }))} />}
          </Section>
          {FACE_GROUPS.map(g => <Section key={g.title} title={g.title}>{g.items.map(s => <Slider key={s.key} label={s.label} min={s.min} left={s.left} right={s.right} value={draft.face[s.key] as number} onChange={v => update(c => ({ ...c, face: { ...c.face, [s.key]: v } }))} />)}</Section>)}
          <Section title="Cor dos olhos"><Swatches label="Olhos" colors={EYE_COLORS} value={draft.eyeColor} onChange={c => update(cur => ({ ...cur, eyeColor: c }))} /></Section>
        </>}

        {tab === 'hair' && <>
          <Section title="Tom de pele"><Swatches label="Pele" colors={SKIN_TONES} value={draft.skinTone} onChange={c => update(cur => ({ ...cur, skinTone: c }))} /></Section>
          <Section title="Cabelo">{slotGrid('hair')}</Section>
          <Section title="Cor do cabelo"><Swatches label="Cabelo" colors={HAIR_COLORS} value={draft.hairColor} onChange={c => update(cur => ({ ...cur, hairColor: c }))} /></Section>
          <Section title="Pontas descoloridas" aside={<label className="as-toggle"><input type="checkbox" checked={!!draft.hairTips} onChange={e => update(c => ({ ...c, hairTips: e.target.checked ? '#e2bf7a' : null }))} /><span>{draft.hairTips ? 'Ligado' : 'Desligado'}</span></label>}>
            {draft.hairTips && <Swatches label="Pontas" colors={['#e2bf7a', '#f3e2b8', '#d9481c', '#7c5ce0', '#2f7ad8', '#e8e8e8']} value={draft.hairTips} onChange={c => update(cur => ({ ...cur, hairTips: c }))} />}
            <p className="as-note">Visível nos estilos cacheados.</p>
          </Section>
          <Section title="Sobrancelhas">{slotGrid('brows')}</Section>
          <Section title="Barba">{slotGrid('beard')}</Section>
        </>}

        {tab === 'outfit' && <>
          {slotTabs(['top', 'bottom', 'socks'], outfitSlot, setOutfitSlot)}
          <Section title={SLOT_LABELS[outfitSlot]}>{slotGrid(outfitSlot)}</Section>
          {tintEditor(outfitSlot)}
        </>}

        {tab === 'shoes' && <><Section title="Calçados">{slotGrid('shoes')}</Section>{tintEditor('shoes')}</>}

        {tab === 'extras' && <>
          {slotTabs(['headwear', 'eyewear', 'neck', 'back', 'belt', 'hands', 'wrist', 'prop', 'bodyart'], extraSlot, setExtraSlot)}
          <Section title={SLOT_LABELS[extraSlot]}>{slotGrid(extraSlot)}</Section>
          {tintEditor(extraSlot)}
        </>}

        {tab === 'moves' && <>
          {(['dance', 'celebration'] as const).map(kind => <Section key={kind} title={kind === 'dance' ? 'Danças' : 'Comemorações'}>
            <div className="as-moves">{MOTIONS.filter(m => m.kind === kind).map(m => {
              const selected = kind === 'dance' ? draft.dance === m.id : draft.celebration === m.id;
              const owned = ownsMotion(profile, m.id);
              return <button type="button" key={m.id} className={`as-move ${selected ? 'on' : ''} ${motion === m.id ? 'live' : ''}`} aria-pressed={selected} onClick={() => preview(m)}>
                <span className="as-move-icon"><Icon name={motion === m.id && playing ? 'pause' : 'play'} size={16} /></span>
                <span className="as-move-text"><b>{m.name}</b><small>{m.subtitle}</small></span>
                <span className={`as-item-price ${owned ? 'owned' : ''}`}>{owned ? (selected ? 'Equipada' : m.price === 0 ? 'Grátis' : 'Sua') : <><Icon name="coin" size={12} />{m.price}</>}</span>
              </button>;
            })}</div>
          </Section>)}
          <p className="as-note">A mesma coreografia funciona em qualquer corpo criado: todos compartilham o mesmo esqueleto.</p>
        </>}
      </div>

      <footer className="as-actions">
        <div className="as-actions-summary">
          {equipped ? <><span className="as-status ok"><Icon name="check" size={14} />Equipado</span><small>É assim que você aparece no jogo.</small></>
            : cart.total ? <><span className="as-status"><Icon name="lock" size={14} />{cart.items.length + cart.bundles.length + cart.motions.length} {cart.items.length + cart.bundles.length + cart.motions.length > 1 ? 'novidades' : 'novidade'}</span><small><Icon name="coin" size={12} /> {cart.total} · saldo {profile.coins.toLocaleString('pt-BR')}</small></>
              : <><span className="as-status">Alterações não equipadas</span><small>Tudo já é seu.</small></>}
        </div>
        <div className="as-actions-buttons">
          <button type="button" className="as-ghost" onClick={undo} disabled={!history.length} aria-label="Desfazer"><Icon name="undo" /></button>
          <button type="button" className="as-ghost" onClick={() => setModal('save')} aria-label="Salvar visual"><Icon name="save" /></button>
          {equipped && onPlay ? <button type="button" className="as-primary" onClick={onPlay}>Jogar com ele</button>
            : <button type="button" className="as-primary" disabled={busy || equipped} onClick={() => cart.total ? setModal('buy') : void equip()}>{busy ? 'Salvando…' : cart.total ? 'Comprar e equipar' : 'Salvar e equipar'}</button>}
        </div>
        {message && <p className={`as-toast ${message.tone}`} role="status">{message.text}</p>}
      </footer>
    </aside>

    {modal && <div className="as-modal-backdrop" onClick={() => !busy && setModal(null)}>
      <div className="as-modal" role="dialog" aria-modal="true" aria-labelledby="as-modal-title" onClick={e => e.stopPropagation()}>
        <button type="button" className="as-icon-btn as-modal-close" aria-label="Fechar" onClick={() => setModal(null)} disabled={busy}><Icon name="close" /></button>
        {modal === 'buy' ? <>
          <h2 id="as-modal-title">Confirmar compra</h2>
          <ul className="as-cart">
            {cart.bundles.map(b => <li key={b.id}><img src={thumbUrl(`bundle_${b.id}`)} alt="" onError={e => { e.currentTarget.style.visibility = 'hidden'; }} /><span><b>{b.name} · personagem completo</b><small>Libera {ITEMS.filter(i => i.bundle === b.id).length} peças do visual</small></span><em><Icon name="coin" size={12} />{b.price}</em></li>)}
            {cart.items.map(i => <li key={i.id}><img src={thumbUrl(i.id)} alt="" onError={e => { e.currentTarget.style.visibility = 'hidden'; }} /><span><b>{i.name}</b><small>{SLOT_LABELS[i.slot]}</small></span><em><Icon name="coin" size={12} />{i.price}</em></li>)}
            {cart.motions.map(m => <li key={m.id}><span className="as-cart-move"><Icon name="music" /></span><span><b>{m.name}</b><small>{m.kind === 'dance' ? 'Dança' : 'Comemoração'}</small></span><em><Icon name="coin" size={12} />{m.price}</em></li>)}
          </ul>
          <div className="as-cart-total"><span>Total</span><b><Icon name="coin" size={14} />{cart.total}</b></div>
          <p className="as-note">Saldo atual: {profile.coins.toLocaleString('pt-BR')} moedas{cart.total > profile.coins ? ` · faltam ${cart.total - profile.coins}` : ` · depois da compra: ${(profile.coins - cart.total).toLocaleString('pt-BR')}`}.</p>
          <button type="button" className="as-primary wide" disabled={busy || cart.total > profile.coins} onClick={() => void equip()}>{busy ? 'Confirmando…' : `Comprar e equipar · ${cart.total}`}</button>
        </> : <>
          <h2 id="as-modal-title">Salvar visual</h2>
          <p className="as-note">Guarde esta combinação para trocar depois. Salvar não compra nada.</p>
          <input className="as-input" autoFocus maxLength={24} placeholder={`Visual ${profile.outfits.length + 1}`} value={outfitName} onChange={e => setOutfitName(e.target.value)} onKeyDown={e => e.key === 'Enter' && saveOutfit()} aria-label="Nome do visual" />
          {profile.outfits.length >= 12 && <p className="as-note">Limite de 12 visuais: o mais antigo será substituído.</p>}
          <button type="button" className="as-primary wide" onClick={saveOutfit}>Salvar em Meus visuais</button>
        </>}
      </div>
    </div>}
  </div>;
}
