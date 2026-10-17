// Compacta os GLBs do avatar (Meshopt + quantização). node scripts/avatar/optimize.mjs [arquivos]
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, meshopt, sparse } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';
import { readdirSync, statSync, mkdirSync } from 'node:fs';
import { join, basename } from 'node:path';
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });
const root = new URL('../../public/avatar/', import.meta.url).pathname;
const files = process.argv.slice(2).length ? process.argv.slice(2) : [join(root, 'base.glb'), ...readdirSync(join(root, 'items')).filter(f => f.endsWith('.glb')).map(f => join(root, 'items', f))];
for (const file of files) {
  const before = statSync(file).size;
  const doc = await io.read(file);
  if (doc.getRoot().listExtensionsUsed().some(e => e.extensionName === 'EXT_meshopt_compression')) { console.log(`${basename(file)}: já otimizado`); continue; }
  await doc.transform(dedup(), prune({ keepExtras: true }), sparse({ ratio: 1 / 3 }), meshopt({ encoder: MeshoptEncoder, level: 'high' }));
  await io.write(file, doc);
  console.log(`${basename(file)}: ${(before / 1024).toFixed(0)} KB -> ${(statSync(file).size / 1024).toFixed(0)} KB`);
}
