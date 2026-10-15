import { LEVELS } from '../story/levels';
import { useProfile } from '../lib/profile';

export function StoryTab({ onPlay }: { onPlay: (level: number) => void }) {
  const p = useProfile();
  return (
    <div className="story-tab">
      <h2>Modo história</h2>
      <p className="hint">Recupere as cartas roubadas pelos impostores. Cada carta vale 20 moedas.</p>
      <div className="levels">
        {LEVELS.map((lv, i) => {
          const n = i + 1;
          const locked = n > p.story.unlocked;
          const best = p.story.best[n];
          const total = lv.map.join('').split('C').length - 1;
          return (
            <button
              key={lv.name}
              className={`level-card ${locked ? 'locked' : ''}`}
              style={{ background: `linear-gradient(160deg, ${lv.sky[0]}, ${lv.sky[1]})` }}
              disabled={locked}
              onClick={() => onPlay(n)}
            >
              <span className="level-num">{locked ? '🔒' : n}</span>
              <b>{lv.name.replace(/^\d+\.\s*/, '')}</b>
              <small>{best ? `🃏 ${best.cards}/${total} · ● ${best.coins}` : locked ? 'Complete a fase anterior' : 'Nova!'}</small>
            </button>
          );
        })}
      </div>
    </div>
  );
}
