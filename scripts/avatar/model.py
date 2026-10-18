"""Modelo-base compartilhado: geometria em repouso, morphs, juntas e pesos.

Tudo que é vestido no avatar (roupa, cabelo, acessório) é amarrado à superfície
deste modelo por coordenadas baricêntricas. Assim pesos de deformação e morphs
são transferidos automaticamente, sem rig manual por peça ou por jogador.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

import mh
import spec


class AvatarModel:
    def __init__(self):
        self.mesh = mh.load_base()
        n = len(self.mesh.coords)
        self.targets = mh.TargetCache(n)
        base_macro = mh.macro_delta(self.targets, **spec.BASE)
        self.ethnic = spec.BASE.get('ethnic', (1 / 3, 1 / 3, 1 / 3))
        athletic = sum(self.targets(t) * w for t, w in spec.ATHLETIC)
        face = sum(self.targets(t) * w for t, w in spec.FACE_BASE)
        self.coords = self.mesh.coords + base_macro + athletic + face
        self.morphs: dict[str, np.ndarray] = {}
        for name, overrides in spec.MACRO_MORPHS.items():
            params = dict(spec.BASE, **overrides)
            reference = dict(spec.BASE)
            if params['gender'] != spec.BASE['gender']:
                reference['gender'] = params['gender']
            if name == 'body_feminine':
                reference = dict(spec.BASE)
            self.morphs[name] = mh.macro_delta(self.targets, **params) - mh.macro_delta(self.targets, **reference)
            if name == 'body_feminine':
                self.morphs[name] -= athletic * .8
            if name == 'body_child_m':
                self.morphs[name] -= athletic * .9
            if name == 'body_child_f':
                self.morphs[name] -= athletic * .2
        for name, parts in spec.TARGET_MORPHS.items():
            d = np.zeros((n, 3))
            for target, w in parts:
                d += self.targets(target) * w
            self.morphs[name] = d
        for name, units in spec.EXPRESSIONS.items():
            d = np.zeros((n, 3))
            for unit in units:
                for e, w in zip(spec.ETHNIC, self.ethnic):
                    d += self.targets(f'expression/units/{e}/{unit}') * w
            self.morphs[name] = d
        self._sculpt_toon_face()
        self.morph_names = list(self.morphs)
        self.bones = mh.load_rig(self.mesh, self.coords)
        self.bone_names = [b.name for b in self.bones]
        # Ossos dos olhos (padrão Mixamo opcional) para direção do olhar.
        self.heads = {b.name: b.head for b in self.bones}
        self.tails = {b.name: b.tail for b in self.bones}
        for side, src in (('Left', 'l'), ('Right', 'r')):
            self.heads[f'{side}Eye'] = self.mesh.joint(f'helper-{src}-eye', self.coords)
            self.tails[f'{side}Eye'] = self.heads[f'{side}Eye'] + np.array([0, 0, .02])
            self.bones.append(mh.Bone(f'{side}Eye', 'Head', self.heads[f'{side}Eye'], self.tails[f'{side}Eye']))
            self.bone_names.append(f'{side}Eye')
        names, W = mh.load_weights(n)
        self.weights = np.zeros((n, len(self.bone_names)), dtype=np.float32)
        for j, name in enumerate(names):
            self.weights[:, self.bone_names.index(name)] += W[:, j]
        for side, src in (('Left', 'l'), ('Right', 'r')):
            ids = self.mesh.group_vertices(f'helper-{src}-eye')
            self.weights[ids] = 0
            self.weights[ids, self.bone_names.index(f'{side}Eye')] = 1
        # Deslocamento de cada junta por morph (necessário quando a proporção muda).
        self.joint_deltas: dict[str, dict[str, list[float]]] = {}
        for name, d in self.morphs.items():
            moved = self.joint_positions(self.coords + d)
            delta = {}
            for b in self.bone_names + ['ground']:
                v = moved[b] - (self.heads[b] if b != 'ground' else self.mesh.joint('joint-ground', self.coords))
                if np.abs(v).max() > 2e-4:
                    delta[b] = [round(float(x), 5) for x in v]
            if delta:
                self.joint_deltas[name] = delta
        # Superfície do corpo para amarrações.
        self.body_faces = self.mesh.groups['body']
        self.body_tris = np.array([[v for v, _ in t] for t in mh.triangulate(self.body_faces)])
        self.normals = vertex_normals(self.coords, self.body_tris)

    def _sculpt_toon_face(self):
        """Amplia o morph de animação com escultura anatômica compartilhada."""
        from sculpt_face import cinematic_delta
        self.morphs['style_toon'] += cinematic_delta(self)

    def smoothed(self, iters=12):
        """Corpo alisado (sem mamilos/umbigo/veias) para colisão de roupas."""
        if getattr(self, '_smooth', None) is None:
            tris = self.body_tris
            n = len(self.coords)
            e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]], tris[:, [1, 0]], tris[:, [2, 1]], tris[:, [0, 2]]])
            deg = np.bincount(e[:, 0], minlength=n).astype(float)
            P = self.coords.copy()
            for _ in range(iters):
                for k in (.5, -.53):
                    acc = np.zeros_like(P)
                    np.add.at(acc, e[:, 0], P[e[:, 1]])
                    L = acc / np.maximum(deg, 1)[:, None] - P
                    L[deg == 0] = 0
                    P = P + k * L
            from wardrobe import nipple_centers
            from garments import Surface, flatten
            tmp = Surface(P, np.arange(n), np.zeros((n, 2)), tris, self.coords)
            flatten(tmp, nipple_centers(self), .028)
            P = tmp.pos
            self._smooth = P
        return self._smooth

    def joint_positions(self, coords):
        out = {}
        bones = mh.load_rig(self.mesh, coords)
        for b in bones:
            out[b.name] = b.head
        for side, src in (('Left', 'l'), ('Right', 'r')):
            out[f'{side}Eye'] = self.mesh.joint(f'helper-{src}-eye', coords)
        out['ground'] = self.mesh.joint('joint-ground', coords)
        return out

    def bone_index(self, name):
        return self.bone_names.index(name)

    # -- amarração de geometria arbitrária -----------------------------
    def bind(self, points, tris=None, k=12, coords=None):
        """Projeta pontos na superfície (tris) e retorna (ids (N,3), bary (N,3), offset (N,3))."""
        tris = self.body_tris if tris is None else tris
        coords = self.coords if coords is None else coords
        P = np.asarray(points, dtype=np.float64)
        A, B, C = coords[tris[:, 0]], coords[tris[:, 1]], coords[tris[:, 2]]
        tree = cKDTree((A + B + C) / 3)
        _, cand = tree.query(P, k=min(k, len(tris)))
        best = np.full(len(P), np.inf)
        ids = np.zeros((len(P), 3), dtype=np.int64)
        bary = np.zeros((len(P), 3))
        for j in range(cand.shape[1]):
            t = cand[:, j]
            q, b = closest_on_triangle(P, A[t], B[t], C[t])
            d = np.linalg.norm(P - q, axis=1)
            better = d < best
            best[better] = d[better]
            ids[better] = tris[t[better]]
            bary[better] = b[better]
        surface = (coords[ids] * bary[..., None]).sum(axis=1)
        return ids, bary, P - surface

    def bound_morphs(self, ids, bary, names=None):
        out = {}
        for name in names or self.morph_names:
            d = (self.morphs[name][ids] * bary[..., None]).sum(axis=1)
            if np.abs(d).max() > 1e-5:
                out[name] = d
        return out

    def bound_weights(self, ids, bary):
        return (self.weights[ids] * bary[..., None]).sum(axis=1)


def vertex_normals(coords, tris):
    n = np.zeros_like(coords)
    fn = np.cross(coords[tris[:, 1]] - coords[tris[:, 0]], coords[tris[:, 2]] - coords[tris[:, 0]])
    for i in range(3):
        np.add.at(n, tris[:, i], fn)
    length = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(length, 1e-12)


def closest_on_triangle(p, a, b, c):
    """Ponto mais próximo em triângulos (vetorizado). Retorna ponto e baricêntricas."""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1)
    bp = p - b
    d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = p - c
    d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    denom = va + vb + vc
    denom = np.where(np.abs(denom) < 1e-18, 1e-18, denom)
    v = vb / denom
    w = vc / denom
    u = 1 - v - w
    bary = np.stack([u, v, w], 1)
    # Regiões de vértice e aresta.
    def setb(mask, uu, vv, ww):
        bary[mask] = np.stack([uu[mask], vv[mask], ww[mask]], 1)
    one, zero = np.ones_like(d1), np.zeros_like(d1)
    setb((d1 <= 0) & (d2 <= 0), one, zero, zero)
    setb((d3 >= 0) & (d4 <= d3), zero, one, zero)
    setb((d6 >= 0) & (d5 <= d6), zero, zero, one)
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0) & ~((d1 <= 0) & (d2 <= 0))
    t = np.clip(d1 / np.where(d1 - d3 == 0, 1e-18, d1 - d3), 0, 1)
    setb(m, 1 - t, t, zero)
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0) & ~((d1 <= 0) & (d2 <= 0))
    t = np.clip(d2 / np.where(d2 - d6 == 0, 1e-18, d2 - d6), 0, 1)
    setb(m, 1 - t, zero, t)
    m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    t = np.clip((d4 - d3) / np.where((d4 - d3) + (d5 - d6) == 0, 1e-18, (d4 - d3) + (d5 - d6)), 0, 1)
    setb(m, zero, 1 - t, t)
    bary = np.clip(bary, 0, 1)
    bary /= bary.sum(1, keepdims=True)
    q = a * bary[:, :1] + b * bary[:, 1:2] + c * bary[:, 2:3]
    return q, bary


def top4(weights):
    """Converte pesos densos (N, ossos) em JOINTS_0/WEIGHTS_0."""
    idx = np.argsort(-weights, axis=1)[:, :4]
    w = np.take_along_axis(weights, idx, axis=1)
    w = np.where(w < 1e-3, 0, w)
    s = w.sum(1, keepdims=True)
    fallback = s[:, 0] <= 0
    w = w / np.where(s <= 0, 1, s)
    if fallback.any():
        w[fallback] = [1, 0, 0, 0]
    # Indices ociosos apontam para 0 com peso 0.
    idx = np.where(w > 0, idx, 0)
    return idx.astype(np.uint16), w.astype(np.float32)
