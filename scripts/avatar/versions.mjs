// Gera src/avatar/assetVersions.json: hash curto do conteúdo de cada GLB e miniatura.
// As URLs ganham ?v=<hash>, então navegador e CDN nunca misturam uma base nova com peças antigas em cache.
// node scripts/avatar/versions.mjs (rodado também por optimize.mjs e thumbs.mjs)
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
const root = new URL('../../', import.meta.url).pathname;
const pub = join(root, 'public');
const hash = f => createHash('sha1').update(readFileSync(f)).digest('hex').slice(0, 10);
const out = {};
out['/avatar/base.glb'] = hash(join(pub, 'avatar/base.glb'));
for (const dir of ['avatar/items', 'avatar/thumbs']) {
  if (!existsSync(join(pub, dir))) continue;
  for (const f of readdirSync(join(pub, dir)).sort()) if (/\.(glb|webp)$/.test(f)) out[`/${dir}/${f}`] = hash(join(pub, dir, f));
}
writeFileSync(join(root, 'src/avatar/assetVersions.json'), JSON.stringify(out, null, 0).replace(/,"/g, ',\n"') + '\n');
console.log(`versões de ${Object.keys(out).length} arquivos`);
