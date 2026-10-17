"""Rasterização no espaço UV e ruídos 3D para pintar texturas sem costuras.

Cada texel recebe a posição 3D, a normal e a base tangente da superfície. Os
padrões (poros, trama do tecido, costuras, emblemas) são funções da posição 3D,
então continuam contínuos mesmo cruzando costuras de UV.
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage


class Bake:
    """Mapas por texel: pos (H,W,3), nrm, tan, bit, mask e atributos extras."""

    def __init__(self, size, uv, pos, nrm, extra=None):
        """uv: (T,3,2) em [0,1] (v para baixo); pos/nrm: (T,3,3); extra: dict nome->(T,3,C)."""
        self.size = size
        H = W = size
        self.mask = np.zeros((H, W), bool)
        self.pos = np.zeros((H, W, 3), np.float32)
        self.nrm = np.zeros((H, W, 3), np.float32)
        self.tan = np.zeros((H, W, 3), np.float32)
        self.bit = np.zeros((H, W, 3), np.float32)
        self.tri = np.full((H, W), -1, np.int32)
        extra = extra or {}
        self.extra = {k: np.zeros((H, W, v.shape[2]), np.float32) for k, v in extra.items()}
        # Tangente (direção +u) e "bitangente para cima" (direção -v) por triângulo.
        e1, e2 = pos[:, 1] - pos[:, 0], pos[:, 2] - pos[:, 0]
        d1, d2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
        r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
        r = np.where(np.abs(r) < 1e-12, 1e-12, r)
        T = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
        B = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
        B = -B / np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-12)
        px = uv * size - .5
        for i in range(len(uv)):
            p = px[i]
            x0, y0 = np.floor(p.min(0)).astype(int)
            x1, y1 = np.ceil(p.max(0)).astype(int)
            x0, y0 = max(x0, 0), max(y0, 0)
            x1, y1 = min(x1, W - 1), min(y1, H - 1)
            if x1 < x0 or y1 < y0:
                continue
            ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
            a, b, c = p
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(den) < 1e-12:
                continue
            l0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
            l1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
            l2 = 1 - l0 - l1
            eps = -1e-3
            inside = (l0 >= eps) & (l1 >= eps) & (l2 >= eps)
            if not inside.any():
                continue
            yy, xx = ys[inside], xs[inside]
            L = np.stack([l0[inside], l1[inside], l2[inside]], 1)
            self.mask[yy, xx] = True
            self.tri[yy, xx] = i
            self.pos[yy, xx] = L @ pos[i]
            self.nrm[yy, xx] = L @ nrm[i]
            self.tan[yy, xx] = T[i]
            self.bit[yy, xx] = B[i]
            for k, v in extra.items():
                self.extra[k][yy, xx] = L @ v[i]
        n = np.linalg.norm(self.nrm, axis=2, keepdims=True)
        self.nrm /= np.maximum(n, 1e-9)
        # Ortogonaliza a base tangente.
        self.tan -= self.nrm * (self.tan * self.nrm).sum(2, keepdims=True)
        self.tan /= np.maximum(np.linalg.norm(self.tan, axis=2, keepdims=True), 1e-9)
        sign = np.sign((np.cross(self.nrm, self.tan) * self.bit).sum(2, keepdims=True))
        self.bit = np.cross(self.nrm, self.tan) * np.where(sign == 0, 1, sign)

    def normal_map(self, height_fn, strength=1.0, eps=.0004):
        """Normal em espaço tangente a partir de uma altura h(pos) em metros."""
        p = self.pos[self.mask]
        n = self.nrm[self.mask]
        t = self.tan[self.mask]
        b = self.bit[self.mask]
        h0 = height_fn(p)
        ht = height_fn(p + t * eps)
        hb = height_fn(p + b * eps)
        dx = (ht - h0) / eps * strength
        dy = (hb - h0) / eps * strength
        v = np.stack([-dx, -dy, np.ones_like(dx)], 1)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        out = np.zeros(self.mask.shape + (3,), np.float32)
        out[..., 2] = 1
        out[self.mask] = v
        return out

    def eval(self, fn, channels=1, fill=0.0):
        """Avalia fn(pos, nrm, mask_index_data) apenas nos texels cobertos."""
        out = np.full(self.mask.shape + ((channels,) if channels > 1 else ()), fill, np.float32)
        out[self.mask] = fn(self)
        return out

    def at(self, name):
        return self.extra[name][self.mask]


def dilate(img, mask, px=8):
    """Estende as cores para fora das ilhas UV (evita costuras com mipmaps)."""
    if mask.all():
        return img
    _, (iy, ix) = ndimage.distance_transform_edt(~mask, return_indices=True)
    out = img[iy, ix]
    return out


def to_image(arr, mask=None, mode=None, dil=True):
    a = np.asarray(arr, np.float32)
    if mask is not None and dil:
        a = dilate(a, mask)
    a = np.clip(a * 255 + .5, 0, 255).astype(np.uint8)
    return Image.fromarray(a, mode)


def normal_to_image(nmap, mask):
    return to_image(nmap * .5 + .5, mask)


# --- ruídos determinísticos -------------------------------------------------

def _hash(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xffffff).astype(np.float64) / 0xffffff


def value_noise(p, freq, seed=0):
    """Ruído de valor 3D suave, p em metros, freq em ciclos por metro. Retorna [0,1]."""
    q = np.asarray(p, np.float64) * freq
    i = np.floor(q).astype(np.int64)
    f = q - i
    u = f * f * (3 - 2 * f)
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                out = out + w * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def fbm(p, freq, octaves=4, seed=0, gain=.5):
    total, amp, norm = 0, 1, 0
    for o in range(octaves):
        total = total + amp * value_noise(p, freq * 2 ** o, seed + o * 17)
        norm += amp
        amp *= gain
    return total / norm


def worley(p, freq, seed=0):
    """Distância ao ponto de célula mais próximo (células de Voronoi 3D), normalizada."""
    q = np.asarray(p, np.float64) * freq
    i = np.floor(q).astype(np.int64)
    best = np.full(len(q), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                jitter = np.stack([_hash(c[:, 0], c[:, 1], c[:, 2], seed + k) for k in range(3)], 1)
                d = np.linalg.norm(c + jitter - q, axis=1)
                best = np.minimum(best, d)
    return best


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)
