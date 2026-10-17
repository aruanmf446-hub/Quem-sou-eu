import { lazy, Suspense, useMemo, useState } from 'react';
const AvatarView = lazy(() => import('../avatar/AvatarView').then(m => ({ default: m.AvatarView })));
const AvatarStudio = lazy(() => import('./AvatarStudio').then(m => ({ default: m.AvatarStudio })));
import { resolveConfig } from '../avatar/ownership';
import { audio } from '../audio/music';
import { maxPlayersForDeck, MIN_PLAYERS } from '../game/engine';
import type { Deck } from '../game/types';
import { playableDecks, setProfile, useProfile } from '../lib/profile';
import { isOnlineAvailable } from '../lib/supabase';
import { Room } from '../online/room';
import { LockerTab } from './LockerTab';
import { ShopTab } from './ShopTab';
import { DecksTab } from './DecksTab';
import { StoryTab } from './StoryTab';
import { SettingsModal } from './SettingsModal';

export type MenuTab = 'jogar' | 'armario' | 'loja' | 'decks' | 'historia' | 'studio';

const TABS: { id: MenuTab; label: string }[] = [
  { id: 'jogar', label: 'Jogar' },
  { id: 'studio', label: 'Estúdio 3D' },
  { id: 'armario', label: 'Armário' },
  { id: 'loja', label: 'Loja' },
  { id: 'decks', label: 'Decks' },
  { id: 'historia', label: 'História' },
];

interface Props {
  tab: MenuTab;
  onTab: (t: MenuTab) => void;
  onQuickMatch: (deck: Deck, players: number) => void;
  onRoom: (room: Room) => void;
  onStory: (level: number) => void;
}

export function MainMenu({ tab, onTab, onQuickMatch, onRoom, onStory }: Props) {
  const profile = useProfile();
  const [settings, setSettings] = useState(false);

  return (
    <div className="menu">
      <header className="topbar">
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => {
                audio.sfx('click');
                onTab(t.id);
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="topbar-right">
          <div className="coins" title="Moedas">
            <span className="coin-icon">●</span> {profile.coins.toLocaleString('pt-BR')}
          </div>
          <button className="icon-btn" onClick={() => setSettings(true)} aria-label="Configurações">
            ⚙
          </button>
        </div>
      </header>

      <main className="menu-body">
        {tab === 'jogar' && <PlayTab onQuickMatch={onQuickMatch} onRoom={onRoom} onLocker={() => onTab('studio')} />}
        {tab === 'studio' && <Suspense fallback={<p className="hint">Carregando estúdio…</p>}><AvatarStudio onPlay={() => onTab('jogar')} /></Suspense>}
        {tab === 'armario' && <LockerTab />}
        {tab === 'loja' && <ShopTab onStudio={() => onTab('studio')} />}
        {tab === 'decks' && <DecksTab />}
        {tab === 'historia' && <StoryTab onPlay={onStory} />}
      </main>

      {settings && <SettingsModal onClose={() => setSettings(false)} />}
    </div>
  );
}

function PlayTab({ onQuickMatch, onRoom, onLocker }: { onQuickMatch: Props['onQuickMatch']; onRoom: Props['onRoom']; onLocker: () => void }) {
  const profile = useProfile();
  const decks = playableDecks(profile);
  const deck = decks.find((d) => d.id === profile.selectedDeckId) ?? decks[0];
  const maxP = maxPlayersForDeck(deck);
  const [players, setPlayers] = useState(6);
  const [mode, setMode] = useState<'bots' | 'criar' | 'entrar'>('bots');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const count = Math.max(MIN_PLAYERS, Math.min(players, maxP));

  const me = { id: profile.id, name: profile.name, isBot: false, skin: profile.skin };
  const config = useMemo(() => resolveConfig(profile.avatar), [profile.avatar]);
  const [celebrating, setCelebrating] = useState(false);

  async function go() {
    audio.sfx('click');
    setError('');
    if (mode === 'bots') return onQuickMatch(deck, count);
    setBusy(true);
    try {
      const room = mode === 'criar' ? await Room.create(me) : await Room.join(me, code);
      onRoom(room);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="play">
      <section className="stage">
        <div className="stage-glow" />
        <div className="lobby-character">
          <Suspense fallback={<p className="hint">Carregando personagem 3D…</p>}>
            <AvatarView config={config} motion={celebrating ? config.celebration : config.dance} interactive={false} label={`${profile.name} dançando no lobby`} />
          </Suspense>
          <button type="button" className="lobby-celebrate" onClick={() => setCelebrating(v => !v)}>{celebrating ? 'Voltar a dançar' : 'Comemorar'}</button>
        </div>
        <div className="pedestal" />
        <input
          className="name-input"
          value={profile.name}
          maxLength={16}
          onChange={(e) => setProfile({ name: e.target.value.replace(/\s+/g, ' ') })}
          aria-label="Seu nome"
        />
        <button className="btn-ghost" onClick={onLocker}>
          Personalizar 3D
        </button>
      </section>

      <section className="play-panel">
        <div className="panel">
          <h3>Modo</h3>
          <div className="seg">
            <button className={mode === 'bots' ? 'on' : ''} onClick={() => setMode('bots')}>
              Contra bots
            </button>
            <button className={mode === 'criar' ? 'on' : ''} onClick={() => setMode('criar')} disabled={!isOnlineAvailable}>
              Criar sala
            </button>
            <button className={mode === 'entrar' ? 'on' : ''} onClick={() => setMode('entrar')} disabled={!isOnlineAvailable}>
              Entrar
            </button>
          </div>
          {!isOnlineAvailable && <p className="hint">Online desativado: configure o Supabase no arquivo .env.</p>}

          {mode !== 'entrar' && (
            <>
              <h3>Deck</h3>
              <select value={deck.id} onChange={(e) => setProfile({ selectedDeckId: e.target.value })}>
                {decks.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.cards.length} cartas)
                  </option>
                ))}
              </select>
            </>
          )}

          {mode === 'bots' && (
            <>
              <h3>
                Jogadores: <b>{count}</b>
              </h3>
              <input type="range" min={MIN_PLAYERS} max={maxP} value={count} onChange={(e) => setPlayers(Number(e.target.value))} />
            </>
          )}

          {mode === 'entrar' && (
            <>
              <h3>Código da sala</h3>
              <input
                className="code-input"
                value={code}
                maxLength={5}
                placeholder="ABCDE"
                onChange={(e) => setCode(e.target.value.toUpperCase())}
              />
            </>
          )}
          {error && <p className="error">{error}</p>}
        </div>

        <button className="play-btn" onClick={go} disabled={busy || (mode === 'entrar' && code.length !== 5)}>
          {busy ? '...' : 'JOGAR'}
        </button>
      </section>
    </div>
  );
}
