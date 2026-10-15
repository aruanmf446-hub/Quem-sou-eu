/**
 * Todos os arquivos de arte e música ficam no Cloudflare R2.
 * Defina VITE_ASSETS_BASE_URL com a URL pública do bucket (domínio próprio ou r2.dev).
 * Sem ela, o jogo usa placeholders gerados em código (emojis, SVG e chiptune).
 * A estrutura de pastas esperada está em docs/ASSETS.md.
 */
const BASE = (import.meta.env.VITE_ASSETS_BASE_URL as string | undefined)?.replace(/\/+$/, '') || '';

export const hasRemoteAssets = BASE.length > 0;

export function assetUrl(path?: string): string | null {
  if (!path) return null;
  if (/^https?:\/\//.test(path)) return path;
  return hasRemoteAssets ? `${BASE}/${path.replace(/^\/+/, '')}` : null;
}

export const MUSIC_TRACKS = {
  menu: 'music/menu.mp3',
  match: 'music/match.mp3',
  story: 'music/story.mp3',
  victory: 'music/victory.mp3',
} as const;

export type TrackId = keyof typeof MUSIC_TRACKS;

export const SFX = {
  click: 'sfx/click.mp3',
  hit: 'sfx/hit.mp3',
  miss: 'sfx/miss.mp3',
  coin: 'sfx/coin.mp3',
  jump: 'sfx/jump.mp3',
} as const;

export type SfxId = keyof typeof SFX;
