import * as THREE from 'three';

/**
 * Ajustes de shader sobre os materiais físicos do three.js.
 * - Pele: tom escolhido x tint da textura, clareamento (unhas/palmas) e
 *   espalhamento subsuperficial aproximado (luz "envolvente" avermelhada).
 * - Tecido: brilho de fibra via sheen.
 */
export interface SkinUniforms {
  tone: { value: THREE.Color };
  light: { value: THREE.Color };
  scatter: { value: THREE.Color };
}

const SSS_DIFFUSE = /reflectedLight\.directDiffuse \+= irradiance \* BRDF_Lambert\( material\.diffuseColor \);/;

export function makeSkinMaterial(source: THREE.MeshStandardMaterial, uniforms: SkinUniforms) {
  const m = new THREE.MeshPhysicalMaterial();
  THREE.MeshStandardMaterial.prototype.copy.call(m, source);
  m.metalness = 0;
  m.metalnessMap = null;
  m.sheen = .2;
  m.sheenRoughness = .55;
  m.sheenColor = new THREE.Color('#e8d6cf');
  m.name = source.name;
  const ormMap = source.roughnessMap;
  m.onBeforeCompile = shader => {
    shader.uniforms.skinTone = uniforms.tone;
    shader.uniforms.skinLight = uniforms.light;
    shader.uniforms.skinScatter = uniforms.scatter;
    shader.uniforms.skinOrm = { value: ormMap };
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>
uniform vec3 skinTone;
uniform vec3 skinLight;
uniform vec3 skinScatter;
uniform sampler2D skinOrm;`)
      .replace('#include <map_fragment>', `#include <map_fragment>
#ifdef USE_ROUGHNESSMAP
  float skinLift = texture2D( skinOrm, vRoughnessMapUv ).b;
#else
  float skinLift = 0.0;
#endif
  diffuseColor.rgb *= mix( skinTone, skinLight, skinLift );`)
      .replace('#include <lights_physical_pars_fragment>', THREE.ShaderChunk.lights_physical_pars_fragment.replace(SSS_DIFFUSE, `
  float wrapNL = saturate( ( dot( geometryNormal, directLight.direction ) + 0.5 ) / 1.5 );
  vec3 scatterLight = max( wrapNL - dotNL, 0.0 ) * directLight.color * skinScatter;
  reflectedLight.directDiffuse += ( irradiance + scatterLight ) * BRDF_Lambert( material.diffuseColor );`));
  };
  m.customProgramCacheKey = () => 'avatar-skin';
  return m;
}

export function skinToneColors(hex: string) {
  const tone = new THREE.Color(hex);
  const hsl = { h: 0, s: 0, l: 0 };
  tone.getHSL(hsl);
  const light = new THREE.Color().setHSL(hsl.h, hsl.s * .75, Math.min(.86, hsl.l + (1 - hsl.l) * .45));
  const scatter = new THREE.Color().setHSL(.02, .6, .16 + hsl.l * .12);
  return { tone, light, scatter };
}

/**
 * Cabelo: textura em escala de cinza (R) com máscara de pontas no canal B.
 * As pontas descoloridas combinam o atributo _TIP (0 raiz -> 1 ponta) e a máscara da textura.
 */
export function applyHairTips(m: THREE.MeshStandardMaterial, tips: { value: THREE.Color }, amount: { value: number }) {
  m.envMapIntensity = .55;
  m.onBeforeCompile = shader => {
    shader.uniforms.hairTips = tips;
    shader.uniforms.hairTipAmount = amount;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float _tip;\nvarying float vTip;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvTip = _tip;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform vec3 hairTips;\nuniform float hairTipAmount;\nvarying float vTip;')
      .replace('#include <map_fragment>', `
#ifdef USE_MAP
  vec4 hairTexel = texture2D( map, vMapUv );
  float hairLum = hairTexel.r;
  float hairTipMask = hairTexel.b;
  diffuseColor.a *= hairTexel.a;
#else
  float hairLum = 1.0;
  float hairTipMask = 0.0;
#endif
  diffuseColor.rgb *= hairLum;
  float hairTip = max( smoothstep( 0.45, 1.0, vTip ), hairTipMask ) * hairTipAmount;
  diffuseColor.rgb = mix( diffuseColor.rgb, hairTips * ( 0.55 + 0.45 * hairLum ), hairTip );`);
  };
  m.customProgramCacheKey = () => 'avatar-hair-tips';
}
