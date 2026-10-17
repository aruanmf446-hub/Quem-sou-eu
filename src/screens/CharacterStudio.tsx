import { useState } from 'react';
import { CharacterStage, type CameraView } from '../components/CharacterStage';
import { AvatarCreatorTrial } from './AvatarCreatorTrial';
import { CHARACTERS, DANCES, type AvatarLook } from '../data/characters';
import { buy } from '../lib/economy';
import { getProfile, setProfile, useProfile } from '../lib/profile';

type Environment = 'studio' | 'arena' | 'midnight';
const COLORS = ['#8463df', '#efc51d', '#c2b9a4', '#e65068', '#235fba', '#172b32', '#e3e8ee', '#61ad8b'];
const IDENTITY = {
  street: { label: 'NOVA', collection: 'COLEÇÃO URBANA', rarity: 'ÉPICO', number: '01', description: 'Atitude nas ruas. Presença na pista.', color: '#a18aff' },
  striker: { label: 'CAMISA 10', collection: 'COLEÇÃO JOGA BONITO', rarity: 'ÉPICO', number: '02', description: 'O campo é seu. O ritmo também.', color: '#f3d45b' },
  'night-clown': { label: 'MEIA-NOITE', collection: 'COLEÇÃO AFTER DARK', rarity: 'LENDÁRIO', number: '03', description: 'O espetáculo começa quando a luz apaga.', color: '#ff7485' },
};

