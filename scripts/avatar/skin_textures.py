"""Texturas PBR de pele geradas a partir da anatomia (sem fotos de terceiros).

O albedo é um "tint" relativo (próximo de branco). O tom de pele escolhido pelo
jogador multiplica esse tint no runtime, então um único conjunto de texturas
serve para todos os tons sem perder lábios, rubor, poros e unhas.
Canal B do mapa ORM: máscara de clareamento (unhas, palmas e solas).
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

from raster import Bake, fbm, normal_to_image, smoothstep, to_image, value_noise, worley

HERE = os.path.dirname(os.path.abspath(__file__))
MASKS = os.path.join(HERE, 'data', 'masks')


def load_mask(name):
    return np.asarray(Image.open(os.path.join(MASKS, name + '.jpg')).convert('L'), np.float32) / 255


def sample(img, uv):
    """Amostragem bilinear de uma imagem (H,W) em UV glTF (N,2)."""
    H, W = img.shape[:2]
    x = np.clip(uv[:, 0] * W - .5, 0, W - 1.001)
    y = np.clip(uv[:, 1] * H - .5, 0, H - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = x - x0, y - y0
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def concavity(model):
    """Cavidade por vértice (Laplaciano projetado na normal), em [0,1]."""
    c, tris = model.coords, model.body_tris
    acc = np.zeros_like(c)
    cnt = np.zeros(len(c))
    for a, b in ((0, 1), (1, 2), (2, 0), (1, 0), (2, 1), (0, 2)):
        np.add.at(acc, tris[:, a], c[tris[:, b]])
        np.add.at(cnt, tris[:, a], 1)
    lap = acc / np.maximum(cnt, 1)[:, None] - c
    edge = np.linalg.norm(c[tris[:, 0]] - c[tris[:, 1]], axis=1).mean()
    k = (lap * model.normals).sum(1) / edge
    return np.clip(k * 2.2, 0, 1)


def gaussian(p, center, radius):
    d = np.linalg.norm((p - center) / radius, axis=1)
    return np.exp(-d * d)


def generate(model, layout, size=2048):
    masks = {k: load_mask(k) for k in ('lips', 'fingernails', 'toenails', 'eyelids', 'ears', 'inside-mouth', 'face', 'aureolae')}
    cav = concavity(model)
    hand_w = model.weights[:, [i for i, n in enumerate(model.bone_names) if 'Hand' in n]].sum(1)
    eyeL, eyeR = model.heads['LeftEye'], model.heads['RightEye']
    eye_mid = (eyeL + eyeR) / 2
    out = {}
    for mat in ('head', 'body'):
        verts, uv = layout.triangles(mat)
        pos = model.coords[verts]
        nrm = model.normals[verts]
        extra = {
            'uvo': layout.original_uv(mat, uv),
            'cav': cav[verts][..., None],
            'hand': hand_w[verts][..., None],
        }
        bake = Bake(size, uv, pos, nrm, extra)
        p = bake.pos[bake.mask].astype(np.float64)
        n = bake.nrm[bake.mask]
        uvo = bake.at('uvo')
        m = {k: sample(v, uvo) for k, v in masks.items()}
        cv = bake.at('cav')[:, 0]
        hand = bake.at('hand')[:, 0]
        lips = smoothstep(.2, .8, m['lips'])
        nails = np.maximum(smoothstep(.3, .7, m['fingernails']), smoothstep(.3, .7, m['toenails']))
        lids = m['eyelids']
        mouth_in = m['inside-mouth']
        face = m['face']
        # Variação de cor (manchas sutis e microvariação).
        var = 1 + .06 * (fbm(p, 9, 3, 1) - .5) + .035 * (fbm(p, 70, 3, 5) - .5)
        tint = np.stack([var, var, var], 1)
        # Rubor: bochechas, nariz, orelhas, nós dos dedos, cotovelos e joelhos.
        flush = np.zeros(len(p))
        for s in (1, -1):
            flush += .8 * gaussian(p, eye_mid + np.array([s * .048, -.04, .0]), np.array([.03, .025, .05]))
            flush += .6 * gaussian(p, model.heads['LeftForeArm' if s > 0 else 'RightForeArm'], .05)
            flush += .5 * gaussian(p, model.heads['LeftLeg' if s > 0 else 'RightLeg'] + np.array([0, 0, .05]), .06)
        flush += .9 * gaussian(p, eye_mid + np.array([0, -.045, .07]), np.array([.016, .02, .03]))
        flush += .55 * smoothstep(.2, .8, m['ears'])
        flush += .45 * hand * smoothstep(.1, .6, cv)
        flush = np.clip(flush, 0, 1)
        red = np.array([1.0, .84, .82])
        tint *= 1 + flush[:, None] * (red - 1) * .55
        # Lábios, pálpebras e boca interna.
        tint = tint * (1 - lips[:, None]) + np.array([.84, .64, .62]) * (var[:, None] * .97) * lips[:, None]
        tint *= 1 - lids[:, None] * np.array([.08, .12, .1])
        tint = tint * (1 - mouth_in[:, None]) + np.array([.62, .33, .34]) * mouth_in[:, None]
        # Sombreamento suave em cavidades (dobras, entre os dedos, narinas).
        ao = 1 - .55 * smoothstep(.05, .9, cv)
        tint *= (.8 + .2 * ao)[:, None]
        # Palmas e solas mais claras (realismo em tons escuros).
        palm = np.zeros(len(p))
        side = np.sign(p[:, 0])
        palm += hand * np.clip(-n[:, 0] * side * 1.3 + .1, 0, 1)
        palm += smoothstep(-.3, -.8, n[:, 1]) * (p[:, 1] < .03)
        lighten = np.clip(np.maximum(nails, palm * .55), 0, 1)
        albedo = bake.eval(lambda _: np.clip(tint, 0, 1), 3, 1.0)
        # Rugosidade: zona T mais oleosa, lábios úmidos, unhas brilhantes.
        tzone = gaussian(p, eye_mid + np.array([0, .03, .06]), np.array([.025, .05, .05])) + \
            gaussian(p, eye_mid + np.array([0, -.04, .08]), np.array([.015, .03, .04]))
        rough = .56 - .1 * np.clip(tzone, 0, 1) - .12 * lips - .3 * nails + .06 * palm + .05 * (fbm(p, 30, 2, 9) - .5)
        rough = np.where(mouth_in > .5, .3, rough)
        orm = bake.eval(lambda _: np.stack([ao, np.clip(rough, .15, .9), lighten], 1), 3, 1.0)
        # Relevo: poros (rosto mais denso), microtextura, linhas dos lábios e dobras das juntas.
        facew = np.clip(face * 1.5 + (mat == 'head') * .4, 0, 1)
        lipline_phase = fbm(p, 120, 2, 13)

        def height(q):
            if mat == 'head':
                pores = 1 - smoothstep(0, .45, worley(q, 650, 3))
                h = -0.000045 * pores * (.6 + .4 * facew)
            else:
                h = -0.00003 * smoothstep(.62, .82, value_noise(q, 520, 3))
            h = h + 0.000012 * (fbm(q, 1800, 2, 21) - .5)
            h = h + lips * 0.000018 * np.sin(q[:, 0] * 2 * np.pi * 420 + lipline_phase * 6)
            h = h + hand * 0.00004 * np.sin(np.linalg.norm(q, axis=1) * 2 * np.pi * 900) * smoothstep(.15, .5, cv)
            return h
        nmap = bake.normal_map(height, strength=1.0)
        out[f'{mat}_albedo'] = to_image(albedo, bake.mask)
        out[f'{mat}_orm'] = to_image(orm, bake.mask)
        out[f'{mat}_normal'] = normal_to_image(nmap, bake.mask)
    out['lashes'] = lash_texture()
    return out


def lash_texture(w=512, h=128, seed=4):
    """Fios de cílios com afinamento e curvatura (alpha)."""
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(260):
        x0 = rng.uniform(0, w)
        length = rng.uniform(.55, 1.0) * h
        bend = rng.uniform(-.25, .25) * h
        width = rng.uniform(1.0, 1.8)
        t = np.clip(yy / length, 0, 1)
        cx = x0 + bend * t * t
        d = np.abs(xx - cx)
        strand = np.clip(1 - d / (width * (1 - .85 * t)), 0, 1) * (yy < length)
        img = np.maximum(img, strand * (1 - .4 * t))
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(rgba, 'RGBA')
