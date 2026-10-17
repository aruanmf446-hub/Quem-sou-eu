// Miniaturas das peças e dos personagens renderizadas pelo próprio motor do jogo.
// Requer o servidor de desenvolvimento (npm run dev). node scripts/avatar/thumbs.mjs [ids...]
import { chromium } from 'playwright';
import { readFileSync, mkdirSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
const root = new URL('../../', import.meta.url).pathname;
const out = `${root}public/avatar/thumbs`;
mkdirSync(out, { recursive: true });
const catalog = readFileSync(`${root}src/avatar/catalog.ts`, 'utf8');
const items = [...catalog.matchAll(/\{ id: '([\w-]+)', slot: '(\w+)'/g)].map(m => ({ id: m[1], slot: m[2] }));
const only = process.argv.slice(2);
const base = { skinTone: '#a8714e', hairColor: '#2b1d14', items: { brows: 'brows_natural' } };
const HEAD = new Set(['hair', 'brows', 'beard', 'eyewear', 'headwear']);
function job(item) {
  const cfg = structuredClone(base);
  cfg.items[item.slot] = item.id;
  if (item.id === 'hair_curly_fade') cfg.hairTips = '#e2bf7a';
  if (item.id === 'hair_clown') cfg.hairColor = '#d9481c';
  if (item.slot === 'bodyart' && item.id.startsWith('facepaint')) cfg.skinTone = '#e9dccf';
  const p = new URLSearchParams({ cfg: JSON.stringify(cfg), transparent: '1', only: item.id, fit: HEAD.has(item.slot) ? 'all' : 'item' });
  if (HEAD.has(item.slot) || item.id.startsWith('facepaint')) { p.set('keepHead', '1'); p.set('az', '.45'); p.set('pad', '1.05'); }
  if (item.slot === 'bodyart' && item.id.startsWith('tattoo')) { p.set('keepBody', '1'); p.set('fit', 'item'); p.set('az', '-.9'); p.set('pad', '1.25'); }
  if (item.slot === 'shoes' || item.slot === 'socks') { p.set('az', '.85'); p.set('el', '.3'); }
  if (item.slot === 'brows') { p.set('az', '.15'); }
  return { name: item.id, query: p.toString(), w: 320, h: 320 };
}
const jobs = items.filter(i => existsSync(`${root}public/avatar/items/${i.id}.glb`)).map(job);
const bundles = [...catalog.matchAll(/id: '(street|striker|night-clown)', name: '[^']+'[\s\S]*?config: base\((\{[\s\S]*?\})\),\n  \}/g)];
for (const id of ['street', 'striker', 'night-clown']) jobs.push({ name: `bundle_${id}`, bundle: id, w: 360, h: 440 });
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 320, height: 320 } });
page.on('pageerror', e => console.log('[pageerror]', e.message));
for (const j of jobs) {
  if (only.length && !only.includes(j.name)) continue;
  await page.setViewportSize({ width: j.w, height: j.h });
  const query = j.query ?? new URLSearchParams({ bundle: j.bundle, transparent: '1', fit: 'all', az: '.35', pad: '1.06', el: '.05' }).toString();
  await page.goto(`http://localhost:5173/scripts/avatar/preview/index.html?${query}`);
  await page.waitForFunction(() => window.__ready, null, { timeout: 180000 });
  const png = `${out}/${j.name}.png`;
  await page.screenshot({ path: png, omitBackground: true });
  execFileSync('python3', ['-c', `from PIL import Image; im=Image.open('${png}'); im.save('${out}/${j.name}.webp','WEBP',quality=86,method=6)`]);
  execFileSync('rm', [png]);
  console.log('ok', j.name);
}
await browser.close();
