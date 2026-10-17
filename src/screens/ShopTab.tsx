import { useMemo, useState } from 'react';
import { Crewmate } from '../components/Crewmate';
import { HATS, RARITY_COLORS, SKIN_COLORS, VISORS } from '../data/skins';
import { OFFICIAL_DECKS } from '../data/decks';
import { buy } from '../lib/economy';
import { useProfile } from '../lib/profile';
import type { ItemKind } from '../lib/supabase';
import { assetUrl } from '../config/assets';

interface ShopEntry {
  kind: ItemKind;
  id: string;
  name: string;
  price: number;
  rarity: keyof typeof RARITY_COLORS;
}

function rarityFor(price: number): ShopEntry['rarity'] {
  if (price >= 1000) return 'lendário';
  if (price >= 500) return 'épico';
  if (price >= 200) return 'raro';
  return 'comum';
}

const ALL: ShopEntry[] = [
  ...SKIN_COLORS.filter((c) => c.price > 0).map((c) => ({ kind: 'color' as const, id: c.id, name: c.name, price: c.price, rarity: rarityFor(c.price) })),
  ...HATS.map((h) => ({ kind: 'hat' as const, id: h.id, name: h.name, price: h.price, rarity: h.rarity })),
  ...VISORS.filter((v) => v.price > 0).map((v) => ({ kind: 'visor' as const, id: v.id, name: `Visor ${v.name}`, price: v.price, rarity: rarityFor(v.price) })),
];

/** Itens em destaque mudam todo dia (mesma seleção para todo mundo). */
function dailyFeatured(date: Date): ShopEntry[] {
  let seed = Number(date.toISOString().slice(0, 10).replace(/-/g, ''));
  const rand = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  return [...ALL].sort(() => rand() - 0.5).slice(0, 4);
}

function msToMidnight() {
  const now = new Date();
  const next = new Date(now);
  next.setHours(24, 0, 0, 0);
  const ms = next.getTime() - now.getTime();
  const h = Math.floor(ms / 3.6e6);
  const m = Math.floor((ms % 3.6e6) / 6e4);
  return `${h}h ${m}min`;
}

export function ShopTab({ onStudio }: { onStudio: () => void }) {
  const p = useProfile();
  const featured = useMemo(() => dailyFeatured(new Date()), []);
  const [msg, setMsg] = useState('');

  const owned = (e: { kind: ItemKind; id: string }) =>
    ({ color: p.ownedColors, hat: p.ownedHats, visor: p.ownedVisors, deck: p.ownedDecks, character: p.ownedCharacters, dance: p.ownedDances })[e.kind].includes(e.id);

  async function purchase(kind: ItemKind, id: string, name: string) {
    setMsg('');
    try {
      await buy(kind, id);
      setMsg(`${name} é seu!`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  const preview = (e: ShopEntry) => {
    const skin = { ...p.skin };
    if (e.kind === 'color') skin.body = SKIN_COLORS.find((c) => c.id === e.id)!.color;
    if (e.kind === 'hat') skin.hat = e.id;
    if (e.kind === 'visor') skin.visor = VISORS.find((v) => v.id === e.id)!.color;
    return skin;
  };

  const Tile = ({ e, big }: { e: ShopEntry; big?: boolean }) => (
    <div className={`shop-tile ${big ? 'big' : ''}`} style={{ ['--rarity' as string]: RARITY_COLORS[e.rarity] }}>
      <div className="shop-art">
        <Crewmate skin={preview(e)} size={big ? 110 : 70} />
      </div>
      <div className="shop-info">
        <span className="rarity">{e.rarity}</span>
        <b>{e.name}</b>
        {owned(e) ? (
          <span className="owned">ADQUIRIDO</span>
        ) : (
          <button className="buy" onClick={() => purchase(e.kind, e.id, e.name)} disabled={p.coins < e.price}>
            ● {e.price}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="shop">
      <section className="studio-shop-banner"><div><span className="studio-eyebrow">NOVIDADE / PERSONAGENS 3D</span><h2>Seu visual. Seu movimento.</h2><p>Experimente e compre skins e danças no Estúdio 3D.</p></div><button className="studio-equip" onClick={onStudio}>Explorar skins e danças ↗</button></section>
      {msg && <div className="toast">{msg}</div>}
      <div className="shop-head">
        <h2>Destaques do dia</h2>
        <span className="shop-timer">Muda em {msToMidnight()}</span>
      </div>
      <div className="shop-featured">
        {featured.map((e) => (
          <Tile key={`${e.kind}-${e.id}`} e={e} big />
        ))}
      </div>

      <h2>Decks premium</h2>
      <div className="shop-decks">
        {OFFICIAL_DECKS.filter((d) => d.price > 0).map((d) => {
          const cover = assetUrl(d.cover);
          const has = p.ownedDecks.includes(d.id);
          return (
            <div key={d.id} className="deck-tile">
              <div className="deck-cover">
                {cover ? <img src={cover} alt="" onError={(ev) => (ev.currentTarget.style.display = 'none')} /> : null}
                <div className="deck-emojis">{d.cards.slice(0, 6).map((c) => c.emoji).join(' ')}</div>
              </div>
              <b>{d.name}</b>
              <p>{d.description}</p>
              <small>{d.cards.length} cartas</small>
              {has ? (
                <span className="owned">ADQUIRIDO</span>
              ) : (
                <button className="buy" onClick={() => purchase('deck', d.id, d.name)} disabled={p.coins < d.price}>
                  ● {d.price}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <h2>Todos os itens</h2>
      <div className="shop-grid">
        {ALL.map((e) => (
          <Tile key={`${e.kind}-${e.id}`} e={e} />
        ))}
      </div>
    </div>
  );
}
