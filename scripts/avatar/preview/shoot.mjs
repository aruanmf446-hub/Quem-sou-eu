// node scripts/avatar/preview/shoot.mjs out.png "view=face&cfg=..." [w h]
import { chromium } from 'playwright';
const [out, query = '', w = '900', h = '1200'] = process.argv.slice(2);
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('[console]', m.text()); });
page.on('pageerror', e => console.log('[pageerror]', e.message));
await page.goto(`http://localhost:5173/scripts/avatar/preview/index.html?${query}`);
await page.waitForFunction(() => window.__ready, null, { timeout: 180000 });
const state = await page.evaluate(() => window.__ready);
if (state === 'error') console.log(await page.textContent('body'));
await page.screenshot({ path: out });
await browser.close();
