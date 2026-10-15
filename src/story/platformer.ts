import type { Skin } from '../game/types';
import type { LevelDef } from './levels';

export const TILE = 32;
const GRAVITY = 1900;
const JUMP_V = 760;
const RUN = 250;
const ACCEL = 1800;
const ENEMY_SPEED = 60;
const PLAYER_W = 24;
const PLAYER_H = 30;

export interface Input {
  left: boolean;
  right: boolean;
  jump: boolean;
}

interface Body {
  x: number;
  y: number;
  vx: number;
  vy: number;
  w: number;
  h: number;
  onGround: boolean;
}

interface Enemy extends Body {
  alive: boolean;
  squash: number;
}

interface Pickup {
  x: number;
  y: number;
  kind: 'coin' | 'card';
  taken: boolean;
}

export interface HudState {
  coins: number;
  cards: number;
  totalCards: number;
  lives: number;
  status: 'playing' | 'won' | 'dead' | 'gameover';
}

export type StoryEvent = 'coin' | 'card' | 'jump' | 'hurt' | 'stomp' | 'win';

/** Motor da fase estilo Mario: física simples em grade, inimigos que andam, coletáveis. */
export class Platformer {
  private solid: Set<string> = new Set();
  private hazards: Set<string> = new Set();
  private bonus: Map<string, boolean> = new Map();
  private pickups: Pickup[] = [];
  private enemies: Enemy[] = [];
  private spawn = { x: 0, y: 0 };
  private goal = { x: 0, y: 0 };
  private player: Body;
  private camX = 0;
  private jumpHeld = false;
  private coyote = 0;
  private invuln = 0;
  private time = 0;
  readonly width: number;
  readonly height: number;
  hud: HudState;

  constructor(private level: LevelDef, private skin: Skin, private onEvent: (e: StoryEvent) => void) {
    const rows = level.map;
    this.height = rows.length * TILE;
    this.width = Math.max(...rows.map((r) => r.length)) * TILE;
    let cards = 0;
    rows.forEach((row, ty) => {
      [...row].forEach((ch, tx) => {
        const key = `${tx},${ty}`;
        const px = tx * TILE;
        const py = ty * TILE;
        if (ch === '#' || ch === '=') this.solid.add(key);
        if (ch === '?') {
          this.solid.add(key);
          this.bonus.set(key, true);
        }
        if (ch === '^') this.hazards.add(key);
        if (ch === 'o') this.pickups.push({ x: px + TILE / 2, y: py + TILE / 2, kind: 'coin', taken: false });
        if (ch === 'C') {
          this.pickups.push({ x: px + TILE / 2, y: py + TILE / 2, kind: 'card', taken: false });
          cards++;
        }
        if (ch === 'E') this.enemies.push({ x: px + 4, y: py + 8, vx: -ENEMY_SPEED, vy: 0, w: 24, h: 24, onGround: false, alive: true, squash: 0 });
        if (ch === 'P') this.spawn = { x: px + 4, y: py };
        if (ch === 'F') this.goal = { x: px, y: py };
      });
    });
    this.player = this.newPlayer();
    this.hud = { coins: 0, cards: 0, totalCards: cards, lives: 3, status: 'playing' };
  }

  private newPlayer(): Body {
    return { x: this.spawn.x, y: this.spawn.y, vx: 0, vy: 0, w: PLAYER_W, h: PLAYER_H, onGround: false };
  }

  private isSolid(px: number, py: number) {
    if (px < 0) return true;
    return this.solid.has(`${Math.floor(px / TILE)},${Math.floor(py / TILE)}`);
  }

