"""Cabelos estilizados em mechas esculpidas (estilo animação).

Cada penteado é composto por:
- mechas de "calota": nascem no couro cabeludo e correm rente à cabeça até um
  ponto de destino (penteado para trás, coque, rabo de cavalo);
- mechas "livres": nascem num ponto e caem com gravidade, ondas e cachos
  (franja, rabo, mechas laterais, espetos), sem atravessar cabeça e ombros.
Cada mecha é um tubo de seção elíptica, largo e achatado, com a face larga
voltada para fora da cabeça, como nos modelos esculpidos à mão.
"""
from __future__ import annotations

import numpy as np

from hair import scalp_line
from overlays import Landmarks


class HeadVolume:
    """Elipsoide ajustado ao crânio + esferas dos ombros/pescoço para colisão."""

    def __init__(self, model):
        L = Landmarks(model)
        c = model.coords[:13380]
        head = c[(c[:, 1] > L.eye_y - .02)]
        self.center = (head.min(0) + head.max(0)) / 2
        self.radii = (head.max(0) - head.min(0)) / 2
        self.L = L
        self.neck = model.heads['Neck']
        self.shoulders = [model.heads['LeftArm'], model.heads['RightArm'], model.heads['Spine2'] + np.array([0, .08, .03])]

    def push_out(self, p, margin):
        rel = (p - self.center) / (self.radii + margin)
        r = np.linalg.norm(rel, axis=-1, keepdims=True)
        inside = r < 1
        p = np.where(inside, self.center + rel / np.maximum(r, 1e-6) * (self.radii + margin), p)
        for s, rad in zip(self.shoulders, (.085, .085, .13)):
            d = p - s
            n = np.linalg.norm(d, axis=-1, keepdims=True)
            p = np.where(n < rad + margin, s + d / np.maximum(n, 1e-6) * (rad + margin), p)
        return p

    def surface_dir(self, p):
        d = (p - self.center) / self.radii ** 2
        return d / np.linalg.norm(d, axis=-1, keepdims=True)


def roots(model, spacing, predicate, seed=3):
    """Raízes no couro cabeludo (posição, normal, azimute em graus, altura relativa à linha do cabelo)."""
    from hair import scalp_samples
    L = Landmarks(model)
    P, N, _ = scalp_samples(model, spacing, lambda P, N, h, aaz: predicate(P, N, aaz), seed)
    rel = P - L.center
    az = np.degrees(np.arctan2(rel[:, 0], rel[:, 2]))
    return P, N, az


def cap_path(vol, start, target, k=16, lift=(.004, .02), bulge=.0):
    """Caminho rente ao crânio de `start` até `target`, afastando-se aos poucos (volume)."""
    t = np.linspace(0, 1, k)[:, None]
    a = (start - vol.center) / vol.radii
    b = (target - vol.center) / vol.radii
    a /= np.linalg.norm(a)
    b /= np.linalg.norm(b)
    ang = np.arccos(np.clip(np.dot(a, b), -1, 1))
    if ang < 1e-4:
        dirs = np.repeat(a[None], k, 0)
    else:
        dirs = (np.sin((1 - t) * ang) * a + np.sin(t * ang) * b) / np.sin(ang)
    off = lift[0] + (lift[1] - lift[0]) * np.sin(t * np.pi) ** .7 + bulge * np.sin(t * np.pi)
    pts = vol.center + dirs * vol.radii + vol.surface_dir(vol.center + dirs * vol.radii) * off
    return pts


def free_path(vol, start, direction, length, k=18, gravity=.6, wave=(0, 0, 0), curl=(0, 0), stiff=.35, margin=.006, seed=0, swirl=None):
    """Mecha que cai: direção inicial, gravidade, ondas (amplitude, frequência, fase) e cachos (raio, voltas)."""
    rng = np.random.default_rng(seed)
    step = length / (k - 1)
    p = np.array(start, float)
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    pts = [p.copy()]
    side = np.cross(d, [0, 1, 0])
    if np.linalg.norm(side) < 1e-3:
        side = np.array([1.0, 0, 0])
    side /= np.linalg.norm(side)
    for i in range(1, k):
        t = i / (k - 1)
        g = np.array([0, -1, 0]) * gravity * t
        d = d * (1 - stiff * .2) + g * .25 + (swirl(p) if swirl else 0)
        d /= np.linalg.norm(d)
        p = p + d * step
        p = vol.push_out(p, margin)
        pts.append(p.copy())
    pts = np.array(pts)
    t = np.linspace(0, 1, k)
    amp, freq, phase = wave
    if amp:
        pts += np.outer(np.sin(t * freq * 2 * np.pi + phase) * amp * np.clip(t * 3, 0, 1), side)
    rad, turns = curl
    if rad:
        T = np.gradient(pts, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        u = np.cross(T, [0, 0, 1.0])
        u[np.linalg.norm(u, axis=1) < 1e-3] = [1, 0, 0]
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        v = np.cross(T, u)
        ang = t * turns * 2 * np.pi + rng.uniform(0, 6.28)
        r = rad * np.clip(t * 2.5, 0, 1)
        pts += u * (np.cos(ang) * r)[:, None] + v * (np.sin(ang) * r)[:, None]
        pts = vol.push_out(pts, margin * .6)
    return pts


def clump_mesh(paths, widths, vol, sides=6, flat=.42, twist=None):
    """Tubos achatados: largura w(t), espessura flat*w, face larga voltada para fora da cabeça."""
    pos, nrm, uv, tris, along = [], [], [], [], []
    base = 0
    for j, (path, w) in enumerate(zip(paths, widths)):
        K = len(path)
        T = np.gradient(path, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        out = path - vol.center
        out -= T * (out * T).sum(1, keepdims=True)
        out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
        wide = np.cross(T, out)
        wide /= np.maximum(np.linalg.norm(wide, axis=1, keepdims=True), 1e-9)
        if twist is not None:
            a = twist[j] * np.linspace(0, 1, K)[:, None]
            wide, out = wide * np.cos(a) + out * np.sin(a), out * np.cos(a) - wide * np.sin(a)
        L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        for k in range(K):
            for s in range(sides):
                a = 2 * np.pi * s / sides
                cx, cy = np.cos(a), np.sin(a)
                # Perfil levemente pontudo nas bordas (mecha esculpida).
                ex = np.sign(cx) * abs(cx) ** .8
                pos.append(path[k] + wide[k] * ex * w[k] / 2 + out[k] * cy * w[k] * flat / 2)
                n = wide[k] * cx * flat + out[k] * cy
                nrm.append(n / np.linalg.norm(n))
                uv.append((s / sides, L[k] * 12))
                along.append(k / (K - 1))
        for k in range(K - 1):
            for s in range(sides):
                a0 = base + k * sides + s
                b0 = base + k * sides + (s + 1) % sides
                tris += [(a0, a0 + sides, b0), (b0, a0 + sides, b0 + sides)]
        # Tampa na ponta (fecha o tubo).
        tip = base + (K - 1) * sides
        for s in range(1, sides - 1):
            tris.append((tip, tip + s + 1, tip + s))
        base += K * sides
    return np.array(pos), np.array(nrm), np.array(uv), np.array(tris), np.array(along)


def taper(K, w0, w_end=.15, start=.0):
    t = np.linspace(0, 1, K)
    return w0 * (1 - (1 - w_end) * np.clip((t - start) / (1 - start + 1e-9), 0, 1) ** 1.6) * (.75 + .25 * np.clip(t * 6, 0, 1))
