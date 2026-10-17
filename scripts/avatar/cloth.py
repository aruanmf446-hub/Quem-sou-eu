"""Texturas PBR de tecido (albedo, normal, rugosidade/oclusão) geradas proceduralmente.

Padrões de trama usam projeção triplanar sobre a posição anatômica, então não
dependem da UV e não apresentam costuras falsas.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from garments import Surface, vertex_normals_canon
from raster import Bake, dilate, fbm, normal_to_image, smoothstep, to_image, value_noise


def bake_surface(s: Surface, size=2048, extra=None):
    """Rasteriza só o lado de fora (o lado de dentro reaproveita a mesma UV)."""
    n = vertex_normals_canon(s)
    part = s.part if s.part is not None else np.zeros(len(s.pos))
    t = s.tris[(part[s.tris] < 1.5).all(1)]
    ex = {'part': (s.part if s.part is not None else np.zeros(len(s.pos)))[t][..., None].astype(np.float32)}
    for k, v in (extra or {}).items():
        ex[k] = v[t] if v.ndim > 1 else v[t][..., None]
    return Bake(size, s.uv[t], s.ref[t], n[t], ex)


def triplanar(p, n, fn):
    w = np.abs(n) ** 4
    w /= w.sum(1, keepdims=True)
    return fn(p[:, 2], p[:, 1]) * w[:, 0] + fn(p[:, 0], p[:, 2]) * w[:, 1] + fn(p[:, 0], p[:, 1]) * w[:, 2]


# --- tramas (alturas em metros) ---------------------------------------------

def knit(u, v, scale=.0016):
    """Malha de jérsei: colunas de laçadas em V."""
    x = u / scale
    y = v / (scale * 1.3)
    loop = np.abs(np.sin(np.pi * x)) * (.6 + .4 * np.cos(2 * np.pi * (y + np.abs(np.sin(np.pi * x * .5)) * .5)))
    return loop * .00012


def rib(u, v, scale=.0028):
    return (.5 + .5 * np.cos(2 * np.pi * u / scale)) * .00025


def diamond(u, v, scale=.009):
    a = np.abs(((u + v) / scale) % 1 - .5) + np.abs(((u - v) / scale) % 1 - .5)
    return smoothstep(.42, .5, a) * .00006


def perforated(u, v, scale=.0042):
    gx = (u / scale) % 1 - .5
    gy = (v / scale + .5 * (np.floor(u / scale) % 2)) % 1 - .5
    d = np.hypot(gx, gy * 1.2)
    return -smoothstep(.28, .18, d) * .00035


def twill(u, v, scale=.0011):
    return (.5 + .5 * np.sin(2 * np.pi * (u + v * .9) / scale)) * .00009


def fleece(p, n):
    return (fbm(p, 900, 2, 3) - .5) * .00012


# --- formas 2D (SDF) ----------------------------------------------------------

def sd_box(x, y, cx, cy, hw, hh, r=0.0):
    qx = np.abs(x - cx) - hw + r
    qy = np.abs(y - cy) - hh + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_circle(x, y, cx, cy, r):
    return np.hypot(x - cx, y - cy) - r


def sd_polygon(x, y, pts):
    pts = np.asarray(pts, float)
    d = np.full(x.shape, np.inf)
    sign = np.ones(x.shape)
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        ex, ey = b - a
        wx, wy = x - a[0], y - a[1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0, 1)
        dx, dy = wx - ex * t, wy - ey * t
        d = np.minimum(d, np.hypot(dx, dy))
        c1 = y >= a[1]
        c2 = y < b[1]
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        sign = np.where(flip, -sign, sign)
    return d * sign


def fill(sd, aa=.0004):
    return smoothstep(aa, -aa, sd)


# Números esportivos originais em blocos (sem fonte de terceiros).
DIGITS = {
    '0': [[(-.5, -1), (.5, -1), (.5, 1), (-.5, 1)], 'hole'],
    '1': [[(-.15, -1), (.22, -1), (.22, 1), (-.08, 1), (-.38, .72), (-.38, .5), (-.15, .58)]],
}


def sd_digit(ch, x, y, cx, cy, h):
    """Dígito com altura h centrado em (cx, cy)."""
    sx, sy = (x - cx) / (h / 2), (y - cy) / (h / 2)
    if ch == '0':
        outer = sd_box(sx, sy, 0, 0, .5, 1, .32)
        inner = sd_box(sx, sy, 0, 0, .2, .66, .14)
        return np.maximum(outer, -inner) * h / 2
    return sd_polygon(sx, sy, DIGITS[ch][0]) * h / 2


def sd_number(text, x, y, cx, cy, h, spacing=.62):
    d = np.full(x.shape, np.inf)
    n = len(text)
    for i, ch in enumerate(text):
        ox = cx + (i - (n - 1) / 2) * h * spacing
        d = np.minimum(d, sd_digit(ch, x, y, ox, cy, h))
    return d


def finish(bake: Bake, albedo, rough, height_fn, ao=None, metal=None, normal_strength=1.0):
    """Gera imagens (albedo, normal, ORM) a partir dos valores por texel."""
    m = bake.mask
    alb = np.zeros(m.shape + (3,), np.float32)
    alb[m] = albedo
    orm = np.zeros(m.shape + (3,), np.float32)
    orm[m, 0] = 1 if ao is None else ao
    orm[m, 1] = rough
    orm[m, 2] = 0 if metal is None else metal
    nmap = bake.normal_map(height_fn, normal_strength)
    return to_image(alb, m), normal_to_image(nmap, m), to_image(orm, m)


def srgb(hexstr):
    return np.array([int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5)])


def lin_mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return a * (1 - t) + b * t
