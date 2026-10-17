"""Extração de isosuperfície por surface nets (numpy puro, sem dependências extras).

Cada célula da grade atravessada pela superfície recebe um vértice (média dos
cruzamentos nas arestas); cada aresta da grade com troca de sinal vira um quad
entre as quatro células vizinhas. A orientação é corrigida pelo gradiente.
"""
from __future__ import annotations

import numpy as np

_CORNERS = np.array([(i, j, k) for i in (0, 1) for j in (0, 1) for k in (0, 1)])
_EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8) if np.abs(_CORNERS[a] - _CORNERS[b]).sum() == 1]


def surface_nets(vals, step=1.0, origin=(0, 0, 0)):
    """vals: grade (nx, ny, nz) de distâncias (negativo = dentro). Retorna (verts, tris)."""
    vals = np.asarray(vals, np.float64)
    nx, ny, nz = vals.shape
    cs = (nx - 1, ny - 1, nz - 1)
    corner = np.stack([vals[i:i + cs[0], j:j + cs[1], k:k + cs[2]] for i, j, k in _CORNERS], -1)
    neg = corner < 0
    mixed = neg.any(-1) & ~neg.all(-1)
    cell = np.full(cs, -1, np.int64)
    ci = np.argwhere(mixed)
    cell[mixed] = np.arange(len(ci))
    cv = corner[mixed]
    acc = np.zeros((len(ci), 3))
    cnt = np.zeros(len(ci))
    for a, b in _EDGES:
        va, vb = cv[:, a], cv[:, b]
        m = (va < 0) != (vb < 0)
        t = va[m] / (va[m] - vb[m])
        acc[m] += _CORNERS[a] + t[:, None] * (_CORNERS[b] - _CORNERS[a])
        cnt[m] += 1
    verts = (ci + acc / np.maximum(cnt, 1)[:, None]) * step + np.asarray(origin, float)
    quads = []
    for ax in range(3):
        o1, o2 = [d for d in range(3) if d != ax]
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[ax] = slice(0, -1)
        sl1[ax] = slice(1, None)
        for d in (o1, o2):
            sl0[d] = slice(1, -1)
            sl1[d] = slice(1, -1)
        v0, v1 = vals[tuple(sl0)], vals[tuple(sl1)]
        cross = (v0 < 0) != (v1 < 0)
        g = np.argwhere(cross)
        g[:, o1] += 1
        g[:, o2] += 1
        flip = (v0[cross] < 0)
        offs = []
        for d1, d2 in ((1, 1), (0, 1), (0, 0), (1, 0)):
            c = g.copy()
            c[:, o1] -= d1
            c[:, o2] -= d2
            offs.append(cell[c[:, 0], c[:, 1], c[:, 2]])
        q = np.stack(offs, 1)
        q[flip] = q[flip][:, ::-1]
        quads.append(q)
    q = np.vstack(quads)
    q = q[(q >= 0).all(1)]
    tris = np.vstack([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    return verts, tris


def orient(verts, tris, fn, eps=1e-4):
    """Inverte triângulos cuja normal geométrica contraria o gradiente de fn (aponta para fora)."""
    p = verts[tris]
    c = p.mean(1)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    g = np.stack([fn(c + e) - fn(c - e) for e in np.eye(3) * eps], -1)
    bad = (n * g).sum(1) < 0
    tris = tris.copy()
    tris[bad] = tris[bad][:, ::-1]
    return tris