  /** Move em X e depois em Y, resolvendo colisão com os tiles. Retorna o tile batido com a cabeça. */
  private moveBody(b: Body, dt: number): { hitX: boolean; headKey: string | null } {
    let hitX = false;
    let headKey: string | null = null;
    b.x += b.vx * dt;
    const top = b.y + 1;
    const bottom = b.y + b.h - 1;
    if (b.vx > 0 && (this.isSolid(b.x + b.w, top) || this.isSolid(b.x + b.w, bottom))) {
      b.x = Math.floor((b.x + b.w) / TILE) * TILE - b.w - 0.01;
      hitX = true;
    } else if (b.vx < 0 && (this.isSolid(b.x, top) || this.isSolid(b.x, bottom))) {
      b.x = Math.floor(b.x / TILE + 1) * TILE + 0.01;
      hitX = true;
    }
    b.vy = Math.min(b.vy + GRAVITY * dt, 1100);
    b.y += b.vy * dt;
    b.onGround = false;
    const left = b.x + 1;
    const right = b.x + b.w - 1;
    if (b.vy > 0 && (this.isSolid(left, b.y + b.h) || this.isSolid(right, b.y + b.h))) {
      b.y = Math.floor((b.y + b.h) / TILE) * TILE - b.h;
      b.vy = 0;
      b.onGround = true;
    } else if (b.vy < 0 && (this.isSolid(left, b.y) || this.isSolid(right, b.y))) {
      const hx = this.isSolid(b.x + b.w / 2, b.y) ? b.x + b.w / 2 : this.isSolid(left, b.y) ? left : right;
      headKey = `${Math.floor(hx / TILE)},${Math.floor(b.y / TILE)}`;
      b.y = Math.floor(b.y / TILE + 1) * TILE;
      b.vy = 0;
    }
    return { hitX, headKey };
  }

  update(dt: number, input: Input) {
    if (this.hud.status !== 'playing') return;
    dt = Math.min(dt, 1 / 30);
    this.time += dt;
    const p = this.player;

    const dir = (input.right ? 1 : 0) - (input.left ? 1 : 0);
    if (dir !== 0) p.vx = Math.max(-RUN, Math.min(RUN, p.vx + dir * ACCEL * dt));
    else p.vx *= p.onGround ? 0.75 : 0.95;
    if (Math.abs(p.vx) < 5) p.vx = 0;

    this.coyote = p.onGround ? 0.1 : Math.max(0, this.coyote - dt);
    if (input.jump && !this.jumpHeld && this.coyote > 0) {
      p.vy = -JUMP_V;
      this.coyote = 0;
      this.onEvent('jump');
    }
    // Soltar o pulo cedo = pulo mais baixo.
    if (!input.jump && p.vy < -JUMP_V * 0.45) p.vy = -JUMP_V * 0.45;
    this.jumpHeld = input.jump;

    const { headKey } = this.moveBody(p, dt);
    if (headKey && this.bonus.get(headKey)) {
      this.bonus.set(headKey, false);
      this.hud.coins += 1;
      this.onEvent('coin');
    }

    if (p.x > this.width - p.w) p.x = this.width - p.w;
    this.invuln = Math.max(0, this.invuln - dt);

    // Espinhos
    const feetY = p.y + p.h + 1;
    const spikes = [p.x + 3, p.x + p.w - 3].some((x) => this.hazards.has(`${Math.floor(x / TILE)},${Math.floor((feetY - 4) / TILE)}`));
    if (spikes) this.hurt();
    if (p.y > this.height + 50) return this.die();

    for (const e of this.enemies) {
      if (!e.alive) {
        e.squash -= dt;
        continue;
      }
      const { hitX } = this.moveBody(e, dt);
      // Vira na parede ou na beira da plataforma.
      const aheadX = e.vx > 0 ? e.x + e.w + 2 : e.x - 2;
      if (hitX || (e.onGround && !this.isSolid(aheadX, e.y + e.h + 4))) e.vx = -e.vx;
      if (e.y > this.height + 50) e.alive = false;
      if (overlap(p, e)) {
        if (p.vy > 0 && p.y + p.h - e.y < 14) {
          e.alive = false;
          e.squash = 0.4;
          p.vy = -JUMP_V * 0.6;
          this.hud.coins += 2;
          this.onEvent('stomp');
        } else {
          this.hurt();
        }
      }
    }

    for (const it of this.pickups) {
      if (it.taken) continue;
      if (Math.abs(p.x + p.w / 2 - it.x) < 20 && Math.abs(p.y + p.h / 2 - it.y) < 24) {
        it.taken = true;
        if (it.kind === 'coin') {
          this.hud.coins += 1;
          this.onEvent('coin');
        } else {
          this.hud.cards += 1;
          this.onEvent('card');
        }
      }
    }

    if (p.x + p.w > this.goal.x + 8 && p.x < this.goal.x + TILE && p.y + p.h > this.goal.y) {
      this.hud.status = 'won';
      this.onEvent('win');
    }
  }

