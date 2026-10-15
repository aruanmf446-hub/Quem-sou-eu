import { useEffect, useMemo, useRef, useState } from 'react';
import { CardView, type CardStatus } from '../components/CardView';
import { Crewmate } from '../components/Crewmate';
import { audio } from '../audio/music';
import { coinsForResult, currentPlayer } from '../game/engine';
import type { LogEntry, PublicState } from '../game/types';
import type { MatchController, MatchSnapshot } from '../online/match';
import { award } from '../lib/economy';

interface Props {
  controller: MatchController;
  online: boolean;
  onExit: () => void;
}

function describe(entry: LogEntry, s: PublicState, myId: string): string | null {
  const name = (id: string) => (id === myId ? 'Você' : (s.players.find((p) => p.id === id)?.name ?? '?'));
  const card = (id: string) => s.deck.cards.find((c) => c.id === id)?.name ?? '?';
  switch (entry.kind) {
    case 'hit':
      return `🎯 ${name(entry.by)} acertou ${card(entry.cardId)} de ${name(entry.target)}!`;
    case 'miss':
      return `💨 ${name(entry.by)} chutou ${card(entry.cardId)}... ninguém tinha.`;
    case 'timeout':
      return `⏰ ${name(entry.by)} demorou e perdeu a vez.`;
    case 'eliminated':
      return `💀 ${name(entry.player)} ficou sem cartas!`;
    case 'round':
      return `— Rodada ${entry.round} —`;
    case 'win':
      return `🏆 ${name(entry.player)} venceu!`;
  }
}

