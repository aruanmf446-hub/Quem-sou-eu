import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { animateCharacter, type CharacterRig } from './choreography';

async function load(id: string) {
  const bytes = readFileSync(`public/models/${id}.glb`);
  const array = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const gltf = await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).parseAsync(array, '');
  const rig: CharacterRig = new Map();
  const meshes: THREE.SkinnedMesh[] = [];
  gltf.scene.traverse(object => {
    if (object instanceof THREE.Bone) rig.set(object.name, { bone: object, rest: object.quaternion.clone(), position: object.position.clone() });
    if (object instanceof THREE.SkinnedMesh) meshes.push(object);
  });
  return { gltf, rig, meshes };
}

describe('modelos de produção e coreografias', () => {
  for (const id of ['street', 'striker', 'night-clown']) {
    it(`${id}: modelo comprimido carrega com 17 ossos e pesos normalizados`, async () => {
      const { rig, meshes } = await load(id);
      expect(rig.size).toBe(17);
      expect(meshes.length).toBeGreaterThan(0);
      for (const mesh of meshes) {
        const weights = mesh.geometry.getAttribute('skinWeight');
        for (let i = 0; i < weights.count; i++) {
          const sum = weights.getX(i) + weights.getY(i) + weights.getZ(i) + weights.getW(i);
          if (Math.abs(sum - 1) > .01) throw new Error(`Peso inválido no vértice ${i}: ${sum}`);
        }
      }
    });
  }
  it('as quatro danças movem membros após a sanitização dos nomes pelo GLTFLoader', async () => {
    const { gltf, rig, meshes } = await load('striker');
    const arm = rig.get('upper_armL')!;
    const shin = rig.get('shinL')!;
    expect(arm).toBeDefined();
    const poses: number[][] = [];
    for (const dance of ['groove', 'samba', 'robot', 'thriller'] as const) {
      animateCharacter(rig, dance, .7, 1);
      expect(arm.bone.quaternion.angleTo(arm.rest)).toBeGreaterThan(.1);
      expect(shin.bone.quaternion.angleTo(shin.rest)).toBeGreaterThan(.01);
      poses.push(arm.bone.quaternion.toArray());
      for (const time of [0, .2, .7, 1.5, 3, 8]) {
        animateCharacter(rig, dance, time, 1);
        gltf.scene.updateMatrixWorld(true);
        const bounds = new THREE.Box3();
        for (const mesh of meshes) {
          mesh.skeleton.update();
          const pos = mesh.geometry.getAttribute('position'), point = new THREE.Vector3();
          for (let i = 0; i < pos.count; i += 7) {
            point.fromBufferAttribute(pos, i); mesh.applyBoneTransform(i, point); point.applyMatrix4(mesh.matrixWorld);
            if (!Number.isFinite(point.x + point.y + point.z)) throw new Error('Pose com coordenadas inválidas');
            bounds.expandByPoint(point);
          }
        }
        const size = bounds.getSize(new THREE.Vector3());
        expect(size.y).toBeGreaterThan(1.7); expect(size.y).toBeLessThan(2.6);
        expect(size.x).toBeLessThan(2.7);
      }
    }
    expect(new Set(poses.map(p => p.map(v => v.toFixed(3)).join(','))).size).toBe(4);
  });
  it('recalcular a mesma pose não acumula rotações nem deslocamento', async () => {
    const { rig } = await load('street');
    animateCharacter(rig, 'samba', 2, 1);
    const first = [...rig.values()].map(j => ({ q: j.bone.quaternion.clone(), p: j.bone.position.clone() }));
    animateCharacter(rig, 'samba', 2, 1);
    [...rig.values()].forEach((j, i) => {
      expect(j.bone.position.distanceTo(first[i].p)).toBeLessThan(.0001);
      expect(j.bone.quaternion.angleTo(first[i].q)).toBeLessThan(.001);
    });
  });
});
