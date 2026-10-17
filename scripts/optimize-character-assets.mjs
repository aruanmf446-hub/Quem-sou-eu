import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, weld, meshopt } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';
import { statSync } from 'node:fs';
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });
for (const id of ['street', 'striker', 'night-clown']) {
 const file = new URL(`../public/models/${id}.glb`, import.meta.url).pathname;
 const before = statSync(file).size;
 const document = await io.read(file);
 await document.transform(dedup(), weld(), prune(), meshopt({ encoder: MeshoptEncoder, level: 'high' }));
 await io.write(file, document);
 console.log(`${id}: ${(before/1024).toFixed(0)} KB → ${(statSync(file).size/1024).toFixed(0)} KB`);
}