export function MatchScreen({ controller, online, onExit }: Props) {
  const [snap, setSnap] = useState<MatchSnapshot | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [panel, setPanel] = useState<'chat' | 'log'>('chat');
  const [text, setText] = useState('');
  const [now, setNow] = useState(Date.now());
  const [earned, setEarned] = useState<number | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const logLen = useRef(0);
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => controller.subscribe(setSnap), [controller]);

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(t);
  }, []);

  // Sons e avisos para cada novo evento.
  useEffect(() => {
    if (!snap) return;
    const { log } = snap.state;
    const fresh = log.slice(logLen.current);
    logLen.current = log.length;
    for (const e of fresh) {
      if (e.kind === 'hit') audio.sfx('hit');
      if (e.kind === 'miss') audio.sfx('miss');
      const msg = e.kind === 'round' ? null : describe(e, snap.state, snap.myId);
      if (msg) setToast(msg);
    }
    if (snap.error) setToast(`⚠️ ${snap.error}`);
  }, [snap]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ block: 'end' });
  }, [snap?.state.chat.length, panel, panelOpen]);

  // Moedas no fim da partida.
  useEffect(() => {
    if (!snap || snap.state.phase !== 'finished' || earned !== null) return;
    if (!snap.state.players.some((p) => p.id === snap.myId)) return;
    const coins = coinsForResult(snap.state, snap.myId);
    setEarned(coins);
    audio.play('victory');
    void award(Math.min(150, coins), 'match');
  }, [snap, earned]);

  const lastChatId = snap?.state.chat.at(-1)?.id;
  const [seenChat, setSeenChat] = useState<string | undefined>();
  useEffect(() => {
    if (panelOpen && panel === 'chat') setSeenChat(lastChatId);
  }, [panelOpen, panel, lastChatId]);

  const statusOf = useMemo(() => {
    if (!snap) return () => 'open' as CardStatus;
    const discarded = new Set(snap.state.discarded);
    const missed = new Set(snap.state.missed);
    const mine = new Set(snap.myHand);
    return (id: string): CardStatus => (mine.has(id) ? 'mine' : discarded.has(id) ? 'discarded' : missed.has(id) ? 'missed' : 'open');
  }, [snap]);

  if (!snap) return <div className="center-msg">Carregando partida...</div>;

  const s = snap.state;
  const turn = currentPlayer(s);
  const myTurn = s.phase === 'playing' && turn.id === snap.myId;
  const me = s.players.find((p) => p.id === snap.myId);
  const spectator = !me;
  const timeLeft = Math.max(0, Math.ceil((s.turnEndsAt - now) / 1000));
  const pct = Math.max(0, Math.min(100, ((s.turnEndsAt - now) / (s.settings.turnSeconds * 1000)) * 100));
  const nameOf = (id: string) => s.players.find((p) => p.id === id)?.name ?? '?';
  const selectedCard = s.deck.cards.find((c) => c.id === selected);
  const ranking = [...s.players].sort((a, b) => (b.id === s.winnerId ? 1 : 0) - (a.id === s.winnerId ? 1 : 0) || b.handCount - a.handCount);
  const unread = lastChatId !== undefined && lastChatId !== seenChat && !(panelOpen && panel === 'chat');

  const confirmGuess = () => {
    if (!selected) return;
    controller.guess(selected);
    setSelected(null);
  };

  return (
    <div className="match">
      <header className="match-top">
        <button
          className="btn-ghost"
          onClick={() => {
            if (s.phase === 'finished' || confirm('Sair da partida? Suas cartas serão descartadas.')) onExit();
          }}
        >
          ✕
        </button>
        <div className="match-title">
          <b>Rodada {s.round}</b>
          <small>
            {s.deck.name} · {online ? 'Online' : 'Bots'}
          </small>
        </div>
        <button className={`btn-ghost chat-toggle ${unread ? 'unread' : ''}`} onClick={() => setPanelOpen((o) => !o)}>
          💬
        </button>
      </header>

      <div className="players-strip">
        {s.players.map((p) => (
          <div key={p.id} className={`seat ${p.id === turn.id && s.phase === 'playing' ? 'turn' : ''} ${p.eliminated ? 'out' : ''} ${p.id === snap.myId ? 'me' : ''}`}>
            <Crewmate skin={p.skin} size={40} dead={p.eliminated} />
            <span className="seat-name">{p.id === snap.myId ? 'Você' : p.name}</span>
            <span className="lives">{p.eliminated ? '—' : '🂠'.repeat(p.handCount)}</span>
          </div>
        ))}
      </div>

      <div className={`turn-banner ${myTurn ? 'mine' : ''}`}>
        {s.phase === 'finished' ? (
          <span>Fim de jogo!</span>
        ) : myTurn ? (
          <span>SUA VEZ! Escolha um personagem que algum adversário tenha.</span>
        ) : (
          <span>Vez de {nameOf(turn.id)}...</span>
        )}
        {s.phase === 'playing' && (
          <div className="timer">
            <div className="timer-fill" style={{ width: `${pct}%` }} />
            <span>{timeLeft}s</span>
          </div>
        )}
      </div>

      <div className="match-main">
        <section className="board-wrap">
          <div className="board">
            {s.deck.cards.map((c) => {
              const st = statusOf(c.id);
              return (
                <div key={c.id} className={selected === c.id ? 'selected-wrap' : ''}>
                  <CardView card={c} status={st} small onClick={myTurn && st === 'open' ? () => setSelected(c.id) : undefined} />
                </div>
              );
            })}
          </div>
        </section>

        <aside className={`side-panel ${panelOpen ? 'open' : ''}`}>
          <div className="seg">
            <button className={panel === 'chat' ? 'on' : ''} onClick={() => setPanel('chat')}>
              Chat
            </button>
            <button className={panel === 'log' ? 'on' : ''} onClick={() => setPanel('log')}>
              Histórico
            </button>
          </div>
          <div className="feed">
            {panel === 'chat'
              ? s.chat.map((m) => {
                  const p = s.players.find((x) => x.id === m.from);
                  return (
                    <div key={m.id} className={`msg ${m.from === snap.myId ? 'mine' : ''}`}>
                      <b style={{ color: p?.skin.body }}>{p?.name ?? '?'}:</b> {m.text}
                    </div>
                  );
                })
              : s.log.map((e, i) => (
                  <div key={i} className={`log-line log-${e.kind}`}>
                    {describe(e, s, snap.myId)}
                  </div>
                ))}
            <div ref={chatEnd} />
          </div>
          {panel === 'chat' && !spectator && (
            <form
              className="chat-form"
              onSubmit={(e) => {
                e.preventDefault();
                controller.chat(text);
                setText('');
              }}
            >
              <input value={text} maxLength={140} placeholder="Blefe à vontade..." onChange={(e) => setText(e.target.value)} />
              <button className="btn-primary" type="submit">
                ➤
              </button>
            </form>
          )}
        </aside>
      </div>

      <footer className="hand">
        <span className="hand-label">{spectator ? 'Assistindo' : me?.eliminated ? 'Você foi eliminado' : 'Suas cartas (vidas)'}</span>
        <div className="hand-cards">
          {snap.myHand.map((id) => {
            const c = s.deck.cards.find((x) => x.id === id);
            return c ? <CardView key={id} card={c} status="mine" /> : null;
          })}
        </div>
      </footer>

      {selectedCard && myTurn && (
        <div className="guess-bar">
          <span>
            Chutar <b>{selectedCard.name}</b>?
          </span>
          <button className="btn-ghost" onClick={() => setSelected(null)}>
            Cancelar
          </button>
          <button className="btn-primary" onClick={confirmGuess}>
            CHUTAR!
          </button>
        </div>
      )}

      {toast && <div className="toast">{toast}</div>}

      {s.phase === 'finished' && (
        <div className="overlay">
          <div className="modal results">
            <h2>{s.winnerId === snap.myId ? '🏆 VITÓRIA!' : `${nameOf(s.winnerId ?? '')} venceu!`}</h2>
            <ol className="ranking">
              {ranking.map((p, i) => (
                <li key={p.id} className={p.id === snap.myId ? 'me' : ''}>
                  <span>#{i + 1}</span>
                  <Crewmate skin={p.skin} size={30} dead={p.eliminated} />
                  <span className="r-name">{p.id === snap.myId ? 'Você' : p.name}</span>
                  <span>{p.handCount} 🂠</span>
                </li>
              ))}
            </ol>
            {earned !== null && !spectator && <p className="reward">+{earned} ●</p>}
            <button className="play-btn small" onClick={onExit}>
              CONTINUAR
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
