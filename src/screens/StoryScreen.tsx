import { useEffect, useRef, useState } from 'react';
import { LEVELS } from '../story/levels';
import { Platformer, type HudState, type Input } from '../story/platformer';
import { audio } from '../audio/music';
import { getProfile, setProfile } from '../lib/profile';
import { award } from '../lib/economy';

interface Props {
  level: number;
  onExit: () => void;
  onNext: (level: number) => void;
}

export function StoryScreen({ level, onExit, onNext }: Props) {
  const def = LEVELS[level - 1];
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const input = useRef<Input>({ left: false, right: false, jump: false });
  const [hud, setHud] = useState<HudState | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [intro, setIntro] = useState(true);
  const [reward, setReward] = useState<number | null>(null);

  useEffect(() => {
    if (intro) return;
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    const game = new Platformer(def, getProfile().skin, (e) => {
      if (e === 'coin' || e === 'card') audio.sfx('coin');
      if (e === 'jump') audio.sfx('jump');
      if (e === 'hurt') audio.sfx('miss');
      if (e === 'stomp') audio.sfx('hit');
      if (e === 'win') audio.play('victory');
    });
    let raf = 0;
    let last = performance.now();
    let lastHud = '';
    const loop = (t: number) => {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== Math.round(w * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      game.update((t - last) / 1000, input.current);
      last = t;
      game.render(ctx, w, h);
      const key = JSON.stringify(game.hud);
      if (key !== lastHud) {
        lastHud = key;
        setHud({ ...game.hud });
      }
      if (game.hud.status === 'playing') raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [def, attempt, intro]);

  // Teclado
  useEffect(() => {
    const map: Record<string, keyof Input> = {
      ArrowLeft: 'left', KeyA: 'left', ArrowRight: 'right', KeyD: 'right',
      ArrowUp: 'jump', KeyW: 'jump', Space: 'jump',
    };
    const down = (e: KeyboardEvent) => {
      const k = map[e.code];
      if (k) {
        input.current[k] = true;
        e.preventDefault();
      }
      if (e.code === 'Escape') onExit();
    };
    const up = (e: KeyboardEvent) => {
      const k = map[e.code];
      if (k) input.current[k] = false;
    };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
    };
  }, [onExit]);

  // Fim de fase: salva progresso e dá moedas.
  useEffect(() => {
    if (hud?.status !== 'won' || reward !== null) return;
    const coins = hud.coins + hud.cards * 20 + 30;
    setReward(coins);
    const p = getProfile();
    const prevBest = p.story.best[level];
    setProfile({
      story: {
        unlocked: Math.max(p.story.unlocked, Math.min(LEVELS.length, level + 1)),
        best: {
          ...p.story.best,
          [level]: { coins: Math.max(prevBest?.coins ?? 0, hud.coins), cards: Math.max(prevBest?.cards ?? 0, hud.cards) },
        },
      },
    });
    void award(Math.min(150, coins), `story-${level}`);
  }, [hud, level, reward]);

  const hold = (k: keyof Input) => ({
    onPointerDown: (e: React.PointerEvent) => {
      e.preventDefault();
      input.current[k] = true;
    },
    onPointerUp: () => (input.current[k] = false),
    onPointerLeave: () => (input.current[k] = false),
    onPointerCancel: () => (input.current[k] = false),
  });

  const retry = () => {
    audio.play('story');
    setReward(null);
    setHud(null);
    setAttempt((a) => a + 1);
  };

  if (intro) {
    return (
      <div className="story-intro">
        <h1>{def.name}</h1>
        <p>{def.intro}</p>
        <p className="hint">PC: setas/A-D para andar, espaço para pular. Celular: botões na tela.</p>
        <div className="row-center">
          <button className="btn-ghost" onClick={onExit}>
            Voltar
          </button>
          <button className="play-btn small" onClick={() => setIntro(false)}>
            COMEÇAR
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="story">
      <canvas ref={canvasRef} className="story-canvas" />
      {hud && (
        <div className="story-hud">
          <span>❤️ {hud.lives}</span>
          <span>● {hud.coins}</span>
          <span>
            🃏 {hud.cards}/{hud.totalCards}
          </span>
          <button className="icon-btn" onClick={onExit} aria-label="Sair">
            ✕
          </button>
        </div>
      )}
      <div className="touch-controls">
        <div className="dpad">
          <button {...hold('left')} aria-label="Esquerda">
            ◀
          </button>
          <button {...hold('right')} aria-label="Direita">
            ▶
          </button>
        </div>
        <button className="jump-btn" {...hold('jump')} aria-label="Pular">
          ▲
        </button>
      </div>
      {hud && hud.status !== 'playing' && (
        <div className="overlay">
          <div className="modal">
            {hud.status === 'won' ? (
              <>
                <h2>Fase completa!</h2>
                <p>
                  Cartas: {hud.cards}/{hud.totalCards} · Moedas da fase: {hud.coins}
                </p>
                <p className="reward">+{reward} ●</p>
                <div className="row-center">
                  <button className="btn-ghost" onClick={onExit}>
                    Menu
                  </button>
                  {level < LEVELS.length ? (
                    <button className="btn-primary" onClick={() => onNext(level + 1)}>
                      Próxima fase
                    </button>
                  ) : (
                    <button className="btn-primary" onClick={retry}>
                      Jogar de novo
                    </button>
                  )}
                </div>
              </>
            ) : (
              <>
                <h2>Fim de jogo</h2>
                <p>Os impostores venceram desta vez.</p>
                <div className="row-center">
                  <button className="btn-ghost" onClick={onExit}>
                    Menu
                  </button>
                  <button className="btn-primary" onClick={retry}>
                    Tentar de novo
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
