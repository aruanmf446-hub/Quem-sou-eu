import { chromium } from 'playwright';
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 400, height: 400 } });
page.on('console', m => console.log('[console]', m.text()));
await page.goto(`http://localhost:5173/scripts/avatar/preview/index.html?${process.argv[2]}`);
await page.waitForFunction(() => window.__ready, null, { timeout: 180000 });
console.log(await page.evaluate(process.argv[3]));
await browser.close();
