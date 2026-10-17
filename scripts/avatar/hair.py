"""Cabelos com volume real: cachos em hélice, tranças e coques gerados sobre o couro cabeludo."""
from __future__ import annotations

import numpy as np
from PIL import Image

from overlays import Landmarks
from raster import fbm


def scalp_line(L, aaz):
    ey = L.eye_y
    return np.interp(aaz, [0, 30, 55, 72, 80, 95, 112, 140, 180],
                     [ey + .062, ey + .06, ey + .052, ey + .03, ey + .002, ey + .02, ey + .006, ey - .05, ey - .085])


def scalp_samples(model, spacing, predicate, seed=1):
    """Pontos aproximadamente equidistantes sobre o couro cabeludo (Poisson por rejeição)."""
    rng = np.random.default_rng(seed)
    L = Landmarks(model)
    c = model.coords
    tris = model.body_tris
    cen = c[tris].mean(1)
    head = cen[:, 1] > model.heads['Neck'][1] + .05
    t = tris[head]
    A, B, C = c[t[:, 0]], c[t[:, 1]], c[t[:, 2]]
    area = np.linalg.norm(np.cross(B - A, C - A), axis=1) / 2
    n_cand = 30000
    pick = rng.choice(len(t), n_cand, p=area / area.sum())
    r1, r2 = rng.random(n_cand), rng.random(n_cand)
    s = np.sqrt(r1)
    bary = np.stack([1 - s, s * (1 - r2), s * r2], 1)
    P = A[pick] * bary[:, :1] + B[pick] * bary[:, 1:2] + C[pick] * bary[:, 2:3]
    N = model.normals[t[pick]]
    N = (N * bary[..., None]).sum(1)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    rel = P - L.center
    aaz = np.abs(np.degrees(np.arctan2(rel[:, 0], rel[:, 2])))
    height = (P[:, 1] - scalp_line(L, aaz)) / (L.top - L.eye_y)
    ok = predicate(P, N, height, aaz)
    P, N, height = P[ok], N[ok], height[ok]
    order = rng.permutation(len(P))
    kept = []
    from scipy.spatial import cKDTree
    grid = {}
    for i in order:
        key = tuple((P[i] // spacing).astype(int))
        close = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        if np.linalg.norm(P[i] - P[j]) < spacing:
                            close = True
                            break
        if not close:
            kept.append(i)
            grid.setdefault(key, []).append(i)
    kept = np.array(kept)
    return P[kept], N[kept], height[kept]


def tube_mesh(paths, radii, sides=6, tip=None):
    """Tubos ao longo de caminhos (lista de (K,3)). Retorna pos, nrm, uv, tris, along."""
    pos, nrm, uv, tris, along = [], [], [], [], []
    base = 0
    for path, rad in zip(paths, radii):
        K = len(path)
        T = np.gradient(path, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        # Quadro de transporte paralelo (sem torções bruscas).
        ref = np.array([0, 1, 0]) if abs(T[0, 1]) < .9 else np.array([1, 0, 0])
        Nf = np.cross(T[0], ref)
        Nf /= np.linalg.norm(Nf)
        frames = []
        for k in range(K):
            if k:
                Nf = Nf - T[k] * np.dot(Nf, T[k])
                Nf /= max(np.linalg.norm(Nf), 1e-9)
            Bf = np.cross(T[k], Nf)
            frames.append((Nf.copy(), Bf))
        length = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        for k in range(K):
            Nf, Bf = frames[k]
            r = rad[k]
            for s in range(sides):
                a = 2 * np.pi * s / sides
                d = np.cos(a) * Nf + np.sin(a) * Bf
                pos.append(path[k] + d * r)
                nrm.append(d)
                uv.append((s / sides, length[k] * 40))
                along.append(k / (K - 1))
        for k in range(K - 1):
            for s in range(sides):
                a = base + k * sides + s
                b = base + k * sides + (s + 1) % sides
                c = a + sides
                d = b + sides
                tris.append((a, c, b))
                tris.append((b, c, d))
        base += K * sides
    return np.array(pos), np.array(nrm), np.array(uv), np.array(tris), np.array(along)


def coils(roots, normals, rng, length, radius, turns, thickness, lean, seg_per_turn=10, center=None, envelope=None):
    paths, radii = [], []
    for p, n in zip(roots, normals):
        L = rng.uniform(*length)
        R = rng.uniform(*radius)
        tn = rng.uniform(*turns)
        th = rng.uniform(*thickness)
        axis = n + lean + rng.normal(0, .25, 3)
        axis /= np.linalg.norm(axis)
        ref = np.array([0, 1, 0]) if abs(axis[1]) < .9 else np.array([1, 0, 0])
        u = np.cross(axis, ref); u /= np.linalg.norm(u)
        v = np.cross(axis, u)
        K = max(8, int(seg_per_turn * tn) + 2)
        t = np.linspace(0, 1, K)
        phase = rng.uniform(0, 2 * np.pi)
        ang = phase + t * tn * 2 * np.pi
        rr = R * np.clip(t * 4, 0, 1)  # começa colado à raiz
        path = p + np.outer(t * L, axis) + np.outer(np.cos(ang) * rr, u) + np.outer(np.sin(ang) * rr, v)
        if envelope is not None:
            path = envelope(path)
        # Nunca atravessa o couro cabeludo.
        depth = (path - p) @ n
        path = path - np.outer(np.minimum(depth - .0015 * t, 0), n)
        paths.append(path)
        radii.append(th * (1 - .55 * t ** 1.5))
    return paths, radii


def strand_texture(size=256, seed=5):
    """Textura de fios (albedo leve + normal) que acompanha o comprimento do tubo."""
    rng = np.random.default_rng(seed)
    x = (np.arange(size) + .5) / size
    cols = np.zeros(size)
    for k in range(1, 40):
        cols += rng.uniform(.2, 1) * np.sin(2 * np.pi * (k * 3 * x + rng.uniform()))
    cols = (cols - cols.min()) / (cols.max() - cols.min())
    yy, xx = np.mgrid[0:size, 0:size] / size
    pts = np.stack([xx.ravel() * 6, yy.ravel() * .5, np.zeros(size * size)], 1)
    var = fbm(pts, 8, 2, seed).reshape(size, size)
    h = cols[None, :] * .7 + var * .3
    alb = .78 + .22 * h
    gx = np.gradient(h, axis=1) * 6
    nmap = np.stack([-gx, np.zeros_like(gx), np.ones_like(gx)], -1)
    nmap /= np.linalg.norm(nmap, axis=2, keepdims=True)
    a = Image.fromarray((np.stack([alb, alb, np.zeros_like(alb)], -1) * 255).astype(np.uint8), 'RGB')
    n = Image.fromarray(((nmap * .5 + .5) * 255).astype(np.uint8), 'RGB')
    return a, n


def curl_height(p, freq=420, seed=3):
    """Relevo de cachos: anéis em células de Voronoi (vistos de fora, cada cacho é uma espiral)."""
    from raster import _hash
    q = np.asarray(p, np.float64) * freq
    i = np.floor(q).astype(np.int64)
    best = np.full(len(q), 9.0)
    second = np.full(len(q), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                jitter = np.stack([_hash(c[:, 0], c[:, 1], c[:, 2], seed + k) for k in range(3)], 1)
                d = np.linalg.norm(c + jitter - q, axis=1)
                second = np.where(d < best, best, np.minimum(second, d))
                best = np.minimum(best, d)
    ring = np.abs(np.sin(best * np.pi * 2.6))
    edge = np.clip((second - best) * 3, 0, 1)
    return ring * edge, best
