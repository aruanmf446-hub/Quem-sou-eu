import { useState } from 'react';
import { assetUrl } from '../config/assets';
import type { CharacterCard } from '../game/types';

export type CardStatus = 'open' | 'mine' | 'discarded' | 'missed';

interface Props {
  card: CharacterCard;
  status?: CardStatus;
  onClick?: () => void;
  disabled?: boolean;
  small?: boolean;
}

export function CardArt({ card }: { card: CharacterCard }) {
  const [failed, setFailed] = useState(false);
  const url = assetUrl(card.image);
  if (url && !failed) {
    return <img className="card-img" src={url} alt="" loading="lazy" onError={() => setFailed(true)} />;
  }
  return <span className="card-emoji">{card.emoji || '❔'}</span>;
}

export function CardView({ card, status = 'open', onClick, disabled, small }: Props) {
  return (
    <button
      type="button"
      className={`card card-${status}${small ? ' card-small' : ''}`}
      onClick={onClick}
      disabled={disabled || !onClick}
      title={card.name}
    >
      <div className="card-art">
        <CardArt card={card} />
      </div>
      <div className="card-name">{card.name}</div>
      {status === 'mine' && <div className="card-badge">SUA</div>}
      {status === 'missed' && <div className="card-badge badge-miss">NINGUÉM</div>}
      {status === 'discarded' && <div className="card-badge badge-out">FORA</div>}
    </button>
  );
}
