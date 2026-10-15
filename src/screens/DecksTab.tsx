import { useEffect, useState } from 'react';
import { CardView } from '../components/CardView';
import { OFFICIAL_DECKS, MAX_DECK_CARDS, MIN_DECK_CARDS } from '../data/decks';
import type { CharacterCard, Deck } from '../game/types';
import { maxPlayersForDeck } from '../game/engine';
import { ownsDeck, setProfile, useProfile } from '../lib/profile';
import { deleteDeckRemote, isOnlineAvailable, listCommunityDecks, saveDeckRemote } from '../lib/supabase';

function newDeck(): Deck {
  return { id: `custom-${Date.now()}`, name: 'Meu deck', description: '', cards: [], price: 0, official: false };
}

export function DecksTab() {
  const p = useProfile();
  const [editing, setEditing] = useState<Deck | null>(null);
  const [viewing, setViewing] = useState<Deck | null>(null);
  const [community, setCommunity] = useState<Deck[]>([]);

  useEffect(() => {
    if (isOnlineAvailable) void listCommunityDecks().then(setCommunity);
  }, []);

  if (editing) return <DeckEditor deck={editing} onClose={() => setEditing(null)} />;

  if (viewing) {
    return (
      <div className="deck-view">
        <button className="btn-ghost" onClick={() => setViewing(null)}>
          ← Voltar
        </button>
        <h2>{viewing.name}</h2>
        <p>{viewing.description}</p>
        <div className="board">
          {viewing.cards.map((c) => (
            <CardView key={c.id} card={c} small />
          ))}
        </div>
      </div>
    );
  }

  const DeckRow = ({ d, mine }: { d: Deck; mine?: boolean }) => (
    <div className={`deck-row ${p.selectedDeckId === d.id ? 'selected' : ''}`}>
      <div className="deck-emojis">{d.cards.slice(0, 4).map((c) => c.emoji).join('')}</div>
      <div className="deck-meta">
        <b>{d.name}</b>
        <small>
          {d.cards.length} cartas · até {maxPlayersForDeck(d)} jogadores {d.author ? `· por ${d.author}` : ''}
          {d.official && d.price > 0 && !ownsDeck(p, d) ? ` · ● ${d.price} na Loja` : ''}
        </small>
      </div>
      <div className="deck-actions">
        <button className="btn-ghost" onClick={() => setViewing(d)}>
          Ver
        </button>
        {ownsDeck(p, d) && d.cards.length >= MIN_DECK_CARDS && (
          <button className="btn-ghost" onClick={() => setProfile({ selectedDeckId: d.id })}>
            {p.selectedDeckId === d.id ? '✓ Usando' : 'Usar'}
          </button>
        )}
        {mine && (
          <button className="btn-ghost" onClick={() => setEditing(d)}>
            Editar
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="decks">
      <h2>Decks oficiais</h2>
      {OFFICIAL_DECKS.map((d) => (
        <DeckRow key={d.id} d={d} />
      ))}

      <div className="row-between">
        <h2>Meus decks</h2>
        <button className="btn-primary" onClick={() => setEditing(newDeck())}>
          + Criar deck
        </button>
      </div>
      {p.customDecks.length === 0 && <p className="hint">Crie seu próprio deck com no mínimo {MIN_DECK_CARDS} personagens.</p>}
      {p.customDecks.map((d) => (
        <DeckRow key={d.id} d={d} mine />
      ))}

      {isOnlineAvailable && (
        <>
          <h2>Comunidade</h2>
          {community.length === 0 && <p className="hint">Nenhum deck público ainda.</p>}
          {community
            .filter((d) => !p.customDecks.some((m) => m.id === d.id))
            .map((d) => (
              <div key={d.id} className="deck-row">
                <div className="deck-emojis">{d.cards.slice(0, 4).map((c) => c.emoji).join('')}</div>
                <div className="deck-meta">
                  <b>{d.name}</b>
                  <small>
                    {d.cards.length} cartas · por {d.author ?? 'anônimo'}
                  </small>
                </div>
                <button
                  className="btn-ghost"
                  onClick={() =>
                    setProfile((cur) => ({ customDecks: [...cur.customDecks, { ...d, id: `custom-${Date.now()}`, name: `${d.name} (cópia)` }] }))
                  }
                >
                  Copiar
                </button>
              </div>
            ))}
        </>
      )}
    </div>
  );
}

function DeckEditor({ deck, onClose }: { deck: Deck; onClose: () => void }) {
  const [draft, setDraft] = useState<Deck>(deck);
  const [name, setName] = useState('');
  const [emoji, setEmoji] = useState('');
  const [image, setImage] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const exists = useProfile().customDecks.some((d) => d.id === deck.id);

  function addCard() {
    const n = name.trim();
    if (!n) return;
    if (draft.cards.some((c) => c.name.toLowerCase() === n.toLowerCase())) return setError('Já existe um personagem com esse nome');
    if (draft.cards.length >= MAX_DECK_CARDS) return setError(`Máximo de ${MAX_DECK_CARDS} cartas`);
    const card: CharacterCard = { id: `${draft.id}-${Date.now().toString(36)}`, name: n.slice(0, 24), emoji: emoji.trim() || '❔', image: image.trim() || undefined };
    setDraft({ ...draft, cards: [...draft.cards, card] });
    setName('');
    setEmoji('');
    setImage('');
    setError('');
  }

  async function save() {
    if (!draft.name.trim()) return setError('Dê um nome ao deck');
    if (draft.cards.length < MIN_DECK_CARDS) return setError(`O deck precisa de pelo menos ${MIN_DECK_CARDS} cartas`);
    setSaving(true);
    try {
      const saved = await saveDeckRemote(draft, isPublic).catch((e: Error) => {
        setError(`Salvo só neste aparelho (${e.message})`);
        return draft;
      });
      setProfile((cur) => ({
        customDecks: cur.customDecks.some((d) => d.id === deck.id)
          ? cur.customDecks.map((d) => (d.id === deck.id ? saved : d))
          : [...cur.customDecks, saved],
      }));
      onClose();
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!confirm(`Apagar o deck "${deck.name}"?`)) return;
    await deleteDeckRemote(deck.id);
    setProfile((cur) => ({ customDecks: cur.customDecks.filter((d) => d.id !== deck.id), selectedDeckId: cur.selectedDeckId === deck.id ? 'espaco' : cur.selectedDeckId }));
    onClose();
  }

  return (
    <div className="deck-editor">
      <div className="row-between">
        <button className="btn-ghost" onClick={onClose}>
          ← Cancelar
        </button>
        <span className={draft.cards.length >= MIN_DECK_CARDS ? 'ok' : 'warn'}>
          {draft.cards.length}/{MIN_DECK_CARDS}+ cartas
        </span>
      </div>
      <input className="field" value={draft.name} maxLength={40} placeholder="Nome do deck" onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
      <input className="field" value={draft.description} maxLength={120} placeholder="Descrição" onChange={(e) => setDraft({ ...draft, description: e.target.value })} />

      <form
        className="add-card"
        onSubmit={(e) => {
          e.preventDefault();
          addCard();
        }}
      >
        <input className="field emoji-field" value={emoji} placeholder="😀" maxLength={8} onChange={(e) => setEmoji(e.target.value)} />
        <input className="field" value={name} placeholder="Nome do personagem" maxLength={24} onChange={(e) => setName(e.target.value)} />
        <input className="field" value={image} placeholder="Imagem (opcional, caminho no R2 ou URL)" onChange={(e) => setImage(e.target.value)} />
        <button className="btn-primary" type="submit">
          Adicionar
        </button>
      </form>
      {error && <p className="error">{error}</p>}

      <div className="board">
        {draft.cards.map((c) => (
          <div key={c.id} className="editable-card">
            <CardView card={c} small />
            <button className="remove" onClick={() => setDraft({ ...draft, cards: draft.cards.filter((x) => x.id !== c.id) })} aria-label={`Remover ${c.name}`}>
              ×
            </button>
          </div>
        ))}
      </div>

      <div className="row-between">
        {isOnlineAvailable ? (
          <label className="check">
            <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} /> Publicar para a comunidade
          </label>
        ) : (
          <span />
        )}
        <div className="deck-actions">
          {exists && (
            <button className="btn-danger" onClick={remove}>
              Apagar
            </button>
          )}
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving ? 'Salvando...' : 'Salvar deck'}
          </button>
        </div>
      </div>
    </div>
  );
}
