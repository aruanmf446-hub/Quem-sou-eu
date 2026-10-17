// Abre o jogo, entra no Estúdio 3D e fotografa (desktop e celular). node scripts/avatar/preview/studio.mjs out-prefix [actions]
import { chromium } from 'playwright';
const [prefix = '/tmp/studio', script = ''] = process.argv.slice(2);
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
for (const [name, viewport, mobile] of [['desktop', { width: 1440, height: 900 }, false], ['mobile', { width: 390, height: 844 }, true]]) {
  if (process.env.ONLY && process.env.ONLY !== name) continue;
  const ctx = await browser.newContext({ viewport, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('pageerror', e => console.log(`[${name} pageerror]`, e.message));
  page.on('console', m => { if (m.type() === 'error') console.log(`[${name} console]`, m.text()); });
  await page.goto('http://localhost:5173/');
  await page.click('.splash');
  await page.getByRole('button', { name: 'Estúdio 3D' }).click();
  await page.waitForSelector('.as-root .avatar-view.is-ready', { timeout: 240000 });
  await page.waitForFunction(() => !document.querySelector('.as-loading-pill'), null, { timeout: 240000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${prefix}-${name}.png` });
  if (script) { const fn = new Function('page', 'name', 'prefix', `return (async () => { ${script} })()`); await fn(page, name, prefix); }
  await ctx.close();
}
await browser.close();
