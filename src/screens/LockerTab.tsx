import { Crewmate } from '../components/Crewmate';
import { HATS, SKIN_COLORS, VISORS } from '../data/skins';
import { audio } from '../audio/music';
import { setProfile, useProfile } from '../lib/profile';

export function LockerTab() {
  const p = useProfile();
  const equip = (patch: Partial<typeof p.skin>) => {
    audio.sfx('click');
    setProfile((cur) => ({ skin: { ...cur.skin, ...patch } }));
  };

  return (
    <div className="locker">
      <section className="stage small">
        <div className="stage-glow" />
        <Crewmate skin={p.skin} size={150} className="float" />
        <div className="pedestal" />
      </section>
      <section className="locker-items">
        <h2>Cor</h2>
        <div className="grid-items">
          {SKIN_COLORS.map((c) => {
            const owned = p.ownedColors.includes(c.id);
            return (
              <button
                key={c.id}
                className={`item ${p.skin.body === c.color ? 'equipped' : ''}`}
                disabled={!owned}
                onClick={() => equip({ body: c.color })}
                title={owned ? c.name : `${c.name}: compre na Loja`}
              >
                <Crewmate skin={{ ...p.skin, body: c.color, hat: 'none' }} size={44} />
                <span>{owned ? c.name : '🔒'}</span>
              </button>
            );
          })}
        </div>
        <h2>Chapéu</h2>
        <div className="grid-items">
          <button className={`item ${p.skin.hat === 'none' ? 'equipped' : ''}`} onClick={() => equip({ hat: 'none' })}>
            <Crewmate skin={{ ...p.skin, hat: 'none' }} size={44} />
            <span>Nenhum</span>
          </button>
          {HATS.map((h) => {
            const owned = p.ownedHats.includes(h.id);
            return (
              <button key={h.id} className={`item ${p.skin.hat === h.id ? 'equipped' : ''}`} disabled={!owned} onClick={() => equip({ hat: h.id })}>
                <Crewmate skin={{ ...p.skin, hat: h.id }} size={44} />
                <span>{owned ? h.name : '🔒'}</span>
              </button>
            );
          })}
        </div>
        <h2>Visor</h2>
        <div className="grid-items">
          {VISORS.map((v) => {
            const owned = p.ownedVisors.includes(v.id);
            return (
              <button key={v.id} className={`item ${p.skin.visor === v.color ? 'equipped' : ''}`} disabled={!owned} onClick={() => equip({ visor: v.color })}>
                <Crewmate skin={{ ...p.skin, visor: v.color, hat: 'none' }} size={44} />
                <span>{owned ? v.name : '🔒'}</span>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