  private hurt() {
    if (this.invuln > 0) return;
    this.hud.lives -= 1;
    this.onEvent('hurt');
    if (this.hud.lives <= 0) {
      this.hud.status = 'gameover';
      return;
    }
    this.invuln = 1.5;
    this.player.vy = -JUMP_V * 0.5;
  }

  private die() {
    this.hud.lives -= 1;
    this.onEvent('hurt');
    if (this.hud.lives <= 0) {
      this.hud.status = 'gameover';
      return;
    }
    this.player = this.newPlayer();
    this.invuln = 1.5;
  }

  render(ctx: CanvasRenderingContext2D, viewW: number, viewH: number) {
    const scale = viewH / this.height;
    const worldViewW = viewW / scale;
    const target = this.player.x - worldViewW * 0.4;
    this.camX = Math.max(0, Math.min(this.width - worldViewW, target));

    const sky = ctx.createLinearGradient(0, 0, 0, viewH);
    sky.addColorStop(0, this.level.sky[0]);
    sky.addColorStop(1, this.level.sky[1]);
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, viewW, viewH);

    ctx.save();
    ctx.scale(scale, scale);
    // Estrelas com parallax
    ctx.fillStyle = 'rgba(255,255,255,0.7)';
    for (let i = 0; i < 80; i++) {
      const sx = ((i * 97) % 1000) * 1.3 - this.camX * 0.2;
      const x = ((sx % (worldViewW + 40)) + worldViewW + 40) % (worldViewW + 40);
      const y = (i * 53) % (this.height * 0.6);
      ctx.fillRect(x, y, 2, 2);
    }
    ctx.translate(-Math.floor(this.camX), 0);

    const x0 = Math.floor(this.camX / TILE) - 1;
    const x1 = x0 + Math.ceil(worldViewW / TILE) + 2;
    this.level.map.forEach((row, ty) => {
      for (let tx = x0; tx <= x1; tx++) {
        const ch = row[tx];
        const px = tx * TILE;
        const py = ty * TILE;
        if (ch === '#') {
          const top = this.level.map[ty - 1]?.[tx];
          ctx.fillStyle = '#5b4a7a';
          ctx.fillRect(px, py, TILE, TILE);
          ctx.fillStyle = '#7a66a3';
          ctx.fillRect(px + 2, py + 2, TILE - 4, TILE - 4);
          if (top !== '#' && top !== '^' && top !== '=') {
            ctx.fillStyle = '#4ad991';
            ctx.fillRect(px, py, TILE, 7);
          }
        } else if (ch === '=') {
          ctx.fillStyle = '#c0632f';
          ctx.fillRect(px, py, TILE, TILE);
          ctx.strokeStyle = '#7a3412';
          ctx.lineWidth = 2;
          ctx.strokeRect(px + 1, py + 1, TILE - 2, TILE / 2 - 1);
          ctx.strokeRect(px + 1, py + TILE / 2, TILE - 2, TILE / 2 - 1);
        } else if (ch === '?') {
          const active = this.bonus.get(`${tx},${ty}`);
          ctx.fillStyle = active ? '#f5c518' : '#8a6d3b';
          ctx.fillRect(px, py, TILE, TILE);
          ctx.strokeStyle = '#5a3d0a';
          ctx.lineWidth = 3;
          ctx.strokeRect(px + 1.5, py + 1.5, TILE - 3, TILE - 3);
          if (active) {
            ctx.fillStyle = '#5a3d0a';
            ctx.font = 'bold 22px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('?', px + TILE / 2, py + 24);
          }
        } else if (ch === '^') {
          ctx.fillStyle = '#d9dde3';
          for (let i = 0; i < 3; i++) {
            ctx.beginPath();
            ctx.moveTo(px + i * 11, py + TILE);
            ctx.lineTo(px + i * 11 + 5.5, py + 8);
            ctx.lineTo(px + i * 11 + 11, py + TILE);
            ctx.fill();
          }
        }
      }
    });