function Icon({ name }: { name: 'play' | 'pause' | 'body' | 'face' | 'back' | 'rotate' | 'check' | 'arrow' | 'rig' }) {
  const paths = {
    play: 'M8 5l11 7-11 7V5Z', pause: 'M8 5v14M16 5v14', body: 'M9 3h6M12 3v4M5 9l7-2 7 2M12 7v7M12 14l-4 7M12 14l4 7',
    face: 'M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5M8 10h.01M16 10h.01M9 16q3 2 6 0',
    back: 'M9 5l-6 6 6 6M3 11h11a6 6 0 010 12', rotate: 'M4 10a8 8 0 111 8M4 10V4M4 10h6',
    check: 'M5 12l4 4L19 6', arrow: 'M5 12h14M13 6l6 6-6 6', rig: 'M12 3v12M4 8l8 3 8-3M12 15l-5 6M12 15l5 6',
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

export function CharacterStudio() {
  const p = useProfile();
  const [look, setLook] = useState<AvatarLook>(() => ({ ...p.avatar }));
  const [tab, setTab] = useState<'character' | 'dance'>('character');
  const [playing, setPlaying] = useState(() => !window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [speed, setSpeed] = useState(1);
  const [rig, setRig] = useState(false);
  const [view, setView] = useState<CameraView>('full');
  const [rotate, setRotate] = useState(false);
  const [environment, setEnvironment] = useState<Environment>('studio');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [trialOpen, setTrialOpen] = useState(false);
  const character = CHARACTERS.find(c => c.id === look.character) ?? CHARACTERS[0];
  const dance = DANCES.find(d => d.id === look.dance) ?? DANCES[0];
  const identity = IDENTITY[character.id];
  const characterOwned = p.ownedCharacters.includes(character.id), danceOwned = p.ownedDances.includes(dance.id);
  const cost = (characterOwned ? 0 : character.price) + (danceOwned ? 0 : dance.price);
  const equipped = p.avatar.character === look.character && p.avatar.dance === look.dance && p.avatar.color === look.color && p.avatar.height === look.height;
  function chooseCharacter(id: typeof CHARACTERS[number]['id']) {
    const c = CHARACTERS.find(c => c.id === id)!;
    setLook(l => ({ ...l, character: c.id, color: c.color })); setMessage('');
  }
  async function equip() {
    setBusy(true); setMessage('');
    try {
      if (getProfile().coins < cost) throw new Error(`Faltam ${cost - getProfile().coins} moedas. Ganhe moedas jogando partidas e fases.`);
      if (!characterOwned) await buy('character', character.id);
      if (!danceOwned) await buy('dance', dance.id);
      const current = getProfile();
      if (!current.ownedCharacters.includes(look.character) || !current.ownedDances.includes(look.dance)) throw new Error('Não foi possível confirmar os itens. Tente novamente.');
      setProfile({ avatar: { ...look } });
      setMessage('Pronto para entrar em cena. Personagem e dança equipados!');
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }
  if (trialOpen) return <AvatarCreatorTrial onClose={() => setTrialOpen(false)} />;
  return <div className="studio studio-v2" style={{ '--character-accent': identity.color } as React.CSSProperties}>
    <header className="lab-header"><div className="lab-wordmark"><span className="lab-symbol">Q<span>✦</span></span><div><b>CHARACTER<span>LAB</span></b><small>SEU PERSONAGEM. SUAS REGRAS.</small></div></div><div className="lab-header-note"><span className="live-dot" /> ESTÚDIO INTERATIVO <span className="lab-header-divider">/</span> 3D</div><span className="lab-edition">VOL. 01 — ORIGINALS</span></header>
    <div className="studio-test-banner"><div><strong>NOVO · CRIADOR PRONTO</strong><span>Experimente um editor externo sem mexer nas suas compras ou personagens.</span></div><button type="button" onClick={() => setTrialOpen(true)}>TESTAR CRIADOR 3D ↗</button></div>
    <div className="lab-workspace">
      <section className={`lab-stage scene-${environment}`} aria-label="Estúdio de personagens 3D">
        <div className="lab-stage-grid" /><div className="lab-stage-halo" />
        <div className="lab-stage-top"><span><i /> {identity.collection}</span><span className="lab-quality">MODELO 3D · RIG ARTICULADO</span></div>
        <div className="lab-oversized-name" aria-hidden="true">{identity.label}</div>
        <div className="lab-character-number" aria-hidden="true">{identity.number}<span> / 03</span></div>
        <CharacterStage look={look} playing={playing} speed={speed} rig={rig} view={view} autoRotate={rotate} environment={environment} />
        <div className="lab-view-tools" aria-label="Câmera e visualização">
          {([{ id: 'full', icon: 'body', label: 'Corpo inteiro' }, { id: 'portrait', icon: 'face', label: 'Ver rosto' }, { id: 'back', icon: 'back', label: 'Ver costas' }] as const).map(v => <button key={v.id} className={view === v.id ? 'active' : ''} aria-label={v.label} title={v.label} aria-pressed={view === v.id} onClick={() => setView(v.id)}><Icon name={v.icon} /></button>)}
          <span /><button className={rotate ? 'active' : ''} aria-label="Girar automaticamente" title="Giro automático" aria-pressed={rotate} onClick={() => setRotate(v => !v)}><Icon name="rotate" /></button>
          <button className={rig ? 'active' : ''} aria-label="Mostrar esqueleto" title="Mostrar esqueleto" aria-pressed={rig} onClick={() => setRig(v => !v)}><Icon name="rig" /></button>
        </div>
        <div className="lab-drag-hint"><span>↔</span> ARRASTE PARA EXPLORAR <b>·</b> SCROLL PARA ZOOM</div>
        <div className="lab-stage-bottom"><div><span className="lab-rarity"><i />{identity.rarity}</span><h1>{identity.label}</h1><p>{identity.description}</p></div><span className="lab-avatar-tag">ORIGINAL<br /><b>CHARACTER</b></span></div>
        <div className={`lab-player ${playing ? 'playing' : ''}`}>
          <button className="lab-play" onClick={() => setPlaying(v => !v)} aria-label={playing ? 'Pausar dança' : 'Reproduzir dança'}><Icon name={playing ? 'pause' : 'play'} /></button>
          <div className="lab-player-track"><span>EMOTE EM PRÉVIA</span><b>{dance.name}</b></div>
          <div className="lab-waveform" aria-hidden="true">{Array.from({ length: 22 }, (_, i) => <i key={i} style={{ height: `${8 + Math.sin(i * 2.4) ** 2 * 18}px`, animationDelay: `${i * -.09}s` }} />)}</div>
          <label className="lab-speed"><span>RITMO</span><select aria-label="Velocidade da dança" value={speed} onChange={e => setSpeed(Number(e.target.value))}><option value={.5}>0,5×</option><option value={1}>1×</option><option value={1.5}>1,5×</option><option value={2}>2×</option></select></label>
        </div>
      </section>
      <aside className="lab-inspector">
        <div className="lab-inspector-top"><span>SEU PRÓXIMO MAIN</span><h2>Feito para<br /><em>ser você.</em></h2><p>Monte o visual. Escolha o movimento.<br />O resto é presença.</p></div>
        <div className="lab-tabs" aria-label="Catálogo"><button aria-pressed={tab === 'character'} className={tab === 'character' ? 'active' : ''} onClick={() => setTab('character')}><span>01</span> SKINS <small>03</small></button><button aria-pressed={tab === 'dance'} className={tab === 'dance' ? 'active' : ''} onClick={() => setTab('dance')}><span>02</span> EMOTES <small>04</small></button></div>
        {tab === 'character' ? <div className="lab-skin-grid">{CHARACTERS.map(c => {
          const selected = look.character === c.id, owned = p.ownedCharacters.includes(c.id);
          return <button className={`lab-skin-card skin-${c.id} ${selected ? 'selected' : ''}`} aria-label={`Experimentar ${c.name}`} aria-pressed={selected} key={c.id} onClick={() => chooseCharacter(c.id)}><span className="lab-skin-card-id">{IDENTITY[c.id].number}</span><img src={`/characters/${c.id}.webp`} alt={c.name} width="225" height="300" /><span className="lab-skin-card-name">{c.name}</span><span className="lab-skin-card-cost">{owned ? 'ADQUIRIDO' : `● ${c.price}`}</span>{selected && <span className="lab-selection-check"><Icon name="check" /></span>}</button>;
        })}</div> : <div className="lab-dance-list">{DANCES.map((d, i) => {
          const selected = look.dance === d.id;
          return <button key={d.id} className={selected ? 'selected' : ''} aria-pressed={selected} onClick={() => { setLook(l => ({ ...l, dance: d.id })); setMessage(''); }}><span className={`lab-emote-icon emote-${d.id}`}><svg viewBox="0 0 32 40" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="16" cy="6" r="3" fill="currentColor" stroke="none" /><path d={['M16 12v12M7 18l9-6 9 4M16 24l-7 11M16 24l9 9','M16 12v12M5 12l11 4 10-7M16 24l-8 8M16 24l7 11','M16 12v12M5 13v7h11M16 15h10v-6M16 24l-6 11M16 24l6 11','M16 12v12M6 20l10-6 10 6M16 24l-8 11M16 24l8 11'][i]} /></svg></span><span><b>{d.name}</b><small>{d.subtitle}</small></span><span className="lab-dance-price">{p.ownedDances.includes(d.id) ? <Icon name="check" /> : `● ${d.price}`}</span></button>;
        })}</div>}
        <div className="lab-personalize"><div className="lab-section-label"><h3>PALETA DO VISUAL</h3><span>{look.color.toUpperCase()}</span></div><div className="lab-swatches">{COLORS.map(color => <button aria-label={`Roupa ${color}`} aria-pressed={look.color === color} className={look.color.toLowerCase() === color ? 'selected' : ''} key={color} style={{ '--swatch': color } as React.CSSProperties} onClick={() => setLook(l => ({ ...l, color }))}>{look.color.toLowerCase() === color && <Icon name="check" />}</button>)}<label className="lab-custom-color" title="Escolher outra cor"><span>+</span><input type="color" aria-label="Cor personalizada da roupa" value={look.color} onChange={e => setLook(l => ({ ...l, color: e.target.value }))} /></label></div>
          <label className="lab-height"><span>PROPORÇÃO<span>{Math.round(look.height * 100)}%</span></span><input type="range" min={.85} max={1.15} step={.01} value={look.height} onChange={e => setLook(l => ({ ...l, height: Number(e.target.value) }))} /></label>
        </div>
        <div className="lab-environments"><div className="lab-section-label"><h3>AMBIENTE</h3><span>03 CENÁRIOS</span></div><div>{([{ id: 'studio', label: 'Estúdio' }, { id: 'arena', label: 'Arena' }, { id: 'midnight', label: 'Meia-noite' }] as const).map(e => <button key={e.id} className={`env-${e.id} ${environment === e.id ? 'selected' : ''}`} aria-pressed={environment === e.id} onClick={() => setEnvironment(e.id)}><span /><b>{e.label}</b>{environment === e.id && <Icon name="check" />}</button>)}</div></div>
        <div className="lab-purchase"><div><span>{cost ? 'DESBLOQUEAR VISUAL + EMOTE' : 'PRONTO PARA ENTRAR EM CENA'}</span><b>{cost ? `● ${cost} moedas` : equipped ? 'Visual equipado' : 'Itens da sua coleção'}</b></div><button onClick={() => void equip()} disabled={busy || equipped} className="lab-equip">{busy ? 'CONFIRMANDO…' : equipped ? 'EQUIPADO' : cost ? 'DESBLOQUEAR E EQUIPAR' : 'SALVAR E EQUIPAR'}<Icon name={equipped ? 'check' : 'arrow'} /></button><p role="status" className={message ? 'lab-feedback' : 'lab-purchase-note'}>{message || 'Moedas do jogo. Experimente tudo antes de comprar.'}</p></div>
      </aside>
    </div>
    <footer className="lab-footer"><span>PERSONAGENS ORIGINAIS <i /> FEITOS PARA SE MOVER</span><span>QUEM SOU EU? <b>© 2026</b></span></footer>
  </div>;
}
