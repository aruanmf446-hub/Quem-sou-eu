"""Camadas de pelos sobre a pele: sobrancelhas, barbas e couro cabeludo (degradê).

Cada estilo é uma máscara alfa pintada no espaço UV do rosto, avaliada a partir
da posição 3D de cada texel. Pontos de referência vêm do modelo-base, então os
estilos acompanham qualquer formato de rosto criado pelo jogador (via morphs).
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from raster import Bake, dilate, fbm, smoothstep, value_noise, worley
from skin_textures import load_mask, sample

SIZE = 2048
_bake = {}


def head_bake(model, layout):
    if 'head' not in _bake:
        verts, uv = layout.triangles('head')
        extra = {'uvo': layout.original_uv('head', uv)}
        _bake['head'] = Bake(SIZE, uv, model.coords[verts], model.normals[verts], extra)
        _bake['lips'] = sample(load_mask('lips'), _bake['head'].at('uvo'))
        _bake['lids'] = sample(load_mask('eyelids'), _bake['head'].at('uvo'))
    return _bake['head']


class Landmarks:
    def __init__(self, model):
        self.eyeL = model.heads['LeftEye']
        self.eye_y = self.eyeL[1]
        self.eye_x = abs(self.eyeL[0])
        c = model.coords
        head = np.arange(13380)[c[:13380, 1] > model.heads['Neck'][1]]
        hc = c[head]
        self.top = hc[:, 1].max()
        front = hc[(np.abs(hc[:, 0]) < .006)]
        self.front_z = front[:, 2].max()
        self.mouth_y = self.eye_y - .0735
        self.chin_y = self.mouth_y - .052
        self.center = np.array([0, self.eye_y + .01, self.eyeL[2] - .085])


def polyline_coords(p2, pts, samples=200):
    """Projeta pontos 2D numa polilinha: retorna (s em [0,1], distância assinada, tangente)."""
    pts = np.asarray(pts, float)
    seg = np.linspace(0, 1, samples)
    # Catmull-Rom simples entre os pontos de controle.
    k = len(pts) - 1
    curve = []
    for t in seg:
        x = t * k
        i = min(int(x), k - 1)
        f = x - i
        p0, p1, p2_, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, k)]
        curve.append(.5 * ((2 * p1) + (-p0 + p2_) * f + (2 * p0 - 5 * p1 + 4 * p2_ - p3) * f * f + (-p0 + 3 * p1 - 3 * p2_ + p3) * f ** 3))
    curve = np.array(curve)
    tan = np.gradient(curve, axis=0)
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    tree = cKDTree(curve)
    d, i = tree.query(p2)
    normal = np.stack([-tan[i, 1], tan[i, 0]], 1)
    signed = ((p2 - curve[i]) * normal).sum(1)
    return seg[i], signed, tan[i]


def strands(a, b, freq_across, freq_along, seed):
    """Fios: ruído muito esticado ao longo do crescimento."""
    q = np.stack([b * freq_across, a * freq_along, np.zeros_like(a)], 1)
    n = value_noise(q, 1.0, seed) * .7 + value_noise(q * 2.1, 1.0, seed + 7) * .3
    return n


def brows_alpha(model, layout, style):
    bake = head_bake(model, layout)
    L = Landmarks(model)
    p = bake.pos[bake.mask].astype(np.float64)
    out = np.zeros(len(p))
    front = p[:, 2] > L.eyeL[2] - .03
    params = {
        'natural': dict(thick=(.0062, .0052, .0022), arch=.0085, inner=.0105, tail=.057, density=.85),
        'thick': dict(thick=(.0078, .0068, .0032), arch=.0075, inner=.0095, tail=.058, density=.95),
        'thin': dict(thick=(.0036, .0030, .0014), arch=.011, inner=.012, tail=.055, density=.8),
        'arched': dict(thick=(.0055, .0046, .0018), arch=.0135, inner=.011, tail=.056, density=.88),
    }[style]
    ex, ey = L.eye_x, L.eye_y
    for s in (1, -1):
        sx = p[:, 0] * s
        pts = [(params['inner'], ey + .0165), (ex - .002, ey + .0195 + params['arch'] * .55), (ex + .012, ey + .0175 + params['arch']), (params['tail'], ey + .0135)]
        u, d, tan = polyline_coords(np.stack([sx, p[:, 1]], 1), pts)
        t0, t1, t2 = params['thick']
        thick = np.where(u < .5, t0 + (t1 - t0) * u * 2, t1 + (t2 - t1) * (u - .5) * 2)
        inside = 1 - smoothstep(.55, 1.05, np.abs(d) / thick)
        ends = smoothstep(0, .08, u) * (1 - smoothstep(.9, 1.0, u))
        # Direção de crescimento: para cima no início, para fora/baixo na cauda.
        ang = np.radians(75 - 95 * u)
        gx, gy = np.cos(ang), np.sin(ang)
        a = sx * gx + p[:, 1] * gy
        b = -sx * gy + p[:, 1] * gx
        st = strands(a, b, 2600, 380, 11 if s > 0 else 12)
        hair = smoothstep(.45, .75, st)
        soft = 1 - smoothstep(.2, 1.1, np.abs(d) / thick)
        alpha = (inside * hair * .85 + soft * .22) * ends * params['density']
        out = np.maximum(out, alpha * front * (sx > 0))
    return out


def beard_alpha(model, layout, style):
    bake = head_bake(model, layout)
    L = Landmarks(model)
    p = bake.pos[bake.mask].astype(np.float64)
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ax = np.abs(x)
    lips = smoothstep(.15, .5, _bake['lips'])
    mouth_y = L.mouth_y
    frontish = z > .02
    # Zona total da barba: abaixo da linha das bochechas, acima do pescoço.
    cheek_line = mouth_y + .028 + .045 * smoothstep(.02, .075, ax)
    jaw_low = L.chin_y - .012 + .055 * smoothstep(.0, .07, ax) - .03 * smoothstep(.03, .07, ax) * (z < .06)
    zone = (1 - smoothstep(cheek_line - .006, cheek_line + .004, y)) * smoothstep(jaw_low - .01, jaw_low + .002, y) * frontish
    zone *= 1 - smoothstep(.074, .082, ax)
    # Pelos: pontos/fios curtos para baixo.
    grain = smoothstep(.5, .78, strands(y, x, 1800, 420, 31))
    speck = 1 - smoothstep(.0, .55, worley(p, 1100, 5))
    must_top = mouth_y + .0115 - .004 * smoothstep(.006, .024, ax)
    mustache = (1 - smoothstep(.019, .025, ax)) * smoothstep(mouth_y + .004, mouth_y + .006, y) * (1 - smoothstep(must_top - .002, must_top + .001, y)) * (z > L.front_z - .05)
    chin_w = .0125 + .004 * smoothstep(mouth_y - .015, L.chin_y, y)
    chin = (1 - smoothstep(chin_w - .002, chin_w + .001, ax)) * (y < mouth_y - .011) * (y > L.chin_y - .012) * (z > L.front_z - .07)
    soul = (ax < .006) * (y < mouth_y - .006) * (y > mouth_y - .02) * (z > L.front_z - .05)
    jaw_d = np.abs(y - jaw_low - .007)
    strap = (jaw_d < .0045) * zone
    if style == 'stubble':
        a = zone * (.18 + .35 * speck)
    elif style == 'goatee':
        a = np.clip(mustache * .8 + chin + soul, 0, 1) * (.45 + .55 * grain) + zone * .06 * speck
    elif style == 'chinstrap':
        a = np.clip(mustache * .7 + chin + strap, 0, 1) * (.45 + .55 * grain) + zone * .08 * speck
    else:  # full
        a = zone * (.55 + .45 * grain) + mustache * .3
    a = a * (1 - lips)
    return np.clip(a, 0, 1)


def scalp_alpha(model, layout, style):
    """Couro cabeludo: degradê nas laterais e cabelo curto/raspado."""
    bake = head_bake(model, layout)
    L = Landmarks(model)
    p = bake.pos[bake.mask].astype(np.float64)
    rel = p - L.center
    az = np.degrees(np.arctan2(rel[:, 0], rel[:, 2]))  # 0 = frente
    aaz = np.abs(az)
    ey = L.eye_y
    # Linha do cabelo por azimute (frente -> costeleta -> atrás da orelha -> nuca).
    from hair import scalp_line
    line = scalp_line(L, aaz)
    above = smoothstep(line - .002, line + .006, p[:, 1])
    # Orelhas não recebem cabelo.
    ear = (aaz > 78) & (aaz < 112) & (p[:, 1] < ey + .03) & (np.abs(rel[:, 0]) > .066)
    above = above * ~ear
    height = np.clip((p[:, 1] - line) / max(L.top - ey, 1e-3), 0, 1)
    fine = smoothstep(.45, .8, strands(p[:, 1] + rel[:, 2] * .3, np.arctan2(rel[:, 0], rel[:, 2]) * .09, 2400, 600, 41))
    speck = 1 - smoothstep(0, .5, worley(p, 1500, 9))
    if style == 'fade':
        # Pele aparece embaixo, densidade cresce até o topo (onde ficam os cachos).
        # Degradê só nas laterais e nuca; na frente a linha do cabelo é definida.
        side = smoothstep(40, 75, aaz)
        dens = (smoothstep(.0, .55, height) * .92 + .12) * side + (1 - side) * .95
        a = above * dens * (.55 + .45 * np.maximum(fine, speck))
        a *= (.55 + .45 * smoothstep(.15, .5, height)) * side + (1 - side)
    elif style == 'buzz':
        a = above * (.62 + .3 * np.maximum(fine, speck))
    else:  # full (base para coque, tranças e volumes)
        a = above * (.85 + .15 * fine)
    return np.clip(a, 0, 1)


def alpha_image(model, layout, values, blur=False):
    bake = head_bake(model, layout)
    img = np.zeros((SIZE, SIZE), np.float32)
    img[bake.mask] = values
    img = dilate(img, bake.mask)
    rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.clip(img * 255 + .5, 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, 'RGBA')


def faces_in(layout, model, values, mat='head', threshold=.01):
    """Faces do rosto cobertas pela máscara (com folga) para a malha da camada."""
    bake = head_bake(model, layout)
    covered = np.zeros(SIZE * SIZE, bool)
    idx = np.flatnonzero(bake.mask.reshape(-1))
    covered[idx[values > threshold]] = True
    covered = covered.reshape(SIZE, SIZE)
    tri_hit = np.unique(bake.tri[covered])
    keep_tris = set(int(t) for t in tri_hit if t >= 0)
    # Mapeia triângulos de volta às faces (quads) do layout.
    faces, t = [], 0
    for m, corners in layout.faces:
        if m != mat:
            continue
        n = len(corners) - 2
        if any(t + k in keep_tris for k in range(n)):
            faces.append(corners)
        t += n
    return faces
