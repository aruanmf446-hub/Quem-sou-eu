// Fluxo completo do jogador no Estúdio 3D (sem nenhuma etapa técnica): criar, vestir, dançar,
// comprar, salvar, recarregar e usar o avatar no lobby e na partida.
// node scripts/avatar/preview/e2e.mjs [pasta-de-saída]
import { chromium } from 'playwright';
const out = process.argv[2] ?? '/tmp/e2e';
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
let failures = 0;
const check = (ok, msg) => { console.log(`${ok ? '✓' : '✗'} ${msg}`); if (!ok) failures++; };
for (const [name, viewport, mobile] of [['desktop', { width: 1440, height: 900 }, false], ['mobile', { width: 390, height: 844 }, true]]) {
  if (process.env.ONLY && process.env.ONLY !== name) continue;
  console.log(`\n== ${name}`);
  const ctx = await browser.newContext({ viewport, isMobile: mobile, hasTouch: mobile });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const ready = async () => {
    await page.waitForSelector('.as-root .avatar-view.is-ready', { timeout: 240000 });
    await page.waitForFunction(() => !document.querySelector('.avatar-view-swap'), null, { timeout: 240000 });
    await page.waitForTimeout(800);
  };
  const tab = n => page.getByRole('tab', { name: n }).click();
  await page.goto('http://localhost:5173/');
  await page.click('.splash');
  await page.getByRole('button', { name: 'Estúdio 3D' }).click();
  await ready();
  check(await page.locator('.as-status.ok').isVisible(), 'perfil novo já aparece equipado (Nova)');
  // Corpo e rosto
  await tab('Corpo');
  await page.getByRole('slider', { name: 'Estrutura' }).fill('0');
  await page.getByRole('slider', { name: 'Musculatura' }).fill('0.6');
  await page.getByRole('slider', { name: 'Altura' }).fill('0.3');
  await tab('Rosto');
  await page.getByRole('button', { name: 'Quadrado' }).click();
  await page.getByRole('slider', { name: 'Mandíbula' }).fill('0.5');
  // Pele, cabelo, barba
  await tab('Pele e cabelo');
  await page.getByRole('radio', { name: 'Pele #8d5a3b' }).click();
  await page.getByRole('button', { name: /Raspado/ }).click();
  await page.getByRole('button', { name: /Cavanhaque/ }).click();
  await page.getByRole('radio', { name: 'Cabelo #3a2618' }).click();
  // Roupas e calçados
  await tab('Roupas');
  await page.getByRole('button', { name: /Camiseta essencial/ }).click();
  await page.getByRole('radio', { name: 'Cor #efc51d' }).click();
  await page.getByRole('tab', { name: 'Parte de baixo' }).click();
  await page.getByRole('button', { name: /Bermuda esportiva/ }).click();
  await tab('Calçados');
  await page.getByRole('button', { name: /Tênis casual/ }).click();
  await tab('Acessórios');
  await page.getByRole('button', { name: /Faixa esportiva/ }).click();
  // Dança (compra) e comemoração
  await tab('Danças');
  await page.getByRole('button', { name: /Passinho do craque/ }).click();
  await page.getByRole('button', { name: /Aviãozinho/ }).click();
  await ready();
  await page.screenshot({ path: `${out}-${name}-criado.png` });
  const summary = await page.locator('.as-actions-summary').innerText();
  check(/125/.test(summary), `carrinho mostra 125 moedas (faixa 25 + dança 100): ${summary.replace(/\n/g, ' ')}`);
  // Salvar visual
  await page.getByRole('button', { name: 'Salvar visual' }).click();
  await page.getByRole('textbox', { name: 'Nome do visual' }).fill('Craque de treino');
  await page.getByRole('button', { name: 'Salvar em Meus visuais' }).click();
  // Comprar e equipar
  await page.getByRole('button', { name: 'Comprar e equipar' }).click();
  await page.getByRole('button', { name: /Comprar e equipar · 125/ }).click();
  await page.waitForSelector('.as-status.ok', { timeout: 30000 });
  check(true, 'compra concluída e avatar equipado');
  const coins = await page.locator('.coins').innerText();
  check(coins.includes('75'), `saldo debitado: ${coins.trim()}`);
  // Persistência após recarregar
  await page.reload();
  await page.click('.splash');
  await page.getByRole('button', { name: 'Estúdio 3D' }).click();
  await ready();
  check(await page.locator('.as-status.ok').isVisible(), 'após recarregar, o visual criado continua equipado');
  await tab('Visuais');
  check(await page.getByText('Craque de treino').isVisible(), 'visual salvo aparece em Meus visuais');
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('quem-sou-eu:profile:v1')));
  check(stored.avatar.creator.items.headwear === 'headband' && stored.ownedItems.includes('headband') && stored.ownedDances.includes('samba'), 'perfil salvo com peças, compras e dança');
  check(!!stored.avatarPortrait, 'retrato do avatar gerado para outras telas');
  await page.screenshot({ path: `${out}-${name}-recarregado.png` });
  // Uso no jogo: lobby e partida
  await page.getByRole('button', { name: 'Jogar com ele' }).click();
  await page.waitForSelector('.lobby-character .avatar-view.is-ready', { timeout: 240000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${out}-${name}-lobby.png` });
  check(true, 'avatar dança no lobby');
  await page.getByRole('button', { name: 'Comemorar' }).click();
  await page.waitForTimeout(1500);
  await page.locator('.play-btn').click();
  await page.waitForSelector('.seat-portrait', { timeout: 30000 });
  await page.screenshot({ path: `${out}-${name}-partida.png` });
  check(true, 'retrato 3D do jogador aparece na partida');
  check(errors.length === 0, `sem erros de página ${errors.join(' | ')}`);
  await ctx.close();
}
await browser.close();
console.log(failures ? `\n${failures} falha(s)` : '\nTudo certo');
process.exit(failures ? 1 : 0);
