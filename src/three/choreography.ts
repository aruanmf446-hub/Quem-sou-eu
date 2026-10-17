import * as THREE from 'three';
import type { DanceId } from '../data/characters';

export interface RigBone { bone: THREE.Bone; rest: THREE.Quaternion; position: THREE.Vector3; }
export type CharacterRig = Map<string, RigBone>;
const rotation = new THREE.Quaternion();
const parentRotation = new THREE.Quaternion();
const inverseParent = new THREE.Quaternion();
const euler = new THREE.Euler();
const translation = new THREE.Vector3();
const leftFoot = new THREE.Vector3(), rightFoot = new THREE.Vector3();

/** Apply a rotation in model space while preserving the exported bone rest axes. */
function rotate(rig: CharacterRig, name: string, x = 0, y = 0, z = 0) {
  const joint = rig.get(name) ?? rig.get(name.replace('.', ''));
  if (!joint) return;
  joint.bone.parent!.getWorldQuaternion(parentRotation);
  inverseParent.copy(parentRotation).invert();
  rotation.setFromEuler(euler.set(x, y, z, 'YXZ'));
  joint.bone.quaternion.copy(inverseParent).multiply(rotation).multiply(parentRotation).multiply(joint.rest);
  joint.bone.updateMatrixWorld(true);
}
const smoothStep = (x: number) => x * x * (3 - 2 * x);
const snap = (t: number) => {
  // Hold robot accents, then smoothly move between them (no discontinuous transforms).
  const q = t / Math.PI, n = Math.floor(q), f = q - n;
  return Math.sin(n * Math.PI / 2) + (Math.sin((n + 1) * Math.PI / 2) - Math.sin(n * Math.PI / 2)) * smoothStep(Math.min(1, f * 3));
};

export function animateCharacter(rig: CharacterRig, dance: DanceId, seconds: number, height: number) {
  for (const j of rig.values()) { j.bone.quaternion.copy(j.rest); j.bone.position.copy(j.position); }
  const t = seconds * (dance === 'samba' ? 7.2 : dance === 'thriller' ? 5.8 : 5.4);
  const beat = Math.sin(t), half = Math.sin(t / 2), sway = Math.sin(t / 2 + .4);
  const hips = rig.get('hips');
  if (!hips) return;
  const travel = dance === 'samba' ? .075 : dance === 'thriller' ? .048 : .032;
  // Exported armatures retain their coordinate conversion. Translate in world axes.
  hips.bone.parent!.getWorldQuaternion(parentRotation);
  inverseParent.copy(parentRotation).invert();
  hips.bone.position.add(translation.set(half * travel, -(.014 + .015 * Math.cos(t * 2)) / height, 0).applyQuaternion(inverseParent));
  hips.bone.updateMatrixWorld(true);
  rotate(rig, 'hips', 0, sway * .10, half * -.035);
  rotate(rig, 'spine', .02 + Math.sin(t + .4) * .035, -sway * .07, half * .065);
  rotate(rig, 'chest', -.02, Math.sin(t / 2 - .3) * .10, -half * .045);
  rotate(rig, 'neck', .015, Math.sin(t / 2 - .6) * .045, 0);
  rotate(rig, 'head', Math.sin(t - .3) * .025, Math.sin(t / 2 - .5) * .12, -half * .035);
  for (const [side, sign] of [['L', -1], ['R', 1]] as const) {
    const leg = Math.sin(t + (sign > 0 ? Math.PI : 0));
    let thighX = leg * .11 - .045, kneeX = .08 + Math.max(0, -leg) * .18;
    let armX = leg * .22, armZ = -sign * .48, elbowX = -.48 - Math.max(0, leg) * .22;
    let wristX = -.06, wristZ = sign * .08;
    if (dance === 'samba') {
      thighX = leg * .30 - .05; kneeX = .12 + Math.max(0, -leg) * .48;
      armX = -leg * .32; armZ = -sign * (.30 + .09 * half); elbowX = -.85 + leg * .18;
      wristZ = sign * .2; wristX = Math.sin(t + .4) * .15;
    } else if (dance === 'robot') {
      const accent = snap(t);
      thighX = -.08; kneeX = .17;
      armZ = sign * .45; armX = accent * .18;
      elbowX = -.9 + sign * accent * .65; wristX = sign * accent * .35;
      wristZ = sign * -.3;
      rotate(rig, 'head', 0, snap(t - .5) * .3, 0);
    } else if (dance === 'thriller') {
      thighX = leg * .22 - .08; kneeX = .14 + Math.max(0, -leg) * .3;
      armX = -1.05 + half * .25; armZ = -sign * (.25 + beat * .12);
      elbowX = -.2 - Math.max(0, half) * .5; wristX = .7; wristZ = sign * Math.sin(t / 2) * .25;
    }
    rotate(rig, `thigh.${side}`, thighX, sign * half * .03, sign * .025 + half * .03);
    rotate(rig, `shin.${side}`, kneeX);
    rotate(rig, `foot.${side}`, -thighX - kneeX + Math.max(0, -leg) * .10, sign * .025);
    rotate(rig, `upper_arm.${side}`, armX, sign * -.06, armZ);
    rotate(rig, `forearm.${side}`, elbowX, 0, sign * .06);
    rotate(rig, `hand.${side}`, wristX, 0, wristZ);
  }
  // Keep the supporting foot on the platform instead of floating during knee bends.
  const left = rig.get('foot.L') ?? rig.get('footL');
  const right = rig.get('foot.R') ?? rig.get('footR');
  if (left && right) {
    left.bone.getWorldPosition(leftFoot); right.bone.getWorldPosition(rightFoot);
    const correction = THREE.MathUtils.clamp(.086 * height - Math.min(leftFoot.y, rightFoot.y), -.2, .2);
    hips.bone.parent!.getWorldQuaternion(parentRotation); inverseParent.copy(parentRotation).invert();
    hips.bone.position.add(translation.set(0, correction / height, 0).applyQuaternion(inverseParent));
    hips.bone.updateMatrixWorld(true);
  }
}
