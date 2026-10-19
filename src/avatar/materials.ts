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
  // Pele de animação: mais fosca e lisa (sem aspecto de plástico nem ruído de poros).
  m.roughness = Math.max(source.roughness, .62);
  m.sheen = .32;
  m.sheenRoughness = .6;
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
  // Brilho de cabelo macio: menos reflexo de ambiente e especular mais espalhado (sem aspecto de plástico).
  m.envMapIntensity = .3;
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

/**
 * Acabamento de animação (estilo Pixar/Riot) aplicado sobre os materiais PBR do avatar e das peças:
 * - luz envolvente: a transição luz/sombra fica macia, como pintura, sem o contraste duro do realista;
 * - luz de recorte (rim) colorida pelo palco, contornando a silhueta;
 * - gradiente vertical sutil (pés um pouco mais escuros, como nas artes de referência);
 * - cor levemente mais saturada.
 * Os uniforms são compartilhados: o palco define a cor do recorte conforme o cenário.
 */
export const TOON = {
  rimColor: { value: new THREE.Color('#bcc8ff') },
  rim: { value: .26 },
  rimPower: { value: 3.0 },
  wrap: { value: .6 },
  soft: { value: .75 },
  saturation: { value: 1.06 },
  floor: { value: .9 },
  height: { value: 1.7 },
};

export function stylize(m: THREE.Material) {
  const std = m as THREE.MeshStandardMaterial;
  if (!std.isMeshStandardMaterial || m.userData.stylized || m.userData.overlay || m.userData.cornea) return;
  m.userData.stylized = true;
  const prev = m.onBeforeCompile;
  const prevKey = m.customProgramCacheKey;
  m.onBeforeCompile = (shader, renderer) => {
    prev?.call(m, shader, renderer);
    shader.uniforms.toonRimColor = TOON.rimColor;
    shader.uniforms.toonRim = TOON.rim;
    shader.uniforms.toonRimPower = TOON.rimPower;
    shader.uniforms.toonWrap = TOON.wrap;
    shader.uniforms.toonSoft = TOON.soft;
    shader.uniforms.toonSat = TOON.saturation;
    shader.uniforms.toonFloor = TOON.floor;
    shader.uniforms.toonHeight = TOON.height;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying float vToonY;')
      .replace('#include <project_vertex>', '#include <project_vertex>\nvToonY = ( modelMatrix * vec4( transformed, 1.0 ) ).y;');
    const uniforms = 'uniform vec3 toonRimColor;\nuniform float toonRim, toonRimPower, toonWrap, toonSoft, toonSat, toonFloor, toonHeight;\nvarying float vToonY;';
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>\n${uniforms}`)
      .replace('#include <lights_physical_pars_fragment>', THREE.ShaderChunk.lights_physical_pars_fragment)
      // Luz envolvente só no difuso: o especular continua físico (senão estoura nas bordas com luz por trás).
      .replace('vec3 irradiance = dotNL * directLight.color;', `vec3 irradiance = dotNL * directLight.color;
	float toonNL = dot( geometryNormal, directLight.direction );
	float toonWrapNL = smoothstep( 0.0, 1.0, saturate( ( toonNL + toonWrap ) / ( 1.0 + toonWrap ) ) );
	vec3 toonIrradiance = mix( dotNL, toonWrapNL, toonSoft ) * directLight.color;`)
      .replace('reflectedLight.directDiffuse += ( irradiance + scatterLight )', 'reflectedLight.directDiffuse += ( toonIrradiance + scatterLight )')
      .replace('reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );', 'reflectedLight.directDiffuse += toonIrradiance * BRDF_Lambert( material.diffuseColor );')
      .replace('#include <opaque_fragment>', `{
	float toonFacing = saturate( dot( normal, normalize( vViewPosition ) ) );
	float toonFres = pow( 1.0 - toonFacing, toonRimPower ) * ( 0.45 + 0.55 * saturate( normal.y * 0.5 + 0.6 ) );
	outgoingLight += toonRimColor * ( 0.25 + 0.9 * diffuseColor.rgb ) * toonFres * toonRim;
	outgoingLight *= mix( toonFloor, 1.0, smoothstep( 0.0, toonHeight, vToonY ) );
	float toonLuma = dot( outgoingLight, vec3( 0.299, 0.587, 0.114 ) );
	// Limita picos especulares (bordas rasantes): no buffer HDR do pós-processamento eles viram contorno branco.
	outgoingLight = clamp( mix( vec3( toonLuma ), outgoingLight, toonSat ), 0.0, 3.0 );
}
#include <opaque_fragment>`);
  };
  m.customProgramCacheKey = () => `${prevKey ? prevKey.call(m) : ''}|toon`;
  m.needsUpdate = true;
}

/**
 * Íris de animação gerada por código (sem textura nova): a malha da íris tem UV centrado em (0,5; 0,5),
 * com raio 0,5 na borda. O shader desenha pupila, gradiente radial (centro claro, borda escura),
 * anel límbico, fibras sutis e dois reflexos fixos (catchlight), como nos olhos de filmes de animação.
 */
export function makeIrisMaterial(source: THREE.MeshStandardMaterial) {
  const m = source.clone();
  m.roughness = .25;
  m.onBeforeCompile = shader => {
    shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>', `
#ifdef USE_MAP
  vec2 irisUv = vMapUv - 0.5;
#else
  vec2 irisUv = vec2( 0.0 );
#endif
  float irisR = length( irisUv ) * 2.0;
  float irisAng = atan( irisUv.y, irisUv.x );
  vec3 irisBase = diffuseColor.rgb;
  // Gradiente: centro mais claro e quente, borda mais escura.
  vec3 irisInner = irisBase * vec3( 1.8, 1.55, 1.25 );
  vec3 irisOuter = irisBase * 0.45;
  vec3 irisCol = mix( irisInner, irisOuter, smoothstep( 0.3, 0.95, irisR ) );
  // Fibras radiais sutis.
  irisCol *= 0.9 + 0.1 * sin( irisAng * 38.0 + irisR * 6.0 );
  // Metade de baixo um pouco mais clara (luz entrando pelo topo da córnea).
  irisCol *= 1.0 + 0.25 * smoothstep( 0.0, 0.4, irisUv.y );
  // Anel límbico escuro na borda.
  irisCol *= 1.0 - 0.75 * smoothstep( 0.82, 0.98, irisR );
  // Pupila.
  irisCol = mix( irisCol, vec3( 0.015 ), 1.0 - smoothstep( 0.34, 0.4, irisR ) );
  // Reflexos fixos: um grande no alto à esquerda e um pequeno embaixo à direita.
  float glint = 1.0 - smoothstep( 0.07, 0.1, length( irisUv - vec2( -0.15, -0.16 ) ) );
  glint = max( glint, ( 1.0 - smoothstep( 0.025, 0.04, length( irisUv - vec2( 0.17, 0.15 ) ) ) ) * 0.8 );
  diffuseColor.rgb = mix( irisCol, vec3( 1.0 ), glint );
  float irisGlint = glint;`).replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
  totalEmissiveRadiance += irisGlint * 0.9;`);
  };
  m.customProgramCacheKey = () => 'avatar-iris-toon-v2';
  return m;
}