    // Bandeira
    const gx = this.goal.x + TILE / 2;
    ctx.fillStyle = '#ddd';
    ctx.fillRect(gx - 2, this.goal.y, 4, 11 * TILE - this.goal.y);
    ctx.fillStyle = '#e8384f';
    ctx.beginPath();
    ctx.moveTo(gx + 2, this.goal.y);
    ctx.lineTo(gx + 30, this.goal.y + 10 + Math.sin(this.time * 6) * 2);
    ctx.lineTo(gx + 2, this.goal.y + 20);
    ctx.fill();

    for (const it of this.pickups) {
      if (it.taken) continue;
      const bob = Math.sin(this.time * 4 + it.x) * 3;
      if (it.kind === 'coin') {
        ctx.fillStyle = '#ffd23a';
        ctx.beginPath();
        ctx.ellipse(it.x, it.y + bob, 7 * Math.abs(Math.cos(this.time * 3 + it.x)) + 2, 9, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#b8860b';
        ctx.lineWidth = 2;
        ctx.stroke();
      } else {
        ctx.save();
        ctx.translate(it.x, it.y + bob);
        ctx.rotate(Math.sin(this.time * 2) * 0.15);
        ctx.fillStyle = '#fff';
        ctx.strokeStyle = '#2f6fe4';
        ctx.lineWidth = 3;
        roundRect(ctx, -11, -15, 22, 30, 4);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#2f6fe4';
        ctx.font = 'bold 16px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('?', 0, 6);
        ctx.restore();
      }
    }

    for (const e of this.enemies) {
      if (!e.alive && e.squash <= 0) continue;
      drawCrew(ctx, e.x, e.y, e.w, e.h, { body: '#30343b', visor: '#ff4757', hat: 'chifres' }, e.vx < 0, e.alive ? 1 : 0.35);
    }

    const p = this.player;
    if (this.invuln <= 0 || Math.floor(this.time * 12) % 2 === 0) {
      drawCrew(ctx, p.x, p.y, p.w, p.h, this.skin, p.vx < 0, 1);
    }
    ctx.restore();
  }
}

function overlap(a: Body, b: Body) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** Tripulante desenhado no canvas (versão simplificada do SVG). */
function drawCrew(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, skin: Skin, flip: boolean, squashY: number) {
  ctx.save();
  ctx.translate(x + w / 2, y + h);
  ctx.scale(flip ? -1 : 1, squashY);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = '#111';
  ctx.fillStyle = skin.body;
  // mochila
  roundRect(ctx, -w / 2 - 4, -h * 0.72, 7, h * 0.42, 3);
  ctx.fill();
  ctx.stroke();
  // corpo
  roundRect(ctx, -w / 2, -h, w, h, w * 0.45);
  ctx.fill();
  ctx.stroke();
  // visor
  ctx.fillStyle = skin.visor;
  roundRect(ctx, -2, -h * 0.78, w / 2 + 5, h * 0.3, 5);
  ctx.fill();
  ctx.stroke();
  if (skin.hat === 'chifres') {
    ctx.fillStyle = '#e23b3b';
    ctx.beginPath();
    ctx.moveTo(-8, -h);
    ctx.lineTo(-6, -h - 8);
    ctx.lineTo(-2, -h);
    ctx.moveTo(4, -h);
    ctx.lineTo(7, -h - 8);
    ctx.lineTo(9, -h);
    ctx.fill();
  } else if (skin.hat !== 'none') {
    ctx.fillStyle = skin.hat === 'coroa' || skin.hat === 'aureola' ? '#ffd23a' : '#ff5fa2';
    ctx.fillRect(-7, -h - 6, 14, 6);
  }
  ctx.restore();
}
