// Garante que toda fase pode ser terminada: um bot simples que só anda para a direita e pula tenta 30 vezes.
/* eslint-disable @typescript-eslint/no-explicit-any */
import { it, expect } from 'vitest';
import { LEVELS } from './levels';
import { Platformer, TILE } from './platformer';

function attempt(i: number, seed: number) {
  let s = seed;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const g = new Platformer(LEVELS[i], { body: '#f00', visor: '#0ff', hat: 'none' }, () => {});
  g.hud.lives = 50;
  const a = g as any;
  let jumpHold = 0;
  for (let step = 0; step < 60 * 180 && g.hud.status === 'playing'; step++) {
    const p = a.player;
    const ahead = p.x + p.w + 6;
    const wall = a.isSolid(ahead, p.y + p.h - 4);
    const pit = !a.isSolid(p.x + p.w + TILE * (0.3 + rnd() * 0.6), 11 * TILE + 4) && p.y > 9 * TILE;
    const hazard = [10, 11].some((r) => a.hazards.has(`${Math.floor((p.x + p.w + 20) / TILE)},${r}`)) && p.y > 9 * TILE;
    const enemy = a.enemies.some((e: any) => e.alive && e.x > p.x && e.x - p.x < 50 + rnd() * 60 && Math.abs(e.y - p.y) < 40);
    if (p.onGround && (wall || pit || hazard || enemy)) jumpHold = 10 + Math.floor(rnd() * 25);
    g.update(1 / 60, { left: false, right: true, jump: jumpHold-- > 0 });
  }
  return g.hud;
}

it.each([0, 1, 2])('fase %i pode ser completada', (i) => {
  const results = Array.from({ length: 30 }, (_, k) => attempt(i, k + 1));
  const wins = results.filter((r) => r.status === 'won');
  
  expect(wins.length).toBeGreaterThan(0);
});
