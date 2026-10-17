"""Ferramentas de modelagem de roupas a partir da anatomia do avatar-base.

Fluxo de uma peça:
1. Seleciona faces do corpo (região anatômica).
2. Desloca pela normal (folga), alisa (Taubin) e aplica caimento (tecido pendurado).
3. Garante distância mínima do corpo, adiciona espessura, golas, punhos e barras.
4. Cada vértice da roupa guarda o vértice anatômico de origem: pesos de
   deformação e morphs vêm dele, então a roupa veste qualquer corpo criado.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

import mh
from model import vertex_normals


@dataclass
class Surface:
    pos: np.ndarray      # (N,3)
    vid: np.ndarray      # (N,) vértice do corpo de origem
    uv: np.ndarray       # (N,2)
    tris: np.ndarray     # (T,3)
    ref: np.ndarray      # (N,3) posição anatômica de referência (para padrões de textura)
    part: np.ndarray | None = None  # (N,) rótulo opcional (0 corpo, 1 gola/punho, 2 espessura)

    def copy(self):
        return Surface(self.pos.copy(), self.vid.copy(), self.uv.copy(), self.tris.copy(), self.ref.copy(),
                       None if self.part is None else self.part.copy())


class Anatomy:
    """Parâmetros anatômicos por vértice: osso dominante e posição ao longo dele."""

    def __init__(self, model):
        self.model = model
        W = model.weights
        self.bone = np.array(model.bone_names)[np.argmax(W, axis=1)]
        heads = np.array([model.heads[b] for b in model.bone_names])
        tails = np.array([model.tails[b] for b in model.bone_names])
        idx = np.argmax(W, axis=1)
        h, t = heads[idx], tails[idx]
        d = t - h
        self.t = ((model.coords - h) * d).sum(1) / np.maximum((d * d).sum(1), 1e-9)
        self.h = model.heads

    def is_(self, v, *names):
        b = self.bone[v]
        return np.isin(b, [n for n in names])

    def side(self, v):
        return np.sign(self.model.coords[v, 0])


def select(layout, pred):
    """Faces do material 'body' cujo predicado (sobre os ids dos vértices) é verdadeiro."""
    return [corners for mat, corners in layout.faces if mat == 'body' and pred(np.array([v for v, _ in corners]))]


def surface(model, faces) -> Surface:
    index, vid, uvs, tris = {}, [], [], []
    for corners in faces:
        ids = []
        for v, uv in corners:
            key = (v, round(float(uv[0]), 6), round(float(uv[1]), 6))
            if key not in index:
                index[key] = len(vid)
                vid.append(v)
                uvs.append(uv)
            ids.append(index[key])
        for i in range(1, len(ids) - 1):
            tris.append((ids[0], ids[i], ids[i + 1]))
    vid = np.array(vid)
    return Surface(model.coords[vid].copy(), vid, np.array(uvs), np.array(tris), model.coords[vid].copy())


def welded(s: Surface):
    """Mapa de vértices duplicados por costura de UV -> índice canônico (para alisar sem rasgar)."""
    key = np.concatenate([np.round(s.pos * 1e5).astype(np.int64), s.vid[:, None]], 1)
    _, canon = np.unique(key, axis=0, return_inverse=True)
    return canon.reshape(-1)


def neighbors(s: Surface):
    canon = welded(s)
    n = canon.max() + 1
    edges = set()
    for a, b, c in canon[s.tris]:
        edges.update({(a, b), (b, a), (b, c), (c, b), (c, a), (a, c)})
    e = np.array(sorted(edges))
    return canon, n, e


def boundary_mask(s: Surface):
    canon = welded(s)
    count = {}
    for tri in canon[s.tris]:
        for i in range(3):
            a, b = sorted((tri[i], tri[(i + 1) % 3]))
            count[(a, b)] = count.get((a, b), 0) + 1
    border = np.zeros(canon.max() + 1, bool)
    for (a, b), c in count.items():
        if c == 1:
            border[a] = border[b] = True
    return border[canon]


def smooth(s: Surface, iters=6, lam=.5, mu=-.53, weights=None, keep_boundary=False):
    """Alisamento Taubin (remove detalhe anatômico sem encolher)."""
    canon, n, e = neighbors(s)
    P = np.zeros((n, 3))
    P[canon] = s.pos
    deg = np.bincount(e[:, 0], minlength=n).astype(float)
    fixed = boundary_mask(s) if keep_boundary else None
    fixed_c = np.zeros(n, bool)
    if fixed is not None:
        fixed_c[canon[fixed]] = True
    w = np.ones(n) if weights is None else np.bincount(canon, weights=weights, minlength=n) / np.maximum(np.bincount(canon, minlength=n), 1)
    for _ in range(iters):
        for k in (lam, mu):
            acc = np.zeros((n, 3))
            np.add.at(acc, e[:, 0], P[e[:, 1]])
            L = acc / np.maximum(deg, 1)[:, None] - P
            step = k * L * w[:, None]
            step[fixed_c] = 0
            P = P + step
    s.pos = P[canon]


def flatten(s: Surface, centers, radius=.03, iters=0):
    """Remove saliências (mamilos) ajustando uma superfície quadrática ao anel ao redor."""
    for c in centers:
        d = np.linalg.norm(s.ref - c, axis=1)
        ring = (d > radius * .9) & (d < radius * 1.7)
        inner = d < radius * 1.2
        if ring.sum() < 6 or not inner.any():
            continue
        P = s.pos[ring]
        cen = P.mean(0)
        _, _, vt = np.linalg.svd(P - cen)
        nrm = vt[2]
        if nrm[2] < 0:
            nrm = -nrm
        ax, ay = vt[0], vt[1]
        def local(Q):
            r = Q - cen
            return r @ ax, r @ ay, r @ nrm
        x, y, z = local(P)
        A = np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], 1)
        coef, *_ = np.linalg.lstsq(A, z, rcond=None)
        Q = s.pos[inner]
        qx, qy, qz = local(Q)
        fz = np.stack([np.ones_like(qx), qx, qy, qx * qx, qx * qy, qy * qy], 1) @ coef
        w = np.clip((radius * 1.2 - d[inner]) / (radius * .5), 0, 1)
        w = w * w * (3 - 2 * w)
        s.pos[inner] = Q + nrm * ((fz - qz) * w)[:, None]


def smooth_values(s: Surface, values, iters=4):
    canon, n, e = neighbors(s)
    V = np.zeros((n,) + values.shape[1:])
    np.add.at(V, canon, values)
    V /= np.maximum(np.bincount(canon, minlength=n), 1).reshape((-1,) + (1,) * (values.ndim - 1))
    deg = np.bincount(e[:, 0], minlength=n).astype(float)
    for _ in range(iters):
        acc = np.zeros_like(V)
        np.add.at(acc, e[:, 0], V[e[:, 1]])
        V = .5 * V + .5 * acc / np.maximum(deg, 1).reshape((-1,) + (1,) * (values.ndim - 1))
    return V[canon]


def offset(model, s: Surface, amount):
    """Afasta da pele pela normal anatômica (amount escalar ou por vértice)."""
    s.pos = s.pos + model.normals[s.vid] * np.reshape(amount, (-1, 1))


def push_out(model, s: Surface, minimum, tris=None, smooth_body=True, skip=None):
    """Nenhum ponto da roupa fica a menos de `minimum` da pele (alisada: tecido não marca mamilos)."""
    ids, bary, off = model.bind(s.pos, tris, coords=model.smoothed() if smooth_body else None)
    if skip is not None:
        minimum = np.where(skip, -1.0, minimum)
    n = (model.normals[ids] * bary[..., None]).sum(1)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    d = (off * n).sum(1)
    m = np.reshape(minimum, -1) if np.ndim(minimum) else np.full(len(s.pos), minimum)
    s.pos = s.pos + n * np.maximum(m - d, 0)[:, None]


def drape(model, s: Surface, mask, amount=.85, slope=.18, axis_z=None):
    """Tecido pendurado: abaixo do peito o raio não encolhe tão rápido quanto o corpo.

    mask: vértices do tronco que participam. Usa fatias horizontais e setores angulares.
    """
    P = s.pos
    cz = axis_z if axis_z is not None else np.median(P[mask, 2])
    rel = P - np.array([0, 0, cz])
    r = np.hypot(rel[:, 0], rel[:, 2])
    th = np.arctan2(rel[:, 0], rel[:, 2])
    nb_th, dy = 48, .01
    ti = ((th + np.pi) / (2 * np.pi) * nb_th).astype(int) % nb_th
    yi = np.floor(P[:, 1] / dy).astype(int)
    y0 = yi[mask].min()
    ny = yi[mask].max() - y0 + 1
    R = np.zeros((ny, nb_th))
    np.maximum.at(R, (yi[mask] - y0, ti[mask]), r[mask])
    # Propaga o raio de cima para baixo (o tecido cai do peito/omoplatas).
    env = R.copy()
    for k in range(ny - 2, -1, -1):
        env[k] = np.maximum(R[k], env[k + 1] - slope * dy * 10)
    # Suaviza angularmente.
    env = (np.roll(env, 1, 1) + 2 * env + np.roll(env, -1, 1)) / 4
    target = env[np.clip(yi - y0, 0, ny - 1), ti]
    k = np.where(mask, amount, 0)
    newr = np.maximum(r, r + (target - r) * k)
    scale = np.where(r > 1e-6, newr / np.maximum(r, 1e-6), 1)
    s.pos = np.stack([rel[:, 0] * scale, P[:, 1], rel[:, 2] * scale + cz], 1)


def loops(s: Surface):
    """Laços de borda (cada abertura da roupa) como listas ordenadas de vértices."""
    canon = welded(s)
    edge_count = {}
    for tri in s.tris:
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            key = tuple(sorted((canon[a], canon[b])))
            edge_count.setdefault(key, []).append((a, b))
    nxt = {}
    for key, uses in edge_count.items():
        if len(uses) == 1:
            a, b = uses[0]
            nxt[a] = b
    # Liga por vértice canônico (costuras de UV).
    by_canon = {}
    for a in nxt:
        by_canon.setdefault(canon[a], a)
    out, seen = [], set()
    for start in list(nxt):
        if start in seen:
            continue
        loop, cur = [], start
        while cur not in seen:
            seen.add(cur)
            loop.append(cur)
            n = nxt.get(cur)
            if n is None:
                n = nxt.get(by_canon.get(canon[cur], -1))
                if n is None:
                    alt = [a for a in nxt if canon[a] == canon[cur] and a not in seen]
                    if not alt:
                        break
                    n = nxt[alt[0]]
            if canon[n] in [canon[x] for x in loop[:1]]:
                break
            cur = n
            if cur in seen:
                break
        if len(loop) > 4:
            out.append(np.array(loop))
    return out


_strip = [0]


def strip_rect():
    """Retângulo de UV livre (área da cabeça no atlas do corpo) para faixas: (u0, v0, u1, v1)."""
    k = _strip[0]
    _strip[0] += 1
    col, row = divmod(k, 20)
    v0 = .2 + row * .032
    u0 = .655 + col * .17
    return u0, v0, u0 + .165, v0 + .028


def reset_strips():
    _strip[0] = 0


def straighten(s: Surface, loop, point, normal, rings=3):
    """Corta a borda num plano (barra reta) e relaxa os anéis vizinhos."""
    normal = np.asarray(normal, float) / np.linalg.norm(normal)
    canon = welded(s)
    d = (s.pos[loop] - point) @ normal
    move = -d[:, None] * normal
    targets = {int(c): mv for c, mv in zip(canon[loop], move)}
    # Propaga o deslocamento amortecido para os anéis internos.
    _, n, e = neighbors(s)
    disp = np.zeros((n, 3))
    w = np.zeros(n)
    for c, mv in targets.items():
        disp[c] = mv
        w[c] = 1
    front = set(targets)
    seen = set(front)
    for r in range(1, rings + 1):
        nxt = set()
        for a, b in e:
            if a in front and b not in seen:
                nxt.add(b)
        for b in nxt:
            nb = [a for a in e[e[:, 0] == b][:, 1] if a in front]
            disp[b] = np.mean([disp[a] for a in nb], axis=0) * (1 - r / (rings + 1))
            w[b] = 1
        seen |= nxt
        front = nxt
    s.pos = s.pos + disp[canon]


def band(s: Surface, loop, out_dir, height, rows=3, part=1, flare=0.0, uv_scale=(1, 1), inward=0.0):
    """Faixa (gola, punho, barra) construída ao longo de um laço de borda.

    out_dir(p) -> direção da extrusão; a faixa herda vid/ref do vértice de borda.
    """
    # Alisa o contorno (bordas de faces em escada viram uma curva limpa).
    P = s.pos[loop].copy()
    for _ in range(4):
        P = .25 * np.roll(P, 1, 0) + .5 * P + .25 * np.roll(P, -1, 0)
    canon = welded(s)
    same = {c: P[i] for i, c in enumerate(canon[loop])}
    for i in range(len(s.pos)):
        c = canon[i]
        if c in same:
            s.pos[i] = same[c]
    D = out_dir(P)
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    # Direção "para fora" da faixa (perpendicular ao laço e à extrusão).
    T = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    O = np.cross(T, D)
    center = P.mean(0)
    flip = ((P - center) * O).sum(1).mean() < 0
    if flip:
        O = -O
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1))])
    u0, v0, u1, v1 = strip_rect()
    u = u0 + L[:-1] / L[-1] * (u1 - u0)
    base = len(s.pos)
    new_pos, new_vid, new_uv, new_ref, new_part = [], [], [], [], []
    for r in range(1, rows + 1):
        f = r / rows
        bulge = np.sin(f * np.pi) * .0015
        new_pos.append(P + D * height * f + O * (flare * f + bulge) - O * inward * f)
        new_vid.append(s.vid[loop])
        new_uv.append(np.stack([u, np.full_like(u, v0 + f * (v1 - v0))], 1))
        new_ref.append(s.ref[loop] + D * height * f)
        new_part.append(np.full(len(loop), part))
    rows_idx = [np.asarray(loop)] + [base + k * len(loop) + np.arange(len(loop)) for k in range(rows)]
    # Para a faixa, o primeiro anel precisa de UV próprio: duplica a borda.
    first = base + rows * len(loop) + np.arange(len(loop))
    new_pos.append(P)
    new_vid.append(s.vid[loop])
    new_uv.append(np.stack([u, np.full_like(u, v0)], 1))
    new_ref.append(s.ref[loop])
    new_part.append(np.full(len(loop), part))
    rows_idx[0] = first
    tris = []
    n = len(loop)
    for k in range(rows):
        a_row, b_row = rows_idx[k], rows_idx[k + 1]
        for i in range(n):
            j = (i + 1) % n
            a, b, c, d = a_row[i], a_row[j], b_row[i], b_row[j]
            tris.append((a, c, b) if not flip else (a, b, c))
            tris.append((b, c, d) if not flip else (b, d, c))
    s.pos = np.vstack([s.pos] + new_pos)
    s.vid = np.concatenate([s.vid] + new_vid)
    s.uv = np.vstack([s.uv] + new_uv)
    s.ref = np.vstack([s.ref] + new_ref)
    s.part = np.concatenate([s.part if s.part is not None else np.zeros(base, int)] + new_part)
    s.tris = np.vstack([s.tris, np.array(tris)])
    return rows_idx[-1]


def solidify(s: Surface, thickness=.0025):
    """Adiciona o lado de dentro do tecido e fecha as bordas (espessura visível)."""
    n = vertex_normals_canon(s)
    N = len(s.pos)
    inner = s.pos - n * thickness
    tris_in = s.tris[:, ::-1] + N
    rims = []
    for loop in loops(s):
        for i in range(len(loop)):
            a, b = loop[i], loop[(i + 1) % len(loop)]
            rims.append((a, b + N, b))
            rims.append((a, a + N, b + N))
    s.pos = np.vstack([s.pos, inner])
    s.vid = np.concatenate([s.vid, s.vid])
    s.uv = np.vstack([s.uv, s.uv])
    s.ref = np.vstack([s.ref, s.ref])
    part = s.part if s.part is not None else np.zeros(N, int)
    s.part = np.concatenate([part, np.full(N, 2)])
    s.tris = np.vstack([s.tris, tris_in, np.array(rims).reshape(-1, 3)])


def vertex_normals_canon(s: Surface):
    canon = welded(s)
    # Normais suaves através das costuras (vértices com o mesmo vid e mesma posição).
    key = np.round(s.pos * 1e5).astype(np.int64)
    _, uniq = np.unique(key, axis=0, return_inverse=True)
    uniq = uniq.reshape(-1)
    P = np.zeros((uniq.max() + 1, 3))
    P[uniq] = s.pos
    n = vertex_normals(P, uniq[s.tris])
    return n[uniq]


def smooth_loop(s: Surface, loop, iters=20, rings=3):
    """Suaviza uma borda curva (cava, decote) removendo os degraus da malha."""
    P = s.pos[loop].copy()
    target = P.copy()
    for _ in range(iters):
        target = .5 * target + .25 * (np.roll(target, 1, 0) + np.roll(target, -1, 0))
    move = target - P
    canon = welded(s)
    _, n, e = neighbors(s)
    disp = np.zeros((n, 3))
    front = set()
    for c, mv in zip(canon[loop], move):
        disp[int(c)] = mv
        front.add(int(c))
    seen = set(front)
    for r in range(1, rings + 1):
        nxt = set()
        for a, b in e:
            if a in front and b not in seen:
                nxt.add(b)
        for b in nxt:
            nb = [a for a in e[e[:, 0] == b][:, 1] if a in front]
            disp[b] = np.mean([disp[a] for a in nb], axis=0) * (1 - r / (rings + 1))
        seen |= nxt
        front = nxt
    s.pos = s.pos + disp[canon]
