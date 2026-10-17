import { useState } from 'react';
import { CharacterStage } from '../components/CharacterStage';
import { CHARACTERS, DANCES, type AvatarLook } from '../data/characters';
import { buy, owns } from '../lib/economy';
import { getProfile, setProfile, useProfile } from '../lib/profile';

export function CharacterStudio() {
  const p = useProfile();
  const [look, setLook] = useState<AvatarLook>(() => ({ ...p.avatar }));
  const [tab, setTab] = useState<'character' | 'dance'>('character');
  const [playing, setPlaying] = useState(() => !window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [speed, setSpeed] = useState(1);
  const [rig, setRig] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const character = CHARACTERS.find(c => c.id === look.character)!;
  const dance = DANCES.find(d => d.id === look.dance)!;
  const entries = tab === 'character' ? CHARACTERS : DANCES;
  async function purchase(kind: 'character' | 'dance', id: string) {
    setBusy(true); setMessage('');
    try { await buy(kind, id); setMessage('Adicionado à sua coleção. Você já pode equipar!'); }
    catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }
  const canEquip = p.ownedCharacters.includes(look.character) && p.ownedDances.includes(look.dance);
  return <div className="studio">
    <header className="studio-heading"><div><span className="studio-eyebrow">QUEM SOU EU? / CHARACTER LAB</span><h1>Crie seu próximo <em>personagem.</em></h1><p>Escolha o visual. Encontre seu ritmo. Entre em cena.</p></div><span className="studio-badge">● ESTÚDIO 3D</span></header>
    <div className="studio-layout">
      <section className="studio-preview" aria-label="Provador 3D">
        <div className="studio-preview-top"><span>PRÉVIA AO VIVO</span><span>{rig ? 'ESQUELETO VISÍVEL' : 'RIG HUMANOIDE'}</span></div>
        <CharacterStage look={look} playing={playing} speed={speed} rig={rig} />
        <div className="studio-caption"><span>ARRASTE PARA GIRAR · SCROLL PARA APROXIMAR</span><h2>{character.name}</h2><p>{dance.name}</p></div>
        <div className="studio-controls"><button onClick={() => setPlaying(!playing)} aria-label={playing ? 'Pausar dança' : 'Reproduzir dança'}>{playing ? 'Ⅱ Pausar' : '▶ Dançar'}</button><label>Velocidade <select value={speed} onChange={e => setSpeed(Number(e.target.value))}><option value={.5}>0,5×</option><option value={1}>1×</option><option value={1.5}>1,5×</option><option value={2}>2×</option></select></label><label><input type="checkbox" checked={rig} onChange={e => setRig(e.target.checked)} /> Ver rig</label></div>
      </section>
      <section className="studio-editor">
        <div className="studio-tabs" role="tablist" aria-label="Catálogo"><button role="tab" aria-selected={tab === 'character'} onClick={() => setTab('character')}>01 / Skins</button><button role="tab" aria-selected={tab === 'dance'} onClick={() => setTab('dance')}>02 / Danças</button></div>
        <div className="studio-catalog"><div className="studio-section-title"><h2>{tab === 'character' ? 'Escolha sua identidade' : 'Solte o movimento'}</h2><span>{entries.length} opções</span></div><p className="studio-hint">Experimente qualquer item antes de comprar.</p>
          {entries.map((entry, index) => {
            const selected = entry.id === (tab === 'character' ? look.character : look.dance);
            const owned = owns(tab, entry.id);
            return <article className={`studio-item ${selected ? 'selected' : ''}`} key={entry.id}>
              <button className="studio-select-item" aria-pressed={selected} onClick={() => {
                if (tab === 'character') { const c = CHARACTERS.find(c => c.id === entry.id)!; setLook({ ...look, character: c.id, color: c.color }); }
                else setLook({ ...look, dance: DANCES.find(d => d.id === entry.id)!.id });
                setMessage('');
              }}><span className={`studio-item-icon item-${entry.id}`}>{tab === 'character' ? ['◈', '10', '✦'][index] : ['♫', '↗', '⌘', '☾'][index]}</span><span><b>{entry.name}</b><small>{entry.subtitle}</small></span><span className="studio-item-check">{selected ? '●' : '○'}</span></button>
              <div className="studio-item-footer"><span>{owned ? 'NA SUA COLEÇÃO' : `● ${entry.price} moedas`}</span>{!owned && <button disabled={busy || p.coins < entry.price} onClick={() => void purchase(tab, entry.id)}>{busy ? 'Aguarde…' : 'Comprar'}</button>}</div>
            </article>;
          })}
        </div>
        <div className="studio-customize"><h3>Seu toque pessoal</h3><label>Cor da roupa <input type="color" value={look.color} onChange={e => setLook({ ...look, color: e.target.value })} /></label><label>Altura <input type="range" min={.85} max={1.15} step={.01} value={look.height} onChange={e => setLook({ ...look, height: Number(e.target.value) })} /></label></div>
        <button className="studio-equip" disabled={!canEquip || busy} onClick={() => {
          // Recheck ownership at action time, not just when the view rendered.
          const current = getProfile();
          if (!current.ownedCharacters.includes(look.character) || !current.ownedDances.includes(look.dance)) return;
          setProfile({ avatar: { ...look } }); setMessage('Personagem e dança equipados! Veja no menu Jogar.');
        }}>{canEquip ? 'Equipar personagem e dança ↗' : 'Compre os itens para equipar'}</button>
        <p className="studio-message" role="status">{message}</p>
        <p className="studio-fine">Compras com moedas do jogo. Personagens originais e estilizados. Personalização salva no seu perfil.</p>
      </section>
    </div>
  </div>;
}
