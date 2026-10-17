import { useEffect, useState } from 'react';
import { Crewmate } from '../components/Crewmate';
import { maxPlayersForDeck, MIN_PLAYERS } from '../game/engine';
import { playableDecks, setProfile, useProfile } from '../lib/profile';
import type { MatchController } from '../online/match';
import type { LobbyState, Room } from '../online/room';

interface Props {
  room: Room;
  onMatch: (m: MatchController) => void;
  onExit: () => void;
}

export function RoomScreen({ room, onMatch, onExit }: Props) {
  const profile = useProfile();
  const [lobby, setLobby] = useState<LobbyState | null>(null);
  const [total, setTotal] = useState(6);
  const [error, setError] = useState('');
  const decks = playableDecks(profile);
  const deck = decks.find((d) => d.id === profile.selectedDeckId) ?? decks[0];
  const maxP = maxPlayersForDeck(deck);

  useEffect(() => {
    room.onMatchStart(onMatch);
    return room.subscribe(setLobby);
  }, [room, onMatch]);

  if (!lobby) return <div className="center-msg">Conectando...</div>;

  const humans = lobby.members.length;
  const target = Math.max(humans, MIN_PLAYERS, Math.min(total, maxP));

  return (
    <div className="room">
      <header className="room-head">
        <button className="btn-ghost" onClick={onExit}>
          ← Sair
        </button>
        <div className="room-code" onClick={() => navigator.clipboard?.writeText(lobby.code)} title="Copiar código">
          SALA <b>{lobby.code}</b>
        </div>
      </header>

      {lobby.status === 'closed' ? (
        <div className="center-msg">
          <p>{lobby.message}</p>
          <button className="btn-primary" onClick={onExit}>
            Voltar ao menu
          </button>
        </div>
      ) : (
        <>
          <div className="room-players">
            {lobby.members.map((m) => (
              <div key={m.id} className="room-player">
                {m.id === profile.id && profile.avatarPortrait ? <img className="seat-portrait room-portrait float" src={profile.avatarPortrait} alt="Seu personagem" width={64} height={64} /> : <Crewmate skin={m.skin} size={64} className="float" />}
                <span>
                  {m.name}
                  {m.isHost ? ' 👑' : ''}
                </span>
              </div>
            ))}
            {Array.from({ length: Math.max(0, target - humans) }).map((_, i) => (
              <div key={`bot-${i}`} className="room-player bot-slot">
                <Crewmate skin={{ body: '#666', visor: '#999', hat: 'none' }} size={64} />
                <span>Bot</span>
              </div>
            ))}
          </div>

          {lobby.isHost ? (
            <div className="panel room-panel">
              <h3>Deck</h3>
              <select value={deck.id} onChange={(e) => setProfile({ selectedDeckId: e.target.value })}>
                {decks.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.cards.length} cartas)
                  </option>
                ))}
              </select>
              <h3>
                Total de jogadores (com bots): <b>{target}</b>
              </h3>
              <input type="range" min={Math.max(MIN_PLAYERS, humans)} max={maxP} value={target} onChange={(e) => setTotal(Number(e.target.value))} />
              {humans > maxP && <p className="error">Esse deck comporta no máximo {maxP} jogadores.</p>}
              {error && <p className="error">{error}</p>}
              <button
                className="play-btn"
                disabled={humans > maxP}
                onClick={() => {
                  try {
                    room.start(deck, target);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                COMEÇAR
              </button>
            </div>
          ) : (
            <p className="center-msg">Esperando o anfitrião começar a partida...</p>
          )}
          <p className="hint center">Passe o código para seus amigos entrarem pelo botão "Entrar".</p>
        </>
      )}
    </div>
  );
}
